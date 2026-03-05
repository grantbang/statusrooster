"""
Page routes — serves all HTML templates.
Separate from API routes which return JSON.
"""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.database import get_db
from app.models.user import create_user, get_user_by_email, verify_password
from app.models.monitor import list_monitors_by_user, get_monitor, get_monitor_by_slug, create_monitor, update_monitor, delete_monitor
from app.models.check import get_recent_checks, get_daily_uptime
from app.models.incident import list_incidents_by_monitor, list_incidents_by_user
from app.models.api_key import generate_api_key, list_api_keys, revoke_api_key
from app.services.auth import create_access_token, decode_access_token
from app.services.alerts import _format_duration, send_test_alert
from app.models.user import get_user_by_id
import os

router = APIRouter(tags=["pages"], include_in_schema=False)

# Templates setup
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


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

@router.post("/api/check-url")
async def public_url_check(request: Request):
    """Public endpoint: check a single URL and return enriched status."""
    import httpx, time, re, ssl, socket
    from fastapi.responses import JSONResponse
    from datetime import datetime, timezone

    body = await request.json()
    url = body.get("url", "").strip()

    if not url:
        return JSONResponse({"error": "URL is required"}, status_code=400)
    if not re.match(r'^https?://', url):
        url = f"https://{url}"

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
    token = create_access_token(user_id=user["id"], email=user["email"])

    # Set cookie and redirect to dashboard
    response = RedirectResponse(url="/dashboard", status_code=302)
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
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": error})


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

    # ---------- Incidents for the sidebar + incidents panel ----------
    monitor_ids = [m["id"] for m in monitors]
    # Get recent incidents (fetch 30d so JS can filter + sidebar can use any range)
    recent_incidents = list_incidents_by_user(db, monitor_ids, hours=30*24, limit=200) if monitor_ids else []

    # ---------- Summary stats for multiple time ranges ----------
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    active_monitors = [m for m in monitors if not m.get("paused")]

    def compute_summary(hours_back):
        cutoff = now - timedelta(hours=hours_back)
        incidents_period = [i for i in recent_incidents if i.get("started_at") and i["started_at"] >= cutoff]

        # Overall uptime: average uptime_percent of all active monitors
        if active_monitors:
            avg_uptime = sum(m.get("uptime_percent", 100) for m in active_monitors) / len(active_monitors)
        else:
            avg_uptime = 100.0

        # Average response time across all active monitors
        response_vals = [m.get("last_response_ms", 0) for m in active_monitors if m.get("last_response_ms")]
        avg_response = round(sum(response_vals) / len(response_vals)) if response_vals else 0

        # Time without incidents
        resolved = [i for i in incidents_period if i.get("status") == "resolved" and i.get("resolved_at")]
        open_incs = [i for i in incidents_period if i.get("status") == "open"]

        if open_incs:
            time_without_incident = "0m"
        elif resolved:
            last_resolved = max(resolved, key=lambda x: x["resolved_at"])
            delta = now - last_resolved["resolved_at"]
            hrs = delta.total_seconds() / 3600
            if hrs >= 24:
                time_without_incident = f"{int(hrs // 24)}d, {int(hrs % 24)}h"
            elif hrs >= 1:
                time_without_incident = f"{int(hrs)}h, {int((delta.total_seconds() % 3600) / 60)}m"
            else:
                time_without_incident = f"{int(delta.total_seconds() / 60)}m"
        else:
            time_without_incident = f"{hours_back}h+"

        # MTBF
        if len(incidents_period) > 1:
            mtbf_hours = hours_back / len(incidents_period)
            if mtbf_hours >= 24:
                mtbf = f"{mtbf_hours / 24:.1f}d"
            elif mtbf_hours >= 1:
                mtbf = f"{mtbf_hours:.1f}h"
            else:
                mtbf = f"{int(mtbf_hours * 60)}m"
        elif len(incidents_period) == 1:
            mtbf = f"{hours_back}h"
        else:
            mtbf = "∞"

        return {
            "uptime": round(avg_uptime, 3),
            "avg_response": avg_response,
            "incidents": len(incidents_period),
            "time_without_incident": time_without_incident,
            "mtbf": mtbf,
        }

    summary_stats = {
        "24h": compute_summary(24),
        "7d": compute_summary(7 * 24),
        "30d": compute_summary(30 * 24),
    }

    # ---------- Uptime bars (read pre-computed from monitor docs) ----------
    uptime_bars = {}
    uptime_bars_hourly = {}
    if monitor_ids:
        # Daily bars: read from monitor doc (updated incrementally by checker)
        today = datetime.now(timezone.utc).date()
        for m in monitors:
            mid = m["id"]
            raw_bars = m.get("daily_uptime_bars") or []
            # Build 30-day array with labels, filling gaps
            bar_map = {b["date"]: b for b in raw_bars}
            filled = []
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                day_key = d.isoformat()
                label = d.strftime("%b %-d, '%y")
                b = bar_map.get(day_key)
                if b and b.get("total", 0) > 0:
                    pct = round((b["up"] / b["total"]) * 100, 3)
                    filled.append({"date": label, "pct": pct})
                else:
                    filled.append({"date": label, "pct": None})
            uptime_bars[mid] = filled

        # Hourly bars: read from monitor doc (updated incrementally by checker)
        for m in monitors:
            mid = m["id"]
            raw_hbars = m.get("hourly_uptime_bars") or []
            hbar_map = {b["hour"]: b for b in raw_hbars}
            filled_h = []
            for i in range(23, -1, -1):
                h = now - timedelta(hours=i)
                hour_key = h.strftime("%Y-%m-%d-%H")
                label = h.strftime("%-I%p").lower() if i > 0 else "now"
                b = hbar_map.get(hour_key)
                if b and b.get("total", 0) > 0:
                    pct = round((b["up"] / b["total"]) * 100, 3)
                    filled_h.append({"date": label, "pct": pct})
                else:
                    filled_h.append({"date": label, "pct": None})
            uptime_bars_hourly[mid] = filled_h

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "monitors": monitors,
        "flash_message": flash_message,
        "flash_type": flash_type,
        "recent_incidents": recent_incidents,
        "summary_stats": summary_stats,
        "uptime_bars": uptime_bars,
        "uptime_bars_hourly": uptime_bars_hourly,
    })


