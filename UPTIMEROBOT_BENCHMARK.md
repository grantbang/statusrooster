# UptimeRobot vs StatusRooster — Form Benchmark & Action Plan

> **Context:** Competitive analysis of UptimeRobot's edit monitor form (3 screenshots) against our current Add/Edit monitor forms. Goal is to identify high-ROI functional gaps and UX improvements — not to copy their design, but to borrow critical ideas that indie devs expect.

---

## 1. Feature-by-Feature Comparison (HTTP Monitor)

| Feature | UptimeRobot | StatusRooster | Gap? |
|---------|------------|---------------|------|
| **URL input** | Large prominent field at top | ✅ Same pattern | — |
| **Friendly name** | Inline rename below URL | ✅ Separate "Identity" section | — |
| **Groups** | Dropdown (paid only) | ✅ Free text + datalist suggestions | — |
| **Tags** | Free-text tag input | ❌ Not implemented | Low priority — groups cover this |
| **Notification channels** | Email, SMS, Voice, Push — checkbox grid | ✅ Email (always on) + Slack + Webhook with toggles | — |
| **Notification delay/repeat** | Per-channel "delay, no repeat" config | ❌ Not implemented | **Medium — nice-to-have post-launch** |
| **Monitor interval** | Slider (30s–24h), labels at key points | ✅ Slider (60s–5m for Pro, locked 5m for Free) | — |
| **Region selection** | Dropdown (paid only) | ❌ N/A (single region: us-east1) | Not applicable pre-launch |
| **SSL certificate checks** | Collapsible section within HTTP form (paid) | ✅ Separate SSL monitor type (better!) | We're better |
| **Request timeout** | Slider (1s–60s) with labels | ✅ Number input (1–60s) | **Low — slider is nicer UX** |
| **Slow response time alert** | Toggle + threshold input (ms) | ✅ Response threshold field (supports expressions) | We're more powerful |
| **Follow redirections** | Toggle with description | ✅ Toggle in Advanced Settings | — |
| **Up HTTP status codes** | Multi-select chips (2xx, 3xx removable) | ✅ Single expected status code input | **Medium — see analysis** |
| **Auth type** | Dropdown (Bearer/Basic/etc.) + token field | ✅ Basic Auth only (dropdown: None/Basic) | **High — Bearer token for HTTP** |
| **HTTP method** | Segmented button group (HEAD/GET/POST/...) | ✅ Segmented button group | — |
| **Request body** | Text area for POST/PUT body (paid) | ❌ Not implemented | **Medium — useful for API monitoring** |
| **Custom headers** | Key-value builder (paid) | ❌ Not implemented | **Medium — useful for API monitoring** |
| **IP version** | Dropdown (IPv4/IPv6) | ❌ N/A | Not needed for target market |
| **Keyword check** | Not visible in HTTP edit | ✅ Keyword expression builder with AND/OR | We're better |
| **JSON assertions** | Not available (separate product) | ✅ First-class JSON/API type with assertions | We're better |
| **Heartbeat/cron** | Separate product | ✅ First-class monitor type | We're better |
| **Status page** | Separate settings | ✅ Per-monitor public toggle + slug | We're better |
| **Maintenance windows** | Separate settings | ✅ Per-monitor windows (Pro) | We're better |
| **Pause/start** | Separate action | ✅ In-form toggle | — |

---

## 2. UX Pattern Comparison

