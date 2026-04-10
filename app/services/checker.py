import httpx
import asyncio
import time
import logging
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.config import settings
from app.models.monitor import get_all_monitors, get_due_monitors, update_monitor
from app.models.check import create_check, create_checks_batch
from app.models.incident import create_incident, resolve_incident, get_open_incident, log_incident_event
from app.services.alerts import send_down_alert, send_recovery_alert, send_ssl_expiry_alert, send_keyword_alert, send_threshold_alert, send_threshold_recovery_alert, send_webhook_notification

# Import pure check functions from checker_core (shared with regional workers)
from checker_core import (
    validate_url_not_internal,
    check_url,
    check_url_with_retry,
    check_json_api,
    check_ssl_certificate,
    grab_ssl_info,
    _check_keyword_expression,
    _check_threshold_condition,
    _resolve_json_path,
    _evaluate_assertion,
)

logger = logging.getLogger(__name__)

# ── Multi-Region Configuration ────────────────────────────────────────────────

WORKER_REGIONS = {
    "us-east1": settings.WORKER_URL_US_EAST1,
    "us-west1": settings.WORKER_URL_US_WEST1,
    "europe-west1": settings.WORKER_URL_EU_WEST1,
    "asia-east1": settings.WORKER_URL_ASIA_EAST1,
}

# All users get the same 4 regions (australia-southeast1 dropped — GCP quota)
CHECK_REGIONS = ["us-east1", "us-west1", "europe-west1", "asia-east1"]

# Limit concurrent outbound connections to avoid socket exhaustion
CHECK_CONCURRENCY = 50
_check_semaphore = asyncio.Semaphore(CHECK_CONCURRENCY)

# Prevent overlapping or too-frequent run_checks() cycles
_run_checks_lock = asyncio.Lock()
_last_cycle_start: float = 0  # monotonic timestamp of last cycle start

# Shared httpx client for connection pooling (lazily created)
_shared_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx.AsyncClient with connection pooling."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
            timeout=httpx.Timeout(30.0),
        )
        logger.info("[checker] Created shared httpx.AsyncClient (pool: 100 max, 50 keepalive)")
    return _shared_client


async def close_client():
    """Close the shared httpx client gracefully."""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None
        logger.info("[checker] Closed shared httpx.AsyncClient")


def is_in_maintenance_window(monitor: dict) -> bool:
    """Check if the current UTC time falls within any of the monitor's maintenance windows."""
    # Support both legacy single window and new array format
    windows = monitor.get("maintenance_windows") or []
    legacy = monitor.get("maintenance_window")
    if legacy and isinstance(legacy, dict):
        windows = [legacy]  # backwards compatibility
    if not windows:
        return False

    now = datetime.now(timezone.utc)
    day_name = now.strftime("%A")  # Monday, Tuesday, etc.
    now_minutes = now.hour * 60 + now.minute

    for mw in windows:
        mw_day = mw.get("day", "")
        if mw_day and mw_day.lower() != "daily" and mw_day.lower() != day_name.lower():
            continue

        try:
            start_h, start_m = map(int, mw.get("start_utc", "00:00").split(":"))
            end_h, end_m = map(int, mw.get("end_utc", "00:00").split(":"))
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m

            if start_minutes <= end_minutes:
                if start_minutes <= now_minutes <= end_minutes:
                    return True
            else:
                # Overnight window (e.g., 23:00 - 03:00)
                if now_minutes >= start_minutes or now_minutes <= end_minutes:
                    return True
        except Exception:
            continue

    return False


def _percentile(sorted_values: list, pct: float) -> float:
    """Compute a percentile from a pre-sorted list of values."""
    if not sorted_values:
        return 0
    idx = int(len(sorted_values) * pct)
    idx = min(idx, len(sorted_values) - 1)
    return sorted_values[idx]


# ── Multi-Region Dispatcher (Phase 2.4) ───────────────────────────────────────

def _serialize_monitor_for_worker(monitor: dict) -> dict:
    """Strip a monitor dict down to only fields needed for checking.
    Removes Firestore metadata, user info, and stats — keeps only
    the fields that checker_core functions need to run a check."""
    return {
        "id": monitor.get("id"),
        "url": monitor.get("url", ""),
        "monitor_type": monitor.get("monitor_type", "http"),
        "timeout": monitor.get("timeout", 10),
        "expected_status_code": monitor.get("expected_status_code"),
        "http_method": monitor.get("http_method", "GET"),
        "follow_redirects": monitor.get("follow_redirects", True),
        "basic_auth_user": monitor.get("basic_auth_user", ""),
        "basic_auth_pass": monitor.get("basic_auth_pass", ""),
        "bearer_token": monitor.get("bearer_token", ""),
        "request_body": monitor.get("request_body", ""),
        "request_content_type": monitor.get("request_content_type", ""),
        "custom_headers": monitor.get("custom_headers", []),
        "auth_header": monitor.get("auth_header", ""),
        "json_assertions": monitor.get("json_assertions", []),
        "keyword": monitor.get("keyword", ""),
        "ssl_domain": monitor.get("ssl_domain", ""),
    }