# ---------------------------------------------------------------------------
# Monitor CRUD (form-based)
# ---------------------------------------------------------------------------

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

    db = get_db()

    # Plan enforcement
    existing = list_monitors_by_user(db, user["id"])
    plan = user.get("plan", "free")
    if plan == "free" and len(existing) >= 5:
        return RedirectResponse(
            url="/dashboard?msg=Free+plan+limited+to+5+monitors.+Upgrade+to+Pro+for+up+to+250!&msg_type=error",
            status_code=302,
        )
    if plan == "pro" and len(existing) >= 250:
        return RedirectResponse(
            url="/dashboard?msg=Pro+plan+limited+to+250+monitors.+Contact+us+if+you+need+more.&msg_type=error",
            status_code=302,
        )

    # Validate URL
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    # Build maintenance windows list (Pro only)
    maintenance_windows = []
    if plan != "free":
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
        public_limit = 10 if plan == "pro" else 1
        if public_count >= public_limit:
            return RedirectResponse(
                url=f"/dashboard?msg={'Pro' if plan == 'pro' else 'Free'}+plan+limited+to+{public_limit}+public+status+page{'s' if public_limit > 1 else ''}.{'Contact+us+if+you+need+more.' if plan == 'pro' else '+Upgrade+to+Pro+for+up+to+10!'}&msg_type=error",
                status_code=302,
            )

    # Parse check interval (Pro only, 60-300s)
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

    monitor = create_monitor(
        db,
        user_id=user["id"],
        url=url,
        name=name,
        alert_email=alert_email or user.get("email", ""),
        alert_slack_webhook=alert_slack_webhook if user.get("plan", "free") != "free" else "",
        keyword=keyword,
        response_threshold_ms=response_threshold_ms.strip() if response_threshold_ms else None,
        webhook_url=webhook_url if user.get("plan", "free") != "free" else "",
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
    )

    # For heartbeat monitors, set the ping URL on the monitor doc
    if monitor_type == "heartbeat":
        from app.config import settings
        ping_url = f"{settings.APP_URL}/api/ping/{monitor['id']}"
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
        url=f"/dashboard?msg=Monitor+'{name}'+added!&msg_type=success",
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

    return templates.TemplateResponse("edit_monitor.html", {
        "request": request,
        "user": user,
        "monitor": monitor,
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

    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor or monitor["user_id"] != user["id"]:
        return RedirectResponse(url="/dashboard?msg=Monitor+not+found&msg_type=error", status_code=302)

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    # Clean up slug (lowercase, hyphens only)
    import re
    if slug:
        slug = re.sub(r"[^a-z0-9\-]", "", slug.lower().replace(" ", "-")).strip("-")
    else:
        slug = monitor.get("slug", "")

    # Build maintenance windows list (Pro only)
    maintenance_windows = []
    if user.get("plan", "free") != "free":
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
        "alert_slack_webhook": alert_slack_webhook if user.get("plan", "free") != "free" else monitor.get("alert_slack_webhook", ""),
        "slug": slug,
        "public": public == "true",
        "paused": form.get("paused") == "true",
        "keyword": keyword,
        "response_threshold_ms": response_threshold_ms.strip() if response_threshold_ms else None,
        "group": group,
    }
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

    # Handle auth header
    if monitor.get("monitor_type") == "json_api":
        updates["auth_header"] = auth_header

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
        plan = user.get("plan", "free")
        public_limit = 10 if plan == "pro" else 1
        if public_count >= public_limit:
            return RedirectResponse(
                url=f"/dashboard?msg={'Pro' if plan == 'pro' else 'Free'}+plan+limited+to+{public_limit}+public+status+page{'s' if public_limit > 1 else ''}.+{'Contact+us.' if plan == 'pro' else 'Upgrade+to+Pro+for+up+to+10!'}&msg_type=error",
                status_code=302,
            )

    # Pro-only fields
    if user.get("plan", "free") != "free":
        updates["webhook_url"] = webhook_url
        updates["maintenance_windows"] = maintenance_windows
        # Custom check interval (Pro: 60-300s)
        if check_interval_raw:
            try:
                ci = max(60, min(300, int(check_interval_raw)))
                updates["check_interval"] = ci
            except (ValueError, TypeError):
                pass

    update_monitor(db, monitor_id, updates)

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
    limit = 250 if plan == "pro" else 5
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

    # Copy extra fields
    extra = {}
    for field in ["keyword", "response_threshold_ms", "webhook_url", "check_interval",
                   "maintenance_windows"]:
        if monitor.get(field):
            extra[field] = monitor[field]
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
    checks = get_recent_checks(db, monitor_id, limit=1440)

    # Get incidents (more for the detail page)
    incidents = list_incidents_by_monitor(db, monitor_id, limit=50)

    # ---------- Multi-period uptime stats from daily_uptime_bars ----------
    raw_bars = monitor.get("daily_uptime_bars") or []
    bar_map = {b["date"]: b for b in raw_bars}

    def compute_period_uptime(days_back):
        total_checks = 0
        up_checks = 0
        for i in range(days_back):
            d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            b = bar_map.get(d)
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
    today = now.date()
    daily_bars = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        day_key = d.isoformat()
        label = d.strftime("%b %-d, '%y")
        b = bar_map.get(day_key)
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
        label = h.strftime("%-I%p").lower() if i > 0 else "now"
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

    # ---------- MTBF (Mean Time Between Failures) ----------
    # Computed from incidents in the last 30 days
    resolved_incidents = [
        inc for inc in incidents
        if inc.get("started_at") and inc.get("status") == "resolved"
        and inc["started_at"] >= now - timedelta(days=30)
    ]
    if len(resolved_incidents) >= 1:
        # MTBF = (total monitored time - total downtime) / number of failures
        monitoring_hours = 30 * 24  # 30 days in hours
        total_down_hours = sum(
            (inc.get("duration_seconds", 0) or 0) / 3600
            for inc in resolved_incidents
        )
        uptime_hours = max(monitoring_hours - total_down_hours, 0)
        mtbf_hours = round(uptime_hours / len(resolved_incidents), 2)
        if mtbf_hours >= 24:
            mtbf_str = f"{mtbf_hours / 24:.1f} days"
        else:
            mtbf_str = f"{mtbf_hours:.1f} hours"
        mtbf = {"value": mtbf_str, "hours": mtbf_hours, "failures": len(resolved_incidents)}
    else:
        mtbf = None

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
        "mtbf": mtbf,
        "last_check_ago": last_check_ago,
        "flash_message": flash_message,
        "flash_type": flash_type,
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
        checks.append({
            "timestamp": c["timestamp"].isoformat() if hasattr(c.get("timestamp"), 'isoformat') else str(c.get("timestamp", "")),
            "response_ms": c.get("response_ms"),
            "is_up": c.get("is_up"),
            "status_code": c.get("status_code"),
        })

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

    lc = monitor.get("last_checked")
    last_checked_iso = None
    if lc:
        if hasattr(lc, "isoformat"):
            last_checked_iso = lc.isoformat()
        else:
            last_checked_iso = str(lc)

    return JSONResponse({
        "last_checked": last_checked_iso,
        "status": monitor.get("status", "pending"),
        "last_response_ms": monitor.get("last_response_ms"),
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
        mon["daily_uptime"] = get_daily_uptime(db, mon["id"], days=90)

    # Overall status
    all_up = all(m.get("status") == "up" for m in public_monitors)

    return templates.TemplateResponse("aggregate_status.html", {
        "request": request,
        "owner": owner,
        "monitors": public_monitors,
        "all_up": all_up,
        "format_duration": _format_duration,
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
    daily_uptime = get_daily_uptime(db, monitor["id"], days=90)

    # Get recent incidents
    incidents = list_incidents_by_monitor(db, monitor["id"], limit=10)

    return templates.TemplateResponse("status_page.html", {
        "request": request,
        "monitor": monitor,
        "daily_uptime": daily_uptime,
        "incidents": incidents,
        "format_duration": _format_duration,
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

    # Check for flash
    flash_message = request.cookies.get("flash_message")
    flash_type = request.cookies.get("flash_type", "success")
    new_api_key = request.cookies.get("new_api_key")

    response = templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user,
        "api_keys": api_keys,
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


@router.post("/settings/api-keys/generate", response_class=HTMLResponse)
async def generate_api_key_page(request: Request, label: str = Form("Default")):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    key_data = generate_api_key(db, user["id"], label=label.strip() or "Default")

    response = RedirectResponse(url="/settings", status_code=302)
    response.set_cookie("flash_message", "API key created! Copy it now -- you won't see it again.", max_age=10)
    response.set_cookie("flash_type", "success", max_age=10)
    response.set_cookie("new_api_key", key_data["raw_key"], max_age=10)
    return response


@router.post("/settings/api-keys/{key_id}/revoke", response_class=HTMLResponse)
async def revoke_api_key_page(request: Request, key_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    success = revoke_api_key(db, key_id, user["id"])

    response = RedirectResponse(url="/settings", status_code=302)
    if success:
        response.set_cookie("flash_message", "API key revoked.", max_age=10)
        response.set_cookie("flash_type", "success", max_age=10)
    else:
        response.set_cookie("flash_message", "Could not revoke key.", max_age=10)
        response.set_cookie("flash_type", "error", max_age=10)
    return response


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
