# StatusRooster Build Tracker

**Start:** Feb 25, 2026 · **Target Launch:** Mar 7, 2026
**Current Day: 10 (in progress)** · **Phase 3: Hardening & Launch**

---

## 🧭 Vision & Positioning

**One-liner:** StatusRooster monitors your websites, APIs, and cron jobs — and alerts you instantly when something breaks. Built for indie developers and small SaaS teams.

**Who we serve:** Solo developers, indie hackers, SaaS founders, freelancers, and small teams (1-5 people). NOT enterprises. NOT DevOps teams with Datadog budgets.

**Why we win:**
1. **Positioning** — "Monitoring for indie SaaS" resonate| 3. Hardening & Launch | 10-12 | 🟡 In progress |
| 4. Post-Launch | 13+ | 🔲 Not started |

**Day 10 in progress** · **Target launch: Day 12 (Mar 7)**otionally. Users identify with it. UptimeRobot is generic. Datadog is enterprise. Better Stack is VC-funded. We're for *them*.
2. **Simplicity** — Sign up → add URL → done. No 15-tab settings page. No team hierarchy. No enterprise SSO. Every feature is inline, not buried.
3. **Fair pricing** — Free tier that actually works (5 monitors, email alerts, status pages, API access, badges). Pro at $9/mo — not $29/mo for webhooks like UptimeRobot.
4. **Three monitoring types** — Website uptime + API validation + cron/heartbeat monitoring, bundled in one product at indie prices. Competitors charge separately or don't offer all three.
5. **Status pages as distribution** — Every public status page says "Powered by StatusRooster." Viral growth loop that competitors paywall.
6. **Modern stack** — GCP Cloud Run, Firestore, serverless. No legacy infra. We move fast.

**What we are NOT building:**
- ❌ Mobile apps (months of work, zero ROI now)
- ❌ Enterprise SSO / SAML
- ❌ Team management / role-based access (until $10k+ MRR)
- ❌ On-call rotation / PagerDuty clone
- ❌ Full observability suite (logs, traces, metrics)
- ❌ 15+ integrations — Email + Slack + Webhook covers 95% of indie needs

**Revenue target:** $5k-$30k/mo within 12-18 months. ~400 Pro customers at $9-$19/mo.

**Competitive advantages over UptimeRobot (validated by audit, March 2, 2026):**
- 🟢 Integrations inline (not buried behind paywall tabs)
- 🟢 Webhooks at $9/mo (UptimeRobot: $29/mo)
- 🟢 Full public API with docs on Free tier
- 🟢 Uptime badges (shields.io-style SVGs)
- 🟢 Column-customizable data table dashboard
- 🟢 Keyword/content checking with AND/OR operators
- 🟢 Status pages on Free tier

**See also:**
- `COMPETITIVE_AUDIT.md` — full page-by-page UptimeRobot comparison with screenshots
- `ACTION_PLAN.md` — original Day 10 workstream plan (superseded by this tracker)

### Pricing
| | Free | Pro $9/mo |
|---|---|---|
| Monitors | 5 | 250 |
| Check interval | 5 min | 60s |
| Alerts | Email | Email + Slack + SMS |
| Status pages | 1 | 10 |
| API access | ✅ | ✅ |
| Webhooks | — | ✅ |
| Maintenance windows | — | ✅ |
| Uptime badges | ✅ | ✅ |

### Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | Python / FastAPI, Jinja2 templates (SSR) |
| Database | Google Firestore |
| Hosting | Google Cloud Run (us-east1) |
| Scheduler | Google Cloud Scheduler (60s cron) |
| Email | SendGrid (`alerts@statusrooster.com`) |
| Billing | Stripe (Free + Pro $9/mo) |
| Auth | JWT cookies + Google OAuth + GitHub OAuth (code done, needs env vars) |
| Domain | `statusrooster.com` (Namecheap) |
| Design | Dark theme, indigo `#6366f1`, Inter + JetBrains Mono |

| Phase | Days | Status |
|-------|------|--------|
| 1. Core Engine | 1-4 | ✅ Complete |
| 2. Feature Suite & Billing | 5-9 | ✅ Complete |
| 3. Hardening & Launch | 10-12 | 🟡 In progress |
| 4. Post-Launch | 13-14+ | 🔲 Not started |

---

## Phase 1: Core Engine — Days 1-4

