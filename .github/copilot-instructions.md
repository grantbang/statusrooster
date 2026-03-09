# StatusRooster — Copilot Instructions

## What Is This Project?
StatusRooster is a **SaaS uptime monitoring product** for indie developers and small teams.
It monitors websites, APIs, and cron jobs (heartbeat monitoring), and alerts users when things break.
**Target launch: Day 12 (Mar 7, 2026).**

> **`TRACKER.md` is the single source of truth** for the project plan, completed work, and every remaining task. Read it first when starting a new chat.

## TRACKER.md Rules
- **Always work within the bounds of TRACKER.md.** Only build what's listed there. Don't add features, refactor code, or skip ahead without explicit approval.
- **Keep TRACKER.md updated as you work.** When you complete a build item or gate test, mark its checkbox `[x]` immediately. Update the Execution Order Summary table and Remaining Checkboxes counts when a phase is finished.
- **Follow the phase order.** Complete all build items and gate tests for the current phase before moving to the next one.
- **Say which step you're working on.** When starting a task, reference the TRACKER item number (e.g., "Working on **3.2**").

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
│   ├── pages.py         # All SSR page routes + AJAX endpoints (~1400 lines)
│   ├── monitors.py      # Internal monitor API (CRUD)
│   ├── api_v1.py        # Public API v1 (key-authed)
│   ├── auth.py          # Auth routes (signup, login, logout)
│   ├── oauth.py         # Google + GitHub OAuth
│   ├── billing.py       # Stripe checkout + webhooks
│   ├── cron.py          # Cloud Scheduler cron endpoint
│   ├── heartbeat.py     # Public heartbeat ping endpoint (/api/ping/{id})
│   └── badge.py         # SVG uptime badges
├── services/
│   ├── checker.py       # HTTP + heartbeat + SSL + JSON/API check engine
│   ├── alerts.py        # Email (SendGrid) + Slack + SMS (Twilio) + webhook alert dispatch
│   └── auth.py          # JWT + password hashing
├── templates/           # Jinja2 HTML templates
│   ├── base.html        # Public page base (nav + footer)
│   ├── dashboard_base.html  # App layout (sidebar + content area)
│   ├── dashboard.html       # Monitor list (card rows, status strip, bulk actions)
│   ├── monitor_detail.html  # Single monitor view (uptime slicer, chart, incidents)
│   ├── add_monitor.html     # Add monitor form (4 monitor types)
│   ├── edit_monitor.html    # Edit monitor form
│   ├── incidents.html       # Incidents list (column grid, filter/sort/search)
│   ├── incident_detail.html # Incident detail (root cause, timestamps)
│   └── ...              # landing, login, signup, pricing, settings, status pages, etc.
└── static/
    └── style.css        # Unified CSS (~4500 lines) with design tokens
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
- **CSS class prefixes**: Dashboard uses `d-` prefix, monitor detail uses `md-` prefix, monitor forms use `mf-` prefix, incidents use `inc-` prefix
- **Jinja2 filters**: Use `| tojson | safe` for passing data to JavaScript
- **Firestore**: Always use `merge=True` on updates to avoid clobbering fields
- **Error handling**: Flash messages via cookie-based system (`set_flash` / `get_flash`)
- **Auth**: `get_current_user()` dependency returns user dict or redirects to login
- **API responses**: `{"data": ..., "error": ..., "meta": ...}` shape on all API v1 endpoints

## Monitor Types
StatusRooster has **4 distinct, first-class monitor types**:

| Type | `monitor_type` | Key Fields | Status Values |
|------|----------------|------------|---------------|
| HTTP/HTTPS | `"http"` | `url`, `expected_status_code`, `timeout`, `keyword`, `response_threshold_ms` | up, down, pending |
| JSON/API | `"json_api"` | `url`, `expected_status_code`, `timeout`, `auth_header`, `json_assertions[]` | up, down, pending |
| Heartbeat/Cron | `"heartbeat"` | `ping_url`, `heartbeat_interval`, `heartbeat_grace_period` | up, down, pending |
| SSL Certificate | `"ssl"` | `ssl_domain`, `ssl_expiry_threshold_days` | up, warn, down, pending |

Each type has its own form section (create + edit), execution branch in `checker.py`, and display in templates.

## Current Priorities (What To Work On)
See `TRACKER.md` for the full plan with testing gates. The remaining work before launch:

1. **UI Redesign — Add/Edit Forms** (Phases 1–5) — CSS foundation, Add template, Edit template, backend wiring, E2E QA ← **ACTIVE WORK**
2. **UI Redesign — Dashboard** (Phases 6–9) — CSS, template + JS, backend, E2E QA
3. **10F** — Pro upsell polish (interval badge, alert footer CTA)
4. **11B** — Activity log / event timeline on incident detail
5. **11C** — Hardening (404/500 pages, meta tags, favicon, mobile audit)
6. **11D** — Admin dashboard (lightweight KPIs, signup list, cron health)
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

## Running Gate Tests (How to Authenticate)

