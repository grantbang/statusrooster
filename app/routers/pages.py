"""
Page routes — serves all HTML templates.
Separate from API routes which return JSON.
"""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.database import get_db
from app.models.user import create_user, get_user_by_email, verify_password, get_user_by_id, update_user, hash_password, delete_user, create_password_reset_token, verify_password_reset_token, consume_password_reset_token
from app.models.monitor import list_monitors_by_user, get_monitor, get_monitor_by_slug, create_monitor, update_monitor, delete_monitor
from app.models.check import get_recent_checks, get_daily_uptime
from app.models.incident import list_incidents_by_monitor, list_incidents_by_user, get_incident, get_incident_events
from app.models.api_key import generate_api_key, list_api_keys, revoke_api_key
from app.services.auth import create_access_token, decode_access_token
from app.services.alerts import _format_duration, send_test_alert
from app.services.checker import check_monitor_now
import os
import re

router = APIRouter(tags=["pages"], include_in_schema=False)


def _set_flash(response, message: str, flash_type: str = "success"):
    """Set flash message cookies with security flags."""
    cookie_opts = dict(max_age=10, httponly=True, secure=True, samesite="lax")
    response.set_cookie("flash_message", message, **cookie_opts)
    response.set_cookie("flash_type", flash_type, **cookie_opts)

# Templates setup
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


# ---------------------------------------------------------------------------
# Helper: normalize + validate SMS number (E.164 format)
# Returns (normalized_str, error_str|None)
# ---------------------------------------------------------------------------

def _normalize_sms(raw: str) -> tuple[str, str | None]:
    """Strip spaces/dashes/parens, validate E.164 format (+CC + 6-14 digits).
    Returns (normalized, None) on success, ('', error_message) on failure."""
    val = raw.strip()
    if not val:
        return ("", None)
    normalized = re.sub(r"[\s\-\(\)]", "", val)
    if re.match(r"^\+[1-9]\d{6,14}$", normalized):
        return (normalized, None)
    return ("", "Invalid SMS number. Use international format: +15551234567 or +447911123456")


# ---------------------------------------------------------------------------
# Helper: get current user from cookie (returns None if not logged in)
# ---------------------------------------------------------------------------

def get_user_from_cookie(request: Request) -> dict | None:
    """Try to get the current user from the access_token cookie. Returns None if not logged in."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        db = get_db()
        user = get_user_by_id(db, payload["sub"])
        return user
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Landing Page
# ---------------------------------------------------------------------------

@router.head("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, preview: str = None):
    user = get_user_from_cookie(request)
    if user and preview is None:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("landing.html", {"request": request, "user": None})


# ---------------------------------------------------------------------------
# Public URL Check (landing page teaser)
# ---------------------------------------------------------------------------

# Rate limiter: max 10 requests per IP per 60 seconds
_url_check_rate: dict[str, list] = {}
_url_check_cleanup_counter = 0
_URL_CHECK_LIMIT = 10
_URL_CHECK_WINDOW = 60  # seconds

# Rate limiter for discover-preview: max 5 per IP per 60 seconds
_discover_rate: dict[str, list] = {}
_discover_cleanup_counter = 0
_DISCOVER_LIMIT = 5
_DISCOVER_WINDOW = 60

@router.post("/api/check-url")
async def public_url_check(request: Request):
    """Public endpoint: check a single URL and return enriched status."""
    import httpx, time, re, ssl, socket
    from fastapi.responses import JSONResponse
    from datetime import datetime, timezone

    # Rate limiting by client IP
    client_ip = request.client.host if request.client else "unknown"
    now_ts = time.monotonic()

    hits = _url_check_rate.get(client_ip, [])
    hits = [t for t in hits if now_ts - t < _URL_CHECK_WINDOW]
    if len(hits) >= _URL_CHECK_LIMIT:
        retry_after = int(_URL_CHECK_WINDOW - (now_ts - hits[0]))
        return JSONResponse(
            {"error": "Rate limit exceeded. Try again shortly.", "retry_after": retry_after},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now_ts)
    _url_check_rate[client_ip] = hits

    # Periodic cleanup of stale IPs to prevent memory leak
    global _url_check_cleanup_counter
    _url_check_cleanup_counter += 1
    if _url_check_cleanup_counter >= 100:
        _url_check_cleanup_counter = 0
        stale_cutoff = now_ts - (_URL_CHECK_WINDOW * 5)
        stale_ips = [ip for ip, h in _url_check_rate.items() if not h or h[-1] < stale_cutoff]
        for ip in stale_ips:
            del _url_check_rate[ip]

    body = await request.json()
    url = body.get("url", "").strip()

    if not url:
        return JSONResponse({"error": "URL is required"}, status_code=400)
    if not re.match(r'^https?://', url):
        url = f"https://{url}"

    # SSRF protection — block private/internal IPs
    try:
        from app.services.checker import validate_url_not_internal
        validate_url_not_internal(url)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    # Rich check — we do it inline to grab headers + SSL info
    result = {
        "url": url,
        "is_up": False,
        "status_code": None,
        "response_ms": None,
        "server": None,
        "content_type": None,
        "ssl_issuer": None,
        "ssl_expiry": None,
        "redirects": 0,
        "final_url": url,
    }

    try:
        async with httpx.AsyncClient() as client:
            start = time.monotonic()
            resp = await client.get(url, timeout=8.0, follow_redirects=True)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

            result["is_up"] = 200 <= resp.status_code < 400
            result["status_code"] = resp.status_code
            result["response_ms"] = elapsed_ms
            result["server"] = resp.headers.get("server")
            result["content_type"] = (resp.headers.get("content-type") or "").split(";")[0].strip() or None
            result["redirects"] = len(resp.history)
            result["final_url"] = str(resp.url)
    except Exception:
        pass

    # SSL certificate info
    try:
        from urllib.parse import urlparse
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        parsed = urlparse(result["final_url"])
        if parsed.scheme == "https":
            hostname = parsed.hostname
            port = parsed.port or 443

            # Connect without strict verification so we always get the cert
            ctx2 = ssl.create_default_context()
            ctx2.check_hostname = False
            ctx2.verify_mode = ssl.CERT_NONE
            with socket.create_connection((hostname, port), timeout=4) as sock:
                with ctx2.wrap_socket(sock, server_hostname=hostname) as ssock:
                    der = ssock.getpeercert(binary_form=True)
                    if der:
                        cert = x509.load_der_x509_certificate(der, default_backend())
                        # Issuer org name
                        try:
                            org = cert.issuer.get_attributes_for_oid(x509.oid.NameOID.ORGANIZATION_NAME)
                            result["ssl_issuer"] = org[0].value if org else None
                        except Exception:
                            pass
                        if not result["ssl_issuer"]:
                            try:
                                cn = cert.issuer.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
                                result["ssl_issuer"] = cn[0].value if cn else "Valid"
                            except Exception:
                                result["ssl_issuer"] = "Valid"
                        # Expiry
                        exp = cert.not_valid_after_utc
                        days_left = (exp - datetime.now(timezone.utc)).days
                        result["ssl_expiry"] = f"{exp.strftime('%b %d, %Y')} ({days_left}d)"
    except Exception:
        pass

    return JSONResponse(result)


@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    user = get_user_from_cookie(request)
    return templates.TemplateResponse("pricing.html", {"request": request, "user": user})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    user = get_user_from_cookie(request)
    return templates.TemplateResponse("privacy.html", {"request": request, "user": user})


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    user = get_user_from_cookie(request)
    return templates.TemplateResponse("terms.html", {"request": request, "user": user})


@router.get("/sms-consent", response_class=HTMLResponse)
async def sms_consent_page(request: Request):
    user = get_user_from_cookie(request)
    return templates.TemplateResponse("sms_consent.html", {"request": request, "user": user})


@router.get("/cookies", response_class=HTMLResponse)
async def cookies_page(request: Request):
    user = get_user_from_cookie(request)
    return templates.TemplateResponse("cookies.html", {"request": request, "user": user})


# ---------------------------------------------------------------------------
# Auth Pages
# ---------------------------------------------------------------------------

@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    user = get_user_from_cookie(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("signup.html", {"request": request, "user": None, "error": None})


@router.post("/signup", response_class=HTMLResponse)
async def signup_submit(request: Request, email: str = Form(...), password: str = Form(...), password_confirm: str = Form(...)):
    import re as _re
    # Validate email format
    email = email.strip().lower()
    if not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return templates.TemplateResponse("signup.html", {
            "request": request, "user": None, "error": "Please enter a valid email address.", "email": email
        })

    # Validate
    if password != password_confirm:
        return templates.TemplateResponse("signup.html", {
            "request": request, "user": None, "error": "Passwords don't match", "email": email
        })

    if len(password) < 8:
        return templates.TemplateResponse("signup.html", {
            "request": request, "user": None, "error": "Password must be at least 8 characters", "email": email
        })

    db = get_db()
    existing = get_user_by_email(db, email)
    if existing:
        return templates.TemplateResponse("signup.html", {
            "request": request, "user": None, "error": "Email already registered", "email": email
        })

    # Create user
    user = create_user(db, email, password)

    # Capture referral source if present
    ref = request.query_params.get("ref", "")
    if ref:
        from app.models.user import update_user
        update_user(db, user["id"], {"referral_source": ref[:100]})

    token = create_access_token(user_id=user["id"], email=user["email"])

    # Redirect to discover if domain was passed, otherwise dashboard
    domain = request.query_params.get("domain", "")
    redirect_url = f"/discover?domain={domain}" if domain else "/dashboard"
    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=72 * 3600,  # 72 hours
    )
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_user_from_cookie(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    error = request.query_params.get("error")
    flash_message = request.cookies.get("flash_message")
    flash_type = request.cookies.get("flash_type", "success")
    return templates.TemplateResponse("login.html", {
        "request": request, "user": None, "error": error,
        "flash_message": flash_message, "flash_type": flash_type,
    })


@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = get_user_by_email(db, email)

    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request, "user": None, "error": "Invalid email or password", "email": email
        })

    # OAuth-only user trying to use password login
    if not user.get("password_hash"):
        provider = user.get("auth_provider", "OAuth")
        return templates.TemplateResponse("login.html", {
            "request": request, "user": None,
            "error": f"This account uses {provider.title()} login. Use the button above.",
            "email": email
        })

    if not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse("login.html", {
            "request": request, "user": None, "error": "Invalid email or password", "email": email
        })

    token = create_access_token(user_id=user["id"], email=user["email"])

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=72 * 3600,
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ---------------------------------------------------------------------------
# Forgot / Reset Password
# ---------------------------------------------------------------------------

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request, "user": None})


@router.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password_submit(request: Request, email: str = Form(...)):
    from app.services.alerts import send_email
    from app.config import settings

    email = email.strip().lower()
    db = get_db()
    user = get_user_by_email(db, email)

    # Always show success message to prevent email enumeration
    success_msg = "If an account exists with that email, we've sent a reset link. Check your inbox (and spam folder)."

    if not user:
        return templates.TemplateResponse("forgot_password.html", {
            "request": request, "user": None, "success": success_msg, "email": email
        })

    # Only email-auth users can reset passwords
    if not user.get("password_hash"):
        provider = user.get("auth_provider", "OAuth")
        return templates.TemplateResponse("forgot_password.html", {
            "request": request, "user": None,
            "error": f"This account uses {provider.title()} login. Please sign in with {provider.title()} instead.",
            "email": email
        })

    raw_token = create_password_reset_token(db, user["id"], email)
    reset_url = f"{settings.APP_URL}/reset-password?token={raw_token}"

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 2rem;">
        <h2 style="color: #1a1a1a; margin-bottom: 0.5rem;">Reset your password</h2>
        <p style="color: #4a4a4a; line-height: 1.6;">
            We received a request to reset the password for your StatusRooster account.
            Click the button below to choose a new password.
        </p>
        <div style="text-align: center; margin: 2rem 0;">
            <a href="{reset_url}" style="display: inline-block; background: #6366f1; color: #ffffff; padding: 0.75rem 2rem; border-radius: 8px; text-decoration: none; font-weight: 600;">
                Reset password
            </a>
        </div>
        <p style="color: #6b7280; font-size: 0.875rem; line-height: 1.5;">
            This link expires in 30 minutes. If you didn't request this, you can safely ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0;">
        <p style="color: #9ca3af; font-size: 0.75rem;">
            If the button doesn't work, copy and paste this URL into your browser:<br>
            <span style="word-break: break-all;">{reset_url}</span>
        </p>
    </div>
    """

    await send_email(email, "Reset your StatusRooster password", html_body)

    return templates.TemplateResponse("forgot_password.html", {
        "request": request, "user": None, "success": success_msg, "email": email
    })


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    token = request.query_params.get("token", "")
    if not token:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "user": None, "expired": True
        })

    db = get_db()
    token_doc = verify_password_reset_token(db, token)
    if not token_doc:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "user": None, "expired": True
        })

    return templates.TemplateResponse("reset_password.html", {
        "request": request, "user": None, "token": token
    })


