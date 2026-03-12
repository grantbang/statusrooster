"""
Public API v1 — programmatic access to monitors and checks.
Authenticated via X-API-Key header.
All responses follow: {data, error, meta}
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, HttpUrl, field_validator
from typing import Literal
from app.database import get_db
from app.models.api_key import get_user_by_api_key
from app.models.monitor import (
    create_monitor, list_monitors_by_user, get_monitor,
    update_monitor, delete_monitor,
)
from app.models.check import get_recent_checks
from app.models.incident import get_incident, list_incidents_by_user
from app.models.user import update_user
from datetime import datetime

router = APIRouter(prefix="/api/v1", tags=["monitors"])

FREE_MONITOR_LIMIT = 100
PRO_MONITOR_LIMIT = 500

# Security scheme — tells Swagger to show an "Authorize" button + lock icons
api_key_header = APIKeyHeader(name="X-API-Key", description="Your StatusRooster API key (starts with sr_)", auto_error=False)


# ─── Auth dependency ────────────────────────────────────────────────

async def get_api_user(api_key: str | None = Depends(api_key_header)) -> dict:
    """Authenticate via X-API-Key header."""
    if not api_key or not api_key.strip():
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Pass your key in the X-API-Key header.",
        )
    api_key = api_key.strip()
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
    # Remove internal / pre-computed fields that are not part of the public API
    _INTERNAL_FIELDS = {
        "user_id",
        "daily_uptime_bars",
        "hourly_uptime_bars",
        "ping_token",
        "ssl_expiry_alerted_days",
        "regions",
    }
    for field in _INTERNAL_FIELDS:
        s.pop(field, None)
    return s


def _serialize_check(c: dict) -> dict:
    s = _serialize(c)
    s.pop("monitor_id", None)
    return s


def _serialize_incident(inc: dict) -> dict:
    """Serialize an incident for API output."""
    s = _serialize(inc)
    return s


# ─── Shared schemas ─────────────────────────────────────────────────

VALID_DAYS = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "daily"]


class MaintenanceWindow(BaseModel):
    day: VALID_DAYS
    start_utc: str  # "HH:MM" format
    end_utc: str    # "HH:MM" format


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

    checks = get_recent_checks(db, monitor_id, limit=limit, plan=user.get("plan", "free"))
    return ok(
        data=[_serialize_check(c) for c in checks],
        meta={"monitor_id": monitor_id, "total": len(checks), "limit": limit},
    )


# ─── Incident endpoints ────────────────────────────────────────────

# LIST ALL INCIDENTS
@router.get("/incidents")
async def api_list_incidents(
    status: str | None = None,
    monitor_id: str | None = None,
    monitor_type: str | None = None,
    hours: int = 720,
    limit: int = 50,
    user: dict = Depends(get_api_user),
):
    """List incidents across all monitors for the authenticated user."""
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500
    if hours < 1:
        hours = 1
    if hours > 8760:
        hours = 8760  # max 1 year

    if status and status not in ("open", "resolved"):
        err("Invalid status filter. Use 'open' or 'resolved'.", 422)

    valid_types = ("http", "json_api", "heartbeat", "ssl")
    if monitor_type and monitor_type not in valid_types:
        err(f"Invalid monitor_type. Use one of: {', '.join(valid_types)}.", 422)

    db = get_db()
    monitors = list_monitors_by_user(db, user["id"])

    # Filter by monitor_type if specified
    if monitor_type:
        monitors = [m for m in monitors if m.get("monitor_type") == monitor_type]

    monitor_ids = [m["id"] for m in monitors]

    # If filtering by a specific monitor, validate ownership
    if monitor_id:
        if monitor_id not in monitor_ids:
            err("Monitor not found", 404)
        monitor_ids = [monitor_id]

    incidents = list_incidents_by_user(db, monitor_ids, hours=hours, limit=limit, status=status)
    return ok(
        data=[_serialize_incident(inc) for inc in incidents],
        meta={"total": len(incidents), "limit": limit, "hours": hours},
    )


# GET SINGLE INCIDENT
@router.get("/incidents/{incident_id}")
async def api_get_incident(incident_id: str, user: dict = Depends(get_api_user)):
    """Get a single incident by ID."""
    db = get_db()
    incident = get_incident(db, incident_id)
    if not incident:
        err("Incident not found", 404)

    # Validate ownership — incident must belong to one of the user's monitors
    monitor = get_monitor(db, incident["monitor_id"])
    if not monitor or monitor["user_id"] != user["id"]:
        err("Incident not found", 404)

    return ok(data=_serialize_incident(incident))


# CREATE MONITOR
class ApiCreateMonitor(BaseModel):
    url: HttpUrl | None = None
    name: str
    alert_email: str = ""
    alert_slack_webhook: str = ""
    keyword: str = ""
    response_threshold_ms: str | None = None
    webhook_url: str = ""
    public: bool = True
    paused: bool = False
    check_interval: int | None = None
    maintenance_windows: list[MaintenanceWindow] | None = None
    monitor_type: Literal["http", "json_api", "heartbeat", "ssl"] = "http"
    heartbeat_interval: int | None = None
    heartbeat_grace_period: int | None = None
    expected_status_code: int | None = None
    timeout: int | None = None
    json_assertions: list | None = None  # [{path, operator, value}]
    auth_header: str = ""
    ssl_domain: str = ""
    ssl_expiry_threshold_days: int | None = None
    group: str = ""
    http_method: str = "GET"             # GET, POST, HEAD, PUT, PATCH, DELETE, OPTIONS
    basic_auth_user: str = ""            # Basic Auth username (Pro)
    basic_auth_pass: str = ""            # Basic Auth password (Pro)
    follow_redirects: bool = True        # Follow HTTP redirects
    bearer_token: str = ""               # Bearer token auth (sent as Authorization: Bearer <token>)
    request_body: str = ""               # Request body for POST/PUT/PATCH/DELETE
    request_content_type: str = ""       # Content-Type for request body (e.g. application/json)
    custom_headers: list[dict] | None = None  # [{key, value}] custom request headers (Pro)


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

    # Build maintenance windows (all plans)
    mw_list = None
    if req.maintenance_windows:
        mw_list = [w.model_dump() for w in req.maintenance_windows]

    # Status page limit enforcement
    if req.public:
        public_count = sum(1 for m in existing if m.get("public", False))
        public_limit = 10
        if public_count >= public_limit:
            err(f"Limited to {public_limit} public status pages. Contact us if you need more.", 403)

    # Validate http_method
    allowed_methods = {"GET", "POST", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS"}
    http_method = req.http_method.upper() if req.http_method else "GET"
    if http_method not in allowed_methods:
        err(f"Invalid http_method. Use one of: {', '.join(sorted(allowed_methods))}.", 422)

    # Basic auth available to all plans
    basic_auth_user = req.basic_auth_user or ""
    basic_auth_pass = req.basic_auth_pass or ""

    # Custom headers available to all plans
    custom_headers = req.custom_headers if req.custom_headers else []

    # Bearer token available to all plans
    bearer_token = req.bearer_token or ""

    # Validate check_interval bounds (apply plan-appropriate default if omitted)
    check_interval = req.check_interval
    min_interval = 30 if plan == "pro" else 60
    if check_interval is not None:
        if check_interval < min_interval:
            err(f"Minimum check interval is {min_interval}s for your plan.", 403)
        check_interval = max(min_interval, min(300, check_interval))
    else:
        check_interval = min_interval

    # Clamp optional numeric fields to valid bounds (consistent with update)
    timeout = max(1, min(60, req.timeout)) if req.timeout is not None else None
    heartbeat_interval = max(60, min(86400, req.heartbeat_interval)) if req.heartbeat_interval is not None else None
    heartbeat_grace_period = max(0, min(3600, req.heartbeat_grace_period)) if req.heartbeat_grace_period is not None else None
    ssl_expiry_threshold_days = max(1, min(90, req.ssl_expiry_threshold_days)) if req.ssl_expiry_threshold_days is not None else None

    monitor = create_monitor(
        db,
        user_id=user["id"],
        url=str(req.url) if req.url else "",
        name=req.name,
        alert_email=req.alert_email or user.get("email", ""),
        alert_slack_webhook=req.alert_slack_webhook or "",
        public=req.public,
        keyword=req.keyword,
        response_threshold_ms=req.response_threshold_ms,
        webhook_url=req.webhook_url or "",
        maintenance_windows=mw_list,
        paused=req.paused,
        check_interval=check_interval,
        monitor_type=req.monitor_type,
        heartbeat_interval=heartbeat_interval,
        heartbeat_grace_period=heartbeat_grace_period,
        expected_status_code=req.expected_status_code,
        timeout=timeout,
        json_assertions=req.json_assertions,
        auth_header=req.auth_header,
        ssl_domain=req.ssl_domain,
        ssl_expiry_threshold_days=ssl_expiry_threshold_days,
        group=req.group,
        http_method=http_method,
        basic_auth_user=basic_auth_user,
        basic_auth_pass=basic_auth_pass,
        follow_redirects=req.follow_redirects,
        bearer_token=bearer_token,
        request_body=req.request_body or "",
        request_content_type=req.request_content_type or "",
        custom_headers=custom_headers,
    )
    if req.monitor_type == "heartbeat":
        from app.config import settings
        ping_url = f"{settings.APP_URL}/api/ping/{monitor['id']}"
        update_monitor(db, monitor["id"], {"url": ping_url, "ping_url": ping_url})
        monitor["url"] = ping_url
        monitor["ping_url"] = ping_url

    update_user(db, user["id"], {"monitors_count": (user.get("monitors_count", 0) + 1)})
    return ok(data=_serialize_monitor(monitor))


# UPDATE MONITOR
class ApiUpdateMonitor(BaseModel):
    url: HttpUrl | None = None
    name: str | None = None
    alert_email: str | None = None
    alert_slack_webhook: str | None = None
    keyword: str | None = None
    response_threshold_ms: str | None = None
    webhook_url: str | None = None
    public: bool | None = None
    paused: bool | None = None
    slug: str | None = None
    check_interval: int | None = None
    maintenance_windows: list[MaintenanceWindow] | None = None
    heartbeat_interval: int | None = None
    heartbeat_grace_period: int | None = None
    expected_status_code: int | None = None
    timeout: int | None = None
    json_assertions: list | None = None
    auth_header: str | None = None
    ssl_domain: str | None = None
    ssl_expiry_threshold_days: int | None = None
    group: str | None = None
    http_method: str | None = None          # GET, POST, HEAD, PUT, PATCH, DELETE, OPTIONS
    basic_auth_user: str | None = None      # Basic Auth username (Pro)
    basic_auth_pass: str | None = None      # Basic Auth password (Pro)
    follow_redirects: bool | None = None    # Follow HTTP redirects
    bearer_token: str | None = None         # Bearer token auth
    request_body: str | None = None         # Request body for POST/PUT/PATCH/DELETE
    request_content_type: str | None = None # Content-Type for request body
    custom_headers: list[dict] | None = None  # [{key, value}] custom request headers (Pro)


@router.put("/monitors/{monitor_id}")
@router.patch("/monitors/{monitor_id}")
async def api_update_monitor(
    monitor_id: str,
    req: ApiUpdateMonitor,
    user: dict = Depends(get_api_user),
):
    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor:
        err("Monitor not found", 404)
    if monitor["user_id"] != user["id"]:
        err("Monitor not found", 404)

    # Build update dict from non-None fields
    updates = {}
    if req.url is not None:
        updates["url"] = str(req.url)
    if req.name is not None:
        updates["name"] = req.name
    if req.alert_email is not None:
        updates["alert_email"] = req.alert_email
    if req.alert_slack_webhook is not None:
        updates["alert_slack_webhook"] = req.alert_slack_webhook
    if req.keyword is not None:
        updates["keyword"] = req.keyword
    if req.response_threshold_ms is not None:
        updates["response_threshold_ms"] = req.response_threshold_ms
    if req.webhook_url is not None:
        updates["webhook_url"] = req.webhook_url
    if req.public is not None:
        # Status page limit enforcement (only if turning public ON)
        if req.public and not monitor.get("public", False):
            all_monitors = list_monitors_by_user(db, user["id"])
            public_count = sum(1 for m in all_monitors if m.get("public", False))
            public_limit = 10
            if public_count >= public_limit:
                err(f"Limited to {public_limit} public status pages. Contact us if you need more.", 403)
        updates["public"] = req.public
    if req.paused is not None:
        updates["paused"] = req.paused
    if req.slug is not None:
        import re
        updates["slug"] = re.sub(r"[^a-z0-9\-]", "", req.slug.lower().replace(" ", "-")).strip("-")
    if req.maintenance_windows is not None:
        updates["maintenance_windows"] = [w.model_dump() for w in req.maintenance_windows]
    if req.check_interval is not None:
        plan = user.get("plan", "free")
        min_interval = 30 if plan == "pro" else 60
        if req.check_interval < min_interval:
            err(f"Minimum check interval is {min_interval}s for your plan.", 403)
        updates["check_interval"] = max(min_interval, min(300, req.check_interval))
    if req.heartbeat_interval is not None:
        updates["heartbeat_interval"] = max(60, min(86400, req.heartbeat_interval))
    if req.heartbeat_grace_period is not None:
        updates["heartbeat_grace_period"] = max(0, min(3600, req.heartbeat_grace_period))
    if req.expected_status_code is not None:
        updates["expected_status_code"] = req.expected_status_code
    if req.timeout is not None:
        updates["timeout"] = max(1, min(60, req.timeout))
    if req.json_assertions is not None:
        updates["json_assertions"] = req.json_assertions
    if req.auth_header is not None:
        updates["auth_header"] = req.auth_header
    if req.ssl_domain is not None:
        updates["ssl_domain"] = req.ssl_domain
    if req.ssl_expiry_threshold_days is not None:
        updates["ssl_expiry_threshold_days"] = max(1, min(90, req.ssl_expiry_threshold_days))
    if req.group is not None:
        updates["group"] = req.group
    if req.http_method is not None:
        allowed_methods = {"GET", "POST", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS"}
        method = req.http_method.upper()
        if method not in allowed_methods:
            err(f"Invalid http_method. Use one of: {', '.join(sorted(allowed_methods))}.", 422)
        updates["http_method"] = method
    if req.basic_auth_user is not None:
        updates["basic_auth_user"] = req.basic_auth_user
    if req.basic_auth_pass is not None:
        updates["basic_auth_pass"] = req.basic_auth_pass
    if req.follow_redirects is not None:
        updates["follow_redirects"] = req.follow_redirects
    if req.bearer_token is not None:
        updates["bearer_token"] = req.bearer_token
    if req.request_body is not None:
        updates["request_body"] = req.request_body
    if req.request_content_type is not None:
        updates["request_content_type"] = req.request_content_type
    if req.custom_headers is not None:
        updates["custom_headers"] = req.custom_headers

    if not updates:
        err("No fields to update. Send at least one field.", 422)

    update_monitor(db, monitor_id, updates)

    # Return the updated monitor
    updated = get_monitor(db, monitor_id)
    return ok(data=_serialize_monitor(updated))


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
