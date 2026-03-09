import httpx
import asyncio
import time
import ssl
import socket
import json as json_lib
import logging
import random
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.models.monitor import get_all_monitors, update_monitor
from app.models.check import create_check, create_checks_batch
from app.models.incident import create_incident, resolve_incident, get_open_incident, log_incident_event
from app.services.alerts import send_down_alert, send_recovery_alert, send_ssl_expiry_alert, send_keyword_alert, send_threshold_alert, send_webhook_notification

logger = logging.getLogger(__name__)

# Limit concurrent outbound connections to avoid socket exhaustion
CHECK_CONCURRENCY = 50
_check_semaphore = asyncio.Semaphore(CHECK_CONCURRENCY)

# Shared httpx client for connection pooling (lazily created)
_shared_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx.AsyncClient with connection pooling."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
            timeout=httpx.Timeout(30.0),
        )
        logger.info("[checker] Created shared httpx.AsyncClient (pool: 100 max, 50 keepalive)")
    return _shared_client


async def close_client():
    """Close the shared httpx client gracefully."""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None
        logger.info("[checker] Closed shared httpx.AsyncClient")


async def check_url(url: str, timeout: float = 10.0, expected_status_code: int | None = None,
                    http_method: str = "GET", follow_redirects: bool = True,
                    basic_auth_user: str = "", basic_auth_pass: str = "",
                    bearer_token: str = "",
                    request_body: str = "", request_content_type: str = "",
                    custom_headers: list | None = None,
                    client: httpx.AsyncClient | None = None) -> dict:
    """
    Perform an HTTP request to the target URL.
    Returns dict with status_code, response_ms, is_up, body (first 10KB).
    Uses shared client if provided, otherwise creates a one-off client.
    """
    try:
        headers = {}
        # Custom headers (applied first so auth headers can override)
        if custom_headers:
            for h in custom_headers:
                key = h.get("key", "").strip()
                val = h.get("value", "").strip()
                if key:
                    headers[key] = val
        # Auth: Bearer token takes priority over Basic Auth
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        elif basic_auth_user and basic_auth_pass:
            import base64
            credentials = base64.b64encode(f"{basic_auth_user}:{basic_auth_pass}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

        # Request body for POST/PUT/PATCH/DELETE
        content = None
        if request_body and http_method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            content = request_body.encode("utf-8")
            if request_content_type:
                headers["Content-Type"] = request_content_type
            else:
                headers["Content-Type"] = "application/json"

        # Use shared client if provided, otherwise create a one-off client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient()
        try:
            start = time.monotonic()
            response = await client.request(
                http_method.upper(),
                url,
                timeout=timeout,
                follow_redirects=follow_redirects,
                headers=headers,
                content=content,
            )
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

            if expected_status_code:
                is_up = response.status_code == expected_status_code
            else:
                is_up = 200 <= response.status_code < 400
            # Capture response headers as a plain dict (for incident storage)
            resp_headers = dict(response.headers)
            return {
                "status_code": response.status_code,
                "response_ms": elapsed_ms,
                "is_up": is_up,
                "body": response.text[:10240] if is_up else response.text[:10240],
                "response_headers": resp_headers,
            }
        finally:
            if owns_client:
                await client.aclose()
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError):
        return {
            "status_code": None,
            "response_ms": None,
            "is_up": False,
            "body": "",
            "response_headers": {},
        }


async def check_url_with_retry(url: str, timeout: float = 10.0, expected_status_code: int | None = None,
                               http_method: str = "GET", follow_redirects: bool = True,
                               basic_auth_user: str = "", basic_auth_pass: str = "",
                               bearer_token: str = "",
                               request_body: str = "", request_content_type: str = "",
                               custom_headers: list | None = None,
                               client: httpx.AsyncClient | None = None) -> dict:
    """
    Check a URL with false positive prevention.
    If the first check fails, wait with jitter and retry once.
    Returns result dict with added 'retried' key.
    """
    _extra = dict(bearer_token=bearer_token, request_body=request_body,
                  request_content_type=request_content_type, custom_headers=custom_headers)
    result = await check_url(url, timeout, expected_status_code,
                             http_method=http_method, follow_redirects=follow_redirects,
                             basic_auth_user=basic_auth_user, basic_auth_pass=basic_auth_pass,
                             client=client, **_extra)
    if not result["is_up"]:
        # Jitter retry delay to prevent synchronized retry storms during outages
        await asyncio.sleep(random.uniform(2, 8))
        result = await check_url(url, timeout, expected_status_code,
                                 http_method=http_method, follow_redirects=follow_redirects,
                                 basic_auth_user=basic_auth_user, basic_auth_pass=basic_auth_pass,
                                 client=client, **_extra)
        result["retried"] = True
    else:
        result["retried"] = False
    return result


