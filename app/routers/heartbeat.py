"""
Heartbeat / Cron job monitoring — public ping endpoint.

Users configure a cron job or scheduled task to POST (or GET) to:
    https://statusrooster.com/api/ping/{monitor_id}?token={ping_token}

If StatusRooster doesn't receive a ping within the expected interval,
the monitor is marked DOWN and alerts fire.

Authentication: each heartbeat monitor has a unique ping_token that must
be passed as a query parameter. Monitors created before this feature was
added (no ping_token field) are accepted without a token for backwards
compatibility — they should be migrated via scripts/backfill_ping_tokens.py.
"""

from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
from app.database import get_db
from app.models.monitor import get_monitor, record_heartbeat
from app.models.check import create_check
from app.models.incident import get_open_incident, resolve_incident, log_incident_event
from app.services.alerts import send_recovery_alert, send_webhook_notification

router = APIRouter(tags=["heartbeat"], include_in_schema=False)


@router.api_route("/api/ping/{monitor_id}", methods=["GET", "POST", "HEAD"])
async def receive_heartbeat(monitor_id: str, request: Request):
    """
    Record a heartbeat ping for a cron/heartbeat monitor.
    Accepts GET, POST, or HEAD — so it works with curl, wget, or any HTTP client.

    Usage:
        curl https://statusrooster.com/api/ping/{monitor_id}?token={ping_token}
        wget -q -O /dev/null "https://statusrooster.com/api/ping/{monitor_id}?token={ping_token}"
        */5 * * * * curl -fsS --retry 3 "https://statusrooster.com/api/ping/abc123?token=xyz"
    """
    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    if monitor.get("monitor_type") != "heartbeat":
        raise HTTPException(status_code=400, detail="This monitor is not a heartbeat monitor")

    # Token validation — only enforced when monitor has a ping_token set.
    # Monitors without ping_token (legacy, pre-backfill) are accepted without token.
    stored_token = monitor.get("ping_token")
    if stored_token:
        provided_token = request.query_params.get("token", "")
        if not provided_token or provided_token != stored_token:
            raise HTTPException(status_code=403, detail="Invalid or missing ping token")

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

    # Resolve open incident if monitor was down or has an orphaned incident
    open_incident = get_open_incident(db, monitor_id)
    if open_incident:
            resolved = resolve_incident(db, open_incident["id"])
            log_incident_event(db, resolved["id"], "resolved", {
                "duration_seconds": resolved.get("duration_seconds"),
            })
            # Send recovery alerts
            try:
                recovery_results = await send_recovery_alert(monitor, resolved)
                for channel, ok in recovery_results.items():
                    log_incident_event(db, resolved["id"],
                                       f"recovery_{channel}_{'sent' if ok else 'failed'}")
                if monitor.get("webhook_url"):
                    await send_webhook_notification(monitor, "monitor.up", {"is_up": True})
            except Exception as e:
                print(f"[heartbeat] Recovery alert error: {e}")

    return {
        "ok": True,
        "status": "up",
        "monitor": monitor.get("name", ""),
        "next_expected_before": (
            datetime.now(timezone.utc).timestamp() + monitor.get("heartbeat_interval", 300)
        ),
    }
