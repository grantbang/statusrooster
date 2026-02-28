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
from app.models.incident import list_incidents_by_monitor
from app.services.auth import create_access_token, decode_access_token
from app.services.alerts import _format_duration
from app.models.user import get_user_by_id
import os

router = APIRouter(tags=["pages"])

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

@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    user = get_user_from_cookie(request)
    if user:
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
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = get_user_by_email(db, email)

    if not user or not verify_password(password, user["password_hash"]):
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

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "monitors": monitors,
        "flash_message": flash_message,
        "flash_type": flash_type,
    })


# ---------------------------------------------------------------------------
# Monitor CRUD (form-based)
# ---------------------------------------------------------------------------

@router.post("/monitors/add", response_class=HTMLResponse)
async def add_monitor(
    request: Request,
    url: str = Form(...),
    name: str = Form(...),
    alert_email: str = Form(""),
    alert_slack_webhook: str = Form(""),
):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()

    # Plan enforcement
    existing = list_monitors_by_user(db, user["id"])
    if user.get("plan", "free") == "free" and len(existing) >= 5:
        return RedirectResponse(
            url="/dashboard?msg=Free+plan+limited+to+5+monitors.+Upgrade+to+Pro!&msg_type=error",
            status_code=302,
        )

    # Validate URL
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    monitor = create_monitor(
        db,
        user_id=user["id"],
        url=url,
        name=name,
        alert_email=alert_email or user.get("email", ""),
        alert_slack_webhook=alert_slack_webhook,
    )

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
    url: str = Form(...),
    name: str = Form(...),
    alert_email: str = Form(""),
    alert_slack_webhook: str = Form(""),
    slug: str = Form(""),
    public: str = Form(""),
):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

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

    update_monitor(db, monitor_id, {
        "url": url,
        "name": name,
        "alert_email": alert_email,
        "alert_slack_webhook": alert_slack_webhook,
        "slug": slug,
        "public": public == "true",
    })

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

    # Get recent checks for chart (last 24h worth, max 1440 = 24*60)
    checks = get_recent_checks(db, monitor_id, limit=1440)

    # Get incidents
    incidents = list_incidents_by_monitor(db, monitor_id, limit=10)

    return templates.TemplateResponse("monitor_detail.html", {
        "request": request,
        "user": user,
        "monitor": monitor,
        "checks": checks,
        "incidents": incidents,
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
