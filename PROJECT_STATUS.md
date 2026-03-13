# StatusRooster — Project Status Tracker

**Last updated:** 2026-03-13

---

## Build Phases (v2 Implementation)

All core build phases are complete. These delivered the product from scratch.

| Phase | Name | Status |
|-------|------|--------|
| Phase 2 | Multi-Region Monitoring | DONE |
| Phase 6 | Infrastructure Hardening | DONE |
| Phase 1 | Free Tier Unlocking | DONE |
| Phase 4 | Custom Branding | DONE |
| Phase 3 | Data Retention | DONE (scheduling pending — 3.6) |
| Phase 7 | Viral Loop | DONE |

### Remaining build items
- [ ] **3.6** Schedule `/cron/cleanup` in Cloud Scheduler (daily 3am UTC)
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

### Sprint 3: Incident Enrichment — NOT STARTED
- [ ] 3.1 Failed check count on incident detail page
  - Backend: query checks where `is_up == False` during incident window
  - Template: add "Failed Checks" row to details grid
- [ ] 3.2 Failed regions on incident detail page
  - Backend: store `regions_checked`/`regions_up` on incident creation
  - Template: show "2/4 regions UP" in details grid

### Sprint 4: UX Audit — NOT STARTED
- [ ] 4.1 Loading states (chart spinner during range switch, bulk action disable)
- [ ] 4.2 Empty states (chart with no checks, hide region section when no data)
- [ ] 4.3 Mobile responsiveness (test at 375px, 768px, 1024px, 1440px)
- [ ] 4.4 Accessibility (aria-labels on dots, role/tabindex on clickable elements, chart labels)

### Sprint 5: Manual QA Plan — NOT STARTED
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

### Sprint 6: Incident Region Corroboration — DONE
- [x] Checker stores per-region `status_code` and `error` in aggregation
- [x] Incident model accepts `region_results` and `failure_response_body`
- [x] Incident detail timeline shows "Confirmed down from X/Y regions"
- [x] Collapsible per-region table (region, status, code, time, error)
- [x] Response body preview section (truncated to 2048 bytes)
- [x] Incident events include region metadata

### Sprint 7: Admin Dashboard — DONE
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
| Cron cleanup | NOT SCHEDULED | Need to add `/cron/cleanup` daily job |
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
