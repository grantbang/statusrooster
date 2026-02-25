from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, HttpUrl
from app.database import get_db
from app.services.auth import get_current_user
from app.models.monitor import (
    create_monitor, list_monitors_by_user, get_monitor,
    update_monitor, delete_monitor,
)
from app.models.user import update_user

router = APIRouter(prefix="/api/monitors", tags=["monitors"])

FREE_MONITOR_LIMIT = 5


class CreateMonitorRequest(BaseModel):
    url: HttpUrl
    name: str
    alert_email: str = ""
    alert_slack_webhook: str = ""
    public: bool = True


class UpdateMonitorRequest(BaseModel):
    url: HttpUrl | None = None
    name: str | None = None
    alert_email: str | None = None
    alert_slack_webhook: str | None = None
    public: bool | None = None


@router.post("")
async def create(req: CreateMonitorRequest, user: dict = Depends(get_current_user)):
    db = get_db()

    # Plan enforcement: free users capped at 5 monitors
    if user.get("plan", "free") == "free":
        existing = list_monitors_by_user(db, user["id"])
        if len(existing) >= FREE_MONITOR_LIMIT:
            raise HTTPException(
                status_code=403,
                detail=f"Free plan is limited to {FREE_MONITOR_LIMIT} monitors. Upgrade to Pro for unlimited."
            )

    monitor = create_monitor(
        db,
        user_id=user["id"],
        url=str(req.url),
        name=req.name,
        alert_email=req.alert_email or user.get("email", ""),
        alert_slack_webhook=req.alert_slack_webhook,
        public=req.public,
    )

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

    if updates:
        update_monitor(db, monitor_id, updates)

    return {"monitor": {**monitor, **updates}}


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