| UX Pattern | UptimeRobot | StatusRooster | Gap? |
|-----------|------------|---------------|------|
| **Form layout** | Flat scroll, sections separated by whitespace | ✅ Sectioned cards with icons + headers | We're better |
| **Advanced settings** | Inline collapsible (`▸ Advanced settings`) | ✅ Same pattern, auto-opens on Edit | — |
| **Pro gating** | Lock icon + "Available only in Solo, Team..." badge inline | ✅ PRO badge + upgrade link + greyed out | Similar |
| **Pro upgrade CTA text** | "Upgrade now" link next to feature label | ✅ "Upgrade to Pro" link | — |
| **Save button** | Top-right "Finish update" button (fixed) | ✅ Sticky bottom footer "Save changes" | Both work |
| **Navigation context** | "← Monitor detail" breadcrumb at top | ✅ Same pattern — "← Monitor detail" on Edit | — |
| **Right sidebar navigation** | "Monitor details / Integrations & Team / Maintenance info" tabs | ❌ Single scrolling form | **Low — not needed for simpler product** |
| **Slider UX** | Slider with labeled tick marks (30s, 1m, 5m, etc.) | ✅ Slider with labels at 60s/3m/5m | — |
| **Request timeout UX** | Slider with tick marks (1s/15s/30s/45s/60s) | Number input — works but less visual | **Low — slider is marginally better** |

---

## 3. Gap Analysis — What's Worth Doing

### 🟢 HIGH ROI (do before launch)

