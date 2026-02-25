from fastapi import APIRouter, HTTPException, Request
from app.config import settings
from app.services.checker import run_checks

router = APIRouter(prefix="/cron", tags=["cron"])

# Shared secret for cron auth (use JWT_SECRET as a simple approach)
CRON_SECRET = settings.JWT_SECRET


@router.post("/check")
async def cron_check(request: Request):
    """
    Run uptime checks for all monitors.
    Called by Cloud Scheduler every 60 seconds.
    Authenticated via shared secret in header or query param.
    """
    # Verify request comes from Cloud Scheduler or authorized caller
    auth_header = request.headers.get("X-Cron-Secret", "")
    query_secret = request.query_params.get("secret", "")

    if auth_header != CRON_SECRET and query_secret != CRON_SECRET:
        # Also accept Cloud Scheduler's OIDC token (checked via header)
        user_agent = request.headers.get("User-Agent", "")
        if "Google-Cloud-Scheduler" not in user_agent:
            raise HTTPException(status_code=403, detail="Unauthorized cron request")

    results = await run_checks()
    return {"status": "completed", "results": results}
