# StatusRooster Build Tracker

**Start:** Feb 25, 2026 · **Target Launch:** Mar 7, 2026

| Phase | Days | Status |
|-------|------|--------|
| 1. Core Engine | 1-4 | ✅ Complete |
| 2. Feature Suite & Billing | 5-9 | 🔄 In Progress (Day 9) |
| 3. Testing & Launch | 10-12 | 🔲 Not started |
| 4. Post-Launch | 13-14+ | 🔲 Not started |

**Current Day: 9** · **Current Phase: 2**

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
_Goal: Build real monitoring features people actually need. Lean into simplicity — not trying to be UptimeRobot, just a great uptime tool for freelancers, indie devs, and small agencies._

**Strategic Positioning (decided Day 7):**
- ❌ NOT competing head-to-head with UptimeRobot
- ✅ Positioning on simplicity: "No bloat. No confusion. Just uptime monitoring."
- ✅ Honest feature stack — only claim what's actually built
- ✅ Target audience: freelancers, indie devs, small agencies who want simple, not enterprise
- ✅ Goal: $10-20K/mo niche SaaS, not a VC-backed UptimeRobot killer

**What's Actually Built (Free tier):**
```
50 monitors, HTTP/HTTPS monitoring, SSL expiry monitoring + alerts,
Keyword monitoring, Response time threshold alerts, Email alerts,
Slack integration, Test alert button, 1 public status page
```
**What's Actually Built (Pro $9/mo):**
```
Everything in Free + Unlimited monitors, Webhook notifications,
Maintenance windows, Aggregate status page, 10 status pages
```

**Tier 1 — Core Monitor Enhancements (ALL plans, including Free) ✅**
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

**Plan Enforcement Updates (partial)**
- [x] Webhook/maintenance fields hidden or show "Upgrade to Pro" for Free users
- [x] Monitor limit enforcement: Free = 50, Pro = Unlimited
- [ ] Check interval enforcement: Free = 5 min cron, Pro = 60 sec cron _(deferred — needs per-monitor scheduling)_
- [ ] Status page limit enforcement: Free = 1, Pro = 10 _(not yet enforced in code)_