async def check_json_api(url: str, timeout: float = 10.0, expected_status_code: int | None = None,
                         auth_header: str = "", assertions: list | None = None,
                         client: httpx.AsyncClient | None = None) -> dict:
    """
    Check a JSON API endpoint. Validates:
    - HTTP response status
    - JSON validity
    - Field assertions (key path + operator + expected value)
    Returns dict with status_code, response_ms, is_up, body, assertion_results.
    Uses shared client if provided, otherwise creates a one-off client.
    """
    assertions = assertions or []
    try:
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header

        # Use shared client if provided, otherwise create a one-off client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient()
        try:
            start = time.monotonic()
            response = await client.get(url, timeout=timeout, follow_redirects=True, headers=headers)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

            # Check status code
            if expected_status_code:
                status_ok = response.status_code == expected_status_code
            else:
                status_ok = 200 <= response.status_code < 400

            body_text = response.text[:10240]

            # Try parsing JSON
            json_data = None
            json_valid = False
            try:
                json_data = response.json()
                json_valid = True
            except Exception:
                pass

            # Run assertions
            assertion_results = []
            assertions_passed = True
            if json_valid and json_data is not None and assertions:
                for assertion in assertions:
                    path = assertion.get("path", "")
                    operator = assertion.get("operator", "equals")
                    expected = assertion.get("value", "")
                    actual = _resolve_json_path(json_data, path)
                    passed = _evaluate_assertion(actual, operator, expected)
                    assertion_results.append({
                        "path": path,
                        "operator": operator,
                        "expected": expected,
                        "actual": str(actual) if actual is not None else None,
                        "passed": passed,
                    })
                    if not passed:
                        assertions_passed = False
            elif assertions and not json_valid:
                assertions_passed = False
                assertion_results.append({
                    "path": "*",
                    "operator": "json_valid",
                    "expected": "valid JSON",
                    "actual": "invalid",
                    "passed": False,
                })

            is_up = status_ok and json_valid and assertions_passed

            return {
                "status_code": response.status_code,
                "response_ms": elapsed_ms,
                "is_up": is_up,
                "body": body_text,
                "json_valid": json_valid,
                "assertion_results": assertion_results,
                "response_headers": dict(response.headers),
            }
        finally:
            if owns_client:
                await client.aclose()
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError):
        return {
            "status_code": None,
            "response_ms": None,
            "is_up": False,
            "body": "",
            "json_valid": False,
            "assertion_results": [],
            "response_headers": {},
        }


