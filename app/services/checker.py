import httpx
import asyncio
import time
from datetime import datetime, timezone
from app.database import get_db
from app.models.monitor import get_all_monitors, update_monitor
from app.models.check import create_check


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

        # Store status change info for alert processing (Day 3)
        result["previous_status"] = previous_status
        result["new_status"] = new_status
        result["monitor"] = monitor

    return results