### Day 1 — Scaffolding & Auth ✅
- [x] FastAPI project structure (`app/`, `routers/`, `services/`, `templates/`, `static/`)
- [x] `requirements.txt` + `Dockerfile` + `.dockerignore`
- [x] Config/settings module (loads `.env`)
- [x] Firestore client singleton
- [x] User model + Firestore CRUD (create, get by email, get by ID)
- [x] Auth: signup endpoint (email + password, bcrypt hash)
- [x] Auth: login endpoint (verify password, return JWT)
- [x] Auth: JWT middleware (protect routes, extract current user)
- [x] Base Jinja2 template (`base.html` — nav, footer, block content)
- [x] Health check endpoint (`/health`)
- [x] Deploy skeleton to Cloud Run (app starts, `/health` returns 200)

### Day 2 — Monitors & Check Engine ✅
- [x] Monitor model + Firestore CRUD (create, list by user, get, update, delete)
- [x] Plan enforcement: free users capped at 5 monitors
- [x] `POST /api/monitors` — create monitor (validate URL, generate slug)
- [x] `GET /api/monitors` — list user's monitors
- [x] `PUT /api/monitors/{id}` — update monitor
- [x] `DELETE /api/monitors/{id}` — delete monitor + cleanup checks
- [x] HTTP check function (GET with timeout, measure response_ms, capture status code)
- [x] False positive prevention: retry once after 5s before marking down
- [x] `POST /cron/check` — iterate all monitors, run checks, write results to Firestore
- [x] Update monitor doc after each check (status, last_checked, response_ms, uptime%)
- [x] Cloud Scheduler job: hits `/cron/check` every 60 seconds
- [x] Cron auth: verify request comes from Cloud Scheduler (header or shared secret)

### Day 3 — Alerts & Incidents ✅
- [x] Incident model + Firestore CRUD (create, resolve, list by monitor)
- [x] Status change detection: compare previous status vs current
- [x] On UP→DOWN: create incident, trigger alerts
- [x] On DOWN→UP: resolve incident (set `resolved_at`, calculate duration), send recovery alert
- [x] Alert deduplication: don't re-alert for same ongoing incident
- [x] SendGrid email alert (down notification — site, time, status code)
- [x] SendGrid email alert (recovery notification — site, duration)
- [x] Slack webhook alert (down + recovery, formatted message)
- [x] Alert service abstraction (easy to add SMS later)
- [x] Test with real SendGrid + Slack webhook

### Day 4 — Dashboard UI ✅
- [x] Signup page (`/signup` — form, validation, redirect to dashboard)
- [x] Login page (`/login` — form, error states, redirect to dashboard)
- [x] Auth cookie handling (set JWT in httpOnly cookie on login)
- [x] Dashboard page (`/dashboard` — list all monitors with status indicators)
- [x] Monitor status badges (Up / Down / Pending)
- [x] Add monitor form (modal or inline — URL, name, alert settings)
- [x] Edit monitor form (pre-filled, save changes)
- [x] Delete monitor (confirmation prompt)
- [x] Monitor detail view (response time chart — Chart.js, last 24h)
- [x] Alert settings per monitor (email, Slack webhook URL)
- [x] Flash messages (success/error feedback on actions)

**✅ Day 4 Checkpoint:** Sign up → add URL → see checks → get alert on down → see recovery.

---

## Phase 2: Status Pages & Billing — Days 5-9

### Day 5 — Public Status Pages ✅
- [x] Status page route: `GET /s/{slug}`
- [x] Status page template: site name, current status, uptime bars (90 days)
- [x] Uptime bar component (green/red/gray day-by-day blocks)
- [x] Incident history list (last 10 incidents with timestamps + durations)
- [x] "Powered by StatusRooster" footer with signup link
- [x] User can toggle monitor public/private
- [x] User can set/edit slug for their status page
- [x] Status page works when logged out (public)

### Day 6 — Stripe Billing ✅
- [x] Stripe Checkout session creation (`POST /api/billing/checkout`)
- [x] Redirect user to Stripe Checkout for Pro upgrade
- [x] Stripe webhook endpoint (`POST /api/billing/webhook`)
- [x] Handle `checkout.session.completed` → update user plan to Pro
- [x] Handle `customer.subscription.deleted` → downgrade to Free
- [x] Plan enforcement: block monitor creation beyond 5 on Free
- [x] Upgrade prompt on dashboard when at monitor limit
- [x] Manage subscription link (Stripe Customer Portal)
- [x] Plan badge on dashboard (Free / Pro)
- [x] Upgrade accessible from nav, dashboard, pricing page, landing page
- [x] Landing page with interactive URL checker (live ping demo)
- [x] Enriched URL check: status, response time, server, SSL issuer, SSL expiry, redirects
- [x] Logged-in users redirect from `/` → `/dashboard`
- [x] "About Our Code" transparency section on landing page
- [x] Deploy Day 6 to production (revision `statusrooster-00011-6mp`)
- [x] Git commit Day 6 (`dbc0afb`)