**Pricing Page ✅**
- [x] Rewrote pricing.html — simplicity positioning, accurate feature lists, FAQ section
- [x] Removed UptimeRobot comparison table (was overclaiming features we don't have)
- [x] Removed "Weekly uptime digest email" from Pro features (not built yet)
- [x] Every feature listed on pricing page is actually built and working

**NOT built (removed from scope or deferred):**
- 🔲 Weekly Uptime Digest Email — removed from pricing page claims, moved to Day 9 (competitive edge feature)
- 🔲 Domain Expiry Monitoring — deferred to post-launch (needs WHOIS library)
- 🔲 API access gating (Free vs Pro) — Day 8 scope

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

### Day 9 — UI Polish & Competitive Edge 🔄
_Goal: Make everything look professional. Add differentiating features._

**CSS Unification ✅**
- [x] Created `app/static/style.css` (1,930 lines) with CSS custom properties (design tokens)
- [x] Replaced inline `<style>` in `base.html` with `<link rel="stylesheet" href="/static/style.css">`
- [x] Added mobile hamburger nav in `base.html`
- [x] Stripped inline CSS from all 9 child templates (dashboard, monitor_detail, edit_monitor, settings, landing, pricing, api_docs, login, signup)
- [x] `status_page.html` and `aggregate_status.html` kept self-contained (standalone public pages)

**UI Cleanup ✅**
- [x] Removed all decorative emojis from headings, labels, buttons across all 12 templates
- [x] Removed all `→` arrows from button/link text
- [x] Replaced emoji status circles with CSS `.status-dot` elements (dashboard + monitor detail)
- [x] Removed feature icon divs from landing page
- [x] Professional text-only UI throughout

**Competitive Edge Features** 🔲
- [ ] Smart Onboarding — landing URL checker stores result, auto-creates first monitor on signup
- [ ] Weekly Uptime Digest Email — Cloud Scheduler Monday 9am UTC, per-user summary
- [ ] Uptime Badges — `GET /badge/{id}.svg`, public SVG for GitHub READMEs

**Hardening** 🔲
- [ ] Custom 404 page
- [ ] Custom 500 page
- [ ] Meta tags (title, description, OG image) on all public pages
- [ ] Favicon

- [ ] Deploy Day 9 to production
- [ ] Git commit Day 9

---

## Phase 3: Testing & Launch — Days 10-12

### Day 10 — Automated Test Suite 🔲
_Goal: Comprehensive pytest suite that covers every route, edge case, and failure mode._

- [ ] pytest + httpx async test client setup
- [ ] Test fixtures: mock Firestore, test user, test monitor
- [ ] Auth Tests (12): signup, login, session, logout edge cases
- [ ] Monitor CRUD Tests (12): create, edit, delete, plan limits, user isolation
- [ ] Check Engine Tests (12): cron auth, up/down detection, incidents, alerts, SSL
- [ ] API Key & API Tests (10): generate, revoke, CRUD via API, user isolation
- [ ] Webhook & Integration Tests (6): webhook payload, maintenance windows
- [ ] Test Alert Tests (4): email, Slack, webhook test notifications
- [ ] Billing Tests (6): Stripe checkout, webhooks, plan changes
- [ ] Edge Cases & Security (8): injection, XSS, validation, rate limiting
- [ ] **ALL TESTS PASSING** ✅
- [ ] Git commit Day 10

### Day 11 — End-to-End Testing & Pre-Launch 🔲
_Goal: Manual smoke test the ENTIRE product. Deploy final build. Dogfood it._

- [ ] Full manual E2E test of every user flow in production
- [ ] Dogfooding: StatusRooster monitoring statusrooster.com
- [ ] Mobile viewport testing
- [ ] Final Cloud Run deploy with production env vars
- [ ] Switch Stripe from test mode to live mode
- [ ] Write Show HN post draft
- [ ] Screenshots / demo GIF
- [ ] Git commit Day 11

### Day 12 — Launch 🔲
- [ ] Submit Show HN
- [ ] Post to r/SideProject, r/webdev, r/SaaS
- [ ] Post to IndieHackers
- [ ] Monitor comments, respond to feedback
- [ ] Hot-fix any bugs reported
- [ ] Track signups in Firestore

---

## Phase 4: Post-Launch — Days 13-14+

### Days 13-14 — Bug Fixes & Growth 🔲
- [ ] Fix bugs from real user feedback
- [ ] SEO blog posts ("Free Website Uptime Monitoring", "UptimeRobot Alternatives 2026")
- [ ] Free SSL checker tool page (standalone, ranks on Google)
- [ ] Submit to AlternativeTo, G2
- [ ] Plan Product Hunt launch (week 3)

### Future Features (Post-Launch Backlog) 🔲
- [ ] **Team Plan ($29/mo)**: 200 monitors, 30s intervals, 5 login seats, unlimited status pages
- [ ] SMS Alerts (Twilio integration)
- [ ] TCP/Ping Checks (non-HTTP services)
- [ ] Port / DNS Monitoring
- [ ] Team / Multi-User accounts (login seats, roles)
- [ ] API Response Validation (check JSON fields)
- [ ] Multiple check regions (US-East, EU, Asia)
- [ ] PagerDuty / Opsgenie integration
- [ ] Custom check intervals (30s, 5m, 15m)
- [ ] Incident postmortem notes
- [ ] Cron Job / Heartbeat monitoring
- [ ] Custom HTTP headers per monitor
- [ ] Password-protected status pages
- [ ] Dashboard filtering / sorting / search
- [ ] CI/CD pipeline (GitHub Actions → Cloud Run)
- [ ] Password reset flow

---

## Progress Summary

| Phase | Days | Status |
|-------|------|--------|
| 1. Core Engine | 1-4 | ✅ Complete |
| 2. Feature Suite & Billing | 5-9 | 🔄 In Progress (Day 9) |
| 3. Testing & Launch | 10-12 | 🔲 Not started |
| 4. Post-Launch | 13-14+ | 🔲 Not started |

**Current Day: 9** · **Current Phase: 2**

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
