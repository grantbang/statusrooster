"""
Admin metrics service — GCP cost tracking via BigQuery billing export.
"""

from datetime import datetime, timezone, timedelta


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
