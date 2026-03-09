# StatusRooster — Master Project Tracker

**Start:** Feb 25, 2026 · **Target Launch:** Mar 7, 2026
**Current Day: 11 (in progress)** · **Phase 3: Hardening & Launch**

> **This is the single source of truth.** It contains the project DNA (vision, architecture, design system, features), all completed work, and every remaining task with testing gates. Start here when opening a new Copilot chat.

---

# 🧬 Project DNA

## Mission & Positioning

**One-liner:** StatusRooster monitors your websites, APIs, and cron jobs — and alerts you instantly when something breaks. Built for indie developers and small SaaS teams.

**Who we serve:** Solo developers, indie hackers, SaaS founders, freelancers, and small teams (1-5 people). NOT enterprises. NOT DevOps teams with Datadog budgets.

**Revenue target:** $5k-$30k/mo within 12-18 months. ~400 Pro customers at $9-$19/mo.

**Why we win:**
1. **Positioning** — "Monitoring for indie SaaS" resonates emotionally. UptimeRobot is generic. Datadog is enterprise. Better Stack is VC-funded. We're for *them*.
2. **Simplicity** — Sign up → add URL → done. No 15-tab settings page. No team hierarchy. No enterprise SSO.
3. **Fair pricing** — Free tier that actually works (5 monitors, email alerts, status pages, API access, badges). Pro at $9/mo — not $29/mo for webhooks like UptimeRobot.
4. **Four monitoring types** — Website uptime + JSON/API validation + cron/heartbeat + SSL certificate monitoring, bundled at indie prices.
5. **Status pages as distribution** — Every public status page says "Powered by StatusRooster." Viral growth loop.
6. **Modern stack** — GCP Cloud Run, Firestore, serverless. No legacy infra.

**What we are NOT building:**
- ❌ Mobile apps
- ❌ Enterprise SSO / SAML
- ❌ Team management / role-based access (until $10k+ MRR)
- ❌ On-call rotation / PagerDuty clone
- ❌ Full observability suite (logs, traces, metrics)
- ❌ New JS frameworks (React, Vue, HTMX, Alpine) — vanilla JS only
- ❌ External CSS frameworks (Tailwind, Bootstrap) — unified `style.css`
- ❌ Features not in this tracker without explicit approval
- ❌ Refactoring working code unless it blocks a new feature

---

## Pricing

| | Free | Pro $9/mo |
|---|---|---|
| Monitors | 5 | 250 |
| Check interval | 5 min | 60–300s (custom) |
| Alerts | Email | Email + Slack + SMS (Twilio) + Webhooks |
| Status pages | 1 | 10 |
| API access | ✅ | ✅ |
| Maintenance windows | — | ✅ |
| Basic Auth on checks | — | ✅ |
| Uptime badges | ✅ | ✅ |
| CSV export | — | ✅ |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
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
| Domain | `statusrooster.com` (Namecheap) |

---

## Design System

- **White theme**: `--bg: #ffffff`, `--surface: #fff`, `--text: #111827`, `--muted: #6b7280`
- **Brand color**: `--brand: #6366f1` (indigo)
- **Success**: `--success: #22c55e` / **Danger**: `--danger: #ef4444` / **Warning**: `--warning: #f59e0b`
- **Border radius**: 12px cards, 8px buttons/inputs
- **Shadows**: minimal — prefer `border: 1px solid var(--border)`
- **Icons**: inline SVG only (no icon library)
- **Mobile**: responsive with hamburger nav; sidebar collapses on <768px
- **CSS class prefixes**: `.mf-*` for monitor forms, `.d-*` for dashboard columns, `.md-*` for monitor detail, `.inc-*` for incidents

---

## Monitor Types

| Type | `monitor_type` | Key Fields | Status Values |
|------|----------------|------------|---------------|
| HTTP/HTTPS | `"http"` | `url`, `expected_status_code`, `timeout`, `keyword`, `response_threshold_ms` | up, down, pending |
| JSON/API | `"json_api"` | `url`, `expected_status_code`, `timeout`, `auth_header`, `json_assertions[]` | up, down, pending |
| Heartbeat/Cron | `"heartbeat"` | `ping_url`, `heartbeat_interval`, `heartbeat_grace_period` | up, down, pending |
| SSL Certificate | `"ssl"` | `ssl_domain`, `ssl_expiry_threshold_days` | up, warn, down, pending |

---

## Architecture Patterns

### SSR-First
All pages are server-side rendered with Jinja2. JavaScript is used sparingly for: Chart.js charts, AJAX actions (pause/resume, delete, clone, polling), client-side filter/search/sort, tab/slicer switching.

### Pre-Computed Data on Monitor Docs
Dashboard performance depends on storing computed data directly on monitor Firestore documents:
- `daily_uptime_bars` — list of {date, pct} for last 30 days
- `hourly_uptime_bars` — list of {hour, pct} for last 24 hours
- `uptime_pct`, `avg_response_ms`, `status`, `last_checked`, `response_ms`

The checker (`services/checker.py`) updates these incrementally on every check.
The dashboard reads **only monitor docs** — zero queries to the `checks` collection.

### Plan Gating
Gate features **server-side** (never trust the client). Show upgrade CTAs for Free users.

### Firestore Conventions
Always use `merge=True` on updates to avoid clobbering fields.

### API Response Shape
`{"data": ..., "error": ..., "meta": ...}` on all API v1 endpoints.

### Error Handling
Flash messages via cookie-based system (`set_flash` / `get_flash`).

### Auth
`get_current_user()` dependency returns user dict or redirects to login.

---

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
│   ├── alerts.py        # Email + Slack + SMS + webhook alert dispatch
│   └── auth.py          # JWT + password hashing
├── templates/           # Jinja2 HTML templates
│   ├── base.html        # Public page base (nav + footer)
│   ├── dashboard_base.html  # App layout (sidebar + content area)
│   ├── dashboard.html       # Monitor list
│   ├── monitor_detail.html  # Single monitor view
│   ├── add_monitor.html     # Add monitor form
│   ├── edit_monitor.html    # Edit monitor form
│   ├── incidents.html       # Incidents list
│   ├── incident_detail.html # Incident detail
│   └── ...                  # landing, login, signup, pricing, settings, status pages, etc.
└── static/
    └── style.css        # Unified CSS (~4500 lines) with design tokens
