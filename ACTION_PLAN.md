# StatusRooster — Day 10 Action Plan

> **⚠️ SUPERSEDED:** This document has been reconciled into `TRACKER.md` (Phase 3, Days 10-12). The tracker is the single source of truth for what to build and in what order. This file is kept for historical context and the detailed feature reconciliation matrix below.

**Date:** March 1, 2026  
**Goal:** Full feature reconciliation, Pro upsell strategy, dashboard rebuild, inline editing, keyword builder, GitHub OAuth.

---

## Overview

Six workstreams, in priority order:

| # | Workstream | What | Est. |
|---|-----------|------|------|
| 0 | GitHub OAuth | Register app, set env vars — code is done | 10 min |
| 1 | Feature Reconciliation | Hard audit: every field across Firestore → API → UI → Checker → Pricing | 20 min |
| 2 | Roadmap/Tracker Update | Update TRACKER.md to reflect actual state after audit | 10 min |
| 3 | Pro Upsell Strategy | Design & implement Pro selling points *inside* the app itself | 30 min |
| 4 | Dashboard Rebuild — Data Table | Replace card grid with sortable/filterable/exportable data table | 90 min |
| 5 | Inline Editing + Keyword Builder | Edit from table rows, keyword expression builder UI | 60 min |

---

## 0. GitHub OAuth

**Status:** Code is 100% done. Routes, callbacks, account linking, login/signup buttons — all built.

**What exists:**
- `app/routers/oauth.py` — full Google + GitHub OAuth flows (redirect → callback → create/find user → JWT cookie)
- `app/config.py` — `GITHUB_CLIENT_ID` + `GITHUB_CLIENT_SECRET` env vars ready
- `app/templates/login.html` + `signup.html` — "Continue with GitHub" buttons already in UI
- `app/models/user.py` — `create_oauth_user()` + `auth_provider` field

**What's needed:**
1. Register a GitHub OAuth App at https://github.com/settings/developers
   - App name: `StatusRooster`
   - Homepage URL: `https://statusrooster.com`
   - Callback URL: `https://statusrooster.com/auth/github/callback`
2. Copy Client ID + Client Secret
3. Set env vars locally in `.env`:
   ```
   GITHUB_CLIENT_ID=...
   GITHUB_CLIENT_SECRET=...
   ```
4. Set env vars on Cloud Run:
   ```
   gcloud run services update statusrooster --region us-east1 \
     --set-env-vars GITHUB_CLIENT_ID=...,GITHUB_CLIENT_SECRET=...
   ```
5. Test: click "Continue with GitHub" on login page → authorize → land on dashboard

**Files to change:** None (just env vars)

---

## 1. Feature Reconciliation Audit

**This is the hard stop.** Map every single monitor attribute across all 5 layers. No gaps left unaccounted for.

### The 5 Layers

1. **Firestore** — what's stored in the `monitors` collection
2. **API** — what `POST/PUT /api/v1/monitors` accept and return
3. **Dashboard UI** — what Add Modal shows, what the table/cards display
4. **Edit UI** — what the edit form exposes
5. **Checker** — what the cron engine reads/writes
6. **Pricing page** — what we *promise* customers

### Monitor Attributes — Complete Matrix

