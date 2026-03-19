# StatusRooster — Project Status Tracker

**Last updated:** 2026-03-14

---

## Build Phases (v2 Implementation)

All core build phases are complete. These delivered the product from scratch.

| Phase | Name | Status |
|-------|------|--------|
| Phase 2 | Multi-Region Monitoring | DONE |
| Phase 6 | Infrastructure Hardening | DONE |
| Phase 1 | Free Tier Unlocking | DONE |
| Phase 4 | Custom Branding | DONE |
| Phase 3 | Data Retention | DONE |
| Phase 7 | Viral Loop | DONE |

### Remaining build items
- [x] **3.6** Schedule `/cron/cleanup` in Cloud Scheduler (daily 3am UTC)
- [ ] **Final verification** E2E tests, security, multi-region, plan enforcement (see IMPLEMENTATION_PLAN.md)

---

## Pre-Launch Polish Sprints

These sprints focus on UX polish, feature enrichment, and QA before public launch.

### Sprint 1: SSL Bug Fix + Template Quick Wins — DONE
- [x] 1.0 SSL monitor creation bug fix (`pages.py` line 629)
- [x] 1.1 Status code badge in monitor detail header
- [x] 1.2 HTTP method badge in URL display
- [x] 1.3 Group name in breadcrumb
- [x] 1.4 Group badge on dashboard cards
- [x] 1.5 Ongoing incident elapsed timer
- [x] 1.6 Incident severity color-coding
- [x] 1.7 "Up for X" status duration on dashboard

### Sprint 2: Chart Enhancements — DONE
- [x] 2.1 Response threshold line (dashed red line at threshold_ms)
- [x] 2.2 Per-region response time overlay (toggle button, color-coded lines per region)
- [x] 2.2b Checks API returns `response_ms_by_region` for chart data

### Sprint 3: Incident Enrichment — DONE
- [x] 3.1 Failed check count on incident detail page
- [x] 3.2 Failed regions on incident detail page ("X/Y regions UP")

### Sprint 4: UX Audit — DONE
- [x] 4.1 Loading states (chart spinner, bulk action button disable during request)
- [x] 4.2 Empty states (chart empty overlay, region section hidden when no data)
- [x] 4.3 Mobile responsiveness (375px/480px/768px breakpoints, action button wrapping, toolbar wrapping)
- [x] 4.4 Accessibility (focus-visible on all buttons/pills/menus, aria-labels on search/status dots, keyboard nav on monitor cards, aria-hidden on decorative SVGs)

### Sprint 5: Mobile Optimization — DONE
Deep mobile polish pass across all pages (480px + 375px breakpoints):
- [x] Landing page (hero, feature checklist, versus cards, pricing cards, URL checker)
- [x] Dashboard (cards, filters, toolbar, uptime bars, context menu)
- [x] Monitor detail (action buttons, chart, stats grid, incidents table)
- [x] Add/Edit monitor forms (inputs, selects, toggle groups)
- [x] Incidents list + detail (grid, timeline, region table)
- [x] Settings (plan card, forms, API keys table)
- [x] Status pages (public-facing)
- [x] API docs + request builder
- [x] Pricing page

### Sprint 6: CI/CD Pipeline — DONE
GitHub Actions for automated test + deploy:
- [x] GitHub Actions workflow (`.github/workflows/deploy.yml`)
- [x] On PR: run E2E + functional tests
- [x] On push to main: test → build → deploy primary to Cloud Run
- [x] Smart worker deploy: only if `checker_core/` or `worker/` changed
- [x] GCP Workload Identity Federation (keyless auth from GitHub)
- [x] GitHub secrets: `SR_API_KEY`, GCP project config
- [ ] Slack/email notification on deploy failure (optional)

