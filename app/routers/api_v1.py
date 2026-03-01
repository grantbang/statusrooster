"""
Public API v1 — programmatic access to monitors and checks.
Authenticated via X-API-Key header.
All responses follow: {data, error, meta}
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, HttpUrl
from app.database import get_db
from app.models.api_key import get_user_by_api_key
from app.models.monitor import (
    create_monitor, list_monitors_by_user, get_monitor,
    update_monitor, delete_monitor,
)
from app.models.check import get_recent_checks
from app.models.user import update_user
from datetime import datetime

router = APIRouter(prefix="/api/v1", tags=["monitors"])

FREE_MONITOR_LIMIT = 5
PRO_MONITOR_LIMIT = 250

# Security scheme — tells Swagger to show an "Authorize" button + lock icons
api_key_header = APIKeyHeader(name="X-API-Key", description="Your StatusRooster API key (starts with sr_)")


# ─── Auth dependency ────────────────────────────────────────────────

async def get_api_user(api_key: str = Depends(api_key_header)) -> dict:
    """Authenticate via X-API-Key header."""
    api_key = api_key.strip()
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Pass your key in the X-API-Key header.",
        )
    db = get_db()
    user = get_user_by_api_key(db, api_key)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key.",
        )
    return user


# ─── Response helpers ───────────────────────────────────────────────

def ok(data, meta=None):
    resp = {"data": data, "error": None}
    if meta:
        resp["meta"] = meta
    return resp


def err(detail: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"data": None, "error": detail},
    )


# ─── Serializer (strip Firestore timestamps for clean JSON) ────────

def _serialize(obj):
    """Convert Firestore doc dict to JSON-safe dict."""
    if obj is None:
        return None
    clean = {}
    for k, v in obj.items():
        if isinstance(v, datetime):
            clean[k] = v.isoformat()
        elif hasattr(v, '_seconds'):  # Firestore DatetimeWithNanoseconds
            clean[k] = datetime.fromtimestamp(v._seconds).isoformat()
        elif isinstance(v, dict):
            clean[k] = _serialize(v)
        else:
            clean[k] = v
    return clean


def _serialize_monitor(m: dict) -> dict:
    """Serialize a monitor, keeping only the fields the API should expose."""
    s = _serialize(m)
    # Remove internal fields
    s.pop("user_id", None)
    return s


def _serialize_check(c: dict) -> dict:
    s = _serialize(c)
    s.pop("monitor_id", None)
    return s


# ─── Endpoints ──────────────────────────────────────────────────────

# LIST MONITORS
@router.get("/monitors")
async def api_list_monitors(user: dict = Depends(get_api_user)):
    db = get_db()
    monitors = list_monitors_by_user(db, user["id"])
    return ok(
        data=[_serialize_monitor(m) for m in monitors],
        meta={"total": len(monitors)},
    )


# GET SINGLE MONITOR
@router.get("/monitors/{monitor_id}")
async def api_get_monitor(monitor_id: str, user: dict = Depends(get_api_user)):
    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor:
        err("Monitor not found", 404)
    if monitor["user_id"] != user["id"]:
        err("Monitor not found", 404)
    return ok(data=_serialize_monitor(monitor))


# GET CHECKS FOR A MONITOR
@router.get("/monitors/{monitor_id}/checks")
async def api_get_checks(
    monitor_id: str,
    limit: int = 100,
    user: dict = Depends(get_api_user),
):
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500

    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor:
        err("Monitor not found", 404)
    if monitor["user_id"] != user["id"]:
        err("Monitor not found", 404)

    checks = get_recent_checks(db, monitor_id, limit=limit)
    return ok(
        data=[_serialize_check(c) for c in checks],
        meta={"monitor_id": monitor_id, "total": len(checks), "limit": limit},
    )


# CREATE MONITOR
class ApiCreateMonitor(BaseModel):
    url: HttpUrl
    name: str
    alert_email: str = ""
    alert_slack_webhook: str = ""
    keyword: str = ""
    response_threshold_ms: int | None = None
    webhook_url: str = ""
    public: bool = True


@router.post("/monitors", status_code=201)
async def api_create_monitor(req: ApiCreateMonitor, user: dict = Depends(get_api_user)):
    db = get_db()

    # Plan enforcement
    plan = user.get("plan", "free")
    existing = list_monitors_by_user(db, user["id"])
    if plan == "free" and len(existing) >= FREE_MONITOR_LIMIT:
        err(f"Free plan limited to {FREE_MONITOR_LIMIT} monitors. Upgrade to Pro for up to {PRO_MONITOR_LIMIT}.", 403)
    if plan == "pro" and len(existing) >= PRO_MONITOR_LIMIT:
        err(f"Pro plan limited to {PRO_MONITOR_LIMIT} monitors. Contact us if you need more.", 403)

    monitor = create_monitor(
        db,
        user_id=user["id"],
        url=str(req.url),
        name=req.name,
        alert_email=req.alert_email or user.get("email", ""),
        alert_slack_webhook=req.alert_slack_webhook,
        public=req.public,
        keyword=req.keyword,
        response_threshold_ms=req.response_threshold_ms,
        webhook_url=req.webhook_url if user.get("plan", "free") != "free" else "",
    )

    update_user(db, user["id"], {"monitors_count": (user.get("monitors_count", 0) + 1)})
    return ok(data=_serialize_monitor(monitor))


# DELETE MONITOR
@router.delete("/monitors/{monitor_id}")
async def api_delete_monitor(monitor_id: str, user: dict = Depends(get_api_user)):
    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor:
        err("Monitor not found", 404)
    if monitor["user_id"] != user["id"]:
        err("Monitor not found", 404)

    delete_monitor(db, monitor_id)
    new_count = max(0, user.get("monitors_count", 1) - 1)
    update_user(db, user["id"], {"monitors_count": new_count})
    return ok(data={"deleted": True, "monitor_id": monitor_id})
