# StatusRooster — Copilot Instructions

## What Is This Project?
StatusRooster is a **free-first SaaS uptime monitoring product** for indie developers and small teams.
It monitors websites, APIs, cron jobs (heartbeat monitoring), and SSL certificates — and alerts users when things break.

**Strategy:** Maximize users and market share, not revenue. The free tier is intentionally the most generous in the industry. Pro exists to cover costs and reward supporters, not as a growth gate.

**The pitch:** "Free uptime monitoring. Better than paid. 100 monitors. 60-second checks. Multi-region. All alert channels. Status pages. $0."

> **`TRACKER.md` is the single source of truth** for the project plan, completed work, and every remaining task. Read it first when starting a new chat.
> **`IMPLEMENTATION_PLAN.md`** is the v2 build plan for the free-tier pivot and multi-region architecture. Reference it for all Phase 1–7 work.
> **`FEEDBACK.md`** (if present) contains the latest codebase review with prioritized action items.

## TRACKER.md & IMPLEMENTATION_PLAN.md Rules
- **Always work within the bounds of the active plan.** Only build what's listed. Don't add features, refactor code, or skip ahead without explicit approval.
- **Keep the plan updated as you work.** When you complete a build item or gate test, mark its checkbox `[x]` immediately.
- **Follow the phase order from IMPLEMENTATION_PLAN.md:** Phase 2 → 6 → 1 → 4 → 3 → 7.
- **Say which step you're working on.** When starting a task, reference the item number (e.g., "Working on **2.4.3**").
- **Use Opus for architecture decisions.** If you hit a design question in Phase 2 (multi-region), switch to Opus. Use Sonnet for all implementation.

## Tech Stack
| Layer | Tech |
|-------|------|
| Backend | Python 3.12 / FastAPI |
| Templating | Jinja2 SSR (server-side rendered HTML — **NOT a SPA**) |
| Database | Google Firestore (collections: `users`, `monitors`, `checks`, `incidents`) |
| Hosting | Google Cloud Run (us-east1 primary + multi-region workers) |
| Check Workers | Cloud Run services in us-west1, europe-west1, asia-east1 |
| Scheduler | Google Cloud Scheduler (60s cron → `POST /cron/check`, daily → `POST /cron/cleanup`) |
| Email | SendGrid (`alerts@statusrooster.com`) — retry + backoff + circuit breaker |
| SMS | Twilio (Pro only — real per-message cost) |
| Billing | Stripe (Free + Pro $9/mo) |
| Auth | JWT cookies + Google OAuth + GitHub OAuth |
| Charts | Chart.js 4.4.0 |
| Fonts | Inter (body) + JetBrains Mono (code) via Google Fonts |
| Shared Module | `checker_core/` — pure check logic shared between primary service and workers |

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
├── config.py            # Settings (loads .env) — includes JWT prod check + worker config
├── database.py          # Firestore client singleton
├── models/
│   ├── user.py          # User CRUD (Firestore) — includes branding fields (Phase 4)
│   ├── monitor.py       # Monitor CRUD — includes get_due_monitors() with cursor pagination
│   ├── check.py         # Check CRUD — includes per-region data fields
│   ├── incident.py      # Incident CRUD + event logging
│   └── api_key.py       # API key CRUD (hash-based, never store raw)
├── routers/
│   ├── pages.py         # All SSR page routes + AJAX endpoints (~1400 lines)
│   ├── monitors.py      # Internal monitor API (CRUD)
│   ├── api_v1.py        # Public API v1 (key-authed)
│   ├── auth.py          # Auth routes (signup, login, logout)
│   ├── oauth.py         # Google + GitHub OAuth
│   ├── billing.py       # Stripe checkout + webhooks
│   ├── cron.py          # Cloud Scheduler cron endpoints (/check and /cleanup)
│   ├── heartbeat.py     # Public heartbeat ping endpoint — requires ping_token
│   └── badge.py         # SVG uptime badges
├── services/
│   ├── checker.py       # Check orchestrator — dispatches to multi-region workers, aggregates, writes Firestore
│   ├── alerts.py        # Email (SendGrid) + Slack + SMS (Twilio) + webhook alert dispatch
│   └── auth.py          # JWT + password hashing
├── templates/           # Jinja2 HTML templates
│   ├── base.html        # Public page base (nav + footer)
│   ├── dashboard_base.html  # App layout (sidebar + content area)
│   ├── dashboard.html       # Monitor list (card rows, status strip, bulk actions)
│   ├── monitor_detail.html  # Single monitor view (uptime slicer, chart, per-region display, incidents)
│   ├── add_monitor.html     # Add monitor form (4 monitor types)
│   ├── edit_monitor.html    # Edit monitor form
│   ├── incidents.html       # Incidents list (column grid, filter/sort/search)
│   ├── incident_detail.html # Incident detail (root cause, timeline)
│   └── ...              # landing, login, signup, pricing, settings, status pages, etc.
└── static/
    └── style.css        # Unified CSS (~4500 lines) with design tokens

