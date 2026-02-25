from datetime import datetime, timezone

COLLECTION = "checks"


def create_check(db, monitor_id: str, status_code: int | None,
                 response_ms: float | None, is_up: bool) -> dict:
    """Record a check result."""
    doc_ref = db.collection(COLLECTION).document()
    check_data = {
        "monitor_id": monitor_id,
        "timestamp": datetime.now(timezone.utc),
        "status_code": status_code,
        "response_ms": response_ms,
        "is_up": is_up,
    }
    doc_ref.set(check_data)
    check_data["id"] = doc_ref.id
    return check_data


def get_recent_checks(db, monitor_id: str, limit: int = 100) -> list[dict]:
    """Get recent checks for a monitor, newest first."""
    docs = (
        db.collection(COLLECTION)
        .where("monitor_id", "==", monitor_id)
        .order_by("timestamp", direction="DESCENDING")
        .limit(limit)
        .get()
    )
    checks = []
    for doc in docs:
        c = doc.to_dict()
        c["id"] = doc.id
        checks.append(c)
    return checks
