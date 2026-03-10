# Codebase Review — StatusRooster (v2)
**Date:** March 9, 2026
**Reviewed by:** Claude Opus 4.6
**Codebase:** Python 3.12 / FastAPI / Firestore / Cloud Run
**Stage:** Day 11, pre-launch — P1 security sprint complete

---

## Quick-Reference Checklist

> Updated after P1 sprint. Items marked ✅ have been verified in the code.

### 🔴 P1 — Fix Before Launch
- [x] **#1** Cron auth bypass — removed User-Agent fallback ✅
- [x] **#2** JWT secret default — raises RuntimeError in production ✅
- [x] **#3** SSRF protection — blocks private/internal IPs ✅
- [x] **#4** Rate limit `/api/check-url` — 10 req/min per IP ✅
- [x] **#5** Replace `get_all_monitors()` — `get_due_monitors()` with paused filter + 500 cap ✅
- [x] **#6** Heartbeat ping secret — `ping_token` generated and validated ✅

### 🟡 P2 — Fix Soon (post-launch sprint)
- [ ] **#7** Remove raw check queries — finish migration to pre-aggregated bars (`models/check.py`)
- [ ] **#8** Cache dashboard data — add short TTL or precompute stats (`routers/pages.py`)
- [ ] **#9** Split `pages.py` — break into dashboard, monitors, settings, public modules (`routers/pages.py`)
- [ ] **#10** Deduplicate API logic — extract shared validation to `services/monitors.py` (`routers/monitors.py`, `routers/api_v1.py`)
- [ ] **#11** Orphaned data cleanup — background job for deleted monitor data (`models/monitor.py`)
- [ ] **#12** Circuit breaker persistence — move `_email_fail_count` out of memory (`services/alerts.py`)
- [ ] **#13** API key in cookie — use one-time Firestore doc instead (`routers/pages.py`)

### 🟢 P3 — Nice to Have
- [ ] **#14** Remove `db` param passing — import `get_db()` in models (`models/*.py`)
- [ ] **#15** Break up `run_checks()` — extract sub-functions (`services/checker.py`)
- [ ] **#16** Extract form parsing — shared helper for 30+ field forms (`routers/pages.py`)
- [ ] **#17** Simplify `create_monitor()` — use dict/dataclass instead of 30+ kwargs (`models/monitor.py`)
- [ ] **#18** Merge duplicate SSL functions — `check_ssl_certificate()` + `grab_ssl_info()` (`services/checker.py`)
- [ ] **#19** Add tests — unit, integration, and cron smoke tests (all)
- [ ] **#20** Extract stats computation — move to `services/stats.py` (`routers/pages.py`)

### 🆕 New Issues Found in This Review
- [ ] **#21** Rate limiter memory leak — `_url_check_rate` dict grows unbounded (`routers/pages.py`)
- [ ] **#22** Heartbeat backfill script missing — legacy monitors accept pings without token (`routers/heartbeat.py`)
- [ ] **#23** SSRF bypass via DNS rebinding — validation happens before request, hostname could resolve differently at request time (`services/checker.py`)
- [ ] **#24** `get_due_monitors()` 500-cap silently drops monitors — no warning when limit is hit (`models/monitor.py`)

---

## P1 Sprint Audit — Detailed Verification

### #1 Cron Auth Bypass — ✅ FIXED
- [x] User-Agent fallback code removed
- [x] Only `X-Cron-Secret` header and `?secret=` query param accepted
- [x] Returns 403 for all unauthorized requests
- [ ] **Remaining:** Cloud Scheduler should be updated to send `X-Cron-Secret` header if it isn't already (can't verify from code alone)

**Code review notes:** Clean fix. The `query_secret` fallback is fine for testing but consider removing it for production since query params can appear in access logs.

### #2 JWT Secret Default — ✅ FIXED
- [x] Startup check added at module level in `config.py`
- [x] Raises `RuntimeError` if `APP_ENV=production` and JWT_SECRET is default or empty
- [x] Includes helpful generation command in the error message

**Code review notes:** Well implemented. The check runs at import time so the app won't even start if misconfigured. One minor note: the default `"change-me-to-a-random-string"` is still there for development mode, which is fine.

### #3 SSRF Protection — ✅ FIXED
- [x] `validate_url_not_internal()` function created in `services/checker.py`
- [x] Blocks 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16
- [x] Also blocks 100.64.0.0/10 (shared address space) — good addition beyond what was requested
- [x] Also blocks IPv6 loopback, unique local, and link-local — thorough
- [x] Called in `check_url()` — returns a safe error dict with `ssrf_blocked: True`
- [x] Called in `check_json_api()` — same pattern
- [x] Called in `public_url_check()` in `pages.py` — returns 400 with error message
- [x] Uses `socket.getaddrinfo()` to resolve before checking — catches domain names pointing to internal IPs