checker_core/             # Shared pure check logic (NO Firestore, NO alerts)
├── __init__.py          # check_url, check_url_with_retry, check_json_api,
│                        # check_ssl_certificate, grab_ssl_info,
│                        # validate_url_not_internal, assertion helpers
└── requirements.txt     # httpx, cryptography only

worker/                   # Lightweight regional check runner (Cloud Run)
├── main.py              # FastAPI: POST /check-batch, GET /health
├── Dockerfile           # python:3.12-slim, imports checker_core
├── requirements.txt     # fastapi, uvicorn, httpx, cryptography, pydantic
└── .dockerignore

scripts/
├── backfill_ping_tokens.py   # Migrate legacy heartbeat monitors
└── cleanup_old_checks.py     # Delete checks older than retention period

tests/
├── conftest.py          # Fixtures: client, API keys, pro/free users, check_and_get_result helper
└── test_e2e.py          # 80+ automated tests: auth, security, CRUD, plan enforcement, badges, errors
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
- `daily_uptime_bars` — list of {date, total, up} for last 30 days
- `hourly_uptime_bars` — list of {hour, total, up} for last 24 hours
- `uptime_percent`, `last_response_ms`, `status`, `last_checked`
- `last_response_by_region` — dict of {region: ms} from multi-region checks
- `last_regions_checked`, `last_regions_up` — multi-region summary

The checker (`services/checker.py`) updates these incrementally on every check.
The dashboard reads **only monitor docs** — zero queries to the `checks` collection.

### Multi-Region Check Architecture
```
                    ┌─────────────────────────┐
                    │    Primary (us-east1)    │
                    │  - Web app / dashboard   │
                    │  - Firestore             │
                    │  - Cron scheduler         │
                    │  - Check orchestrator    │
                    └──────────┬──────────────┘
                               │ dispatches via POST /check-batch
              ┌────────────────┼────────────────┐
              │                │                 │
     ┌────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
     │ Worker         │ │ Worker       │ │ Worker       │
     │ us-west1       │ │ europe-west1 │ │ asia-east1   │
     │ (Cloud Run)    │ │ (Cloud Run)  │ │ (Cloud Run)  │
     └────────────────┘ └──────────────┘ └──────────────┘
```

**How it works:**
1. Primary region always runs a local check (us-east1)
2. Simultaneously dispatches to remote workers via HTTP POST
3. Workers import `checker_core` and run the same check logic
4. Primary aggregates results using **majority vote** (is_up = true if majority of regions agree)
5. Response time = average across all regions
6. Per-region data stored on monitor doc and check records for UI display

**Graceful degradation:** If no workers are configured (WORKER_SECRET empty), falls back to local-only checks. If a worker times out, the remaining regions still produce a result. Heartbeat and SSL monitors skip multi-region (passive and global respectively).

