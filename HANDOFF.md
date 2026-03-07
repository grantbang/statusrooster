# Chat Handoff — Add/Edit Full-Page Forms QA

**Date:** March 7, 2026 (Launch Day)
**Last commit:** `9639fee` — "Replace Add/Edit modals with full-page forms"
**Branch:** `main` (up to date with `origin/main`)

---

## What Was Just Done

We replaced the old modal-based Add Monitor / Edit Monitor flows with **full-page forms** using a new `.mf-*` CSS design system. This was a significant UX overhaul.

### Files Changed (commit `9639fee`)

| File | Lines | What changed |
|------|-------|--------------|
| `app/templates/add_monitor.html` | 476 | **New file.** Full-page Add Monitor form extending `dashboard_base.html` |
| `app/templates/edit_monitor.html` | 515 | **Rewritten.** Was a basic `base.html` card; now full-page form with `dashboard_base.html`, `.mf-*` classes, collapsible advanced section |
| `app/templates/dashboard.html` | ~630 (was ~1053) | Removed ~420 lines of old modal HTML + JS. All `openModal()` references replaced with `<a href="/monitors/add">` links |
| `app/routers/pages.py` | 1371 | Added `GET /monitors/add` route (line 407) with `group_names`. Added `group_names` to `GET /monitors/{id}/edit` route (line 624) |
| `app/static/style.css` | 4531 | Added ~300 lines of `.mf-*` CSS at end of file (starts ~line 4227) |

### Architecture of the New Forms

Both forms use:
- **`.mf-layout`** — single-column (max-width 640px), padded bottom for sticky footer
- **`.mf-section`** — white card sections with 12px border-radius
- **`.mf-footer`** — fixed sticky submit bar at bottom (respects sidebar on desktop)
- **`.mf-collapse-toggle` / `.mf-collapse-content`** — collapsible Advanced Settings
- **`.mf-notify-row`** — notification channel rows (Email/Slack/Webhook) with Pro gating
- **`.mf-interval-wrap`** — range slider for check interval (Pro) or disabled (Free)

**Add form** (`add_monitor.html`):
- Type selector: `<select>` dropdown (HTTP, JSON/API, Heartbeat, SSL)
- `setMonitorType()` JS shows/hides sections + calls `syncFieldNames()` to swap `name` attributes
- URL section per type (httpSection, jsonApiSection, heartbeatSection, sslSection)
- Advanced: HTTP fields (status code, timeout, keyword builder, response threshold), JSON fields (status code, timeout, auth header, assertion builder), status page, paused toggle, maintenance windows

**Edit form** (`edit_monitor.html`):
- Read-only type badge (not changeable)
- Pre-populated values from `{{ monitor.* }}`
- Heartbeat: shows ping URL with copy button
- Advanced: same fields as add, plus slug with live preview, paused toggle
- Keyword builder: parses existing `keyword` value back into builder rows on load (`initKeywordBuilder()`)

### Routes

```
GET  /monitors/add          → add_monitor_page()    [pages.py:407]
POST /monitors/add          → add_monitor()         [pages.py:424]
GET  /monitors/{id}/edit    → edit_monitor_page()   [pages.py:611]
POST /monitors/{id}/edit    → edit_monitor_submit() [pages.py:634]
```

### POST handler details (`add_monitor`, lines 424-610)
- Reads all form fields including `monitor_type`, `group`, maintenance windows, JSON assertions, keyword
- Auto-prepends `https://` if URL doesn't start with `http://` or `https://`
- Plan enforcement: Free=5 monitors, Pro=250
- Public status page limit enforcement: Free=1, Pro=10
- Heartbeat: auto-generates `ping_url`, redirects with `heartbeat_created=1` query param (triggers dashboard modal)
- SSL: stores `https://{domain}` as URL for display

### POST handler details (`edit_monitor_submit`, lines 634-790)
- Reads form, validates ownership
- Builds `updates` dict, calls `update_monitor(db, monitor_id, updates)` with `merge=True`
- Handles: timeout clamping (1-60), heartbeat interval (60-86400), grace period (0-3600), SSL threshold (1-90)
- Pro-only: webhook_url, maintenance_windows, custom check_interval (60-300)
- Status page limit re-checked when toggling public ON

---

## What Needs Testing Now

This is launch day. These forms are the primary way users create and edit monitors. They need **exhaustive testing** across all 4 monitor types, both plans, and all form fields.

### Test Matrix — Add Monitor (`/monitors/add`)

**For each monitor type (HTTP, JSON/API, Heartbeat, SSL):**

1. **Type switching** — Select each type, verify correct sections show/hide:
   - HTTP: httpSection visible, advHttp visible, intervalSection visible
   - JSON/API: jsonApiSection visible, advJson visible, intervalSection visible
   - Heartbeat: heartbeatSection visible, intervalSection HIDDEN
   - SSL: sslSection visible, intervalSection visible

2. **Field name swapping** (`syncFieldNames`) — When switching types, verify `name` attributes are correct so the right fields POST:
   - HTTP → `url`, `expected_status_code`, `timeout` get `name` attrs
   - JSON/API → `json_url` gets `name="url"`, `json_expected_status` gets `name="expected_status_code"`, `json_timeout` gets `name="timeout"`
   - Heartbeat/SSL → `url` field loses `required`

