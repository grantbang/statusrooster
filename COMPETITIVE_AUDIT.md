# StatusRooster vs UptimeRobot — Competitive Audit

> **📋 Punch list merged into `TRACKER.md`** (Phase 3, Days 10-12 + Phase 4 v1.1). This document is the detailed analysis — the tracker is where work gets checked off.

**Date:** March 2, 2026  
**Method:** Side-by-side screenshot comparison of live UptimeRobot account vs StatusRooster  
**Goal:** Identify high-value gaps to close, skip what doesn't fit our product.

**Legend:**
- 🟢 We have this (or better)
- 🟡 Easy win (< 30 min)
- 🔴 Important gap (needs real work)
- ⚪ Skip (doesn't fit our product/positioning)

---

## 1. Dashboard (UptimeRobot: "Monitors")

*Screenshots analyzed: 3 (default view, three-dot context menu, "+ New" dropdown)*

### Layout & Information Architecture
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Left sidebar nav | Persistent sidebar: Monitoring, Incidents, Status pages, Maintenance, Team members, Integrations & API | No sidebar nav — uses top-bar links only | 🟡 Add left nav sidebar for multi-page navigation | Medium |
| Monitor list format | Simple card-style rows — no table headers, clean and spacious | Full data table with headers, column toggles, sort indicators | 🟢 Our table is more powerful / data-rich | — |
| Right sidebar | Current status donut + Last 24h card | Same pattern: donut + Last 24h + Quick Actions | 🟢 Parity (we have extra Quick Actions card) | — |
| "Using X of Y" | Shows "Using 1 of 50 monitors" under donut | Shows "Using X of 5/250 monitors" | 🟢 Parity | — |
| Page title | "Monitors." with period — quirky branding touch | "Dashboard (N monitors)" | 🟢 Fine as-is, different branding | — |
| Upgrade CTA | Bottom-left corner green "Upgrade now" button, always visible | Inline "Upgrade" link next to plan badge + upgrade banner near limit | 🟢 Comparable — ours is more contextual | — |

### Data Shown per Monitor Row
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Status indicator | Green/red/yellow circle dot inline with name | Status pill (colored, gradient, first column) | 🟢 Our pills are more prominent | — |
| Monitor name | Bold text, clickable | Bold link text in Name column | 🟢 Parity | — |
| Type + uptime text | "HTTP · Up 17 min, 14 sec" below name — shows monitor type + how long in current state | No "uptime duration" display | 🟡 **Show "Up for X" / "Down for X" duration** | **High** |
| Check interval | Small "⏱ 5 min" inline | Interval badge column (60s / 5m) | 🟢 Parity | — |
| Uptime bar chart | **Mini sparkline bar chart** showing up/down history — green/red bars | No sparkline — just uptime % number | 🔴 **Add uptime sparkline / bar visualization** | **High** |
| Uptime percentage | "95.762%" next to sparkline | "XX.X%" in Uptime column | 🟢 Parity (we show fewer decimals — fine) | — |
| URL display | Not shown in list row | URL column with truncation | 🟢 We show more info | — |
| Response time | Not shown in list row | Response time column | 🟢 We show more info | — |
| Last checked | Not shown explicitly | "Checked" column with relative time | 🟢 We show more info | — |

### Actions Available
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| "+ New" button | Dropdown: Single monitor, Monitor wizard, Bulk upload, Group (PREMIUM) | Single "Add monitor" button opens modal | 🟡 **Add dropdown to "+ Add" button with monitor type options** (HTTP, keyword, ping) | Medium |
| Three-dot context menu | Per-row ⋯ menu: Add/Remove tags, Add to status page, Set notifications, Integrations, Interval & timeout, Cron job | No per-row context menu — row clicks navigate to detail | 🟡 **Add three-dot ⋯ context menu per row** with quick actions (pause/resume, edit, delete, copy URL) | **High** |
| Bulk actions | "Bulk actions ▾" dropdown in toolbar (appears when items selected) | Bulk bar appears below toolbar when items selected (pause/resume/delete) | 🟢 Parity | — |
| Search | Search by name or URL, inline in toolbar | Same — search input in toolbar | 🟢 Parity | — |
| Filter | "Filter" button + "Down first" sort dropdown | Filter dropdown (All/Up/Down/Paused/Pending) + metric pills for quick filter | 🟢 Our metric pill filters are arguably better UX | — |
| Sort | "Down first" dropdown (dedicated sort control) | Click column headers to sort | 🟢 Our sort is more flexible (any column) | — |
| Select all | Checkbox in toolbar row, shows "1/1" counter | Checkbox in thead, bulk bar shows count | 🟢 Parity | — |
| Tags / categorization | "Add / Remove tags" in context menu | No tagging system | ⚪ Skip — enterprise bloat, not high ROI for our positioning | — |
| Groups | "Move to Group" (PREMIUM) + "Show groups" button | No grouping | ⚪ Skip — enterprise feature | — |
| Status pages link | "Add to status page" in context menu | Public toggle in column selector | 🟢 Different approach, comparable | — |

### UX Patterns
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Row interaction | Click row → detail; ⋯ for quick actions | Click row → detail (same). No quick actions menu. | 🟡 See "three-dot menu" above | High |
| Dark theme | Dark charcoal background, consistent dark sidebar | Dark theme with indigo accents, glassmorphism sidebar | 🟢 Our styling is more distinctive | — |
| Empty state | Large empty area when few monitors | Add-monitor row in tfoot | 🟢 Ours is better — invites action | — |
| Monitor count | "0/1" in toolbar showing selected/total | Total in page title + metric pills | 🟢 Parity | — |
| Refresh | No visible refresh button | "↻ Refresh" button in toolbar | 🟢 We have more | — |
| Column customization | None — fixed columns | Full column selector dropdown with 17+ columns | 🟢 We're ahead | — |
| Export | Not visible on free dashboard | CSV/JSON export (Pro gated) | 🟢 We're ahead | — |

### 🏆 High-ROI Takeaways (Dashboard)

| # | Gap | Effort | Impact | Do it? |
|---|-----|--------|--------|--------|
| 1 | **"Up for 17min" / "Down for 2h" duration text** below monitor name | 🟡 ~20 min | High — immediate status context at a glance | ✅ Yes |
| 2 | **Uptime sparkline / bar chart** per row showing up/down history | 🔴 ~1-2 hours (need check history data) | High — the single most eye-catching UptimeRobot feature | ✅ Yes (simplified version) |
| 3 | **Three-dot ⋯ context menu** per row (pause, edit, delete, copy URL) | 🟡 ~30 min | High — reduces clicks for common actions | ✅ Yes |
| 4 | **Left sidebar navigation** (Monitoring, Incidents, Settings, API) | 🟡 ~45 min | Medium — proper app navigation for multi-page | 🤔 Maybe later |
| 5 | Tags / Groups | 🔴 hours | Low for indie/SMB positioning | ❌ Skip |
| 6 | Monitor wizard / Bulk upload | 🔴 hours | Low — niche feature | ❌ Skip |

---

## 2. Monitor Detail Page

*Screenshots analyzed: 2 (full page view, three-dot overflow menu)*

### Layout & Information Architecture
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Page header | Status dot + name + edit icon, "HTTP/S monitor for [url]" subtitle | Status dot + name, URL below | 🟢 Parity | — |
| Top action bar | Test Notification, Pause, Edit buttons + ⋮ overflow | Edit + Back buttons only | 🟡 **Add Pause + Test Notification buttons to header** | **High** |
| ⋮ overflow menu | Edit, Integrations, Maintenance, Tags, Status page, Clone, Move to Group, Pause, Reset stats, Delete (red) | No overflow menu | 🟡 **Add ⋮ menu with: Delete, Clone, Reset stats** | Medium |
| Top stat cards | 3 cards across: Current Status, Last Check, Last 24h sparkline | 8 stat cards in grid (uptime, response, checks, fails, code, last checked, interval, created) | 🟢 We show more data — could reorganize for hierarchy though | — |
| Right sidebar | 5 cards: Domain & SSL, Next maintenance, Regions, To be notified, Appears on | No sidebar on detail page | 🟡 **Add sidebar with SSL + alert config cards** (reuse data we already have) | Medium |
| Breadcrumb | "← Monitoring" back link | "Back" button in header | 🟢 Comparable | — |

### Data / Charts
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Current status card | "Up" + "Currently up for 0h 28m 28s" — **duration in current state** | Banner: "Currently up" (no duration) | 🟡 **Add duration to status banner** ("Up for 2h 15m") | **High** |
| Last check card | "3m, 23s ago" + "Checked every 5m" + **"Get 60 sec. checks" upsell link** | "Last Checked" stat card shows time | 🟡 **Add Pro upsell to check interval on Free** | **High** |
| Last 24h card | Uptime % + **sparkline bar chart** + "1 incident, 1h down" summary | Uptime % stat card only | 🔴 **Add 24h sparkline + incident count summary card** | **High** |
| Multi-period uptime | **Last 7d, 30d, 365d, custom range** — shows uptime % + incident count per period | Single lifetime uptime % only | 🔴 **Add multi-period uptime row** (7d / 30d / 90d) | **High** |
| Response time chart | Line chart + time range selector (Last hour / 6h / 24h / 7d / 30d) + Avg/Min/Max stats below | Line chart (Last 24h only), no range picker, no summary stats | 🟡 **Add time range picker + Avg/Min/Max stats below chart** | **High** |
| "Setup alerts" CTA | In-context "Setup alerts for slow response times" link above chart | No in-context alert CTA | 🟡 **Add CTA to set threshold if none configured** | Medium |
| MTBF | Shown in multi-period row with time range selector | Shown only in dashboard sidebar 24h card | 🟢 We have it, just in different location | — |

### Right Sidebar Cards (UptimeRobot)
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Domain & SSL | Shows domain validity + SSL cert validity + "Unlock" upsell | SSL section exists but only shows if data present | 🟢 Parity (ours conditional, theirs always shows) | — |
| Next maintenance | "No maintenance planned" + "Set up maintenance" CTA | Maintenance windows shown in Advanced Monitoring section | 🟢 Different approach, comparable | — |
| Regions | World map graphic showing check region ("North America") | Not shown | ⚪ Skip — we only check from one region currently | — |
| To be notified | User avatar showing who gets alerts | Alert Settings card shows email/slack/SMS | 🟢 Our approach is more detailed | — |
| Appears on | Status page attachment info | Public Status Page section with shareable link | 🟢 Parity | — |

### Actions Available
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Test Notification | Dedicated button in header | "Send test alert" in Alert Settings card (below fold) | 🟡 **Move test alert to header for visibility** | Medium |
| Pause | Dedicated button in header | Only in Edit form | 🟡 **Add Pause/Resume toggle to detail header** | **High** |
| Edit | Button in header + in ⋮ menu | Button in header | 🟢 Parity | — |
| Delete | In ⋮ menu (red, bottom) | Only in Edit form | 🟡 Add to ⋮ menu | Low |
| Clone monitor | In ⋮ menu | Not available | ⚪ Skip — nice-to-have but low ROI | — |
| Reset stats | In ⋮ menu | Not available | ⚪ Skip — rarely used | — |
| Export logs | "Export logs" button in incidents section | Not available | 🟡 Could add later | Low |

### Incidents Section
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Incidents table | Columns: Status, Root Cause (shows HTTP code badge), Started, Duration | List format: status + monitor name + time + duration | 🟢 Comparable — different layout | — |
| Root cause display | Shows "405 Method Not Allowed" badge | Shows status code in incident list | 🟢 Parity | — |
| "That's all, folks!" | Whimsical empty state | "No incidents recorded yet." | 🟢 Fine — different tone | — |

### 🏆 High-ROI Takeaways (Monitor Detail)

| # | Gap | Effort | Impact | Do it? |
|---|-----|--------|--------|--------|
| 1 | **"Up for 2h 15m" duration in status banner** | 🟡 ~15 min | High — matches dashboard duration text, key UX signal | ✅ Yes |
| 2 | **Pause/Resume button in detail header** | 🟡 ~15 min | High — currently buried in edit form | ✅ Yes |
| 3 | **Multi-period uptime row (7d / 30d / 90d)** | 🔴 ~1 hr (needs Firestore query for historical checks) | High — the thing power users look at first | ✅ Yes |
| 4 | **Response chart time range picker + Avg/Min/Max** | 🟡 ~30 min (data already exists in checks) | High — our chart is already there, just needs controls | ✅ Yes |
| 5 | **Pro upsell on check interval** ("Get 60s checks →") | 🟡 ~10 min | Medium — monetization opportunity on every Free detail page | ✅ Yes |
| 6 | Clone monitor / Reset stats / Regions map | 🔴 hours | Low — niche features | ❌ Skip |

---

## 3. Monitor Add/Edit

*Screenshots analyzed: 4 (edit form top half, advanced settings bottom half, Integrations & Team tab, Maintenance info tab)*

### Form Fields Comparison
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| URL | Text input | Text input | 🟢 Parity | — |
| Friendly name | Inline "Rename" link | Text input | 🟢 Parity | — |
| Alert email | Checkbox "E-mail" + shows address | Text input for email | 🟢 Parity | — |
| Slack webhook | Not inline — via "Integrations & Team" tab | Text input (Pro gated) | 🟢 Ours is simpler — inline config | — |
| SMS / Voice / Push | Checkbox options with phone number links | "Coming soon" label | 🟢 Fine — we're honest about scope | — |
| Keyword check | Not visible in edit form (may be elsewhere) | Text input with AND/OR support | 🟢 **We're ahead** — inline keyword config | — |
| Response threshold | "Slow response time alert" toggle + ms input — **paid only** | Text input with >, <, range syntax — available to all | 🟢 **We're ahead** — available to Free users too | — |
| Webhook URL | Via Integrations tab | Inline text input (Pro gated) | 🟢 Ours is simpler | — |
| Maintenance windows | Separate "Maintenance info" tab | Inline day/time rows (Pro gated) | 🟢 Ours is simpler — single-page form | — |
| Public toggle | Not in edit — via "Add to status page" menu | Checkbox + slug input | 🟢 **We're ahead** — simpler workflow | — |
| Paused toggle | Not in edit — via header "Pause" button | Checkbox in edit form | 🟢 Parity (different location) | — |

### Advanced Settings (UptimeRobot has, we don't)
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Request timeout | Slider 1s–60s (default 30s) | Hardcoded (no user control) | 🟡 **Add timeout field** (simple input, default 30s) | **High** |
| Follow redirections | Toggle (on by default) | Not configurable (always follows) | ⚪ Skip — following redirects is correct default | — |
| HTTP method | HEAD/GET/POST/PUT/PATCH/DELETE/OPTIONS — paid methods beyond HEAD/GET | Not configurable (always GET) | 🟡 **Add HTTP method selector** (GET/HEAD/POST) | Medium |
| Auth credentials | None/Basic/Digest + username/password | Not available | 🟡 **Add Basic Auth fields** (username/password) | **High** |
| Custom status codes | "Up HTTP status codes" chip selector (2xx, 3xx) — paid | Not configurable | ⚪ Skip — our default (2xx = up) is fine | — |
| Request body | JSON body field — paid | Not available | ⚪ Skip — niche, POST monitoring is rare | — |
| IPv4/IPv6 | Dropdown selector | Not configurable | ⚪ Skip — IPv4 default is fine | — |
| Monitor interval slider | Visual slider 30s–24h | Plan-enforced: 60s Pro, 5m Free (no user choice) | 🟢 Our approach is cleaner — plan-based, no confusion | — |
| Region selector | Dropdown — paid only | Not available (single region) | ⚪ Skip — post-launch v1.1 item | — |
| SSL/Domain checks | 3 toggles (errors, expiry, domain) — paid | Automatic for all HTTPS monitors | 🟢 **We're ahead** — auto-detect, no toggle needed | — |
| Groups | Dropdown — paid | Not available | ⚪ Skip — enterprise feature | — |
| Tags | Tag input field | Not available | ⚪ Skip — enterprise bloat | — |

### UX / Layout
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Form layout | Full-page form, scrollable sections, collapsible "Advanced settings" | Single card form, sections with dividers | 🟢 Comparable | — |
| Right sidebar tabs | "Monitor details / Integrations & Team / Maintenance info" — 3 separate tab pages | No tabs — everything inline on one page | 🟢 **We're ahead** — less navigation, less confusion | — |
| Notification config | Per-channel with "delay, no repeat" settings | Simple email/slack/webhook fields | 🟡 **Add alert delay / repeat config** (e.g. "wait 2 checks before alerting") | Medium |
| Save button | Green "Save changes" at bottom | "Save changes" button | 🟢 Parity | — |
| Upsell placement | Inline "Upgrade now" links next to locked features throughout | Greyed-out inputs with "Upgrade to Pro" links | 🟢 Comparable approach | — |

### "Integrations & Team" Tab (UptimeRobot)
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Team notifications | "Notify team members" section — search by name/email, Manage button. **Paywalled**: "Available in Team and Enterprise plans. Plans start at $7/month." | Single alert email field + Slack webhook (Pro) | 🟢 Our approach is simpler — no team features needed for indie/SMB | — |
| Integrations | "Connect integrations" section — Slack, MS Teams, Telegram, Webhooks. **Paywalled**: "Manage integrations" button, "Solo, Team and Enterprise" | Slack webhook inline + generic webhook URL, both in edit form | 🟢 **We're ahead** — our integrations are inline, not buried in a separate tab behind a paywall | — |
| Overall impression | Two big upsell cards on a mostly-empty page | Everything configured inline in one form | 🟢 **We're significantly ahead here** — UptimeRobot Free users see two paywalls. Our Free users get email alerts working out of the box, and see Slack/webhook as clear Pro upsells inline. | — |

### "Maintenance Info" Tab (UptimeRobot)
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Maintenance setup | "Setup planned maintenance period" — **fully paywalled**: "Plans start at $7/month", "See plans" CTA | Inline maintenance window rows (day picker + time range) — Pro gated but visible | 🟢 **We're ahead** — our Pro users configure maintenance inline. UptimeRobot sends you to a separate page and locks the whole thing. | — |
| Maintenance description | "Keep your uptime untouched with scheduled regular or unplanned maintenance. During maintenance windows, no alerts are sent." | Same behavior — maintenance windows suppress alerts | 🟢 Parity in concept | — |

### 🏆 High-ROI Takeaways (Add/Edit)

| # | Gap | Effort | Impact | Do it? |
|---|-----|--------|--------|--------|
| 1 | **Request timeout field** (input, default 30s) | 🟡 ~15 min | High — users with slow APIs need this | ✅ Yes |
| 2 | **Basic Auth fields** (username/password) | 🟡 ~20 min | High — needed for staging/internal site monitoring | ✅ Yes |
| 3 | **HTTP method selector** (GET/HEAD/POST) | 🟡 ~15 min | Medium — HEAD is lighter, POST for APIs | ✅ Yes |
| 4 | Alert confirmation threshold ("wait N fails before alerting") | 🟡 ~20 min | Medium — reduces false positive alerts | 🤔 Maybe |
| 5 | Tags / Groups / Region / IPv6 / Custom status codes | 🔴 hours | Low ROI | ❌ Skip |

---

## 4. Incidents List Page

*Screenshots analyzed: 3 (full incidents page, sort dropdown, filter dropdown)*

**Key finding: We don't have a dedicated Incidents page.** Our incidents only appear as a panel on the dashboard (time-filtered: 24h/3d/7d/All) and in each monitor's detail page. UptimeRobot has a full standalone page at `/incidents`.

### Layout & Features
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Dedicated /incidents page | Full standalone page with title "Incidents." | **No dedicated page** — incidents only in dashboard panel + monitor detail | 🟡 **Add /incidents page** | **High** |
| Table columns | Status, Monitor, Root Cause, Comments, Started, Resolved, Duration, Visibility | Dashboard panel: indicator + monitor name + status badge + time + duration | 🟡 Reuse data we already query, just needs a page | — |
| Search | "Search by name or url" | No incident search | 🟡 Add search to incidents page | Medium |
| Tag filter | "All tags" dropdown | No tags (skipped) | ⚪ Skip | — |
| Sort options | Started (Newest/Oldest), Resolved (Newest/Oldest), Longest first, Shortest first | Dashboard panel has 24h/3d/7d/All time filter only | 🟡 **Add sort controls** | Medium |
| Filter (root cause) | Checkbox filter: Resolved, Ongoing, Time/Out, 2xx, 3xx, 4xx, 5xx, DNS resolving issue, Assertion failed, Invalid JSON, Slow response + Reset | No root cause filtering | 🟡 **Add status + root cause filter** | Medium |
| Export | Export button (top right icon) | Not available for incidents | 🟡 Add later | Low |
| Root cause badges | Color-coded HTTP code badge (e.g. "405 Method Not Allowed") | Status code shown as text | 🟡 **Add root cause badges** (color-coded) | Low |
| Comments count | "0" comments column | No comments on incidents | ⚪ Skip — overkill for our positioning | — |
| Visibility | "Included" column (relates to uptime calculation) | Not shown | ⚪ Skip — niche | — |
| IP Allowlist banner | Blue info banner: "Possible IP Allowlist Issue — ensure our new IPs are allowlisted" | No similar banner | ⚪ Skip — infrastructure concern | — |

### 🏆 High-ROI Takeaways (Incidents)

| # | Gap | Effort | Impact | Do it? |
|---|-----|--------|--------|--------|
| 1 | **Dedicated /incidents page** — full table with all incidents across monitors | 🟡 ~45 min (data layer exists, need template + route) | High — it's a top-level nav item, users expect it | ✅ Yes |
| 2 | **Sort + filter controls** on incidents page | 🟡 ~20 min (reuse toolbar pattern from dashboard) | Medium — power users want to slice incidents | ✅ Yes |
| 3 | Comments / Visibility / Tags on incidents | 🔴 hours | Low — enterprise bloat | ❌ Skip |

---

## 5. Incident Detail Page

*Screenshots analyzed: 1 (full incident detail page with activity log)*

**This is one of UptimeRobot's strongest pages. The Activity Log is a killer feature for post-mortems.**

### Layout & Information Architecture
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Dedicated incident detail page | Full page at `/incidents/{id}` | **No incident detail page** — incidents shown as list items only | 🔴 **Add /incidents/{id} detail page** | **High** |
| Header | "Resolved incident on {monitor}" + status dot + monitor type + breadcrumb | N/A | 🔴 Part of building the page | — |
| Action bar | "Go to monitor" + "Download response" + ⋮ menu | N/A | 🟡 "Go to monitor" link is easy | — |

### Data Shown
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Root cause card | Large prominent card: "405 Method Not Allowed" | Status code shown inline in incident list | 🟡 **Show root cause prominently** — HTTP code + human-readable text | **High** |
| Status + timestamps | "Resolved" with start timestamp | We store started_at and resolved_at | 🟢 Data exists, just needs display | — |
| Duration card | "1h 1m 2s" with resolved timestamp | We compute duration_seconds | 🟢 Data exists | — |
| **Activity log / timeline** | **Full chronological timeline**: detection → multi-region confirmation → alert sent (SUCCESS badge) → resolved → recovery alert sent | **We don't log alert events or detection steps** | 🔴 **Add incident event log** — at minimum: detected, alert sent, resolved, recovery sent | **High** |
| Multi-region confirmation | "Detected by Ohio, USA: 3.20.63.178" → "Confirmed by N. Virginia" → "Confirmed by Ashburn" — shows IP addresses | Single-region checks, no confirmation chain | ⚪ Skip for now — requires multi-region (v1.1) | — |
| Alert delivery status | "Email sent to Grant Bangenter SUCCESS" with green badge | We send alerts but don't log delivery status | 🟡 **Log alert send events** (email sent, Slack sent, with success/fail) | **High** |

### Right Sidebar
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Request info | URL tab: "HEAD https://statusrooster.com" + Headers tab | Not shown | 🟡 **Show request URL + method** | Medium |
| Response info | Body tab + Headers tab — shows raw JSON response headers | Not stored | 🟡 **Store + show response headers/body snippet** on incident | Medium |
| Download response | Button to download full response | Not available | ⚪ Skip — niche debugging feature | — |

### Comments
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Incident comments | "Collaborate with ease, comment incidents" — **Paywalled at $29/mo Team plan** | Not available | ⚪ Skip — enterprise/team feature, high cost for low indie ROI | — |

### 🏆 High-ROI Takeaways (Incident Detail)

| # | Gap | Effort | Impact | Do it? |
|---|-----|--------|--------|--------|
| 1 | **Incident detail page** (`/incidents/{id}`) with root cause, status, duration, timestamps | 🟡 ~30 min (data already in Firestore) | High — currently no way to drill into an incident | ✅ Yes |
| 2 | **Activity log / event timeline** — detected, alert sent (email/slack), resolved, recovery sent | 🔴 ~1 hr (need to log events to incident sub-collection) | **Very High** — this is the post-mortem feature that makes a monitoring tool feel professional | ✅ Yes |
| 3 | **Alert delivery logging** — record when email/slack was sent + success/fail | 🟡 ~20 min (add to alert functions, store in incident events) | High — "did the alert actually fire?" is a common user question | ✅ Yes |
| 4 | Request/response display on incident | 🟡 ~20 min (store during check, show on page) | Medium — useful for debugging | 🤔 Maybe |
| 5 | Comments on incidents | 🔴 hours | Low — team feature, $29/mo on UptimeRobot | ❌ Skip |

---

## 6. Integrations & API

*Screenshots analyzed: 5 (Chat Platforms, Webhooks, Connectors & Incident Mgmt, Push Notifications, API)*

**Key finding: This is where UptimeRobot paywalls HARD. Almost everything is locked behind Solo ($7/mo), Team, or Enterprise plans. We should NOT try to match breadth here — just ensure our existing integrations feel polished.**

### Page Layout
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Dedicated /integrations page | Full standalone page with left sub-nav (5 tabs) + search | **No dedicated page** — integrations are inline in edit form | 🟢 **Our inline approach is better for indie/SMB** — no hunting through a separate page | — |
| Search bar | "Search by integration type..." | N/A (only 2 integrations: Slack + Webhook) | ⚪ Skip — we don't have enough integrations to need search | — |
| Sub-navigation | Chat platforms · Webhooks · Connectors & Incident mgmt · Push notifications · API | N/A | ⚪ Skip — unnecessary complexity for our scale | — |

### Chat Platforms Tab
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Slack | Listed — **Paywalled**: "Available only in Solo, Team and Enterprise. Upgrade now" | ✅ Slack webhook URL field in edit form (Pro gated) | 🟢 **We're ahead** — our Pro users paste a URL and go. No separate integrations page needed. | — |
| Telegram | Listed — **Paywalled** at Solo+ | Not available | ⚪ Skip — niche. Slack covers 90% of chat notification needs. | — |
| Discord | Listed — **Free!** "+ Add" button available | Not available | 🟡 Discord webhook is trivial (same format as Slack — just POST to URL) | Low |
| Mattermost | Listed — **Paywalled** at Solo+ | Not available | ⚪ Skip — enterprise self-hosted chat | — |
| MS Teams | Listed — **Paywalled** at Solo+ | Not available | ⚪ Skip — enterprise | — |
| Google Chat | Listed — **Free!** "+ Add" button | Not available | ⚪ Skip — low adoption for indie/SMB | — |

### Webhooks Tab
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Webhook | Listed — **Paywalled at Team+** ($29/mo) | ✅ Webhook URL field in edit form (Pro gated at $9/mo) | 🟢 **We're significantly ahead** — they charge $29/mo for webhooks, we include it in Pro at $9/mo | — |

### Connectors & Incident Management Tab
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Zapier | Listed — **Paywalled at Team+** | Not available | ⚪ Skip — webhook is functionally equivalent for Zapier users (they can receive webhooks) | — |
| PagerDuty | Listed — **Paywalled at Team+** | Not available | ⚪ Skip — enterprise on-call, not our market | — |
| Splunk | Listed — **Free!** "+ Add" button | Not available | ⚪ Skip — observability enterprise tool | — |

### Push Notifications Tab
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Android / iOS app | "Download" buttons — native mobile apps | No mobile app | ⚪ Skip — building a native app is months of work, zero ROI right now | — |
| Pushbullet | Listed — **Free** "+ Add" | Not available | ⚪ Skip — dying platform | — |
| Pushover | Listed — **Free** "+ Add" | Not available | ⚪ Skip — niche power user tool | — |

### API Tab
| Element | UptimeRobot | StatusRooster | Gap | Priority |
|---------|-------------|---------------|-----|----------|
| Main API keys | "Main API key" + "Read-only API key" with "+ Create" buttons + link to API docs | No public API | 🟡 Future consideration — not launch priority | Low |
| Monitor-specific API keys | Per-monitor read-only API keys with search | N/A | ⚪ Skip — power user / CI-CD feature | — |
| MCP (AI integration) | "Connect AI assistants to your UptimeRobot monitors using natural language" — "Get Started" button | Not available | 🟡 Interesting but not launch priority | Low |
| API documentation | Link to full API docs | N/A | ⚪ Skip for now | — |

### 🏆 High-ROI Takeaways (Integrations & API)

**Bottom line: We're in great shape here. UptimeRobot locks almost everything behind paywalls. Our inline approach is simpler and more user-friendly.**

| # | Gap | Effort | Impact | Do it? |
|---|-----|--------|--------|--------|
| 1 | **Discord webhook** (just another URL field, same as Slack) | 🟢 ~15 min (add field to edit form + send function) | Low-medium — nice "we support more channels" checkbox | 🤔 Maybe post-launch |
| 2 | **Public API** (read-only monitor status endpoint) | 🔴 ~2-4 hrs | Medium — power users & CI/CD want this | 🔲 v1.1 |
| 3 | **MCP / AI integration** | 🔴 hours | Low — novelty, not a purchase driver | ❌ Skip |
| 4 | Native mobile app | 🔴 weeks/months | Low ROI now | ❌ Skip |
| 5 | Telegram / Mattermost / MS Teams / PagerDuty | 🔴 hours each | Low — enterprise integrations | ❌ Skip |

**🚨 Caution: This is exactly where scope creep lives. Every integration is "just one more URL field" but the support + documentation + testing burden adds up fast. Stick with Email + Slack + Webhook for launch. That covers 95% of indie/SMB needs.**

---

## Summary — Prioritized Punch List

| # | Gap | Page | Priority | Est. | Status |
|---|-----|------|----------|------|--------|
| 1 | "Up for X" / "Down for X" duration text | Dashboard + Detail | 🟡 High ROI | 20 min | 🔲 |
| 2 | Uptime sparkline bar chart per row | Dashboard | 🔴 High ROI | 1-2 hrs | 🔲 |
| 3 | Three-dot ⋯ context menu per row (pause, edit, delete, copy URL) | Dashboard | 🟡 High ROI | 30 min | 🔲 |
| 4 | Pause/Resume button in detail header | Detail | 🟡 High ROI | 15 min | 🔲 |
| 5 | Multi-period uptime row (7d / 30d / 90d) | Detail | 🔴 High ROI | 1 hr | 🔲 |
| 6 | Response chart time range picker + Avg/Min/Max stats | Detail | 🟡 High ROI | 30 min | 🔲 |
| 7 | Pro upsell on check interval ("Get 60s checks →") | Detail | 🟡 Medium | 10 min | 🔲 |
| 8 | Left sidebar navigation | All pages | 🟡 Medium | 45 min | 🔲 |
| 9 | Multi-region checks (US, EU, Asia) — Pro feature | Checker | 🔴 Post-launch | Days | 🔲 v1.1 |
| 10 | Request timeout field (default 30s) | Add/Edit | 🟡 High ROI | 15 min | 🔲 |
| 11 | Basic Auth fields (username/password) | Add/Edit | 🟡 High ROI | 20 min | 🔲 |
| 12 | HTTP method selector (GET/HEAD/POST) | Add/Edit | 🟡 Medium | 15 min | 🔲 |
| 13 | Dedicated /incidents page with full table | Incidents | 🟡 High ROI | 45 min | 🔲 |
| 14 | Sort + filter controls on incidents page | Incidents | 🟡 Medium | 20 min | 🔲 |
| 15 | Incident detail page (`/incidents/{id}`) | Incident Detail | 🟡 High ROI | 30 min | 🔲 |
| 16 | Activity log / event timeline on incident detail | Incident Detail | 🔴 **Very High ROI** | 1 hr | 🔲 |
| 17 | Alert delivery logging (email/slack sent + success/fail) | Alerts + Incidents | 🟡 High ROI | 20 min | 🔲 |
| 18 | Discord webhook (optional, post-launch) | Add/Edit | ⚪ Low | 15 min | 🔲 v1.1 |
| 19 | Public read-only API | API | ⚪ Low | 2-4 hrs | 🔲 v1.1 |
| | *(Status Pages audit still pending)* | | | | |