| # | Attribute | Firestore | API Create | API Update | API Response | Add Modal | Dashboard | Edit Form | Detail Page | Checker | Pricing Claims |
|---|-----------|-----------|------------|------------|--------------|-----------|-----------|-----------|-------------|---------|---------------|
| 1 | `url` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (card) | ✅ | ✅ | ✅ reads | — |
| 2 | `name` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (card) | ✅ | ✅ | — | — |
| 3 | `status` | ✅ | — auto | — | ✅ | — | ✅ (dot) | — | ✅ | ✅ sets | — |
| 4 | `check_interval` | ✅ (60) | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | hardcoded | **"5min Free / 60s Pro"** |
| 5 | `uptime_percent` | ✅ | — auto | — | ✅ | — | ✅ (card) | — | ✅ | ✅ sets | — |
| 6 | `checks_total` | ✅ | — auto | — | ✅ | — | ❌ | — | ✅ | ✅ sets | — |
| 7 | `checks_failed` | ✅ | — auto | — | ✅ | — | ❌ | — | ❌ | ✅ sets | — |
| 8 | `last_checked` | ✅ | — auto | — | ✅ | — | ❌ | — | ❌ | ✅ sets | — |
| 9 | `last_status_code` | ✅ | — auto | — | ✅ | — | ❌ | — | ✅ | ✅ sets | — |
| 10 | `last_response_ms` | ✅ | — auto | — | ✅ | — | ✅ (card) | — | ✅ | ✅ sets | — |
| 11 | `alert_email` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | — | — |
| 12 | `alert_slack_webhook` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | — | **"Slack = Pro"** but not gated |
| 13 | `alert_sms` | ✅ ("") | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | "coming soon" | — | **"SMS = Pro"** but not built |
| 14 | `keyword` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (badge) | ✅ | ✅ | ✅ | — |
| 15 | `response_threshold_ms` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | — |
| 16 | `webhook_url` | ✅ | ✅ Pro | ✅ Pro | ✅ | ✅ greyed | ❌ | ✅ greyed | ✅ | ✅ | "Webhooks = Pro" ✅ |
| 17 | `ssl_expiry` | ✅ | — auto | — | ✅ | — | ✅ (badge) | — | ✅ | ✅ sets | — |
| 18 | `ssl_issuer` | ✅ | — auto | — | ✅ | — | ❌ | — | ✅ | ✅ sets | — |
| 19 | `ssl_expiry_days` | ✅ | — auto | — | ❌ | — | ❌ | — | ✅ | ✅ sets | — |
| 20 | `maintenance_windows` | ✅ | ✅ Pro | ✅ Pro | ✅ | ✅ greyed | ❌ | ✅ greyed | ✅ | ✅ | "Maint. = Pro" ✅ |
| 21 | `public` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | — | — |
| 22 | `paused` | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | — |
| 23 | `slug` | ✅ | — auto | ❌ | ✅ | — | ❌ | ✅ | ✅ | — | — |
| 24 | `created_at` | ✅ | — auto | — | ✅ | — | ❌ | — | ❌ | — | — |

### Gap Analysis — By Severity

**🔴 CRITICAL (breaks promises or features):**

| Gap | Problem | Fix |
|-----|---------|-----|
| `paused` not functional | API Update accepts it but: not in Firestore default, not in Create API, no UI anywhere, checker doesn't skip | Add to model, Create API, Add/Edit UI, checker `if paused: skip` |
| Check interval not enforced | All monitors run at 60s regardless of plan. Pricing says Free=5min, Pro=60s | Checker: skip if `last_checked` < interval for plan. Set `check_interval` based on plan |
| Slack not gated to Pro | Free users can set Slack webhook and receive alerts. Pricing says Slack = Pro | Gate in checker/alerts + grey out in UI for Free |

**🟡 IMPORTANT (data in API but invisible in UI):**

| Gap | Fix |
|-----|-----|
| `checks_failed` not on detail page | Add to stats grid |
| `last_checked` not on dashboard or detail | Add "Last Checked: 2m ago" to both |
| `created_at` not on detail page | Add to detail page |
| `ssl_expiry_days` not in API response | Add to serializer |
| `slug` not in API Update | Add to `ApiUpdateMonitor` schema |
| `public` not in Add modal | Add toggle |
| 12 attributes not on dashboard | Solved by data table with column selector (Workstream 4) |

**🟢 NICE TO HAVE (deferred):**

| Gap | Status |
|-----|--------|
| SMS / `alert_sms` | Listed on pricing, not built. Needs Twilio. Defer to post-launch |
| Domain expiry | Backlog |