```

---

## What's Live Right Now

- ✅ Full monitoring engine: HTTP checks, SSL, keyword, response threshold, heartbeat/cron, JSON/API assertions, SSL certificate monitoring
- ✅ 4 distinct monitor types: HTTP/HTTPS, JSON/API, Heartbeat/Cron, SSL Certificate
- ✅ Alerts: email (SendGrid w/ retry + circuit breaker), Slack webhooks, webhook notifications, SMS (Twilio)
- ✅ Public status pages + aggregate status page
- ✅ Stripe billing (Free / Pro $9/mo)
- ✅ Public API with key auth (6 endpoints, consistent JSON)
- ✅ Uptime badges (3 SVG types, shields.io-style)
- ✅ API docs with tabbed examples (curl/Python/JS), copy buttons
- ✅ Interactive Swagger playground + OpenAPI spec
- ✅ Card-based dashboard with sidebar nav, status strip, uptime bars, inline stats
- ✅ Search, filter, sort, bulk actions, clone monitor, context menus
- ✅ Dedicated incidents page with column-based grid, filter/sort/search, time range
- ✅ Pre-computed uptime bars on monitor docs (dashboard loads in ~0.3s)
- ✅ Plan gating: Free (5 monitors, 5min, email) vs Pro (250, 60s, Slack + webhooks)
- ✅ Monitor detail: unified uptime slicer (24h/7d/30d), response chart with time picker, incidents table, CSV export
- ✅ Custom check interval for Pro users (60–300s slider)
- ✅ Live-ticking last check counter with polling
- ✅ Domain, DNS, SSL, email delivery all working

---

## Dev Environment

```bash
cd /Applications/statusrooster
source venv/bin/activate
uvicorn app.main:app --reload --port 8080
```
- Local Firestore uses production data (same project)
- Cloud Scheduler cron does NOT run locally — checks only happen in production
- Test user: `testaccount1@statusrooster.com` (plan: pro)

---
---

# 📋 Completed Work

## Phase 1: Core Engine — Days 1-4 ✅

### Day 1 — Scaffolding & Auth ✅
- [x] FastAPI project structure, Dockerfile, config, Firestore client
- [x] User model + CRUD, Auth: signup, login, JWT middleware
- [x] Base Jinja2 template, health check, deploy to Cloud Run

### Day 2 — Monitors & Check Engine ✅
- [x] Monitor model + CRUD, plan enforcement (5 monitors Free)
- [x] API: create, list, get, update, delete monitors
- [x] Check engine: HTTP checks with status tracking
- [x] Dashboard template (basic), Add monitor form, Edit page

### Day 3 — Cron & Alerts ✅
- [x] Cloud Scheduler cron (60s → `POST /cron/check`)
- [x] Check model + storage, uptime calculation
- [x] SendGrid email alerts (down + recovery), incident tracking
- [x] Monitor detail page, flash messages, deploy

### Day 4 — Status Pages & Billing ✅
- [x] Public status pages (`/s/{slug}`), aggregate status page
- [x] SSL checking, keyword checking, response threshold alerts
- [x] Stripe Checkout + webhooks (Free → Pro upgrade)
- [x] Settings page, plan display, deploy

## Phase 2: Feature Suite & Billing — Days 5-9 ✅

### Day 5-6 — Slack, Webhooks, API v1, Badges ✅
- [x] Slack webhook alerts, webhook URL alerts
- [x] Public API v1 (6 endpoints, API key auth)
- [x] Uptime badges (3 SVG types), API docs page

### Day 7-8 — Settings, Export, Maintenance ✅
- [x] Settings: email, password, Slack, webhook, phone, delete account
- [x] CSV export (Pro), maintenance windows (Pro)
- [x] Google OAuth, response chart (Chart.js)

### Day 9 — Developer-First Pivot & Polish ✅
- [x] New design system: indigo brand, Inter + JetBrains Mono
- [x] Landing page rewrite (developer-first hero, terminal code block)
- [x] Pricing restructure (Free 5 / Pro $9), all templates updated
- [x] API docs overhaul: tabbed code blocks, copy buttons, field references
- [x] OpenAPI/Swagger playground, CSS unification (~2,600→4,500 lines)

## Phase 3: Hardening & Launch — Days 10-12 (in progress)

### Day 10A — Critical Backend Gating ✅
- [x] `paused` field: model default + checker skip + API schema
- [x] Check interval enforcement per plan (Free=5min, Pro=60s)
- [x] Slack/response threshold gated to Pro
- [x] Status page limit: Free=1, Pro=10
- [x] `paused`/`public` toggles on Add + Edit forms
- [x] Fixed FREE_MONITOR_LIMIT (50→5)

### Day 10B — GitHub OAuth 🔲
- [ ] Register GitHub OAuth App, set env vars, test

### Day 10C — Dashboard Full Redesign ✅
- [x] "Up for X" / "Down for X" duration text
- [x] Three-dot ⋯ context menu (pause/resume, edit, clone, delete, copy URL)
- [x] Pause/Resume in monitor detail header
- [x] Left sidebar navigation (`dashboard_base.html`)
- [x] 30-day daily + 24-hour hourly uptime sparkline bars with toggle
- [x] Card-based monitor rows, status strip, per-row inline stats
- [x] Bulk actions, search/filter/sort
- [x] Pre-computed uptime bars (27s → 0.3s dashboard load)

### Day 10D — Monitor Detail Complete Redesign ✅
- [x] Unified uptime slicer (24h/7d/30d), response chart time picker
- [x] Top stat cards (Status, Last check, MTBF), live-ticking counter
- [x] Incidents table with root cause badges, CSV export
- [x] Config grid, alert channels display, uptime badge copy widgets
- [x] Custom check interval slider (Pro), polling endpoint

### Day 10G — Heartbeat + Email Resilience + SMS ✅
- [x] Heartbeat/cron monitoring: type toggle, ping URL, overdue detection
- [x] Post-creation modal with copy-ready snippets
- [x] Email retry (3 attempts) + exponential backoff + circuit breaker
- [x] Real Twilio SMS (Pro-gated)

### Day 10H — 4 Monitor Types ✅
- [x] HTTP/HTTPS, JSON/API (assertions builder), Heartbeat/Cron, SSL Certificate
- [x] 4-button type grid selector, type-specific form sections
- [x] `check_json_api()`, `check_ssl_certificate()`, `_resolve_json_path()`, `_evaluate_assertion()`
- [x] Type badges on dashboard + edit page + detail page
- [x] "warn" status support (SSL approaching expiry)

### Day 11A — Incidents Pages ✅
- [x] Dedicated `/incidents` page: column grid, filter/sort/search, time range
- [x] Incident detail page: root cause card, status + timestamps, "Go to monitor" link
- [x] Active filter badge with ✕ clear button on dashboard + incidents

---
---

# 🚧 Active Work — Remaining Before Launch

> Everything below is **not yet done**. Work through each section sequentially. Run every testing gate before moving to the next phase.

---

## UI Redesign — Add/Edit Monitor Forms

> **Problem**: The current Add/Edit forms look "cheap and AI-generated" — every field is stacked identically in plain white cards with no visual hierarchy, grouping, or breathing room. The redesign organizes fields into logical **card sections** with clear headings, uses 2-column grids where natural, adds subtle visual polish (section icons, better spacing, pro badges), and makes the experience feel hand-crafted.

**Files to change:**
| File | What Changes |
|------|-------------|
| `app/static/style.css` | Replace/extend `.mf-*` section (~lines 4230–4540) |
| `app/templates/add_monitor.html` | Full rewrite of form layout/structure |
| `app/templates/edit_monitor.html` | Full rewrite of form layout/structure |
| `app/routers/pages.py` | Parse new fields: `http_method`, `basic_auth_user`, `basic_auth_pass`, `follow_redirects` |
| `app/models/monitor.py` | Add `follow_redirects` field (other new fields already exist) |

**Design principles:**
1. **Sectioned cards** — Each logical group lives in its own bordered card with a section title + small inline SVG icon
2. **Two-column fields** where natural (timeout + status code, username + password) — `.mf-field-row` flex grid
3. **Pro gating is visual** — locked sections show subtle overlay + upgrade link, not just disabled inputs
4. **Collapsible Advanced Settings** — auto-open on Edit if any advanced field has a non-default value
5. **Consistent hint text** — every field gets a helpful `.hint` subtext
6. **Sticky submit footer** — keep existing `.mf-footer` pattern
7. **Type switcher** — select dropdown on Add, read-only badge on Edit

**Rules:**
- No new JS frameworks — vanilla JS only
- No external CSS — all in `style.css`, keep `.mf-*` prefix
- SSR-first — Jinja2 templates only
- Backend already has `http_method`, `basic_auth_user`, `basic_auth_pass` params — we expose them on the form
- Edit form must preserve backward compatibility — existing monitors must render correctly

---

### Phase 1: CSS Foundation

- [x] **1.1** Add `.mf-section-header` — flex row with icon + title (replaces plain `.mf-section-title`)
- [x] **1.2** Add `.mf-field-row` — 2-column flex grid for side-by-side fields, stacks on mobile
- [x] **1.3** Add `.mf-field-group` — wrapper for a single field in the grid (label + input + hint)
- [x] **1.4** Add `.mf-pro-overlay` — subtle visual treatment for locked pro features (disabled state + badge)
- [x] **1.5** Add `.mf-method-select` — HTTP method button group (HEAD/GET/POST/PUT/PATCH/DELETE/OPTIONS)
- [x] **1.6** Add `.mf-toggle-row` — styled toggle/switch row for boolean settings (follow redirects, public, paused)
- [x] **1.7** Add `.mf-auth-section` — auth type selector + credential fields
- [x] **1.8** Refine existing `.mf-section` — slightly more padding, subtle left-border accent on hover
- [x] **1.9** Refine `.mf-heading` — add subtitle support (`.mf-heading-sub`) for edit page to show monitor type

#### ✅ Phase 1 Gate — CSS Validation
- [x] **1.T1** `grep` for every new class name in `style.css` — confirm all 9 classes exist and have rules
- [x] **1.T2** Create a throwaway HTML snippet with one of each new class to confirm they render without errors — check browser DevTools for missing/overridden styles
- [x] **1.T3** Verify no existing `.mf-*` classes were broken — load current Add Monitor page and confirm it still renders identically (templates not yet touched)

---

### Phase 2: Add Monitor Template (`add_monitor.html`)

Layout order (top to bottom):
- [x] **2.1** Back link + heading (existing pattern, keep)
- [x] **2.2** **Section: Monitor Type** — type selector dropdown (existing, keep)
- [x] **2.3** **Section: URL / Endpoint** — contextual per type:
  - HTTP: URL input with `https://` prefix hint
  - JSON/API: API endpoint input
  - Heartbeat: "How it works" info box
  - SSL: Domain input + threshold in a 2-column row
