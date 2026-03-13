"""
Admin metrics service — GCP cost tracking and usage estimation.

Provides two approaches:
1. BigQuery billing export (accurate, requires GCP Console setup)
2. Usage-based estimation from Firestore doc counts + known pricing (always available)
"""

from datetime import datetime, timezone, timedelta

# ── GCP Pricing constants (us-east1, as of 2025) ─────────────────────────
# Cloud Run
CR_CPU_PER_VCPU_SEC = 0.00002400   # per vCPU-second
CR_MEM_PER_GIB_SEC = 0.00000250    # per GiB-second
CR_REQUEST_PER_MILLION = 0.40      # per million requests
CR_FREE_REQUESTS = 2_000_000       # free tier per month
CR_FREE_CPU_SEC = 180_000          # 50 free vCPU-hours
CR_FREE_MEM_GIB_SEC = 360_000      # 100 free GiB-hours

# Firestore
FS_READ_PER_100K = 0.036           # per 100K reads
FS_WRITE_PER_100K = 0.108          # per 100K writes
FS_DELETE_PER_100K = 0.012         # per 100K deletes
FS_STORAGE_PER_GIB = 0.108         # per GiB-month
FS_FREE_READS = 50_000             # free per day
FS_FREE_WRITES = 20_000            # free per day
FS_FREE_STORAGE_GIB = 1.0          # free


def get_gcp_costs_from_bigquery(project_id: str = "statusrooster",
                                dataset: str = "billing_export",
                                days: int = 30) -> dict | None:
    """
    Query BigQuery billing export for actual GCP costs.
    Returns None if the table doesn't exist or BigQuery isn't set up.
    """
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=project_id)

        # Find the billing export table (auto-named by GCP)
        tables = list(client.list_tables(f"{project_id}.{dataset}"))
        if not tables:
            return None

        table_id = f"{project_id}.{dataset}.{tables[0].table_id}"
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        query = f"""
        SELECT
            service.description AS service,
            DATE(usage_start_time) AS date,
            SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net_cost
        FROM `{table_id}`
        WHERE DATE(usage_start_time) >= '{cutoff}'
        GROUP BY service, date
        ORDER BY date DESC, net_cost DESC
        """

        rows = list(client.query(query).result())
        if not rows:
            return {"daily": [], "by_service": {}, "total": 0, "source": "bigquery"}

        daily = []
        by_service = {}
        total = 0
        for row in rows:
            daily.append({
                "date": row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date),
                "service": row.service,
                "cost": round(float(row.net_cost), 4),
            })
            by_service[row.service] = by_service.get(row.service, 0) + float(row.net_cost)
            total += float(row.net_cost)

        # Round service totals
        by_service = {k: round(v, 2) for k, v in sorted(by_service.items(), key=lambda x: -x[1])}

        return {
            "daily": daily,
            "by_service": by_service,
            "total": round(total, 2),
            "days": days,
            "source": "bigquery",
        }

    except Exception as e:
        print(f"[admin_metrics] BigQuery cost query failed: {e}")
        return None


