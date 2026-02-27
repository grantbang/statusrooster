from datetime import datetime, timezone
import re
import uuid

COLLECTION = "monitors"


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a monitor name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    # Append short unique suffix to avoid collisions
    suffix = uuid.uuid4().hex[:6]
    return f"{slug}-{suffix}"


def create_monitor(db, user_id: str, url: str, name: str, alert_email: str = "",
                   alert_slack_webhook: str = "", public: bool = False) -> dict:
    """Create a new monitor. Returns monitor dict with id."""
    doc_ref = db.collection(COLLECTION).document()
    slug = generate_slug(name)
    monitor_data = {
        "user_id": user_id,
        "url": url,
        "name": name,
        "check_interval": 60,
        "status": "pending",  # pending | up | down
        "last_checked": None,
        "last_status_code": None,
        "last_response_ms": None,
        "uptime_percent": 100.0,
        "checks_total": 0,
        "checks_failed": 0,
        "alert_email": alert_email,
        "alert_slack_webhook": alert_slack_webhook,
        "alert_sms": "",
        "public": public,
        "slug": slug,
        "created_at": datetime.now(timezone.utc),
    }
    doc_ref.set(monitor_data)
    monitor_data["id"] = doc_ref.id
    return monitor_data


def list_monitors_by_user(db, user_id: str) -> list[dict]:
    """List all monitors for a user."""
    docs = (
        db.collection(COLLECTION)
        .where("user_id", "==", user_id)
        .order_by("created_at")
        .get()
    )
    monitors = []
    for doc in docs:
        m = doc.to_dict()
        m["id"] = doc.id
        monitors.append(m)
    return monitors


def get_monitor(db, monitor_id: str) -> dict | None:
    """Get a single monitor by ID."""
    doc = db.collection(COLLECTION).document(monitor_id).get()
    if doc.exists:
        m = doc.to_dict()
        m["id"] = doc.id
        return m
    return None


def update_monitor(db, monitor_id: str, updates: dict) -> None:
    """Update fields on a monitor document."""
    db.collection(COLLECTION).document(monitor_id).update(updates)


def delete_monitor(db, monitor_id: str) -> None:
    """Delete a monitor and its associated checks."""
    # Delete checks for this monitor
    checks = db.collection("checks").where("monitor_id", "==", monitor_id).get()
    for check in checks:
        check.reference.delete()

    # Delete incidents for this monitor
    incidents = db.collection("incidents").where("monitor_id", "==", monitor_id).get()
    for incident in incidents:
        incident.reference.delete()

    # Delete the monitor itself
    db.collection(COLLECTION).document(monitor_id).delete()


def get_monitor_by_slug(db, slug: str) -> dict | None:
    """Get a monitor by its public slug. Used for status pages."""
    docs = (
        db.collection(COLLECTION)
        .where("slug", "==", slug)
        .limit(1)
        .get()
    )
    for doc in docs:
        m = doc.to_dict()
        m["id"] = doc.id
        return m
    return None


def get_all_monitors(db) -> list[dict]:
    """Get ALL monitors across all users (for cron check)."""
    docs = db.collection(COLLECTION).get()
    monitors = []
    for doc in docs:
        m = doc.to_dict()
        m["id"] = doc.id
        monitors.append(m)
    return monitors