### Day 7 — Monitoring Suite Features ✅
_Goal: Build real monitoring features people actually need._

**Tier 1 — Core Monitor Enhancements (all plans) ✅**
- [x] SSL Expiry Monitoring: on each check, grab cert expiry → store on monitor doc
- [x] SSL Expiry Alerts: alert at 14 days, 7 days, 3 days before cert expires
- [x] SSL expiry visible on monitor detail page + dashboard card
- [x] Keyword/Content Check: user sets "expected keyword" → alert if page body doesn't contain it
- [x] Keyword field on add/edit monitor form
- [x] Response Time Threshold: user sets max acceptable ms → alert if exceeded
- [x] Threshold field on add/edit monitor form (e.g., "Alert if > 2000ms")
- [x] Response time threshold visible on monitor detail page
- [x] **Test Alert Button**: "Send Test" on each monitor → fires test email/Slack/webhook to verify config
- [x] Test alert endpoint: `POST /api/monitors/{id}/test-alert`
- [x] Test alert sends clearly-labeled test notification (email + Slack + webhook if configured)
- [x] Test alert button visible on monitor detail page

**Tier 2 — Pro Features (gated behind Pro $9/mo plan) ✅**
- [x] Webhook Notification: user provides a URL → POST JSON payload on status change
- [x] Webhook URL field on add/edit monitor form (show upgrade prompt for Free users)
- [x] Webhook payload: `{event, monitor_name, monitor_url, status, status_code, response_ms, timestamp}`
- [x] Scheduled Maintenance Windows: "Don't alert me [day] [start]-[end] UTC"
- [x] Maintenance window fields on edit monitor form (Pro only)
- [x] Maintenance window fields on add monitor modal (Pro only)
- [x] Check engine skips alerting (still checks) during maintenance windows
- [x] Maintenance window in API: CREATE and UPDATE endpoints (Pro-gated)
- [x] Maintenance window day comparison bug fix (case-insensitive)

**Tier 2 — Status Pages & Reporting (Pro only) ✅**
- [x] Aggregate Status Page: shows ALL public monitors for a user
- [x] Aggregate page: overall status badge + individual monitor rows + uptime bars

**Plan Enforcement**
- [x] Webhook/maintenance fields hidden or show "Upgrade to Pro" for Free users
- [x] Monitor limit enforcement: Free = 5, Pro = 250
- [x] Check interval enforcement: Free = 5 min, Pro = 60s _(set at creation, enforced in checker)_
- [x] Status page limit enforcement: Free = 1, Pro = 10
- [x] Slack/SMS gated to Pro only _(Slack gated in all alert functions + API + UI; SMS not yet built)_

**Pricing Page ✅**
- [x] Rewrote pricing.html — developer-first, accurate feature lists, FAQ section
- [x] Free: 5 monitors, 5-min checks, email alerts, 1 status page, API, badges
- [x] Pro $9/mo: 250 monitors, 60s checks, Slack + SMS, webhooks, maintenance windows, 10 status pages

**Deferred:**
- 🔲 Weekly Uptime Digest Email — moved to post-launch backlog
- 🔲 Domain Expiry Monitoring — needs WHOIS library, post-launch
- 🔲 SMS/Twilio — listed on pricing as Pro, not wired up yet

- [x] Deploy Day 7 to production (revision `statusrooster-00012-4xq`)
- [x] Git commit Day 7 (`227ce35`)

### Day 8 — Public API & Developer Experience ✅
_Goal: Give developers programmatic access. API keys, docs, exports._

**API Keys**
- [x] API key model (generate, store hashed, revoke)
- [x] API key auth middleware (check `X-API-Key` header)
- [x] API key management UI (generate/revoke from Settings page)

**API Endpoints**
- [x] `GET /api/v1/monitors` — list monitors (API key auth)
- [x] `GET /api/v1/monitors/{id}` — single monitor detail
- [x] `GET /api/v1/monitors/{id}/checks` — export checks as JSON (with pagination)
- [x] `POST /api/v1/monitors` — create monitor via API
- [x] `PUT /api/v1/monitors/{id}` — update monitor via API (partial update, Pro-gated webhooks)
- [x] `DELETE /api/v1/monitors/{id}` — delete monitor via API
- [x] All API responses follow consistent JSON shape `{data, error, meta}`

