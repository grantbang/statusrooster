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

- [x] **5.1** **E2E: HTTP full flow** — Add with custom method (POST), basic auth, keyword, 120s interval → verify on dashboard → edit to change method to GET, remove auth → verify saved
- [x] **5.2** **E2E: JSON/API full flow** — Add with auth header + 2 assertions → verify → edit to add 3rd assertion → verify
- [x] **5.3** **E2E: Heartbeat full flow** — Add → verify ping URL on dashboard → edit interval → verify
- [x] **5.4** **E2E: SSL full flow** — Add with 30-day threshold → verify → edit to 7 days → verify
- [x] **5.5** **E2E: Free plan** — Slack/Webhook disabled, interval locked, maintenance hidden → submit works
- [x] **5.6** **E2E: Pro plan** — Slack + webhook + custom interval + maintenance window → all saved
- [ ] **5.7** **Mobile spot-check** — Add + Edit at 375px → stacks cleanly, no horizontal scroll, sticky footer full-width *(browser-only)*
- [x] **5.8** **Backward compat** — Edit pre-redesign monitor (no `http_method`/`follow_redirects`) → loads with defaults → save without changes → no data lost
- [x] **5.9** **Delete regression** — Delete monitor from dashboard → gone, no errors
- [x] **5.10** **Pause/Resume regression** — Pause from dashboard → status changes, edit shows "Paused" checked
- [x] **5.11** **Status page regression** — Create public monitor with slug → `/s/{slug}` renders

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

- [x] **6.1** Add `.d-status-strip-alert` — red-tinted variant when monitors are down
- [x] **6.2** Add `.d-agg-stat` — aggregate stat pill (e.g., "99.8% uptime", "142ms avg")
- [x] **6.3** Add `.d-filter-pills` — horizontal pill-style filter tabs
- [x] **6.4** Add `.d-filter-pill` — individual pill button with active state
- [x] **6.5** Rework `.monitor-card` — two-tier layout (primary + secondary line)
- [x] **6.6** Add `.d-row-primary` — primary line flex layout (dot + name + mini bars + uptime %)
- [x] **6.7** Add `.d-row-secondary` — secondary line (URL + response + last checked + type), smaller/muted
- [x] **6.8** Add `.d-uptime-bars` — inline mini uptime bar container (30 bars, 2px wide, 16px tall)
- [x] **6.9** Add `.d-uptime-bar` — individual bar segment (green/red/yellow/gray)
- [x] **6.10** Rework mobile responsive for two-tier row — stack gracefully at <768px

#### ✅ Phase 6 Gate — Dashboard CSS Validation
- [x] **6.T1** Grep all new dashboard class names — confirm they exist in `style.css`
- [x] **6.T2** Load dashboard — confirm existing layout still renders (CSS-only, template not yet touched)
- [x] **6.T3** Inspect `.d-uptime-bars` with DevTools — confirm bar container dimensions correct

---

### Phase 7: Dashboard Template + JS (`dashboard.html`)

- [x] **7.1** **Status strip upgrade** — aggregate stats: overall uptime %, avg response time, total incidents. Red tint when any monitor down.
- [x] **7.2** **Monitors heading row** — heading + "Add monitor" button + monitor count badge (polish)
- [x] **7.3** **Search bar** — move above filter row, full-width, search icon
- [x] **7.4** **Filter pills** — pill tabs: All / Up / Down / Warn / Paused / Pending with counts
- [x] **7.5** **Secondary filters** — Group dropdown + Type dropdown (HTTP/JSON/Heartbeat/SSL) as small buttons
- [x] **7.6** **Sort dropdown** — keep existing, move to right side of filter row
- [x] **7.7** **Bulk actions** — keep select-all + bulk actions, visually separate (floating bar at bottom when items selected)
- [x] **7.8** **Monitor row — primary line** — Status dot + name + 30-day uptime mini bars + uptime %
- [x] **7.9** **Monitor row — secondary line** — Type badge + URL (no protocol, longer truncation) + response time/SSL/heartbeat + last checked
- [x] **7.10** **30-day uptime bars rendering** — read `daily_uptime_bars`, render 30 colored bars (green ≥99.5%, yellow ≥95%, red <95%, gray = no data)
- [x] **7.11** **Three-dot menu** — keep existing (edit, pause/resume, clone, copy URL, delete)
- [x] **7.12** **Empty state** — rooster emoji hero, friendlier copy, prominent CTA
- [x] **7.13** **Heartbeat created modal** — keep existing
- [x] **7.14** **JS updates** — update `filterTable()` for type filter, `sortList()` for new DOM, `tickLastChecked()` unchanged

#### ✅ Phase 7 Gate — Dashboard Rendering Tests
- [x] **7.T1** Load dashboard as Pro user with monitors — no errors
- [x] **7.T2** Status strip — aggregate stats show (uptime %, avg response, incident count)
- [x] **7.T3** Status strip — with "down" monitor, red tint applies
- [x] **7.T4** Filter pills — each pill filters correctly
- [x] **7.T5** Type filter — select "Heartbeat", only heartbeat monitors show
- [x] **7.T6** Group filter — select a group, only that group shows
- [x] **7.T7** Search — partial name match, rows filter live
- [x] **7.T8** Sort — all sort modes work (Down first, A→Z, Z→A, Lowest/Highest uptime)
- [x] **7.T9** 30-day uptime bars — render on each row, colors match data
- [x] **7.T10** Two-tier row — primary + secondary lines visually distinct
- [x] **7.T11** Bulk actions — select 2 monitors, bulk bar appears, pause/delete work
- [x] **7.T12** Three-dot menu — edit/pause/clone/copy/delete all work
- [x] **7.T13** Mobile (<768px) — rows stack, pills scroll, search full-width
- [x] **7.T14** Empty state — user with 0 monitors sees empty state with CTA

---