def estimate_gcp_costs(db, monitors_count: int, checks_per_day: int,
                       users_count: int) -> dict:
    """
    Estimate monthly GCP costs based on current usage patterns.
    Uses known pricing and observable metrics.
    """
    # ── Cloud Run estimates ──
    # Each cron check cycle: ~monitors_count requests to primary
    # Workers get ~monitors_count requests each (3 workers)
    # Assume 1 cron run per minute = 1440/day
    cron_runs_per_day = 1440
    # Each run checks monitors that are due (based on interval)
    # Average 60s interval = each monitor checked ~1440 times/day
    # But we have actual checks_per_day from the admin
    total_requests_per_month = checks_per_day * 30 * 4  # x4 for primary + 3 workers
    # User page views estimated at 10x users per day
    page_views_per_month = users_count * 10 * 30
    total_cr_requests = total_requests_per_month + page_views_per_month

    billable_requests = max(0, total_cr_requests - CR_FREE_REQUESTS)
    cr_request_cost = (billable_requests / 1_000_000) * CR_REQUEST_PER_MILLION

    # CPU: each check ~0.1s of CPU, each page view ~0.05s
    cpu_seconds = (checks_per_day * 30 * 4 * 0.1) + (page_views_per_month * 0.05)
    billable_cpu = max(0, cpu_seconds - CR_FREE_CPU_SEC)
    cr_cpu_cost = billable_cpu * CR_CPU_PER_VCPU_SEC

    # Memory: assume 256MB instances, same seconds as CPU
    mem_gib_seconds = cpu_seconds * 0.25
    billable_mem = max(0, mem_gib_seconds - CR_FREE_MEM_GIB_SEC)
    cr_mem_cost = billable_mem * CR_MEM_PER_GIB_SEC

    cr_total = round(cr_request_cost + cr_cpu_cost + cr_mem_cost, 2)

    # ── Firestore estimates ──
    # Reads: each check reads 1 monitor doc + writes 1 check doc
    # Dashboard loads read all monitors for a user
    # Cron reads all monitors each cycle
    reads_per_day = (checks_per_day * 2) + (cron_runs_per_day * monitors_count) + (users_count * 10 * monitors_count / max(users_count, 1))
    writes_per_day = checks_per_day + (checks_per_day * 0.1)  # checks + monitor updates

    reads_per_month = reads_per_day * 30
    writes_per_month = writes_per_day * 30
    billable_reads = max(0, reads_per_month - (FS_FREE_READS * 30))
    billable_writes = max(0, writes_per_month - (FS_FREE_WRITES * 30))

    fs_read_cost = (billable_reads / 100_000) * FS_READ_PER_100K
    fs_write_cost = (billable_writes / 100_000) * FS_WRITE_PER_100K

    # Storage: estimate based on check doc count
    # Each check doc ~500 bytes, each monitor ~2KB, each user ~1KB
    total_checks_stored = checks_per_day * 30  # ~30 days retention
    storage_bytes = (total_checks_stored * 500) + (monitors_count * 2000) + (users_count * 1000)
    storage_gib = storage_bytes / (1024 ** 3)
    billable_storage = max(0, storage_gib - FS_FREE_STORAGE_GIB)
    fs_storage_cost = billable_storage * FS_STORAGE_PER_GIB

    fs_total = round(fs_read_cost + fs_write_cost + fs_storage_cost, 2)

    # ── Cloud Scheduler ──
    # 3 free jobs, $0.10/job/month after that
    scheduler_jobs = 2  # /cron/check + /cron/cleanup
    scheduler_cost = max(0, (scheduler_jobs - 3)) * 0.10

    # ── Networking / Egress ──
    # First 1GB free, then $0.12/GB
    # Estimate: each check response ~1KB, page ~50KB
    egress_gb = ((checks_per_day * 30 * 4 * 1) + (page_views_per_month * 50)) / (1024 ** 2)
    egress_cost = round(max(0, egress_gb - 1) * 0.12, 2)

    grand_total = round(cr_total + fs_total + scheduler_cost + egress_cost, 2)

    return {
        "source": "estimated",
        "cloud_run": {
            "requests": total_cr_requests,
            "billable_requests": billable_requests,
            "request_cost": round(cr_request_cost, 2),
            "cpu_cost": round(cr_cpu_cost, 2),
            "memory_cost": round(cr_mem_cost, 2),
            "total": cr_total,
        },
        "firestore": {
            "reads_per_month": int(reads_per_month),
            "writes_per_month": int(writes_per_month),
            "billable_reads": int(billable_reads),
            "billable_writes": int(billable_writes),
            "read_cost": round(fs_read_cost, 2),
            "write_cost": round(fs_write_cost, 2),
            "storage_gib": round(storage_gib, 3),
            "storage_cost": round(fs_storage_cost, 2),
            "total": fs_total,
        },
        "scheduler": {"jobs": scheduler_jobs, "total": round(scheduler_cost, 2)},
        "egress": {"gb": round(egress_gb, 2), "total": egress_cost},
        "total": grand_total,
    }
