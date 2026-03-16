from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from app.routers import auth, monitors, cron, pages, billing, api_v1, badge, oauth, heartbeat
from datetime import datetime
import json
import logging
import os

# Configure root logger so app.services.checker logs are visible
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

app = FastAPI(
    title="StatusRooster",
    version="1.0.0",
    description="Uptime monitoring API for developers. Monitor endpoints, get alerts, embed status badges.",
    docs_url="/docs",
    redoc_url=None,  # We mount our own below with a working CDN URL
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "monitors", "description": "CRUD operations for monitors (requires API key)"},
        {"name": "badge", "description": "Public SVG badge endpoints for embedding in READMEs"},
    ],
)


# Custom ReDoc page — FastAPI's default uses a stale @next CDN tag that 404s
from fastapi.responses import HTMLResponse

@app.get("/redoc", include_in_schema=False)
async def custom_redoc():
    return HTMLResponse("""<!DOCTYPE html>
<html><head>
<title>StatusRooster - API Reference</title>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
<style>body { margin: 0; padding: 0; }</style>
</head><body>
<redoc spec-url="/openapi.json"></redoc>
<script src="https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js"></script>
</body></html>""")

# Routers — pages first so / doesn't conflict
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(monitors.router)
app.include_router(billing.router)
app.include_router(api_v1.router)
app.include_router(badge.router)
app.include_router(oauth.router)
app.include_router(cron.router)
app.include_router(heartbeat.router)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


# Custom JSON serializer for Firestore timestamps
class FirestoreEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, '_seconds'):  # Firestore DatetimeWithNanoseconds
            return datetime.fromtimestamp(obj._seconds).isoformat()
        return super().default(obj)


def tojson_filter(value):
    return json.dumps(value, cls=FirestoreEncoder)


def as_tz_filter(dt, tz_name: str = "UTC", fmt: str = "%b %-d, %Y %H:%M"):
    """Convert a UTC datetime to the given IANA timezone and format it."""
    if dt is None:
        return ""
    try:
        import pytz
        from datetime import datetime as _dt
        # Handle Firestore DatetimeWithNanoseconds
        if hasattr(dt, '_seconds'):
            dt = _dt.fromtimestamp(dt._seconds, tz=pytz.utc)
        elif isinstance(dt, _dt) and dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.utc)
        tz = pytz.timezone(tz_name or "UTC")
        return dt.astimezone(tz).strftime(fmt)
    except Exception:
        # Fall back to UTC if tz is invalid or dt is malformed
        try:
            return dt.strftime(fmt)
        except Exception:
            return str(dt)


templates.env.filters["tojson"] = tojson_filter
templates.env.filters["as_tz"] = as_tz_filter

# Also register filter in the pages router templates
from app.routers.pages import templates as page_templates
page_templates.env.filters["tojson"] = tojson_filter
page_templates.env.filters["as_tz"] = as_tz_filter


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # HSTS — Cloud Run terminates TLS but this protects direct access
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "healthy", "service": "statusrooster"}


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /admin\n"
        "Disallow: /settings\n"
        "Disallow: /dashboard\n"
        "Disallow: /monitors/\n"
        "Disallow: /incidents\n"
        "Disallow: /cron/\n"
        "\n"
        "Sitemap: https://statusrooster.com/sitemap.xml\n"
    )


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    from fastapi.responses import Response
    urls = [
        ("https://statusrooster.com/", "weekly", "1.0"),
        ("https://statusrooster.com/pricing", "monthly", "0.8"),
        ("https://statusrooster.com/docs/api", "monthly", "0.7"),
        ("https://statusrooster.com/signup", "monthly", "0.6"),
        ("https://statusrooster.com/login", "monthly", "0.5"),
        ("https://statusrooster.com/privacy", "yearly", "0.3"),
        ("https://statusrooster.com/terms", "yearly", "0.3"),
    ]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for loc, freq, priority in urls:
        xml += f"  <url><loc>{loc}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>\n"
    xml += "</urlset>\n"
    return Response(content=xml, media_type="application/xml")


# ---------------------------------------------------------------------------
# Custom error pages
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic validation errors — wrap in our standard API shape for /api/ routes."""
    from fastapi.responses import JSONResponse
    if request.url.path.startswith("/api/"):
        errors = exc.errors()
        msg = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in errors if e.get("loc"))
        return JSONResponse({"data": None, "error": msg or "Validation error", "meta": None}, status_code=422)
    # Non-API routes: return FastAPI's default behavior
    return JSONResponse({"detail": exc.errors()}, status_code=422)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    from fastapi.responses import JSONResponse
    # API routes: return {"data": null, "error": "..."} shape directly (not wrapped in "detail")
    if request.url.path.startswith("/api/"):
        if isinstance(exc.detail, dict):
            return JSONResponse(exc.detail, status_code=exc.status_code)
        return JSONResponse({"data": None, "error": str(exc.detail)}, status_code=exc.status_code)
    # HTML routes: custom error pages
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request, "user": None}, status_code=404)
    # For other HTML errors, return FastAPI's default JSON (these are rare — most HTML
    # errors are redirects, not HTTPExceptions)
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Internal server error"}, status_code=500)
    return templates.TemplateResponse("500.html", {"request": request, "user": None}, status_code=500)
