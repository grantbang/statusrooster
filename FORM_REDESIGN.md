# Add / Edit Monitor Form Redesign — Checklist

> **Goal**: Redesign the Add Monitor and Edit Monitor pages from the current flat, all-inline look into a polished, sectioned layout inspired by UptimeRobot — but made our own. The current layout reads "AI-generated" because every field is stacked identically in plain white cards with no visual hierarchy, grouping, or breathing room. The redesign organizes fields into logical **card sections** with clear headings, uses a clean 2-column grid inside sections where it makes sense, adds subtle visual polish (section icons, better spacing, pro badges), and makes the whole experience feel hand-crafted.

**Rules**:
- No new JS frameworks (React, Vue, HTMX, Alpine) — vanilla JS only
- No external CSS frameworks (Tailwind, Bootstrap) — all CSS goes in `style.css`
- Keep `.mf-*` prefix for all new CSS classes
- SSR-first — Jinja2 templates only
- Backend model (`monitor.py`) already has `http_method`, `basic_auth_user`, `basic_auth_pass` params — we expose them on the form now
- Edit form must preserve backward compatibility — existing monitors must render correctly

---

## FILES TO CHANGE

| File | What Changes |
|------|-------------|
| `app/templates/add_monitor.html` | Full rewrite of form layout/structure |
| `app/templates/edit_monitor.html` | Full rewrite of form layout/structure |
| `app/static/style.css` | Replace/extend `.mf-*` section (~lines 4230–4540) |
| `app/routers/pages.py` | Parse new fields: `http_method`, `basic_auth_user`, `basic_auth_pass`, `follow_redirects` |
| `app/models/monitor.py` | Already has `http_method`, `basic_auth_user`, `basic_auth_pass` — add `follow_redirects` field |

---

## DESIGN PRINCIPLES (our take, not a copy)

1. **Sectioned cards** — Each logical group (URL, notifications, interval, advanced) lives in its own bordered card with a section title and a small inline SVG icon
2. **Two-column fields** where natural (e.g., timeout + status code side by side, username + password side by side) — using a `.mf-field-row` flex grid
3. **Section icons** — Small muted SVG next to section titles for scanability
4. **Pro gating** is visually clear — locked sections show a subtle overlay + upgrade link, not just disabled inputs
5. **Collapsible Advanced Settings** — keep the existing `mf-collapse-toggle` pattern but auto-open it on Edit if the monitor has advanced values set
6. **Consistent hint text** — every field gets a helpful `.hint` subtext
7. **Sticky footer** — keep the existing `.mf-footer` pattern
8. **Type switcher** — keep select dropdown on Add, read-only badge on Edit (existing pattern works)

---

## CHECKLIST

### Phase 1: CSS Foundation
- [ ] **1.1** Add `.mf-section-header` — flex row with icon + title (replaces plain `.mf-section-title`)
- [ ] **1.2** Add `.mf-field-row` — 2-column flex grid for side-by-side fields, stacks on mobile
- [ ] **1.3** Add `.mf-field-group` — wrapper for a single field in the grid (label + input + hint)
- [ ] **1.4** Add `.mf-pro-overlay` — subtle visual treatment for locked pro features (disabled state + badge)
- [ ] **1.5** Add `.mf-method-select` — HTTP method button group (HEAD/GET/POST/PUT/PATCH/DELETE/OPTIONS)
- [ ] **1.6** Add `.mf-toggle-row` — styled toggle/switch row for boolean settings (follow redirects, public, paused)
- [ ] **1.7** Add `.mf-auth-section` — auth type selector + credential fields
- [ ] **1.8** Refine existing `.mf-section` — slightly more padding, subtle left-border accent on hover
- [ ] **1.9** Refine `.mf-heading` — add subtitle support (`.mf-heading-sub`) for edit page to show monitor type

