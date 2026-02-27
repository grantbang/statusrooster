# StatusRooster Build Tracker 🐓

**Start:** Feb 25, 2026 · **Target Launch:** Mar 7, 2026
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
- [x] Monitor status badges (🟢 Up / 🔴 Down / ⚪ Pending)
- [x] Add monitor form (modal or inline — URL, name, alert settings)
- [x] Edit monitor form (pre-filled, save changes)
- [x] Delete monitor (confirmation prompt)
- [x] Monitor detail view (response time chart — Chart.js, last 24h)
- [x] Alert settings per monitor (email, Slack webhook URL)
- [x] Flash messages (success/error feedback on actions)

**✅ Day 4 Checkpoint:** Sign up → add URL → see checks → get alert on down → see recovery.

---

## Phase 2: Status Pages & Billing — Days 5-8

### Day 5 — Public Status Pages ✅
- [x] Status page route: `GET /s/{slug}`
- [x] Status page template: site name, current status, uptime bars (90 days)
- [x] Uptime bar component (green/red/gray day-by-day blocks)
- [x] Incident history list (last 10 incidents with timestamps + durations)
- [x] "Powered by StatusRooster 🐓" footer with signup link
- [x] User can toggle monitor public/private
- [x] User can set/edit slug for their status page
- [x] Status page works when logged out (public)

### Day 6 — Stripe Billing 🔲
- [ ] Stripe Checkout session creation (`POST /api/billing/checkout`)
- [ ] Redirect user to Stripe Checkout for Pro upgrade
- [ ] Stripe webhook endpoint (`POST /api/billing/webhook`)
- [ ] Handle `checkout.session.completed` → update user plan to Pro
- [ ] Handle `customer.subscription.deleted` → downgrade to Free
- [ ] Plan enforcement: block monitor creation beyond 5 on Free
- [ ] Upgrade prompt on dashboard when at monitor limit
- [ ] Manage subscription link (Stripe Customer Portal)
- [ ] Plan badge on dashboard (Free / Pro)

### Day 7 — Public API, Docs & Landing Page 🔲
- [ ] API key model (generate, store hashed, revoke)
- [ ] API key auth middleware (check `X-API-Key` header)
- [ ] API key management UI (generate/revoke from dashboard settings)
- [ ] `GET /api/monitors` — list monitors (API key auth)
- [ ] `GET /api/monitors/{id}/checks` — export checks as JSON
- [ ] API docs page (`/docs` — endpoints, auth, examples with curl)
- [ ] Marketing landing page (`/`)
- [ ] Hero section: headline, subhead, CTA button
- [ ] Features grid (6 features with icons)
- [ ] Pricing table (Free vs Pro, side-by-side)
- [ ] FAQ section (5-6 common questions)
- [ ] Footer (links, legal placeholder)
- [ ] Mobile responsive

### Day 8 — UI Polish & Hardening 🔲
- [ ] UI polish pass: clean typography, spacing, color consistency (think Google, not AI-generated)
- [ ] Dashboard card redesign (tighter layout, better hierarchy)
- [ ] Dashboard filtering (All / Up / Down / Pending)
- [ ] Dashboard sorting (name, status, uptime%, response time)
- [ ] Dashboard search (filter by name or URL)
- [ ] Monitor detail page polish (chart styling, stat cards)
- [ ] Auth pages polish (signup, login — consistent with dashboard)
- [ ] Mobile responsive pass on all pages (dashboard, status page, forms)
- [ ] Error states: form validation messages, API error handling
- [ ] Rate limiting on auth endpoints (prevent brute force)
- [ ] Custom 404 page
- [ ] Custom 500 page
- [ ] Meta tags (title, description, OG image) on all public pages
- [ ] Favicon + basic branding
- [ ] Logout functionality
- [ ] Password reset flow (forgot password → email link → reset form)
- [ ] Loading states / disabled buttons on form submit

**✅ Day 8 Checkpoint:** Full product. Signup → monitor → alerts → status page → upgrade → manage subscription.

### Day 8.5 — Automated Test Suite 🔲
_Goal: Comprehensive pytest suite that covers every route, edge case, and failure mode. CI/CD-ready._

**Test Infrastructure**
- [ ] pytest + httpx async test client setup
- [ ] Test fixtures: mock Firestore, test user, test monitor
- [ ] Conftest with reusable auth helpers (create user, get token, get cookie)
- [ ] GitHub Actions CI workflow (run tests on every push/PR)

**Auth Tests (10+)**
- [ ] Signup with valid credentials → 302 + cookie + user in DB
- [ ] Signup with duplicate email → error "Email already registered"
- [ ] Signup with mismatched passwords → error "Passwords don't match"
- [ ] Signup with short password (<8 chars) → error
- [ ] Signup with invalid email format → error
- [ ] Login with correct credentials → 302 + cookie
- [ ] Login with wrong password → error "Invalid email or password"
- [ ] Login with non-existent email → same generic error (no info leak)
- [ ] Access /dashboard without cookie → redirect to /login
- [ ] Access /dashboard with expired JWT → redirect to /login
- [ ] Access /dashboard with tampered JWT → redirect to /login
- [ ] Logout clears cookie → redirect to /login

