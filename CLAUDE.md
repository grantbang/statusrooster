# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is StatusRooster

A free-first SaaS uptime monitoring product for indie developers. Monitors websites, APIs, cron jobs (heartbeat), and SSL certificates. Built with Python/FastAPI, server-side rendered with Jinja2, backed by Google Firestore, deployed on Google Cloud Run.

**Strategy:** Attract users via a capable free tier (10 monitors, 60s checks, all alert channels, status pages). Pro ($9/mo, 200 monitors) is the natural upgrade when users outgrow the free limit. Do NOT add new free-tier gates without explicit approval.

## Development Commands

```bash
# Start dev server
source venv/bin/activate
uvicorn app.main:app --reload --port 8080

# Run E2E tests (need a valid API key)
SR_API_KEY=sr_xxx pytest tests/test_e2e.py -v --asyncio-mode=auto -k "not slow"

# Run specific test class
SR_API_KEY=sr_xxx pytest tests/test_e2e.py::TestSecurity -v --asyncio-mode=auto

# Test worker locally via Docker
docker build -t sr-worker -f worker/Dockerfile .
docker run -p 8081:8080 -e WORKER_REGION=local -e WORKER_SECRET=test123 sr-worker
```

Local dev uses production Firestore (same project). Cloud Scheduler cron and multi-region workers don't run locally — set `WORKER_SECRET=""` in `.env` to fall back to local-only checks.

## Architecture

**SSR-first:** All pages are server-rendered Jinja2. JavaScript is only for Chart.js charts, AJAX actions, and client-side filtering. Do NOT introduce React, Vue, HTMX, Alpine, Tailwind, or Bootstrap.

**Three deployable units:**
1. **Primary app** (`app/`) — FastAPI web app + API + cron handlers, deployed to Cloud Run us-east1
2. **Workers** (`worker/`) — lightweight regional check runners, deployed to us-west1, europe-west1, asia-east1
3. **Shared library** (`checker_core/`) — pure check logic (HTTP, JSON/API, SSL, heartbeat). NEVER import `app.database`, `app.models`, or `app.services` into `checker_core/` — it must stay standalone for workers.

**Multi-region flow:** Primary dispatches to workers via `POST /check-batch` (authed with `X-Worker-Secret`), aggregates results via majority vote, stores per-region data on monitor docs.

**Pre-computed dashboard data:** Monitor Firestore docs hold `daily_uptime_bars`, `hourly_uptime_bars`, `uptime_percent`, `last_response_by_region`, etc. The dashboard reads only monitor docs — zero queries to the `checks` collection. The checker (`services/checker.py`) updates these incrementally.

## Key Files

| Path | Purpose |
|------|---------|
| `app/main.py` | FastAPI entry point |
| `app/config.py` | Settings from `.env`, worker config, JWT prod check |
| `app/routers/pages.py` | All SSR page routes + AJAX endpoints (~1400 lines) |
| `app/routers/cron.py` | Cloud Scheduler endpoints (`/cron/check`, `/cron/cleanup`) |
| `app/routers/api_v1.py` | Public API v1 (API-key authed) |
| `app/services/checker.py` | Check orchestrator — dispatches multi-region, aggregates, writes Firestore |
| `app/services/alerts.py` | Email (SendGrid) + Slack + SMS (Twilio) + webhook dispatch |
| `app/static/style.css` | Unified CSS (~4500 lines) with design tokens |
| `tests/test_e2e.py` | 80+ automated E2E tests |
| `tests/conftest.py` | Fixtures: client, API keys, pro/free users |

## Coding Conventions

- **CSS class prefixes:** `d-` dashboard, `md-` monitor detail, `mf-` monitor forms, `inc-` incidents
- **Firestore updates:** Always use `merge=True` to avoid clobbering fields
- **API response shape:** `{"data": ..., "error": ..., "meta": ...}` on all v1 endpoints
- **Auth:** `get_current_user()` dependency returns user dict or redirects to login
- **Jinja2 → JS:** Use `| tojson | safe` for passing data to JavaScript
- **Worker auth:** `X-Worker-Secret` header validated against `WORKER_SECRET` env var
- **Cron auth:** `X-Cron-Secret` header only, no User-Agent fallback
- **Design tokens:** `--brand: #6366f1` (indigo), `--bg: #ffffff`, 12px card radius, 8px button radius, inline SVG icons only

## Security (Do Not Weaken)

- SSRF protection via `validate_url_not_internal()` in `checker_core` blocks all private/reserved IPs
- JWT secret raises `RuntimeError` on startup if default value used in production
- Heartbeat monitors use `ping_token` (secrets.token_urlsafe(32))
- Rate limiting on `/api/check-url` (10/60s per IP) and check-now (1/30s per monitor)

## Monitor Types

Four types, all free: HTTP (`http`), JSON/API (`json_api`), Heartbeat/Cron (`heartbeat`), SSL Certificate (`ssl`). Each has its own form section, checker branch, and template display. Heartbeat and SSL skip multi-region checks.

## Planning & Tracking

- **`IMPLEMENTATION_PLAN.md`** — v2 build plan for free-tier pivot and multi-region. Reference for all phase work.
- **`.github/copilot-instructions.md`** — detailed architecture, plan gating rules, coding conventions.
- **Build phase order:** Phase 2 → 6 → 1 → 4 → 3 → 7 (Phases 2 and 6 are complete).
- When working on implementation tasks, reference the step number (e.g., "Working on **2.4.3**") and mark checkboxes `[x]` when complete.