**Documentation**
- [x] API docs page (`/docs/api` — endpoints, auth, examples with curl)
- [x] Python + JavaScript quick-start examples on docs page

**Navigation**
- [x] Settings link in nav bar
- [x] API docs link in nav bar

- [x] Deploy Day 8 to production (revision `statusrooster-00013-zld`)
- [x] Git commit Day 8 (`8951176`)

### Day 9 — Developer-First Pivot & Polish ✅
_Goal: Reposition as developer-first. Modern design. API docs excellence. New pricing._

**Design System Overhaul ✅**
- [x] New color palette: indigo brand (`#6366f1`), near-black dark (`#0a0a0a`), green success (`#22c55e`), red danger (`#ef4444`)
- [x] Added Inter + JetBrains Mono via Google Fonts
- [x] Updated all 12 templates + email templates to new palette
- [x] Zero legacy hex values remaining (verified with grep)

**Landing Page Rewrite ✅**
- [x] Developer-first hero with terminal code block
- [x] Feature sections: API-first, uptime badges, dashboard
- [x] Pricing section inline (Free vs Pro $9/mo)
- [x] `?preview` bypass for logged-in users to see landing page
- [x] UptimeRobot-inspired clean layout

**Pricing Restructure ✅**
- [x] Free: 5 monitors, 5-min checks, email alerts
- [x] Pro $9/mo: 250 monitors, 60s checks, Slack + SMS alerts
- [x] Updated pricing page, landing page, dashboard upgrade banners

**Dashboard Polish ✅**
- [x] Fixed upgrade banner ("4 of 5 monitors" instead of "4 of 50")
- [x] Interval hints based on plan
- [x] Empty state for new users
- [x] Card styling: border-based, no shadows
- [x] Removed all decorative emojis (rooster in nav only)

**Uptime Badges ✅**
- [x] `GET /badge/{id}.svg` — uptime percentage badge (color-coded)
- [x] `GET /badge/{id}/status.svg` — up/down/pending badge
- [x] `GET /badge/{id}/response.svg` — response time badge
- [x] Shields.io-style SVG, 5-min cache, public monitors only

**API Documentation Overhaul ✅**
- [x] Tabbed code blocks: curl / Python / JavaScript on all endpoints
- [x] Copy-to-clipboard button on all code blocks + response shapes
- [x] Field reference dropdowns on every endpoint (consistent)
- [x] Badges moved into Endpoints section as sub-group
- [x] Top CTA bar (signup/API key + playground + OpenAPI spec)
- [x] Client Setup section with shared variable definitions
- [x] Tab preference persists via localStorage
- [x] Removed redundant bottom CTA section and ReDoc link

**OpenAPI / Swagger ✅**
- [x] APIKeyHeader security scheme on all endpoints
- [x] Interactive playground at `/docs`
- [x] Custom ReDoc at `/redoc` (pinned to 2.1.5)

**CSS Unification ✅**
- [x] Unified `style.css` (~2,600 lines) with design tokens
- [x] Mobile hamburger nav
- [x] Stripped inline CSS from all child templates
- [x] `status_page.html` and `aggregate_status.html` kept self-contained

**Still TODO (carry to Day 10+):**
- [ ] Backend feature gating: Slack/SMS/webhooks/response_threshold as Pro-only
- [ ] Check interval enforcement: 5min Free vs 60s Pro in cron
- [ ] SMS/Twilio integration (listed on pricing, not wired)
- [x] Deploy Day 9 to production (revision `statusrooster-00001-hgw`)
- [x] Git commits: `50155fd`, `99f249a`, `de9bd73`, `0616228`, `baf9847`

---

## Phase 3: Hardening & Launch — Days 10-12

> **Source:** Reconciled from ACTION_PLAN.md workstreams + COMPETITIVE_AUDIT.md punch list + GPT strategy session. This is the single source of truth.

### Day 10 — Feature Gating + Competitive Gap Fixes �
_Goal: Make pricing honest, close highest-ROI gaps from UptimeRobot audit, enable OAuth._

**10A. Critical Backend Gating (~45 min)** _(from ACTION_PLAN.md reconciliation)_
_These are broken promises — pricing page says Pro, backend allows Free._