### Fixes to Implement (ordered)

| # | Fix | Files | Priority |
|---|-----|-------|----------|
| 1 | Add `paused` field to Firestore model default | `monitor.py` | 🔴 |
| 2 | Add `paused` to API Create schema | `api_v1.py` | 🔴 |
| 3 | Checker: skip paused monitors entirely | `checker.py` | 🔴 |
| 4 | Checker: enforce check interval per plan | `checker.py` | 🔴 |
| 5 | Gate Slack alerts to Pro in alerts service | `alerts.py` | 🔴 |
| 6 | Add `paused` toggle to Add modal + Edit form | `dashboard.html`, `edit_monitor.html` | 🔴 |
| 7 | Add `public` toggle to Add modal | `dashboard.html` | 🟡 |
| 8 | Add `slug` to API Update schema | `api_v1.py` | 🟡 |
| 9 | Add `ssl_expiry_days` to API serializer | `api_v1.py` | 🟡 |
| 10 | Add `last_checked`, `created_at`, `checks_failed` to detail page | `monitor_detail.html` | 🟡 |

---

## 2. Roadmap / Tracker Update

After implementing the reconciliation fixes, update `TRACKER.md`:

- Mark Day 10 items complete as we go
- Update "What's NOT gated yet" section — remove items we fix
- Add new items discovered during audit
- Update "Current Day" marker
- Log this session's commits

---

## 3. Pro Upsell Strategy

**Goal:** Make the free tier feel complete but *visibly limited*. Every Pro feature should be a constant, tasteful reminder that more is available. The app itself should sell Pro.

### Current State — Where We Upsell Today

| Location | What | Format |
|----------|------|--------|
| Dashboard header | "Upgrade to Pro" button | Button (Free users only) |
| Dashboard banner | "4 of 5 monitors" warning | Yellow banner (≥4 monitors) |
| Add Modal — Webhook | Greyed-out input | Disabled field + "Upgrade to Pro" link |
| Add Modal — Maintenance | Greyed-out fields | Disabled fields + "Upgrade to Pro" link |
| Edit Form — Webhook | Greyed-out input | Disabled field + "Upgrade to Pro" link |
| Edit Form — Maintenance | Greyed-out fields | Disabled fields + "Upgrade to Pro" link |
| Settings page | "Free · Upgrade to Pro" | Text link |
| Pricing page | Feature comparison table | Full page |
| Landing page | Pricing section | Cards |

### What's Missing — Pro Upsell Opportunities

**Dashboard (biggest opportunity — users see it every day):**

| Opportunity | Implementation |
|-------------|---------------|
| **Check interval badge** | Show "⏱ 5min" badge on each monitor card/row for Free users, with tooltip "Upgrade to Pro for 60-second checks" |
| **Paused monitors limit** | When Free user tries to have >5 monitors, show inline "Unlock 250 monitors with Pro" |
| **Column restrictions** | In column selector, show Pro-only columns (Webhook, Maintenance, Slack) greyed with lock icon + "Pro" badge |
| **Export restrictions** | Export button shows "Export to CSV — Pro" with upgrade prompt for Free users |
| **Bulk actions** | Bulk pause/resume available to all, but bulk export is Pro |

**Monitor Detail Page:**

| Opportunity | Implementation |
|-------------|---------------|
| **60s vs 5min chart** | Show "Checking every 5 minutes" for Free with "Get 60-second checks →" link |
| **Webhook section** | Show greyed "Webhook Notifications" section with Pro badge and upgrade CTA |
| **Maintenance section** | Show greyed "Maintenance Windows" section with Pro badge |
| **Slack/SMS** | If not configured AND Free, show "Add Slack alerts (Pro)" with upgrade link instead of "Not configured" |

**Alert Emails (passive upsell in every alert):**

| Opportunity | Implementation |
|-------------|---------------|
| **Email footer** | Add "Upgrade to Pro for 60s checks, Slack alerts, and webhooks → statusrooster.com/pricing" footer to Free user alert emails |