3. **Required field validation** — Submit empty form, verify browser validation fires on required fields (url, name)

4. **URL auto-prefix** — Submit `www.google.com` (no protocol) → should auto-prepend `https://`

5. **Monitor creation per type:**
   - HTTP: url + name → creates, redirects to dashboard with success message
   - JSON/API: url + name + auth_header + assertions → creates correctly
   - Heartbeat: name only → creates, generates ping_url, shows heartbeat created modal on dashboard
   - SSL: domain + name → creates, stores `https://{domain}` as url

6. **Notifications section:**
   - Email row always checked+disabled, hidden input sends `user.email`
   - Slack: Free → disabled checkbox + PRO badge + upgrade link; Pro → toggle shows input
   - Webhook: same Pro gating as Slack

7. **Monitor interval:**
   - Free → disabled slider, locked at 5m, upgrade CTA
   - Pro → working slider 60-300s, display updates live

8. **Advanced settings:**
   - Collapse toggle works (arrow rotates, content slides open)
   - HTTP: expected status code, timeout, keyword builder, response threshold all render
   - JSON: expected status code, timeout, auth header, assertion builder all render
   - Keyword builder: add/remove rows, AND/OR toggles, syncs to hidden `keyword` input
   - Assertion builder: add/remove rows
   - Public status page checkbox → shows slug input
   - Start paused checkbox
   - Maintenance windows: Free → upgrade CTA; Pro → add/remove windows

9. **Group field:**
   - Datalist shows existing group names
   - Typed value saved on monitor doc

10. **Plan limits:**
    - Free: 6th monitor → redirect with error
    - Pro: 251st monitor → redirect with error
    - Public status page limits (Free=1, Pro=10)

### Test Matrix — Edit Monitor (`/monitors/{id}/edit`)

**For each existing monitor type:**

1. **Page loads correctly** — type badge shows, correct sections visible, values pre-populated
2. **All fields pre-populated** — url, name, group, alert_email, slack webhook, webhook_url, check_interval, expected_status_code, timeout, keyword, response_threshold_ms, ssl_domain, ssl_expiry_threshold_days, heartbeat_interval, heartbeat_grace_period, public, paused, slug, maintenance_windows, json_assertions, auth_header
3. **Heartbeat ping URL** — displays read-only with working Copy button
4. **Keyword builder initialization** — existing keyword value parsed back into builder rows (e.g. `Welcome AND !error` → 2 rows with AND join)
5. **JSON assertion pre-population** — existing assertions rendered as editable rows
6. **Maintenance windows** — existing windows rendered as editable rows (Pro only)
7. **Save changes** — all fields POST correctly, monitor updated in Firestore
8. **Slug preview** — typing in slug field updates the live preview URL
9. **Public toggle** → shows/hides slug group
10. **Paused toggle** → correctly sends `paused=true` or omits field
11. **Ownership check** — can't edit someone else's monitor (redirects)
12. **Back link** — goes to `/monitors/{id}` (monitor detail)

### Cross-cutting Tests

1. **Navigation:**
   - Dashboard "Add monitor" button → `/monitors/add`
   - Dashboard "Add monitor" row at bottom → `/monitors/add`
   - Empty state "Add your first monitor" → `/monitors/add`
   - Three-dot menu "Edit" → `/monitors/{id}/edit`
   - No remaining `openModal()` references anywhere

2. **Responsive/Mobile (<768px):**
   - Sidebar collapses
   - `.mf-footer` spans full width (no sidebar offset)
   - `.mf-submit` goes full-width
   - Sections don't overflow

3. **CSS audit:**
   - All `.mf-*` classes present in style.css (verified: 19+ matches starting line ~4227)
   - No broken styles or unstyled elements

4. **Flash messages** — success/error messages show on dashboard after create/edit

### Known Issues to Watch For

- **VS Code save conflicts** were a problem during development — files got emptied or reverted. Current files are verified correct as of commit `9639fee`.
- **`type="text"` on URL fields** (not `type="url"`) — intentional fix so URLs like `www.cnn.com` aren't rejected by browser validation.

---

## What's Next After QA (from TRACKER.md)

| Task | Status | Priority |
|------|--------|----------|
| 10E: timeout/basic-auth/HTTP-method fields | 🔲 Partially done (timeout exists, basic auth + HTTP method still missing) | Medium |
| 10F: Pro upsell polish | 🔲 | Low |
| 11B: Activity log / event timeline | 🔲 | Medium |
| 11C: Hardening (404/500 pages, meta, favicon, mobile) | 🔲 | High |
| 11D: Admin dashboard | 🔲 | Medium |
| Day 12: Testing & launch | 🟡 Today | 🔴 Critical |

---

## Dev Environment

```bash
cd /Applications/statusrooster
source venv/bin/activate
uvicorn app.main:app --reload --port 8080
```

- Test user: `testaccount1@statusrooster.com` (plan: pro)
- Local Firestore uses production data
- App URL: `http://localhost:8080`
- Dashboard: `http://localhost:8080/dashboard`
- Add monitor: `http://localhost:8080/monitors/add`
- Edit monitor: `http://localhost:8080/monitors/{id}/edit`