- [x] `paused` field: add to Firestore model default + API Create schema
- [x] Checker: skip paused monitors entirely (`if paused: skip`)
- [x] Checker: enforce check interval per plan (Free = 5min, Pro = 60s) — skip check if `last_checked` < plan interval
- [x] Gate Slack webhook alerts to Pro only in alert service (Free users see upgrade prompt, backend blocks)
- [x] Gate response threshold alerts to Pro only
- [x] Status page limit enforcement: Free = 1, Pro = 10
- [x] Add `paused` toggle to Add Monitor modal + Edit form
- [x] Add `public` toggle to Add Monitor modal (currently only in Edit)
- [x] Add `ssl_expiry_days` to API response serializer
- [x] Add `slug` to API Update schema
- [x] Fix internal monitors router FREE_MONITOR_LIMIT (was 50, now 5)

**10B. GitHub OAuth (~10 min)** _(from ACTION_PLAN.md — code is done, just env vars)_
- [ ] Register GitHub OAuth App at github.com/settings/developers (callback: `https://statusrooster.com/auth/github/callback`)
- [ ] Set `GITHUB_CLIENT_ID` + `GITHUB_CLIENT_SECRET` in `.env`
- [ ] Set same env vars on Cloud Run: `gcloud run services update statusrooster --region us-east1 --set-env-vars ...`
- [ ] Test: click "Continue with GitHub" on login page → authorize → dashboard

**10C. Dashboard UX Gaps (~1.5 hrs)** _(from COMPETITIVE_AUDIT.md Sections 1-2)_
_The data table is built. These are the visual polish items UptimeRobot does that we don't._

- [x] **"Up for X" / "Down for X" duration text** — show below monitor name in table row (~20 min)
  - Compute from `last_status_change` timestamp (or latest incident start/resolve)
  - Format: "Up for 2h 15m" / "Down for 38m"
  - Same duration in monitor detail page status banner
- [x] **Three-dot ⋯ context menu per row** — pause/resume, edit, delete, copy URL (~30 min)
  - Dropdown menu on ⋯ button at end of each row
  - Pause/Resume: instant AJAX toggle
  - Copy URL: clipboard API
  - Delete: confirmation prompt → AJAX
  - Edit: navigate to edit page
- [x] **Pause/Resume button in monitor detail header** (~15 min)
  - Add toggle button next to Edit button
  - AJAX `POST /api/monitors/{id}/pause` endpoint

**10D. Monitor Detail Enhancements (~1.5 hrs)** _(from COMPETITIVE_AUDIT.md Section 2)_

- [ ] **Multi-period uptime row** — show 7d / 30d / 90d uptime % + incident count (~1 hr)
  - Query check history from Firestore for each period
  - Display as stat cards or horizontal row below the status banner
  - Color-coded: green ≥99.5%, yellow ≥95%, red <95%
- [ ] **Response chart time range picker** — Last hour / 6h / 24h / 7d / 30d (~20 min)
  - Radio buttons or tab bar above existing Chart.js chart
  - AJAX fetch checks for selected range, re-render chart
  - Show Avg / Min / Max response time stats below chart
- [ ] **Pro upsell on check interval** — "Checking every 5 min · Get 60s checks →" for Free users (~10 min)
  - Conditional text below the interval stat card
  - Links directly to Stripe checkout

**10E. Add/Edit Form — API Monitoring Fields (~50 min)** _(from COMPETITIVE_AUDIT.md Section 3)_
_These close the "API monitoring" gap. Not a separate product — just 3 form fields._

- [ ] **Request timeout field** — number input, default 30s, stored on monitor doc (~15 min)
  - Add `timeout_seconds` to Firestore model (default 30)
  - Add to API Create/Update schemas
  - Add to Add modal + Edit form
  - Checker: use `timeout_seconds` instead of hardcoded value
- [ ] **Basic Auth fields** — username + password inputs, Pro gated (~20 min)
  - Add `basic_auth_user` + `basic_auth_pass` to monitor model (encrypted at rest)
  - Add to API schemas (Pro-gated)
  - Add to Edit form (greyed for Free with upgrade CTA)
  - Checker: include `Authorization: Basic ...` header when set
- [ ] **HTTP method selector** — dropdown: GET / HEAD / POST (~15 min)
  - Add `http_method` to monitor model (default "GET")
  - Add to API schemas
  - Add to Add modal + Edit form
  - Checker: use selected method instead of hardcoded GET

**10F. Pro Upsell Polish (~20 min)** _(from ACTION_PLAN.md workstream 3)_

- [ ] Check interval badge on dashboard rows: "⏱ 5min" for Free with tooltip "Upgrade for 60s →"
- [ ] Greyed Pro-only columns in column selector with lock 🔒 icon
- [ ] Alert email footer for Free users: "Upgrade to Pro for 60s checks, Slack alerts, and webhooks →"
- [ ] Gate Slack input in Add modal for Free users (grey out + upgrade link)

