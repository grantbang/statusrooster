"""
checker_core — Pure check logic shared between the primary StatusRooster service
and regional worker services.

This module contains ONLY the network check functions (HTTP, JSON/API, SSL, heartbeat
helpers) and SSRF protection. It has ZERO dependencies on app.database, app.models,
or app.services — keeping it portable for lightweight Cloud Run worker deployments.

v1.1.0 — Added custom_headers support for JSON/API monitors
"""

import httpx
import asyncio
import time
import ssl
import socket
import ipaddress
import random
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── SSRF Protection ────────────────────────────────────────────────────────────

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private class A
    ipaddress.ip_network("172.16.0.0/12"),    # Private class B
    ipaddress.ip_network("192.168.0.0/16"),   # Private class C
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / GCP metadata
    ipaddress.ip_network("100.64.0.0/10"),    # Shared address space
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


def validate_url_not_internal(url: str) -> None:
    """Raise ValueError if the URL resolves to a private/internal IP address.
    
    Prevents SSRF attacks where users submit internal URLs (metadata server,
    localhost, RFC-1918 ranges) to be fetched by the checker from within Cloud Run.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"Invalid URL: no hostname in {url!r}")
        # Resolve all addresses the hostname maps to
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        for info in infos:
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            for network in _PRIVATE_NETWORKS:
                if ip in network:
                    raise ValueError(
                        f"URL resolves to a private/internal IP ({ip}) — "
                        "monitoring internal addresses is not allowed."
                    )
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not resolve hostname for SSRF check: {e}") from e


# ── HTTP Check ─────────────────────────────────────────────────────────────────

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
        validate_url_not_internal(url)
    except ValueError as e:
        return {"is_up": False, "status_code": None, "response_ms": None, "body": "", "error": str(e), "ssrf_blocked": True}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; StatusRooster/1.0; +https://statusrooster.com)",
        }
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


# ── JSON/API Check ─────────────────────────────────────────────────────────────

async def check_json_api(url: str, timeout: float = 10.0, expected_status_code: int | None = None,
                         auth_header: str = "", assertions: list | None = None,
                         client: httpx.AsyncClient | None = None,
                         http_method: str = "GET",
                         request_body: str = "", request_content_type: str = "",
                         custom_headers: list | None = None) -> dict:
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
        validate_url_not_internal(url)
    except ValueError as e:
        return {"is_up": False, "status_code": None, "response_ms": None, "body": "", "error": str(e), "ssrf_blocked": True, "assertion_results": []}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; StatusRooster/1.0; +https://statusrooster.com)",
        }
        # Custom headers (applied first so auth header can override)
        if custom_headers:
            for h in custom_headers:
                key = h.get("key", "").strip()
                val = h.get("value", "").strip()
                if key:
                    headers[key] = val
        if auth_header:
            headers["Authorization"] = auth_header

        # Use shared client if provided, otherwise create a one-off client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient()
        try:
            start = time.monotonic()
            method = http_method.upper() if http_method else "GET"
            kwargs: dict = {"timeout": timeout, "follow_redirects": True, "headers": headers}
            if method != "GET" and request_body:
                if request_content_type:
                    headers["Content-Type"] = request_content_type
                kwargs["content"] = request_body.encode()
            response = await client.request(method, url, **kwargs)
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


# ── JSON Path & Assertion Helpers ──────────────────────────────────────────────

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


# ── SSL Check ──────────────────────────────────────────────────────────────────

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


# ── Keyword & Threshold Helpers ────────────────────────────────────────────────

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
