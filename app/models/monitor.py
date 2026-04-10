from datetime import datetime, timezone
import logging
import re
import secrets
import uuid

logger = logging.getLogger(__name__)

COLLECTION = "monitors"


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a monitor name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    # Append short unique suffix to avoid collisions
    suffix = uuid.uuid4().hex[:6]
    return f"{slug}-{suffix}"


def create_monitor(db, user_id: str, url: str, name: str, alert_email: str = "",
                   alert_slack_webhook: str = "", alert_sms: str = "",
                   public: bool = False,
                   keyword: str = "", response_threshold_ms: str | None = None,
                   webhook_url: str = "", maintenance_windows: list | None = None,
                   paused: bool = False, check_interval: int | None = None,
                   monitor_type: str = "http", heartbeat_interval: int | None = None,
                   expected_status_code: int | None = None, timeout: int | None = None,
                   json_assertions: list | None = None, auth_header: str = "",
                   ssl_domain: str = "", ssl_expiry_threshold_days: int | None = None,
                   heartbeat_grace_period: int | None = None,
                   group: str = "", slug: str = "",
                   http_method: str = "GET",
                   basic_auth_user: str = "", basic_auth_pass: str = "",
                   bearer_token: str = "",
                   request_body: str = "", request_content_type: str = "",
                   custom_headers: list | None = None,
                   follow_redirects: bool = True) -> dict:
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
        # Free: custom interval 60-300s, default 60
        if check_interval is not None:
            check_interval = max(60, min(300, int(check_interval)))
        else:
            check_interval = 60

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
        "alert_sms": alert_sms,
        # HTTP-specific fields
        "timeout": timeout,                          # Request timeout in seconds
        "expected_status_code": expected_status_code,  # Expected HTTP status code (optional)
        "keyword": keyword,                          # Expected keyword in response body
        "response_threshold_ms": response_threshold_ms,  # Alert if response > this many ms
        "http_method": http_method,                  # HTTP method (GET, POST, HEAD, etc.)
        "basic_auth_user": basic_auth_user,          # Basic Auth username        "basic_auth_pass": basic_auth_pass,          # Basic Auth password        "bearer_token": bearer_token,                # Bearer token        "request_body": request_body,                # Request body for POST/PUT/PATCH
        "request_content_type": request_content_type,  # Content-Type for request body
        "custom_headers": custom_headers or [],      # Custom request headers [{key, value}]        "follow_redirects": follow_redirects,        # Follow HTTP redirects (default True)
        # JSON/API assertion fields
        "json_assertions": json_assertions or [],    # List of {path, operator, value}
        "auth_header": auth_header,                  # Authorization header value
        # Heartbeat fields
        "heartbeat_interval": heartbeat_interval,    # Expected ping interval in seconds
        "heartbeat_grace_period": heartbeat_grace_period if monitor_type == "heartbeat" else None,
        "last_heartbeat": None,                      # Last ping timestamp
        "ping_token": secrets.token_urlsafe(32) if monitor_type == "heartbeat" else None,  # Secret token for heartbeat auth
        # SSL monitor fields
        "ssl_domain": ssl_domain,                    # Domain to check SSL for (ssl type only)
        "ssl_expiry_threshold_days": ssl_expiry_threshold_days,  # Days before expiry to warn
        # Shared monitoring fields
        "webhook_url": webhook_url,                  # POST JSON on status change        "ssl_expiry": None,            # SSL cert expiry date (auto-detected on http, primary on ssl)
        "ssl_issuer": None,            # SSL cert issuer
        "ssl_expiry_alerted_days": None,  # Track which threshold we last alerted at
        "maintenance_windows": maintenance_windows or [],  # List of {day, start_utc, end_utc}        "public": public,
        "slug": slug,
        "group": group,
        "regions": [],  # Populated after checks — list of regions that checked this monitor
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
        "status": "up",
        "last_status_change": now if m.get("status") != "up" else m.get("last_status_change", now),
    })
    m["last_heartbeat"] = now
    m["status"] = "up"
    return m


def delete_monitor(db, monitor_id: str) -> None:
    """Delete a monitor and clean up a limited batch of associated data.
    
    Deletes the monitor document immediately, then cleans up a small batch
    of checks/incidents. Large histories are left as orphans (harmless)
    to avoid blocking the request for minutes on large datasets.
    """
    # Delete the monitor itself first (so it disappears from dashboard immediately)
    db.collection(COLLECTION).document(monitor_id).delete()

    # Best-effort cleanup: delete up to 50 checks and 50 incidents
    # This keeps the request fast. Orphaned docs are harmless.
    try:
        checks = db.collection("checks").where("monitor_id", "==", monitor_id).limit(50).get()
        for check in checks:
            check.reference.delete()
    except Exception:
        pass

    try:
        incidents = db.collection("incidents").where("monitor_id", "==", monitor_id).limit(50).get()
        for incident in incidents:
            incident.reference.delete()
    except Exception:
        pass


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
    """Get ALL monitors across all users (for cron check).
    
    Deprecated: use get_due_monitors() for cron/checker use cases.
    Kept for backwards compatibility with any other callers.
    """
    docs = db.collection(COLLECTION).get()
    monitors = []
    for doc in docs:
        m = doc.to_dict()
        m["id"] = doc.id
        monitors.append(m)
    return monitors


def get_due_monitors(db) -> list[dict]:
    """Get monitors that are candidates for checking (not paused).

    Filters paused=False at the Firestore query level to avoid loading
    every monitor into memory. Uses Firestore cursor pagination to fetch
    all monitors in batches of 500, so there is no hard cap on total
    monitor count. The interval check (is it time to run?) is still done
    in Python since it requires per-monitor arithmetic.
    """
    PAGE_SIZE = 500
    monitors = []
    last_doc = None

    while True:
        query = (
            db.collection(COLLECTION)
            .where("paused", "==", False)
            .limit(PAGE_SIZE)
        )
        if last_doc is not None:
            query = query.start_after(last_doc)

        docs = list(query.stream())  # Use .stream() for cursor support
        for doc in docs:
            m = doc.to_dict()
            m["id"] = doc.id
            monitors.append(m)

        if len(docs) < PAGE_SIZE:
            # Fewer results than page size — we've reached the end
            break

        last_doc = docs[-1]
        logger.info(f"[monitor] get_due_monitors: fetched batch of {len(docs)}, total so far: {len(monitors)}")

    logger.info(f"[monitor] get_due_monitors: loaded {len(monitors)} monitors total")
    return monitors