**Monitor CRUD Tests (10+)**
- [ ] Create monitor with valid URL → appears in dashboard
- [ ] Create monitor with invalid URL → error
- [ ] Create monitor without auth → redirect to /login
- [ ] Create 6th monitor on free plan → error "Upgrade to Pro"
- [ ] Edit monitor name → name updated in Firestore
- [ ] Edit monitor URL → URL updated
- [ ] Edit someone else's monitor → 404 (no cross-user access)
- [ ] Delete monitor → removed from dashboard + Firestore
- [ ] Delete someone else's monitor → 404
- [ ] List monitors only shows current user's monitors

**Check Engine Tests (8+)**
- [ ] Cron endpoint without secret → 401
- [ ] Cron endpoint with wrong secret → 401
- [ ] Cron endpoint with valid secret → runs checks
- [ ] Check against UP site → is_up=true, status_code=200
- [ ] Check against DOWN site → is_up=false after retry
- [ ] Status change UP→DOWN → creates incident + triggers alerts
- [ ] Status change DOWN→UP → resolves incident + sends recovery
- [ ] No status change → no duplicate alerts

**API Tests (6+)**
- [ ] API endpoints return JSON (not HTML)
- [ ] API with valid JWT → 200 + data
- [ ] API without auth → 401
- [ ] API with invalid token → 401
- [ ] Monitor API respects user isolation
- [ ] Check export returns correct data shape

**Edge Cases & Security (6+)**
- [ ] SQL/NoSQL injection attempts in email field
- [ ] XSS attempt in monitor name → properly escaped
- [ ] Extremely long URL → handled gracefully
- [ ] Concurrent duplicate signup → only one user created
- [ ] Empty form submission → proper validation errors
- [ ] CORS headers on API endpoints

---

## Phase 3: Launch Prep — Days 9-10

### Day 9 — Bonus Features & Testing 🔲
- [ ] SSL expiration check (connect to host, read cert expiry, alert if < 14 days)
- [ ] SSL monitor type in UI (add SSL check to a monitor)
- [ ] End-to-end manual test: full user journey (signup → monitors → alerts → status page → billing)
- [ ] Set up StatusRooster monitoring itself (eat your own dog food)
- [ ] Write Show HN post draft
- [ ] Take screenshots / record demo GIF
- [ ] Final Cloud Run deploy with production env vars

### Day 10 — Launch 🔲
- [ ] Submit Show HN
- [ ] Post to r/SideProject, r/webdev, r/SaaS
- [ ] Post to IndieHackers
- [ ] Monitor comments, respond to feedback
- [ ] Hot-fix any bugs reported
- [ ] Track signups in Firestore

**🚀 LAUNCHED**

---

## Phase 4: Post-Launch — Days 11-14

### Days 11-12 — Bug Fixes & Quick Wins 🔲
- [ ] Fix bugs from real user feedback
- [ ] Add most-requested small features
- [ ] Performance improvements if needed
- [ ] Monitor error logs

### Days 13-14 — Growth & SEO 🔲
- [ ] SEO blog post: "Free Website Uptime Monitoring"
- [ ] SEO blog post: "UptimeRobot Alternatives 2026"
- [ ] Free SSL checker tool page (standalone, ranks on Google)
- [ ] Submit to AlternativeTo
- [ ] Submit to G2
- [ ] Plan Product Hunt launch (week 3)

---

## Progress Summary

| Phase | Days | Status |
|-------|------|--------|
| 1. Core Engine | 1-4 | ✅ Complete |
| 2. Status Pages & Billing | 5-8 | 🔲 Not started |
| 3. Launch Prep | 9-10 | 🔲 Not started |
| 4. Post-Launch | 11-14 | 🔲 Not started |

**Current Day: 4** · **Current Phase: 1**

---

## 🔧 Domain & Email Setup ✅
- [x] Point `statusrooster.com` DNS to Cloud Run (4x A records)
- [x] Map custom domain in Cloud Run (`gcloud run domain-mappings create`)
- [x] SSL certificate provisioned (automatic via Cloud Run) — verified ✅ `https://statusrooster.com/health` → 200
- [x] SendGrid domain authentication (3x CNAME records validated)
- [x] Update `SENDGRID_FROM_EMAIL` to `alerts@statusrooster.com`
- [x] Email forwarding: catch-all `*@statusrooster.com` → `gjbangerter@gmail.com` (Namecheap)
- [x] Test email delivery end-to-end (confirmed inbox delivery, not spam!)
- [x] Update `APP_URL` env var to `https://statusrooster.com`
