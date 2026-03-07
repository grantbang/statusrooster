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
                   alert_slack_webhook: str = "", public: bool = False,
                   keyword: str = "", response_threshold_ms: str | None = None,
                   webhook_url: str = "", maintenance_windows: list | None = None,
                   paused: bool = False, check_interval: int | None = None,
                   monitor_type: str = "http", heartbeat_interval: int | None = None,
                   expected_status_code: int | None = None, timeout: int | None = None,
                   json_assertions: list | None = None, auth_header: str = "",
                   ssl_domain: str = "", ssl_expiry_threshold_days: int | None = None,
                   heartbeat_grace_period: int | None = None,
                   group: str = "", slug: str = "") -> dict:
    """Create a new monitor. Returns monitor dict with id.

    monitor_type: "http" | "heartbeat" | "json_api" | "ssl"
    """
    # Determine check interval based on user plan
    user_ref = db.collection("users").document(user_id).get()
    user_data = user_ref.to_dict() if user_ref.exists else {}
    plan = user_data.get("plan", "free")

    if plan == "pro":
        # Pro: custom interval 60-300s, default 60
        if check_interval is not None:
            check_interval = max(60, min(300, int(check_interval)))
        else:
            check_interval = 60
    else:
        # Free: locked at 300s (5 minutes)
        check_interval = 300

    # Heartbeat defaults
    if monitor_type == "heartbeat":
        if heartbeat_interval is None:
            heartbeat_interval = 300  # default: expect ping every 5 min
        heartbeat_interval = max(60, min(86400, int(heartbeat_interval)))  # 1min - 24h
        if heartbeat_grace_period is None:
            heartbeat_grace_period = 30  # default 30s grace
        heartbeat_grace_period = max(0, min(3600, int(heartbeat_grace_period)))

    # SSL monitor defaults
    if monitor_type == "ssl":
        if ssl_expiry_threshold_days is None:
            ssl_expiry_threshold_days = 14  # default: warn 14 days before expiry
        ssl_expiry_threshold_days = max(1, min(90, int(ssl_expiry_threshold_days)))

    # Timeout defaults (all types that make HTTP requests)
    if monitor_type in ("http", "json_api"):
        if timeout is None:
            timeout = 10
        timeout = max(1, min(60, int(timeout)))

    doc_ref = db.collection(COLLECTION).document()
    if not slug:
        slug = generate_slug(name)
    monitor_data = {
        "user_id": user_id,
        "url": url,
        "name": name,
        "monitor_type": monitor_type,            # "http" | "heartbeat" | "json_api" | "ssl"
        "check_interval": check_interval,
        "status": "pending",  # pending | up | down | warn
        "paused": paused,
        "last_checked": None,
        "last_status_code": None,
        "last_response_ms": None,
        "uptime_percent": 100.0,
        "checks_total": 0,
        "checks_failed": 0,
        "alert_email": alert_email,
        "alert_slack_webhook": alert_slack_webhook,
        "alert_sms": "",
        # HTTP-specific fields
        "timeout": timeout,                          # Request timeout in seconds
        "expected_status_code": expected_status_code,  # Expected HTTP status code (optional)
        "keyword": keyword,                          # Expected keyword in response body
        "response_threshold_ms": response_threshold_ms,  # Alert if response > this many ms
        # JSON/API assertion fields
        "json_assertions": json_assertions or [],    # List of {path, operator, value}
        "auth_header": auth_header,                  # Authorization header value
        # Heartbeat fields
        "heartbeat_interval": heartbeat_interval,    # Expected ping interval in seconds
        "heartbeat_grace_period": heartbeat_grace_period if monitor_type == "heartbeat" else None,
        "last_heartbeat": None,                      # Last ping timestamp
        # SSL monitor fields
        "ssl_domain": ssl_domain,                    # Domain to check SSL for (ssl type only)
        "ssl_expiry_threshold_days": ssl_expiry_threshold_days,  # Days before expiry to warn
        # Shared monitoring fields
        "webhook_url": webhook_url,                  # POST JSON on status change (Pro only)
        "ssl_expiry": None,            # SSL cert expiry date (auto-detected on http, primary on ssl)
        "ssl_issuer": None,            # SSL cert issuer
        "ssl_expiry_alerted_days": None,  # Track which threshold we last alerted at
        "maintenance_windows": maintenance_windows or [],  # List of {day, start_utc, end_utc} (Pro only)
        "public": public,
        "slug": slug,
        "group": group,
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


def record_heartbeat(db, monitor_id: str) -> dict | None:
    """Record an incoming heartbeat ping. Returns the updated monitor or None."""
    doc = db.collection(COLLECTION).document(monitor_id).get()
    if not doc.exists:
        return None
    m = doc.to_dict()
    m["id"] = doc.id
    if m.get("monitor_type") != "heartbeat":
        return None
    now = datetime.now(timezone.utc)
    db.collection(COLLECTION).document(monitor_id).update({
        "last_heartbeat": now,
        "last_checked": now,
        "status": "up",
        "last_status_change": now if m.get("status") != "up" else m.get("last_status_change", now),
    }, merge=True)
    m["last_heartbeat"] = now
    m["status"] = "up"
    return m


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