**API Docs:**

| Opportunity | Implementation |
|-------------|---------------|
| **Pro badges** | Already showing "(Pro)" on webhook/maintenance fields ✅ |
| **Rate limit hint** | Add "Free: 100 req/hr · Pro: 1000 req/hr" to auth section |

### Design Principles for Upselling

1. **Show, don't hide** — Free users see *all* features, but Pro ones are greyed/locked with a clear path to upgrade
2. **Contextual** — upsell appears at the moment the user wants the feature, not randomly
3. **Non-annoying** — no popups, no banners that block content. Inline hints and disabled fields only
4. **Consistent visual language** — Pro features always show:
   - Indigo `#6366f1` "Pro" badge
   - `opacity: 0.5` + `cursor: not-allowed` on disabled inputs
   - Small indigo "Upgrade to Pro →" link below the field
5. **One-click upgrade** — every upsell point links directly to `/api/billing/checkout` (Stripe), not to the pricing page

### Implementation Plan

| # | Upsell Point | Where | How |
|---|-------------|-------|-----|
| 1 | Check interval badge on dashboard rows | `dashboard.html` | `⏱ 5min` badge per row, tooltip with upgrade link |
| 2 | Greyed Pro columns in column selector | `dashboard.html` | Lock icon + "Pro" on Webhook/Maintenance/Slack columns |
| 3 | Export = Pro only | `dashboard.html` | Export button shows upgrade prompt for Free |
| 4 | Detail page — interval hint | `monitor_detail.html` | "Checking every 5 min · Upgrade for 60s →" |
| 5 | Detail page — greyed webhook/maint/slack sections | `monitor_detail.html` | Show sections for Free but greyed with CTA |
| 6 | Alert email footer | `alerts.py` | Append upgrade line to Free user emails |
| 7 | Paused toggle — Pro badge in Add modal | `dashboard.html` | Show toggle but hint "Pause/resume anytime" |
| 8 | Gate Slack input for Free in Add modal | `dashboard.html` | Grey out like webhook, add upgrade link |

---

## 4. Dashboard Rebuild — Data Table

**Current state:** Card grid. Shows: name, URL, status dot, uptime %, response ms, keyword badge, SSL badge. No filtering, no sorting, no export.

**Target:** Proper data table. Technical. Dense. Every attribute available.

### Table Design

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Dashboard (5 monitors)  Pro          [Search...] [Filter ▾] [Columns ▾] [⤓ Export]│
│                                                                [+ Add monitor]  │
├────┬────┬──────────┬────────────────────┬────────┬────────┬─────────┬───────────┤
│ ☐  │ ⏱  │ Name ▲   │ URL                │ Status │ Uptime │ Resp ms │ Checked   │
├────┼────┼──────────┼────────────────────┼────────┼────────┼─────────┼───────────┤
│ ☐  │ 60s│ My Site  │ example.com        │ ● Up   │ 99.8%  │ 245     │ 2m ago    │
│ ☐  │ 60s│ API      │ api.example.com    │ ● Up   │ 100%   │ 89      │ 2m ago    │
│ ☐  │ 5m │ Blog     │ blog.example.com   │ ● Down │ 98.1%  │ —       │ 1m ago    │
│ ☐  │ 5m │ Staging  │ staging.example.com│ ⏸ Psd  │ 100%   │ 120     │ Paused    │
└────┴────┴──────────┴────────────────────┴────────┴────────┴─────────┴───────────┘
  [3 selected: Pause | Resume | Delete]