**10G. Deploy + Commit**
- [ ] Deploy Day 10 to production
- [ ] Git commit Day 10

**Day 10 total estimate: ~4.5 hrs**

---

### Day 11 — Incidents, Activity Log, Hardening & Admin 🔲
_Goal: Build the incidents experience (our differentiator), harden for real users, basic admin._

**11A. Incidents Pages (~1.5 hrs)** _(from COMPETITIVE_AUDIT.md Sections 4-5 — user said "LEAN IN HERE")_

- [ ] **Dedicated /incidents page** — full table with all incidents across monitors (~45 min)
  - Route: `GET /incidents` in `pages.py`
  - Template: `incidents.html` — reuse data table pattern from dashboard
  - Columns: Status (resolved/ongoing), Monitor name, Root Cause (HTTP code badge), Started, Resolved, Duration
  - Data: `list_incidents_by_user()` already exists
  - Search by monitor name/URL
  - Sort: newest/oldest, longest/shortest
  - Filter: Resolved / Ongoing / by status code range
- [ ] **Incident detail page** — `/incidents/{id}` (~30 min)
  - Route: `GET /incidents/{id}` in `pages.py`
  - Template: `incident_detail.html`
  - Root cause card: prominent HTTP status code + human-readable text (e.g. "503 Service Unavailable")
  - Status + timestamps: started_at, resolved_at, duration
  - "Go to monitor" link
  - Request URL + method shown

**11B. Activity Log / Event Timeline (~1.5 hrs)** _(COMPETITIVE_AUDIT.md — rated "Very High ROI")_
_This is the post-mortem feature that makes us feel professional. UptimeRobot's strongest page._

- [ ] **Incident events sub-collection** in Firestore (~20 min)
  - `incidents/{id}/events/{auto_id}` → `{type, timestamp, metadata}`
  - Event types: `detected`, `alert_email_sent`, `alert_slack_sent`, `alert_webhook_sent`, `resolved`, `recovery_email_sent`, `recovery_slack_sent`
- [ ] **Log events in checker + alert service** (~20 min)
  - On detection: write `detected` event with status code, response time
  - On each alert sent: write event with channel (email/slack/webhook) + success/fail status
  - On resolve: write `resolved` event with duration
  - On recovery alert: write event per channel
- [ ] **Activity log timeline on incident detail page** (~30 min)
  - Chronological vertical timeline (newest at bottom)
  - Each event: icon + text + timestamp
  - Alert events show delivery status badge (✅ Success / ❌ Failed)
- [ ] **Alert delivery logging** — store success/fail result from SendGrid/Slack/webhook calls (~20 min)
  - Wrap alert functions in try/catch, record result
  - Show on incident timeline: "Email sent to user@example.com ✅" or "Slack webhook failed ❌"

**11C. Hardening (~45 min)**

- [ ] Custom 404 page (dark theme, "Page not found", link to dashboard)
- [ ] Custom 500 page (dark theme, "Something went wrong", link to dashboard)
- [ ] Meta tags (title, description, OG image) on all public pages: landing, pricing, status pages, API docs
- [ ] Favicon (rooster icon, 32x32 + 180x180 apple-touch)
- [ ] Input validation audit: all form fields + all API endpoints
- [ ] Mobile viewport testing: dashboard, detail, edit, landing, pricing, status page

**11D. Admin Dashboard — Lightweight (~45 min)**
_Minimal admin to know if the business is working. NOT a full analytics suite._

- [ ] Route: `GET /admin` — guard: only your email can access
- [ ] KPI cards: total users, Pro users, Free users, MRR ($), total monitors, checks today
- [ ] Signup list: last 20 signups with email + date + plan
- [ ] Cron health: last run time, monitors checked, alerts fired, errors
- [ ] Link to Stripe Dashboard, GCP Console, SendGrid dashboard

**11E. Deploy + Commit**
- [ ] Deploy Day 11 to production
- [ ] Git commit Day 11

**Day 11 total estimate: ~4.5 hrs**

---

### Day 12 — Testing & Launch 🔲
_Goal: Make sure nothing is broken. Ship it. Tell people._

**12A. Testing (~1.5 hrs)**

