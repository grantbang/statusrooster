# StatusRooster Build Tracker 🐓

**Start:** Feb 25, 2026 · **Target Launch:** Mar 7, 2026

---

## Phase 1: Core Engine — Days 1-4

### Day 1 — Scaffolding & Auth �
- [x] FastAPI project structure (`app/`, `routers/`, `services/`, `templates/`, `static/`)
- [x] `requirements.txt` + `Dockerfile` + `.dockerignore`
- [x] Config/settings module (loads `.env`)
- [x] Firestore client singleton
- [x] User model + Firestore CRUD (create, get by email, get by ID)
- [x] Auth: signup endpoint (email + password, bcrypt hash)
- [x] Auth: login endpoint (verify password, return JWT)
- [x] Auth: JWT middleware (protect routes, extract current user)
- [ ] Base Jinja2 template (`base.html` — nav, footer, block content)
- [ ] Health check endpoint (`/health`)
- [ ] Deploy skeleton to Cloud Run (app starts, `/health` returns 200)

### Day 2 — Monitors & Check Engine 🔲
- [ ] Monitor model + Firestore CRUD (create, list by user, get, update, delete)
- [ ] Plan enforcement: free users capped at 5 monitors
- [ ] `POST /api/monitors` — create monitor (validate URL, generate slug)
- [ ] `GET /api/monitors` — list user's monitors
- [ ] `PUT /api/monitors/{id}` — update monitor
- [ ] `DELETE /api/monitors/{id}` — delete monitor + cleanup checks
- [ ] HTTP check function (GET with timeout, measure response_ms, capture status code)
- [ ] False positive prevention: retry once after 5s before marking down
- [ ] `POST /cron/check` — iterate all monitors, run checks, write results to Firestore
- [ ] Update monitor doc after each check (status, last_checked, response_ms, uptime%)
- [ ] Cloud Scheduler job: hits `/cron/check` every 60 seconds
- [ ] Cron auth: verify request comes from Cloud Scheduler (header or shared secret)

### Day 3 — Alerts & Incidents 🔲
- [ ] Incident model + Firestore CRUD (create, resolve, list by monitor)
- [ ] Status change detection: compare previous status vs current
- [ ] On UP→DOWN: create incident, trigger alerts
- [ ] On DOWN→UP: resolve incident (set `resolved_at`, calculate duration), send recovery alert
- [ ] Alert deduplication: don't re-alert for same ongoing incident
- [ ] SendGrid email alert (down notification — site, time, status code)
- [ ] SendGrid email alert (recovery notification — site, duration)
- [ ] Slack webhook alert (down + recovery, formatted message)
- [ ] Alert service abstraction (easy to add SMS later)
- [ ] Test with real SendGrid + Slack webhook

### Day 4 — Dashboard UI 🔲
- [ ] Signup page (`/signup` — form, validation, redirect to dashboard)
- [ ] Login page (`/login` — form, error states, redirect to dashboard)
- [ ] Auth cookie handling (set JWT in httpOnly cookie on login)
- [ ] Dashboard page (`/dashboard` — list all monitors with status indicators)
- [ ] Monitor status badges (🟢 Up / 🔴 Down / ⚪ Pending)
- [ ] Add monitor form (modal or inline — URL, name, alert settings)
- [ ] Edit monitor form (pre-filled, save changes)
- [ ] Delete monitor (confirmation prompt)
- [ ] Monitor detail view (response time chart — Chart.js, last 24h)
- [ ] Alert settings per monitor (email, Slack webhook URL)
- [ ] Flash messages (success/error feedback on actions)

**✅ Day 4 Checkpoint:** Sign up → add URL → see checks → get alert on down → see recovery.

---

## Phase 2: Status Pages & Billing — Days 5-8

### Day 5 — Public Status Pages 🔲
- [ ] Status page route: `GET /s/{slug}`
- [ ] Status page template: site name, current status, uptime bars (90 days)
- [ ] Uptime bar component (green/red/gray day-by-day blocks)
- [ ] Incident history list (last 10 incidents with timestamps + durations)
- [ ] "Powered by StatusRooster 🐓" footer with signup link
- [ ] User can toggle monitor public/private
- [ ] User can set/edit slug for their status page
- [ ] Status page works when logged out (public)

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

### Day 7 — Landing Page 🔲
- [ ] Marketing landing page (`/`)
- [ ] Hero section: headline, subhead, CTA button
- [ ] Features grid (6 features with icons)
- [ ] Pricing table (Free vs Pro, side-by-side)
- [ ] FAQ section (5-6 common questions)
- [ ] Footer (links, legal placeholder)
- [ ] Mobile responsive

### Day 8 — Polish 🔲
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
| 1. Core Engine | 1-4 | 🔲 Not started |
| 2. Status Pages & Billing | 5-8 | 🔲 Not started |
| 3. Launch Prep | 9-10 | 🔲 Not started |
| 4. Post-Launch | 11-14 | 🔲 Not started |

**Current Day: 1** · **Current Phase: 1**
