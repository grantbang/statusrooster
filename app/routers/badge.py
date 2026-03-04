"""
Uptime badge endpoint — returns an SVG badge image.
Public endpoint, no auth required, only works for public monitors.
Designed to be embedded in GitHub READMEs and documentation.

Usage:
  ![Uptime](https://statusrooster.com/badge/{monitor_id}.svg)
"""

from fastapi import APIRouter, Response
from app.database import get_db
from app.models.monitor import get_monitor

router = APIRouter(tags=["badge"])

# 5-minute cache so GitHub/CDNs don't hammer us
CACHE_HEADERS = {
    "Cache-Control": "public, max-age=300, s-maxage=300",
    "Content-Type": "image/svg+xml",
}


def _make_badge_svg(label: str, value: str, color: str) -> str:
    """Generate a shields.io-style SVG badge."""
    label_width = len(label) * 6.5 + 12
    value_width = len(value) * 6.8 + 12
    total_width = label_width + value_width

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text aria-hidden="true" x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_width / 2}" y="14" fill="#fff">{label}</text>
    <text aria-hidden="true" x="{label_width + value_width / 2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{label_width + value_width / 2}" y="14" fill="#fff">{value}</text>
  </g>
</svg>"""


@router.get("/badge/{monitor_id}.svg")
async def uptime_badge(monitor_id: str):
    """Return an SVG uptime badge for a public monitor."""
    db = get_db()
    monitor = get_monitor(db, monitor_id)

    # Monitor must exist and be public
    if not monitor or not monitor.get("public"):
        svg = _make_badge_svg("uptime", "not found", "#9f9f9f")
        return Response(content=svg, media_type="image/svg+xml", headers=CACHE_HEADERS)

    uptime = monitor.get("uptime_percent", 0)
    status = monitor.get("status", "pending")

    # Color based on uptime percentage
    if status == "pending":
        color = "#9f9f9f"  # gray
        value = "pending"
    elif uptime >= 99.5:
        color = "#4c1"     # bright green
        value = f"{uptime:.2f}%"
    elif uptime >= 99.0:
        color = "#a3c51c"  # yellow-green
        value = f"{uptime:.2f}%"
    elif uptime >= 95.0:
        color = "#dfb317"  # yellow
        value = f"{uptime:.1f}%"
    else:
        color = "#e05d44"  # red
        value = f"{uptime:.1f}%"

    svg = _make_badge_svg("uptime", value, color)
    return Response(content=svg, media_type="image/svg+xml", headers=CACHE_HEADERS)


@router.get("/badge/{monitor_id}/status.svg")
async def status_badge(monitor_id: str):
    """Return an SVG status badge (up/down) for a public monitor."""
    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor or not monitor.get("public"):
        svg = _make_badge_svg("status", "not found", "#9f9f9f")
        return Response(content=svg, media_type="image/svg+xml", headers=CACHE_HEADERS)

    status = monitor.get("status", "pending")
    if status == "up":
        color = "#4c1"
        value = "up"
    elif status == "down":
        color = "#e05d44"
        value = "down"
    elif status == "warn":
        color = "#dfb317"
        value = "warn"
    else:
        color = "#9f9f9f"
        value = "pending"

    svg = _make_badge_svg("status", value, color)
    return Response(content=svg, media_type="image/svg+xml", headers=CACHE_HEADERS)


@router.get("/badge/{monitor_id}/response.svg")
async def response_time_badge(monitor_id: str):
    """Return an SVG response time badge for a public monitor."""
    db = get_db()
    monitor = get_monitor(db, monitor_id)

    if not monitor or not monitor.get("public"):
        svg = _make_badge_svg("response", "not found", "#9f9f9f")
        return Response(content=svg, media_type="image/svg+xml", headers=CACHE_HEADERS)

    ms = monitor.get("last_response_ms")
    if ms is None:
        color = "#9f9f9f"
        value = "n/a"
    elif ms < 500:
        color = "#4c1"
        value = f"{ms:.0f}ms"
    elif ms < 1500:
        color = "#a3c51c"
        value = f"{ms:.0f}ms"
    elif ms < 3000:
        color = "#dfb317"
        value = f"{ms:.0f}ms"
    else:
        color = "#e05d44"
        value = f"{ms:.0f}ms"

    svg = _make_badge_svg("response", value, color)
    return Response(content=svg, media_type="image/svg+xml", headers=CACHE_HEADERS)
