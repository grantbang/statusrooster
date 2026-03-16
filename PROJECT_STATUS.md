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