@router.post("/reset-password", response_class=HTMLResponse)
async def reset_password_submit(request: Request, token: str = Form(...), password: str = Form(...), password_confirm: str = Form(...)):
    db = get_db()
    token_doc = verify_password_reset_token(db, token)

    if not token_doc:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "user": None, "expired": True
        })

    if len(password) < 8:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "user": None, "token": token,
            "error": "Password must be at least 8 characters."
        })

    if password != password_confirm:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "user": None, "token": token,
            "error": "Passwords don't match."
        })

    # Update password and consume token
    update_user(db, token_doc["user_id"], {"password_hash": hash_password(password)})
    consume_password_reset_token(db, token_doc["id"])

    response = RedirectResponse(url="/login", status_code=302)
    _set_flash(response, "Password reset successful. Please log in with your new password.")
    return response


# ---------------------------------------------------------------------------
# Auto-Discovery
# ---------------------------------------------------------------------------

@router.get("/discover", response_class=HTMLResponse)
async def discover_page(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    domain = request.query_params.get("domain", "")
    db = get_db()
    current_monitors = len(db.collection("monitors").where("user_id", "==", user["id"]).get())
    monitor_limit = 200 if user.get("plan", "free") == "pro" else 10
    return templates.TemplateResponse("discover.html", {
        "request": request, "user": user, "prefill_domain": domain,
        "monitors_current": current_monitors, "monitors_limit": monitor_limit,
    })


@router.post("/api/discover-create")
async def discover_create_monitors(request: Request):
    """Create monitors from discovery results (session-authenticated, no API key needed)."""
    from fastapi.responses import JSONResponse
    from app.models.monitor import create_monitor as _create_mon, update_monitor as _update_mon

    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    body = await request.json()
    monitors = body.get("monitors", [])
    if not monitors:
        return JSONResponse({"error": "No monitors provided"}, status_code=422)

    db = get_db()
    plan = user.get("plan", "free")
    limit = 200 if plan == "pro" else 10

    # Use actual Firestore count — monitors_count field can drift
    existing = db.collection("monitors").where("user_id", "==", user["id"]).get()
    current = len(existing)

    if current + len(monitors) > limit:
        remaining = max(0, limit - current)
        return JSONResponse({"error": f"Would exceed monitor limit ({current}/{limit}). Can create {remaining} more."}, status_code=403)

    created = []
    for item in monitors:
        try:
            mon = _create_mon(
                db,
                user_id=user["id"],
                url=item.get("url", ""),
                name=item.get("name", "Untitled"),
                monitor_type=item.get("monitor_type", "http"),
                alert_email=user.get("alert_email", user.get("email", "")),
                ssl_domain=item.get("ssl_domain", ""),
                group=item.get("group", ""),
                public=item.get("public", False),
            )
            if item.get("monitor_type") == "heartbeat":
                import secrets as _secrets
                from app.config import settings
                ping_token = _secrets.token_urlsafe(32)
                ping_url = f"{settings.APP_URL}/api/ping/{mon['id']}?token={ping_token}"
                _update_mon(db, mon["id"], {"url": ping_url, "ping_url": ping_url, "ping_token": ping_token})
            created.append({"id": mon["id"], "name": mon["name"]})
        except Exception:
            pass

    from app.models.user import update_user as _update_usr
    _update_usr(db, user["id"], {"monitors_count": current + len(created)})

    return JSONResponse({"data": {"created": created, "count": len(created)}})


# ---------------------------------------------------------------------------
# Auto-Discovery (unauthenticated preview)
# ---------------------------------------------------------------------------

@router.post("/api/discover-preview")
async def discover_preview(request: Request):
    """Unauthenticated discovery preview — rate limited, capped at 20 URLs."""
    import time
    from fastapi.responses import JSONResponse
    from app.services.discovery import discover_endpoints

    client_ip = request.client.host if request.client else "unknown"
    now_ts = time.monotonic()

    hits = _discover_rate.get(client_ip, [])
    hits = [t for t in hits if now_ts - t < _DISCOVER_WINDOW]
    if len(hits) >= _DISCOVER_LIMIT:
        retry_after = int(_DISCOVER_WINDOW - (now_ts - hits[0]))
        return JSONResponse(
            {"error": "Rate limit exceeded. Try again shortly.", "retry_after": retry_after},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now_ts)
    _discover_rate[client_ip] = hits

    global _discover_cleanup_counter
    _discover_cleanup_counter += 1
    if _discover_cleanup_counter >= 50:
        _discover_cleanup_counter = 0
        stale_cutoff = now_ts - (_DISCOVER_WINDOW * 5)
        stale_ips = [ip for ip, h in _discover_rate.items() if not h or h[-1] < stale_cutoff]
        for ip in stale_ips:
            del _discover_rate[ip]

    body = await request.json()
    domain = (body.get("domain") or "").strip()
    if not domain:
        return JSONResponse({"error": "domain is required"}, status_code=422)

    result = await discover_endpoints(domain, max_urls=20)
    return JSONResponse({"data": result})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    monitors = list_monitors_by_user(db, user["id"])

    # Get flash message from query params
    flash_message = request.query_params.get("msg")
    flash_type = request.query_params.get("msg_type", "success")

    # ---------- Group names for filter dropdown ----------
    group_names = sorted(set(m.get("group", "") for m in monitors) - {""})

    # ---------- Compute 24h uptime from hourly_uptime_bars ----------
    for m in monitors:
        hbars = m.get("hourly_uptime_bars") or []
        total = sum(b.get("total", 0) for b in hbars)
        up = sum(b.get("up", 0) for b in hbars)
        m["uptime_24h"] = round((up / total) * 100, 2) if total > 0 else None

    # ---------- Cap daily bar dates at user's local "today" ----------
    # Bars are stored with UTC date keys. When UTC is ahead of user's timezone,
    # the latest bar can show tomorrow's date. Relabel it as today.
    import pytz
    from datetime import datetime as _dt
    user_tz = pytz.timezone(user.get("timezone", "UTC"))
    local_today = _dt.now(pytz.utc).astimezone(user_tz).strftime("%Y-%m-%d")
    for m in monitors:
        bars = m.get("daily_uptime_bars") or []
        for b in bars:
            if b.get("date", "") > local_today:
                b["date"] = local_today

    # ---------- Aggregate stats for status strip ----------
    # Compute avg response time (skip heartbeat/SSL — they don't have meaningful response_ms)
    response_monitors = [m for m in monitors if m.get("monitor_type") in ("http", "json_api") and m.get("last_response_ms")]
    avg_response_ms = round(sum(m["last_response_ms"] for m in response_monitors) / len(response_monitors)) if response_monitors else None

    # Compute overall uptime % (average of all monitors' 24h uptime)
    uptime_vals = [m["uptime_24h"] for m in monitors if m.get("uptime_24h") is not None]
    overall_uptime_pct = round(sum(uptime_vals) / len(uptime_vals), 2) if uptime_vals else None

    # Count today's incidents — use user's local "today" (midnight to now)
    try:
        monitor_ids = [m["id"] for m in monitors]
        # Compute hours since midnight in user's timezone
        _now_utc = _dt.now(pytz.utc)
        _now_local = _now_utc.astimezone(user_tz)
        _local_midnight = _now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        _hours_since_midnight = (_now_local - _local_midnight).total_seconds() / 3600
        all_incidents = list_incidents_by_user(db, monitor_ids, hours=max(1, int(_hours_since_midnight) + 1), limit=50)
        # Filter to only incidents that started today in user's TZ
        _today_str = _now_local.strftime("%Y-%m-%d")
        all_incidents = [inc for inc in all_incidents
                         if inc.get("started_at") and
                         inc["started_at"].astimezone(user_tz).strftime("%Y-%m-%d") == _today_str]
        incidents_today = len(all_incidents)
        # Per-monitor incident count for dashboard cards
        from collections import defaultdict
        incidents_per_monitor = defaultdict(int)
        for inc in all_incidents:
            incidents_per_monitor[inc["monitor_id"]] += 1
        incidents_per_monitor = dict(incidents_per_monitor)
    except Exception:
        incidents_today = 0
        incidents_per_monitor = {}

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "monitors": monitors,
        "flash_message": flash_message,
        "flash_type": flash_type,
        "group_names": group_names,
        "avg_response_ms": avg_response_ms,
        "overall_uptime_pct": overall_uptime_pct,
        "incidents_today": incidents_today,
        "incidents_per_monitor": incidents_per_monitor,
    })


