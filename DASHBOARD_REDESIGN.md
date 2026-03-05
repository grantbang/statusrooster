# Dashboard Redesign — Detailed Build Plan

**Date:** March 4, 2026 · **Target:** Complete before launch (Mar 7)
**Audience:** Indie developers, solo founders, small SaaS teams (1-5 people)
**Philosophy:** Simple > dense. Glanceable > information-overloaded. Ship > perfect.

---

## Why This Redesign

The current dashboard was built incrementally across Days 4 → 10C → 10D. It works, but it's accumulated cruft that fights our "simple monitoring for indie devs" positioning:

1. **Monitor rows are overloaded** — each row has: type badge, duration text, interval icon, dual uptime bars (30d + 24h with a toggle!), 3 inline stat columns, and a ⋯ menu with 7 items. This is UptimeRobot-level density. Our users don't want that.
2. **No dedicated incidents page** — incidents are wedged into a bottom panel below the monitor list. An indie dev needs to see "what broke this week" on its own page.
3. **Add/Edit forms don't match the API** — the API docs are beautifully organized by monitor type with clear sections. The Add modal is a pile of conditional `div`s. The Edit form is a completely separate full-page route with different code. Two patterns = two codebases to maintain.
4. **No concept of grouping** — an indie dev running a SaaS likely has: production monitors, staging monitors, and maybe a side project. Right now they're all in one flat list.
5. **Sidebar has 3 links** — needs Incidents now.

---

## Design Principles

1. **Indie-dev simple** — if a solo founder can't parse the dashboard in 2 seconds ("everything's up" or "something's down"), we've failed. Our audience doesn't want 20-column data tables. They want: green dots = good, red dots = bad.
2. **API-docs-aligned** — the modal sections mirror the API: Type → Request → Validation → Alerts → Schedule → Options. Same field names, same groupings. If a dev reads the API docs and then opens the modal, it should feel familiar.
3. **One pattern** — same modal for Add and Edit. The only difference: title, submit button text, pre-populated fields, read-only type badge.
4. **Groups are tags** — lightweight. A `group` is just a string on the monitor doc. Dashboard groups monitors visually. No Firestore sub-collections, no group management page, no group CRUD API. A text input on the modal, client-side grouping on the dashboard.

---

## New Feature: Monitor Groups

### What It Is

A simple string tag that groups monitors together on the dashboard. That's it.

### Why It Matters for Indie Devs

A typical indie dev has:
- **Production** — their main SaaS app, API, landing page
- **Staging** — staging/preview environment
- **Infrastructure** — SSL certs, cron jobs, database heartbeats
- **Side projects** — other domains they monitor

Without groups, 15 monitors is a wall of rows. With groups, it's 3-4 collapsible sections.

### Implementation

**Firestore:** Add `group` field to monitor doc (string, default `""`)

```python
# In create_monitor():
"group": group,  # e.g. "Production", "Staging", "" (ungrouped)
```

**API:** Add `group` to `ApiCreateMonitor` and `ApiUpdateMonitor` schemas (string, optional)

**Dashboard display:**
```
┌─────────────────────────────────────────────────────────┐
│ ▼ Production (3 monitors)                               │
│   ● My SaaS App      app.example.com      99.98%  120ms│
│   ● Payment API      api.example.com      100.0%   89ms│
│   ● Landing Page     example.com           99.9%  245ms│
│                                                         │
│ ▼ Infrastructure (2 monitors)                           │
│   ● DB Backup         ♥ Heartbeat         100.0%    —  │
│   ● SSL: example.com  🔒 SSL              42d left   — │
│                                                         │
│ ▼ Ungrouped (1 monitor)                                 │
│   ⏸ Staging           staging.example.com    —       —  │
└─────────────────────────────────────────────────────────┘
```

