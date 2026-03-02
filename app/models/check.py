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


def get_daily_uptime_bulk(db, monitor_ids: list[str], days: int = 30) -> dict[str, list[dict]]:
    """
    Get daily uptime for multiple monitors in a single Firestore query.
    Returns {monitor_id: [{date, uptime_percent}, ...]} — 30 segments for uptime bar.
    """
    if not monitor_ids:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    # Single query for all monitors' checks in the period
    docs = (
        db.collection(COLLECTION)
        .where("monitor_id", "in", monitor_ids[:30])  # Firestore 'in' limit = 30
        .where("timestamp", ">=", cutoff)
        .order_by("timestamp")
        .get()
    )

    # Bucket by monitor_id + date
    buckets: dict[str, dict[str, dict]] = {mid: {} for mid in monitor_ids}
    for doc in docs:
        c = doc.to_dict()
        mid = c.get("monitor_id")
        ts = c.get("timestamp")
        if not mid or not ts or mid not in buckets:
            continue
        day_key = ts.strftime("%Y-%m-%d")
        if day_key not in buckets[mid]:
            buckets[mid][day_key] = {"total": 0, "up": 0}
        buckets[mid][day_key]["total"] += 1
        if c.get("is_up"):
            buckets[mid][day_key]["up"] += 1

    # Build result per monitor — each entry has date label + pct
    today = datetime.now(timezone.utc).date()
    result = {}
    for mid in monitor_ids:
        bars = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            day_key = d.isoformat()
            label = d.strftime("%b %-d, '%y")
            b = buckets.get(mid, {}).get(day_key)
            if b and b["total"] > 0:
                pct = round((b["up"] / b["total"]) * 100, 3)
                bars.append({"date": label, "pct": pct})
            else:
                bars.append({"date": label, "pct": None})
        result[mid] = bars

    # Handle overflow if >30 monitors — do additional queries
    if len(monitor_ids) > 30:
        extra = get_daily_uptime_bulk(db, monitor_ids[30:], days)
        result.update(extra)

    return result


def get_hourly_uptime_bulk(db, monitor_ids: list[str], hours: int = 24) -> dict[str, list[dict]]:
    """
    Get hourly uptime for multiple monitors in a single Firestore query.
    Returns {monitor_id: [{label, pct}, ...]} — 24 segments for hourly uptime bar.
    """
    if not monitor_ids:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    docs = (
        db.collection(COLLECTION)
        .where("monitor_id", "in", monitor_ids[:30])
        .where("timestamp", ">=", cutoff)
        .order_by("timestamp")
        .get()
    )

    # Bucket by monitor_id + hour
    buckets: dict[str, dict[str, dict]] = {mid: {} for mid in monitor_ids}
    for doc in docs:
        c = doc.to_dict()
        mid = c.get("monitor_id")
        ts = c.get("timestamp")
        if not mid or not ts or mid not in buckets:
            continue
        hour_key = ts.strftime("%Y-%m-%d-%H")
        if hour_key not in buckets[mid]:
            buckets[mid][hour_key] = {"total": 0, "up": 0}
        buckets[mid][hour_key]["total"] += 1
        if c.get("is_up"):
            buckets[mid][hour_key]["up"] += 1

    # Build result per monitor — each entry has label + pct
    now = datetime.now(timezone.utc)
    result = {}
    for mid in monitor_ids:
        bars = []
        for i in range(hours - 1, -1, -1):
            h = now - timedelta(hours=i)
            hour_key = h.strftime("%Y-%m-%d-%H")
            label = h.strftime("%-I%p").lower()  # e.g. "3pm"
            if i == 0:
                label = "now"
            b = buckets.get(mid, {}).get(hour_key)
            if b and b["total"] > 0:
                pct = round((b["up"] / b["total"]) * 100, 3)
                bars.append({"date": label, "pct": pct})
            else:
                bars.append({"date": label, "pct": None})
        result[mid] = bars

    # Handle overflow if >30 monitors
    if len(monitor_ids) > 30:
        extra = get_hourly_uptime_bulk(db, monitor_ids[30:], hours)
        result.update(extra)

    return result