- [x] **2.4** **Section: Friendly name + Group** — 2-column row (name required, group optional with datalist)
- [x] **2.5** **Section: Notifications** — Email (always on) + Slack (Pro) + Webhook (Pro) using `.mf-notify-row`
- [x] **2.6** **Section: Monitor Interval** — slider (Pro) or locked display (Free). Hidden for heartbeat type.
- [x] **2.7** **Section: Advanced Settings** (collapsible) containing sub-sections per type:
  - HTTP: Request timeout + Expected status code (2-col row), HTTP method (button group), Follow redirects toggle, Basic Auth (type select → username/password 2-col), Keyword builder, Response threshold
  - JSON/API: Timeout + Expected status code (2-col), Auth header, JSON assertions builder, Response threshold
  - Heartbeat: (hidden — no advanced settings)
  - SSL: (hidden — settings already in main section)
- [x] **2.8** **Section: Advanced Settings → Status Page** — Public toggle + slug field
- [x] **2.9** **Section: Advanced Settings → Start Paused** — Paused toggle
- [x] **2.10** **Section: Advanced Settings → Maintenance Windows** — Pro-gated window builder
- [x] **2.11** Sticky submit footer (existing pattern)
- [x] **2.12** JavaScript: Ensure `setMonitorType()` / `syncFieldNames()` work with new DOM structure
- [x] **2.13** JavaScript: HTTP method button group click handler

