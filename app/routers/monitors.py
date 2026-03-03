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

FREE_MONITOR_LIMIT = 5
PRO_MONITOR_LIMIT = 250


class CreateMonitorRequest(BaseModel):
    url: HttpUrl
    name: str
    alert_email: str = ""
    alert_slack_webhook: str = ""
    keyword: str = ""
    response_threshold_ms: int | None = None
    webhook_url: str = ""
    public: bool = True
    check_interval: int | None = None


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
            detail=f"{'Pro' if plan == 'pro' else 'Free'} plan is limited to {limit} monitors. {'Contact us if you need more.' if plan == 'pro' else 'Upgrade to Pro for up to 250.'}"
        )

    monitor = create_monitor(
        db,
        user_id=user["id"],
        url=str(req.url),
        name=req.name,
        alert_email=req.alert_email or user.get("email", ""),
        alert_slack_webhook=req.alert_slack_webhook,
        public=req.public,
        check_interval=req.check_interval,
    )

    # Set Day 7 fields that aren't in create_monitor params
    extra_fields = {}
    if req.keyword:
        extra_fields["keyword"] = req.keyword
    if req.response_threshold_ms:
        extra_fields["response_threshold_ms"] = req.response_threshold_ms
    if req.webhook_url and user.get("plan", "free") != "free":
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
    if "webhook_url" in updates and user.get("plan", "free") == "free":
        del updates["webhook_url"]
    if "check_interval" in updates:
        if user.get("plan", "free") == "free":
            del updates["check_interval"]
        else:
            updates["check_interval"] = max(60, min(300, updates["check_interval"]))

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