- Groups are collapsible (click header to toggle)
- Collapse state saved to `localStorage`
- Monitors without a group go in "Ungrouped" (or just listed at the bottom without a header if there's only one group or none)
- If no monitors have groups, no group headers shown — flat list like today
- Group names are user-defined strings, not a fixed enum

**Add/Edit modal:** Simple text input with datalist (autocomplete from existing group names):
```html
<input type="text" name="group" list="groupSuggestions" placeholder="e.g. Production">
<datalist id="groupSuggestions">
  <option value="Production">
  <option value="Staging">
  <option value="Infrastructure">
</datalist>
```

**Filter dropdown:** Add group names to the filter list:
```
All | Up | Down | Paused | ── | Production | Staging | Infrastructure
```

### What Groups Are NOT

- ❌ Not a separate Firestore collection
- ❌ Not a management page (`/groups`)
- ❌ No group-level aggregate uptime
- ❌ No group-level status pages (maybe post-launch)
- ❌ No API endpoint for listing groups (they're derived from monitor docs)

---

## Architecture

### Sidebar Navigation (Updated)

```
🐓 StatusRooster
─────────────────────
📊 Monitors        ← /dashboard
🔔 Incidents       ← /incidents (NEW)
⚙️ Settings        ← /settings
</> API & Docs     ← /docs/api
─────────────────────
[User avatar]
[Upgrade to Pro]
[Log out]
```

### Four Routes

| Page | Route | Template | Purpose |
|------|-------|----------|---------|
| **Monitors** | `GET /dashboard` | `dashboard.html` | Status strip + grouped monitor list + Add/Edit modal |
| **Incidents** | `GET /incidents` | `incidents.html` (NEW) | All incidents with search/filter |
| **Incident Detail** | `GET /incidents/{id}` | `incident_detail.html` (NEW) | Single incident: root cause, details, activity log |
| **Monitor Detail** | `GET /monitors/{id}` | `monitor_detail.html` | Unchanged (already good) |

---

## Page 1: Monitors Dashboard (`/dashboard`)

### What the Monitor Row Becomes

**Current row (too much):**
```
[☐] [●] [HTTP] Name  URL  "Up 2h"  [⏱60s]  [████████ uptime bars ████████]  99.98% 245ms 0inc  [⋯]
```

**New row (clean):**
```
[☐] [●] Name                       example.com            99.98%    245ms    [⋯]
      Up for 2h 15m · HTTP
```

Each row:
1. **Checkbox** — bulk actions
2. **Status dot** — green/red/amber/gray
3. **Name** (bold) + second line: duration text + type label (muted, small)
4. **URL** — truncated, or type-specific: `♥ Heartbeat`, `🔒 example.com`
5. **Uptime %** — color-coded
6. **Response** — `245ms`, or `Last ping: ✓`, or `42d left` for SSL
7. **⋯ menu** — Edit, Pause/Resume, Clone, Copy URL, Delete (5 items, no sub-sections)

### What Gets Removed from Dashboard

| Element | Where It Goes |
|---------|---------------|
| Uptime bar charts (30d/24h) | Stay on monitor detail page only |
| 30d/24h toggle in toolbar | Removed (no bars = no toggle) |
| Incidents panel at bottom | → dedicated `/incidents` page |
| Inline incident count per row | → monitor detail page |
| Interval icon per row | Visible in detail + edit only |
| "Edit monitor settings" sub-menu | Removed (Edit covers this) |

### What Stays

- ✅ Status strip (headline + count pills)
- ✅ Search bar (client-side filter by name/URL)
- ✅ Filter dropdown (All / Up / Down / Paused / Pending + group names)
- ✅ Sort dropdown (Down first / A→Z / Z→A / Uptime low→high / Uptime high→low)
- ✅ Bulk actions (select all → Pause / Resume / Delete)
- ✅ ⋯ context menu per row
- ✅ "+ Add monitor" card at bottom
- ✅ Upgrade banner for Free users near limit

### Toolbar

```
[☐ 0/12] [Bulk ▾]   [Search...............] [Filter ▾] [Sort ▾]     [+ Add monitor]
```

Same as today minus the 30d/24h toggle. Filter dropdown gains group name options.

### Grouped Layout — Client-Side

The backend passes `monitors` as a flat list (same as today). The template groups them:

```jinja2
{% set groups = monitors | groupby('group') %}
{% for group_name, group_monitors in groups %}
<div class="monitor-group" data-group="{{ group_name }}">
    {% if group_name %}
    <div class="group-header" onclick="toggleGroup(this)">
        <svg class="group-chevron">▼</svg>
        <span class="group-name">{{ group_name }}</span>
        <span class="group-count">({{ group_monitors | length }})</span>
    </div>
    {% endif %}
    <div class="group-body">
        {% for m in group_monitors %}
        <!-- monitor row -->
        {% endfor %}
    </div>
</div>
{% endfor %}
```

If zero monitors have a group, no group headers render — same flat list as today.

---

## Page 2: Incidents (`/incidents`)

### Route

```python
@router.get("/incidents", response_class=HTMLResponse)
async def incidents_page(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    monitors = list_monitors_by_user(db, user["id"])
    monitor_ids = [m["id"] for m in monitors]

    # Default: last 7 days, all statuses
    hours = int(request.query_params.get("hours", 168))  # 7d
    status_filter = request.query_params.get("status")  # "open" | "resolved" | None

    incidents = list_incidents_by_user(
        db, monitor_ids,
        hours=hours if hours > 0 else None,
        limit=200,
        status=status_filter,
    ) if monitor_ids else []

    return templates.TemplateResponse("incidents.html", {
        "request": request,
        "user": user,
        "incidents": incidents,
        "monitors": monitors,
        "hours": hours,
        "status_filter": status_filter,
    })
```

### Template Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Incidents                                                       │
│                                                                 │
│ [Search by monitor...] [All | Ongoing | Resolved]  [7d ▾]      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ● ONGOING                                              38m ago │
│  My Website — HTTP 503 Service Unavailable                      │
│  https://example.com                                            │
│                                                                 │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│                                                                 │
│  ✓ Resolved  ·  Duration: 2h 15m                       Mar 3   │
│  Payment API — Request timeout                                  │
│  https://api.example.com                                        │
│                                                                 │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│                                                                 │
│  ✓ Resolved  ·  Duration: 45m                          Mar 2   │
│  Blog — HTTP 502 Bad Gateway                                    │
│  https://blog.example.com                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

Each incident card:
- **Status badge** — `● ONGOING` (red) or `✓ Resolved` (green)
- **Duration** — for resolved: `Duration: 2h 15m` / for ongoing: live-ticking timer
- **Timestamp** — right-aligned, relative or date
- **Monitor name + root cause** — `My Website — HTTP 503 Service Unavailable`
- **URL** — second line, muted
- **Clickable** → `/incidents/{id}`

### Root Cause Text

Map status codes to human-readable text (same as monitor detail page):

```python
ROOT_CAUSES = {
    0: "Connection refused",
    None: "Request timeout",
    400: "HTTP 400 Bad Request",
    401: "HTTP 401 Unauthorized",
    403: "HTTP 403 Forbidden",
    404: "HTTP 404 Not Found",
    500: "HTTP 500 Internal Server Error",
    502: "HTTP 502 Bad Gateway",
    503: "HTTP 503 Service Unavailable",
    504: "HTTP 504 Gateway Timeout",
}

def get_root_cause(status_code, monitor_type=None):
    if monitor_type == "heartbeat":
        return "Missed heartbeat ping"
    if monitor_type == "ssl":
        return "SSL certificate expiring"
    if status_code is None:
        return "Request timeout"
    return ROOT_CAUSES.get(status_code, f"HTTP {status_code}")
```

### Filters (Client-Side)

- **Search** — filter by monitor name or URL (instant, keyup)
- **Status tabs** — All | Ongoing | Resolved (click = filter)
- **Time range dropdown** — 24h | 3d | 7d | 30d | All (changes query param, reloads page)

---

## Page 3: Incident Detail (`/incidents/{id}`)

### Route

```python
@router.get("/incidents/{incident_id}", response_class=HTMLResponse)
async def incident_detail_page(request: Request, incident_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()
    incident = get_incident(db, incident_id)
    if not incident:
        return RedirectResponse(url="/incidents", status_code=302)

    # Validate ownership
    monitor = get_monitor(db, incident["monitor_id"])
    if not monitor or monitor["user_id"] != user["id"]:
        return RedirectResponse(url="/incidents", status_code=302)

    return templates.TemplateResponse("incident_detail.html", {
        "request": request,
        "user": user,
        "incident": incident,
        "monitor": monitor,
    })
```

### Template Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Incidents                                             │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │                                                             │ │
│ │  ● ONGOING · 38 minutes                                    │ │
│ │  HTTP 503 Service Unavailable                               │ │
│ │  My Website                                                 │ │
│ │                                                             │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ── Details ──────────────────────────────────────────────────── │
│                                                                 │
│  Monitor         My Website                                     │
│  URL             https://example.com         [View monitor →]   │
│  Type            HTTP / HTTPS                                   │
│  Started         Mar 4, 2026 14:22 UTC  (38m ago)               │
│  Resolved        —                                              │
│  Duration        38m (ongoing)                                  │
│  Status Code     503                                            │
│  Response Time   3,240ms                                        │
│                                                                 │
│ ── Timeline ─────────────────────────────────────────────────── │
│                                                                 │
│  14:22 UTC  ● Incident detected — HTTP 503                     │
│             Response time: 3,240ms                              │
│                                                                 │
│  (Activity log events will appear here — Day 11B)              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Elements

**Hero card:** Large status badge, root cause text, monitor name. Color-coded border (red ongoing, green resolved).

**Details grid:** 2-column key-value layout. All fields from the incident doc + monitor context.

**Timeline section:** Placeholder for now. Shows the initial detection event using data from the incident doc (started_at, status_code, response_ms). Day 11B will add the full event sub-collection (alert sent, retry failed, resolved, etc.)

---

## Add/Edit Modal — Unified (The Big One)

### Current Problems

1. **Add modal** (`dashboard.html` lines 370-650) — 280 lines of HTML with conditional sections
2. **Edit form** (`edit_monitor.html` — 500 lines) — completely separate full-page route with duplicated logic
3. **Two codebases** — keyword builder JS is duplicated. Assertion builder JS is duplicated. Maintenance window JS is duplicated. All slightly different.
4. **No section labels** — fields are just stacked. No visual hierarchy.

### New Modal Design

One modal. Works for both Add and Edit. Sections mirror the API docs.

```
┌──────────────────────────────────────────────────────────┐
│ Add Monitor                                        [✕]   │
│                                                          │
│ ┌──────┐ ┌──────────┐ ┌───────────┐ ┌────────────────┐  │
│ │ HTTP │ │ JSON/API │ │ Heartbeat │ │ SSL Certificate│  │
│ └──────┘ └──────────┘ └───────────┘ └────────────────┘  │
│                                                          │
│ ── REQUEST ──────────────────────────────────────────    │
│                                                          │
│ URL                [https://example.com              ]   │
│ Expected Status    [200     ] (optional)                  │
│ Timeout            [10      ] seconds                    │
│                                                          │
│ ── VALIDATION ───────────────────────────────────────    │
│                                                          │
│ Keyword Check                                            │
│ ┌────────────────────────────────────────────────────┐   │
│ │ [Contains ▾] [Welcome           ] [✕]             │   │
│ │      AND                                           │   │
│ │ [Contains ▾] [Dashboard         ] [✕]             │   │
│ │ [+ Add keyword]                                    │   │
│ └────────────────────────────────────────────────────┘   │
│                                                          │
│ Response Threshold [> 2000                           ]   │
│                                                          │
│ ── ALERTS ───────────────────────────────────────────    │
│                                                          │
│ Display Name       [My Website                       ]   │
│ Alert Email        [me@example.com                   ]   │
│ Slack Webhook      [https://hooks.slack.com/...  ] Pro   │
│ Webhook URL        [https://your-api.com/hook    ] Pro   │
│ SMS Number         [+1234567890                  ] Pro   │
│                                                          │
│ ── SCHEDULE ─────────────────────────────────────────    │
│                                                          │
│ Check Interval     [=====●=========] 60s           Pro   │
│ Maintenance        [+ Add window]                  Pro   │
│                                                          │
│ ── OPTIONS ──────────────────────────────────────────    │
│                                                          │
│ Group              [Production          ] (optional)     │
│ ☐ Public status page                                     │
│ ☐ Start paused                                           │
│                                                          │
│                              [Add monitor]               │
└──────────────────────────────────────────────────────────┘
```

### Section Mapping: Modal ↔ API Docs

| Modal Section | API Docs Equivalent | Visibility |
|---------------|--------------------|-----------| 
| **Type selector** | Monitor Types sidebar | All types (read-only badge in edit mode) |
| **Request** | Per-type Create → Request fields | HTTP + JSON: url, status, timeout. Heartbeat: interval, grace. SSL: domain, threshold. |
| **Validation** | Per-type Create → Validation fields | HTTP: keyword + threshold. JSON: auth_header + assertions + threshold. Others: hidden. |
| **Alerts** | Shared fields | All types: name, email, slack, webhook, sms |
| **Schedule** | Pro fields | HTTP + JSON + SSL: interval + maintenance. Heartbeat: hidden (has its own interval in Request). |
| **Options** | Optional fields | All types: group, public, paused. Edit mode adds: slug. |

### Per-Type Field Visibility Matrix

| Section | Field | HTTP | JSON/API | Heartbeat | SSL |
|---------|-------|------|----------|-----------|-----|
| **Request** | URL | ✅ | ✅ "API Endpoint" | ❌ | ❌ |
| | Domain | ❌ | ❌ | ❌ | ✅ |
| | Expected Status Code | ✅ | ✅ | ❌ | ❌ |
| | Timeout | ✅ | ✅ | ❌ | ❌ |
| | Heartbeat Interval | ❌ | ❌ | ✅ | ❌ |
| | Grace Period | ❌ | ❌ | ✅ | ❌ |
| | SSL Warning Threshold | ❌ | ❌ | ❌ | ✅ |
| **Validation** | Auth Header | ❌ | ✅ | ❌ | ❌ |
| | JSON Assertions | ❌ | ✅ | ❌ | ❌ |
| | Keyword Check | ✅ | ❌ | ❌ | ❌ |
| | Response Threshold | ✅ | ✅ | ❌ | ❌ |
| **Alerts** | Name | ✅ | ✅ | ✅ | ✅ |
| | Email | ✅ | ✅ | ✅ | ✅ |
| | Slack | ✅ Pro | ✅ Pro | ✅ Pro | ✅ Pro |
| | Webhook URL | ✅ Pro | ✅ Pro | ✅ Pro | ✅ Pro |
| | SMS | ✅ Pro | ✅ Pro | ✅ Pro | ✅ Pro |
| **Schedule** | Check Interval | ✅ Pro | ✅ Pro | ❌ | ✅ Pro |
| | Maintenance Windows | ✅ Pro | ✅ Pro | ❌ | ❌ |
| **Options** | Group | ✅ | ✅ | ✅ | ✅ |
| | Public | ✅ | ✅ | ✅ | ✅ |
| | Paused | ✅ | ✅ | ✅ | ✅ |
| | Slug (edit only) | ✅ | ✅ | ✅ | ✅ |

### Edit Mode Behavior

When the user clicks "Edit" in the ⋯ menu:

1. JS calls `GET /api/monitors/{id}/edit-data` (new internal endpoint, session-authed)
2. Returns monitor JSON with all fields
3. JS populates the modal:
   - Title → "Edit Monitor"
   - Type selector → read-only badge (can't change type after creation)
   - All fields pre-filled from response
   - Form action → `POST /monitors/{id}/edit`
   - Submit button → "Save changes"
   - Slug field visible (hidden in Add mode)
4. Modal opens

This eliminates the need for `edit_monitor.html` entirely. One template, one set of JS.

**New endpoint in `pages.py`:**
```python
@router.get("/api/monitors/{monitor_id}/edit-data")
async def get_monitor_edit_data(request: Request, monitor_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    db = get_db()
    monitor = get_monitor(db, monitor_id)
    if not monitor or monitor["user_id"] != user["id"]:
        return JSONResponse({"error": "Not found"}, status_code=404)
    # Serialize datetimes to ISO strings for JSON
    data = {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in monitor.items()}
    return JSONResponse(data)
```

### JS Functions for Edit Mode

```javascript
async function openEditModal(monitorId) {
    const resp = await fetch(`/api/monitors/${monitorId}/edit-data`);
    if (!resp.ok) { alert('Failed to load monitor data.'); return; }
    const m = await resp.json();

    // Set modal to edit mode
    document.getElementById('modalTitle').textContent = 'Edit Monitor';
    document.getElementById('modalSubmitBtn').textContent = 'Save changes';
    document.getElementById('addForm').action = `/monitors/${monitorId}/edit`;

    // Set type (read-only in edit mode)
    setMonitorType(m.monitor_type, null, true); // true = readonly

    // Populate fields
    document.getElementById('url').value = m.url || '';
    document.getElementById('name').value = m.name || '';
    document.getElementById('alert_email').value = m.alert_email || '';
    document.getElementById('group').value = m.group || '';
    // ... etc for all fields

    // Show slug field (edit only)
    document.getElementById('slugGroup').style.display = 'block';
    document.getElementById('slug').value = m.slug || '';

    openModal();
}
```

---

## Execution Checklist

### Step 0: Backend — Add `group` field (~15 min)

- [x] `models/monitor.py` — add `group: str = ""` param to `create_monitor()` + add to `monitor_data` dict
- [x] `api_v1.py` — add `group: str = ""` to `ApiCreateMonitor` schema
- [x] `api_v1.py` — add `group: str | None = None` to `ApiUpdateMonitor` schema + update logic
- [x] `api_v1.py` — add `"group"` to `_serialize_monitor()` response (auto-exposed via `_serialize_monitor`)
- [x] `pages.py` — parse `group` from form data in `add_monitor()`
- [x] `pages.py` — parse `group` from form data in `edit_monitor_submit()`

### Step 1: Sidebar — Add Incidents link (~5 min)

- [ ] `dashboard_base.html` — add Incidents nav link with alert-triangle SVG icon
- [ ] `dashboard_base.html` — add `{% block nav_incidents %}{% endblock %}` for active state

### Step 2: Dashboard Simplification (~45 min)

**Remove from `dashboard.html`:**
- [ ] Remove uptime bar daily div + all `bar-seg` generation (~30 lines)
- [ ] Remove uptime bar hourly div (~20 lines)
- [ ] Remove `monitor-row-stats` div (3 inline stat columns)
- [ ] Remove 30d/24h toggle from toolbar
- [ ] Remove incidents panel (`incidents-panel`) + all incident HTML (~60 lines)
- [ ] Simplify ⋯ menu → keep only: Edit, Pause/Resume, Clone, Copy URL, Delete

**Add to `dashboard.html`:**
- [ ] Group headers with collapse toggle (client-side `groupby`)
- [ ] Uptime % as direct row element
- [ ] Response time as direct row element
- [ ] Group names in filter dropdown

**Remove from `pages.py` dashboard route:**
- [ ] Remove `uptime_bars` computation
- [ ] Remove `uptime_bars_hourly` computation
- [ ] Remove both from template context dict

**JS cleanup:**
- [ ] Remove `initBarTooltips()`, `barMouseEnter()`, `barMouseLeave()`
- [ ] Remove `setUptimeRange()`
- [ ] Remove `filterIncidents()`
- [ ] Add `toggleGroup()` function (collapse state → `localStorage`)

### Step 3: Incidents Page (~1 hr)

**Backend:**
- [ ] `pages.py` — add `GET /incidents` route (query params: `hours`, `status`)

**Template (`incidents.html` — NEW):**
- [ ] Extends `dashboard_base.html`, sets `nav_incidents` active
- [ ] Toolbar: search input + status tabs (All/Ongoing/Resolved) + time range dropdown
- [ ] Incident card loop — each card: status badge, monitor name, root cause, URL, timestamp
- [ ] Cards clickable → `/incidents/{id}`
- [ ] Client-side search (filter by monitor name/URL on keyup)
- [ ] Status tabs — client-side filter
- [ ] Time range — reload with `?hours=24` / `72` / `168` / `0`
- [ ] Empty state: `✓ No incidents — all monitors healthy`

**CSS (`style.css`):**
- [ ] `.inc-card` — card style
- [ ] `.inc-status-badge` — red ongoing / green resolved
- [ ] `.inc-root-cause` — monospace badge
- [ ] `.inc-meta` — muted URL line
- [ ] `.inc-time` — right-aligned timestamp

### Step 4: Incident Detail Page (~45 min)

**Backend:**
- [ ] `pages.py` — add `GET /incidents/{id}` route (ownership validation)

**Template (`incident_detail.html` — NEW):**
- [ ] Extends `dashboard_base.html`
- [ ] Back link → `/incidents`
- [ ] Hero card: status badge + root cause text + monitor name (colored border)
- [ ] Details grid: monitor, URL, type, started, resolved, duration, status code, response time
- [ ] "View monitor →" link to `/monitors/{id}`
- [ ] Timeline section: placeholder + initial detection event from incident doc

**CSS:**
- [ ] `.inc-detail-hero` — colored left border card
- [ ] `.inc-detail-grid` — 2-column key-value
- [ ] `.inc-timeline` — vertical timeline with dots

### Step 5: Add/Edit Modal Rebuild (~1.5 hrs)

**Modal HTML rewrite:**
- [ ] Add section labels: REQUEST → VALIDATION → ALERTS → SCHEDULE → OPTIONS
- [ ] Restructure field order to match API docs
- [ ] Add `group` text input with `<datalist>` autocomplete in Options
- [ ] Add `slug` input in Options (hidden in add mode, visible in edit)
- [ ] Add `id="addForm"` to form, `id="modalTitle"` to h2, `id="modalSubmitBtn"` to submit
- [ ] Per-type field visibility (show/hide sections based on type selector)

**Edit mode JS:**
- [ ] `pages.py` — add `GET /api/monitors/{id}/edit-data` endpoint (returns monitor JSON)
- [ ] `openEditModal(monitorId)` — fetch data, populate all fields, set title/action/button
- [ ] `resetModal()` — clear all fields, reset to "Add Monitor" mode
- [ ] Update `openModal()` to call `resetModal()` first
- [ ] ⋯ menu "Edit" → `onclick="openEditModal('{{ m.id }}')"` (no page navigation)
- [ ] Type selector read-only in edit mode (badge, not buttons)

**Fallback:**
- [ ] Keep `edit_monitor.html` working (don't delete — bookmarks, fallback)

### Step 6: Polish + CSS (~30 min)

- [ ] `.modal-section-label` — uppercase, muted, border-bottom, letter-spacing
- [ ] `.monitor-group` / `.group-header` / `.group-body` — group collapse styles
- [ ] `.group-chevron` — rotate animation on collapse
- [ ] Mobile: modal scrolls at full height
- [ ] Mobile: incident cards stack properly
- [ ] Mobile: group headers have large enough tap target

### Step 7: API Docs Update (~15 min)

- [x] Add `group` field to all 4 monitor type Create sections (parameter tables + JSON response examples)
- [x] Add `group` field to all 4 Update sections (parameter tables)
- [x] Add `group` to response shape example (shared response + all 4 Create responses)
- [x] Add `group` to field reference table (Complete field reference)

### Step 8: Commit + Push

- [ ] `git add -A && git commit -m "Dashboard redesign: simplified rows, groups, incidents pages, unified Add/Edit modal" && git push`

---

## Files to Change — Complete List

| File | Action | Lines Changed (est.) |
|------|--------|---------------------|
| `app/models/monitor.py` | Add `group` param + field | ~5 lines |
| `app/routers/api_v1.py` | Add `group` to schemas + serializer | ~10 lines |
| `app/routers/pages.py` | Add incidents routes, edit-data endpoint, parse group | ~80 lines |
| `app/templates/dashboard_base.html` | Add Incidents sidebar link | ~8 lines |
| `app/templates/dashboard.html` | Major rewrite: simplified rows, groups, modal rebuild | ~300 lines net change |
| `app/templates/incidents.html` | **NEW** — incidents list page | ~180 lines |
| `app/templates/incident_detail.html` | **NEW** — incident detail page | ~200 lines |
| `app/templates/api_docs.html` | Add `group` field to docs | ~30 lines |
| `app/static/style.css` | Groups, incidents, modal sections, cleanup | ~150 lines |

---

## Total Estimate

| Step | Task | Time |
|------|------|------|
| 0 | Backend: add `group` field | 15 min |
| 1 | Sidebar: Incidents link | 5 min |
| 2 | Dashboard simplification | 45 min |
| 3 | Incidents page | 1 hr |
| 4 | Incident detail page | 45 min |
| 5 | Add/Edit modal rebuild | 1.5 hrs |
| 6 | Polish + CSS | 30 min |
| 7 | API docs: `group` field | 15 min |
| 8 | Commit + push | 5 min |
| | **Total** | **~5 hrs** |

---

## What This Covers from TRACKER.md

| Tracker Item | Status After This |
|---|---|
| **10E** (timeout, basic auth, HTTP method) | Timeout already in modal. Basic auth + HTTP method = post-launch. |
| **10F** (pro upsell polish) | Pro badges on modal sections. Interval badge on rows: skipped (detail page shows it). |
| **11A** (incidents pages) | ✅ Fully covered (list + detail) |
| **11B** (activity log timeline) | Placeholder in incident detail. Real events = next step. |
| **Groups** | ✅ New feature — lightweight, high value for indie devs |

---

## What This Does NOT Cover

- ❌ Activity log event sub-collection in Firestore (Day 11B — separate task after this)
- ❌ Admin dashboard (Day 11D)
- ❌ Custom 404/500 pages, meta tags, favicon (Day 11C)
- ❌ Basic Auth / HTTP method fields (post-launch)
- ❌ Inline editing from dashboard (modal handles edit)
- ❌ Dashboard-level CSV export (detail page has it)
- ❌ Column selector / data table (card rows are right for indie devs)

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Edit modal JS is complex (populate all fields from API) | Test all 4 monitor types. If it's fragile, keep `edit_monitor.html` as fallback and link to it from modal. |
| Removing uptime bars from dashboard loses visual appeal | They're still on the monitor detail page. Dashboard is for status-at-a-glance, detail is for deep-dive. |
| Groups add scope | It's literally one string field. ~20 lines of backend code, ~40 lines of template code. If it takes longer than 15 min, skip it. |
| Breaking existing edit page bookmarks | Keep `edit_monitor.html` working. It's not hurting anything. Deprecate it quietly. |
