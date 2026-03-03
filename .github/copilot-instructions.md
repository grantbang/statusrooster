# StatusRooster — Copilot Instructions

## What Is This Project?
StatusRooster is a **SaaS uptime monitoring product** for indie developers and small teams.
It monitors websites, APIs, and cron jobs (heartbeat monitoring), and alerts users when things break.
**Target launch: Day 12 (Mar 7, 2026).**

## Tech Stack
| Layer | Tech |
|-------|------|
| Backend | Python 3.12 / FastAPI |
| Templating | Jinja2 SSR (server-side rendered HTML — **NOT a SPA**) |
| Database | Google Firestore (collections: `users`, `monitors`, `checks`, `incidents`) |
| Hosting | Google Cloud Run (us-east1) |
| Scheduler | Google Cloud Scheduler (60s cron → `POST /cron/check`) |
| Email | SendGrid (`alerts@statusrooster.com`) — retry + backoff + circuit breaker |
| SMS | Twilio (Pro only) |
| Billing | Stripe (Free + Pro $9/mo) |
| Auth | JWT cookies + Google OAuth + GitHub OAuth |
| Charts | Chart.js 4.4.0 |
| Fonts | Inter (body) + JetBrains Mono (code) via Google Fonts |

## Design System
- **White theme**: `--bg: #ffffff`, `--surface: #fff`, `--text: #111827`, `--muted: #6b7280`
- **Brand color**: `--brand: #6366f1` (indigo)
- **Success**: `--success: #22c55e` / **Danger**: `--danger: #ef4444` / **Warning**: `--warning: #f59e0b`
- **Border radius**: 12px cards, 8px buttons/inputs
- **Shadows**: minimal — prefer `border: 1px solid var(--border)`
- **Icons**: inline SVG only (no icon library)
- **Mobile**: responsive with hamburger nav; sidebar collapses on <768px

## Project Structure
```
app/
├── main.py              # FastAPI app entry point
├── config.py            # Settings (loads .env)
├── database.py          # Firestore client singleton
├── models/
│   ├── user.py          # User CRUD (Firestore)
│   ├── monitor.py       # Monitor CRUD (Firestore)
│   ├── check.py         # Check CRUD (Firestore)
│   ├── incident.py      # Incident CRUD (Firestore)
│   └── api_key.py       # API key CRUD
├── routers/
│   ├── pages.py         # All SSR page routes + AJAX endpoints (~1200 lines)
│   ├── monitors.py      # Internal monitor API (CRUD)
│   ├── api_v1.py        # Public API v1 (key-authed)
│   ├── auth.py          # Auth routes (signup, login, logout)
│   ├── oauth.py         # Google + GitHub OAuth
│   ├── billing.py       # Stripe checkout + webhooks
│   ├── cron.py          # Cloud Scheduler cron endpoint
│   ├── heartbeat.py     # Public heartbeat ping endpoint (/api/ping/{id})
│   └── badge.py         # SVG uptime badges
├── services/
│   ├── checker.py       # HTTP + heartbeat check engine (retry, SSL, keyword, threshold)
│   ├── alerts.py        # Email (SendGrid) + Slack + SMS (Twilio) + webhook alert dispatch
│   └── auth.py          # JWT + password hashing
├── templates/           # Jinja2 HTML templates
│   ├── base.html        # Public page base (nav + footer)
│   ├── dashboard_base.html  # App layout (sidebar + content area)
│   ├── dashboard.html   # Monitor list (card rows, status strip, bulk actions)
│   ├── monitor_detail.html  # Single monitor view (uptime slicer, chart, incidents)
│   ├── edit_monitor.html    # Edit monitor form
│   └── ...              # landing, login, signup, pricing, settings, status pages, etc.
└── static/
    └── style.css        # Unified CSS (~4000 lines) with design tokens
```

## Key Architecture Patterns

### SSR-First
All pages are **server-side rendered** with Jinja2. JavaScript is used sparingly for:
- Chart.js response time charts
- AJAX actions (pause/resume, delete, clone, polling)
- Client-side filter/search/sort on dashboard
- Tab/slicer switching (uptime periods, chart ranges)

**Do NOT** introduce React, Vue, HTMX, or any client-side framework.

### Pre-Computed Data on Monitor Docs
Dashboard performance depends on storing computed data directly on monitor Firestore documents:
- `daily_uptime_bars` — list of {date, pct} for last 30 days
- `hourly_uptime_bars` — list of {hour, pct} for last 24 hours
- `uptime_pct`, `avg_response_ms`, `status`, `last_checked`, `response_ms`

The checker (`services/checker.py`) updates these incrementally on every check.
The dashboard reads **only monitor docs** — zero queries to the `checks` collection.

### Plan Gating
| | Free | Pro $9/mo |
|---|---|---|
| Monitors | 5 | 250 |
| Check interval | 300s (5 min) | 60–300s (custom) |
| Alerts | Email only | Email + Slack + SMS + Webhooks |
| Status pages | 1 | 10 |
| Features | — | Maintenance windows, Basic Auth, CSV export |

Gate features **server-side** (never trust the client). Show upgrade CTAs for Free users.

## Coding Conventions
- **CSS class prefixes**: Dashboard uses `d-` prefix, monitor detail uses `md-` prefix
- **Jinja2 filters**: Use `| tojson | safe` for passing data to JavaScript
- **Firestore**: Always use `merge=True` on updates to avoid clobbering fields
- **Error handling**: Flash messages via cookie-based system (`set_flash` / `get_flash`)
- **Auth**: `get_current_user()` dependency returns user dict or redirects to login
- **API responses**: `{"data": ..., "error": ..., "meta": ...}` shape on all API v1 endpoints

## Current Priorities (What To Work On)
See `TRACKER.md` for the full plan. The remaining work before launch:

1. **Day 10E** — Add/Edit form: timeout, basic auth, HTTP method fields
2. **Day 10F** — Pro upsell polish (interval badge, alert footer CTA)
3. **Day 11A** — **Incidents pages** (`/incidents` list + `/incidents/{id}` detail) ← HIGHEST PRIORITY
4. **Day 11B** — Activity log / event timeline on incident detail
5. **Day 11C** — Hardening (404/500 pages, meta tags, favicon, mobile audit)
6. **Day 11D** — Admin dashboard (lightweight KPIs, signup list, cron health)
7. **Day 12** — Testing & launch

## What NOT To Do
- ❌ Don't add mobile apps, enterprise SSO, team management, or on-call rotation
- ❌ Don't introduce new JS frameworks (React, Vue, HTMX, Alpine)
- ❌ Don't build analytics/telemetry before launch
- ❌ Don't over-engineer — simple > clever. Ship > perfect.
- ❌ Don't add features not in TRACKER.md without explicit approval
- ❌ Don't refactor working code unless it's blocking a new feature
- ❌ Don't add external CSS frameworks (Tailwind, Bootstrap) — we have a unified style.css

## Dev Environment
```bash
cd /Applications/statusrooster
source venv/bin/activate
uvicorn app.main:app --reload --port 8080
```
- Local Firestore uses production data (same project)
- Cloud Scheduler cron does NOT run locally — checks only happen in production
- Test user: `testaccount1@statusrooster.com` (plan: pro)