### Sprint 7: Manual QA Plan — NOT STARTED
Full manual QA checklist covering:
- [ ] Auth flows (signup, login, OAuth, logout, redirects)
- [ ] Dashboard (filters, sort, context menu, bulk actions, uptime bars)
- [ ] Add/Edit monitor (all 4 types, validation, optional fields)
- [ ] Monitor detail (all sections, chart, check now, pause/resume)
- [ ] Incidents (list, detail, timeline, region corroboration)
- [ ] Status pages (single, aggregate, branding, free vs pro)
- [ ] Settings (timezone, API keys, branding)
- [ ] Responsive testing (4 breakpoints)
- [ ] API testing (auth, CRUD, plan enforcement, response shape)
- [ ] Integration testing (multi-region, alerts, SSL, heartbeat, incident lifecycle)

### Sprint 7.5: Load / Stress Test — NOT STARTED
Validate the system handles real-world scale before launch.

**Phase A — Baseline (100 monitors, 1 free user):**
- [ ] Create a dedicated test user for load testing
- [ ] Script to bulk-create 100 HTTP monitors (hitting various public endpoints)
- [ ] Let run for 10 minutes (~10 check cycles)
- [ ] Measure: cron cycle duration (from Cloud Run logs), worker batch response times
- [ ] Measure: Firestore reads/writes per cycle (GCP console → Firestore usage tab)
- [ ] Measure: Cloud Run CPU/memory usage
- [ ] Verify: all 100 monitors show correct status, uptime bars populating, no timeouts
- [ ] Verify: dashboard loads in <3 seconds with 100 cards

**Phase B — Pro scale (500 monitors, 1 pro user):**
- [ ] Upgrade test user to pro (or mock plan), create 500 monitors
- [ ] Let run for 10 minutes
- [ ] Measure: same metrics as Phase A
- [ ] Watch for: `/cron/check` approaching 60-second cycle time (overlap = missed checks)
- [ ] Watch for: worker timeouts on large batches
- [ ] Verify: dashboard still usable, filters/search responsive

**Phase C — Multi-user (1,000 monitors, 10 users):**
- [ ] Create 10 test users with 100 monitors each
- [ ] Let run for 10 minutes
- [ ] Measure: cron cycle duration (this is the key metric — must stay under 55s)
- [ ] Measure: total Firestore ops and estimated daily cost
- [ ] Verify: each user's dashboard loads correctly, no cross-user data leaks
- [ ] Verify: incidents fire correctly when a monitor goes down

**Phase D — Cleanup & report:**
- [ ] Delete all test monitors and test users
- [ ] Document: cycle time at each scale, cost projections, any bottlenecks found
- [ ] If cron cycle > 45s at 1,000 monitors: flag for architecture review (batch splitting, parallel dispatch)

**Cost guard rails:**
- [ ] Check GCP billing dashboard before, during, and after each phase
- [ ] Set a billing alert at $10/day as a safety net
- [ ] Each phase runs only 10 minutes — estimated cost <$1 total

### Sprint 8: Incident Region Corroboration — DONE
- [x] Checker stores per-region `status_code` and `error` in aggregation
- [x] Incident model accepts `region_results` and `failure_response_body`
- [x] Incident detail timeline shows "Confirmed down from X/Y regions"
- [x] Collapsible per-region table (region, status, code, time, error)
- [x] Response body preview section (truncated to 2048 bytes)
- [x] Incident events include region metadata

### Sprint 9: Admin Dashboard — DONE
- [x] GCP cost tracking via BigQuery billing export (real data only, no estimates)
- [x] Manual cost CRUD (add/delete non-trackable expenses)
- [x] Revenue tab with MRR/ARPU/ARR KPIs
- [x] Stripe webhook event logging (`checkout.session.completed`, `customer.subscription.deleted`, `invoice.payment_succeeded`)
- [x] BigQuery billing export enabled in GCP Console (awaiting data backfill)

### Sprint 10: Settings & Profile Enhancement — DONE
- [x] Two-column settings layout with sticky section nav + scroll-spy
- [x] Profile section (display name, read-only email with auth provider badge, member since)
- [x] Password change (email-auth only, with validation)
- [x] Notification preferences (default alert email, recovery toggle, weekly digest toggle)
- [x] Danger zone — account deletion (email confirmation, JS confirm, Stripe cancellation, full data cleanup)
- [x] Sidebar avatar clickable, shows display name when set
- [x] Recovery alerts respect user `alert_on_recovery` preference
- [x] QA walkthrough updated with settings test cases