#### ✅ Phase 2 Gate — Add Form Rendering Tests
- [x] **2.T1** Load `/monitors/add` as Pro user — page renders without errors (check terminal for Jinja2 errors)
- [ ] **2.T2** Type switcher — click each of the 4 types, confirm correct sections show/hide for each
- [x] **2.T3** HTTP method button group — click each method, confirm hidden input updates
- [x] **2.T4** Basic Auth — select "Basic Auth" → username/password fields appear; select "None" → they hide
- [x] **2.T5** Follow redirects toggle — renders, checked by default
- [ ] **2.T6** Keyword builder — add 2 keywords with AND, confirm hidden input value updates
- [ ] **2.T7** JSON assertions builder — switch to JSON/API type, add an assertion, confirm row renders
- [ ] **2.T8** Maintenance window builder (Pro) — add a window, confirm day/start/end row appears
- [ ] **2.T9** Slug field — check "Public status page", confirm slug input appears; type in it, confirm preview updates
- [x] **2.T10** 2-column layout — >768px: name + group side-by-side, timeout + status code side-by-side; <768px: stacks vertically
- [x] **2.T11** Sticky footer — scroll down, confirm "Add monitor" button stays fixed at bottom
- [x] **2.T12** All `name` attributes — inspect form HTML, verify every field has a `name` attribute and no duplicates for active type

---

### Phase 3: Edit Monitor Template (`edit_monitor.html`)

- [x] **3.1** Back link + heading with monitor type subtitle badge
- [x] **3.2** Mirror section structure from Add, but:
  - Monitor type is read-only (badge)
  - Heartbeat shows ping URL with copy button
  - Pre-populate all fields from `monitor` dict
  - HTTP method pre-selected from `monitor.http_method`
  - Basic Auth pre-populated from `monitor.basic_auth_user` / `monitor.basic_auth_pass`
  - Follow redirects pre-populated from `monitor.follow_redirects`
- [x] **3.3** Auto-open Advanced Settings if any advanced field has a non-default value
- [x] **3.4** Mirror all JS from add_monitor.html (interval display, slug preview, maintenance windows, assertions, keyword builder with init)

#### ✅ Phase 3 Gate — Edit Form Rendering Tests
- [x] **3.T1** Load edit for **HTTP monitor** — all fields pre-populated (URL, name, group, email, interval, status code, timeout, keyword)
- [x] **3.T2** Load edit for **Heartbeat monitor** — ping URL with copy button, interval/grace pre-populated, no URL field, no interval slider
- [x] **3.T3** Load edit for **JSON/API monitor** — URL pre-populated, auth header shown, assertions rendered *(verified with `RsJhlKuTjnmWC4QpE3vy` — GitHub API Zen)*
- [x] **3.T4** Load edit for **SSL monitor** — domain + threshold pre-populated, no HTTP advanced fields *(verified with `cv0aiPhqP2l4oVlhbT9m` — Google SSL Check)*
- [x] **3.T5** Auto-open Advanced — HTTP monitor with keyword set → Advanced expanded on load
- [x] **3.T6** Auto-open Advanced — HTTP monitor with no advanced values → Advanced collapsed
- [x] **3.T7** HTTP method — correct method button highlighted (defaults to GET for old monitors)
- [x] **3.T8** Basic Auth — monitor with `basic_auth_user` set → username/password visible and pre-populated
- [x] **3.T9** Backward compat — old monitor without `http_method`/`basic_auth_user`/`follow_redirects` → renders with sane defaults (GET, no auth, follow=true)

---

### Phase 4: Backend Updates (`pages.py` + `monitor.py` + `checker.py`)

> **Context from audit:** The UI has fields for `http_method`, `basic_auth_user`, `basic_auth_pass`, and `follow_redirects` — but they are ghost fields. The form renders them, but `pages.py` never parses them, `monitor.py` never stores them, and `checker.py` never uses them. This phase wires all 4 fields end-to-end: form → storage → execution.
>
> **Audit findings (4 ghost fields on HTTP type):**
> | Field | UI | pages.py | monitor.py | checker.py | Fix |
> |---|---|---|---|---|---|
> | `http_method` | ✅ hidden input | ❌ not parsed | ❌ not stored | ❌ hardcoded `client.get()` | Parse → store → use `client.request(method, ...)` |
> | `basic_auth_user` + `basic_auth_pass` | ✅ text/password | ❌ not parsed | ❌ not stored | ❌ no auth header sent | Parse → store → encode `Basic base64(user:pass)` → send as header (Pro only) |
> | `follow_redirects` | ✅ checkbox | ❌ not parsed | ❌ not stored | ❌ hardcoded `True` | Parse → store → pass boolean to `httpx` |
>
> **JSON/API, Heartbeat, SSL are fully wired** — no changes needed for those types.

#### Build Items — Storage Layer (`monitor.py`)
- [x] **4.1** `create_monitor()`: Add `follow_redirects: bool = True` parameter, store in `monitor_data` dict
- [x] **4.2** `create_monitor()`: Store `http_method`, `basic_auth_user`, `basic_auth_pass` in `monitor_data` dict (params already exist, just not saved)

#### Build Items — Form Parsing (`pages.py`)
- [x] **4.3** `add_monitor()` POST: Parse `http_method`, `basic_auth_user`, `basic_auth_pass`, `follow_redirects` from form
- [x] **4.4** `add_monitor()`: Pass all 4 new fields to `create_monitor()`
- [x] **4.5** `edit_monitor_submit()` POST: Parse same 4 fields, include in `updates` dict
- [x] **4.6** `edit_monitor_submit()`: Gate `basic_auth_user`/`basic_auth_pass` to Pro plan only (Free users get empty strings)

#### Build Items — Checker Engine (`checker.py`)
- [x] **4.7** `check_url()`: Accept `http_method` param (default `"GET"`), use `client.request(method, url, ...)` instead of `client.get(url, ...)`
- [x] **4.8** `check_url()`: Accept `follow_redirects` param (default `True`), pass to `httpx`
- [x] **4.9** `check_url()`: Accept `basic_auth_user` + `basic_auth_pass` params, encode as `Authorization: Basic base64(user:pass)` header when both are non-empty
- [x] **4.10** `check_url_with_retry()`: Pass through `http_method`, `follow_redirects`, `basic_auth_user`, `basic_auth_pass` to `check_url()`
- [x] **4.11** `run_checks()`: Read `http_method`, `follow_redirects`, `basic_auth_user`, `basic_auth_pass` from monitor doc, pass to `check_url_with_retry()` for HTTP type monitors

