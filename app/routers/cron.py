from fastapi import APIRouter, HTTPException, Request
import asyncio
import time
import httpx
from app.config import settings
from app.services.checker import run_checks

router = APIRouter(prefix="/cron", tags=["cron"], include_in_schema=False)

# Shared secret for cron auth (use JWT_SECRET as a simple approach)
CRON_SECRET = settings.JWT_SECRET

# Self-monitor heartbeat URL
_HEARTBEAT_URL = "https://statusrooster.com/api/ping/eqJyb8UWvNq8hskGk3kK?token=h3VeUGTMGYhCY0MPQiUS9q4IoBtejlZFq_1fgmQdZyM"


def _verify_cron_auth(request: Request):
    """Verify cron request via shared secret in header or query param."""
    auth_header = request.headers.get("X-Cron-Secret", "")
    query_secret = request.query_params.get("secret", "")
    if auth_header != CRON_SECRET and query_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized cron request")


async def _ping_heartbeat():
    """Ping self-monitor heartbeat (fire-and-forget)."""
    try:
        async with httpx.AsyncClient() as hb:
            await hb.get(_HEARTBEAT_URL)
    except Exception:
        pass


@router.post("/check")
async def cron_check(request: Request):
    """
    Run uptime checks for all monitors.
    Called by Cloud Scheduler every 60 seconds. Runs two check cycles
    30 seconds apart to support Pro plan's 30-second check intervals.
    Free-plan monitors (60s+ interval) naturally skip the second cycle
    via the elapsed-time guard in run_checks().
    Authenticated via shared secret in header or query param.
    """
    _verify_cron_auth(request)

    # Cycle 1
    t_start = time.monotonic()
    results1 = await run_checks()
    if not results1.get("skipped_reason"):
        await _ping_heartbeat()

    # Wait for the remainder of 30 seconds, then run cycle 2
    elapsed = time.monotonic() - t_start
    sleep_time = max(0, 30 - elapsed)
    if sleep_time > 0:
        await asyncio.sleep(sleep_time)

    # Cycle 2 — picks up 30s-interval Pro monitors that are now due again
    results2 = await run_checks()

    return {"status": "completed", "results": [results1, results2]}


@router.post("/cleanup")
async def cron_cleanup(request: Request):
    """
    Delete check records older than the retention period.
    Called by Cloud Scheduler once daily.
    Free plan: 30 days. Pro plan: 90 days.
    """
    _verify_cron_auth(request)

    from scripts.cleanup_old_checks import cleanup_old_checks
    summary = cleanup_old_checks(dry_run=False)
    return {"status": "completed", "summary": summary}
