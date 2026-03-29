from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
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


async def _run_checks_and_ping():
    """Run checks then ping self-monitor heartbeat."""
    results = await run_checks()
    if not results.get("skipped_reason"):
        try:
            async with httpx.AsyncClient() as hb:
                await hb.get(_HEARTBEAT_URL)
        except Exception:
            pass


@router.post("/check")
async def cron_check(request: Request, background_tasks: BackgroundTasks):
    """
    Run uptime checks for all monitors.
    Called by Cloud Scheduler every 60 seconds.
    Responds immediately (200) and runs checks in the background so
    Cloud Scheduler doesn't retry due to long response times.
    """
    _verify_cron_auth(request)
    background_tasks.add_task(_run_checks_and_ping)
    return {"status": "accepted"}


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
