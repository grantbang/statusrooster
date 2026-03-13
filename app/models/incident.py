from datetime import datetime, timezone, timedelta

COLLECTION = "incidents"


def log_incident_event(db, incident_id: str, event_type: str, metadata: dict | None = None) -> None:
    """
    Write a single event to incidents/{incident_id}/events/{auto_id}.
    event_type: 'detected' | 'alert_email_sent' | 'alert_email_failed' |
                'alert_slack_sent' | 'alert_slack_failed' |
                'alert_sms_sent' | 'alert_sms_failed' |
                'alert_webhook_sent' | 'alert_webhook_failed' |
                'resolved' | 'recovery_email_sent' | 'recovery_slack_sent' |
                'recovery_sms_sent'
    """
    try:
        db.collection(COLLECTION).document(incident_id).collection("events").add({
            "type": event_type,
            "timestamp": datetime.now(timezone.utc),
            "metadata": metadata or {},
        })
    except Exception as e:
        print(f"[incident] Failed to log event '{event_type}' for incident {incident_id}: {e}")


def get_incident_events(db, incident_id: str) -> list[dict]:
    """
    Return all events for an incident, sorted chronologically.
    """
    try:
        docs = (
            db.collection(COLLECTION)
            .document(incident_id)
            .collection("events")
            .order_by("timestamp")
            .get()
        )
        events = []
        for doc in docs:
            ev = doc.to_dict()
            ev["id"] = doc.id
            events.append(ev)
        return events
    except Exception as e:
        print(f"[incident] Failed to load events for incident {incident_id}: {e}")
        return []


def create_incident(db, monitor_id: str, monitor_name: str = "", monitor_url: str = "",
                    status_code: int | None = None, response_ms: float | None = None,
                    failure_response_headers: dict | None = None,
                    failure_error_message: str | None = None,
                    regions_checked: int | None = None,
                    regions_up: int | None = None,
                    region_results: list[dict] | None = None,
                    failure_response_body: str | None = None) -> dict:
    """
    Create a new incident when a monitor goes DOWN.
    Returns incident dict with id.
    """
    doc_ref = db.collection(COLLECTION).document()
    incident_data = {
        "monitor_id": monitor_id,
        "monitor_name": monitor_name,
        "monitor_url": monitor_url,
        "status": "open",  # open | resolved
        "status_code": status_code,
        "response_ms": response_ms,
        "started_at": datetime.now(timezone.utc),
        "resolved_at": None,
        "duration_seconds": None,
        "failure_response_headers": failure_response_headers or {},
        "failure_error_message": failure_error_message or "",
        "regions_checked": regions_checked,
        "regions_up": regions_up,
        "region_results": region_results or [],
        "failure_response_body": (failure_response_body or "")[:2048],
    }
    doc_ref.set(incident_data)
    incident_data["id"] = doc_ref.id
    return incident_data


def resolve_incident(db, incident_id: str) -> dict | None:
    """
    Resolve an open incident when a monitor comes back UP.
    Sets resolved_at and calculates duration.
    Returns updated incident dict.
    """
    doc = db.collection(COLLECTION).document(incident_id).get()
    if not doc.exists:
        return None

    incident = doc.to_dict()
    incident["id"] = doc.id

    now = datetime.now(timezone.utc)
    started_at = incident["started_at"]

    # Calculate duration in seconds
    duration = (now - started_at).total_seconds()

    updates = {
        "status": "resolved",
        "resolved_at": now,
        "duration_seconds": round(duration),
    }
    db.collection(COLLECTION).document(incident_id).update(updates)

    incident.update(updates)
    return incident


def get_incident(db, incident_id: str) -> dict | None:
    """
    Get a single incident by ID.
    Returns incident dict with id, or None if not found.
    """
    doc = db.collection(COLLECTION).document(incident_id).get()
    if not doc.exists:
        return None
    incident = doc.to_dict()
    incident["id"] = doc.id
    return incident


def get_open_incident(db, monitor_id: str) -> dict | None:
    """
    Get the current open (unresolved) incident for a monitor.
    Used for alert deduplication — if one exists, don't create another.
    """
    docs = (
        db.collection(COLLECTION)
        .where("monitor_id", "==", monitor_id)
        .where("status", "==", "open")
        .limit(1)
        .get()
    )
    for doc in docs:
        incident = doc.to_dict()
        incident["id"] = doc.id
        return incident
    return None


def list_incidents_by_monitor(db, monitor_id: str, limit: int = 20, status: str | None = None) -> list[dict]:
    """
    List incidents for a monitor, newest first.
    Optionally filter by status ("open" or "resolved").
    Used for monitor detail views and status pages.
    """
    query = db.collection(COLLECTION).where("monitor_id", "==", monitor_id)
    if status is not None:
        query = query.where("status", "==", status)
    docs = (
        query
        .order_by("started_at", direction="DESCENDING")
        .limit(limit)
        .get()
    )
    incidents = []
    for doc in docs:
        inc = doc.to_dict()
        inc["id"] = doc.id
        incidents.append(inc)
    return incidents


def list_incidents_by_user(db, monitor_ids: list[str], hours: int | None = 24, limit: int = 50, status: str | None = None) -> list[dict]:
    """
    List incidents across multiple monitors (by IDs), optionally filtered to the last N hours.
    Optionally filter by status ("open" or "resolved").
    Returns newest first.
    """
    if not monitor_ids:
        return []

    all_incidents = []
    # Firestore 'in' queries support max 30 items per batch
    for i in range(0, len(monitor_ids), 30):
        batch_ids = monitor_ids[i:i + 30]
        query = db.collection(COLLECTION).where("monitor_id", "in", batch_ids)

        if status is not None:
            query = query.where("status", "==", status)

        if hours is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            query = query.where("started_at", ">=", cutoff)

        query = query.order_by("started_at", direction="DESCENDING").limit(limit)
        docs = query.get()

        for doc in docs:
            inc = doc.to_dict()
            inc["id"] = doc.id
            all_incidents.append(inc)

    # Sort combined results newest first, then trim to limit
    all_incidents.sort(key=lambda x: x.get("started_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return all_incidents[:limit]
