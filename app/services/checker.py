import httpx
import asyncio
import time
from datetime import datetime, timezone
from app.database import get_db
from app.models.monitor import get_all_monitors, update_monitor
from app.models.check import create_check
from app.models.incident import create_incident, resolve_incident, get_open_incident
from app.services.alerts import send_down_alert, send_recovery_alert


async def check_url(url: str, timeout: float = 10.0) -> dict:
    """
    Perform an HTTP GET to the target URL.
    Returns dict with status_code, response_ms, is_up.
    """
    try:
        async with httpx.AsyncClient() as client:
            start = time.monotonic()
            response = await client.get(url, timeout=timeout, follow_redirects=True)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

            is_up = 200 <= response.status_code < 400
            return {
                "status_code": response.status_code,
                "response_ms": elapsed_ms,
                "is_up": is_up,
            }
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError):
        return {
            "status_code": None,
            "response_ms": None,
            "is_up": False,
        }


async def check_url_with_retry(url: str, timeout: float = 10.0) -> dict:
    """
    Check a URL with false positive prevention.
    If the first check fails, wait 5 seconds and retry once.
    """
    result = await check_url(url, timeout)
    if not result["is_up"]:
        # Retry once after 5 seconds to prevent false positives
        await asyncio.sleep(5)
        result = await check_url(url, timeout)
    return result


async def run_checks():
    """
    Run checks for ALL monitors. Called by the cron endpoint.
    Returns summary of results.
    """
    db = get_db()
    monitors = get_all_monitors(db)

    results = {"total": len(monitors), "up": 0, "down": 0}

    for monitor in monitors:
        # Perform the check with retry
        result = await check_url_with_retry(monitor["url"])

        # Record check in Firestore
        create_check(
            db,
            monitor_id=monitor["id"],
            status_code=result["status_code"],
            response_ms=result["response_ms"],
            is_up=result["is_up"],
        )

        # Update monitor stats
        previous_status = monitor.get("status", "pending")
        new_status = "up" if result["is_up"] else "down"

        checks_total = monitor.get("checks_total", 0) + 1
        checks_failed = monitor.get("checks_failed", 0) + (0 if result["is_up"] else 1)
        uptime_percent = round(((checks_total - checks_failed) / checks_total) * 100, 2)

        update_monitor(db, monitor["id"], {
            "status": new_status,
            "last_checked": datetime.now(timezone.utc),
            "last_status_code": result["status_code"],
            "last_response_ms": result["response_ms"],
            "uptime_percent": uptime_percent,
            "checks_total": checks_total,
            "checks_failed": checks_failed,
        })

        if result["is_up"]:
            results["up"] += 1
        else:
            results["down"] += 1

        # ----- Status change detection + Incidents + Alerts -----
        status_changed = previous_status != new_status

        if status_changed and new_status == "down":
            # UP → DOWN: Check for existing open incident (deduplication)
            existing = get_open_incident(db, monitor["id"])
            if existing is None:
                # Create new incident
                incident = create_incident(
                    db,
                    monitor_id=monitor["id"],
                    monitor_name=monitor.get("name", ""),
                    monitor_url=monitor.get("url", ""),
                    status_code=result["status_code"],
                    response_ms=result["response_ms"],
                )
                # Trigger down alerts
                await send_down_alert(monitor, incident)
                print(f"[checker] INCIDENT CREATED: {monitor['name']} is DOWN")
            else:
                print(f"[checker] {monitor['name']} still DOWN — incident already open, skipping alert")

        elif status_changed and new_status == "up":
            # DOWN → UP: Resolve open incident
            open_incident = get_open_incident(db, monitor["id"])
            if open_incident:
                resolved = resolve_incident(db, open_incident["id"])
                # Trigger recovery alerts
                await send_recovery_alert(monitor, resolved)
                duration = resolved.get("duration_seconds", 0)
                print(f"[checker] INCIDENT RESOLVED: {monitor['name']} is UP (down for {duration}s)")

    return results
