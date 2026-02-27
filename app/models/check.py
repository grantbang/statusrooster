from datetime import datetime, timezone, timedelta

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


def get_daily_uptime(db, monitor_id: str, days: int = 90) -> list[dict]:
    """
    Get daily uptime summary for the last N days.
    Returns list of dicts: [{date, total, up, down, uptime_percent}, ...]
    Ordered oldest → newest for the uptime bar.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    docs = (
        db.collection(COLLECTION)
        .where("monitor_id", "==", monitor_id)
        .where("timestamp", ">=", cutoff)
        .order_by("timestamp")
        .get()
    )

    # Bucket checks by date
    daily = {}
    for doc in docs:
        c = doc.to_dict()
        ts = c.get("timestamp")
        if not ts:
            continue
        day_key = ts.strftime("%Y-%m-%d")
        if day_key not in daily:
            daily[day_key] = {"date": day_key, "total": 0, "up": 0, "down": 0}
        daily[day_key]["total"] += 1
        if c.get("is_up"):
            daily[day_key]["up"] += 1
        else:
            daily[day_key]["down"] += 1

    # Build full list for N days (fill gaps with None = no data)
    result = []
    today = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):  # oldest first
        d = today - timedelta(days=i)
        day_key = d.isoformat()
        if day_key in daily:
            entry = daily[day_key]
            entry["uptime_percent"] = round((entry["up"] / entry["total"]) * 100, 1) if entry["total"] > 0 else None
            result.append(entry)
        else:
            result.append({"date": day_key, "total": 0, "up": 0, "down": 0, "uptime_percent": None})

    return result
