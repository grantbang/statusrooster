import httpx
import asyncio
import time
import ssl
import socket
from datetime import datetime, timezone
from app.database import get_db
from app.models.monitor import get_all_monitors, update_monitor
from app.models.check import create_check
from app.models.incident import create_incident, resolve_incident, get_open_incident
from app.services.alerts import send_down_alert, send_recovery_alert, send_ssl_expiry_alert, send_keyword_alert, send_threshold_alert, send_webhook_notification


async def check_url(url: str, timeout: float = 10.0) -> dict:
    """
    Perform an HTTP GET to the target URL.
    Returns dict with status_code, response_ms, is_up, body (first 10KB).
    """
    try:
        async with httpx.AsyncClient() as client:
            start = time.monotonic()
            response = await client.get(url, timeout=timeout, follow_redirects=True)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

            is_up = 200 <= response.status_code < 400
            return {
                "status_code": response.status_code,
                "response_ms": elapsed_ms,
                "is_up": is_up,
                "body": response.text[:10240] if is_up else "",
            }
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError):
        return {
            "status_code": None,
            "response_ms": None,
            "is_up": False,
            "body": "",
        }


async def check_url_with_retry(url: str, timeout: float = 10.0) -> dict:
    """
    Check a URL with false positive prevention.
    If the first check fails, wait 5 seconds and retry once.
    """
    result = await check_url(url, timeout)
    if not result["is_up"]:
        # Retry once after 5 seconds to prevent false positives
        await asyncio.sleep(5)
        result = await check_url(url, timeout)
    return result