**Code review notes:** This is a strong implementation. The `_PRIVATE_NETWORKS` list is comprehensive. One edge case to be aware of (see new issue #23): DNS rebinding attacks could theoretically bypass this since the hostname is resolved once for validation but then again by httpx when making the actual request. For an indie SaaS this is a low-probability risk, but worth noting.

### #4 Rate Limit on Public URL Check — ✅ FIXED
- [x] Rate limiter added to `public_url_check` in `pages.py`
- [x] 10 requests per 60-second window per client IP
- [x] Returns 429 with `Retry-After` header
- [x] Uses sliding window approach (keeps list of timestamps per IP)

**Code review notes:** Works correctly. One issue (see new item #21): the `_url_check_rate` dict is never cleaned up — old IPs stay in memory forever. On Cloud Run this is partially mitigated by instance recycling, but on a long-lived instance it's a slow memory leak. Add a periodic cleanup or use a TTL dict.

### #5 get_all_monitors() Replaced — ✅ FIXED
- [x] New `get_due_monitors()` function added to `models/monitor.py`
- [x] Filters `paused == False` at Firestore query level
- [x] `.limit(500)` safety cap applied
- [x] `run_checks()` in `checker.py` updated to use `get_due_monitors()`
- [x] Old `get_all_monitors()` kept but marked as deprecated with docstring

**Code review notes:** Good implementation. The interval-elapsed check is still done in Python, which is the right call — doing it in Firestore would require a composite index and per-document arithmetic that Firestore can't handle natively. One concern (see new issue #24): when you hit 500+ active monitors, the `.limit(500)` will silently drop some monitors from being checked. You'll want to either log a warning when the limit is hit, or paginate.

### #6 Heartbeat Ping Secret — ✅ FIXED
- [x] `ping_token` field generated via `secrets.token_urlsafe(32)` in `create_monitor()` for heartbeat type
- [x] `receive_heartbeat()` in `heartbeat.py` validates token query param
- [x] Returns 403 if token doesn't match
- [x] Legacy monitors (no `ping_token` field) are accepted without token — good backwards compatibility
- [x] Ping URL in `add_monitor` (pages.py) now includes `?token={ping_token}`
- [x] Docstring updated with new URL format and migration note
- [ ] **Remaining:** `scripts/backfill_ping_tokens.py` is referenced in the docstring but doesn't exist yet — legacy monitors remain unprotected until this is run
- [ ] **Remaining:** API v1 `api_create_monitor` in `api_v1.py` — should also include token in the ping URL (need to verify)

**Code review notes:** Solid implementation with thoughtful backwards compatibility. The legacy fallback is the right approach for a live system — don't break existing users' cron jobs. Just make sure the backfill script gets created before you forget.

---

## New Issues Found

### #21 Rate Limiter Memory Leak
- [ ] **Status: New**
- **Area:** Reliability
- **File:** `routers/pages.py` — `_url_check_rate` dict
- **Problem:** The sliding window rate limiter stores timestamps per IP in a plain dict. Old entries (from IPs that visited once and never returned) are never cleaned up. Over time this dict grows without bound.
- **Impact:** Slow memory leak. On Cloud Run instances that get recycled frequently this is minor, but if an instance stays alive for hours under steady traffic, memory usage creeps up.
- **Fix:** Add a simple cleanup — either prune stale IPs periodically (e.g., every 100 requests, remove IPs with no hits in the last 5 minutes) or cap the dict size.
- **Copilot prompt:** `@workspace In routers/pages.py, add cleanup logic to the _url_check_rate dict in public_url_check. Every 100th request, iterate through the dict and delete any IPs whose newest timestamp is older than 5 minutes. Use a simple counter variable to track when to run cleanup.`

### #22 Heartbeat Backfill Script Missing
- [ ] **Status: New**
- **Area:** Security
- **File:** Referenced in `routers/heartbeat.py` docstring as `scripts/backfill_ping_tokens.py`
- **Problem:** The heartbeat docstring references a migration script that doesn't exist. Any heartbeat monitors created before this update have no `ping_token` and accept unauthenticated pings.
- **Impact:** Legacy heartbeat monitors remain vulnerable to fake heartbeat injection until tokens are backfilled.
- **Fix:** Create `scripts/backfill_ping_tokens.py` that queries all heartbeat monitors without a `ping_token` field, generates one, updates the monitor doc, and logs the new ping URL.
- **Copilot prompt:** `@workspace Create scripts/backfill_ping_tokens.py that: 1) connects to Firestore, 2) queries all monitors where monitor_type == "heartbeat" and ping_token is null, 3) generates a secrets.token_urlsafe(32) for each, 4) updates the monitor doc with the new ping_token and updated ping_url that includes ?token=..., 5) prints each updated monitor name and new URL. Include a --dry-run flag.`

### #23 SSRF DNS Rebinding (Low Priority)
- [ ] **Status: New (informational)**
- **Area:** Security
- **File:** `services/checker.py`
- **Problem:** `validate_url_not_internal()` resolves the hostname via DNS, then `httpx` resolves it again when making the actual request. An attacker could configure DNS to return a public IP on the first lookup (passing validation) and a private IP on the second (hitting internal resources). This is called DNS rebinding.
- **Impact:** Theoretical SSRF bypass. Requires attacker-controlled DNS, making it unlikely for an indie SaaS target. Low probability, medium severity.
- **Fix (if you want to close it):** After resolving, make the HTTP request directly to the resolved IP with the `Host` header set to the original hostname. Or use httpx's transport layer to pin the resolved address.
- **Copilot prompt:** `@workspace In services/checker.py validate_url_not_internal(), return the resolved IP addresses. In check_url(), use the resolved IP to make the request instead of the hostname — set the URL to use the IP and add a Host header with the original hostname. This prevents DNS rebinding attacks.`

### #24 get_due_monitors() Silent Cap
- [ ] **Status: New**
- **Area:** Reliability
- **File:** `models/monitor.py` — `get_due_monitors()`
- **Problem:** The `.limit(500)` cap means if you have 501+ active monitors, some will silently never be checked. There's no warning logged when this happens.
- **Impact:** Missed checks for monitors beyond the 500th. Users won't know their monitors aren't being checked.
- **Fix:** After the query, check if exactly 500 results were returned. If so, log a warning. Long-term, paginate with Firestore cursors to handle the full set.
- **Copilot prompt:** `@workspace In models/monitor.py get_due_monitors(), after fetching docs, if len(monitors) == 500, log a warning using the logger: "WARNING: get_due_monitors() hit 500-document cap — some monitors may not be checked this cycle. Consider implementing pagination." Return the monitors either way.`

---

## What's Working Well (Updated)

Everything from the v1 review still holds, plus:

**Security posture is now solid for launch.** SSRF protection with comprehensive IP range blocking, rate limiting on the public endpoint, proper cron authentication, JWT validation on startup, and authenticated heartbeat pings. This is above average for indie SaaS projects.

**Backwards compatibility handled well.** The heartbeat token migration path (accept old monitors without tokens, require tokens on new ones) is the right pattern for a live system.

**Clean SSRF implementation.** The `_PRIVATE_NETWORKS` list covers IPv4 and IPv6 private ranges, including the often-missed 100.64.0.0/10 shared address space. The function is well-documented and easy to extend.

---

## Recommended Next Steps (Updated)

- [x] ~~Fix P1 items 1-6~~ ✅ Done
- [ ] **1. Create the backfill script** for heartbeat ping tokens (#22) — 15 min fix, closes the last security gap
- [ ] **2. Fix the rate limiter memory leak** (#21) — quick 10-line fix
- [ ] **3. Add the 500-cap warning log** (#24) — one-liner, prevents silent failures
- [ ] **4. Split `pages.py`** (#9) — still the biggest source of tech debt at ~950 lines
- [ ] **5. Add basic tests** (#19) — at minimum, test the SSRF validation function and cron auth
- [ ] **6. Extract shared API logic** (#10) — reduces surface area for validation inconsistencies
- [ ] **7. Set up error tracking** (Sentry free tier) — `print()` statements don't survive instance recycling

---

## Progress Log

| Date | Item | Notes |
|------|------|-------|
| Mar 9 | #1 Cron auth | Removed User-Agent fallback, X-Cron-Secret only |
| Mar 9 | #2 JWT default | RuntimeError on production startup with default secret |
| Mar 9 | #3 SSRF | `validate_url_not_internal()` with comprehensive IP blocking |
| Mar 9 | #4 Rate limit | 10 req/min per IP on `/api/check-url` |
| Mar 9 | #5 get_all_monitors | Replaced with `get_due_monitors()`, paused filter + 500 cap |
| Mar 9 | #6 Heartbeat secret | `ping_token` generated on creation, validated on ping |