### Security (P1 Hardened)
These are already implemented and tested. **Do not weaken or remove them:**
- **SSRF protection:** `validate_url_not_internal()` in `checker_core` blocks private/reserved IPs (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, 100.64.0.0/10, IPv6 loopback/ULA/link-local). Applied in `check_url()`, `check_json_api()`, and `public_url_check()`.
- **Cron auth:** `X-Cron-Secret` header only. No User-Agent fallback.
- **JWT secret:** Raises `RuntimeError` on startup if `JWT_SECRET` is the default value in production.
- **Heartbeat tokens:** Each heartbeat monitor has a `ping_token` (secrets.token_urlsafe(32)). Ping endpoint validates it. Legacy monitors without tokens accepted for backwards compatibility until backfill runs.
- **Rate limiting:** `/api/check-url` limited to 10 requests/60s per IP. `/monitors/{id}/check-now` limited to 1 per 30s per monitor.

### Plan Gating (v2 — Generous Free Tier)

**Strategy:** The free tier is our growth engine. Gate as little as possible on free. Pro is a "support us + power user" tier.

| Feature | Free | Pro $9/mo |
|---------|------|-----------|
| Monitors | **100** | **500** |
| Check interval | **60s–300s** (default 60s) | **30s–300s** (default 30s) |
| Monitor types | ALL (HTTP, JSON/API, Heartbeat, SSL) | ALL |
| Email alerts | ✅ | ✅ |
| Slack alerts | **✅** | ✅ |
| Webhook alerts | **✅** | ✅ |
| SMS alerts | ❌ | ✅ (Twilio) |
| Status pages | **10** | 10 |
| Custom branding on status pages | ❌ (shows "Powered by StatusRooster") | ✅ (custom logo, colors, hide powered-by) |
| Aggregate status page | ❌ | ✅ |
| Multi-region checks | **4 regions** (US-East, US-West, EU-West, Asia-East) | **4 regions** (same) |
| Maintenance windows | **✅** | ✅ |
| Custom headers / Basic Auth | **✅** | ✅ |
| API access | ✅ | ✅ |
| Data retention | 30 days | 90 days |
| CSV/JSON export | ✅ | ✅ |
| Uptime badges | ✅ | ✅ |

**Features that are Pro-only (gate these server-side):**
- SMS alerts (Twilio costs real money per message)
- Check interval below 60 seconds (30s is Pro minimum)
- More than 100 monitors
- Aggregate status page (`/status/{user_id}`)
- Custom branding on status pages (logo, colors, hide "Powered by")
- Data retention beyond 30 days
- More than 500 monitors (Pro cap)

**Everything else is free.** Do NOT add new plan gates without explicit approval.

## Monitor Types
StatusRooster has **4 distinct, first-class monitor types** — ALL available on Free:

| Type | `monitor_type` | Key Fields | Status Values | Multi-Region? |
|------|----------------|------------|---------------|---------------|
| HTTP/HTTPS | `"http"` | `url`, `expected_status_code`, `timeout`, `keyword`, `response_threshold_ms`, `http_method`, auth fields | up, down, pending | ✅ Yes |
| JSON/API | `"json_api"` | `url`, `expected_status_code`, `timeout`, `auth_header`, `json_assertions[]` | up, down, pending | ✅ Yes |
| Heartbeat/Cron | `"heartbeat"` | `ping_url`, `ping_token`, `heartbeat_interval`, `heartbeat_grace_period` | up, down, pending | ❌ No (passive) |
| SSL Certificate | `"ssl"` | `ssl_domain`, `ssl_expiry_threshold_days` | up, warn, down, pending | ❌ No (global) |

Each type has its own form section (create + edit), execution branch in `checker.py`, and display in templates.

## Current Build Phases

**Reference `IMPLEMENTATION_PLAN.md` for full specs with file paths, code snippets, and Copilot prompts.**

**Build order:** Phase 2 → 6 → 1 → 4 → 3 → 7

| Phase | Name | Status | Effort |
|-------|------|--------|--------|
| **2** | Multi-Region Monitoring | ✅ Complete | 15–25 hrs |
| **6** | Infrastructure Hardening | ⬜ Active | 8–12 hrs |
| **1** | Free Tier Unlocking | ⬜ | 4–6 hrs |
| **4** | Custom Branding (Pro) | ⬜ | 4–6 hrs |
| **3** | Data Retention Tiers | ⬜ | 3–4 hrs |
| **7** | Viral Loop Optimization | ⬜ | 3–4 hrs |
| **5** | Landing Page Rewrite | ⬜ Last | 4–6 hrs |