#### ✅ Phase 1 Gate — CSS Validation
- [ ] **1.T1** `grep` for every new class name in `style.css` — confirm all 9 classes exist and have rules
- [ ] **1.T2** Create a throwaway HTML snippet (or temporarily add to `add_monitor.html`) with one of each new class to confirm they render without errors — check browser DevTools for missing/overridden styles
- [ ] **1.T3** Verify no existing `.mf-*` classes were accidentally broken — load the current Add Monitor page and confirm it still renders identically (we haven't touched templates yet)

---

### Phase 2: Add Monitor Template (`add_monitor.html`)
Layout order (top to bottom):
- [ ] **2.1** Back link + heading (existing pattern, keep as-is)
- [ ] **2.2** **Section: Monitor Type** — type selector dropdown (existing, keep)
- [ ] **2.3** **Section: URL / Endpoint** — contextual per type:
  - HTTP: URL input with `https://` prefix hint
  - JSON/API: API endpoint input
  - Heartbeat: "How it works" info box (existing)
  - SSL: Domain input + threshold in a 2-column row
- [ ] **2.4** **Section: Friendly name + Group** — 2-column row (name required, group optional with datalist)
- [ ] **2.5** **Section: Notifications** — Email (always on) + Slack (Pro) + Webhook (Pro) using `.mf-notify-row`
- [ ] **2.6** **Section: Monitor Interval** — slider (Pro) or locked display (Free). Hidden for heartbeat type.
- [ ] **2.7** **Section: Advanced Settings** (collapsible) containing sub-sections per type:
  - HTTP: Request timeout + Expected status code (2-col row), HTTP method (button group), Follow redirects toggle, Basic Auth (type select → username/password 2-col), Keyword builder, Response threshold
  - JSON/API: Timeout + Expected status code (2-col), Auth header, JSON assertions builder, Response threshold
  - Heartbeat: (hidden — no advanced settings)
  - SSL: (hidden — settings already in main section)
- [ ] **2.8** **Section: Advanced Settings → Status Page** — Public toggle + slug field
- [ ] **2.9** **Section: Advanced Settings → Start Paused** — Paused toggle
- [ ] **2.10** **Section: Advanced Settings → Maintenance Windows** — Pro-gated window builder
- [ ] **2.11** Sticky submit footer (existing pattern)
- [ ] **2.12** JavaScript: Ensure `setMonitorType()` / `syncFieldNames()` work with new DOM structure
- [ ] **2.13** JavaScript: HTTP method button group click handler

#### ✅ Phase 2 Gate — Add Form Rendering Tests
- [ ] **2.T1** Load `/monitors/add` as Pro user — page renders without errors (check terminal for Jinja2 errors)
- [ ] **2.T2** Type switcher test — click each of the 4 types in the dropdown, confirm:
  - HTTP: URL input visible, heartbeat/SSL sections hidden, advanced HTTP fields visible, interval visible
  - JSON/API: API URL input visible, JSON advanced fields visible, interval visible
  - Heartbeat: How-it-works box visible, interval section hidden, HTTP/JSON advanced hidden
  - SSL: Domain + threshold visible, interval visible, HTTP/JSON advanced hidden
- [ ] **2.T3** HTTP method button group — click each method, confirm the hidden input updates
- [ ] **2.T4** Basic Auth — select "Basic Auth" from auth type, confirm username/password fields appear; select "None", confirm they hide
- [ ] **2.T5** Follow redirects toggle — confirm it renders and is checked by default
- [ ] **2.T6** Keyword builder — add 2 keywords with AND, confirm hidden input value updates
- [ ] **2.T7** JSON assertions builder — switch to JSON/API type, add an assertion, confirm row renders
- [ ] **2.T8** Maintenance window builder (Pro) — add a window, confirm day/start/end row appears
- [ ] **2.T9** Slug field — check "Public status page", confirm slug input appears; type in it, confirm preview updates
- [ ] **2.T10** 2-column layout — resize browser to >768px, confirm Friendly name + Group sit side-by-side; timeout + status code side-by-side; resize to <768px, confirm they stack vertically
- [ ] **2.T11** Sticky footer — scroll down, confirm "Add monitor" button stays fixed at bottom
- [ ] **2.T12** All `name` attributes — inspect the form HTML, verify every field that should POST has a `name` attribute and no duplicates for the active type

---

### Phase 3: Edit Monitor Template (`edit_monitor.html`)
- [ ] **3.1** Back link + heading with monitor type subtitle badge
- [ ] **3.2** Mirror the section structure from Add, but:
  - Monitor type is read-only (badge, existing pattern)
  - Heartbeat shows ping URL with copy button
  - Pre-populate all fields from `monitor` dict
  - HTTP method pre-selected from `monitor.http_method`
  - Basic Auth pre-populated from `monitor.basic_auth_user` / `monitor.basic_auth_pass`
  - Follow redirects pre-populated from `monitor.follow_redirects`
- [ ] **3.3** Auto-open Advanced Settings if any advanced field has a non-default value
- [ ] **3.4** Mirror all JS from add_monitor.html (interval display, slug preview, maintenance windows, assertions, keyword builder with init)

#### ✅ Phase 3 Gate — Edit Form Rendering Tests
- [ ] **3.T1** Load edit page for an **HTTP monitor** — all fields pre-populated correctly (URL, name, group, email, interval, status code, timeout, keyword, etc.)
- [ ] **3.T2** Load edit page for a **Heartbeat monitor** — ping URL shown with copy button, interval/grace pre-populated, no URL field, no interval slider
- [ ] **3.T3** Load edit page for a **JSON/API monitor** — URL pre-populated, auth header shown, assertions rendered from stored data
- [ ] **3.T4** Load edit page for an **SSL monitor** — domain + threshold pre-populated, no HTTP-specific advanced fields
- [ ] **3.T5** Auto-open Advanced — edit an HTTP monitor that has a keyword set → Advanced section should be auto-expanded on page load
- [ ] **3.T6** Auto-open Advanced — edit an HTTP monitor with no advanced values set → Advanced section should be collapsed
- [ ] **3.T7** HTTP method — edit an HTTP monitor, confirm the correct method button is highlighted (or defaults to GET for old monitors without the field)
- [ ] **3.T8** Basic Auth — edit a monitor with `basic_auth_user` set, confirm username/password fields are pre-populated and visible
- [ ] **3.T9** Backward compat — edit an old monitor that doesn't have `http_method`/`basic_auth_user`/`follow_redirects` fields → form should render with sane defaults (GET, no auth, follow=true)

---

### Phase 4: Backend Updates (`pages.py` + `monitor.py`)
- [ ] **4.1** `monitor.py` → `create_monitor()`: Add `follow_redirects: bool = True` parameter, store in doc
- [ ] **4.2** `pages.py` → `add_monitor()` POST handler: Parse `http_method`, `basic_auth_user`, `basic_auth_pass`, `follow_redirects` from form
- [ ] **4.3** `pages.py` → `edit_monitor_submit()` POST handler: Parse same new fields, include in updates dict
- [ ] **4.4** `pages.py` → `add_monitor()`: Pass new fields to `create_monitor()`
- [ ] **4.5** `pages.py` → `edit_monitor_submit()`: Include `http_method`, `basic_auth_user`, `basic_auth_pass`, `follow_redirects` in updates

#### ✅ Phase 4 Gate — Backend Submission Tests
Run automated curl tests (generate JWT, POST to endpoints, verify Firestore writes):
- [ ] **4.T1** Create HTTP monitor via POST `/monitors/add` with all new fields (`http_method=POST`, `basic_auth_user=admin`, `basic_auth_pass=secret`, `follow_redirects=false`) — verify redirect to dashboard, then GET the monitor from Firestore and confirm all fields are stored
- [ ] **4.T2** Create HTTP monitor with defaults (don't send new fields) — verify `http_method=GET`, `basic_auth_user=""`, `basic_auth_pass=""`, `follow_redirects=True` in Firestore
- [ ] **4.T3** Create Heartbeat monitor — verify new fields are stored with defaults, `ping_url` is generated
- [ ] **4.T4** Create JSON/API monitor — verify `http_method`, `follow_redirects` stored (even though not shown on form, should have defaults)
- [ ] **4.T5** Create SSL monitor — same default verification
- [ ] **4.T6** Edit HTTP monitor — POST to `/monitors/{id}/edit` with `http_method=PUT`, `basic_auth_user=newuser` — verify Firestore doc updated
- [ ] **4.T7** Edit HTTP monitor — POST without new fields (simulating old form) — verify existing values not clobbered, defaults applied
- [ ] **4.T8** Free plan gating — create monitor as Free user, confirm `alert_slack_webhook=""`, `webhook_url=""`, `check_interval=300` regardless of what's sent
- [ ] **4.T9** Pro plan gating — create monitor as Pro user, confirm custom interval (e.g., 120s) accepted
- [ ] **4.T10** Server starts without errors — `uvicorn` reload completes cleanly after all changes

---

### Phase 5: End-to-End Integration QA
Full end-to-end tests — create monitors through the real form, verify they appear on dashboard, edit them, verify changes persist:
- [ ] **5.1** **E2E: HTTP full flow** — Add HTTP monitor with custom method (POST), basic auth, keyword, 120s interval → verify on dashboard → edit to change method to GET, remove auth → verify changes saved
- [ ] **5.2** **E2E: JSON/API full flow** — Add JSON/API monitor with auth header + 2 assertions → verify on dashboard → edit to add a 3rd assertion → verify
- [ ] **5.3** **E2E: Heartbeat full flow** — Add heartbeat monitor → verify ping URL shown on dashboard → edit to change interval → verify
- [ ] **5.4** **E2E: SSL full flow** — Add SSL monitor with domain + 30-day threshold → verify → edit threshold to 7 days → verify
- [ ] **5.5** **E2E: Free plan** — Log in as Free user → add HTTP monitor → confirm Slack/Webhook disabled, interval locked, maintenance hidden → submit works
- [ ] **5.6** **E2E: Pro plan** — Log in as Pro user → add HTTP monitor with Slack + webhook + custom interval + maintenance window → all saved correctly
- [ ] **5.7** **Mobile spot-check** — Load Add + Edit pages at 375px width → confirm layout stacks cleanly, no horizontal scroll, sticky footer full-width
- [ ] **5.8** **Backward compat** — Edit a monitor created before this redesign (no `http_method`/`follow_redirects` fields) → form loads with defaults → save without changes → verify no data lost or corrupted
- [ ] **5.9** **Delete regression** — Delete a monitor from dashboard → verify it's gone, no errors
- [ ] **5.10** **Pause/Resume regression** — Pause a monitor from dashboard → verify status changes, edit page shows "Paused" checked
- [ ] **5.11** **Status page regression** — Create a public monitor with slug → visit `/s/{slug}` → confirm status page renders

---

## FIELD INVENTORY (complete list per type)

### HTTP Monitor
| Field | Location | Default | Notes |
|-------|----------|---------|-------|
| URL | Main section | — | Required, auto-prefix https:// |
| Friendly name | Main section | — | Required |
| Group | Main section | "" | Optional, datalist |
| Email notification | Notifications | user.email | Always on |
| Slack webhook | Notifications | "" | Pro only |
| Webhook URL | Notifications | "" | Pro only |
| Check interval | Interval section | 60s Pro / 300s Free | Slider Pro, locked Free |
| Expected status code | Advanced | None (any 2xx/3xx) | Optional, number |
| Request timeout | Advanced | 10s | 1-60s |
| HTTP method | Advanced | GET | Button group: HEAD/GET/POST/PUT/PATCH/DELETE/OPTIONS |
| Follow redirects | Advanced | true | Toggle |
| Basic Auth type | Advanced | None | Select: None / Basic Auth |
| Basic Auth username | Advanced | "" | Shown when type=basic |
| Basic Auth password | Advanced | "" | Shown when type=basic |
| Keyword check | Advanced | "" | Keyword builder |
| Response threshold | Advanced | None | Expression: >2000, <200, 200-3000 |
| Public status page | Advanced | false | Toggle + slug field |
| Slug | Advanced | auto-generated | Shown when public=true |
| Start paused | Advanced | false | Toggle |
| Maintenance windows | Advanced | [] | Pro only, day/start/end builder |

### JSON/API Monitor
| Field | Location | Default | Notes |
|-------|----------|---------|-------|
| API endpoint URL | Main section | — | Required |
| Friendly name | Main section | — | Required |
| Group | Main section | "" | Optional |
| Email / Slack / Webhook | Notifications | — | Same as HTTP |
| Check interval | Interval section | — | Same as HTTP |
| Expected status code | Advanced | None | Optional |
| Request timeout | Advanced | 10s | 1-60s |
| Authorization header | Advanced | "" | Bearer token etc |
| JSON assertions | Advanced | [] | Path/operator/value builder |
| Response threshold | Advanced | None | Same as HTTP |
| Public + Slug + Paused + Maintenance | Advanced | — | Same as HTTP |

### Heartbeat / Cron Monitor
| Field | Location | Default | Notes |
|-------|----------|---------|-------|
| (Ping URL) | Main section | auto-generated | Shown on Edit only, with copy |
| Expected ping interval | Main section | 300s (5min) | Select dropdown |
| Grace period | Main section | 30s | Number, 0-3600 |
| Friendly name | Main section | — | Required |
| Group | Main section | "" | Optional |
| Email / Slack / Webhook | Notifications | — | Same as HTTP |
| (No interval section) | — | — | Hidden |
| Public + Slug + Paused + Maintenance | Advanced | — | Same as HTTP |

### SSL Certificate Monitor
| Field | Location | Default | Notes |
|-------|----------|---------|-------|
| Domain | Main section | — | Required, no protocol |
| Warning threshold (days) | Main section | 14 | 1-90 |
| Friendly name | Main section | — | Required |
| Group | Main section | "" | Optional |
| Email / Slack / Webhook | Notifications | — | Same as HTTP |
| Check interval | Interval section | — | Same as HTTP |
| Public + Slug + Paused + Maintenance | Advanced | — | Same as HTTP |

---

## EXECUTION ORDER

1. **Phase 1** — CSS foundation → **Gate 1**: grep all classes exist, visual sanity check, no regressions
2. **Phase 2** — Add Monitor template → **Gate 2**: rendering tests (all 4 types, type switching, new widgets, 2-col, mobile)
3. **Phase 3** — Edit Monitor template → **Gate 3**: pre-population tests (all 4 types, auto-open, backward compat)
4. **Phase 4** — Backend wiring → **Gate 4**: curl submission tests (create + edit + plan gating + defaults)
5. **Phase 5** — End-to-end integration QA (full user flows, regressions, mobile)
6. **Phase 6** — Dashboard CSS polish → **Gate 6**: visual audit, class verification
7. **Phase 7** — Dashboard template + JS → **Gate 7**: rendering, filters, sort, columns, responsiveness
8. **Phase 8** — Dashboard backend → **Gate 8**: data accuracy, performance
9. **Phase 9** — Dashboard E2E QA (full flows, mobile, edge cases)

**Work through each checkbox sequentially. Run every Gate test before moving to the next Phase. Do not skip ahead.**

### Total Checklist Count
- Phase 1: 9 build + 3 test = **12**
- Phase 2: 13 build + 12 test = **25**
- Phase 3: 4 build + 9 test = **13**
- Phase 4: 5 build + 10 test = **15**
- Phase 5: 11 E2E tests = **11**
- Phase 6: 10 build + 3 test = **13**
- Phase 7: 14 build + 14 test = **28**
- Phase 8: 4 build + 5 test = **9**
- Phase 9: 10 E2E tests = **10**
- **Grand total: 136 checkboxes**

---
---

# Part 2: Dashboard Redesign

> **Goal**: The dashboard is the first thing users see. It needs to feel crisp, fast, information-dense without clutter, and professional. The current layout has too many columns fighting for space, a toolbar that's hard to parse, status counts that look like an afterthought, and no visual differentiation between normal and degraded states. We're tightening every pixel: simplifying columns, improving the status strip, adding a proper filter bar, making the monitor rows scannable at a glance, and ensuring mobile is excellent.

**Rules (same as Part 1)**:
- No new JS frameworks — vanilla JS only
- No external CSS — all in `style.css`
- Keep `d-` prefix for dashboard column classes, existing class names where possible
- SSR-first — Jinja2
- Performance: dashboard reads **only monitor docs** — zero queries to `checks` collection (existing pattern, keep it)

---

## DASHBOARD FILES TO CHANGE

| File | What Changes |
|------|-------------|
| `app/templates/dashboard.html` | Template restructure — status strip, toolbar, monitor rows, empty state |
| `app/static/style.css` | Rework dashboard CSS sections (~lines 848–1400, 1516–1680) |
| `app/routers/pages.py` | Dashboard route — add aggregate stats (avg response, total incidents today) |

---

## CURRENT PROBLEMS (what we're fixing)

1. **Too many columns** — Monitor Name, Group, Type, URL, 24h, Resp., Checked, Actions = 8 columns on a row. Group and Type rarely differ and waste space. URL is truncated to uselessness at 30 chars.
2. **Status strip is passive** — just shows counts. No visual urgency when things are down. No aggregate uptime or response time.
3. **Toolbar is cluttered** — Select-all checkbox + count + bulk dropdown + search + filter + sort all jammed in one row. Hard to parse.
4. **Monitor rows lack hierarchy** — Every column has the same visual weight. The monitor name and status should dominate; URL, response time, and last-checked are secondary.
5. **No uptime bars on dashboard** — We compute `daily_uptime_bars` and `hourly_uptime_bars` but never show them. These are the most powerful visual signal (like UptimeRobot's 30-day bar).
6. **Filter has no type filter** — Can filter by status and group, but not by monitor type (HTTP/Heartbeat/JSON/SSL).
7. **Empty state is boring** — Generic text, no illustration or personality.
8. **Mobile is cramped** — Column header disappears but rows still try to show everything inline.

---

## DASHBOARD DESIGN PRINCIPLES

1. **Two-tier row** — Each monitor row has a **primary line** (status dot + name + mini uptime bar + uptime %) and a **secondary line** (URL, response time, last checked, type badge). The secondary line is smaller, muted. This creates clear hierarchy.
2. **30-day uptime bar** — Inline mini bar chart (30 narrow bars, green/red/gray) directly in each monitor row. This is our signature visual — it tells the whole story at a glance.
3. **Status strip with teeth** — When monitors are down, the strip has a red tint/border. Show aggregate: total monitors, overall uptime %, avg response time.
4. **Clean filter bar** — Pill-style filter tabs (All / Up / Down / Paused / Pending) that replace the dropdown. Group and Type filters in a secondary dropdown.
5. **Search is prominent** — Full-width search bar above the monitor list, not jammed in the toolbar.
6. **Responsive** — On mobile, the row collapses to: status dot + name + uptime % on one line, with URL below.
7. **Subtle hover** — Rows highlight on hover with a soft left-border accent.
8. **Empty state with personality** — Rooster illustration (emoji or SVG), clear CTA.

---

## DASHBOARD CHECKLIST

### Phase 6: Dashboard CSS
- [ ] **6.1** Add `.d-status-strip-alert` — red-tinted variant of status strip when monitors are down
- [ ] **6.2** Add `.d-agg-stat` — aggregate stat pill (e.g., "99.8% uptime", "142ms avg", "3 incidents today")
- [ ] **6.3** Add `.d-filter-pills` — horizontal pill-style filter tabs (All/Up/Down/Paused/Pending)
- [ ] **6.4** Add `.d-filter-pill` — individual pill button with active state
- [ ] **6.5** Rework `.monitor-card` — two-tier layout (primary line + secondary line)
- [ ] **6.6** Add `.d-row-primary` — primary line flex layout (dot + name + mini bars + uptime %)
- [ ] **6.7** Add `.d-row-secondary` — secondary line (URL + response + last checked + type badge), smaller/muted
- [ ] **6.8** Add `.d-uptime-bars` — inline mini uptime bar container (30 bars, 2px wide each, 16px tall)
- [ ] **6.9** Add `.d-uptime-bar` — individual bar segment (green/red/yellow/gray)
- [ ] **6.10** Rework mobile responsive for two-tier row — stack gracefully at <768px

#### ✅ Phase 6 Gate — Dashboard CSS Validation
- [ ] **6.T1** Grep all new dashboard class names — confirm they exist in `style.css`
- [ ] **6.T2** Load dashboard — confirm existing layout still renders (CSS-only changes, template not yet touched)
- [ ] **6.T3** Inspect `.d-uptime-bars` with DevTools — confirm bar container width/height correct

---

### Phase 7: Dashboard Template + JS (`dashboard.html`)
- [ ] **7.1** **Status strip upgrade** — Add aggregate stats: overall uptime %, avg response time, total incidents (passed from backend). Red tint when any monitor is down.
- [ ] **7.2** **Monitors heading row** — "Monitors." heading + "Add monitor" button + monitor count badge (existing, polish)
- [ ] **7.3** **Search bar** — Move search input above the filter row, full-width, clean styling with search icon
- [ ] **7.4** **Filter pills** — Replace dropdown filter with pill tabs: All / Up / Down / Warn / Paused / Pending. Show count in each pill.
- [ ] **7.5** **Secondary filters** — Group dropdown + Type dropdown (HTTP/JSON/Heartbeat/SSL) as small secondary buttons next to pills
- [ ] **7.6** **Sort dropdown** — Keep existing sort dropdown but move to right side of filter row
- [ ] **7.7** **Bulk actions** — Keep select-all + bulk actions but visually separate from filters (show in a floating bar at bottom when items selected)
- [ ] **7.8** **Monitor row — primary line** — Status dot + Monitor name + 30-day uptime mini bars + uptime % value
- [ ] **7.9** **Monitor row — secondary line** — Type badge + URL (stripped of protocol, longer truncation) + response time/SSL days/heartbeat status + last checked countdown
- [ ] **7.10** **30-day uptime bars rendering** — Read `daily_uptime_bars` from monitor data, render 30 small colored bars (green ≥99.5%, yellow ≥95%, red <95%, gray = no data)
- [ ] **7.11** **Three-dot menu** — Keep existing row menu (edit, pause/resume, clone, copy URL, delete) — no changes needed
- [ ] **7.12** **Empty state** — Rooster emoji hero, friendlier copy, prominent CTA button
- [ ] **7.13** **Heartbeat created modal** — Keep existing modal (no changes needed)
- [ ] **7.14** **JS updates** — Update `filterTable()` to support type filter, `sortList()` to work with new DOM structure, `tickLastChecked()` unchanged

#### ✅ Phase 7 Gate — Dashboard Rendering Tests
- [ ] **7.T1** Load dashboard as Pro user with monitors — page renders without errors
- [ ] **7.T2** Status strip — verify aggregate stats show (uptime %, avg response, incident count)
- [ ] **7.T3** Status strip — with a "down" monitor, verify red tint/alert styling applies
- [ ] **7.T4** Filter pills — click each pill (All/Up/Down/Paused/Pending), confirm rows filter correctly
- [ ] **7.T5** Type filter — select "Heartbeat", confirm only heartbeat monitors show
- [ ] **7.T6** Group filter — select a group, confirm only that group's monitors show
- [ ] **7.T7** Search — type a partial monitor name, confirm rows filter live
- [ ] **7.T8** Sort — test each sort mode (Down first, A→Z, Z→A, Lowest uptime, Highest uptime)
- [ ] **7.T9** 30-day uptime bars — verify bars render on each monitor row, colors match uptime data
- [ ] **7.T10** Two-tier row — verify primary line (name + bars + %) and secondary line (URL + response + checked) are visually distinct
- [ ] **7.T11** Bulk actions — select 2 monitors, confirm bulk bar appears, pause/delete work
- [ ] **7.T12** Three-dot menu — verify edit/pause/clone/copy/delete all work
- [ ] **7.T13** Mobile (<768px) — verify rows stack cleanly, filter pills scroll horizontally, search is full-width
- [ ] **7.T14** Empty state — log in as user with no monitors, verify empty state renders with CTA

---

### Phase 8: Dashboard Backend (`pages.py`)
- [ ] **8.1** Compute `avg_response_ms` across all monitors (skip heartbeat/SSL)
- [ ] **8.2** Compute `overall_uptime_pct` (average of all monitors' 24h uptime)
- [ ] **8.3** Count today's incidents (open + resolved) for the user's monitors
- [ ] **8.4** Pass `avg_response_ms`, `overall_uptime_pct`, `incidents_today` to template context

#### ✅ Phase 8 Gate — Backend Data Tests
- [ ] **8.T1** Load dashboard — verify `avg_response_ms` is a sane number (not 0, not None unless no monitors)
- [ ] **8.T2** Verify `overall_uptime_pct` is computed correctly — cross-check manually against 2-3 monitors' `uptime_24h`
- [ ] **8.T3** Verify `incidents_today` count — create a test incident, confirm count increments
- [ ] **8.T4** Performance — verify dashboard loads in <500ms locally (no additional Firestore queries beyond monitors + incidents count)
- [ ] **8.T5** Edge case — user with 0 monitors → no errors, empty state renders, aggregate stats show "—"

---

### Phase 9: Dashboard E2E QA
- [ ] **9.1** **Full flow** — Create monitor → appears on dashboard immediately → correct status/uptime/response
- [ ] **9.2** **Edit flow** — Edit a monitor from dashboard (three-dot → Edit) → change name → verify dashboard updates
- [ ] **9.3** **Delete flow** — Delete a monitor → gone from dashboard, aggregate stats update
- [ ] **9.4** **Pause/Resume** — Pause via three-dot → row shows paused state → resume → row shows up/pending
- [ ] **9.5** **Clone** — Clone a monitor → new copy appears on dashboard
- [ ] **9.6** **Free plan** — Dashboard as Free user → upgrade banner at 4+ monitors, correct limits shown
- [ ] **9.7** **Filter + Search combo** — Filter to "Down" + search by name → only matching down monitors show
- [ ] **9.8** **Mobile full flow** — Complete dashboard interaction at 375px (filter, search, expand menu, navigate to detail)
- [ ] **9.9** **30-day bars accuracy** — Compare bars against actual `daily_uptime_bars` data on a monitor — colors should match
- [ ] **9.10** **Performance benchmark** — Dashboard with 10+ monitors loads in <1s, no layout shift, no JS errors in console
