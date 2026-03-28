from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl
from app.database import get_db
from app.services.auth import get_current_user
from app.models.monitor import (
    create_monitor, list_monitors_by_user, get_monitor,
    update_monitor, delete_monitor,
)
from app.models.user import update_user
from app.services.alerts import send_test_alert

router = APIRouter(prefix="/api/monitors", tags=["monitors-internal"], include_in_schema=False)

FREE_MONITOR_LIMIT = 10
PRO_MONITOR_LIMIT = 200


class CreateMonitorRequest(BaseModel):
    url: HttpUrl | None = None
    name: str
    alert_email: str = ""
    alert_slack_webhook: str = ""
    keyword: str = ""
    response_threshold_ms: int | None = None
    webhook_url: str = ""
    public: bool = True
    check_interval: int | None = None
    monitor_type: str = "http"          # "http" | "heartbeat" | "json_api" | "ssl"
    heartbeat_interval: int | None = None  # seconds (heartbeat only)
    heartbeat_grace_period: int | None = None  # seconds (heartbeat only)
    expected_status_code: int | None = None
    timeout: int | None = None
    json_assertions: list | None = None  # [{path, operator, value}]
    auth_header: str = ""
    ssl_domain: str = ""
    ssl_expiry_threshold_days: int | None = None


class UpdateMonitorRequest(BaseModel):
    url: HttpUrl | None = None
    name: str | None = None
    alert_email: str | None = None
    alert_slack_webhook: str | None = None
    keyword: str | None = None
    response_threshold_ms: int | None = None
    webhook_url: str | None = None
    public: bool | None = None
    check_interval: int | None = None
    monitor_type: str | None = None
    heartbeat_interval: int | None = None
    heartbeat_grace_period: int | None = None
    expected_status_code: int | None = None
    timeout: int | None = None
    json_assertions: list | None = None
    auth_header: str | None = None
    ssl_domain: str | None = None
    ssl_expiry_threshold_days: int | None = None


@router.post("")
async def create(req: CreateMonitorRequest, user: dict = Depends(get_current_user)):
    db = get_db()

    # Plan enforcement
    plan = user.get("plan", "free")
    existing = list_monitors_by_user(db, user["id"])
    limit = PRO_MONITOR_LIMIT if plan == "pro" else FREE_MONITOR_LIMIT
    if len(existing) >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Limited to {limit} monitors.{' Contact us if you need more.' if plan == 'pro' else ' Upgrade to Pro for up to 200.'}"
        )

    monitor = create_monitor(
        db,
        user_id=user["id"],
        url=str(req.url) if req.url else "",
        name=req.name,
        alert_email=req.alert_email or user.get("email", ""),
        alert_slack_webhook=req.alert_slack_webhook or "",
        public=req.public,
        check_interval=req.check_interval,
        monitor_type=req.monitor_type,
        heartbeat_interval=req.heartbeat_interval,
        heartbeat_grace_period=req.heartbeat_grace_period,
        expected_status_code=req.expected_status_code,
        timeout=req.timeout,
        json_assertions=req.json_assertions,
        auth_header=req.auth_header,
        ssl_domain=req.ssl_domain,
        ssl_expiry_threshold_days=req.ssl_expiry_threshold_days,
    )

    # Set Day 7 fields that aren't in create_monitor params
    extra_fields = {}
    if req.keyword:
        extra_fields["keyword"] = req.keyword
    if req.response_threshold_ms:
        extra_fields["response_threshold_ms"] = req.response_threshold_ms
    if req.webhook_url:
        extra_fields["webhook_url"] = req.webhook_url
    if extra_fields:
        from app.models.monitor import update_monitor as update_mon
        update_mon(db, monitor["id"], extra_fields)
        monitor.update(extra_fields)

    # Update user's monitor count
    update_user(db, user["id"], {"monitors_count": (user.get("monitors_count", 0) + 1)})

    return {"monitor": monitor}


@router.get("")
async def list_all(user: dict = Depends(get_current_user)):
    db = get_db()
    monitors = list_monitors_by_user(db, user["id"])
    return {"monitors": monitors}


@router.get("/{monitor_id}")
async def get_one(monitor_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    if monitor["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your monitor")

    return {"monitor": monitor}


@router.put("/{monitor_id}")
async def update(monitor_id: str, req: UpdateMonitorRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    if monitor["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your monitor")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "url" in updates:
        updates["url"] = str(updates["url"])

    # Gate Pro-only fields
    if "check_interval" in updates:
        plan = user.get("plan", "free")
        min_interval = 60
        updates["check_interval"] = max(min_interval, min(300, updates["check_interval"]))
    if "heartbeat_interval" in updates and updates["heartbeat_interval"] is not None:
        updates["heartbeat_interval"] = max(60, min(86400, updates["heartbeat_interval"]))
    if "heartbeat_grace_period" in updates and updates["heartbeat_grace_period"] is not None:
        updates["heartbeat_grace_period"] = max(0, min(3600, updates["heartbeat_grace_period"]))
    if "timeout" in updates and updates["timeout"] is not None:
        updates["timeout"] = max(1, min(60, updates["timeout"]))
    if "ssl_expiry_threshold_days" in updates and updates["ssl_expiry_threshold_days"] is not None:
        updates["ssl_expiry_threshold_days"] = max(1, min(90, updates["ssl_expiry_threshold_days"]))

    if updates:
        update_monitor(db, monitor_id, updates)

    return {"monitor": {**monitor, **updates}}


@router.post("/{monitor_id}/test-alert")
async def test_alert(monitor_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    if monitor["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your monitor")

    results = await send_test_alert(monitor, user.get("plan", "free"))
    return {"results": results}


@router.delete("/{monitor_id}")
async def delete(monitor_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    if monitor["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your monitor")

    delete_monitor(db, monitor_id)

    # Update user's monitor count
    new_count = max(0, user.get("monitors_count", 1) - 1)
    update_user(db, user["id"], {"monitors_count": new_count})

    return {"deleted": True}