def _resolve_json_path(data, path: str):
    """Resolve a dot-notation JSON path like 'data.user.name' or 'items[0].id'."""
    if not path:
        return data
    parts = path.replace("[", ".[").split(".")
    current = data
    for part in parts:
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            try:
                idx = int(part[1:-1])
                current = current[idx]
            except (IndexError, TypeError, ValueError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _evaluate_assertion(actual, operator: str, expected: str) -> bool:
    """Evaluate a single JSON assertion."""
    if actual is None and operator != "not_exists":
        return False
    try:
        if operator == "equals":
            return str(actual) == str(expected)
        elif operator == "not_equals":
            return str(actual) != str(expected)
        elif operator == "contains":
            return str(expected) in str(actual)
        elif operator == "not_contains":
            return str(expected) not in str(actual)
        elif operator == "exists":
            return actual is not None
        elif operator == "not_exists":
            return actual is None
        elif operator == "greater_than":
            return float(actual) > float(expected)
        elif operator == "less_than":
            return float(actual) < float(expected)
        else:
            return str(actual) == str(expected)
    except (ValueError, TypeError):
        return False


def check_ssl_certificate(domain: str) -> dict:
    """
    Check SSL certificate for a domain.
    Returns {ssl_expiry, ssl_issuer, ssl_expiry_days, is_valid, error}.
    """
    info = {
        "ssl_expiry": None,
        "ssl_issuer": None,
        "ssl_expiry_days": None,
        "is_valid": False,
        "error": None,
    }
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        # Clean domain (strip protocol, path, port)
        domain = domain.strip()
        if domain.startswith(("http://", "https://")):
            from urllib.parse import urlparse
            parsed = urlparse(domain)
            domain = parsed.hostname or domain
        domain = domain.split("/")[0].split(":")[0]

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
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
                    info["is_valid"] = info["ssl_expiry_days"] > 0
    except Exception as e:
        info["error"] = str(e)
        print(f"[checker] SSL check failed for {domain}: {e}")
    return info


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
      - Simple:       "Welcome"              → body contains "welcome"
      - Negation:     "!error"               → body does NOT contain "error"
      - AND:          "Welcome AND Login"     → body contains both
      - OR:           "error OR failure"      → body contains at least one
      - Mixed:        "Welcome AND !error"    → contains "welcome" AND does NOT contain "error"
    AND has higher precedence than OR (standard boolean logic).
    Prefix a term with ! to negate it (NOT contains).
    """
    expression = expression.strip()
    if not expression:
        return True

    # Split by OR first (lower precedence)
    or_groups = [g.strip() for g in expression.split(" OR ")]
    for group in or_groups:
        # Each OR group may contain ANDs
        and_terms = [t.strip() for t in group.split(" AND ")]
        all_match = True
        for term in and_terms:
            if not term:
                continue
            if term.startswith("!"):
                # NOT contains — term passes if keyword is NOT in body
                needle = term[1:].strip().lower()
                if needle and needle in body:
                    all_match = False
                    break
            else:
                # Contains — term passes if keyword IS in body
                if term.lower() not in body:
                    all_match = False
                    break
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


def _percentile(sorted_values: list, pct: float) -> float:
    """Compute a percentile from a pre-sorted list of values."""
    if not sorted_values:
        return 0
    idx = int(len(sorted_values) * pct)
    idx = min(idx, len(sorted_values) - 1)
    return sorted_values[idx]


async def _check_single_monitor(monitor: dict, now: datetime) -> dict | None:
    """
    Perform the network check for a single monitor (with concurrency limiting).
    Returns a dict with {monitor, result, ssl_result?, new_monitor_status?, ssl_info?} or None if skipped.
    """
    async with _check_semaphore:
        return await _check_single_monitor_inner(monitor, now)


async def _check_single_monitor_inner(monitor: dict, now: datetime) -> dict | None:
    """Inner check logic — runs inside the semaphore. Uses shared httpx client."""
    mtype = monitor.get("monitor_type", "http")
    client = await _get_client()

    if mtype == "heartbeat":
        heartbeat_interval = monitor.get("heartbeat_interval", 300)
        grace_period = monitor.get("heartbeat_grace_period", 30)
        last_hb = monitor.get("last_heartbeat")

        last_hb_dt = None
        if last_hb:
            if isinstance(last_hb, str):
                try:
                    last_hb_dt = datetime.fromisoformat(last_hb.replace("Z", "+00:00"))
                except ValueError:
                    pass
            elif hasattr(last_hb, 'timestamp'):
                last_hb_dt = last_hb if last_hb.tzinfo else last_hb.replace(tzinfo=timezone.utc)

        if last_hb_dt is None:
            created = monitor.get("created_at")
            if created:
                created_dt = created if hasattr(created, 'timestamp') else now
                if hasattr(created_dt, 'tzinfo') and created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                age = (now - created_dt).total_seconds()
                is_up = age < heartbeat_interval + grace_period
            else:
                is_up = True
        else:
            overdue = (now - last_hb_dt).total_seconds()
            is_up = overdue <= heartbeat_interval + grace_period

        return {
            "monitor": monitor,
            "result": {"status_code": 200 if is_up else None, "response_ms": 0, "is_up": is_up, "body": ""},
        }

    elif mtype == "ssl":
        ssl_domain = monitor.get("ssl_domain", "")
        threshold_days = monitor.get("ssl_expiry_threshold_days", 14)
        if not ssl_domain:
            return None  # skip

        loop = asyncio.get_event_loop()
        ssl_result = await loop.run_in_executor(None, check_ssl_certificate, ssl_domain)

        if ssl_result.get("error"):
            is_up = False
            new_monitor_status = "down"
        elif ssl_result["ssl_expiry_days"] is not None:
            if ssl_result["ssl_expiry_days"] <= 0:
                is_up, new_monitor_status = False, "down"
            elif ssl_result["ssl_expiry_days"] <= threshold_days:
                is_up, new_monitor_status = True, "warn"
            else:
                is_up, new_monitor_status = True, "up"
        else:
            is_up, new_monitor_status = False, "down"

        return {
            "monitor": monitor,
            "result": {"status_code": 200 if is_up else None, "response_ms": 0, "is_up": is_up, "body": ""},
            "ssl_result": ssl_result,
            "new_monitor_status": new_monitor_status,
        }

    elif mtype == "json_api":
        timeout_val = monitor.get("timeout", 10)
        expected_code = monitor.get("expected_status_code")
        auth_header = monitor.get("auth_header", "")
        assertions = monitor.get("json_assertions") or []

        result = await check_json_api(
            monitor["url"], timeout=timeout_val, expected_status_code=expected_code,
            auth_header=auth_header, assertions=assertions, client=client,
        )
        # Grab SSL info concurrently for HTTPS URLs
        ssl_info = {}
        if monitor.get("url", "").startswith("https"):
            loop = asyncio.get_event_loop()
            ssl_info = await loop.run_in_executor(None, grab_ssl_info, monitor["url"])
        return {"monitor": monitor, "result": result, "ssl_info": ssl_info}

    else:
        # HTTP monitors
        timeout_val = monitor.get("timeout", 10)
        expected_code = monitor.get("expected_status_code")
        http_method = monitor.get("http_method", "GET")
        follow_redir = monitor.get("follow_redirects", True)
        ba_user = monitor.get("basic_auth_user", "")
        ba_pass = monitor.get("basic_auth_pass", "")
        bearer_tok = monitor.get("bearer_token", "")
        req_body = monitor.get("request_body", "")
        req_ct = monitor.get("request_content_type", "")
        cust_headers = monitor.get("custom_headers") or []

        result = await check_url_with_retry(
            monitor["url"], timeout=timeout_val, expected_status_code=expected_code,
            http_method=http_method, follow_redirects=follow_redir,
            basic_auth_user=ba_user, basic_auth_pass=ba_pass,
            bearer_token=bearer_tok,
            request_body=req_body, request_content_type=req_ct,
            custom_headers=cust_headers,
            client=client,
        )
        # Grab SSL info concurrently for HTTPS URLs
        ssl_info = {}
        if monitor.get("url", "").startswith("https"):
            loop = asyncio.get_event_loop()
            ssl_info = await loop.run_in_executor(None, grab_ssl_info, monitor["url"])
        return {"monitor": monitor, "result": result, "ssl_info": ssl_info}


async def check_monitor_now(monitor: dict) -> dict:
    """
    Run an immediate on-demand check for a single monitor.
    Bypasses the scheduler — runs the full check inline and returns a result dict.
    Used by the "Check now" button on monitor detail.

    Returns:
        {
            "is_up": bool,
            "status_code": int | None,
            "response_ms": int | None,
            "error": str | None,
            "ssl_expiry": str | None,
            "ssl_expiry_days": int | None,
            "checked_at": str (ISO),
        }
    """
    now = datetime.now(timezone.utc)
    mtype = monitor.get("monitor_type", "http")

    try:
        cr = await _check_single_monitor_inner(monitor, now)
    except Exception as e:
        return {
            "is_up": False,
            "status_code": None,
            "response_ms": None,
            "error": str(e),
            "ssl_expiry": None,
            "ssl_expiry_days": None,
            "checked_at": now.isoformat(),
        }

    if cr is None:
        return {
            "is_up": False,
            "status_code": None,
            "response_ms": None,
            "error": "Monitor skipped (paused or misconfigured)",
            "ssl_expiry": None,
            "ssl_expiry_days": None,
            "checked_at": now.isoformat(),
        }

    result = cr["result"]
    ssl_info = cr.get("ssl_info") or cr.get("ssl_result") or {}

    return {
        "is_up": result.get("is_up", False),
        "status_code": result.get("status_code"),
        "response_ms": result.get("response_ms"),
        "error": result.get("error_message") or (None if result.get("is_up") else "Check failed"),
        "ssl_expiry": ssl_info.get("ssl_expiry"),
        "ssl_expiry_days": ssl_info.get("ssl_expiry_days"),
        "monitor_type": mtype,
        "checked_at": now.isoformat(),
    }


async def run_checks():
    """
    Run checks for ALL monitors concurrently. Called by the cron endpoint.
    Returns summary of results.
    """
    t_cycle_start = time.monotonic()
    db = get_db()
    monitors = get_all_monitors(db)

    results = {"total": len(monitors), "up": 0, "down": 0, "skipped": 0}

    now = datetime.now(timezone.utc)

    # Phase 1: Filter monitors that are due for checking
    due_monitors = []
    for monitor in monitors:
        if monitor.get("paused", False):
            results["skipped"] += 1
            continue

        check_interval = monitor.get("check_interval", 300)
        last_checked = monitor.get("last_checked")
        if last_checked:
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

        due_monitors.append(monitor)

    # Phase 2: Run all network checks concurrently (bounded by semaphore)
    t_start = time.monotonic()
    check_tasks = [_check_single_monitor(m, now) for m in due_monitors]
    check_results = await asyncio.gather(*check_tasks, return_exceptions=True)
    t_checks = time.monotonic() - t_start
    logger.info(f"[checker] Phase 2: {len(due_monitors)} checks completed in {t_checks:.1f}s (concurrency={CHECK_CONCURRENCY})")

    # Phase 3: Process results — Firestore writes, alerts, incidents
    t_writes = time.monotonic()
    check_batch = []  # Accumulate check records for batch write
    # Instrumentation counters
    response_times = []  # Collect response_ms for percentile calculation
    retry_count = 0
    fw_writes = 0  # Firestore write operations
    errors_by_type = {}  # {monitor_type: down_count}
    for cr in check_results:
        if cr is None:
            results["skipped"] += 1
            continue
        if isinstance(cr, Exception):
            print(f"[checker] check failed with exception: {cr}")
            results["skipped"] += 1
            continue

        monitor = cr["monitor"]
        result = cr["result"]
        ssl_result = cr.get("ssl_result")
        new_monitor_status = cr.get("new_monitor_status")
        ssl_info = cr.get("ssl_info") or {}  # Pre-fetched during Phase 2

        # Accumulate check for batch write (instead of individual create_check)
        check_batch.append({
            "monitor_id": monitor["id"],
            "status_code": result["status_code"],
            "response_ms": result["response_ms"],
            "is_up": result["is_up"],
        })

        # Instrumentation: collect per-check metrics
        if result["response_ms"] is not None and result["response_ms"] > 0:
            response_times.append(result["response_ms"])
        if result.get("retried"):
            retry_count += 1
        if not result["is_up"]:
            mtype = monitor.get("monitor_type", "http")
            errors_by_type[mtype] = errors_by_type.get(mtype, 0) + 1

        # Update monitor stats
        previous_status = monitor.get("status", "pending")
        if monitor.get("monitor_type") == "ssl" and new_monitor_status:
            new_status = new_monitor_status
        else:
            new_status = "up" if result["is_up"] else "down"

        checks_total = monitor.get("checks_total", 0) + 1
        checks_failed = monitor.get("checks_failed", 0) + (0 if result["is_up"] else 1)
        uptime_percent = round(((checks_total - checks_failed) / checks_total) * 100, 2)

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
        if bars and bars[-1].get("date") == today_key:
            bars[-1]["total"] = bars[-1].get("total", 0) + 1
            if result["is_up"]:
                bars[-1]["up"] = bars[-1].get("up", 0) + 1
        else:
            bars.append({"date": today_key, "total": 1, "up": 1 if result["is_up"] else 0})
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        bars = [b for b in bars if b["date"] >= cutoff_date]
        monitor_updates["daily_uptime_bars"] = bars

        # ----- Incrementally update hourly_uptime_bars on monitor doc -----
        hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
        hbars = list(monitor.get("hourly_uptime_bars") or [])
        if hbars and hbars[-1].get("hour") == hour_key:
            hbars[-1]["total"] = hbars[-1].get("total", 0) + 1
            if result["is_up"]:
                hbars[-1]["up"] = hbars[-1].get("up", 0) + 1
        else:
            hbars.append({"hour": hour_key, "total": 1, "up": 1 if result["is_up"] else 0})
        cutoff_hour = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d-%H")
        hbars = [b for b in hbars if b["hour"] >= cutoff_hour]
        monitor_updates["hourly_uptime_bars"] = hbars

        # ----- SSL Expiry (pre-fetched in Phase 2) — HTTP monitors -----
        if monitor.get("monitor_type") == "http" and ssl_info.get("ssl_expiry"):
            monitor_updates["ssl_expiry"] = ssl_info["ssl_expiry"]
            monitor_updates["ssl_issuer"] = ssl_info["ssl_issuer"]
            monitor_updates["ssl_expiry_days"] = ssl_info["ssl_expiry_days"]

        # ----- SSL Expiry (pre-fetched in Phase 2) — JSON/API monitors -----
        if monitor.get("monitor_type") == "json_api" and ssl_info.get("ssl_expiry"):
            monitor_updates["ssl_expiry"] = ssl_info["ssl_expiry"]
            monitor_updates["ssl_issuer"] = ssl_info["ssl_issuer"]
            monitor_updates["ssl_expiry_days"] = ssl_info["ssl_expiry_days"]

        # ----- SSL cert fields for SSL monitors (merged into single update) -----
        if monitor.get("monitor_type") == "ssl" and ssl_result:
            if ssl_result.get("ssl_expiry"):
                monitor_updates["ssl_expiry"] = ssl_result["ssl_expiry"]
                monitor_updates["ssl_issuer"] = ssl_result["ssl_issuer"]
                monitor_updates["ssl_expiry_days"] = ssl_result["ssl_expiry_days"]

        if result["is_up"]:
            results["up"] += 1
        else:
            results["down"] += 1

        # ----- Check if in maintenance window (suppress alerts, not checks) -----
        in_maintenance = is_in_maintenance_window(monitor)

        # ----- Keyword Check — HTTP monitors only -----
        is_http = monitor.get("monitor_type", "http") == "http"
        keyword = monitor.get("keyword", "")
        keyword_failed = False
        if is_http and keyword and result["is_up"]:
            body_lower = result.get("body", "").lower()
            keyword_failed = not _check_keyword_expression(keyword, body_lower)
            if keyword_failed:
                if not in_maintenance:
                    await send_keyword_alert(monitor, keyword)
                    print(f"[checker] KEYWORD MISSING: '{keyword}' not found on {monitor['name']}")

        # ----- Response Time Threshold — HTTP + JSON/API monitors -----
        has_response = monitor.get("monitor_type") in ("http", "json_api")
        threshold = monitor.get("response_threshold_ms")
        if has_response and threshold and result["response_ms"] and result["is_up"]:
            threshold_str = str(threshold)
            if _check_threshold_condition(threshold_str, result["response_ms"]):
                if not in_maintenance:
                    await send_threshold_alert(monitor, result["response_ms"], threshold)
                    print(f"[checker] THRESHOLD: {monitor['name']} {result['response_ms']}ms violated condition '{threshold_str}'")

        # ----- SSL Expiry Alerts (14, 7, 3 days) — HTTP + JSON/API monitors (auto-detect) -----
        if monitor.get("monitor_type") in ("http", "json_api") and ssl_info.get("ssl_expiry_days") is not None:
            days_left = ssl_info["ssl_expiry_days"]
            last_alerted = monitor.get("ssl_expiry_alerted_days")
            for threshold_days in [14, 7, 3]:
                if days_left <= threshold_days and last_alerted != threshold_days:
                    if not in_maintenance:
                        await send_ssl_expiry_alert(monitor, days_left, ssl_info["ssl_expiry"])
                        monitor_updates["ssl_expiry_alerted_days"] = threshold_days
                    break

        # ----- SSL Monitor — Expiry alerts based on configured threshold -----
        if monitor.get("monitor_type") == "ssl" and ssl_result:
            threshold_days = monitor.get("ssl_expiry_threshold_days", 14)
            ssl_days = monitor.get("ssl_expiry_days") or ssl_result.get("ssl_expiry_days")
            if ssl_days is not None:
                last_alerted = monitor.get("ssl_expiry_alerted_days")
                if ssl_days <= threshold_days and last_alerted != threshold_days:
                    if not in_maintenance:
                        ssl_exp = monitor.get("ssl_expiry") or ssl_result.get("ssl_expiry")
                        await send_ssl_expiry_alert(monitor, ssl_days, ssl_exp)
                        monitor_updates["ssl_expiry_alerted_days"] = threshold_days

        # ----- Status change detection + Incidents + Alerts -----
        if status_changed and new_status == "down":
            existing = get_open_incident(db, monitor["id"])
            if existing is None:
                incident = create_incident(
                    db,
                    monitor_id=monitor["id"],
                    monitor_name=monitor.get("name", ""),
                    monitor_url=monitor.get("url", ""),
                    status_code=result["status_code"],
                    response_ms=result["response_ms"],
                    failure_response_headers=result.get("response_headers") or {},
                    failure_error_message=result.get("error_message") or "",
                )
                log_incident_event(db, incident["id"], "detected", {
                    "status_code": result["status_code"],
                    "response_ms": result["response_ms"],
                })
                if not in_maintenance:
                    down_results = await send_down_alert(monitor, incident)
                    for channel, ok in down_results.items():
                        log_incident_event(db, incident["id"],
                                           f"alert_{channel}_{'sent' if ok else 'failed'}")
                    if monitor.get("webhook_url"):
                        await send_webhook_notification(monitor, "monitor.down", result)
                print(f"[checker] INCIDENT CREATED: {monitor['name']} is DOWN" +
                      (" (maintenance — alerts suppressed)" if in_maintenance else ""))
            else:
                print(f"[checker] {monitor['name']} still DOWN — incident already open, skipping alert")

        elif status_changed and new_status == "up":
            open_incident = get_open_incident(db, monitor["id"])
            if open_incident:
                resolved = resolve_incident(db, open_incident["id"])
                log_incident_event(db, resolved["id"], "resolved", {
                    "duration_seconds": resolved.get("duration_seconds"),
                })
                if not in_maintenance:
                    recovery_results = await send_recovery_alert(monitor, resolved)
                    for channel, ok in recovery_results.items():
                        log_incident_event(db, resolved["id"],
                                           f"recovery_{channel}_{'sent' if ok else 'failed'}")
                    if monitor.get("webhook_url"):
                        await send_webhook_notification(monitor, "monitor.up", result)
                duration = resolved.get("duration_seconds", 0)
                print(f"[checker] INCIDENT RESOLVED: {monitor['name']} is UP (down for {duration}s)" +
                      (" (maintenance — alerts suppressed)" if in_maintenance else ""))

        # ----- Single consolidated Firestore write per monitor -----
        update_monitor(db, monitor["id"], monitor_updates)
        fw_writes += 1

    # Batch-write all check records at once (much faster than individual writes)
    if check_batch:
        try:
            create_checks_batch(db, check_batch)
            fw_writes += 1  # Count the batch as one write operation
        except Exception as e:
            logger.error(f"[checker] Batch check write failed, falling back to individual: {e}")
            for c in check_batch:
                try:
                    create_check(db, c["monitor_id"], c["status_code"], c["response_ms"], c["is_up"])
                    fw_writes += 1
                except Exception:
                    pass

    t_phase3 = time.monotonic() - t_writes
    t_total = time.monotonic() - t_cycle_start

    # ----- Instrumentation: compute percentiles and emit structured summary -----
    due_count = len(due_monitors)
    cps = due_count / t_checks if t_checks > 0 else 0
    response_times.sort()
    p50 = _percentile(response_times, 0.50) if response_times else 0
    p95 = _percentile(response_times, 0.95) if response_times else 0
    wpm = fw_writes / due_count if due_count > 0 else 0

    logger.info(
        f"[checker] CYCLE COMPLETE | total={t_total:.1f}s | due={due_count} | checks/sec={cps:.1f} | "
        f"phase2={t_checks:.1f}s | phase3={t_phase3:.1f}s | p50={p50}ms | p95={p95}ms | "
        f"retries={retry_count} | fw_writes={fw_writes} | writes/mon={wpm:.1f} | "
        f"up={results['up']} | down={results['down']} | skipped={results['skipped']} | errors_by_type={errors_by_type}"
    )

    return results