# ---------------------------------------------------------------------------
# Incidents Pages
# ---------------------------------------------------------------------------

@router.get("/incidents", response_class=HTMLResponse)
async def incidents_page(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    monitors = list_monitors_by_user(db, user["id"])
    monitor_ids = [m["id"] for m in monitors]

    # Query params
    hours_param = request.query_params.get("hours", "168")
    status_param = request.query_params.get("status")
    monitor_id_param = request.query_params.get("monitor_id")

    try:
        hours = int(hours_param) if hours_param and hours_param != "0" else None
    except ValueError:
        hours = 168

    status_filter = status_param if status_param in ("open", "resolved") else None

    # Build monitor lookup for type info and pre-filter label
    monitor_map = {m["id"]: m for m in monitors}

    # Pre-filter by monitor_id if provided and valid
    filter_monitor = None
    if monitor_id_param and monitor_id_param in monitor_map:
        filter_monitor = monitor_map[monitor_id_param]
        query_ids = [monitor_id_param]
    else:
        monitor_id_param = None
        query_ids = monitor_ids

    incidents = list_incidents_by_user(
        db, query_ids,
        hours=hours if hours else 30 * 24,
        limit=200,
        status=status_filter,
    ) if query_ids else []

    # Extract unique group names for filter dropdown
    group_names = sorted(set(
        m.get("group", "") for m in monitors if m.get("group")
    ))

    return templates.TemplateResponse("incidents.html", {
        "request": request,
        "user": user,
        "incidents": incidents,
        "monitor_map": monitor_map,
        "group_names": group_names,
        "hours": hours_param,
        "status_filter": status_param or "all",
        "filter_monitor_id": monitor_id_param,
        "filter_monitor_name": filter_monitor.get("name") if filter_monitor else None,
    })


@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
async def incident_detail_page(request: Request, incident_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    incident = get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Verify ownership: incident's monitor must belong to this user
    monitor = get_monitor(db, incident["monitor_id"])
    if not monitor or monitor.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Duration formatting
    if incident.get("duration_seconds"):
        incident["duration_formatted"] = _format_duration(incident["duration_seconds"])
    elif incident.get("status") == "open" and incident.get("started_at"):
        from datetime import datetime, timezone
        elapsed = (datetime.now(timezone.utc) - incident["started_at"]).total_seconds()
        incident["duration_formatted"] = _format_duration(int(elapsed)) + " (ongoing)"
    else:
        incident["duration_formatted"] = "—"

    # Root cause text
    sc = incident.get("status_code")
    if sc:
        if sc == 0:
            incident["root_cause"] = "Connection failed"
        elif sc >= 500:
            incident["root_cause"] = f"HTTP {sc} Server Error"
        elif sc >= 400:
            incident["root_cause"] = f"HTTP {sc} Client Error"
        elif sc == -1:
            incident["root_cause"] = "Timeout"
        elif sc == -2:
            incident["root_cause"] = "DNS resolution failed"
        else:
            incident["root_cause"] = f"HTTP {sc}"
    else:
        mt = monitor.get("monitor_type", "http")
        if mt == "heartbeat":
            incident["root_cause"] = "Missed heartbeat ping"
        elif mt == "ssl":
            incident["root_cause"] = "SSL certificate issue"
        else:
            incident["root_cause"] = "Check failed"

    # Count failed checks during incident window
    failed_check_count = 0
    try:
        q = db.collection("checks").where("monitor_id", "==", incident["monitor_id"]).where("is_up", "==", False)
        if incident.get("started_at"):
            q = q.where("timestamp", ">=", incident["started_at"])
        if incident.get("resolved_at"):
            q = q.where("timestamp", "<=", incident["resolved_at"])
        failed_check_count = len(q.get())
    except Exception:
        pass

    region_labels = {
        "us-east1": "US East",
        "us-west1": "US West",
        "europe-west1": "Europe",
        "asia-east1": "Asia",
    }

    return templates.TemplateResponse("incident_detail.html", {
        "request": request,
        "user": user,
        "incident": incident,
        "monitor": monitor,
        "events": get_incident_events(db, incident_id),
        "failed_check_count": failed_check_count,
        "region_labels": region_labels,
    })


# ---------------------------------------------------------------------------
# Monitor CRUD (form-based)
# ---------------------------------------------------------------------------

@router.get("/monitors/add", response_class=HTMLResponse)
async def add_monitor_page(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    monitors = list_monitors_by_user(db, user["id"])
    group_names = sorted(set(m.get("group", "") for m in monitors) - {""})

    return templates.TemplateResponse("add_monitor.html", {
        "request": request,
        "user": user,
        "group_names": group_names,
    })


@router.post("/monitors/add", response_class=HTMLResponse)
async def add_monitor(
    request: Request,
):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    form = await request.form()
    url = form.get("url", "")
    name = form.get("name", "")
    alert_email = form.get("alert_email", "")
    alert_slack_webhook = form.get("alert_slack_webhook", "")
    alert_sms_raw = form.get("alert_sms", "")
    keyword = form.get("keyword", "")
    response_threshold_ms = form.get("response_threshold_ms", "")
    webhook_url = form.get("webhook_url", "")
    check_interval_raw = form.get("check_interval", "")
    monitor_type = form.get("monitor_type", "http")
    heartbeat_interval_raw = form.get("heartbeat_interval", "")
    heartbeat_grace_period_raw = form.get("heartbeat_grace_period", "")
    expected_status_code_raw = form.get("expected_status_code", "")
    timeout_raw = form.get("timeout", "")
    auth_header = form.get("auth_header", "")
    ssl_domain = form.get("ssl_domain", "")
    ssl_expiry_threshold_days_raw = form.get("ssl_expiry_threshold_days", "")
    group = form.get("group", "")
    slug = form.get("slug", "")
    http_method = form.get("http_method", "GET").upper()
    basic_auth_user = form.get("basic_auth_user", "")
    basic_auth_pass = form.get("basic_auth_pass", "")
    auth_type = form.get("auth_type", "none")  # none | basic | bearer
    bearer_token = form.get("bearer_token", "")
    request_body = form.get("request_body", "")
    request_content_type = form.get("request_content_type", "")
    # Checkbox: sends "true" when checked, absent when unchecked.
    # Default to True for non-HTTP types (where the field isn't shown).
    if monitor_type == "http":
        follow_redirects = form.get("follow_redirects", "") == "true"
    else:
        follow_redirects = True

    # Parse custom headers (HTTP uses header_key[], JSON/API uses json_header_key[])
    custom_headers = []
    header_keys = form.getlist("header_key[]")
    header_values = form.getlist("header_value[]")
    for hk, hv in zip(header_keys, header_values):
        if hk.strip():
            custom_headers.append({"key": hk.strip(), "value": hv.strip() if hv else ""})
    json_header_keys = form.getlist("json_header_key[]")
    json_header_values = form.getlist("json_header_value[]")
    for hk, hv in zip(json_header_keys, json_header_values):
        if hk.strip():
            custom_headers.append({"key": hk.strip(), "value": hv.strip() if hv else ""})

    db = get_db()

    # Plan enforcement
    existing = list_monitors_by_user(db, user["id"])
    plan = user.get("plan", "free")
    limit = 200 if plan == "pro" else 10
    if len(existing) >= limit:
        return RedirectResponse(
            url=f"/dashboard?msg=Limited+to+{limit}+monitors.{'Contact+us+if+you+need+more.' if plan == 'pro' else '+Upgrade+to+Pro+for+up+to+200!'}&msg_type=error",
            status_code=302,
        )

    # Normalize + validate SMS (Pro only)
    alert_sms = ""
    if plan == "pro" and alert_sms_raw.strip():
        alert_sms, sms_err = _normalize_sms(alert_sms_raw)
        if sms_err:
            return RedirectResponse(
                url=f"/monitors/add?msg={sms_err.replace(' ', '+')}&msg_type=error",
                status_code=302,
            )

    # Validate URL (skip for heartbeat — auto-generated, and SSL — uses ssl_domain)
    if monitor_type not in ("heartbeat", "ssl"):
        if not url or not url.strip():
            return templates.TemplateResponse("add_monitor.html", {
                "request": request, "user": user,
                "error": "URL is required.", "form": dict(await request.form()) if False else {},
            })
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

    # Build maintenance windows list (all plans)
    maintenance_windows = []
    days = form.getlist("maintenance_day[]")
    starts = form.getlist("maintenance_start[]")
    ends = form.getlist("maintenance_end[]")
    for d, s, e in zip(days, starts, ends):
        if d and s and e:
            maintenance_windows.append({
                "day": d,
                "start_utc": s,
                "end_utc": e,
            })

    public = form.get("public") == "true"
    paused = form.get("paused") == "true"

    # Status page limit enforcement
    if public:
        public_count = sum(1 for m in existing if m.get("public", False))
        public_limit = 10
        if public_count >= public_limit:
            return RedirectResponse(
                url=f"/dashboard?msg=Limited+to+{public_limit}+public+status+pages.+Contact+us+if+you+need+more.&msg_type=error",
                status_code=302,
            )

    # Parse check interval (all plans: free 60-300s, pro 30-300s)
    check_interval = None
    if check_interval_raw:
        try:
            check_interval = int(check_interval_raw)
        except (ValueError, TypeError):
            pass

    # Parse heartbeat interval
    heartbeat_interval = None
    if heartbeat_interval_raw:
        try:
            heartbeat_interval = int(heartbeat_interval_raw)
        except (ValueError, TypeError):
            pass

    # Parse heartbeat grace period
    heartbeat_grace_period = None
    if heartbeat_grace_period_raw:
        try:
            heartbeat_grace_period = int(heartbeat_grace_period_raw)
        except (ValueError, TypeError):
            pass

    # Parse expected status code
    expected_status_code = None
    if expected_status_code_raw:
        try:
            expected_status_code = int(expected_status_code_raw)
        except (ValueError, TypeError):
            pass

    # Parse timeout
    timeout = None
    if timeout_raw:
        try:
            timeout = int(timeout_raw)
        except (ValueError, TypeError):
            pass

    # Parse SSL expiry threshold
    ssl_expiry_threshold_days = None
    if ssl_expiry_threshold_days_raw:
        try:
            ssl_expiry_threshold_days = int(ssl_expiry_threshold_days_raw)
        except (ValueError, TypeError):
            pass

    # Parse JSON assertions
    json_assertions = []
    assertion_paths = form.getlist("assertion_path[]")
    assertion_operators = form.getlist("assertion_operator[]")
    assertion_values = form.getlist("assertion_value[]")
    for p, o, v in zip(assertion_paths, assertion_operators, assertion_values):
        if p.strip():
            json_assertions.append({
                "path": p.strip(),
                "operator": o.strip() if o else "equals",
                "value": v.strip() if v else "",
            })

    # For heartbeat monitors, URL is optional (auto-generate ping URL)
    if monitor_type == "heartbeat" and not url:
        url = ""  # Will be set after creation

    # Clean up slug (lowercase, hyphens only)
    import re
    if slug:
        slug = re.sub(r"[^a-z0-9\-]", "", slug.lower().replace(" ", "-")).strip("-")

    # Auth/headers available to all plans — clear based on auth type selection only
    if auth_type == "bearer":
        basic_auth_user = ""
        basic_auth_pass = ""
    elif auth_type == "basic":
        bearer_token = ""
    else:
        basic_auth_user = ""
        basic_auth_pass = ""
        bearer_token = ""

    # Validate http_method
    allowed_methods = {"GET", "POST", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS"}
    if http_method not in allowed_methods:
        http_method = "GET"

    monitor = create_monitor(
        db,
        user_id=user["id"],
        url=url,
        name=name,
        alert_email=alert_email or user.get("email", ""),
        alert_slack_webhook=alert_slack_webhook or "",
        alert_sms=alert_sms if user.get("plan", "free") == "pro" else "",
        keyword=keyword,
        response_threshold_ms=response_threshold_ms.strip() if response_threshold_ms else None,
        webhook_url=webhook_url or "",
        maintenance_windows=maintenance_windows,
        public=public,
        paused=paused,
        check_interval=check_interval,
        monitor_type=monitor_type,
        heartbeat_interval=heartbeat_interval,
        heartbeat_grace_period=heartbeat_grace_period,
        expected_status_code=expected_status_code,
        timeout=timeout,
        json_assertions=json_assertions if json_assertions else None,
        auth_header=auth_header,
        ssl_domain=ssl_domain,
        ssl_expiry_threshold_days=ssl_expiry_threshold_days,
        group=group,
        slug=slug,
        http_method=http_method,
        basic_auth_user=basic_auth_user,
        basic_auth_pass=basic_auth_pass,
        bearer_token=bearer_token,
        request_body=request_body,
        request_content_type=request_content_type,
        custom_headers=custom_headers,
        follow_redirects=follow_redirects,
    )

    # Send SMS opt-in confirmation if SMS was enabled
    if alert_sms:
        from app.services.alerts import send_sms_opt_in_confirmation
        import asyncio
        asyncio.ensure_future(send_sms_opt_in_confirmation(alert_sms))

    # For heartbeat monitors, set the ping URL (with token) on the monitor doc
    if monitor_type == "heartbeat":
        from app.config import settings
        ping_token = monitor.get("ping_token", "")
        ping_url = f"{settings.APP_URL}/api/ping/{monitor['id']}?token={ping_token}"
        update_monitor(db, monitor["id"], {"url": ping_url, "ping_url": ping_url})
        # Redirect with ping URL so the dashboard can show the setup modal
        from urllib.parse import quote
        return RedirectResponse(
            url=f"/dashboard?msg=Monitor+'{name}'+added!&msg_type=success&heartbeat_created=1&ping_url={quote(ping_url)}&monitor_name={quote(name)}",
            status_code=302,
        )

    # For SSL monitors, store the domain as the URL for display purposes
    if monitor_type == "ssl" and ssl_domain:
        update_monitor(db, monitor["id"], {"url": f"https://{ssl_domain}" if not ssl_domain.startswith("http") else ssl_domain})

    return RedirectResponse(
        url=f"/monitors/{monitor['id']}?msg=Monitor+'{name}'+added!&msg_type=success",
        status_code=302,
    )


@router.get("/monitors/{monitor_id}/edit", response_class=HTMLResponse)
async def edit_monitor_page(request: Request, monitor_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor or monitor["user_id"] != user["id"]:
        return RedirectResponse(url="/dashboard?msg=Monitor+not+found&msg_type=error", status_code=302)

    monitors = list_monitors_by_user(db, user["id"])
    group_names = sorted(set(m.get("group", "") for m in monitors) - {""})

    return templates.TemplateResponse("edit_monitor.html", {
        "request": request,
        "user": user,
        "monitor": monitor,
        "group_names": group_names,
    })


@router.post("/monitors/{monitor_id}/edit", response_class=HTMLResponse)
async def edit_monitor_submit(
    request: Request,
    monitor_id: str,
):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    form = await request.form()
    url = form.get("url", "")
    name = form.get("name", "")
    alert_email = form.get("alert_email", "")
    alert_slack_webhook = form.get("alert_slack_webhook", "")
    alert_sms_raw = form.get("alert_sms", "")
    slug = form.get("slug", "")
    public = form.get("public", "")
    keyword = form.get("keyword", "")
    response_threshold_ms = form.get("response_threshold_ms", "")
    webhook_url = form.get("webhook_url", "")
    check_interval_raw = form.get("check_interval", "")
    expected_status_code_raw = form.get("expected_status_code", "")
    timeout_raw = form.get("timeout", "")
    auth_header = form.get("auth_header", "")
    ssl_domain = form.get("ssl_domain", "")
    ssl_expiry_threshold_days_raw = form.get("ssl_expiry_threshold_days", "")
    group = form.get("group", "")
    http_method = form.get("http_method", "GET").upper()
    basic_auth_user = form.get("basic_auth_user", "")
    basic_auth_pass = form.get("basic_auth_pass", "")
    auth_type = form.get("auth_type", "none")  # none | basic | bearer
    bearer_token = form.get("bearer_token", "")
    request_body = form.get("request_body", "")
    request_content_type = form.get("request_content_type", "")

    # Parse custom headers (HTTP uses header_key[], JSON/API uses json_header_key[])
    custom_headers = []
    header_keys = form.getlist("header_key[]")
    header_values = form.getlist("header_value[]")
    for hk, hv in zip(header_keys, header_values):
        if hk.strip():
            custom_headers.append({"key": hk.strip(), "value": hv.strip() if hv else ""})
    json_header_keys = form.getlist("json_header_key[]")
    json_header_values = form.getlist("json_header_value[]")
    for hk, hv in zip(json_header_keys, json_header_values):
        if hk.strip():
            custom_headers.append({"key": hk.strip(), "value": hv.strip() if hv else ""})

    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor or monitor["user_id"] != user["id"]:
        return RedirectResponse(url="/dashboard?msg=Monitor+not+found&msg_type=error", status_code=302)

    # Normalize + validate SMS (Pro only)
    alert_sms = ""
    if user.get("plan", "free") == "pro" and alert_sms_raw.strip():
        alert_sms, sms_err = _normalize_sms(alert_sms_raw)
        if sms_err:
            return RedirectResponse(
                url=f"/monitors/{monitor_id}/edit?msg={sms_err.replace(' ', '+')}&msg_type=error",
                status_code=302,
            )
    elif user.get("plan", "free") != "pro":
        alert_sms = monitor.get("alert_sms", "")  # preserve existing value, don't let Free user clear it via bypass

    # Validate URL (skip empty URLs — heartbeat/SSL use hidden fields)
    if url and not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    # Clean up slug (lowercase, hyphens only)
    if slug:
        slug = re.sub(r"[^a-z0-9\-]", "", slug.lower().replace(" ", "-")).strip("-")
    else:
        slug = monitor.get("slug", "")

    # Build maintenance windows list (all plans)
    maintenance_windows = []
    days = form.getlist("maintenance_day[]")
    starts = form.getlist("maintenance_start[]")
    ends = form.getlist("maintenance_end[]")
    for d, s, e in zip(days, starts, ends):
        if d and s and e:
            maintenance_windows.append({
                "day": d,
                "start_utc": s,
                "end_utc": e,
            })

    updates = {
        "url": url,
        "name": name,
        "alert_email": alert_email,
        "alert_slack_webhook": "" if form.get("clear_slack_webhook") == "1" else (alert_slack_webhook if alert_slack_webhook else monitor.get("alert_slack_webhook", "")),
        "alert_sms": alert_sms if user.get("plan", "free") == "pro" else monitor.get("alert_sms", ""),
        "slug": slug,
        "public": public == "true",
        "paused": form.get("paused") == "true",
        "keyword": keyword,
        "response_threshold_ms": response_threshold_ms.strip() if response_threshold_ms else None,
        "group": group,
    }

    # HTTP-specific fields
    if monitor.get("monitor_type") == "http":
        allowed_methods = {"GET", "POST", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS"}
        updates["http_method"] = http_method if http_method in allowed_methods else "GET"
        updates["follow_redirects"] = form.get("follow_redirects", "") == "true"
        updates["request_body"] = request_body
        updates["request_content_type"] = request_content_type

        # Auth: clear fields based on auth type selection
        # Empty values preserve existing secrets (masked in edit form)
        if auth_type == "bearer":
            updates["bearer_token"] = bearer_token if bearer_token else monitor.get("bearer_token", "")
            updates["basic_auth_user"] = ""
            updates["basic_auth_pass"] = ""
        elif auth_type == "basic":
            updates["basic_auth_user"] = basic_auth_user
            updates["basic_auth_pass"] = basic_auth_pass if basic_auth_pass else monitor.get("basic_auth_pass", "")
            updates["bearer_token"] = ""
        else:
            updates["basic_auth_user"] = ""
            updates["basic_auth_pass"] = ""
            updates["bearer_token"] = ""
        updates["custom_headers"] = custom_headers
    if expected_status_code_raw:
        try:
            updates["expected_status_code"] = int(expected_status_code_raw)
        except (ValueError, TypeError):
            pass
    else:
        updates["expected_status_code"] = None

    # Handle timeout
    if timeout_raw:
        try:
            updates["timeout"] = max(1, min(60, int(timeout_raw)))
        except (ValueError, TypeError):
            pass

    # Handle auth header (empty preserves existing — masked in edit form)
    if monitor.get("monitor_type") == "json_api":
        updates["auth_header"] = auth_header if auth_header else monitor.get("auth_header", "")

    # Handle SSL domain and threshold
    if monitor.get("monitor_type") == "ssl":
        updates["ssl_domain"] = ssl_domain
        if ssl_expiry_threshold_days_raw:
            try:
                updates["ssl_expiry_threshold_days"] = max(1, min(90, int(ssl_expiry_threshold_days_raw)))
            except (ValueError, TypeError):
                pass

    # Handle JSON assertions
    if monitor.get("monitor_type") == "json_api":
        json_assertions = []
        assertion_paths = form.getlist("assertion_path[]")
        assertion_operators = form.getlist("assertion_operator[]")
        assertion_values = form.getlist("assertion_value[]")
        for p, o, v in zip(assertion_paths, assertion_operators, assertion_values):
            if p.strip():
                json_assertions.append({
                    "path": p.strip(),
                    "operator": o.strip() if o else "equals",
                    "value": v.strip() if v else "",
                })
        updates["json_assertions"] = json_assertions

    # Handle heartbeat interval
    hb_interval_raw = form.get("heartbeat_interval", "")
    if hb_interval_raw:
        try:
            updates["heartbeat_interval"] = max(60, min(86400, int(hb_interval_raw)))
        except (ValueError, TypeError):
            pass

    # Handle heartbeat grace period
    hb_grace_raw = form.get("heartbeat_grace_period", "")
    if monitor.get("monitor_type") == "heartbeat" and hb_grace_raw:
        try:
            updates["heartbeat_grace_period"] = max(0, min(3600, int(hb_grace_raw)))
        except (ValueError, TypeError):
            pass

    # Status page limit enforcement (only if turning public ON)
    if updates["public"] and not monitor.get("public", False):
        all_monitors = list_monitors_by_user(db, user["id"])
        public_count = sum(1 for m in all_monitors if m.get("public", False))
        public_limit = 10
        if public_count >= public_limit:
            return RedirectResponse(
                url=f"/dashboard?msg=Limited+to+{public_limit}+public+status+pages.+Contact+us+if+you+need+more.&msg_type=error",
                status_code=302,
            )

    # Webhook URL and maintenance windows (all plans)
    updates["webhook_url"] = "" if form.get("clear_webhook_url") == "1" else (webhook_url if webhook_url else monitor.get("webhook_url", ""))
    updates["maintenance_windows"] = maintenance_windows

    # Custom check interval (60-300s for all plans)
    if check_interval_raw:
        try:
            min_interval = 60
            ci = max(min_interval, min(300, int(check_interval_raw)))
            updates["check_interval"] = ci
        except (ValueError, TypeError):
            pass

    update_monitor(db, monitor_id, updates)

    # Send SMS opt-in confirmation if SMS number is new or changed
    new_sms = updates.get("alert_sms", "")
    old_sms = monitor.get("alert_sms", "")
    if new_sms and new_sms != old_sms:
        from app.services.alerts import send_sms_opt_in_confirmation
        import asyncio
        asyncio.ensure_future(send_sms_opt_in_confirmation(new_sms))

    return RedirectResponse(
        url=f"/dashboard?msg=Monitor+'{name}'+updated!&msg_type=success",
        status_code=302,
    )


@router.post("/monitors/{monitor_id}/delete", response_class=HTMLResponse)
async def delete_monitor_submit(request: Request, monitor_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor or monitor["user_id"] != user["id"]:
        return RedirectResponse(url="/dashboard?msg=Monitor+not+found&msg_type=error", status_code=302)

    monitor_name = monitor["name"]
    delete_monitor(db, monitor_id)
    new_count = max(0, user.get("monitors_count", 1) - 1)
    update_user(db, user["id"], {"monitors_count": new_count})

    return RedirectResponse(
        url=f"/dashboard?msg=Monitor+'{monitor_name}'+deleted&msg_type=success",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# Clone Monitor (AJAX)
# ---------------------------------------------------------------------------

@router.post("/monitors/{monitor_id}/clone")
async def clone_monitor(request: Request, monitor_id: str):
    from fastapi.responses import JSONResponse
    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor or monitor["user_id"] != user["id"]:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Plan enforcement
    from app.models.monitor import list_monitors_by_user
    existing = list_monitors_by_user(db, user["id"])
    plan = user.get("plan", "free")
    limit = 200 if plan == "pro" else 10
    if len(existing) >= limit:
        return JSONResponse({"error": "Monitor limit reached"}, status_code=403)

    # Clone with the same settings
    cloned = create_monitor(
        db,
        user_id=user["id"],
        url=monitor.get("url", ""),
        name=monitor.get("name", "Monitor") + " (copy)",
        alert_email=monitor.get("alert_email", ""),
        alert_slack_webhook=monitor.get("alert_slack_webhook", ""),
        public=monitor.get("public", True),
        group=monitor.get("group", ""),
    )

    # Copy extra fields that create_monitor doesn't handle via args
    extra = {}
    clone_fields = [
        "keyword", "response_threshold_ms", "webhook_url", "check_interval",
        "maintenance_windows", "monitor_type", "expected_status_code", "timeout",
        "json_assertions", "auth_header", "ssl_domain", "ssl_expiry_threshold_days",
        "heartbeat_interval", "heartbeat_grace_period", "http_method",
        "basic_auth_user", "basic_auth_pass", "bearer_token",
        "request_body", "request_content_type", "custom_headers",
        "follow_redirects", "alert_sms",
    ]
    for field in clone_fields:
        val = monitor.get(field)
        if val is not None and val != "" and val != []:
            extra[field] = val
    if extra:
        update_monitor(db, cloned["id"], extra)

    from app.models.user import update_user
    update_user(db, user["id"], {"monitors_count": len(existing) + 1})

    return JSONResponse({"ok": True, "monitor_id": cloned["id"]})


# ---------------------------------------------------------------------------
# Toggle Pause (AJAX)
# ---------------------------------------------------------------------------

@router.post("/monitors/{monitor_id}/toggle-pause")
async def toggle_pause(request: Request, monitor_id: str):
    from fastapi.responses import JSONResponse
    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor or monitor["user_id"] != user["id"]:
        return JSONResponse({"error": "Not found"}, status_code=404)

    new_paused = not monitor.get("paused", False)
    update_monitor(db, monitor_id, {"paused": new_paused})
    return JSONResponse({"ok": True, "paused": new_paused})


# ---------------------------------------------------------------------------
# Bulk Actions (AJAX)
# ---------------------------------------------------------------------------

@router.post("/monitors/bulk")
async def bulk_action(request: Request):
    from fastapi.responses import JSONResponse
    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    body = await request.json()
    action = body.get("action")
    monitor_ids = body.get("monitor_ids", [])

    if action not in ("pause", "resume", "delete") or not monitor_ids:
        return JSONResponse({"error": "Invalid request"}, status_code=400)

    db = get_db()
    count = 0
    for mid in monitor_ids:
        monitor = get_monitor(db, mid)
        if not monitor or monitor["user_id"] != user["id"]:
            continue
        if action == "pause":
            update_monitor(db, mid, {"paused": True})
        elif action == "resume":
            update_monitor(db, mid, {"paused": False})
        elif action == "delete":
            delete_monitor(db, mid)
        count += 1

    if action == "delete" and count > 0:
        new_count = max(0, user.get("monitors_count", count) - count)
        update_user(db, user["id"], {"monitors_count": new_count})

    return JSONResponse({"ok": True, "affected": count})


# ---------------------------------------------------------------------------
# Monitor Detail View
# ---------------------------------------------------------------------------

@router.get("/monitors/{monitor_id}", response_class=HTMLResponse)
async def monitor_detail(request: Request, monitor_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor or monitor["user_id"] != user["id"]:
        return RedirectResponse(url="/dashboard?msg=Monitor+not+found&msg_type=error", status_code=302)

    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)

    # Get recent checks for chart (last 24h worth, max 1440 = 24*60)
    checks = get_recent_checks(db, monitor_id, limit=1440, plan=user.get("plan", "free"))

    # Get incidents (more for the detail page)
    incidents = list_incidents_by_monitor(db, monitor_id, limit=50)

    # ---------- Multi-period uptime stats from daily_uptime_bars ----------
    raw_bars = monitor.get("daily_uptime_bars") or []
    bar_map = {b["date"]: b for b in raw_bars}

    # Convert UTC "now" to user's timezone for date-based lookups
    import pytz as _pytz
    _user_tz = _pytz.timezone(user.get("timezone", "UTC"))
    now_local = now.replace(tzinfo=_pytz.utc).astimezone(_user_tz)

    def compute_period_uptime(days_back):
        total_checks = 0
        up_checks = 0
        for i in range(days_back):
            # Look up bars by UTC key (how they're stored) — check both UTC and local date
            d_utc = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            d_local = (now_local - timedelta(days=i)).strftime("%Y-%m-%d")
            b = bar_map.get(d_utc) or bar_map.get(d_local)
            if b:
                total_checks += b.get("total", 0)
                up_checks += b.get("up", 0)
        pct = round((up_checks / total_checks) * 100, 3) if total_checks > 0 else None
        # Count incidents in this period
        cutoff = now - timedelta(days=days_back)
        period_incidents = [inc for inc in incidents if inc.get("started_at") and inc["started_at"] >= cutoff]
        # Total downtime from incidents
        total_down_secs = sum(inc.get("duration_seconds", 0) or 0 for inc in period_incidents)
        if total_down_secs >= 86400:
            down_str = f"{total_down_secs // 86400}d {(total_down_secs % 86400) // 3600}h"
        elif total_down_secs >= 3600:
            down_str = f"{total_down_secs // 3600}h {(total_down_secs % 3600) // 60}m"
        elif total_down_secs >= 60:
            down_str = f"{total_down_secs // 60}m {total_down_secs % 60}s"
        elif total_down_secs > 0:
            down_str = f"{total_down_secs}s"
        else:
            down_str = None
        return {
            "pct": pct,
            "incidents": len(period_incidents),
            "downtime": down_str,
        }

    period_stats = {
        "24h": compute_period_uptime(1),
        "7d": compute_period_uptime(7),
        "30d": compute_period_uptime(30),
    }

    # ---------- Uptime bars for detail page (30d daily + 24h hourly) ----------
    today_local = now_local.date()
    daily_bars = []
    for i in range(29, -1, -1):
        d = today_local - timedelta(days=i)
        day_key = d.isoformat()
        label = d.strftime("%b %-d, '%y")
        # Try local date key first, then check if UTC key differs
        d_utc = (now.date() - timedelta(days=i))
        utc_key = d_utc.isoformat()
        b = bar_map.get(day_key) or (bar_map.get(utc_key) if utc_key != day_key else None)
        if b and b.get("total", 0) > 0:
            pct = round((b["up"] / b["total"]) * 100, 3)
            daily_bars.append({"date": label, "pct": pct})
        else:
            daily_bars.append({"date": label, "pct": None})

    raw_hbars = monitor.get("hourly_uptime_bars") or []
    hbar_map = {b["hour"]: b for b in raw_hbars}
    hourly_bars = []
    for i in range(23, -1, -1):
        h = now - timedelta(hours=i)
        hour_key = h.strftime("%Y-%m-%d-%H")
        h_local = h.replace(tzinfo=_pytz.utc).astimezone(_user_tz)
        label = h_local.strftime("%-I%p").lower() if i > 0 else "now"
        b = hbar_map.get(hour_key)
        if b and b.get("total", 0) > 0:
            pct = round((b["up"] / b["total"]) * 100, 3)
            hourly_bars.append({"date": label, "pct": pct})
        else:
            hourly_bars.append({"date": label, "pct": None})

    # ---------- Response time stats (avg / min / max) from checks ----------
    response_vals = [c.get("response_ms") for c in checks if c.get("response_ms")]
    response_stats = {
        "avg": round(sum(response_vals) / len(response_vals)) if response_vals else None,
        "min": round(min(response_vals)) if response_vals else None,
        "max": round(max(response_vals)) if response_vals else None,
    }

    # ---------- Downtime (30 days) ----------
    resolved_incidents_30d = [
        inc for inc in incidents
        if inc.get("started_at") and inc.get("status") == "resolved"
        and inc["started_at"] >= now - timedelta(days=30)
    ]
    total_down_seconds = sum(
        (inc.get("duration_seconds", 0) or 0)
        for inc in resolved_incidents_30d
    )
    # Also count ongoing incident duration
    open_incidents_30d = [
        inc for inc in incidents
        if inc.get("started_at") and inc.get("status") == "open"
        and inc["started_at"] >= now - timedelta(days=30)
    ]
    for inc in open_incidents_30d:
        started = inc["started_at"]
        if hasattr(started, 'timestamp'):
            total_down_seconds += (now - started).total_seconds()
    incident_count = len(resolved_incidents_30d) + len(open_incidents_30d)
    # Format downtime string
    if total_down_seconds < 60:
        downtime_str = f"{int(total_down_seconds)}s" if total_down_seconds > 0 else "None"
    elif total_down_seconds < 3600:
        downtime_str = f"{int(total_down_seconds / 60)}m"
    elif total_down_seconds < 86400:
        hours = total_down_seconds / 3600
        downtime_str = f"{hours:.1f}h"
    else:
        days = total_down_seconds / 86400
        downtime_str = f"{days:.1f}d"
    # Find longest outage
    all_durations = [inc.get("duration_seconds", 0) or 0 for inc in resolved_incidents_30d]
    for inc in open_incidents_30d:
        started = inc["started_at"]
        if hasattr(started, 'timestamp'):
            all_durations.append((now - started).total_seconds())
    longest_seconds = max(all_durations) if all_durations else 0
    if longest_seconds < 60:
        longest_str = f"{int(longest_seconds)}s" if longest_seconds > 0 else None
    elif longest_seconds < 3600:
        longest_str = f"{int(longest_seconds / 60)}m"
    else:
        longest_str = f"{longest_seconds / 3600:.1f}h"
    downtime_30d = {
        "value": downtime_str,
        "incidents": incident_count,
        "longest": longest_str,
    }

    # ---------- Last check "ago" text (server-rendered) ----------
    last_checked = monitor.get("last_checked")
    if last_checked:
        if hasattr(last_checked, 'timestamp'):
            lc_dt = last_checked if last_checked.tzinfo else last_checked.replace(tzinfo=timezone.utc)
        elif isinstance(last_checked, str):
            try:
                lc_dt = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
            except ValueError:
                lc_dt = None
        else:
            lc_dt = None
        if lc_dt:
            elapsed = (now - lc_dt).total_seconds()
            if elapsed < 60:
                last_check_ago = f"{int(elapsed)}s ago"
            elif elapsed < 3600:
                last_check_ago = f"{int(elapsed // 60)}m, {int(elapsed % 60)}s ago"
            else:
                last_check_ago = f"{int(elapsed // 3600)}h, {int((elapsed % 3600) // 60)}m ago"
        else:
            last_check_ago = None
    else:
        last_check_ago = None

    # Get flash message from query params
    flash_message = request.query_params.get("msg")
    flash_type = request.query_params.get("msg_type", "success")

    return templates.TemplateResponse("monitor_detail.html", {
        "request": request,
        "user": user,
        "monitor": monitor,
        "checks": checks,
        "incidents": incidents,
        "period_stats": period_stats,
        "daily_bars": daily_bars,
        "hourly_bars": hourly_bars,
        "response_stats": response_stats,
        "downtime_30d": downtime_30d,
        "last_check_ago": last_check_ago,
        "flash_message": flash_message,
        "flash_type": flash_type,
        # Region response data (from last check)
        "last_response_by_region": monitor.get("last_response_by_region", {}),
        "last_regions_checked": monitor.get("last_regions_checked", 1),
        "last_regions_up": monitor.get("last_regions_up", 0),
    })


# ---------------------------------------------------------------------------
# Monitor Detail — AJAX chart data by time range
# ---------------------------------------------------------------------------

@router.get("/api/monitors/{monitor_id}/checks")
async def monitor_checks_api(request: Request, monitor_id: str, hours: int = 24):
    """Return checks as JSON for chart time range switching."""
    from fastapi.responses import JSONResponse
    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor or monitor["user_id"] != user["id"]:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Cap to reasonable limits
    hours = min(hours, 720)  # max 30 days
    limit = min(hours * 60, 43200)

    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    docs = (
        db.collection("checks")
        .where("monitor_id", "==", monitor_id)
        .where("timestamp", ">=", cutoff)
        .order_by("timestamp", direction="DESCENDING")
        .limit(limit)
        .get()
    )
    checks = []
    for doc in docs:
        c = doc.to_dict()
        check_data = {
            "timestamp": c["timestamp"].isoformat() if hasattr(c.get("timestamp"), 'isoformat') else str(c.get("timestamp", "")),
            "response_ms": c.get("response_ms"),
            "is_up": c.get("is_up"),
            "status_code": c.get("status_code"),
        }
        if c.get("response_ms_by_region"):
            check_data["response_ms_by_region"] = c["response_ms_by_region"]
        checks.append(check_data)

    # Response stats
    vals = [c["response_ms"] for c in checks if c.get("response_ms")]
    stats = {
        "avg": round(sum(vals) / len(vals)) if vals else None,
        "min": round(min(vals)) if vals else None,
        "max": round(max(vals)) if vals else None,
    }

    return JSONResponse({"checks": checks, "stats": stats})


# ---------------------------------------------------------------------------
# Monitor Detail — lightweight poll for last_checked (live-tick reset)
# ---------------------------------------------------------------------------

@router.get("/api/monitors/{monitor_id}/status")
async def monitor_status_api(request: Request, monitor_id: str):
    """Return monitor's last_checked timestamp for live-tick polling."""
    from fastapi.responses import JSONResponse
    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor or monitor["user_id"] != user["id"]:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Use last_check_completed for display (actual check time), fall back to last_checked
    lc = monitor.get("last_check_completed") or monitor.get("last_checked")
    last_checked_iso = None
    if lc:
        if hasattr(lc, "isoformat"):
            last_checked_iso = lc.isoformat()
        else:
            last_checked_iso = str(lc)

    # Return enough data for the detail page to live-update without refresh
    response_by_region = monitor.get("last_response_by_region", {})
    return JSONResponse({
        "last_checked": last_checked_iso,
        "status": monitor.get("status", "pending"),
        "last_response_ms": monitor.get("last_response_ms"),
        "last_status_code": monitor.get("last_status_code"),
        "uptime_percent": monitor.get("uptime_percent"),
        "last_regions_checked": monitor.get("last_regions_checked"),
        "last_regions_up": monitor.get("last_regions_up"),
        "last_response_by_region": response_by_region,
    })


# ---------------------------------------------------------------------------
# Test Alert (form-based)
# ---------------------------------------------------------------------------

@router.post("/monitors/{monitor_id}/test-alert")
async def test_alert_page(request: Request, monitor_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor or monitor["user_id"] != user["id"]:
        return RedirectResponse(url="/dashboard?msg=Monitor+not+found&msg_type=error", status_code=302)

    results = await send_test_alert(monitor, user.get("plan", "free"))

    # Build a readable message
    parts = []
    if results.get("email"):
        parts.append("email")
    if results.get("slack"):
        parts.append("Slack")
    if results.get("webhook"):
        parts.append("webhook")

    if parts:
        msg = f"Test+alert+sent+via+{'+%26+'.join(parts)}!"
    else:
        msg = "No+alert+channels+configured.+Add+an+email+or+Slack+webhook+first."

    return RedirectResponse(
        url=f"/monitors/{monitor_id}?msg={msg}&msg_type=success",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# Check Now — AJAX endpoint for on-demand manual check
# ---------------------------------------------------------------------------

from fastapi.responses import JSONResponse
import time as _time

# Simple in-process rate limiter: {monitor_id: last_check_timestamp}
_check_now_last: dict[str, float] = {}
RATE_LIMIT_SECONDS = 30

@router.post("/monitors/{monitor_id}/check-now")
async def check_now(request: Request, monitor_id: str):
    """On-demand check for a single monitor. Rate limited to 1 per 30s per monitor."""
    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor or monitor["user_id"] != user["id"]:
        return JSONResponse({"error": "Monitor not found"}, status_code=404)

    if monitor.get("paused"):
        return JSONResponse({"error": "Monitor is paused. Resume it before checking."}, status_code=400)

    # Rate limit
    now_ts = _time.monotonic()
    last = _check_now_last.get(monitor_id, 0)
    wait = RATE_LIMIT_SECONDS - (now_ts - last)
    if wait > 0:
        return JSONResponse(
            {"error": f"Please wait {int(wait)+1}s before checking again.", "retry_after": int(wait)+1},
            status_code=429,
        )
    _check_now_last[monitor_id] = now_ts

    result = await check_monitor_now(monitor)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Aggregate Status Page (public — shows all public monitors for a user)
# ---------------------------------------------------------------------------

@router.get("/status/{user_id}", response_class=HTMLResponse)
async def aggregate_status_page(request: Request, user_id: str):
    db = get_db()

    # Get the user
    owner = get_user_by_id(db, user_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Status page not found")

    # Pro-only feature check
    if owner.get("plan", "free") == "free":
        raise HTTPException(status_code=404, detail="Status page not found")

    # Get all public monitors for this user
    all_monitors = list_monitors_by_user(db, user_id)
    public_monitors = [m for m in all_monitors if m.get("public", False)]

    if not public_monitors:
        raise HTTPException(status_code=404, detail="No public monitors found")

    # Get daily uptime for each monitor
    for mon in public_monitors:
        mon["daily_uptime"] = get_daily_uptime(db, mon["id"], days=90, plan=owner.get("plan", "free"))

    # Overall status
    all_up = all(m.get("status") == "up" for m in public_monitors)

    # Branding (Pro only)
    branding = {}
    if owner.get("plan", "free") == "pro":
        branding = {
            "brand_name": owner.get("status_page_brand_name", ""),
            "logo_url": owner.get("status_page_logo_url", ""),
            "accent_color": owner.get("status_page_accent_color", ""),
            "show_powered_by": not owner.get("hide_powered_by", False),
        }
    else:
        branding = {"brand_name": "", "logo_url": "", "accent_color": "", "show_powered_by": True}

    return templates.TemplateResponse("aggregate_status.html", {
        "request": request,
        "owner": owner,
        "monitors": public_monitors,
        "all_up": all_up,
        "format_duration": _format_duration,
        "branding": branding,
    })


# ---------------------------------------------------------------------------
# Public Status Page (no auth required)
# ---------------------------------------------------------------------------

@router.get("/s/{slug}", response_class=HTMLResponse)
async def public_status_page(request: Request, slug: str):
    """Public status page — anyone can view if monitor is set to public."""
    db = get_db()
    monitor = get_monitor_by_slug(db, slug)

    if not monitor:
        raise HTTPException(status_code=404, detail="Status page not found")

    if not monitor.get("public", False):
        raise HTTPException(status_code=404, detail="Status page not found")

    # Get 90-day uptime data for the bar chart
    # Branding (Pro only)
    owner = get_user_by_id(db, monitor.get("user_id", ""))
    owner_plan = owner.get("plan", "free") if owner else "free"

    daily_uptime = get_daily_uptime(db, monitor["id"], days=90, plan=owner_plan)

    # Get recent incidents
    incidents = list_incidents_by_monitor(db, monitor["id"], limit=10)
    branding = {"brand_name": "", "logo_url": "", "accent_color": "", "show_powered_by": True}
    if owner and owner.get("plan", "free") == "pro":
        branding = {
            "brand_name": owner.get("status_page_brand_name", ""),
            "logo_url": owner.get("status_page_logo_url", ""),
            "accent_color": owner.get("status_page_accent_color", ""),
            "show_powered_by": not owner.get("hide_powered_by", False),
        }

    return templates.TemplateResponse("status_page.html", {
        "request": request,
        "monitor": monitor,
        "daily_uptime": daily_uptime,
        "incidents": incidents,
        "format_duration": _format_duration,
        "branding": branding,
    })


# ---------------------------------------------------------------------------
# Settings / API Keys
# ---------------------------------------------------------------------------

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    api_keys = list_api_keys(db, user["id"])

    # Fetch Stripe subscription info for Pro users
    subscription_info = None
    if user.get("plan") == "pro" and user.get("stripe_customer_id"):
        try:
            import stripe
            from app.config import settings as app_settings
            stripe.api_key = app_settings.STRIPE_SECRET_KEY
            subs = stripe.Subscription.list(
                customer=user["stripe_customer_id"],
                status="active",
                limit=1,
            )
            if subs.data:
                sub = subs.data[0]
                subscription_info = {
                    "status": sub.status,
                    "current_period_end": sub.current_period_end,
                    "cancel_at_period_end": sub.cancel_at_period_end,
                }
        except Exception:
            pass  # Graceful fallback — page still renders

    # Check for flash
    flash_message = request.cookies.get("flash_message")
    flash_type = request.cookies.get("flash_type", "success")
    new_api_key = request.cookies.get("new_api_key")

    response = templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user,
        "api_keys": api_keys,
        "subscription_info": subscription_info,
        "flash_message": flash_message,
        "flash_type": flash_type,
        "new_api_key": new_api_key,
    })

    # Clear flash cookies
    if flash_message:
        response.delete_cookie("flash_message")
        response.delete_cookie("flash_type")
    if new_api_key:
        response.delete_cookie("new_api_key")

    return response


@router.post("/settings/timezone", response_class=HTMLResponse)
async def save_timezone(request: Request, timezone: str = Form(...)):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    import pytz
    # Validate the submitted timezone string
    try:
        pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        db = get_db()
        from app.models.api_key import list_api_keys
        api_keys = list_api_keys(db, user["id"])
        response = templates.TemplateResponse("settings.html", {
            "request": request,
            "user": user,
            "api_keys": api_keys,
            "flash_message": f"Unknown timezone: {timezone}. Please select one from the list.",
            "flash_type": "error",
        })
        return response

    db = get_db()
    update_user(db, user["id"], {"timezone": timezone})

    response = RedirectResponse(url="/settings", status_code=302)
    _set_flash(response, "Timezone saved.")
    return response


@router.post("/settings/branding", response_class=HTMLResponse)
async def save_branding(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Pro-only feature
    if user.get("plan", "free") != "pro":
        response = RedirectResponse(url="/settings", status_code=302)
        _set_flash(response, "Custom branding is a Pro feature.", "error")
        return response

    form = await request.form()
    brand_name = form.get("status_page_brand_name", "").strip()[:100]
    logo_url = form.get("status_page_logo_url", "").strip()[:500]
    accent_color = form.get("status_page_accent_color", "").strip()
    hide_powered_by = form.get("hide_powered_by") == "true"

    # Validate accent color (hex only)
    if accent_color and not re.match(r'^#[0-9a-fA-F]{6}$', accent_color):
        accent_color = ""

    # Validate logo URL (must be https or empty)
    if logo_url and not logo_url.startswith("https://"):
        response = RedirectResponse(url="/settings", status_code=302)
        _set_flash(response, "Logo URL must use HTTPS.", "error")
        return response

    db = get_db()
    update_user(db, user["id"], {
        "status_page_brand_name": brand_name,
        "status_page_logo_url": logo_url,
        "status_page_accent_color": accent_color,
        "hide_powered_by": hide_powered_by,
    })

    response = RedirectResponse(url="/settings", status_code=302)
    _set_flash(response, "Branding settings saved.")
    return response


@router.post("/settings/profile", response_class=HTMLResponse)
async def save_profile(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    form = await request.form()
    display_name = form.get("display_name", "").strip()[:100]

    db = get_db()
    update_user(db, user["id"], {"display_name": display_name})

    response = RedirectResponse(url="/settings#profile", status_code=302)
    _set_flash(response, "Profile updated.")
    return response


@router.post("/settings/password", response_class=HTMLResponse)
async def change_password(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Only email-auth users can change password
    if "email" not in user.get("auth_provider", ""):
        response = RedirectResponse(url="/settings", status_code=302)
        _set_flash(response, "Password change is only available for email accounts.", "error")
        return response

    form = await request.form()
    current_password = form.get("current_password", "")
    new_password = form.get("new_password", "")
    confirm_password = form.get("confirm_password", "")

    if not verify_password(current_password, user.get("password_hash", "")):
        response = RedirectResponse(url="/settings#password", status_code=302)
        _set_flash(response, "Current password is incorrect.", "error")
        return response

    if len(new_password) < 8:
        response = RedirectResponse(url="/settings#password", status_code=302)
        _set_flash(response, "New password must be at least 8 characters.", "error")
        return response

    if new_password != confirm_password:
        response = RedirectResponse(url="/settings#password", status_code=302)
        _set_flash(response, "New passwords do not match.", "error")
        return response

    db = get_db()
    update_user(db, user["id"], {"password_hash": hash_password(new_password)})

    response = RedirectResponse(url="/settings#password", status_code=302)
    _set_flash(response, "Password changed successfully.")
    return response


@router.post("/settings/notifications", response_class=HTMLResponse)
async def save_notifications(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    form = await request.form()
    default_alert_email = form.get("default_alert_email", "").strip()[:200]
    alert_on_recovery = form.get("alert_on_recovery") == "on"
    weekly_digest = form.get("weekly_digest") == "on"

    db = get_db()
    update_user(db, user["id"], {
        "default_alert_email": default_alert_email,
        "alert_on_recovery": alert_on_recovery,
        "weekly_digest": weekly_digest,
    })

    response = RedirectResponse(url="/settings#notifications", status_code=302)
    _set_flash(response, "Notification preferences saved.")
    return response


@router.post("/settings/delete-account", response_class=HTMLResponse)
async def delete_account(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    form = await request.form()
    confirm_email = form.get("confirm_email", "").strip().lower()

    if confirm_email != user.get("email", "").lower():
        response = RedirectResponse(url="/settings#danger", status_code=302)
        _set_flash(response, "Email confirmation did not match. Account was not deleted.", "error")
        return response

    # Cancel Stripe subscription if Pro
    if user.get("plan") == "pro" and user.get("stripe_customer_id"):
        try:
            import stripe
            from app.config import settings as app_settings
            stripe.api_key = app_settings.STRIPE_SECRET_KEY
            subs = stripe.Subscription.list(customer=user["stripe_customer_id"], status="active", limit=1)
            for sub in subs.data:
                stripe.Subscription.cancel(sub.id)
        except Exception:
            pass  # Best-effort

    db = get_db()
    delete_user(db, user["id"])

    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.post("/settings/api-keys/generate")
async def generate_api_key_page(request: Request, label: str = Form("Default")):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    key_data = generate_api_key(db, user["id"], label=label.strip() or "Default")

    response = RedirectResponse(url="/settings#api-keys", status_code=302)
    _set_flash(response, "API key created! Copy it now - you won't see it again.")
    response.set_cookie("new_api_key", key_data["raw_key"], max_age=10, httponly=True, secure=True, samesite="lax")
    return response


@router.post("/settings/api-keys/{key_id}/revoke")
async def revoke_api_key_page(request: Request, key_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    success = revoke_api_key(db, key_id, user["id"])

    response = RedirectResponse(url="/settings#api-keys", status_code=302)
    if success:
        _set_flash(response, "API key revoked.")
    else:
        _set_flash(response, "Could not revoke key.", "error")
    return response


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------

ADMIN_EMAIL = "gjbangerter@gmail.com"

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = get_user_from_cookie(request)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        raise HTTPException(status_code=404)

    db = get_db()
    from datetime import datetime, timezone, timedelta

    # --- Users ---
    all_users = [u.to_dict() | {"id": u.id} for u in db.collection("users").get()]
    total_users = len(all_users)
    pro_users = [u for u in all_users if u.get("plan") == "pro"]
    free_users = [u for u in all_users if u.get("plan") != "pro"]
    pro_count = len(pro_users)
    free_count = len(free_users)
    mrr = pro_count * 9

    # Last 20 signups sorted by created_at desc
    def _created_at(u):
        ca = u.get("created_at")
        if ca is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if hasattr(ca, "tzinfo") and ca.tzinfo is None:
            return ca.replace(tzinfo=timezone.utc)
        return ca

    recent_signups = sorted(all_users, key=_created_at, reverse=True)[:20]

    # --- Monitors ---
    all_monitors = [m.to_dict() | {"id": m.id} for m in db.collection("monitors").get()]
    total_monitors = len(all_monitors)
    monitors_up = sum(1 for m in all_monitors if m.get("status") == "up")
    monitors_down = sum(1 for m in all_monitors if m.get("status") == "down")

    # --- Checks today ---
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    checks_today_docs = (
        db.collection("checks")
        .where("timestamp", ">=", today_start)
        .get()
    )
    checks_today = len(checks_today_docs)

    # --- Cron health: get the most recent check timestamp across all monitors ---
    recent_checks = (
        db.collection("checks")
        .order_by("timestamp", direction="DESCENDING")
        .limit(1)
        .get()
    )
    last_cron_run = None
    for c in recent_checks:
        cd = c.to_dict()
        last_cron_run = cd.get("timestamp")

    # --- Per-user stats (built from monitor docs, no extra queries) ---
    user_map = {u["id"]: u for u in all_users}
    user_stats = {}
    for m in all_monitors:
        uid = m.get("user_id", "")
        if uid not in user_stats:
            user_stats[uid] = {
                "monitors": 0, "up": 0, "down": 0, "paused": 0,
                "checks_total": 0, "checks_failed": 0,
                "http": 0, "heartbeat": 0, "json_api": 0, "ssl": 0,
                "has_slack": 0, "has_sms": 0, "has_webhook": 0,
            }
        s = user_stats[uid]
        s["monitors"] += 1
        st = m.get("status", "pending")
        if m.get("paused"):
            s["paused"] += 1
        elif st == "up":
            s["up"] += 1
        elif st == "down":
            s["down"] += 1
        s["checks_total"] += m.get("checks_total", 0) or 0
        s["checks_failed"] += m.get("checks_failed", 0) or 0
        mt = m.get("monitor_type", "http")
        if mt in s:
            s[mt] += 1
        if m.get("alert_slack_webhook"):
            s["has_slack"] += 1
        if m.get("alert_sms"):
            s["has_sms"] += 1
        if m.get("webhook_url"):
            s["has_webhook"] += 1

    # Attach stats to each user, sort by monitor count desc
    user_rows = []
    for u in all_users:
        uid = u["id"]
        s = user_stats.get(uid, {})
        ct = s.get("checks_total", 0)
        cf = s.get("checks_failed", 0)
        uptime = round((1 - cf / ct) * 100, 1) if ct > 0 else None
        user_rows.append({**u, "stats": s, "uptime_pct": uptime})
    user_rows.sort(key=lambda u: u["stats"].get("monitors", 0), reverse=True)

    # --- GCP Costs (from BigQuery billing export) ---
    from app.services.admin_metrics import get_gcp_costs_from_bigquery
    gcp_bigquery_costs = get_gcp_costs_from_bigquery()

    # --- Manual Costs ---
    cost_docs = db.collection("admin_costs").order_by("created_at", direction="DESCENDING").get()
    manual_costs = [c.to_dict() | {"id": c.id} for c in cost_docs]
    monthly_manual_total = 0
    for c in manual_costs:
        amt = c.get("amount", 0) or 0
        freq = c.get("frequency", "monthly")
        if freq == "monthly":
            monthly_manual_total += amt
        elif freq == "annual":
            monthly_manual_total += amt / 12
        # one-time costs not included in monthly

    # --- Revenue Events ---
    rev_docs = db.collection("admin_revenue").order_by("timestamp", direction="DESCENDING").limit(50).get()
    revenue_events = [r.to_dict() | {"id": r.id} for r in rev_docs]

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "total_users": total_users,
        "pro_count": pro_count,
        "free_count": free_count,
        "mrr": mrr,
        "total_monitors": total_monitors,
        "monitors_up": monitors_up,
        "monitors_down": monitors_down,
        "checks_today": checks_today,
        "recent_signups": recent_signups,
        "last_cron_run": last_cron_run,
        "all_monitors": all_monitors,
        "user_rows": user_rows,
        "manual_costs": manual_costs,
        "monthly_manual_total": round(monthly_manual_total, 2),
        "revenue_events": revenue_events,
        "gcp_costs": gcp_bigquery_costs,
    })


# --- Admin Cost CRUD (AJAX) ---

def _is_admin(request: Request) -> bool:
    user = get_user_from_cookie(request)
    return user is not None and user.get("email", "").lower() == ADMIN_EMAIL


@router.post("/admin/costs")
async def admin_add_cost(request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=404)
    body = await request.json()
    from datetime import datetime, timezone
    db = get_db()
    doc_ref = db.collection("admin_costs").document()
    doc_ref.set({
        "name": body.get("name", ""),
        "category": body.get("category", "other"),
        "amount": float(body.get("amount", 0)),
        "frequency": body.get("frequency", "monthly"),
        "notes": body.get("notes", ""),
        "created_at": datetime.now(timezone.utc),
    })
    return JSONResponse({"ok": True, "id": doc_ref.id})


@router.delete("/admin/costs/{cost_id}")
async def admin_delete_cost(request: Request, cost_id: str):
    if not _is_admin(request):
        raise HTTPException(status_code=404)
    db = get_db()
    db.collection("admin_costs").document(cost_id).delete()
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# API Documentation Page
# ---------------------------------------------------------------------------

@router.get("/docs/api", response_class=HTMLResponse)
async def api_docs_page(request: Request):
    user = get_user_from_cookie(request)
    from app.config import settings as app_settings
    return templates.TemplateResponse("api_docs.html", {
        "request": request,
        "user": user,
        "app_url": app_settings.APP_URL,
    })