- [ ] Full manual E2E test in production:
  - Signup (email + GitHub OAuth)
  - Add monitor → see first check → see status update
  - Trigger downtime → receive email alert → see incident created
  - Recover → receive recovery alert → incident resolved
  - View incident detail + activity log
  - Edit monitor (timeout, auth, HTTP method, keyword, threshold)
  - Pause/resume from dashboard context menu + detail header
  - Export CSV (Pro)
  - Status page works publicly
  - Uptime badges render
  - API: create, list, update, delete via curl
  - Stripe: upgrade to Pro, verify features unlock, downgrade
- [ ] Dogfooding: StatusRooster monitoring statusrooster.com (add as first real monitor)
- [ ] Mobile viewport spot-check: dashboard, detail, landing
- [ ] Switch Stripe from test mode to live mode
- [ ] Verify all env vars on Cloud Run are production values

**12B. Launch Prep (~30 min)**

- [ ] Final Cloud Run deploy with production env vars
- [ ] Write Show HN post (title: "Show HN: StatusRooster — uptime, API, and cron monitoring for indie devs")
- [ ] Screenshots / demo GIF for README
- [ ] Update README.md with positioning, feature list, screenshots

**12C. Launch (~1 hr, then ongoing)**

- [ ] Submit Show HN
- [ ] Post to r/SideProject, r/webdev, r/SaaS
- [ ] Post to IndieHackers
- [ ] Monitor comments, respond to feedback
- [ ] Hot-fix any launch-day bugs
- [ ] Check admin dashboard for signups, conversions, errors

---

## Phase 4: Post-Launch — Days 13+

### Days 13-14 — Bug Fixes & Growth 🔲
- [ ] Fix bugs from real user feedback
- [ ] SEO pages: "Free Uptime Monitoring API", "UptimeRobot Alternative for Developers"
- [ ] Free SSL checker tool page (standalone, ranks on Google)
- [ ] Submit to AlternativeTo, G2
- [ ] Plan Product Hunt launch (week 3)

### v1.1 — High-Value Feature Additions 🔲
_Items identified during competitive audit + GPT strategy session. Build after launch, based on user feedback._

**Cron / Heartbeat Monitoring (NEW — strategic differentiator) ⭐**
- [ ] New monitor type: "Heartbeat" — expects a ping within X minutes
- [ ] Endpoint: `POST /api/ping/{monitor_id}` — records heartbeat
- [ ] Checker: if no heartbeat received within expected window → alert
- [ ] UI: new "Heartbeat" option in Add Monitor dropdown
- [ ] Dashboard: heartbeat monitors show "Last ping: 2m ago" instead of response time
- [ ] _Rationale: Dead Man's Snitch charges $5-50/mo for JUST this. We bundle it. Architecturally trivial (~2-3 hrs). Massive positioning value._

**Uptime Sparkline Bar Chart**
- [ ] Mini bar chart per dashboard row showing up/down history (last 24h or 7d)
- [ ] Green bars = up, red bars = down, gray = no data
- [ ] Requires aggregating check history into time buckets
- [ ] _Rationale: UptimeRobot's most eye-catching visual element. ~1-2 hrs._

**Custom Request Headers**
- [ ] Key/value input fields on edit form for custom HTTP headers
- [ ] Store as JSON array on monitor doc
- [ ] Checker: include custom headers in request
- [ ] _Rationale: Closes the "API monitoring" gap. Users can set Authorization, X-API-Key, etc. ~15 min._

**Left Sidebar Navigation**
- [ ] Persistent sidebar: Dashboard, Incidents, Status Pages, Settings, API Docs
- [ ] Replaces top-bar nav links
- [ ] _Rationale: Proper app navigation for multi-page SaaS. ~45 min._

**Multi-Region Checks (Pro feature)**
- [ ] Check from 3 regions: US-East, EU-West, Asia
- [ ] Confirm outage from 2+ regions before alerting (reduces false positives)
- [ ] _Rationale: Requires deploying checkers to multiple Cloud Run regions. Multi-day project. High value for Pro._

**Discord Webhook**
- [ ] Add `alert_discord_webhook` field to monitor model
- [ ] Same POST-to-URL pattern as Slack
- [ ] _Rationale: Trivial (~15 min) but adds "we support 3 channels" to marketing. Post-launch._

**SMS / Twilio**
- [ ] Twilio account + phone number
- [ ] SMS alert on down/up (Pro only)
- [ ] SMS field on edit form
- [ ] _Rationale: Listed on pricing page but not built. Need to wire up or remove from pricing._

### Future Backlog 🔲
_Nice-to-have. Don't build until there's user demand._

**Developer tools:**
- [ ] CLI tool (`pip install statusrooster`)
- [ ] GitHub Actions integration (check uptime in CI)
- [ ] Public API v2 improvements + rate limiting
- [ ] Weekly Uptime Digest Email