### Phase 2 Sub-Tasks (Multi-Region)
| Step | What | Status |
|------|------|--------|
| 2.1 | Extract `checker_core/` shared module | ✅ |
| 2.2 | Create worker service (`worker/main.py`) | ✅ |
| 2.3 | Multi-region config (env vars, region lists) | ✅ |
| 2.4 | Build dispatcher + aggregation in `checker.py` | ✅ |
| 2.5 | Update check model for per-region data | ✅ |
| 2.6 | Monitor detail UI — per-region display | ✅ |
| 2.7 | Deploy workers to GCP regions (4 regions, all plans) | ✅ |

## Coding Conventions
- **CSS class prefixes**: Dashboard `d-`, monitor detail `md-`, monitor forms `mf-`, incidents `inc-`
- **Jinja2 filters**: Use `| tojson | safe` for passing data to JavaScript
- **Firestore**: Always use `merge=True` on updates to avoid clobbering fields
- **Error handling**: Flash messages via cookie-based system
- **Auth**: `get_current_user()` dependency returns user dict or redirects to login
- **API responses**: `{"data": ..., "error": ..., "meta": ...}` shape on all API v1 endpoints
- **Worker auth**: `X-Worker-Secret` header, validated against `WORKER_SECRET` env var
- **Import rule for checker_core**: NEVER import Firestore, alerts, or app-specific modules into `checker_core/`. It must remain a pure, standalone module that workers can use without the full app.

- **Tests**: After completing each implementation step, run the E2E tests: `SR_API_KEY=sr_xxx pytest tests/test_e2e.py -v --asyncio-mode=auto -k "not slow"`. If your changes break existing tests, fix them before moving on. If your changes add new behavior (new endpoints, changed plan gates, new fields), update or add tests in `tests/test_e2e.py` to cover it. Tests should stay green at every step — don't accumulate failures.

## What NOT To Do
- ❌ Don't add mobile apps, enterprise SSO, team management, or on-call rotation
- ❌ Don't introduce new JS frameworks (React, Vue, HTMX, Alpine)
- ❌ Don't add external CSS frameworks (Tailwind, Bootstrap) — we have a unified style.css
- ❌ Don't add new free-tier gates without explicit approval (strategy is generous free)
- ❌ Don't import app.database, app.models, or app.services into checker_core/
- ❌ Don't weaken or remove any P1 security measures (SSRF, cron auth, JWT check, heartbeat tokens)
- ❌ Don't build analytics/telemetry before the v2 features are shipped
- ❌ Don't over-engineer — simple > clever. Ship > perfect.
- ❌ Don't refactor working code unless it's blocking a new feature

## Dev Environment
```bash
cd /Applications/statusrooster
source venv/bin/activate
uvicorn app.main:app --reload --port 8080
```
- Local Firestore uses production data (same project)
- Cloud Scheduler cron does NOT run locally — checks only happen in production
- Multi-region workers don't run locally — set `WORKER_SECRET=""` in local .env to disable and fall back to local-only checks

### Testing Worker Locally
```bash
cd /Applications/statusrooster
docker build -t sr-worker -f worker/Dockerfile .
docker run -p 8081:8080 -e WORKER_REGION=local -e WORKER_SECRET=test123 sr-worker

# Test health
curl http://localhost:8081/health

# Test a check
curl -X POST http://localhost:8081/check-batch \
  -H "Content-Type: application/json" \
  -H "X-Worker-Secret: test123" \
  -d '{"monitors": [{"id": "test1", "url": "https://httpstat.us/200", "monitor_type": "http", "timeout": 10}]}'
```

## Running Gate Tests (How to Authenticate)

The login cookie is set with `Secure; HttpOnly; SameSite=lax`. This means:
- **Python `requests` library fails** — it drops `Secure` cookies over plain HTTP.
- **curl works** — extract the token from the `set-cookie` header and pass it manually.

### ✅ The correct curl-based auth pattern:

```bash
# Step 1: Login and capture the token
TOKEN=$(curl -s -X POST http://localhost:8080/login \
  -d "email=testaccount1@statusrooster.com&password=password" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -D - -o /dev/null 2>&1 | grep set-cookie | grep -o 'access_token=[^;]*')

# Step 2: Use it
curl -s -H "Cookie: $TOKEN" http://localhost:8080/dashboard
```

### ✅ Automated E2E tests:
```bash
SR_API_KEY=sr_xxx pytest tests/test_e2e.py -v --asyncio-mode=auto
# Skip slow tests (rate limiter):
SR_API_KEY=sr_xxx pytest tests/test_e2e.py -v --asyncio-mode=auto -k "not slow"
# Security tests only:
SR_API_KEY=sr_xxx pytest tests/test_e2e.py::TestSecurity -v --asyncio-mode=auto
```

### ❌ Do NOT use:
- `requests.Session()` with `allow_redirects=True` — cookies get dropped over HTTP
- Any Python-based HTTP client for gate tests against localhost

### Test Account
| Field | Value |
|-------|-------|
| Email | `testaccount1@statusrooster.com` |
| Password | `password` |
| Plan | Pro |
| Firestore user ID | `eydllii8PyTWHyi4BlmL` |

## Cost Model (For Decision Making)

StatusRooster is **not optimizing for revenue**. The free tier is the growth engine.

| Users | Monitors | Est. monthly cost | Pro revenue (2-3% conversion) | Net |
|-------|----------|-------------------|-------------------------------|-----|
| 100 | 500 | ~$5 | ~$18–27 | Profitable |
| 1,000 | 5,000 | ~$45 | ~$180–270 | Profitable |
| 5,000 | 25,000 | ~$150 | ~$900–1,350 | Profitable |
| 10,000 | 50,000 | ~$400 | ~$1,800–2,700 | Profitable |

Cloud Run scales to zero. Firestore has a free tier. The only per-user cost that matters is Twilio (SMS), which is Pro-only. **When in doubt, give features away for free.**

## Chat Handoff Protocol
When the user says they want to switch to a new chat, generate a **copy-paste prompt** using this format:

```
We're building StatusRooster — a free-first uptime monitoring SaaS for indie devs. **Read these files first:**
1. `IMPLEMENTATION_PLAN.md` — the v2 build plan (multi-region, free tier pivot)
2. `.github/copilot-instructions.md` — coding conventions, architecture, plan gating rules
3. `TRACKER.md` — original project tracker (context only, v2 work is in IMPLEMENTATION_PLAN.md)
4. Run E2E tests after each step. Fix any failures before moving on. Update tests if behavior changed.

## Strategy
Free tier = growth weapon (100 monitors, 60s checks, Slack, webhooks, 3-region, status pages — all free).
Pro ($9/mo) = support tier (SMS, 30s checks, 5 regions, custom branding, 500 monitors).
Goal: maximize users, not revenue.

## Where We Left Off

**Current phase:** [Phase N, Step N.X]
**Completed:** [list what's done]
**Next:** [list what's next]

**Key context:**
- [Critical technical details the next agent needs]
- [Any gotchas discovered in this session]

**Rules:**
1. Say which IMPLEMENTATION_PLAN.md step you're working on (e.g., "Working on **2.4.3**").
2. Mark checkboxes `[x]` as you complete each item.
3. Do NOT import app.database or app.models into checker_core/.
4. Do NOT add new free-tier gates.
5. Do NOT weaken P1 security measures.
6. Commit after each phase with clear messages (e.g., "2.4.3: Implement result aggregation in checker.py").


**Dev server:** `cd /Applications/statusrooster && source venv/bin/activate && uvicorn app.main:app --reload --port 8080`

Start by reading IMPLEMENTATION_PLAN.md Phase [N], then begin step [N.X].
```

**Rules for generating the handoff:**
- Fill in ALL brackets with real values from the current session
- Include the last git commit hash if work was committed
- Be specific about what's done vs. what's not
- Include any gotchas or non-obvious context discovered during this session
- Keep it concise — the new chat will read the plan files for full context