def grab_ssl_info(url: str) -> dict:
    """
    Grab SSL certificate info for an HTTPS URL.
    Returns {ssl_expiry: datetime|None, ssl_issuer: str|None, ssl_expiry_days: int|None}.
    """
    info = {"ssl_expiry": None, "ssl_issuer": None, "ssl_expiry_days": None}
    try:
        from urllib.parse import urlparse
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        parsed = urlparse(url)
        if parsed.scheme != "https":
            return info

        hostname = parsed.hostname
        port = parsed.port or 443

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((hostname, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                der = ssock.getpeercert(binary_form=True)
                if der:
                    cert = x509.load_der_x509_certificate(der, default_backend())
                    # Issuer
                    try:
                        org = cert.issuer.get_attributes_for_oid(x509.oid.NameOID.ORGANIZATION_NAME)
                        info["ssl_issuer"] = org[0].value if org else None
                    except Exception:
                        pass
                    if not info["ssl_issuer"]:
                        try:
                            cn = cert.issuer.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
                            info["ssl_issuer"] = cn[0].value if cn else "Unknown"
                        except Exception:
                            info["ssl_issuer"] = "Unknown"
                    # Expiry
                    exp = cert.not_valid_after_utc
                    info["ssl_expiry"] = exp
                    info["ssl_expiry_days"] = (exp - datetime.now(timezone.utc)).days
    except Exception as e:
        print(f"[checker] SSL grab failed for {url}: {e}")
    return info


def is_in_maintenance_window(monitor: dict) -> bool:
    """Check if the current UTC time falls within any of the monitor's maintenance windows."""
    # Support both legacy single window and new array format
    windows = monitor.get("maintenance_windows") or []
    legacy = monitor.get("maintenance_window")
    if legacy and isinstance(legacy, dict):
        windows = [legacy]  # backwards compatibility
    if not windows:
        return False

    now = datetime.now(timezone.utc)
    day_name = now.strftime("%A")  # Monday, Tuesday, etc.
    now_minutes = now.hour * 60 + now.minute

    for mw in windows:
        mw_day = mw.get("day", "")
        if mw_day and mw_day.lower() != "daily" and mw_day.lower() != day_name.lower():
            continue

        try:
            start_h, start_m = map(int, mw.get("start_utc", "00:00").split(":"))
            end_h, end_m = map(int, mw.get("end_utc", "00:00").split(":"))
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m

            if start_minutes <= end_minutes:
                if start_minutes <= now_minutes <= end_minutes:
                    return True
            else:
                # Overnight window (e.g., 23:00 - 03:00)
                if now_minutes >= start_minutes or now_minutes <= end_minutes:
                    return True
        except Exception:
            continue

    return False


def _check_keyword_expression(expression: str, body: str) -> bool:
    """
    Evaluate a keyword expression against page body.
    Supports:
      - Simple:  "Welcome"          → body contains "welcome"
      - AND:     "Welcome AND Login" → body contains both
      - OR:      "error OR failure"  → body contains at least one
    AND has higher precedence than OR (standard boolean logic).
    """
    expression = expression.strip()
    if not expression:
        return True

    # Split by OR first (lower precedence)
    or_groups = [g.strip() for g in expression.split(" OR ")]
    for group in or_groups:
        # Each OR group may contain ANDs
        and_terms = [t.strip() for t in group.split(" AND ")]
        all_match = all(term.lower() in body for term in and_terms if term)
        if all_match:
            return True
    return False


def _check_threshold_condition(condition_str: str, actual_ms: float) -> bool:
    """
    Evaluate a response threshold condition.
    Supports:
      - Simple number:  "2000"       → alert if response > 2000ms
      - Greater than:   "> 2000"     → alert if response > 2000ms
      - Less than:      "< 200"      → alert if response < 200ms
      - Range:          "200-3000"   → alert if response outside range
    Returns True if the condition is VIOLATED (should alert).
    """
    condition_str = condition_str.strip()
    if not condition_str:
        return False

    try:
        # Range: "200-3000" — alert if outside range
        if "-" in condition_str and not condition_str.startswith(("-", "<", ">")):
            parts = condition_str.split("-", 1)
            low = float(parts[0].strip())
            high = float(parts[1].strip())
            return actual_ms < low or actual_ms > high

        # Less than: "< 200" — alert if too fast (possible empty response)
        if condition_str.startswith("<"):
            val = float(condition_str[1:].strip())
            return actual_ms < val

        # Greater than: "> 2000" or just "2000"
        if condition_str.startswith(">"):
            val = float(condition_str[1:].strip())
            return actual_ms > val

        # Plain number — treat as "> value"
        val = float(condition_str)
        return actual_ms > val
    except (ValueError, IndexError):
        return False


async def run_checks():
    """
    Run checks for ALL monitors. Called by the cron endpoint.
    Returns summary of results.
    """
    db = get_db()
    monitors = get_all_monitors(db)

    results = {"total": len(monitors), "up": 0, "down": 0, "skipped": 0}

    now = datetime.now(timezone.utc)

    for monitor in monitors:
        # Skip paused monitors entirely
        if monitor.get("paused", False):
            results["skipped"] += 1
            continue

        # Enforce check interval — skip if not due yet
        check_interval = monitor.get("check_interval", 300)  # default 5min (Free)
        last_checked = monitor.get("last_checked")
        if last_checked:
            # Handle Firestore DatetimeWithNanoseconds or string
            if isinstance(last_checked, str):
                try:
                    last_checked_dt = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
                except ValueError:
                    last_checked_dt = None
            elif hasattr(last_checked, 'timestamp'):
                last_checked_dt = last_checked if last_checked.tzinfo else last_checked.replace(tzinfo=timezone.utc)
            else:
                last_checked_dt = None

            if last_checked_dt:
                elapsed = (now - last_checked_dt).total_seconds()
                if elapsed < check_interval:
                    results["skipped"] += 1
                    continue

        # Perform the check with retry
        result = await check_url_with_retry(monitor["url"])

        # Record check in Firestore
        create_check(
            db,
            monitor_id=monitor["id"],
            status_code=result["status_code"],
            response_ms=result["response_ms"],
            is_up=result["is_up"],
        )

        # Update monitor stats
        previous_status = monitor.get("status", "pending")
        new_status = "up" if result["is_up"] else "down"

        checks_total = monitor.get("checks_total", 0) + 1
        checks_failed = monitor.get("checks_failed", 0) + (0 if result["is_up"] else 1)
        uptime_percent = round(((checks_total - checks_failed) / checks_total) * 100, 2)

        # Track when the status last changed (for "Up for X" / "Down for X")
        status_changed = previous_status != new_status

        monitor_updates = {
            "status": new_status,
            "last_checked": datetime.now(timezone.utc),
            "last_status_code": result["status_code"],
            "last_response_ms": result["response_ms"],
            "uptime_percent": uptime_percent,
            "checks_total": checks_total,
            "checks_failed": checks_failed,
        }

        if status_changed:
            monitor_updates["last_status_change"] = datetime.now(timezone.utc)

        # ----- Incrementally update daily_uptime_bars on monitor doc -----
        today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        bars = list(monitor.get("daily_uptime_bars") or [])
        # Find or create today's entry
        if bars and bars[-1].get("date") == today_key:
            bars[-1]["total"] = bars[-1].get("total", 0) + 1
            if result["is_up"]:
                bars[-1]["up"] = bars[-1].get("up", 0) + 1
        else:
            bars.append({"date": today_key, "total": 1, "up": 1 if result["is_up"] else 0})
        # Prune entries older than 30 days
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        bars = [b for b in bars if b["date"] >= cutoff_date]
        monitor_updates["daily_uptime_bars"] = bars

        # ----- Incrementally update hourly_uptime_bars on monitor doc -----
        hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
        hbars = list(monitor.get("hourly_uptime_bars") or [])
        # Find or create this hour's entry
        if hbars and hbars[-1].get("hour") == hour_key:
            hbars[-1]["total"] = hbars[-1].get("total", 0) + 1
            if result["is_up"]:
                hbars[-1]["up"] = hbars[-1].get("up", 0) + 1
        else:
            hbars.append({"hour": hour_key, "total": 1, "up": 1 if result["is_up"] else 0})
        # Prune entries older than 24 hours
        cutoff_hour = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d-%H")
        hbars = [b for b in hbars if b["hour"] >= cutoff_hour]
        monitor_updates["hourly_uptime_bars"] = hbars

        # ----- SSL Expiry Check -----
        ssl_info = grab_ssl_info(monitor["url"])
        if ssl_info["ssl_expiry"]:
            monitor_updates["ssl_expiry"] = ssl_info["ssl_expiry"]
            monitor_updates["ssl_issuer"] = ssl_info["ssl_issuer"]
            monitor_updates["ssl_expiry_days"] = ssl_info["ssl_expiry_days"]

        update_monitor(db, monitor["id"], monitor_updates)

        if result["is_up"]:
            results["up"] += 1
        else:
            results["down"] += 1

        # ----- Check if in maintenance window (suppress alerts, not checks) -----
        in_maintenance = is_in_maintenance_window(monitor)

        # ----- Keyword Check (supports AND / OR operators) -----
        keyword = monitor.get("keyword", "")
        keyword_failed = False
        if keyword and result["is_up"]:
            body_lower = result.get("body", "").lower()
            keyword_failed = not _check_keyword_expression(keyword, body_lower)
            if keyword_failed:
                if not in_maintenance:
                    await send_keyword_alert(monitor, keyword)
                    print(f"[checker] KEYWORD MISSING: '{keyword}' not found on {monitor['name']}")

        # ----- Response Time Threshold (supports >, <, range) -----
        threshold = monitor.get("response_threshold_ms")
        if threshold and result["response_ms"] and result["is_up"]:
            threshold_str = str(threshold)
            if _check_threshold_condition(threshold_str, result["response_ms"]):
                if not in_maintenance:
                    await send_threshold_alert(monitor, result["response_ms"], threshold)
                    print(f"[checker] THRESHOLD: {monitor['name']} {result['response_ms']}ms violated condition '{threshold_str}'")

        # ----- SSL Expiry Alerts (14, 7, 3 days) -----
        if ssl_info["ssl_expiry_days"] is not None:
            days_left = ssl_info["ssl_expiry_days"]
            last_alerted = monitor.get("ssl_expiry_alerted_days")
            for threshold_days in [14, 7, 3]:
                if days_left <= threshold_days and last_alerted != threshold_days:
                    if not in_maintenance:
                        await send_ssl_expiry_alert(monitor, days_left, ssl_info["ssl_expiry"])
                        update_monitor(db, monitor["id"], {"ssl_expiry_alerted_days": threshold_days})
                    break

        # ----- Status change detection + Incidents + Alerts -----
        if status_changed and new_status == "down":
            # UP → DOWN: Check for existing open incident (deduplication)
            existing = get_open_incident(db, monitor["id"])
            if existing is None:
                # Create new incident
                incident = create_incident(
                    db,
                    monitor_id=monitor["id"],
                    monitor_name=monitor.get("name", ""),
                    monitor_url=monitor.get("url", ""),
                    status_code=result["status_code"],
                    response_ms=result["response_ms"],
                )
                # Trigger down alerts (unless in maintenance)
                if not in_maintenance:
                    await send_down_alert(monitor, incident)
                    # Webhook notification
                    if monitor.get("webhook_url"):
                        await send_webhook_notification(monitor, "monitor.down", result)
                print(f"[checker] INCIDENT CREATED: {monitor['name']} is DOWN" +
                      (" (maintenance — alerts suppressed)" if in_maintenance else ""))
            else:
                print(f"[checker] {monitor['name']} still DOWN — incident already open, skipping alert")

        elif status_changed and new_status == "up":
            # DOWN → UP: Resolve open incident
            open_incident = get_open_incident(db, monitor["id"])
            if open_incident:
                resolved = resolve_incident(db, open_incident["id"])
                # Trigger recovery alerts (unless in maintenance)
                if not in_maintenance:
                    await send_recovery_alert(monitor, resolved)
                    # Webhook notification
                    if monitor.get("webhook_url"):
                        await send_webhook_notification(monitor, "monitor.up", result)
                duration = resolved.get("duration_seconds", 0)
                print(f"[checker] INCIDENT RESOLVED: {monitor['name']} is UP (down for {duration}s)" +
                      (" (maintenance — alerts suppressed)" if in_maintenance else ""))

    return results