async def _dispatch_to_worker(region: str, monitors: list[dict]) -> dict | None:
    """Send a batch of monitors to a regional worker and return results.
    
    Returns: {"region": str, "results": [list of result dicts]} or None on failure.
    Timeout: 30 seconds per worker call.
    """
    worker_url = WORKER_REGIONS.get(region, "")
    if not worker_url:
        return None
    
    try:
        client = await _get_client()
        resp = await client.post(
            f"{worker_url}/check-batch",
            json={"monitors": monitors},
            headers={
                "X-Worker-Secret": settings.WORKER_SECRET,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning(f"[checker] Worker {region} returned {resp.status_code}: {resp.text[:200]}")
            return None
    except httpx.TimeoutException:
        logger.warning(f"[checker] Worker {region} timed out")
        return None
    except Exception as e:
        logger.warning(f"[checker] Worker {region} failed: {e}")
        return None


def _aggregate_multi_region_results(monitor: dict, local_result: dict, 
                                      worker_results: list[dict]) -> dict:
    """Combine results from local check + regional workers.
    
    Aggregation rules:
    1. is_up = True if MAJORITY of regions report UP
       (e.g., 3 of 4 regions)
    2. response_ms = average across all regions
    3. response_ms_by_region = dict of {region: ms} for UI display
    4. status_code = from primary region (us-east1 / local)
    5. regions_checked = total number of regions that responded
    6. regions_up = number of regions that reported UP
    """
    all_results = []
    response_by_region = {}
    
    # Add local result
    local_is_up = local_result.get("result", {}).get("is_up", False)
    local_ms = local_result.get("result", {}).get("response_ms")
    all_results.append({
        "region": "us-east1",
        "is_up": local_is_up,
        "response_ms": local_ms,
        "status_code": local_result.get("result", {}).get("status_code"),
        "error": local_result.get("result", {}).get("error_message"),
    })
    if local_ms and local_ms > 0:
        response_by_region["us-east1"] = local_ms

    # Add worker results
    for wr in worker_results:
        if not wr:
            continue
        region = wr.get("region", "unknown")
        for r in wr.get("results", []):
            if r.get("monitor_id") == monitor.get("id"):
                all_results.append({
                    "region": region,
                    "is_up": r.get("is_up", False),
                    "response_ms": r.get("response_ms"),
                    "status_code": r.get("status_code"),
                    "error": r.get("error"),
                })
                ms = r.get("response_ms")
                if ms and ms > 0:
                    response_by_region[region] = ms
    
    # Majority vote
    total = len(all_results)
    up_count = sum(1 for r in all_results if r["is_up"])
    majority_up = up_count > (total / 2)
    
    # Average response time
    response_times = [r["response_ms"] for r in all_results if r.get("response_ms") and r["response_ms"] > 0]
    avg_ms = round(sum(response_times) / len(response_times), 2) if response_times else None
    
    # Build merged result — start with local_result structure, overlay multi-region data
    merged = dict(local_result)
    merged["result"] = dict(local_result.get("result", {}))
    merged["result"]["is_up"] = majority_up
    merged["result"]["response_ms"] = avg_ms
    merged["result"]["response_ms_by_region"] = response_by_region
    merged["result"]["regions_checked"] = total
    merged["result"]["regions_up"] = up_count
    merged["result"]["region_results"] = all_results

    return merged


async def _check_single_monitor_multi_region(monitor: dict, now: datetime) -> dict | None:
    """Check a monitor from multiple regions and aggregate results.
    
    Flow:
    1. Determine which regions are active (all users get the same 4 regions)
    2. Run local check (us-east1) — always happens, even if workers are down
    3. Dispatch to remote workers concurrently
    4. Wait for all results (with 30s timeout per worker)
    5. Aggregate using majority vote
    6. Return merged result dict
    
    Falls back to local-only check if:
    - No workers are configured (WORKER_SECRET empty or no WORKER_URLs set)
    - Monitor type is heartbeat (passive, not active)
    - Monitor type is ssl (certs are global, multi-region adds nothing)
    - All workers fail (local result is still used)
    """
    mtype = monitor.get("monitor_type", "http")
    
    # Heartbeat and SSL don't benefit from multi-region
    if mtype in ("heartbeat", "ssl"):
        return await _check_single_monitor_inner(monitor, now)
    
    # Check if multi-region is configured
    if not settings.WORKER_SECRET:
        return await _check_single_monitor_inner(monitor, now)
    
    # Determine active regions (all users get the same 4 regions)
    active_regions = [r for r in CHECK_REGIONS if r == "us-east1" or WORKER_REGIONS.get(r)]
    
    # If only primary region is available, fall back to local
    if len(active_regions) <= 1:
        return await _check_single_monitor_inner(monitor, now)
    
    # Step 1: Run local check (always, as baseline)
    local_result = await _check_single_monitor_inner(monitor, now)
    if local_result is None:
        return None  # Monitor was skipped (paused, misconfigured, etc.)
    
    # Step 2: Dispatch to remote workers concurrently
    remote_regions = [r for r in active_regions if r != "us-east1"]
    serialized = [_serialize_monitor_for_worker(monitor)]
    
    worker_tasks = [_dispatch_to_worker(r, serialized) for r in remote_regions]
    worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)
    
    # Filter out exceptions and None results
    valid_worker_results = [
        r for r in worker_results 
        if r is not None and not isinstance(r, Exception)
    ]
    
    # Step 3: Aggregate
    if not valid_worker_results:
        # All workers failed — use local result only, but tag it
        local_result.setdefault("result", {})["regions_checked"] = 1
        local_result["result"]["regions_up"] = 1 if local_result["result"].get("is_up") else 0
        local_result["result"]["response_ms_by_region"] = {"us-east1": local_result["result"].get("response_ms")}
        return local_result
    
    return _aggregate_multi_region_results(monitor, local_result, valid_worker_results)


# ── Single Monitor Check ──────────────────────────────────────────────────────

async def _check_single_monitor(monitor: dict, now: datetime) -> dict | None:
    """Perform the network check for a single monitor (with concurrency limiting).
    Routes to multi-region if configured, otherwise local-only."""
    async with _check_semaphore:
        # Use multi-region if workers are configured
        if settings.WORKER_SECRET and monitor.get("monitor_type") in ("http", "json_api"):
            return await _check_single_monitor_multi_region(monitor, now)
        return await _check_single_monitor_inner(monitor, now)


async def _check_single_monitor_inner(monitor: dict, now: datetime) -> dict | None:
    """Inner check logic — runs inside the semaphore. Uses shared httpx client."""
    mtype = monitor.get("monitor_type", "http")
    client = await _get_client()

    if mtype == "heartbeat":
        heartbeat_interval = monitor.get("heartbeat_interval", 300)
        grace_period = monitor.get("heartbeat_grace_period", 30)
        last_hb = monitor.get("last_heartbeat")

        last_hb_dt = None
        if last_hb:
            if isinstance(last_hb, str):
                try:
                    last_hb_dt = datetime.fromisoformat(last_hb.replace("Z", "+00:00"))
                except ValueError:
                    pass
            elif hasattr(last_hb, 'timestamp'):
                last_hb_dt = last_hb if last_hb.tzinfo else last_hb.replace(tzinfo=timezone.utc)

        if last_hb_dt is None:
            # Never pinged — keep status as pending, don't mark down
            return {
                "monitor": monitor,
                "result": {"status_code": None, "response_ms": 0, "is_up": None, "body": "awaiting_first_ping"},
            }
        else:
            overdue = (now - last_hb_dt).total_seconds()
            is_up = overdue <= heartbeat_interval + grace_period

        return {
            "monitor": monitor,
            "result": {"status_code": 200 if is_up else None, "response_ms": 0, "is_up": is_up, "body": ""},
        }

    elif mtype == "ssl":
        ssl_domain = monitor.get("ssl_domain", "")
        threshold_days = monitor.get("ssl_expiry_threshold_days", 14)
        if not ssl_domain:
            return None  # skip

        loop = asyncio.get_event_loop()
        ssl_result = await loop.run_in_executor(None, check_ssl_certificate, ssl_domain)

        if ssl_result.get("error"):
            is_up = False
            new_monitor_status = "down"
        elif ssl_result["ssl_expiry_days"] is not None:
            if ssl_result["ssl_expiry_days"] <= 0:
                is_up, new_monitor_status = False, "down"
            elif ssl_result["ssl_expiry_days"] <= threshold_days:
                is_up, new_monitor_status = True, "warn"
            else:
                is_up, new_monitor_status = True, "up"
        else:
            is_up, new_monitor_status = False, "down"

        return {
            "monitor": monitor,
            "result": {"status_code": 200 if is_up else None, "response_ms": 0, "is_up": is_up, "body": ""},
            "ssl_result": ssl_result,
            "new_monitor_status": new_monitor_status,
        }

    elif mtype == "json_api":
        timeout_val = monitor.get("timeout", 10)
        expected_code = monitor.get("expected_status_code")
        auth_header = monitor.get("auth_header", "")
        assertions = monitor.get("json_assertions") or []
        http_method = monitor.get("http_method", "GET")
        req_body = monitor.get("request_body", "")
        req_ct = monitor.get("request_content_type", "")

        result = await check_json_api(
            monitor["url"], timeout=timeout_val, expected_status_code=expected_code,
            auth_header=auth_header, assertions=assertions, client=client,
            http_method=http_method, request_body=req_body, request_content_type=req_ct,
            custom_headers=monitor.get("custom_headers"),
        )
        # Grab SSL info concurrently for HTTPS URLs
        ssl_info = {}
        if monitor.get("url", "").startswith("https"):
            loop = asyncio.get_event_loop()
            ssl_info = await loop.run_in_executor(None, grab_ssl_info, monitor["url"])
        return {"monitor": monitor, "result": result, "ssl_info": ssl_info}

    else:
        # HTTP monitors
        timeout_val = monitor.get("timeout", 10)
        expected_code = monitor.get("expected_status_code")
        http_method = monitor.get("http_method", "GET")
        follow_redir = monitor.get("follow_redirects", True)
        ba_user = monitor.get("basic_auth_user", "")
        ba_pass = monitor.get("basic_auth_pass", "")
        bearer_tok = monitor.get("bearer_token", "")
        req_body = monitor.get("request_body", "")
        req_ct = monitor.get("request_content_type", "")
        cust_headers = monitor.get("custom_headers") or []

        result = await check_url_with_retry(
            monitor["url"], timeout=timeout_val, expected_status_code=expected_code,
            http_method=http_method, follow_redirects=follow_redir,
            basic_auth_user=ba_user, basic_auth_pass=ba_pass,
            bearer_token=bearer_tok,
            request_body=req_body, request_content_type=req_ct,
            custom_headers=cust_headers,
            client=client,
        )
        # Grab SSL info concurrently for HTTPS URLs
        ssl_info = {}
        if monitor.get("url", "").startswith("https"):
            loop = asyncio.get_event_loop()
            ssl_info = await loop.run_in_executor(None, grab_ssl_info, monitor["url"])
        return {"monitor": monitor, "result": result, "ssl_info": ssl_info}


async def check_monitor_now(monitor: dict) -> dict:
    """
    Run an immediate on-demand check for a single monitor.
    Bypasses the scheduler — runs the full check inline and returns a result dict.
    Used by the "Check now" button on monitor detail.

    Returns:
        {
            "is_up": bool,
            "status_code": int | None,
            "response_ms": int | None,
            "error": str | None,
            "ssl_expiry": str | None,
            "ssl_expiry_days": int | None,
            "checked_at": str (ISO),
        }
    """
    now = datetime.now(timezone.utc)
    mtype = monitor.get("monitor_type", "http")

    try:
        # Use multi-region path if workers are configured
        if settings.WORKER_SECRET and mtype in ("http", "json_api"):
            cr = await _check_single_monitor_multi_region(monitor, now)
        else:
            cr = await _check_single_monitor_inner(monitor, now)
    except Exception as e:
        return {
            "is_up": False,
            "status_code": None,
            "response_ms": None,
            "error": str(e),
            "ssl_expiry": None,
            "ssl_expiry_days": None,
            "checked_at": now.isoformat(),
        }

    if cr is None:
        return {
            "is_up": False,
            "status_code": None,
            "response_ms": None,
            "error": "Monitor skipped (paused or misconfigured)",
            "ssl_expiry": None,
            "ssl_expiry_days": None,
            "checked_at": now.isoformat(),
        }

    result = cr["result"]
    ssl_info = cr.get("ssl_info") or cr.get("ssl_result") or {}

    # Persist region data to the monitor doc so the detail page can display it
    regions_checked = result.get("regions_checked", 1)
    regions_up = result.get("regions_up", regions_checked if result.get("is_up") else 0)
    response_by_region = result.get("response_ms_by_region", {})
    if regions_checked > 1:
        try:
            db = get_db()
            db.collection("monitors").document(monitor["id"]).update({
                "last_regions_checked": regions_checked,
                "last_regions_up": regions_up,
                "last_response_by_region": response_by_region,
            })
        except Exception as e:
            logger.warning(f"[checker] Failed to update region data on check-now: {e}")

    # ssl_expiry may be a datetime object — convert to ISO string for JSON serialization
    ssl_expiry = ssl_info.get("ssl_expiry")
    if ssl_expiry and hasattr(ssl_expiry, "isoformat"):
        ssl_expiry = ssl_expiry.isoformat()

    return {
        "is_up": result.get("is_up", False),
        "status_code": result.get("status_code"),
        "response_ms": result.get("response_ms"),
        "error": result.get("error_message") or (None if result.get("is_up") else "Check failed"),
        "ssl_expiry": ssl_expiry,
        "ssl_expiry_days": ssl_info.get("ssl_expiry_days"),
        "monitor_type": mtype,
        "checked_at": now.isoformat(),
    }


async def run_checks():
    """
    Run checks for ALL monitors concurrently. Called by the cron endpoint.
    Returns summary of results.
    """
    global _last_cycle_start

    if _run_checks_lock.locked():
        logger.warning("[checker] run_checks() already in progress, skipping overlapping invocation")
        return {"total": 0, "up": 0, "down": 0, "skipped": 0, "skipped_reason": "overlap"}

    # Reject Cloud Scheduler retries/duplicates — must be at least 45s since last cycle
    since_last = time.monotonic() - _last_cycle_start
    if _last_cycle_start > 0 and since_last < 45:
        logger.warning(f"[checker] Ignoring duplicate cron trigger ({since_last:.0f}s since last cycle)")
        return {"total": 0, "up": 0, "down": 0, "skipped": 0, "skipped_reason": "too_soon"}

    _last_cycle_start = time.monotonic()

    async with _run_checks_lock:
        return await _run_checks_inner()


async def _run_checks_inner():
    """Inner implementation of run_checks(), called under the lock."""
    t_cycle_start = time.monotonic()
    db = get_db()
    # Use get_due_monitors() — filters paused=False at Firestore level,
    # capped at 500 monitors to prevent memory blowout as the collection grows.
    monitors = get_due_monitors(db)

    results = {"total": len(monitors), "up": 0, "down": 0, "skipped": 0}

    now = datetime.now(timezone.utc)

    # Phase 1: Filter monitors that are due for checking (interval elapsed)
    # Note: paused monitors are already excluded by get_due_monitors()
    due_monitors = []
    for monitor in monitors:
        # SSL monitors only need infrequent checks (hourly) — cert expiry doesn't change by the second
        mtype = monitor.get("monitor_type", "http")
        if mtype == "ssl":
            check_interval = 3600  # 1 hour
        else:
            check_interval = monitor.get("check_interval", 300)
        last_checked = monitor.get("last_checked")
        if last_checked:
            if isinstance(last_checked, str):
                try:
                    last_checked_dt = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
                except ValueError:
                    last_checked_dt = None
            elif hasattr(last_checked, 'timestamp'):
                last_checked_dt = last_checked if last_checked.tzinfo else last_checked.replace(tzinfo=timezone.utc)
            else:
                last_checked_dt = None

            if last_checked_dt:
                elapsed = (now - last_checked_dt).total_seconds()
                if elapsed < check_interval - 1:  # 1s tolerance for sub-second timing jitter
                    if check_interval == 60:
                        logger.info(f"[interval-debug] SKIP {monitor.get('name','?')} id={monitor.get('id','?')[:8]}: elapsed={elapsed:.1f}s now={now.isoformat()} lc={last_checked_dt.isoformat()}")
                    results["skipped"] += 1
                    continue
                elif check_interval == 60:
                    logger.info(f"[interval-debug] PASS {monitor.get('name','?')} id={monitor.get('id','?')[:8]}: elapsed={elapsed:.1f}s")

        due_monitors.append(monitor)

    # Phase 2: Run all network checks concurrently (bounded by semaphore)
    t_start = time.monotonic()
    check_tasks = [_check_single_monitor(m, now) for m in due_monitors]
    check_results = await asyncio.gather(*check_tasks, return_exceptions=True)
    t_checks = time.monotonic() - t_start
    logger.info(f"[checker] Phase 2: {len(due_monitors)} checks completed in {t_checks:.1f}s (concurrency={CHECK_CONCURRENCY})")

    # Phase 3: Process results — Firestore writes, alerts, incidents
    t_writes = time.monotonic()
    check_batch = []  # Accumulate check records for batch write
    # Instrumentation counters
    response_times = []  # Collect response_ms for percentile calculation
    retry_count = 0
    fw_writes = 0  # Firestore write operations
    errors_by_type = {}  # {monitor_type: down_count}
    for cr in check_results:
        if cr is None:
            results["skipped"] += 1
            continue
        if isinstance(cr, Exception):
            print(f"[checker] check failed with exception: {cr}")
            results["skipped"] += 1
            continue

        monitor = cr["monitor"]
        result = cr["result"]
        ssl_result = cr.get("ssl_result")
        new_monitor_status = cr.get("new_monitor_status")
        ssl_info = cr.get("ssl_info") or {}  # Pre-fetched during Phase 2

        # Heartbeat awaiting first ping — skip processing, keep status as pending
        if result.get("is_up") is None:
            results["skipped"] += 1
            continue

        # Accumulate check for batch write (instead of individual create_check)
        check_batch.append({
            "monitor_id": monitor["id"],
            "status_code": result["status_code"],
            "response_ms": result["response_ms"],
            "is_up": result["is_up"],
            "regions_checked": result.get("regions_checked", 1),
            "regions_up": result.get("regions_up", 1 if result["is_up"] else 0),
            "response_ms_by_region": result.get("response_ms_by_region", {}),
        })

        # Instrumentation: collect per-check metrics
        if result["response_ms"] is not None and result["response_ms"] > 0:
            response_times.append(result["response_ms"])
        if result.get("retried"):
            retry_count += 1
        if not result["is_up"]:
            mtype = monitor.get("monitor_type", "http")
            errors_by_type[mtype] = errors_by_type.get(mtype, 0) + 1

        # Update monitor stats
        previous_status = monitor.get("status", "pending")
        if monitor.get("monitor_type") == "ssl" and new_monitor_status:
            new_status = new_monitor_status
        else:
            new_status = "up" if result["is_up"] else "down"

        checks_total = monitor.get("checks_total", 0) + 1
        checks_failed = monitor.get("checks_failed", 0) + (0 if result["is_up"] else 1)
        uptime_percent = round(((checks_total - checks_failed) / checks_total) * 100, 2)

        status_changed = previous_status != new_status

        monitor_updates = {
            "status": new_status,
            "last_checked": now,  # cycle start time — must match Phase 1's 'now' for interval math
            "last_check_completed": datetime.now(timezone.utc),  # actual time — for UI display
            "last_status_code": result["status_code"],
            "last_response_ms": result["response_ms"],
            "uptime_percent": uptime_percent,
            "checks_total": checks_total,
            "checks_failed": checks_failed,
        }

        # Multi-region data (only meaningful for HTTP/JSON monitors)
        mtype = monitor.get("monitor_type", "http")
        if mtype in ("http", "json_api"):
            regions_checked = result.get("regions_checked", 1)
            regions_up = result.get("regions_up", regions_checked if result["is_up"] else 0)
            response_by_region = result.get("response_ms_by_region", {})
            monitor_updates["last_regions_checked"] = regions_checked
            monitor_updates["last_regions_up"] = regions_up
            monitor_updates["last_response_by_region"] = response_by_region
            # Ensure region_results is always populated (even for local-only checks)
            if not result.get("region_results"):
                result["region_results"] = [{
                    "region": "us-east1",
                    "is_up": result["is_up"],
                    "status_code": result.get("status_code"),
                    "response_ms": result.get("response_ms"),
                    "error": result.get("error_message") or "",
                }]
        else:
            regions_checked = None
            regions_up = None

        if status_changed:
            monitor_updates["last_status_change"] = datetime.now(timezone.utc)

        # ----- Incrementally update daily_uptime_bars on monitor doc -----
        today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        bars = list(monitor.get("daily_uptime_bars") or [])
        if bars and bars[-1].get("date") == today_key:
            bars[-1]["total"] = bars[-1].get("total", 0) + 1
            if result["is_up"]:
                bars[-1]["up"] = bars[-1].get("up", 0) + 1
        else:
            bars.append({"date": today_key, "total": 1, "up": 1 if result["is_up"] else 0})
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        bars = [b for b in bars if b["date"] >= cutoff_date]
        monitor_updates["daily_uptime_bars"] = bars

        # ----- Incrementally update hourly_uptime_bars on monitor doc -----
        hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
        hbars = list(monitor.get("hourly_uptime_bars") or [])
        if hbars and hbars[-1].get("hour") == hour_key:
            hbars[-1]["total"] = hbars[-1].get("total", 0) + 1
            if result["is_up"]:
                hbars[-1]["up"] = hbars[-1].get("up", 0) + 1
        else:
            hbars.append({"hour": hour_key, "total": 1, "up": 1 if result["is_up"] else 0})
        cutoff_hour = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d-%H")
        hbars = [b for b in hbars if b["hour"] >= cutoff_hour]
        monitor_updates["hourly_uptime_bars"] = hbars

        # ----- SSL Expiry (pre-fetched in Phase 2) — HTTP monitors -----
        if monitor.get("monitor_type") == "http" and ssl_info.get("ssl_expiry"):
            monitor_updates["ssl_expiry"] = ssl_info["ssl_expiry"]
            monitor_updates["ssl_issuer"] = ssl_info["ssl_issuer"]
            monitor_updates["ssl_expiry_days"] = ssl_info["ssl_expiry_days"]

        # ----- SSL Expiry (pre-fetched in Phase 2) — JSON/API monitors -----
        if monitor.get("monitor_type") == "json_api" and ssl_info.get("ssl_expiry"):
            monitor_updates["ssl_expiry"] = ssl_info["ssl_expiry"]
            monitor_updates["ssl_issuer"] = ssl_info["ssl_issuer"]
            monitor_updates["ssl_expiry_days"] = ssl_info["ssl_expiry_days"]

        # ----- SSL cert fields for SSL monitors (merged into single update) -----
        if monitor.get("monitor_type") == "ssl" and ssl_result:
            if ssl_result.get("ssl_expiry"):
                monitor_updates["ssl_expiry"] = ssl_result["ssl_expiry"]
                monitor_updates["ssl_issuer"] = ssl_result["ssl_issuer"]
                monitor_updates["ssl_expiry_days"] = ssl_result["ssl_expiry_days"]

        if result["is_up"]:
            results["up"] += 1
        else:
            results["down"] += 1

        # ----- Check if in maintenance window (suppress alerts, not checks) -----
        in_maintenance = is_in_maintenance_window(monitor)

        # ----- Keyword Check — HTTP monitors only -----
        is_http = monitor.get("monitor_type", "http") == "http"
        keyword = monitor.get("keyword", "")
        keyword_failed = False
        if is_http and keyword and result["is_up"]:
            body_lower = result.get("body", "").lower()
            keyword_failed = not _check_keyword_expression(keyword, body_lower)
            was_keyword_failing = monitor.get("keyword_failing", False)
            if keyword_failed:
                monitor_updates["keyword_failing"] = True
                if not was_keyword_failing and not in_maintenance:
                    await send_keyword_alert(monitor, keyword)
                    print(f"[checker] KEYWORD MISSING: '{keyword}' not found on {monitor['name']}")
            else:
                if was_keyword_failing:
                    monitor_updates["keyword_failing"] = False

        # ----- Response Time Threshold — HTTP + JSON/API monitors -----
        # Hysteresis: require 2 consecutive violations to alert, 2 consecutive
        # sub-threshold checks to clear. Prevents flapping-induced alert spam.
        has_response = monitor.get("monitor_type") in ("http", "json_api")
        threshold = monitor.get("response_threshold_ms")
        if has_response and threshold and result["response_ms"] and result["is_up"]:
            threshold_str = str(threshold)
            threshold_violated = _check_threshold_condition(threshold_str, result["response_ms"])
            was_threshold_failing = monitor.get("threshold_failing", False)
            consecutive_threshold_failures = monitor.get("consecutive_threshold_failures", 0)
            consecutive_threshold_oks = monitor.get("consecutive_threshold_oks", 0)

            if threshold_violated:
                consecutive_threshold_failures += 1
                consecutive_threshold_oks = 0
                monitor_updates["consecutive_threshold_failures"] = consecutive_threshold_failures
                monitor_updates["consecutive_threshold_oks"] = 0

                # Only alert after 2 consecutive violations AND not already in failing state
                if consecutive_threshold_failures >= 2 and not was_threshold_failing and not in_maintenance:
                    monitor_updates["threshold_failing"] = True
                    monitor_updates["threshold_failing_since"] = datetime.now(timezone.utc)
                    await send_threshold_alert(monitor, result["response_ms"], threshold)
                    print(f"[checker] THRESHOLD: {monitor['name']} {result['response_ms']}ms violated condition '{threshold_str}' (2 consecutive)")
                elif consecutive_threshold_failures < 2:
                    print(f"[checker] THRESHOLD: {monitor['name']} {result['response_ms']}ms violated ({consecutive_threshold_failures}/2 — waiting for confirmation)")
            else:
                consecutive_threshold_oks += 1
                consecutive_threshold_failures = 0
                monitor_updates["consecutive_threshold_oks"] = consecutive_threshold_oks
                monitor_updates["consecutive_threshold_failures"] = 0

                # Only clear after 2 consecutive OK checks (hysteresis to prevent flapping)
                if was_threshold_failing and consecutive_threshold_oks >= 2:
                    monitor_updates["threshold_failing"] = False
                    monitor_updates["threshold_failing_since"] = None
                    if not in_maintenance:
                        await send_threshold_recovery_alert(monitor, result["response_ms"], threshold)
                        print(f"[checker] THRESHOLD RECOVERY: {monitor['name']} {result['response_ms']}ms back under threshold")

        # ----- SSL Expiry Alerts (14, 7, 3 days) — HTTP + JSON/API monitors (auto-detect) -----
        if monitor.get("monitor_type") in ("http", "json_api") and ssl_info.get("ssl_expiry_days") is not None:
            days_left = ssl_info["ssl_expiry_days"]
            last_alerted = monitor.get("ssl_expiry_alerted_days")
            # Find tightest applicable threshold (ascending so we match the smallest first)
            tightest = None
            for t in [3, 7, 14]:
                if days_left <= t:
                    tightest = t
                    break
            if tightest is not None and (last_alerted is None or last_alerted > tightest):
                if not in_maintenance:
                    await send_ssl_expiry_alert(monitor, days_left, ssl_info["ssl_expiry"])
                    monitor_updates["ssl_expiry_alerted_days"] = tightest

        # ----- SSL Monitor — Expiry alerts based on configured threshold -----
        if monitor.get("monitor_type") == "ssl" and ssl_result:
            threshold_days = monitor.get("ssl_expiry_threshold_days", 14)
            ssl_days = monitor.get("ssl_expiry_days") or ssl_result.get("ssl_expiry_days")
            if ssl_days is not None:
                last_alerted = monitor.get("ssl_expiry_alerted_days")
                if ssl_days <= threshold_days and last_alerted != threshold_days:
                    if not in_maintenance:
                        ssl_exp = monitor.get("ssl_expiry") or ssl_result.get("ssl_expiry")
                        await send_ssl_expiry_alert(monitor, ssl_days, ssl_exp)
                        monitor_updates["ssl_expiry_alerted_days"] = threshold_days

        # ----- Consecutive failure tracking (2 failures before alerting) -----
        prev_consecutive = monitor.get("consecutive_failures", 0)

        if not result["is_up"]:
            consecutive_failures = prev_consecutive + 1
            monitor_updates["consecutive_failures"] = consecutive_failures

            if consecutive_failures < 2:
                # First failure — don't change status, don't create incident
                print(f"[checker] {monitor['name']} failed 1/2 confirmation checks — waiting for confirmation")
                # Keep status as previous (don't flip to "down" yet)
                new_status = previous_status if previous_status != "pending" else "up"
                monitor_updates["status"] = new_status
                status_changed = False
            else:
                # 2+ consecutive failures — confirmed down
                new_status = "down"
                monitor_updates["status"] = new_status
                status_changed = previous_status != new_status
        else:
            # UP — reset consecutive failures
            if prev_consecutive > 0:
                monitor_updates["consecutive_failures"] = 0
            consecutive_failures = 0

        # ----- Status change detection + Incidents + Alerts -----
        if status_changed and new_status == "down":
            existing = get_open_incident(db, monitor["id"])
            if existing is None:
                incident = create_incident(
                    db,
                    monitor_id=monitor["id"],
                    monitor_name=monitor.get("name", ""),
                    monitor_url=monitor.get("url", ""),
                    status_code=result["status_code"],
                    response_ms=result["response_ms"],
                    failure_response_headers=result.get("response_headers") or {},
                    failure_error_message=result.get("error_message") or "",
                    regions_checked=regions_checked,
                    regions_up=regions_up,
                    region_results=result.get("region_results", []),
                    failure_response_body=(result.get("body") or "")[:2048],
                )
                log_incident_event(db, incident["id"], "detected", {
                    "status_code": result["status_code"],
                    "response_ms": result["response_ms"],
                    "regions_checked": regions_checked,
                    "regions_up": regions_up,
                    "region_results": result.get("region_results", []),
                })
                if not in_maintenance:
                    down_results = await send_down_alert(monitor, incident)
                    for channel, ok in down_results.items():
                        log_incident_event(db, incident["id"],
                                           f"alert_{channel}_{'sent' if ok else 'failed'}")
                    if monitor.get("webhook_url"):
                        await send_webhook_notification(monitor, "monitor.down", result)
                print(f"[checker] INCIDENT CREATED: {monitor['name']} is DOWN (confirmed after 2 consecutive failures)" +
                      (" (maintenance — alerts suppressed)" if in_maintenance else ""))
            else:
                print(f"[checker] {monitor['name']} still DOWN — incident already open, skipping alert")

        elif status_changed and new_status == "up":
            open_incident = get_open_incident(db, monitor["id"])
            if open_incident:
                resolved = resolve_incident(db, open_incident["id"])
                log_incident_event(db, resolved["id"], "resolved", {
                    "duration_seconds": resolved.get("duration_seconds"),
                    "regions_checked": regions_checked,
                    "regions_up": regions_up,
                    "region_results": result.get("region_results", []),
                })
                if not in_maintenance:
                    recovery_results = await send_recovery_alert(monitor, resolved)
                    for channel, ok in recovery_results.items():
                        log_incident_event(db, resolved["id"],
                                           f"recovery_{channel}_{'sent' if ok else 'failed'}")
                    if monitor.get("webhook_url"):
                        await send_webhook_notification(monitor, "monitor.up", result)
                duration = resolved.get("duration_seconds", 0)
                print(f"[checker] INCIDENT RESOLVED: {monitor['name']} is UP (down for {duration}s)" +
                      (" (maintenance — alerts suppressed)" if in_maintenance else ""))

        # ----- Single consolidated Firestore write per monitor -----
        update_monitor(db, monitor["id"], monitor_updates)
        fw_writes += 1

    # Batch-write all check records at once (much faster than individual writes)
    if check_batch:
        try:
            create_checks_batch(db, check_batch)
            fw_writes += 1  # Count the batch as one write operation
        except Exception as e:
            logger.error(f"[checker] Batch check write failed, falling back to individual: {e}")
            for c in check_batch:
                try:
                    create_check(db, c["monitor_id"], c["status_code"], c["response_ms"], c["is_up"])
                    fw_writes += 1
                except Exception:
                    pass

    t_phase3 = time.monotonic() - t_writes
    t_total = time.monotonic() - t_cycle_start

    # ----- Instrumentation: compute percentiles and emit structured summary -----
    due_count = len(due_monitors)
    cps = due_count / t_checks if t_checks > 0 else 0
    response_times.sort()
    p50 = _percentile(response_times, 0.50) if response_times else 0
    p95 = _percentile(response_times, 0.95) if response_times else 0
    wpm = fw_writes / due_count if due_count > 0 else 0

    logger.info(
        f"[checker] CYCLE COMPLETE | total={t_total:.1f}s | due={due_count} | checks/sec={cps:.1f} | "
        f"phase2={t_checks:.1f}s | phase3={t_phase3:.1f}s | p50={p50}ms | p95={p95}ms | "
        f"retries={retry_count} | fw_writes={fw_writes} | writes/mon={wpm:.1f} | "
        f"up={results['up']} | down={results['down']} | skipped={results['skipped']} | errors_by_type={errors_by_type}"
    )

    return results