```

### Columns — Full List

| Column | Default On | Pro Only | Sortable | Notes |
|--------|-----------|----------|----------|-------|
| ☐ (checkbox) | ✅ | — | — | Bulk select |
| ⏱ (interval) | ✅ | — | — | "60s" or "5m" — Free users see "5m ⚡" with upgrade hint |
| Name | ✅ | — | ✅ | Click → detail page |
| URL | ✅ | — | ✅ | Truncated, full on hover |
| Status | ✅ | — | ✅ | ● Up / ● Down / ⏸ Paused / ○ Pending |
| Uptime % | ✅ | — | ✅ | Color coded: green >99, yellow >95, red <95 |
| Response ms | ✅ | — | ✅ | — |
| Last Checked | ✅ | — | ✅ | Relative time "2m ago" |
| Keyword | Off | — | — | Shows expression or "—" |
| Threshold | Off | — | — | Shows condition or "—" |
| SSL Expiry | Off | — | ✅ | Date + days left, color coded |
| SSL Issuer | Off | — | — | — |
| Alert Email | Off | — | — | — |
| Slack | Off | 🔒 greyed for Free | — | "Connected" / "—" |
| Webhook | Off | 🔒 greyed for Free | — | URL or "—" |
| Maint. Windows | Off | 🔒 greyed for Free | — | Count or "—" |
| Public | Off | — | — | ✅/— |
| Slug | Off | — | — | — |
| Created | Off | — | ✅ | Date |
| Checks Total | Off | — | ✅ | — |
| Checks Failed | Off | — | ✅ | — |
| Actions | ✅ | — | — | ⋯ menu: Edit, Pause, Delete, Detail |

### Features

**Filtering:**
- Search box: instant filter by name or URL (client-side)
- Filter dropdown: All, Up, Down, Paused, Pending, Has Keyword, Has Threshold, Public
- Active filter shown as pill/chip with ✕ to clear

**Sorting:**
- Click column header → sort asc → click again → desc → click again → clear
- Sort indicator arrow ▲/▼ in header

**Column Selector:**
- Dropdown with checkboxes for each column
- Pro-only columns shown with lock 🔒 for Free users (clicking shows upgrade prompt)
- Saved to localStorage

**Bulk Actions:**
- Header checkbox = select all visible
- When ≥1 selected, show bulk action bar: Pause | Resume | Delete (with confirm)
- Needs new endpoint: `POST /monitors/bulk` accepting `{action, monitor_ids}`

**Export:**
- Dropdown: CSV, JSON
- Free users: "Export — Pro only" with upgrade prompt
- Pro: exports filtered/visible data

**Row Actions (⋯ menu):**
- Edit (opens inline panel — see Workstream 5)
- Pause / Resume (instant toggle via AJAX)
- Delete (confirm → AJAX)
- View Detail (→ `/monitors/{id}`)

### Files to Change

| File | Change |
|------|--------|
| `dashboard.html` | Full rewrite: table, columns JS, filter, search, sort, export, bulk |
| `style.css` | Data table styles, dropdown menus, bulk bar, responsive |
| `pages.py` | Bulk action endpoint, pause/resume endpoint |

---

## 5. Inline Editing + Keyword Expression Builder

### 5a. Inline Editing

**Instead of navigating to `/monitors/{id}/edit`:**

- Click Edit in row ⋯ menu → row expands to show inline edit panel
- Panel shows editable fields in a compact grid layout
- Each field saves independently via AJAX
- Toggles (public, paused) save instantly on click
- Pro-only fields (webhook, maintenance, Slack) greyed with upgrade prompt for Free

**AJAX endpoint:** `POST /monitors/{id}/inline-update` — session-auth, accepts JSON `{field: value}`, returns `{ok: true, monitor: {...}}`.

**Edit panel layout:**
```
┌──────────────────────────────────────────────────────────────┐
│ ✎ Editing: My Website                              [Close ✕]│
├─────────────────────┬────────────────────────────────────────┤
│ Name                │ [My Website          ] [Save]          │
│ URL                 │ [https://example.com ] [Save]          │
├─────────────────────┼────────────────────────────────────────┤
│ Alert Email         │ [me@example.com      ] [Save]          │
│ Slack Webhook  Pro  │ [greyed / url         ] [Save]         │
│ Webhook URL   Pro   │ [greyed / url         ] [Save]         │
├─────────────────────┼────────────────────────────────────────┤
│ Keyword             │ [Builder | Raw]  [Save]                │
│ Response Threshold  │ [> 2000              ] [Save]          │
│ Maint. Windows Pro  │ [+ Add window] [Save]                  │
├─────────────────────┼────────────────────────────────────────┤
│ Public              │ [Toggle ●]  Slug: [my-website] [Save]  │
│ Paused              │ [Toggle ○]                             │
└─────────────────────┴────────────────────────────────────────┘
```

### 5b. Keyword Expression Builder

**Current state:** Raw text input. User types `Welcome AND Login` manually.

**Target:** Simple builder with toggle between modes.

**Builder mode:**
```
┌──────────────────────────────────────────────────┐
│ Keyword Check        [Builder ▪ | Raw ○]         │
│                                                  │
│  [Welcome          ] AND ▾  [✕]                  │
│  [Login            ] AND ▾  [✕]                  │
│  [Dashboard        ]        [✕]                  │
│                                                  │
│  [+ Add condition]                               │
│                                                  │
│  Preview: Welcome AND Login AND Dashboard        │
└──────────────────────────────────────────────────┘
```

**Raw mode:**
```
┌──────────────────────────────────────────────────┐
│ Keyword Check        [Builder ○ | Raw ▪]         │
│                                                  │
│  [Welcome AND Login OR error               ]     │
│  Hint: AND / OR operators supported              │
└──────────────────────────────────────────────────┘
```

- Builder auto-generates the string into a hidden `<input name="keyword">`
- Switching from Raw → Builder parses the string back into rows
- No backend changes — same string format

**Files to change:**
| File | Change |
|------|--------|
| `dashboard.html` | Builder UI in Add modal + inline edit panel |
| `edit_monitor.html` | Builder UI (fallback edit page) |
| `style.css` | Builder row styles |

---

## Execution Order

```
Step 0: GitHub OAuth credentials                (~10 min)
   └─ Register GitHub app, set env vars, test login

Step 1: Feature Reconciliation Fixes            (~30 min)
   ├─ paused: model + API + checker + UI
   ├─ check interval enforcement in checker
   ├─ gate Slack to Pro
   ├─ slug in API Update
   ├─ ssl_expiry_days in API response
   ├─ public toggle in Add modal
   └─ missing fields on detail page

Step 2: Pro Upsell Implementation              (~20 min)
   ├─ Check interval badge on dashboard rows
   ├─ Greyed Pro columns in column selector
   ├─ Detail page Pro section CTAs
   ├─ Gate Slack input for Free users
   └─ Alert email upgrade footer

Step 3: Dashboard Rebuild — Data Table         (~90 min)
   ├─ Table HTML structure
   ├─ Column system + localStorage
   ├─ Sorting (click headers)
   ├─ Filtering (dropdown + search)
   ├─ Export (CSV/JSON, Pro-gated)
   ├─ Bulk actions (select, pause, delete)
   └─ Row action menu

Step 4: Inline Editing + Keyword Builder       (~60 min)
   ├─ AJAX inline-update endpoint
   ├─ Expand-row edit panel
   ├─ Per-field save buttons
   ├─ Toggle saves (public, paused)
   ├─ Keyword expression builder UI
   └─ Pro field gating in edit panel

Step 5: Roadmap Update + Test                  (~15 min)
   ├─ Update TRACKER.md
   ├─ Full UI walkthrough
   └─ API consistency check

Step 6: Commit + Deploy                        (~5 min)
```

**Total estimate: ~4 hours**

---

## Out of Scope (deferred to Day 11+)

- SMS/Twilio integration (needs account + phone number)
- Admin dashboard (Day 11)
- Telemetry/event tracking (Day 11)
- Automated tests (Day 11)
- Google OAuth consent screen: Testing → Production (Day 11)