**Product:**
- [ ] Alert confirmation threshold ("wait N fails before alerting") — reduces false positives
- [ ] Team Plan ($29/mo): 500 monitors, 30s intervals, 5 seats
- [ ] TCP/Ping checks (non-HTTP services)
- [ ] Incident postmortem notes
- [ ] Domain expiry monitoring (WHOIS)
- [ ] Password reset flow
- [ ] Password-protected status pages
- [ ] Custom domains for status pages

**Telemetry & Analytics (build when needed, not before):**
- [ ] Event logging service (signups, upgrades, alert volume)
- [ ] Page view tracking middleware
- [ ] Cron health stats collection
- [ ] Cost tracking vs revenue (admin dashboard)
- [ ] Conversion funnel analytics

**Infrastructure:**
- [ ] CI/CD pipeline (GitHub Actions → Cloud Run)
- [ ] Automated tests (pytest + httpx)
- [ ] Google OAuth consent screen: Testing → Production

---

## Progress Summary

| Phase | Days | Status |
|-------|------|--------|
| 1. Core Engine | 1-4 | ✅ Complete |
| 2. Feature Suite & Billing | 5-9 | ✅ Complete |
| 3. Hardening & Launch | 10-12 | � In progress |
| 4. Post-Launch | 13+ | 🔲 Not started |

**Day 10 in progress** · **Target launch: Day 12 (Mar 7)**

### What's actually live right now
- ✅ Full monitoring engine: HTTP checks, SSL, keyword, response threshold
- ✅ Alerts: email (SendGrid), Slack webhooks, webhook notifications
- ✅ Public status pages + aggregate status page
- ✅ Stripe billing (Free / Pro $9/mo)
- ✅ Public API with key auth (6 endpoints, consistent JSON)
- ✅ Uptime badges (3 SVG types, shields.io-style)
- ✅ API docs with tabbed examples (curl/Python/JS), copy buttons
- ✅ Interactive Swagger playground + OpenAPI spec
- ✅ Modern developer-first design (indigo palette, Inter + JetBrains Mono)
- ✅ Data table dashboard with sort, filter, search, column selector, bulk actions, export

### What's broken / dishonest (Day 10 fixes)
- ~~⚠️ Slack alerts — Free users can set webhook URL (pricing says Pro only)~~ ✅ Fixed
- ~~⚠️ Response threshold — Free users can set threshold (should be Pro?)~~ ✅ Threshold is all-plan, Slack channel is Pro-gated
- ~~⚠️ Check interval — all monitors run at 60s regardless of plan (pricing says Free = 5min)~~ ✅ Fixed (check_interval set at creation, enforced in checker)
- ~~⚠️ `paused` field — exists in API but not functional in checker or UI~~ ✅ Fixed (checker skips paused, UI has toggle)
- ⚠️ SMS — listed on pricing, not implemented (remove from pricing or defer)

### What's missing (Day 10-11 adds)
- 🔲 "Up for X" duration text on dashboard + detail
- 🔲 Three-dot context menu per row
- 🔲 Pause/Resume from dashboard + detail header
- 🔲 Multi-period uptime (7d/30d/90d)
- 🔲 Response chart time range picker
- 🔲 Request timeout / Basic Auth / HTTP method fields
- 🔲 Dedicated /incidents page
- 🔲 Incident detail page + activity log timeline
- 🔲 Custom 404/500 pages, meta tags, favicon

---

## Domain & Email Setup ✅
- [x] Point `statusrooster.com` DNS to Cloud Run (4x A records)
- [x] Map custom domain in Cloud Run (`gcloud run domain-mappings create`)
- [x] SSL certificate provisioned (automatic via Cloud Run) — verified `https://statusrooster.com/health` → 200
- [x] SendGrid domain authentication (3x CNAME records validated)
- [x] Update `SENDGRID_FROM_EMAIL` to `alerts@statusrooster.com`
- [x] Email forwarding: catch-all `*@statusrooster.com` → `gjbangerter@gmail.com` (Namecheap)
- [x] Test email delivery end-to-end (confirmed inbox delivery, not spam!)
- [x] Update `APP_URL` env var to `https://statusrooster.com`

---

## Internal Metrics & Telemetry

> **Deferred to post-launch.** Building a full analytics suite before having users is premature optimization. For launch, the lightweight admin dashboard (Day 11D) + Stripe Dashboard + GCP Console is sufficient. Build event tracking when we need it, not before.
