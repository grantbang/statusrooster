"""
Heartbeat / Cron job monitoring — public ping endpoint.

Users configure a cron job or scheduled task to POST (or GET) to:
    https://statusrooster.com/api/ping/{monitor_id}

If StatusRooster doesn't receive a ping within the expected interval,
the monitor is marked DOWN and alerts fire.

No authentication required — the monitor ID is the secret.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.database import get_db
from app.models.monitor import get_monitor, record_heartbeat
from app.models.check import create_check

router = APIRouter(tags=["heartbeat"], include_in_schema=False)


@router.api_route("/api/ping/{monitor_id}", methods=["GET", "POST", "HEAD"])
async def receive_heartbeat(monitor_id: str):
    """
    Record a heartbeat ping for a cron/heartbeat monitor.
    Accepts GET, POST, or HEAD — so it works with curl, wget, or any HTTP client.

    Usage:
        curl https://statusrooster.com/api/ping/{monitor_id}
        wget -q -O /dev/null https://statusrooster.com/api/ping/{monitor_id}
        */5 * * * * curl -fsS --retry 3 https://statusrooster.com/api/ping/abc123
    """
    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    if monitor.get("monitor_type") != "heartbeat":
        raise HTTPException(status_code=400, detail="This monitor is not a heartbeat monitor")

    if monitor.get("paused", False):
        return {"ok": True, "status": "paused", "message": "Monitor is paused — ping recorded but not tracked"}

    # Record the heartbeat
    updated = record_heartbeat(db, monitor_id)

    # Also record a check entry for history
    create_check(
        db,
        monitor_id=monitor_id,
        status_code=200,
        response_ms=0,
        is_up=True,
    )

    return {
        "ok": True,
        "status": "up",
        "monitor": monitor.get("name", ""),
        "next_expected_before": (
            datetime.now(timezone.utc).timestamp() + monitor.get("heartbeat_interval", 300)
        ),
    }