The login cookie is set with `Secure; HttpOnly; SameSite=lax`. This means:
- **Python `requests` library fails** — it drops `Secure` cookies over plain HTTP.
- **curl works** — extract the token from the `set-cookie` header and pass it manually.

### ✅ The correct curl-based auth pattern (use this every time):

```bash
# Step 1: Login and capture the token from the set-cookie header
TOKEN=$(curl -s -X POST http://localhost:8080/login \
  -d "email=testaccount1@statusrooster.com&password=password" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -D - -o /dev/null 2>&1 | grep set-cookie | grep -o 'access_token=[^;]*')

# Step 2: Use it in all subsequent requests via -H "Cookie: $TOKEN"
curl -s -H "Cookie: $TOKEN" http://localhost:8080/dashboard
curl -s -H "Cookie: $TOKEN" http://localhost:8080/monitors/Ik6AqPcmLGzGEX0jNlGO
curl -s -H "Cookie: $TOKEN" "http://localhost:8080/incidents?monitor_id=Ik6AqPcmLGzGEX0jNlGO"
```

### ✅ Full gate test script template:

```bash
cd /Applications/statusrooster && \
TOKEN=$(curl -s -X POST http://localhost:8080/login \
  -d "email=testaccount1@statusrooster.com&password=password" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -D - -o /dev/null 2>&1 | grep set-cookie | grep -o 'access_token=[^;]*') && \
echo "Token acquired: ${TOKEN:0:30}..." && \
BODY=$(curl -s -H "Cookie: $TOKEN" http://localhost:8080/PAGE_TO_TEST) && \
echo "Contains expected-string: $(echo "$BODY" | grep -c 'expected-string')"
```

### ❌ Do NOT use:
- `requests.Session()` with `allow_redirects=True` — cookies get dropped over HTTP
- `requests.post(..., allow_redirects=False)` then follow manually — still drops `Secure` cookie
- Any Python-based HTTP client for gate tests against localhost

### Test Account
| Field | Value |
|-------|-------|
| Email | `testaccount1@statusrooster.com` |
| Password | `password` |
| Plan | Pro |
| Firestore user ID | `eydllii8PyTWHyi4BlmL` |
| Monitors | 10 (3 HTTP + 4 Heartbeat + 1 HTTP + 1 JSON/API + 1 SSL) |

Sample monitor IDs for this account:
- **HTTP**: `Ik6AqPcmLGzGEX0jNlGO` (cnn), `gS1vyoLvAJO3UB3wovYc` (google), `OektTByRd3616BTFJfZG` (autotrader)
- **Heartbeat**: `4PYKyssXU9AdINCdxci5` (test)
- **JSON/API**: `RsJhlKuTjnmWC4QpE3vy` (GitHub API Zen)
- **SSL**: `cv0aiPhqP2l4oVlhbT9m` (Google SSL Check)

Use this account for all manual and automated testing against `localhost:8080`.

## Chat Handoff Protocol
When the user says they want to switch to a new chat (e.g., "let's switch chats", "new chat", "generate handoff prompt"), generate a **copy-paste prompt** they can send to the new chat. Use this exact format:

```
We're building StatusRooster — an uptime monitoring SaaS. **Read `TRACKER.md` first** — it's the single source of truth. Also read `.github/copilot-instructions.md` for coding conventions, tech stack, test account, and project rules.

## Where We Left Off

**Phases completed:** [list completed phases with commit hashes]

**Next phase: [Phase N: Name] — [status: not started / partially done]**

[If partially done, list which items are done and which remain]

Phase [N] has [X] build items ([N.1]–[N.X]) and [Y] gate tests ([N.T1]–[N.TY]). Here's the summary:

| Item | What |
|------|------|
| **[N.1]** | [description] |
| ... | ... |

**Key context for Phase [N]:**
- [Bullet points with critical technical context the next agent needs — what files to read, what's already wired, what gotchas exist]

**Rules:**
1. Always say which TRACKER step you're working on (e.g., "Working on **[N.1]**").
2. Mark checkboxes `[x]` in `TRACKER.md` as you complete each item.
3. No shortcuts — create real test data and verify with actual requests.
4. Don't skip ahead to Phase [N+1] until all Phase [N] gate tests pass.
5. Commit when Phase [N] is fully done.

**Test account:** `testaccount1@statusrooster.com` / `password` (Pro plan, user ID `eydllii8PyTWHyi4BlmL`)

**Dev server:** Should already be running on port 8080. If not: `cd /Applications/statusrooster && source venv/bin/activate && uvicorn app.main:app --reload --port 8080`

Start by reading [files the agent should read first], then begin **[N.1]** (or resume **[N.X]** if mid-phase).
```

**Rules for generating the handoff:**
- Fill in ALL brackets with real values from the current session
- Include the last git commit hash if work was committed
- Be specific about what's done vs. what's not — don't be vague
- Include any gotchas or non-obvious context discovered during this session
- If mid-phase, say exactly which items are `[x]` done and which are `[ ]` remaining
- Keep it concise — the new chat will read TRACKER.md and copilot-instructions.md for full context
