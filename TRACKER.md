# StatusRooster Build Tracker

**Start:** Feb 25, 2026 · **Target Launch:** Mar 7, 2026
**Positioning:** Developer-first uptime monitoring. Simple API, clean UI, fair pricing.
**Target audience:** Indie devs, SaaS builders, freelancers, small teams.

| Phase | Days | Status |
|-------|------|--------|
| 1. Core Engine | 1-4 | ✅ Complete |
| 2. Feature Suite & Billing | 5-9 | ✅ Complete |
| 3. Testing & Launch | 10-12 | 🔲 Not started |
| 4. Post-Launch | 13-14+ | 🔲 Not started |

**Current Day: 9 (complete)** · **Next: Day 10 (Phase 3)**

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
- [x] Check engine skips alerting (still checks) during maintenance windows

**Tier 2 — Status Pages & Reporting (Pro only) ✅**
- [x] Aggregate Status Page: shows ALL public monitors for a user
- [x] Aggregate page: overall status badge + individual monitor rows + uptime bars

**Plan Enforcement**
- [x] Webhook/maintenance fields hidden or show "Upgrade to Pro" for Free users
- [x] Monitor limit enforcement: Free = 5, Pro = 250
- [ ] Check interval enforcement: Free = 5 min, Pro = 60s _(needs per-monitor scheduling in cron)_
- [ ] Status page limit enforcement: Free = 1, Pro = 10 _(not yet enforced in code)_
- [ ] Slack/SMS gated to Pro only _(UI shows fields, backend doesn't gate yet)_

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
- [ ] Deploy Day 9 to production
- [x] Git commits: `50155fd`, `99f249a`, `de9bd73`, `0616228`

---

## Phase 3: Hardening & Launch — Days 10-12

### Day 10 — Backend Gating & Hardening 🔲
_Goal: Make pricing real. Gate features properly. Harden the product._

**Feature Gating (make pricing honest)**
- [ ] Slack webhook alerts → Pro only (Free users see upgrade prompt)
- [ ] SMS alerts → Pro only (needs Twilio integration)
- [ ] Webhook notifications → Pro only (already partially gated)
- [ ] Response threshold alerts → Pro only
- [ ] Maintenance windows → Pro only (already gated in UI)
- [ ] Check interval enforcement: Free = 5 min, Pro = 60s in cron job
- [ ] Status page limit: Free = 1, Pro = 10

**SMS/Twilio Integration**
- [ ] Twilio account + phone number
- [ ] SMS alert on monitor down/up (Pro only)
- [ ] SMS field on edit monitor form (Pro only)
- [ ] Test alert includes SMS

**Hardening**
- [ ] Custom 404 page
- [ ] Custom 500 page
- [ ] Meta tags (title, description, OG) on all public pages
- [ ] Favicon
- [ ] Input validation audit (all forms + API endpoints)

- [ ] Deploy Day 10 to production
- [ ] Git commit Day 10

### Day 11 — Testing & Pre-Launch 🔲
_Goal: Automated tests + manual smoke test. Deploy final build._

- [ ] pytest + httpx async test client setup
- [ ] Test fixtures: mock Firestore, test user, test monitor
- [ ] Auth tests: signup, login, session, logout
- [ ] Monitor CRUD tests: create, edit, delete, plan limits
- [ ] Check engine tests: cron, up/down, incidents, alerts, SSL
- [ ] API key + API endpoint tests
- [ ] Billing tests: Stripe checkout, webhooks, plan changes
- [ ] Full manual E2E test in production
- [ ] Dogfooding: StatusRooster monitoring statusrooster.com
- [ ] Mobile viewport testing
- [ ] Switch Stripe from test mode to live mode
- [ ] Git commit Day 11

### Day 12 — Launch 🔲
_Goal: Ship it. Tell people._

- [ ] Final Cloud Run deploy with production env vars
- [ ] Write Show HN post
- [ ] Screenshots / demo GIF for README
- [ ] Submit Show HN
- [ ] Post to r/SideProject, r/webdev, r/SaaS
- [ ] Post to IndieHackers
- [ ] Monitor comments, respond to feedback
- [ ] Hot-fix any launch-day bugs
- [ ] Track signups in Firestore

---

## Phase 4: Post-Launch — Days 13-14+

### Days 13-14 — Bug Fixes & Growth 🔲
- [ ] Fix bugs from real user feedback
- [ ] SEO pages: "Free Uptime Monitoring API", "UptimeRobot Alternative for Developers"
- [ ] Free SSL checker tool page (standalone, ranks on Google)
- [ ] Submit to AlternativeTo, G2
- [ ] Plan Product Hunt launch (week 3)

### Future Features (Backlog) 🔲

**High priority (developer value):**
- [ ] Weekly Uptime Digest Email (Cloud Scheduler, per-user summary)
- [ ] CLI tool (`npm install -g statusrooster` or `pip install statusrooster`)
- [ ] GitHub Actions integration (check uptime in CI)
- [ ] Smart Onboarding — landing URL checker auto-creates first monitor on signup
- [ ] API rate limiting (per-key)

**Medium priority:**
- [ ] Team Plan ($29/mo): 500 monitors, 30s intervals, 5 seats, unlimited status pages
- [ ] TCP/Ping checks (non-HTTP services)
- [ ] Multiple check regions (US-East, EU, Asia)
- [ ] Custom HTTP headers per monitor
- [ ] Incident postmortem notes
- [ ] Dashboard filtering / sorting / search
- [ ] Domain expiry monitoring (WHOIS)
- [ ] Cron job / heartbeat monitoring

**Integrations:**
- [ ] PagerDuty / Opsgenie
- [ ] Discord webhooks
- [ ] Telegram alerts
- [ ] Zapier / Make integration

**Infrastructure:**
- [ ] CI/CD pipeline (GitHub Actions → Cloud Run)
- [ ] Password reset flow
- [ ] Password-protected status pages
- [ ] Custom domains for status pages

---

## Progress Summary

| Phase | Days | Status |
|-------|------|--------|
| 1. Core Engine | 1-4 | ✅ Complete |
| 2. Feature Suite & Billing | 5-9 | ✅ Complete |
| 3. Hardening & Launch | 10-12 | 🔲 Next up |
| 4. Post-Launch | 13-14+ | 🔲 Not started |

**Day 9 complete** · **Next: Day 10 — Backend Gating & Hardening**

### What's actually live right now
- ✅ Full monitoring engine: HTTP checks, SSL, keyword, response threshold
- ✅ Alerts: email (SendGrid), Slack webhooks, webhook notifications
- ✅ Public status pages + aggregate status page
- ✅ Stripe billing (Free / Pro $9/mo)
- ✅ Public API with key auth (5 endpoints, consistent JSON)
- ✅ Uptime badges (3 SVG types, shields.io-style)
- ✅ API docs with tabbed examples (curl/Python/JS), copy buttons
- ✅ Interactive Swagger playground + OpenAPI spec
- ✅ Modern developer-first design (indigo palette, Inter + JetBrains Mono)

### What's NOT gated yet (pricing says Pro, backend allows Free)
- ⚠️ Slack alerts — Free users can set webhook URL
- ⚠️ Response threshold — Free users can set threshold
- ⚠️ Check interval — all monitors run at same 60s interval
- ⚠️ SMS — listed on pricing, not implemented

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