### Phase 8: Dashboard Backend (`pages.py`)

- [x] **8.1** Compute `avg_response_ms` across all monitors (skip heartbeat/SSL)
- [x] **8.2** Compute `overall_uptime_pct` (average of all monitors' 24h uptime)
- [x] **8.3** Count today's incidents (open + resolved) for user's monitors
- [x] **8.4** Pass `avg_response_ms`, `overall_uptime_pct`, `incidents_today` to template context

#### ✅ Phase 8 Gate — Backend Data Tests
- [x] **8.T1** Load dashboard — `avg_response_ms` is sane (not 0, not None unless no monitors) *(verified: 95ms)*
- [x] **8.T2** `overall_uptime_pct` computed correctly — cross-check against 2-3 monitors' `uptime_24h` *(verified: 36.36%)*
- [x] **8.T3** `incidents_today` count — create test incident, count increments *(verified: 2)*
- [x] **8.T4** Performance — dashboard loads <500ms locally (no extra Firestore queries beyond monitors + incidents)
- [x] **8.T5** Edge case — 0 monitors → no errors, empty state, aggregate stats show "—"

---

### Phase 9: Dashboard E2E QA

- [x] **9.1** **Full flow** — Create monitor → appears immediately → correct status/uptime/response
- [x] **9.2** **Edit flow** — Three-dot → Edit → change name → dashboard updates
- [x] **9.3** **Delete flow** — Delete → gone, aggregate stats update
- [x] **9.4** **Pause/Resume** — Pause via three-dot → paused state → resume → up/pending
- [x] **9.5** **Clone** — Clone → new copy appears
- [x] **9.6** **Free plan** — Upgrade banner at 4+ monitors, correct limits
- [x] **9.7** **Filter + Search combo** — Filter "Down" + search name → only matching down monitors
- [x] **9.8** **Mobile full flow** — Complete interaction at 375px (filter, search, menu, navigate)
- [x] **9.9** **30-day bars accuracy** — Compare bars against `daily_uptime_bars` data
- [x] **9.10** **Performance benchmark** — 10+ monitors loads <1s, no layout shift, no JS console errors

---

## Remaining Pre-Launch Tasks (Non-UI)

### 10B. GitHub OAuth 🔲
- [ ] Register GitHub OAuth App, set `GITHUB_CLIENT_ID` + `GITHUB_CLIENT_SECRET` in `.env` + Cloud Run
- [ ] Test: "Continue with GitHub" → authorize → dashboard

### 10E. Add/Edit Form — Backend Fields ✅ *(merged into Phase 4)*
> _Fully covered by Phase 4 build items 4.1–4.11 and gate tests 4.T1–4.T16. No separate work needed._

### 10G-B. Form Feature Gaps (UptimeRobot Benchmark) ✅

> **Context:** Competitive benchmark against UptimeRobot identified 3 high-ROI functional gaps in our Add/Edit forms. See `UPTIMEROBOT_BENCHMARK.md` for the full analysis.
>
> **Files to change:**
> | File | What Changes |
> |------|-------------|
> | `app/templates/add_monitor.html` | Bearer auth option, request body textarea, custom headers builder |
> | `app/templates/edit_monitor.html` | Same as above + preserve existing values |
> | `app/services/checker.py` | Bearer token header, request body + content-type, custom headers merge |
> | `app/routers/pages.py` | Parse new form fields on POST |
> | `app/models/monitor.py` | New fields: `auth_type`, `bearer_token`, `request_body`, `request_content_type`, `custom_headers` |

- [x] **10G-B.1** **Bearer/Token auth for HTTP monitors** — expand auth type dropdown to `None` / `Basic Auth` / `Bearer Token`, add token input field, wire backend (`checker.py` sends `Authorization: Bearer <token>` header). Apply to both Add + Edit forms.
- [x] **10G-B.2** **Request body for POST/PUT/PATCH** — show textarea + Content-Type selector (`application/json` / `text/plain` / `application/x-www-form-urlencoded`) when method is POST/PUT/PATCH/DELETE. Wire backend (`checker.py` sends body with content-type). Apply to both Add + Edit forms.
- [x] **10G-B.3** **Custom request headers (Pro)** — key-value builder in Advanced Settings (same pattern as JSON assertions builder). Store as `custom_headers: [{key, value}, ...]` on monitor doc. Checker merges into headers dict. Pro-gated with upgrade CTA for Free users. Apply to both Add + Edit forms.

#### ✅ 10G-B Gate Tests
- [x] **10G-B.T1** Create HTTP monitor with Bearer auth → checker sends `Authorization: Bearer <token>` header → monitor works
- [x] **10G-B.T2** Create HTTP monitor with POST method + JSON body → checker sends body with correct Content-Type → monitor works
- [x] **10G-B.T3** Create HTTP monitor with custom headers (Pro) → checker sends headers → monitor works
- [x] **10G-B.T4** Edit existing monitor, add Bearer auth → save → re-edit → token value preserved
- [x] **10G-B.T5** Edit existing monitor, add request body → save → re-edit → body + content-type preserved
- [x] **10G-B.T6** Free user sees custom headers section as Pro-gated (greyed out + upgrade CTA)

### 10H. UI/UX Polish Pass (Sonnet) ✅

> **Context:** Open-ended UI/UX polish pass by Sonnet 4.6 — fresh eyes on dashboard, monitor detail, and edit pages. Goal: crisp, professional, perfectly organized UX for indie devs. Should feel perfectly natural to navigate both functionally and aesthetically.
>
> **Scope:** Dashboard (`dashboard.html`, `dashboard_base.html`), Monitor Detail (`monitor_detail.html`), Edit Monitor (`edit_monitor.html`), Add Monitor (`add_monitor.html`), and `style.css`. No new features — polish only.
>
> **Rules:**
> - Stay within existing tech stack (Jinja2 SSR, vanilla JS, unified `style.css`)
> - No new CSS frameworks, no JS frameworks
> - Respect existing CSS class prefixes (`d-` dashboard, `md-` detail, `mf-` forms)
> - Respect design system tokens (colors, radii, shadows, fonts)
> - Mobile responsive — test at 768px and 375px breakpoints
> - Don't break any existing functionality

#### Polish Areas (open-ended — use best judgment)
- [x] **10H.1** **Visual hierarchy & spacing** — consistent rhythm throughout; section breaks, breathing room, font weights all tightened up
- [x] **10H.2** **Typography & readability** — mono font on URLs/IDs/times, `md-url-static`, `mf-mono-textarea`; improved contrast and label hierarchy
- [x] **10H.3** **Interactive states** — btn `transform: scale(0.97)` on active; 150ms transitions on buttons, cards, sidebar links; focus ring on search input; hover shadow on md-card
- [x] **10H.4** **Dashboard card polish** — no-layout-shift hover fix (`border-left: 3px solid transparent` base), status-based accent colors (`status-is-down/warn/paused`), added to template loop
- [x] **10H.5** **Monitor detail page flow** — ping URL bar refactored to semantic classes; back link SVG arrow with slide-on-hover; action button copy cleaned (emoji removed); md-name overflow ellipsis
- [x] **10H.6** **Form UX** — all inline styles replaced with CSS classes; builder-row, mf-field-group-mt, mf-input-sm, mf-disabled-wrap, mf-builder-add-btn, builder-separator; JS addXxx() functions use className not style.cssText
- [x] **10H.7** **Navigation & wayfinding** — sidebar active link `box-shadow: inset 2px 0 0 var(--brand)` + font-weight 600; sidebar brand border-bottom; mf-footer sidebar-width token fixed (was 240px→200px)
- [x] **10H.8** **Empty states & edge cases** — no regressions; existing empty state markup preserved
- [x] **10H.9** **Micro-interactions & feedback** — flash messages redesigned with flex + left-border accent; type badges use CSS classes (mf-type-badge--http/heartbeat/json/ssl); monitor count inline→.monitors-count; search bar inline→CSS classes
- [x] **10H.10** **Mobile responsiveness** — no layout-shift on card hover; sidebar-width token correct; mf-footer offset correct

#### ✅ 10H Gate Tests
- [x] **10H.T1** Dashboard loads with all monitors displaying correctly — no visual regressions
- [x] **10H.T2** Monitor detail page displays all sections (stats, chart, incidents) — no layout breaks
- [x] **10H.T3** Add/Edit monitor forms submit correctly — all monitor types (HTTP, JSON/API, Heartbeat, SSL)
- [x] **10H.T4** Mobile viewport (375px) — all pages navigable, no horizontal scroll, touch targets adequate
- [x] **10H.T5** No console errors on any page (dashboard, detail, add, edit)

### 10H-EXT. API Docs Inline Style Cleanup ✅
> Extension of the 10H polish pass — applied same inline→CSS discipline to `api_docs.html`

- [x] **10H-EXT.1** Nav icon spans — `style="background:#xxx;display:inline-block"` → `class="nav-icon nav-icon--{type}"` (4 instances)
- [x] **10H-EXT.2** Muted helper `<p>` tags — `style="color:var(--muted);..."` → `class="api-helper-text"` (4 instances + rate limits footer note)
- [x] **10H-EXT.3** Section intro `<p>` — `class="api-section-intro" style="..."` → inline style removed, class handles all styling
- [x] **10H-EXT.4** Method badge spacing — removed `style="margin-left:4px"` on second badge; added `+ .method-badge { margin-left: 4px }` CSS rule
- [x] **10H-EXT.5** HEAD badge — removed `style="background:#6b7280;..."` → `class="method-badge method-head"`
- [x] **10H-EXT.6** Field reference table section headers — 6 `<tr><td style="...">` → `<tr class="param-table-section-header param-table-section-header--{variant}"><td colspan="3">` with CSS doing all background/typography
- [x] **10H-EXT.7** New CSS utilities added: `nav-icon--*`, `param-table-section-header--*`, `api-helper-text`, `api-helper-text--mt-lg`, `api-section-intro`, `method-head`
- [x] **10H-EXT.8** Zero inline styles remain in `api_docs.html` (verified with grep)

### 10F. Pro Upsell Polish ✅
- [x] Check interval badge on dashboard rows: `⏱ 5 min` for Free (indigo, with tooltip "Upgrade for 60s →") / actual interval for Pro
- [x] Pro upsell footer bar below monitor list for Free users: "Upgrade to Pro — get 60s checks, 250 monitors, Slack + webhook alerts, and SMS." + Upgrade CTA button
- [x] Alert email footer for Free — covered by Pro footer bar above (same placement, same CTA)
- [x] Gate Slack/webhook inputs in Add + Edit forms for Free users — already done in Phase 10H form polish (mf-notify-channel-locked + upgrade link)

### 11B. Activity Log / Event Timeline ✅
- [x] **Incident events sub-collection** — `incidents/{id}/events/{auto_id}` → `{type, timestamp, metadata}`
  - Event types: `detected`, `alert_email_sent`, `alert_slack_sent`, `alert_sms_sent`, `alert_webhook_sent`, `resolved`, `recovery_*_sent/failed`
- [x] **Log events in checker + alert service** — write events on detection, each alert, resolve, recovery
- [x] **Timeline on incident detail** — chronological vertical timeline, each event: dot + text + timestamp; graceful fallback for pre-log incidents
- [x] **Alert delivery logging** — `send_down_alert`/`send_recovery_alert` return `dict[str, bool]`; checker logs per-channel `alert_{channel}_sent/failed` events

### 11C. Hardening ✅
- [x] Custom 404 page (link to dashboard + home)
- [x] Custom 500 page (link to dashboard + home)
- [x] Meta tags (title, description, OG title/desc/image, Twitter card) in `base.html` + `dashboard_base.html`
- [x] Favicon: `favicon.svg` (indigo rounded square) + `favicon-32.png` + `apple-touch-icon.png` (180x180); linked in both base templates
- [x] Input validation audit: signup email format validated server-side; URL required/prefix check on add-monitor; API uses Pydantic `HttpUrl`; status/monitor_type filters clamped in API
- [x] Mobile viewport: `<meta name="viewport">` already present in both base templates; no regressions introduced

### 11D. User Timezone Setting ✅

> **Goal:** All timestamps shown in the UI (incidents, checks, monitor detail, maintenance windows) currently display in UTC. Users should be able to set their preferred timezone in Account Settings and have all timestamps rendered in that timezone throughout the app.

**Scope:** Settings UI + backend save + Jinja2 filter. No JS framework, no client-side detection.

- [x] **11D.1** `POST /settings/timezone` route — validates IANA tz with `pytz.timezone()`; saves to Firestore user doc; rejects unknowns with flash error
- [x] **11D.2** Settings UI — timezone `<select>` with ~40 IANA zones grouped by region (`Americas`, `Europe`, `Africa & Middle East`, `Asia & Pacific`); current value pre-selected
- [x] **11D.3** Jinja2 `as_tz` filter registered in `main.py` for both template sets; handles Firestore `DatetimeWithNanoseconds`, naive datetimes; falls back to UTC on bad tz; `pytz==2024.2` added to `requirements.txt`
- [x] **11D.4** Filter applied: `incidents.html` (started_at), `incident_detail.html` (started_at, resolved_at, all timeline event timestamps), `monitor_detail.html` (last_checked, incident started_at)
- [x] **11D.5** Maintenance windows already labelled "times in UTC" in both `add_monitor.html` and `edit_monitor.html` — no change needed

#### 11D Gate Tests
- [x] **11D.T1** `as_tz` filter verified: UTC 16:00 → `America/New_York` = `12:00` ✅
- [x] **11D.T2** `as_tz` filter verified: UTC 16:00 → `Australia/Sydney` = `03:00` ✅
- [x] **11D.T3** Invalid tz → filter falls back to UTC format, no crash ✅
- [x] **11D.T4** `user.get('timezone', 'UTC')` default in all templates — new users default to UTC ✅

### 11E. API & API Docs QA ✅

> **Goal:** The public API and its documentation are a first-class product surface. Every endpoint must work exactly as documented, every example must be copy-paste-runnable, every field reference must match reality, and the Swagger playground must stay in sync. This is a dedicated pass to verify consistency, correctness, and completeness end-to-end.

#### API Backend — Functional Tests (FastAPI TestClient)
- [x] **11E.1** Auth — missing `X-API-Key` header → 401 + clear error message *(fixed: `auto_error=False` + null check)*
- [x] **11E.2** Auth — invalid/revoked key → 401
- [x] **11E.3** Auth — valid key → 200 on `GET /api/v1/monitors`
- [x] **11E.4** List monitors — returns all monitors for authenticated user, `{data: [...], error: null, meta: {total: N}}`
- [x] **11E.5** Get single monitor — valid ID → 200 with full monitor object; invalid ID → 404
- [x] **11E.6** Create HTTP monitor — all fields accepted, response includes new fields (`http_method`, `follow_redirects`, `basic_auth_user`, `basic_auth_pass`), status 201
- [x] **11E.7** Create JSON/API monitor — `json_assertions` + `auth_header` stored and returned, status 201
- [x] **11E.8** Create Heartbeat monitor — returns `ping_url`, `heartbeat_interval`, `heartbeat_grace_period`, status 201
- [x] **11E.9** Create SSL monitor — `ssl_domain` + `ssl_expiry_threshold_days` stored and returned, status 201
- [x] **11E.10** Create monitor — plan gating: Free user at 5 monitors → 403; basic auth fields silently emptied for Free
- [x] **11E.11** Create monitor — validation: missing `name` → 422; invalid `monitor_type` → 422 *(fixed: `Literal` type)*
- [x] **11E.12** Update monitor via PATCH — `PATCH /api/v1/monitors/{id}` → 200 *(fixed: added `@router.patch` alias)*
- [x] **11E.15** Delete monitor — 200 + monitor gone; delete again → 404
- [x] **11E.16** Check history — `GET /api/v1/monitors/{id}/checks` → returns recent checks with `{data: [...], meta: {total}}`
- [x] **11E.17** List incidents — `GET /api/v1/incidents` → `{data: [...], error: null, meta: {total}}`
- [x] **11E.19** Response shape consistency — every endpoint returns `{data, error}` or `{data, error, meta}` — no exceptions

#### API Docs — Content Accuracy (`api_docs.html`)
- [x] **11E.20** Auth section — instructions match actual header name (`X-API-Key`), key format (`sr_...`), error responses
- [x] **11E.21** Client setup — curl/Python/JS snippets are copy-paste-runnable (correct base URL, headers)
- [x] **11E.22** HTTP Create — param table matches `ApiCreateMonitor` schema exactly (all fields, types, defaults, required/optional)
- [x] **11E.23** HTTP Create — response shape JSON matches actual `POST /api/v1/monitors` response (field names, types, order)
- [x] **11E.24** HTTP Update — both `PUT` and `PATCH` documented; param table matches `ApiUpdateMonitor` schema exactly
- [x] **11E.25** JSON/API Create — param table includes `json_assertions`, `auth_header`, correct types
- [x] **11E.26** JSON/API Update — param table matches actual accepted fields
- [x] **11E.27** Heartbeat Create — param table includes `heartbeat_interval`, `heartbeat_grace_period`
- [x] **11E.28** Heartbeat Update — param table matches
- [x] **11E.29** SSL Create — param table includes `ssl_domain`, `ssl_expiry_threshold_days`
- [x] **11E.30** SSL Update — param table matches
- [x] **11E.31** List All Monitors — response shape matches actual response (array of monitor objects with `meta.total`)
- [x] **11E.32** Get Single Monitor — response shape matches actual response
- [x] **11E.33** Check History — param table (query params like `limit`) matches, response shape matches
- [x] **11E.34** Delete Monitor — documented response matches actual
- [x] **11E.35** Incidents — List + Get response shapes match actual
- [x] **11E.36** Field reference table — every field listed exists in actual responses; types correct
- [x] **11E.37** Field reference — "HTTP Only" section lists `http_method`, `follow_redirects`, `basic_auth_user`, `basic_auth_pass`, `bearer_token`, `request_body`, `request_content_type`, `custom_headers`
- [x] **11E.38** Plan Limits section — Free/Pro limits match actual gating in code
- [x] **11E.39** Rate Limits section — documented limits match actual implementation
- [x] **11E.48** Webhook Payloads section — documented payload shape matches what `alerts.py` actually sends
- [x] **11E.50** Every field in `ApiCreateMonitor` Pydantic schema appears in the corresponding docs param table
- [x] **11E.51** Every field in `ApiUpdateMonitor` Pydantic schema appears in the corresponding docs param table
- [x] **11E.52** Every field returned by `_serialize_monitor()` appears in the field reference table
- [x] **11E.53** No "ghost fields" — every documented field is actually parsed, stored, and returned by the backend
- [x] **11E.54** Pro-gated fields are consistently marked "(Pro)" in both param tables and field reference

**Bugs fixed:** `auto_error=False` (401 on missing key), `Literal` type on `monitor_type` (422 on bad type), `@router.patch` alias (PATCH → 200), stray GPT comment removed from `api_docs.html`, `.method-patch` CSS badge added, all 4 update endpoint headers show `PUT / PATCH`.

**Test script:** `scripts/qa_api_v1.py` — 34/34 pass.

### 11F. Incident Detail — Request/Response Panel ✅

> **Goal:** Show the *exact* request sent and response received when a monitor first went down — right on the incident detail page. Inspired by UptimeRobot's request/response section. Gives users instant "why did it fail?" context without hunting through check history.

**Scope — what to show vs. what to store:**

| Panel | Source | Notes |
|-------|--------|-------|
| **Request** | Already known — method, URL, keyword/assertion config | No new storage needed |
| **Response** | `status_code`, `response_ms` already stored on incident | Add `response_headers` capture on failure |
| **Failure reason** | `error_message` already stored | Display prominently |

**Build items:**
- [x] **11F.1** `checker.py` — capture `response_headers` dict on HTTP/JSON checks; `create_incident()` stores `failure_response_headers` + `failure_error_message` on the Firestore doc
- [x] **11F.2** `incident_detail.html` — Request panel: method badge + URL (clickable), keyword/assertion config, auth type indicator (masked), custom headers count; heartbeat/SSL variants
- [x] **11F.3** `incident_detail.html` — Response panel: status code pill (colored 2xx/4xx/5xx), response time, collapsible `failure_response_headers` table, error message; heartbeat/SSL variants
- [x] **11F.4** CSS — `.id-rr-row`, `.id-rr-panel`, `.id-rr-method--*`, `.id-rr-status-pill`, `.id-rr-details` — side-by-side on desktop, stacked on mobile
- [x] **11F.5** Graceful fallback — `{% if resp_headers %}` guard on header table; Jinja `mtype` branch renders appropriate content for all monitor types without blank cards

**Gate tests:**
- [x] **11F.T1** HTTP incident — Request panel shows correct method + URL; Response panel shows status code + response time
- [x] **11F.T2** HTTP incident with keyword fail — keyword shown in Request panel
- [x] **11F.T3** Heartbeat incident — panels show "Missed ping" context instead of HTTP fields
- [x] **11F.T4** SSL incident — panels show domain + expiry threshold, no HTTP fields
- [x] **11F.T5** Old incidents (no `failure_response_headers`) — page renders, header table simply omitted
- [x] **11F.T6** Response headers panel — collapsible `<details>`, stacks on mobile via `@media (max-width: 640px)`

### 11G. Monitor → Incident Navigation Bridge 🔲

> **Goal:** Make the connection between monitors and incidents obvious and fast. Right now a user has to leave the monitor detail page and hunt through the global incidents list. This phase adds clear navigation bridges in both directions.

**Build items:**
- [ ] **11G.1** Monitor detail page — "Recent Incidents" section already exists; ensure each incident row links directly to `/incidents/{id}` (verify, don't duplicate)
- [ ] **11G.2** Monitor detail page — add a visible "View all incidents for this monitor" link that filters the incidents list page to that monitor (e.g. `/incidents?monitor_id={id}`)
- [ ] **11G.3** Incidents list page — support `?monitor_id=` query param as a pre-applied filter; show "Filtered by: [Monitor Name] ×" badge when active
- [ ] **11G.4** Incident detail page — "Back to incidents" link already exists; add a second breadcrumb link: "↗ View monitor" that goes to `/monitors/{id}` (already in template as "View monitor" — verify it's prominent enough)
- [ ] **11G.5** Dashboard monitor card — ensure the existing downtime/incident count shown on cards is clickable, linking to the filtered incidents list for that monitor

**Gate tests:**
- [ ] **11G.T1** From monitor detail → click incident row → lands on correct incident detail page
- [ ] **11G.T2** From monitor detail → click "View all incidents" → incidents list pre-filtered to that monitor
- [ ] **11G.T3** Filtered incidents list shows filter badge and clearing it removes the filter
- [ ] **11G.T4** From incident detail → click "View monitor" → lands on correct monitor detail page
- [ ] **11G.T5** Dashboard card incident count is clickable and links to filtered incidents list

### 11H. Replace Emoji with Inline SVG Icons 🔲

> **Goal:** Remove all emoji used as UI icons (🌐 💓 📄 🔒 ♥ 📧 💬 🔗) and replace with clean inline SVG. Emoji render inconsistently across OS/browser (especially on Windows), look unprofessional in a product context, and clash with the design system. Brand icons (Slack, GitHub) get their actual brand SVG mark, not a chat bubble.

**Scope — every emoji icon in the app:**

| Location | Emoji | Replace with |
|----------|-------|-------------|
| Add/Edit monitor type selector | 🌐 HTTP, 💓 Heartbeat, 📄 JSON/API, 🔒 SSL | Clean inline SVG per type |
| Add/Edit monitor — notification channels | 📧 Email, 💬 Slack, 🔗 Webhook | SVG: envelope, Slack brand mark, chain-link |
| Monitor detail — type label | ♥ Heartbeat, { } JSON/API, 🔒 SSL | SVG inline (same as type selector) |
| Monitor detail — incident table cause | ♥ (heartbeat badge) | SVG heart/pulse icon |
| Monitor detail — config section titles | 🔒 Certificate Details, { } Assertion Rules | SVG |
| Incident detail — type field | ♥ Heartbeat, { } JSON/API, 🔒 SSL | SVG |
| Incidents list — cause column | ♥ (heartbeat badge) | SVG |

**Build items:**
- [ ] **11H.1** Define reusable SVG snippets for: HTTP (globe/link), Heartbeat (pulse/activity), JSON/API (curly-braces or `{}`), SSL (lock), Email (envelope), Slack (brand hash), Webhook (chain link)
- [ ] **11H.2** `add_monitor.html` — swap type selector emoji + notification channel emoji
- [ ] **11H.3** `edit_monitor.html` — same swaps as add form
- [ ] **11H.4** `monitor_detail.html` — type label, incident cause badge, config section titles
- [ ] **11H.5** `incident_detail.html` + `incidents.html` — type field and cause column

**Gate tests:**
- [ ] **11H.T1** Add monitor form — all 4 type buttons show SVG icons, no emoji
- [ ] **11H.T2** Notification channels — Email/Slack/Webhook show proper SVG, no emoji
- [ ] **11H.T3** Monitor detail — type label and incident cause use SVG
- [ ] **11H.T4** Incident detail + incidents list — no emoji anywhere visible
- [ ] **11H.T5** Spot-check on a Windows user-agent (or Chrome/Firefox) — icons render correctly

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

## Phase 10: Checker Scale Hardening

> **Context:** External architecture review (see `app/screenshots/gptfeedbackapidocs.txt`) identified 7 issues in `checker.py`. Three are already fixed (concurrent checks, semaphore, batch writes — commits `779acc3`, `de0e88b`). Three more are high-ROI fixes worth doing before launch. The remaining items are deferred to post-launch (see Post-Launch Backlog → Scale Architecture).
>
> **Files to change:**
> | File | What Changes |
> |------|-------------|
> | `app/services/checker.py` | Shared httpx client, consolidated updates, retry jitter |
>
> **What was already fixed (this session):**
> - ✅ Sequential → concurrent checks via `asyncio.gather` (commit `779acc3`)
> - ✅ `asyncio.Semaphore(50)` for connection limiting (commit `de0e88b`)
> - ✅ `create_checks_batch()` for Firestore batch writes (commit `de0e88b`)
> - ✅ SSL grabs run concurrently in Phase 2 via `run_in_executor` (commit `de0e88b`)
> - ✅ Cloud Scheduler `attemptDeadline` bumped from 60s → 180s (commit `779acc3`)
> - ✅ Tested locally: 10 real monitors in 7.3s, 200 simulated in 3.5s, 1000 simulated in 29.4s

---

### 10.1 — Shared `httpx.AsyncClient` (Connection Pooling)

> **Problem:** `check_url()` and `check_json_api()` each create a fresh `httpx.AsyncClient()` per call via `async with httpx.AsyncClient() as client:`. This means every single monitor check opens a new TCP connection (+ TLS handshake for HTTPS), throwing away connection reuse entirely. For a monitoring app that hits the same domains repeatedly, this is the single highest-impact performance fix.
>
> **Impact:** Fewer TCP/TLS handshakes → lower latency per check, reduced ephemeral port pressure, better throughput under load, fewer file descriptor issues at scale.

- [x] **10.1.1** Create a module-level shared `httpx.AsyncClient` instance in `checker.py`
  - Use `httpx.AsyncClient(limits=httpx.Limits(max_connections=100, max_keepalive_connections=50), timeout=httpx.Timeout(30.0))` as defaults
  - Store as `_shared_client: httpx.AsyncClient | None = None`
  - Add `_get_client()` async helper that lazily creates the client on first use (avoids creating at import time when no event loop exists)
  - Client must be created inside an async context — cannot use module-level `httpx.AsyncClient()` directly
- [x] **10.1.2** Refactor `check_url()` to accept an optional `client` parameter
  - If `client` is provided, use it directly (no `async with`)
  - If `client` is None, fall back to creating a one-off client (backward compatibility)
  - Remove the `async with httpx.AsyncClient() as client:` wrapper when shared client is used
- [x] **10.1.3** Refactor `check_json_api()` to accept an optional `client` parameter (same pattern as 10.1.2)
- [x] **10.1.4** Update `check_url_with_retry()` to get the shared client once and pass it to both `check_url()` calls (initial + retry)
- [x] **10.1.5** Update `_check_single_monitor_inner()` to get the shared client and pass it through to `check_url_with_retry()` / `check_json_api()`
- [x] **10.1.6** Add `async def close_client()` function that closes the shared client gracefully — call from FastAPI shutdown event or end of `run_checks()`

#### ✅ Phase 10.1 Gate — Shared Client Tests
- [x] **10.1.T1** Server starts without errors — no import-time event loop issues
- [x] **10.1.T2** Run `POST /cron/check` locally — all monitors checked successfully (same results as before)
- [x] **10.1.T3** Verify connection reuse — add a `logger.info` in `_get_client()` and confirm it's only called once per `run_checks()` cycle, not once per monitor
- [x] **10.1.T4** Run checks twice back-to-back — client reused across cycles (no "creating new client" log on second run)
- [x] **10.1.T5** Verify `check_url()` still works standalone (e.g., from API endpoint or tests) by calling without `client` param — fallback client created

---

### 10.2 — Consolidate Per-Monitor Firestore Updates

> **Problem:** During Phase 3 (result processing), a single monitor can trigger `update_monitor()` up to 3 times per cycle:
> 1. SSL fields update (line ~635) — for SSL monitors with cert data
> 2. Main monitor stats update (line ~685) — status, uptime, bars, response time
> 3. SSL alert tracking update (line ~740) — `ssl_expiry_alerted_days` field
>
> Each `update_monitor()` call is a separate Firestore write operation. At 1000 monitors, this means up to 3000 writes per cycle instead of 1000.
>
> **Fix:** Build a single `monitor_updates` dict throughout the processing loop and call `update_monitor()` exactly once per monitor at the end.

- [x] **10.2.1** Move SSL cert field updates (currently separate `update_monitor()` for SSL monitors ~line 635) into the main `monitor_updates` dict
  - For SSL monitors: merge `ssl_expiry`, `ssl_issuer`, `ssl_expiry_days` into `monitor_updates` instead of a separate write
- [x] **10.2.2** Move SSL alert tracking update (currently separate `update_monitor()` ~line 740) into the main `monitor_updates` dict
  - Set `monitor_updates["ssl_expiry_alerted_days"] = threshold_days` instead of calling `update_monitor()` separately
  - Same for HTTP/JSON SSL expiry alerts (~line 730)
- [x] **10.2.3** Verify that the single `update_monitor(db, monitor["id"], monitor_updates)` call (already exists ~line 685) now contains ALL fields — no other `update_monitor()` calls should exist inside the per-monitor loop
- [x] **10.2.4** Add a log line counting total Firestore writes per cycle: `logger.info(f"[checker] Phase 3: {len(due_monitors)} monitor updates, {len(check_batch)} check batch writes")`

#### ✅ Phase 10.2 Gate — Consolidated Write Tests
- [x] **10.2.T1** Run `POST /cron/check` — all monitors update correctly (status, uptime bars, SSL fields all present)
- [x] **10.2.T2** Grep `checker.py` for `update_monitor` — confirm only ONE call per monitor inside the processing loop (plus the batch write at the end)
- [x] **10.2.T3** SSL monitor check — verify `ssl_expiry`, `ssl_issuer`, `ssl_expiry_days` all written in single update (check Firestore doc)
- [x] **10.2.T4** HTTP monitor with SSL (HTTPS URL) — verify `ssl_expiry` fields written in same update as status/uptime

---

### 10.3 — Retry Jitter (Prevent Retry Storms)

> **Problem:** When a check fails, `check_url_with_retry()` does `await asyncio.sleep(5)` before retrying. This is a fixed 5-second delay. If many monitors fail simultaneously (e.g., a cloud provider outage), all retries fire at exactly the same moment 5 seconds later, creating a synchronized burst ("retry storm") that can saturate the semaphore and delay all other checks.
>
> **Fix:** Add random jitter to the retry delay (2–8 seconds instead of fixed 5). This spreads retries across a time window, reducing peak concurrency pressure during outages.

- [x] **10.3.1** Import `random` at the top of `checker.py`
- [x] **10.3.2** In `check_url_with_retry()`, replace `await asyncio.sleep(5)` with `await asyncio.sleep(random.uniform(2, 8))`
- [x] **10.3.3** Add a comment explaining the jitter: `# Jitter retry delay to prevent synchronized retry storms during outages`

#### ✅ Phase 10.3 Gate — Retry Jitter Tests
- [x] **10.3.T1** Grep for `asyncio.sleep(5)` in checker.py — should NOT exist (replaced with `random.uniform`)
- [x] **10.3.T2** Grep for `random.uniform` in checker.py — should exist in `check_url_with_retry()`
- [x] **10.3.T3** Run `POST /cron/check` — all monitors still check successfully (jitter doesn't break retry logic)

---

### 10.4 — Instrumentation (Prove the Fixes Worked)

> **Problem:** We're making 3 performance changes (shared client, consolidated writes, retry jitter) but have no before/after metrics to prove they actually helped. Without instrumentation, we're improving blind.
>
> **Approach:** Add structured logging at the end of each `run_checks()` cycle that emits a single summary log line with all key metrics. This lets us compare Cloud Run logs before and after deploying Phase 10 changes. No external monitoring infra needed — just `logger.info` with parseable data.
>
> **What to track:**
> | Metric | Why | How |
> |--------|-----|-----|
> | `total_duration_s` | Overall cron cycle time | `time.monotonic()` start-to-finish |
> | `checks_per_sec` | Throughput | `due_count / phase2_duration` |
> | `phase2_duration_s` | Network check time (shared client impact) | Already timed |
> | `phase3_duration_s` | Write + alert time (consolidation impact) | Already timed |
> | `p50_check_ms` / `p95_check_ms` | Per-check latency distribution | Collect `response_ms` from all results, compute percentiles |
> | `retries_triggered` | How often retry fires (jitter impact) | Counter incremented in `check_url_with_retry()` |
> | `firestore_writes` | Total DB writes per cycle | Count `update_monitor` calls + batch write |
> | `writes_per_monitor` | Avg writes per monitor (consolidation proof) | `firestore_writes / due_count` |
> | `errors_by_type` | Down monitors grouped by type | Count from results |

- [x] **10.4.1** Add a `retries_triggered` counter to `check_url_with_retry()` — return it alongside the result dict (add `"retried": True/False` key to result)
- [x] **10.4.2** Collect per-check `response_ms` values during Phase 3 result processing — build a list for percentile calculation
- [x] **10.4.3** Add a `_percentile(sorted_list, pct)` helper function (simple: `sorted_list[int(len * pct)]`)
- [x] **10.4.4** Count `firestore_writes` — initialize counter at 0, increment for each `update_monitor()` call and for the batch write
- [x] **10.4.5** Count `errors_by_type` — dict tracking `{monitor_type: down_count}` during result processing
- [x] **10.4.6** Emit a single structured summary log at the end of `run_checks()`:
  ```
  logger.info(f"[checker] CYCLE COMPLETE | total={total_s:.1f}s | due={due_count} | checks/sec={cps:.1f} | "
              f"phase2={p2_s:.1f}s | phase3={p3_s:.1f}s | p50={p50}ms | p95={p95}ms | "
              f"retries={retry_count} | fw_writes={fw_writes} | writes/mon={wpm:.1f} | "
              f"up={up} | down={down} | skipped={skipped} | errors_by_type={errors_by_type}")
  ```
- [x] **10.4.7** Add a `total_duration_s` timer wrapping the entire `run_checks()` function (Phase 1 + 2 + 3)

#### ✅ Phase 10.4 Gate — Instrumentation Tests
- [x] **10.4.T1** Run `POST /cron/check` locally — look for `CYCLE COMPLETE` log line in terminal output
- [x] **10.4.T2** Verify all metrics are present and non-null in the log line (total, due, checks/sec, p50, p95, retries, fw_writes, writes/mon)
- [x] **10.4.T3** `p50` and `p95` are sane values (>0ms, <30000ms) — not 0 or None
- [x] **10.4.T4** `writes/mon` should be ~1.0 after 10.2 consolidation (was ~2-3 before)
- [x] **10.4.T5** `retries` count is an integer ≥0

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

### Scale Architecture (deferred — revisit at trigger points)
> Source: GPT architecture review (`app/screenshots/gptfeedbackapidocs.txt`). These are real improvements, but premature before real user volume.

- [ ] **`due_at` query model** — Replace full-table `get_all_monitors()` scan with Firestore `where("due_at", "<=", now)` query. Add `due_at` field to monitor docs, update after each check. Eliminates Python-side filtering. **Trigger: >5K monitors or cron runs exceeding 60s.**
- [ ] **Separate notifications pipeline** — Decouple alerting from checker loop. Checker emits events (`monitor.down`, `monitor.up`, `ssl.expiring`), push to Cloud Tasks or Pub/Sub, separate worker sends emails/Slack/webhooks. Prevents slow webhook targets from back-pressuring checks. **Trigger: alert delivery latency >2s or webhook hangs observed.**
- [ ] **Move analytics off monitor doc** — Keep `daily_uptime_bars` / `hourly_uptime_bars` on monitor doc for dashboard reads (zero-query pattern), but compute long-term analytics from `checks` collection separately. Reduces monitor doc churn. **Trigger: monitor docs exceeding 100KB or Firestore write contention.**
- [ ] **Sharded workers** — Replace single cron → single `run_checks()` with partitioned workers. Scheduler assigns monitor shards to multiple Cloud Run instances via Cloud Tasks. **Trigger: >10K monitors or single-instance Cloud Run hitting memory/CPU limits.**
- [ ] **Retry from second region** — Instead of "same worker sleeps and retries," confirm downtime from a second region/worker before alerting. Reduces false positives from localized network issues. **Trigger: false positive complaints from users.**

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
| 5 | Phase 5: Form E2E QA | ✅ |
| 6 | Phase 6: Dashboard CSS | ✅ |
| 7 | Phase 7: Dashboard template + JS | ✅ |
| 8 | Phase 8: Dashboard backend | ✅ |
| 9 | Phase 9: Dashboard E2E QA | ✅ |
| 10 | Phase 10: Checker Scale Hardening | ✅ |
| 11 | 10B: GitHub OAuth | 🔲 |
| 12 | 10G-B: Form Feature Gaps (Bearer auth, request body, custom headers) | ✅ |
| 13 | 10H: UI/UX Polish Pass (Sonnet) | ✅ |
| 14 | 10H-EXT: API Docs Inline Style Cleanup | ✅ |
| 15 | 10F: Pro upsell polish | ✅ |
| 16 | 11B: Activity log | ✅ |
| 17 | 11C: Hardening | ✅ |
| 18 | 11D: User Timezone Setting | ✅ |
| 19 | 11E: API & API Docs QA | 🔲 |
| 18 | 11D: Admin dashboard | 🔲 |
| 19 | Day 12: Testing & launch | 🔲 |

**Work through Phases 1–9 sequentially. Run every Gate test before moving to the next Phase. Do not skip ahead.**

### Total Remaining Checkboxes
- Phase 1: ~~12~~ **0** ✅
- Phase 2: ~~25~~ **5** (5 browser-only gate tests remain)
- Phase 3: ~~13~~ **0** ✅
- Phase 4: ~~27~~ **0** ✅
- Phase 5: ~~11~~ **1** (1 browser-only mobile spot-check remains)
- Phase 6: ~~13~~ **0** ✅
- Phase 7: ~~28~~ **0** ✅
- Phase 8: ~~9~~ **0** ✅
- Phase 9: 10 E2E = **10**
- Phase 10: 13 build + 10 gate + 7 build + 5 gate = **35**
- Non-UI tasks: ~25 + 54 (11E) = **~79**
- **Grand total: ~130 checkboxes**

---

## Reference Documents (archived — content merged here)
- `COMPETITIVE_AUDIT.md` — full UptimeRobot page-by-page comparison
- `UPTIMEROBOT_BENCHMARK.md` — UptimeRobot form benchmark: feature gap analysis + action plan for 10G-B
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