#### H1. Bearer/Token Auth for HTTP monitors
**Why:** UptimeRobot has a dropdown with Bearer/Basic auth types + token field. Many APIs use Bearer tokens. We only support Basic Auth for HTTP monitors (JSON/API has `auth_header`, but HTTP doesn't). This is a real functional gap — users monitoring authenticated endpoints will expect it.

**What to do:**
- Expand the auth type dropdown on HTTP monitors: `None` / `Basic Auth` / `Bearer Token`
- Bearer Token: show a single "Token" input field
- Backend: if Bearer selected, send `Authorization: Bearer <token>` header
- Already in checker.py: we set headers dict, just need to add Bearer path
- Apply to both Add + Edit forms
- **Effort:** ~30 min

#### H2. Request body for POST/PUT/PATCH checks
**Why:** If someone selects POST or PUT as their HTTP method but can't send a body, the feature is half-baked. UptimeRobot has this (paid). We already support POST/PUT/PATCH method selection but have no body field.

**What to do:**
- Show a textarea for "Request body" when method is POST, PUT, or PATCH
- Add a "Content-Type" dropdown above it: `application/json` (default) / `text/plain` / `application/x-www-form-urlencoded`
- Backend: pass body + content-type to checker
- `checker.py` change: add `content` and `content_type` params to `check_url()`
- Apply to both Add + Edit forms
- **Effort:** ~45 min

### 🟡 MEDIUM ROI (nice polish, consider for post-launch or if time permits)

#### M1. Custom request headers (key-value builder)
**Why:** Power users monitoring APIs often need custom headers (API keys, custom auth schemes, content negotiation). UptimeRobot has this (paid). Our JSON/API type has `auth_header` but HTTP doesn't have arbitrary headers.

**What to do:**
- Add a "Custom headers" key-value builder (like our JSON assertions builder) in Advanced Settings
- Backend: store as `custom_headers: [{key: "X-Api-Key", value: "abc123"}, ...]`
- Checker: merge into headers dict before request
- Pro-gated
- **Effort:** ~1 hour

#### M2. Accepted status codes as multi-select / range
**Why:** UptimeRobot lets you define "2xx + 3xx" as acceptable status codes (multi-select chips). We have a single `expected_status_code` number input. For most users, "any 2xx" (our default when blank) is fine, but some want "200 or 301" specifically.

**What to do:**
- Change from single number input to a text field that accepts expressions: `200`, `200,301`, `2xx`, `2xx,3xx`
- Backend: parse and evaluate in checker
- Lower priority because our blank = "any 2xx/3xx" default covers 90% of cases
- **Effort:** ~45 min

#### M3. Notification delay / repeat settings
**Why:** UptimeRobot has per-channel "delay X minutes before alerting" and "repeat every X minutes." This prevents alert fatigue. We don't have this.

**What to do:**
- Add "Alert delay" (minutes before first alert) and "Repeat interval" (re-alert every N minutes, 0 = no repeat) fields to the notifications section
- Backend: store on monitor doc, checker respects delay before triggering alert
- **Effort:** ~2 hours (significant backend work)

### 🔵 LOW ROI (skip for now)

| Item | Why Skip |
|------|----------|
| Tags | Groups already serve this purpose for our target market |
| Region selection | We're single-region (us-east1). Multi-region is post-launch scale work |
| Voice call alerts | Enterprise feature, not our market |
| Push notifications | Requires mobile app, not building |
| IP version selection | Edge case, not worth the UI clutter |
| Right sidebar navigation | Our form is short enough to scroll, no need for tab navigation |
| Timeout as slider | Number input works fine, slider is marginal UX improvement |

---

## 4. Action Plan — TRACKER Items

### New Phase: 10G-B — Form Feature Gaps (Pre-Launch)

**Scope:** High-ROI functional gaps identified from UptimeRobot competitive benchmark. These are real capabilities missing from our add/edit forms that users will expect.

| Item | What | Effort | Files |
|------|------|--------|-------|
| **10G-B.1** | Bearer/Token auth for HTTP monitors — auth type dropdown expands to None/Basic/Bearer, token input, backend wiring | 30 min | `add_monitor.html`, `edit_monitor.html`, `checker.py`, `pages.py` |
| **10G-B.2** | Request body for POST/PUT/PATCH — textarea + Content-Type selector, shown when method ≠ GET/HEAD, backend wiring | 45 min | `add_monitor.html`, `edit_monitor.html`, `checker.py`, `pages.py`, `monitor.py` |
| **10G-B.3** | Custom request headers (Pro) — key-value builder in Advanced Settings, stored on monitor, sent in checker | 1 hr | `add_monitor.html`, `edit_monitor.html`, `checker.py`, `pages.py`, `monitor.py` |
| **10G-B.T1** | Test: Create HTTP monitor with Bearer auth → checker sends Authorization header | — | Manual |
| **10G-B.T2** | Test: Create HTTP monitor with POST method + JSON body → checker sends body | — | Manual |
| **10G-B.T3** | Test: Create HTTP monitor with custom headers (Pro) → checker sends headers | — | Manual |
| **10G-B.T4** | Test: Edit existing monitor, add Bearer auth → save → re-edit → values preserved | — | Manual |
| **10G-B.T5** | Test: Edit existing monitor, add request body → save → re-edit → body preserved | — | Manual |
| **10G-B.T6** | Test: Free user sees custom headers as Pro-gated | — | Manual |

### Post-Launch Backlog (from this benchmark)

| Item | What |
|------|------|
| Accepted status code expressions (200,301 / 2xx,3xx) | M2 above |
| Notification delay + repeat settings | M3 above |

---

## 5. Implementation Notes

### Bearer Auth (10G-B.1)
- `add_monitor.html` + `edit_monitor.html`: Expand auth type `<select>` to include `bearer` option
- Show "Token" input when Bearer selected (single field, not username/password)
- `pages.py` POST handler: read `auth_type`, `bearer_token` fields
- Store on monitor doc: `auth_type: "bearer"`, `bearer_token: "eyJ..."`
- `checker.py` `check_url()`: if `bearer_token`, set `headers["Authorization"] = f"Bearer {bearer_token}"`
- Backward compatible: existing monitors with `basic_auth_user` continue working

### Request Body (10G-B.2)
- Show textarea + Content-Type dropdown only when HTTP method is POST/PUT/PATCH/DELETE
- JS: listen to method button clicks, show/hide body section
- `pages.py`: read `request_body`, `request_content_type` from form
- Store on monitor doc: `request_body: "..."`, `request_content_type: "application/json"`
- `checker.py` `check_url()`: add `content` param, pass as `content=body` + set Content-Type header
- Default Content-Type: `application/json`

### Custom Headers (10G-B.3)
- Same builder pattern as JSON assertions: key + value + remove button
- `pages.py`: read `header_key[]`, `header_value[]` arrays, build list of dicts
- Store on monitor doc: `custom_headers: [{key: "X-Api-Key", value: "abc123"}, ...]`
- `checker.py`: merge custom_headers into headers dict before request
- Pro-gated: Free users see greyed out section with upgrade CTA