#### ✅ Phase 4 Gate — Backend Submission Tests
- [x] **4.T1** Create HTTP monitor with all new fields (`http_method=POST`, `basic_auth_user=admin`, `basic_auth_pass=secret`, `follow_redirects=false`) — verify Firestore doc has all 4 fields
- [x] **4.T2** Create HTTP monitor with defaults (don't send new fields) — verify `http_method=GET`, `follow_redirects=True`, `basic_auth_user=""`, `basic_auth_pass=""`
- [x] **4.T3** Create Heartbeat monitor — verify new fields stored with defaults (GET, True, empty auth)
- [x] **4.T4** Create JSON/API monitor — verify defaults stored
- [x] **4.T5** Create SSL monitor — verify defaults stored
- [x] **4.T6** Edit HTTP monitor — change `http_method=PUT`, `basic_auth_user=newuser` — verify Firestore updated
- [x] **4.T7** Edit HTTP monitor without changing new fields — verify existing values not clobbered
- [x] **4.T8** Free plan gating — `basic_auth_user`/`basic_auth_pass` stored as empty regardless of input
- [x] **4.T9** Pro plan gating — custom interval (e.g., 120s) accepted, basic auth saved

#### ✅ Phase 4 Gate — Checker Engine Tests
- [x] **4.T10** Server starts without errors — `uvicorn` reload completes cleanly
- [x] **4.T11** HTTP monitor with `http_method=HEAD` — checker sends HEAD request (verify in check result: no body expected)
- [x] **4.T12** HTTP monitor with `follow_redirects=false` on a 301 URL — checker reports status 302 (not the redirect target)
- [x] **4.T13** HTTP monitor with `basic_auth_user`/`basic_auth_pass` — checker sends `Authorization: Basic` header *(verified against httpbin.org/basic-auth — correct creds=200, wrong creds=401)*
- [x] **4.T14** JSON/API monitor — unchanged, still uses `auth_header` (not basic auth), still works
- [x] **4.T15** Heartbeat monitor — unchanged, overdue detection still works
- [x] **4.T16** SSL monitor — unchanged, cert check still works

---

### Phase 5: Form End-to-End Integration QA

- [ ] **5.1** **E2E: HTTP full flow** — Add with custom method (POST), basic auth, keyword, 120s interval → verify on dashboard → edit to change method to GET, remove auth → verify saved
- [ ] **5.2** **E2E: JSON/API full flow** — Add with auth header + 2 assertions → verify → edit to add 3rd assertion → verify
- [ ] **5.3** **E2E: Heartbeat full flow** — Add → verify ping URL on dashboard → edit interval → verify
- [ ] **5.4** **E2E: SSL full flow** — Add with 30-day threshold → verify → edit to 7 days → verify
- [ ] **5.5** **E2E: Free plan** — Slack/Webhook disabled, interval locked, maintenance hidden → submit works
- [ ] **5.6** **E2E: Pro plan** — Slack + webhook + custom interval + maintenance window → all saved
- [ ] **5.7** **Mobile spot-check** — Add + Edit at 375px → stacks cleanly, no horizontal scroll, sticky footer full-width
- [ ] **5.8** **Backward compat** — Edit pre-redesign monitor (no `http_method`/`follow_redirects`) → loads with defaults → save without changes → no data lost
- [ ] **5.9** **Delete regression** — Delete monitor from dashboard → gone, no errors
- [ ] **5.10** **Pause/Resume regression** — Pause from dashboard → status changes, edit shows "Paused" checked
- [ ] **5.11** **Status page regression** — Create public monitor with slug → `/s/{slug}` renders

---

## UI Redesign — Dashboard

> **Problem**: Monitor rows are overloaded (type badge, duration text, interval icon, dual uptime bars with toggle, 3 inline stats, ⋯ menu with 7 items). Toolbar is hard to parse. Status strip is passive. No type filter. Mobile is cramped. We need to simplify to match our "indie-dev simple" positioning.

**Files to change:**
| File | What Changes |
|------|-------------|
| `app/templates/dashboard.html` | Template restructure — status strip, toolbar, monitor rows, empty state |
| `app/static/style.css` | Rework dashboard CSS (~lines 848–1400, 1516–1680) |
| `app/routers/pages.py` | Dashboard route — add aggregate stats (avg response, total incidents today) |

**Design principles:**
1. **Two-tier row** — Primary line (status dot + name + mini uptime bar + uptime %) + secondary line (URL, response time, last checked, type badge). Secondary is smaller, muted.
2. **30-day uptime bar** — Inline mini bar chart (30 narrow bars, green/red/gray) in each row. Signature visual.
3. **Status strip with teeth** — Red tint when monitors down. Aggregate: total monitors, overall uptime %, avg response time.
4. **Clean filter bar** — Pill-style filter tabs (All/Up/Down/Paused/Pending) replacing dropdown. Group + Type as secondary dropdowns.
5. **Search is prominent** — Full-width search bar above monitor list, not jammed in toolbar.
6. **Responsive** — On mobile, row collapses to: status dot + name + uptime % on one line, URL below.
7. **Subtle hover** — Rows highlight with soft left-border accent.
8. **Empty state with personality** — Rooster emoji/SVG, friendlier copy, prominent CTA.

---

### Phase 6: Dashboard CSS

- [ ] **6.1** Add `.d-status-strip-alert` — red-tinted variant when monitors are down
- [ ] **6.2** Add `.d-agg-stat` — aggregate stat pill (e.g., "99.8% uptime", "142ms avg")
- [ ] **6.3** Add `.d-filter-pills` — horizontal pill-style filter tabs
- [ ] **6.4** Add `.d-filter-pill` — individual pill button with active state
- [ ] **6.5** Rework `.monitor-card` — two-tier layout (primary + secondary line)
- [ ] **6.6** Add `.d-row-primary` — primary line flex layout (dot + name + mini bars + uptime %)
- [ ] **6.7** Add `.d-row-secondary` — secondary line (URL + response + last checked + type), smaller/muted
- [ ] **6.8** Add `.d-uptime-bars` — inline mini uptime bar container (30 bars, 2px wide, 16px tall)
- [ ] **6.9** Add `.d-uptime-bar` — individual bar segment (green/red/yellow/gray)
- [ ] **6.10** Rework mobile responsive for two-tier row — stack gracefully at <768px

#### ✅ Phase 6 Gate — Dashboard CSS Validation
- [ ] **6.T1** Grep all new dashboard class names — confirm they exist in `style.css`
- [ ] **6.T2** Load dashboard — confirm existing layout still renders (CSS-only, template not yet touched)
- [ ] **6.T3** Inspect `.d-uptime-bars` with DevTools — confirm bar container dimensions correct

---

### Phase 7: Dashboard Template + JS (`dashboard.html`)

- [ ] **7.1** **Status strip upgrade** — aggregate stats: overall uptime %, avg response time, total incidents. Red tint when any monitor down.
- [ ] **7.2** **Monitors heading row** — heading + "Add monitor" button + monitor count badge (polish)
- [ ] **7.3** **Search bar** — move above filter row, full-width, search icon
- [ ] **7.4** **Filter pills** — pill tabs: All / Up / Down / Warn / Paused / Pending with counts
- [ ] **7.5** **Secondary filters** — Group dropdown + Type dropdown (HTTP/JSON/Heartbeat/SSL) as small buttons
- [ ] **7.6** **Sort dropdown** — keep existing, move to right side of filter row
- [ ] **7.7** **Bulk actions** — keep select-all + bulk actions, visually separate (floating bar at bottom when items selected)
- [ ] **7.8** **Monitor row — primary line** — Status dot + name + 30-day uptime mini bars + uptime %
- [ ] **7.9** **Monitor row — secondary line** — Type badge + URL (no protocol, longer truncation) + response time/SSL/heartbeat + last checked
- [ ] **7.10** **30-day uptime bars rendering** — read `daily_uptime_bars`, render 30 colored bars (green ≥99.5%, yellow ≥95%, red <95%, gray = no data)
- [ ] **7.11** **Three-dot menu** — keep existing (edit, pause/resume, clone, copy URL, delete)
- [ ] **7.12** **Empty state** — rooster emoji hero, friendlier copy, prominent CTA
- [ ] **7.13** **Heartbeat created modal** — keep existing
- [ ] **7.14** **JS updates** — update `filterTable()` for type filter, `sortList()` for new DOM, `tickLastChecked()` unchanged

#### ✅ Phase 7 Gate — Dashboard Rendering Tests
- [ ] **7.T1** Load dashboard as Pro user with monitors — no errors
- [ ] **7.T2** Status strip — aggregate stats show (uptime %, avg response, incident count)
- [ ] **7.T3** Status strip — with "down" monitor, red tint applies
- [ ] **7.T4** Filter pills — each pill filters correctly
- [ ] **7.T5** Type filter — select "Heartbeat", only heartbeat monitors show
- [ ] **7.T6** Group filter — select a group, only that group shows
- [ ] **7.T7** Search — partial name match, rows filter live
- [ ] **7.T8** Sort — all sort modes work (Down first, A→Z, Z→A, Lowest/Highest uptime)
- [ ] **7.T9** 30-day uptime bars — render on each row, colors match data
- [ ] **7.T10** Two-tier row — primary + secondary lines visually distinct
- [ ] **7.T11** Bulk actions — select 2 monitors, bulk bar appears, pause/delete work
- [ ] **7.T12** Three-dot menu — edit/pause/clone/copy/delete all work
- [ ] **7.T13** Mobile (<768px) — rows stack, pills scroll, search full-width
- [ ] **7.T14** Empty state — user with 0 monitors sees empty state with CTA

---

### Phase 8: Dashboard Backend (`pages.py`)

- [ ] **8.1** Compute `avg_response_ms` across all monitors (skip heartbeat/SSL)
- [ ] **8.2** Compute `overall_uptime_pct` (average of all monitors' 24h uptime)
- [ ] **8.3** Count today's incidents (open + resolved) for user's monitors
- [ ] **8.4** Pass `avg_response_ms`, `overall_uptime_pct`, `incidents_today` to template context

#### ✅ Phase 8 Gate — Backend Data Tests
- [ ] **8.T1** Load dashboard — `avg_response_ms` is sane (not 0, not None unless no monitors)
- [ ] **8.T2** `overall_uptime_pct` computed correctly — cross-check against 2-3 monitors' `uptime_24h`
- [ ] **8.T3** `incidents_today` count — create test incident, count increments
- [ ] **8.T4** Performance — dashboard loads <500ms locally (no extra Firestore queries beyond monitors + incidents)
- [ ] **8.T5** Edge case — 0 monitors → no errors, empty state, aggregate stats show "—"

---

### Phase 9: Dashboard E2E QA

- [ ] **9.1** **Full flow** — Create monitor → appears immediately → correct status/uptime/response
- [ ] **9.2** **Edit flow** — Three-dot → Edit → change name → dashboard updates
- [ ] **9.3** **Delete flow** — Delete → gone, aggregate stats update
- [ ] **9.4** **Pause/Resume** — Pause via three-dot → paused state → resume → up/pending
- [ ] **9.5** **Clone** — Clone → new copy appears
- [ ] **9.6** **Free plan** — Upgrade banner at 4+ monitors, correct limits
- [ ] **9.7** **Filter + Search combo** — Filter "Down" + search name → only matching down monitors
- [ ] **9.8** **Mobile full flow** — Complete interaction at 375px (filter, search, menu, navigate)
- [ ] **9.9** **30-day bars accuracy** — Compare bars against `daily_uptime_bars` data
- [ ] **9.10** **Performance benchmark** — 10+ monitors loads <1s, no layout shift, no JS console errors

---

## Remaining Pre-Launch Tasks (Non-UI)

### 10B. GitHub OAuth 🔲
- [ ] Register GitHub OAuth App, set `GITHUB_CLIENT_ID` + `GITHUB_CLIENT_SECRET` in `.env` + Cloud Run
- [ ] Test: "Continue with GitHub" → authorize → dashboard

### 10E. Add/Edit Form — Backend Fields ✅ *(merged into Phase 4)*
> _Fully covered by Phase 4 build items 4.1–4.11 and gate tests 4.T1–4.T16. No separate work needed._

### 10F. Pro Upsell Polish 🔲
- [ ] Check interval badge on dashboard rows: "⏱ 5min" for Free with tooltip "Upgrade for 60s →"
- [ ] Greyed Pro-only columns with lock 🔒 icon
- [ ] Alert email footer for Free: "Upgrade to Pro for 60s checks, Slack alerts, and webhooks →"
- [ ] Gate Slack input in Add modal for Free users (grey out + upgrade link)

### 11B. Activity Log / Event Timeline 🔲
- [ ] **Incident events sub-collection** — `incidents/{id}/events/{auto_id}` → `{type, timestamp, metadata}`
  - Event types: `detected`, `alert_email_sent`, `alert_slack_sent`, `alert_webhook_sent`, `resolved`, `recovery_*_sent`
- [ ] **Log events in checker + alert service** — write events on detection, each alert, resolve, recovery
- [ ] **Timeline on incident detail** — chronological vertical timeline, each event: icon + text + timestamp
- [ ] **Alert delivery logging** — store success/fail from SendGrid/Slack/webhook, show on timeline

### 11C. Hardening 🔲
- [ ] Custom 404 page (link to dashboard)
- [ ] Custom 500 page (link to dashboard)
- [ ] Meta tags (title, description, OG image) on all public pages
- [ ] Favicon (rooster icon, 32x32 + 180x180 apple-touch)
- [ ] Input validation audit: all forms + all API endpoints
- [ ] Mobile viewport testing: dashboard, detail, edit, landing, pricing, status page

### 11E. API & API Docs QA 🔲

> **Goal:** The public API and its documentation are a first-class product surface. Every endpoint must work exactly as documented, every example must be copy-paste-runnable, every field reference must match reality, and the Swagger playground must stay in sync. This is a dedicated pass to verify consistency, correctness, and completeness end-to-end.

#### API Backend — Functional Tests (curl against localhost:8080)
- [ ] **11E.1** Auth — missing `X-API-Key` header → 401 + clear error message
- [ ] **11E.2** Auth — invalid/revoked key → 401
- [ ] **11E.3** Auth — valid key → 200 on `GET /api/v1/monitors`
- [ ] **11E.4** List monitors — returns all monitors for authenticated user, `{data: [...], error: null, meta: {total: N}}`
- [ ] **11E.5** Get single monitor — valid ID → 200 with full monitor object; invalid ID → 404
- [ ] **11E.6** Create HTTP monitor — all fields accepted, response includes new fields (`http_method`, `follow_redirects`, `basic_auth_user`, `basic_auth_pass`), status 201
- [ ] **11E.7** Create JSON/API monitor — `json_assertions` + `auth_header` stored and returned, status 201
- [ ] **11E.8** Create Heartbeat monitor — returns `ping_url`, `heartbeat_interval`, `heartbeat_grace_period`, status 201
- [ ] **11E.9** Create SSL monitor — `ssl_domain` + `ssl_expiry_threshold_days` stored and returned, status 201
- [ ] **11E.10** Create monitor — plan gating: Free user at 5 monitors → 403; basic auth fields silently emptied for Free
- [ ] **11E.11** Create monitor — validation: missing `name` → 422; invalid `monitor_type` → 422; invalid `http_method` → 400
- [ ] **11E.12** Update monitor — partial update (send only `keyword`) → only that field changes, others preserved
- [ ] **11E.13** Update monitor — `http_method`, `follow_redirects`, `basic_auth_user`, `basic_auth_pass` all updatable
- [ ] **11E.14** Update monitor — can't update another user's monitor → 404
- [ ] **11E.15** Delete monitor — 200 + monitor gone; delete again → 404
- [ ] **11E.16** Check history — `GET /api/v1/monitors/{id}/checks` → returns recent checks with `{data: [...], meta: {total}}`
- [ ] **11E.17** List incidents — `GET /api/v1/incidents` → `{data: [...], error: null, meta: {total}}`
- [ ] **11E.18** Get incident — valid ID → full incident object; invalid → 404
- [ ] **11E.19** Response shape consistency — every endpoint returns `{data, error}` or `{data, error, meta}` — no exceptions

#### API Docs — Content Accuracy (`api_docs.html`)
- [ ] **11E.20** Auth section — instructions match actual header name (`X-API-Key`), key format (`sr_...`), error responses
- [ ] **11E.21** Client setup — curl/Python/JS snippets are copy-paste-runnable (correct base URL, headers)
- [ ] **11E.22** HTTP Create — param table matches `ApiCreateMonitor` schema exactly (all fields, types, defaults, required/optional)
- [ ] **11E.23** HTTP Create — response shape JSON matches actual `POST /api/v1/monitors` response (field names, types, order)
- [ ] **11E.24** HTTP Update — param table matches `ApiUpdateMonitor` schema exactly
- [ ] **11E.25** JSON/API Create — param table includes `json_assertions`, `auth_header`, correct types
- [ ] **11E.26** JSON/API Update — param table matches actual accepted fields
- [ ] **11E.27** Heartbeat Create — param table includes `heartbeat_interval`, `heartbeat_grace_period`
- [ ] **11E.28** Heartbeat Update — param table matches
- [ ] **11E.29** SSL Create — param table includes `ssl_domain`, `ssl_expiry_threshold_days`
- [ ] **11E.30** SSL Update — param table matches
- [ ] **11E.31** List All Monitors — response shape matches actual response (array of monitor objects with `meta.total`)
- [ ] **11E.32** Get Single Monitor — response shape matches actual response
- [ ] **11E.33** Check History — param table (query params like `limit`) matches, response shape matches
- [ ] **11E.34** Delete Monitor — documented response matches actual
- [ ] **11E.35** Incidents — List + Get response shapes match actual
- [ ] **11E.36** Field reference table — every field listed exists in actual responses; no missing fields; types correct
- [ ] **11E.37** Field reference — "HTTP Only" section lists `http_method`, `follow_redirects`, `basic_auth_user`, `basic_auth_pass`
- [ ] **11E.38** Plan Limits section — Free/Pro limits match actual gating in code
- [ ] **11E.39** Rate Limits section — documented limits match actual implementation (if any)

#### API Docs — Code Examples & UX
- [ ] **11E.40** All curl examples — correct method, correct URL path, correct headers, valid JSON body
- [ ] **11E.41** All Python examples — correct `requests` usage, correct JSON keys
- [ ] **11E.42** All JavaScript examples — correct `fetch` usage, correct JSON keys
- [ ] **11E.43** Tab switching — clicking curl/Python/JS tabs works on every endpoint section
- [ ] **11E.44** Copy buttons — every code block copy button copies correct content
- [ ] **11E.45** Sidebar navigation — every sidebar link scrolls to correct section
- [ ] **11E.46** Endpoint expand/collapse — all accordion sections open/close correctly
- [ ] **11E.47** Swagger playground link — `/docs` loads, all endpoints listed, "Authorize" button works with API key
- [ ] **11E.48** Webhook Payloads section — documented payload shape matches what `alerts.py` actually sends
- [ ] **11E.49** Uptime Badges section — all 3 badge URLs work, SVG renders correctly

#### API Docs — Cross-Consistency Checks
- [ ] **11E.50** Every field in `ApiCreateMonitor` Pydantic schema appears in the corresponding docs param table
- [ ] **11E.51** Every field in `ApiUpdateMonitor` Pydantic schema appears in the corresponding docs param table
- [ ] **11E.52** Every field returned by `_serialize_monitor()` appears in the field reference table
- [ ] **11E.53** No "ghost fields" — every documented field is actually parsed, stored, and returned by the backend
- [ ] **11E.54** Pro-gated fields are consistently marked "(Pro)" in both param tables and field reference

### 11D. Admin Dashboard 🔲
- [ ] Route: `GET /admin` — guard: only your email can access
- [ ] KPI cards: total users, Pro users, Free users, MRR, total monitors, checks today
- [ ] Signup list: last 20 signups with email + date + plan
- [ ] Cron health: last run time, monitors checked, alerts fired, errors

### Day 12 — Testing & Launch 🔲

**12A. Testing (~1.5 hrs)**
- [ ] Full manual E2E test in production:
  - Signup (email + GitHub OAuth)
  - Add monitor → first check → status update
  - Trigger downtime → email alert → incident created
  - Recovery → recovery alert → incident resolved
  - Incident detail + activity log
  - Edit monitor (timeout, auth, HTTP method, keyword, threshold)
  - Pause/resume from dashboard + detail header
  - Export CSV (Pro), status page, uptime badges
  - API: create, list, update, delete via curl
  - Stripe: upgrade to Pro, features unlock, downgrade
- [ ] Dogfooding: StatusRooster monitoring statusrooster.com
- [ ] Mobile viewport spot-check
- [ ] Switch Stripe from test to live mode
- [ ] Verify all Cloud Run env vars

**12B. Launch Prep**
- [ ] Final Cloud Run deploy with production env vars
- [ ] Write Show HN post
- [ ] Screenshots / demo GIF for README
- [ ] Update README.md

**12C. Launch**
- [ ] Submit Show HN
- [ ] Post to r/SideProject, r/webdev, r/SaaS, IndieHackers
- [ ] Monitor comments, respond to feedback
- [ ] Hot-fix launch-day bugs
- [ ] Check admin dashboard for signups

---

## Post-Launch Backlog (Phase 4: Days 13+)

### Days 13-14 — Bug Fixes & Growth
- [ ] Fix bugs from real user feedback
- [ ] SEO pages: "Free Uptime Monitoring API", "UptimeRobot Alternative for Developers"
- [ ] Free SSL checker tool page (standalone, ranks on Google)
- [ ] Submit to AlternativeTo, G2
- [ ] Plan Product Hunt launch (week 3)

### v1.1 — Feature Additions (based on user feedback)
- [ ] Custom request headers (key/value input, stored as JSON array)
- [ ] Multi-region checks (Pro — US-East, EU-West, Asia, confirm from 2+ before alerting)
- [ ] Discord webhook (same pattern as Slack)
- [ ] Alert confirmation threshold ("wait N fails before alerting")

### Future Backlog
- [ ] CLI tool (`pip install statusrooster`)
- [ ] GitHub Actions integration
- [ ] Weekly Uptime Digest Email
- [ ] Team Plan ($29/mo: 500 monitors, 30s intervals, 5 seats)
- [ ] TCP/Ping checks, incident postmortem notes, domain expiry (WHOIS)
- [ ] Password reset flow, password-protected status pages, custom domains for status pages
- [ ] CI/CD pipeline (GitHub Actions → Cloud Run)
- [ ] Automated tests (pytest + httpx)
- [ ] Google OAuth consent screen: Testing → Production

---

## Execution Order Summary

| # | What | Status |
|---|------|--------|
| 1 | Phase 1: Form CSS foundation | ✅ |
| 2 | Phase 2: Add Monitor template | ✅ |
| 3 | Phase 3: Edit Monitor template | ✅ |
| 4 | Phase 4: Backend wiring | ✅ |
| 5 | Phase 5: Form E2E QA | 🔲 |
| 6 | Phase 6: Dashboard CSS | 🔲 |
| 7 | Phase 7: Dashboard template + JS | 🔲 |
| 8 | Phase 8: Dashboard backend | 🔲 |
| 9 | Phase 9: Dashboard E2E QA | 🔲 |
| 10 | 10B: GitHub OAuth | 🔲 |
| 11 | 10F: Pro upsell polish | 🔲 |
| 12 | 11B: Activity log | 🔲 |
| 13 | 11C: Hardening | 🔲 |
| 14 | 11E: API & API Docs QA | 🔲 |
| 15 | 11D: Admin dashboard | 🔲 |
| 16 | Day 12: Testing & launch | 🔲 |

**Work through Phases 1–9 sequentially. Run every Gate test before moving to the next Phase. Do not skip ahead.**

### Total Remaining Checkboxes
- Phase 1: ~~12~~ **0** ✅
- Phase 2: ~~25~~ **5** (5 browser-only gate tests remain)
- Phase 3: ~~13~~ **0** ✅
- Phase 4: ~~27~~ **0** ✅
- Phase 5: 11 E2E = **11**
- Phase 6: 10 build + 3 test = **13**
- Phase 7: 14 build + 14 test = **28**
- Phase 8: 4 build + 5 test = **9**
- Phase 9: 10 E2E = **10**
- Non-UI tasks: ~25 + 54 (11E) = **~79**
- **Grand total: ~155 checkboxes** (was 161, 72 completed + 54 new)

---

## Reference Documents (archived — content merged here)
- `COMPETITIVE_AUDIT.md` — full UptimeRobot page-by-page comparison
- `ACTION_PLAN.md` — original Day 10 workstream plan (superseded)
- `DASHBOARD_REDESIGN.md` — original dashboard redesign plan (superseded)
- `UI_REDESIGN.md` — original form + dashboard redesign checklist (superseded — merged into this tracker)
- `TESTING.md` — testing strategy notes

---

## Domain & Email Setup ✅
- [x] DNS pointed to Cloud Run, custom domain mapped, SSL provisioned
- [x] SendGrid domain authentication (3x CNAME validated)
- [x] `alerts@statusrooster.com` verified, email forwarding configured
- [x] `APP_URL` set to `https://statusrooster.com`