### Sprint 11: Auto-Discovery — NOT STARTED
Scan a domain to auto-discover endpoints and bulk-create monitors.

**Backend (`app/services/discovery.py`):**
- [ ] Fetch /sitemap.xml, parse `<loc>` tags
- [ ] Fetch /robots.txt, follow `Sitemap:` directives
- [ ] Crawl homepage — extract same-domain `<a href>` links (regex/html.parser, no BeautifulSoup)
- [ ] Probe common paths: /api/health, /api/v1, /api/status, /graphql, /.well-known/security.txt, /login, /signup, /dashboard
- [ ] Auto-detect SSL cert info for domain
- [ ] Deduplicate, cap at 50 URLs
- [ ] Each URL includes: url, source (sitemap/crawl/probe), suggested priority (high/medium/low)
- [ ] Graceful failure handling (bot detection, timeouts, 404s — never crash)
- [ ] httpx with 10s timeout, follow redirects, realistic User-Agent + Accept/Accept-Language headers
- [ ] Detect Cloudflare/bot challenge pages (403 + challenge HTML) — treat as "blocked" not "down", surface in status message

**API endpoints:**
- [ ] `POST /api/v1/discover` — authenticated, full results
- [ ] `POST /api/discover-preview` — unauthenticated, rate-limited (5/min per IP), capped at 20 URLs
- [ ] `POST /api/v1/monitors/bulk` — bulk-create monitors from discovery results

**Frontend (`/discover` page, 3 states):**
- [ ] State 1 — Input: domain input, "Scan for endpoints" button
- [ ] State 2 — Results: checkbox list of URLs with source badges, "Monitor selected (N)" CTA, select all/deselect all
- [ ] State 3 — Empty/Error: friendly message, link to manual add
- [ ] Sidebar nav entry with sparkle/wand icon after "Add Monitor"
- [ ] Dashboard empty-state: "Or scan your domain to auto-discover endpoints" link

**Tests (`TestDiscovery` in test_e2e.py):**
- [ ] POST /api/v1/discover with statusrooster.com → 200, returns URLs
- [ ] POST /api/v1/discover with invalid domain → 200, empty urls with status message
- [ ] POST /api/v1/discover without API key → 401
- [ ] POST /api/discover-preview → 200
- [ ] POST /api/discover-preview rate limit → 429 after 5 rapid requests

---

## Infrastructure Status

| Item | Status | Notes |
|------|--------|-------|
| Primary app (us-east1) | Deployed | `statusrooster` on Cloud Run |
| Worker us-west1 | Deployed | `statusrooster-worker` |
| Worker europe-west1 | Deployed | `statusrooster-worker` |
| Worker asia-east1 | Deployed | `statusrooster-worker` |
| Firestore | Live | Production, same for local dev |
| Cloud Scheduler | Live | `/cron/check` every minute |
| Cron cleanup | SCHEDULED | `statusrooster-cleanup` daily 3am UTC |
| BigQuery billing export | Enabled | Table exists, awaiting data backfill (~24-48h) |
| SendGrid (email alerts) | Live | |
| Stripe billing | Live | Webhook endpoint active |
| Custom domain | Live | statusrooster.com |

---

## Test Suites

| Suite | Tests | Last Status |
|-------|-------|-------------|
| E2E (`test_e2e.py`) | 80+ | Need to re-run after recent changes |
| Functional (`test_functional.py`) | 38 | Passing (as of Sprint 6/7 work) |
| API docs accuracy | 24 | Passing |

---

## Key Decisions & Constraints

- **No estimates/guesses** — only show real, factual data from actual sources
- **No frontend frameworks** — SSR Jinja2 only, JS for charts/AJAX only
- **Free tier is generous** — 100 monitors, 60s checks, all alert channels except SMS
- **Deploy workers only when `checker_core/` or `worker/` changes** — primary-only otherwise
- **Worker service name** — `statusrooster-worker` (NOT `sr-worker`)
