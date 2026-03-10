# Codebase Review — StatusRooster
**Date:** March 9, 2026
**Reviewed by:** Claude Opus 4.6
**Codebase:** Python 3.12 / FastAPI / Firestore / Cloud Run
**Stage:** Day 11, pre-launch — growing but clean

---

## Quick-Reference Checklist

> Copy this to a GitHub Issue or use it as your daily punch list.
> Check items off as you complete them.

### 🔴 P1 — Fix Before Launch
- [x] **#1** Cron auth bypass — remove User-Agent fallback (`routers/cron.py`)
- [x] **#2** JWT secret default — raise on startup if not set (`config.py`)
- [x] **#3** SSRF protection — block private/internal IPs (`services/checker.py`, `routers/pages.py`)
- [x] **#4** Rate limit `/api/check-url` — prevent open proxy abuse (`routers/pages.py`)
- [x] **#5** Replace `get_all_monitors()` — paginate or filter due monitors only (`models/monitor.py`, `services/checker.py`)
- [x] **#6** Heartbeat ping secret — add `ping_token` validation (`routers/heartbeat.py`, `models/monitor.py`)

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

---

## Executive Summary

StatusRooster is well-structured for an indie solo project — clean separation between models, services, and routers, and the monitoring logic is solid with retry, concurrency limiting, and batch writes. **The biggest risk is security**: the cron endpoint can be bypassed by spoofing a User-Agent header, there's no SSRF protection on user-submitted URLs, and the JWT secret has a dangerous default value. **The biggest scalability risk** is `get_all_monitors()` loading every monitor across every user into memory on each cron tick — this will break around 500-1000 monitors. Code quality is genuinely good for a vibe-coded project — the main debt is in `pages.py` which has grown to ~900 lines and duplicates logic that exists in the API router.

---

## Priority Action Items

### P1 — Fix Immediately (blocks reliability or security)

- [ ] **#1** | Security | `routers/cron.py`
  - **Issue:** Cron auth can be bypassed by setting `User-Agent: Google-Cloud-Scheduler`
  - **Action:** Remove User-Agent fallback; require `X-Cron-Secret` header or use GCP OIDC token verification

- [ ] **#2** | Security | `config.py`
  - **Issue:** JWT_SECRET defaults to `"change-me-to-a-random-string"` — if `.env` is missing, every token is signed with a known key
  - **Action:** Remove the default entirely; raise on startup if not set

- [ ] **#3** | Security | `routers/pages.py`, `services/checker.py`
  - **Issue:** No SSRF protection — users can submit `http://169.254.169.254/...` (GCP metadata), `http://localhost`, or internal IPs as monitor URLs
  - **Action:** Add URL validation that blocks private/reserved IP ranges and metadata endpoints before any HTTP request

- [ ] **#4** | Security | `routers/pages.py`
  - **Issue:** `public_url_check` endpoint has no rate limiting — anyone can use your server as a proxy to scan arbitrary URLs
  - **Action:** Add rate limiting (by IP or session) to `/api/check-url`

- [ ] **#5** | Reliability | `services/checker.py`
  - **Issue:** `get_all_monitors()` loads every monitor for every user into memory on each cron tick
  - **Action:** Needs pagination or per-user fan-out (see detailed finding below)

- [ ] **#6** | Security | `routers/heartbeat.py`
  - **Issue:** Monitor ID is the only "auth" for heartbeat pings — IDs are predictable Firestore auto-IDs, anyone who guesses one can send fake heartbeats
  - **Action:** Add a per-monitor secret token generated at creation time

### P2 — Fix Soon (will hurt at scale)

- [ ] **#7** | Scalability | `models/check.py`
  - **Issue:** `get_daily_uptime()` and `get_recent_checks()` scan raw check docs — at 288 checks/day/monitor, 100 monitors = 28,800 docs per dashboard load
  - **Action:** Migrate to pre-aggregated `daily_uptime_bars` / `hourly_uptime_bars` on the monitor doc (you've started this — finish removing the raw-query fallbacks)

- [ ] **#8** | Scalability | `routers/pages.py`
  - **Issue:** Dashboard loads all monitors + all 24h incidents + computes 24h uptime per monitor on every page load — no caching
  - **Action:** Add a short TTL cache (even 30s) for dashboard data, or precompute aggregate stats on the monitor doc during cron

- [ ] **#9** | Architecture | `routers/pages.py`
  - **Issue:** This file is ~900 lines and growing — handles auth, CRUD, monitor detail, status pages, settings, API keys, bulk ops, and more
  - **Action:** Split into `pages/dashboard.py`, `pages/monitors.py`, `pages/settings.py`, `pages/public.py`

- [ ] **#10** | Code Quality | `routers/monitors.py` vs `routers/api_v1.py`
  - **Issue:** Internal and public APIs duplicate create/update/delete logic with slightly different validation — a bug fixed in one may not be fixed in the other
  - **Action:** Extract shared validation/business logic into a service layer (`services/monitors.py`)

- [ ] **#11** | Scalability | `models/monitor.py`
  - **Issue:** `delete_monitor()` only cleans up 50 checks and 50 incidents — orphaned data accumulates
  - **Action:** Add a background cleanup job (Cloud Task or scheduled) that purges orphaned checks/incidents for deleted monitors

- [ ] **#12** | Reliability | `services/alerts.py`
  - **Issue:** `_email_fail_count` is a global in-memory counter — resets on every Cloud Run instance restart, and each instance has its own counter
  - **Action:** Move circuit breaker state to Firestore or Redis if you want it to actually work across instances

- [ ] **#13** | Security | `routers/pages.py`
  - **Issue:** Flash messages passed via cookies (`flash_message`, `new_api_key`) — the raw API key is set as a cookie value which could be logged by proxies/CDNs
  - **Action:** Pass the new API key via a one-time Firestore doc or in-memory session instead of a cookie

### P3 — Nice to Have (quality/maintainability)

- [ ] **#14** | Code Quality | `models/*.py`
  - **Issue:** Every model function accepts `db` as the first param — creates coupling and repetition
  - **Action:** Consider a lightweight repository pattern or just import `get_db()` inside each model module

- [ ] **#15** | Code Quality | `services/checker.py`
  - **Issue:** `run_checks()` is a ~200-line function doing filtering, checking, incident management, alerting, and stats
  - **Action:** Extract into `_filter_due_monitors()`, `_process_check_result()`, `_handle_status_change()`

- [ ] **#16** | Code Quality | `routers/pages.py`
  - **Issue:** `add_monitor` and `edit_monitor_submit` are 100+ line functions that parse ~30 form fields each
  - **Action:** Extract form parsing into a shared helper or Pydantic model

- [ ] **#17** | Architecture | `models/monitor.py`
  - **Issue:** `create_monitor()` accepts 30+ parameters — hard to maintain and easy to miss new fields
  - **Action:** Accept a dict or dataclass instead of individual kwargs

- [ ] **#18** | Code Quality | `services/checker.py`
  - **Issue:** SSL check functions `check_ssl_certificate()` and `grab_ssl_info()` are nearly identical — ~60 lines of duplicated code
  - **Action:** Merge into one function with a parameter for the return format

- [ ] **#19** | Testing | All
  - **Issue:** No test files were included in the upload — if tests exist, they weren't submitted; if they don't exist, this is a gap
  - **Action:** Add at least: unit tests for `checker.py` logic, integration tests for API endpoints, and a smoke test for the cron cycle

- [ ] **#20** | Code Quality | `routers/pages.py`
  - **Issue:** `monitor_detail` route is ~120 lines computing stats that could live in a service function
  - **Action:** Move stats computation to `services/stats.py`

---

## Detailed Findings

### 1. Cron Endpoint Auth Bypass
- [x] **Status: Complete** (Mar 9, 2026)
- **Area:** Security
- **File:** `routers/cron.py` lines 17-22
- **Problem:** If `X-Cron-Secret` doesn't match, the code falls back to checking if `User-Agent` contains `"Google-Cloud-Scheduler"`. Any attacker can set this header and trigger checks (or abuse it for DoS).
- **Impact:** Unauthorized cron execution, potential abuse of your outbound HTTP pool to scan targets.
- **Fix:** Remove the User-Agent fallback. Use only the shared secret, or properly verify GCP OIDC tokens using Google's auth libraries.
- **Copilot prompt:** `@workspace In routers/cron.py, remove the User-Agent fallback in the cron_check endpoint. Only allow requests that provide the correct X-Cron-Secret header. Return 403 for all other requests.`
- **Verification:**
  - [ ] User-Agent fallback code removed
  - [ ] Tested: request without X-Cron-Secret returns 403
  - [ ] Tested: request with correct X-Cron-Secret succeeds
  - [ ] Cloud Scheduler updated to send the header

### 2. JWT Secret Default Value
- [x] **Status: Complete** (Mar 9, 2026)
- **Area:** Security
- **File:** `config.py` line 8
- **Problem:** `JWT_SECRET` defaults to `"change-me-to-a-random-string"`. If deployed without a `.env` file (common in staging or accidental prod deploys), anyone can forge valid JWTs.
- **Impact:** Complete account takeover for every user.
- **Fix:** Raise an error at startup if `JWT_SECRET` is the default or unset in production.
- **Copilot prompt:** `@workspace In config.py, add a check in Settings.__init__ or as a module-level assertion: if APP_ENV is "production" and JWT_SECRET is "change-me-to-a-random-string" or empty, raise RuntimeError("JWT_SECRET must be set in production").`
- **Verification:**
  - [ ] Default removed or startup check added
  - [ ] Tested: app refuses to start in production mode with default secret
  - [ ] Tested: app starts normally with a proper secret set

### 3. SSRF on User-Submitted URLs
- [x] **Status: Complete** (Mar 9, 2026)
- **Area:** Security
- **File:** `services/checker.py`, `routers/pages.py`
- **Problem:** Users can create monitors pointing to internal IPs (127.0.0.1, 10.x.x.x, 169.254.169.254). Your checker will make HTTP requests to those addresses from inside your Cloud Run container — exposing the GCP metadata server, internal services, and potentially other VPC resources.
- **Impact:** GCP service account token theft, internal network scanning, SSRF-based attacks.
- **Fix:** Before making any HTTP request, resolve the hostname to an IP and reject private/reserved ranges (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, fd00::/8). Apply this in both `check_url()` and `public_url_check()`.
- **Copilot prompt:** `@workspace Create a function validate_url_not_internal(url: str) in services/checker.py that resolves the URL's hostname via socket.getaddrinfo and raises ValueError if the resolved IP is in any private/reserved range (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16). Call this function at the top of check_url() and in the public_url_check endpoint in pages.py before making any HTTP request.`
- **Verification:**
  - [ ] `validate_url_not_internal()` function created
  - [ ] Called in `check_url()`
  - [ ] Called in `public_url_check()`
  - [ ] Called in `check_json_api()`
  - [ ] Tested: `http://169.254.169.254` rejected
  - [ ] Tested: `http://127.0.0.1` rejected
  - [ ] Tested: `http://10.0.0.1` rejected
  - [ ] Tested: normal public URLs still work

### 4. No Rate Limiting on Public URL Check
- [x] **Status: Complete** (Mar 9, 2026)
- **Area:** Security
- **File:** `routers/pages.py` — `public_url_check` endpoint
- **Problem:** `/api/check-url` is unauthenticated and makes outbound HTTP requests to any URL. An attacker can use this as an open proxy / port scanner by sending thousands of requests.
- **Impact:** Your server becomes a tool for attacking other services, and your GCP egress costs spike.
- **Fix:** Add IP-based rate limiting (e.g., 10 requests/minute per IP). You already have in-process rate limiting for `check-now` — apply the same pattern here.
- **Copilot prompt:** `@workspace Add an in-process rate limiter to the public_url_check endpoint in routers/pages.py. Use the same pattern as the _check_now_last dict in the same file. Limit to 10 requests per minute per client IP address (use request.client.host). Return 429 with a retry_after if exceeded.`
- **Verification:**
  - [ ] Rate limiter dict added for `/api/check-url`
  - [ ] Tested: 11th request within 60s returns 429
  - [ ] Tested: requests from different IPs are independent
  - [ ] Landing page still works for normal usage

### 5. get_all_monitors() Scalability Ceiling
- [x] **Status: Complete** (Mar 9, 2026)
- **Area:** Scalability
- **File:** `models/monitor.py` line 209, `services/checker.py`
- **Problem:** `get_all_monitors()` calls `db.collection("monitors").get()` — this loads every monitor document for every user into memory in a single query. Firestore charges per doc read and this will get slow and expensive quickly.
- **Impact:** At ~500+ monitors, cron cycles will start timing out (Cloud Run default timeout). At 1000+, you'll hit memory limits on small Cloud Run instances.
- **Fix:** Two options: (a) paginate with Firestore cursors and process in batches, or (b) query only monitors where `last_checked < (now - check_interval)` which also eliminates the in-Python filtering in `run_checks()`. Option (b) is cleaner but requires a composite index.
- **Copilot prompt:** `@workspace In models/monitor.py, replace get_all_monitors() with get_due_monitors(db) that queries only monitors where paused == False. In services/checker.py run_checks(), use this new function and handle the interval check via Firestore query rather than loading all monitors into memory. Add a .limit(500) safety cap.`
- **Verification:**
  - [ ] `get_all_monitors()` replaced with filtered query
  - [ ] Paused monitors excluded at query level
  - [ ] Safety limit added
  - [ ] Firestore composite index created if needed
  - [ ] Cron cycle still completes successfully

### 6. Heartbeat Endpoint Has No Secret
- [x] **Status: Complete** (Mar 9, 2026)
- **Area:** Security
- **File:** `routers/heartbeat.py`
- **Problem:** The heartbeat ping URL is `/api/ping/{monitor_id}` where `monitor_id` is a Firestore auto-generated ID. These aren't cryptographically random — they're based on timestamp + random, but are shorter and more guessable than a proper secret. Anyone who discovers or guesses an ID can send fake "I'm alive" pings, masking real downtime.
- **Impact:** False positives — a monitor appears UP when the cron job has actually stopped running.
- **Fix:** When creating a heartbeat monitor, generate a separate `ping_token` (e.g., `secrets.token_urlsafe(32)`) stored on the monitor doc. The ping URL becomes `/api/ping/{monitor_id}?token={ping_token}` and the endpoint validates the token before recording the heartbeat.
- **Copilot prompt:** `@workspace In models/monitor.py create_monitor(), when monitor_type is "heartbeat", generate a ping_token field using secrets.token_urlsafe(32). In routers/heartbeat.py receive_heartbeat(), accept a "token" query param and validate it matches monitor["ping_token"] before recording. Return 403 if it doesn't match. Update the ping_url to include the token.`
- **Verification:**
  - [ ] `ping_token` generated in `create_monitor()` for heartbeat type
  - [ ] `receive_heartbeat()` validates token param
  - [ ] Tested: ping without token returns 403
  - [ ] Tested: ping with correct token succeeds
  - [ ] Existing heartbeat monitors migrated (backfill tokens)
  - [ ] UI shows updated ping URL with token

---

## What's Working Well

**Solid monitoring engine.** The checker has retry with jitter, concurrency limiting via semaphore, connection pooling with a shared httpx client, batch writes for check records, and structured instrumentation logging. This is better than most indie projects at this stage.

**Clean model layer.** Each Firestore collection has its own module with clear CRUD functions. The separation makes it easy to understand what data lives where.

**Good incident lifecycle.** The detect → alert → resolve → recovery alert flow is complete with event logging on incidents. Deduplication (checking for open incidents before creating new ones) prevents alert storms.

**Maintenance window support.** Including overnight window handling is a thoughtful touch that competitors often get wrong.

**Incremental uptime bars.** Storing pre-aggregated daily/hourly bars on the monitor document is the right approach for Firestore — it avoids expensive historical queries on every page load.

**Well-scoped plan enforcement.** Free vs Pro gating is applied consistently across both the web UI and the API, with clear error messages.

---

## Recommended Next Steps

- [ ] **1. Fix P1 items 1-4 (security) before launch.** The cron bypass + SSRF + JWT default are the kind of issues that could be exploited within days of going public. These are 1-2 hour fixes each.
- [ ] **2. Add SSRF protection** — this is the most dangerous issue. A single request to `169.254.169.254` from your Cloud Run instance leaks your GCP service account token.
- [ ] **3. Add rate limiting to `/api/check-url`** — simplest P1 to fix, protects you from abuse.
- [ ] **4. Split `pages.py`** — at ~900 lines it's the biggest source of tech debt. Splitting it now is easy; in 2 months it'll be painful.
- [ ] **5. Extract shared business logic** between `routers/monitors.py` and `routers/api_v1.py` into `services/monitors.py` — reduces the surface area for inconsistent validation bugs.
- [ ] **6. Add basic tests** before launch — even just smoke tests for the cron cycle, auth flow, and monitor CRUD will catch regressions fast.
- [ ] **7. Replace `get_all_monitors()`** with a filtered query — this is your first scalability ceiling and the fix is straightforward.
- [ ] **8. Set up error tracking** (Sentry free tier or similar) — right now errors are just `print()` statements that disappear when the Cloud Run instance recycles.

---

## Progress Log

> Use this section to note when items were completed. Helps when re-running reviews.

| Date | Item | Notes |
|------|------|-------|
| Mar 9, 2026 | #1 Cron auth bypass | Removed User-Agent fallback — secret header only |
| Mar 9, 2026 | #2 JWT secret default | Startup RuntimeError if default used in production |
| Mar 9, 2026 | #3 SSRF protection | `validate_url_not_internal()` in checker.py, called in check_url(), check_json_api(), public_url_check() |
| Mar 9, 2026 | #4 Rate limit /api/check-url | `_url_check_rate` dict — 10 req/60s per IP, returns 429 + Retry-After |
| Mar 9, 2026 | #5 get_all_monitors() | Added get_due_monitors() — filters paused=False at Firestore level, .limit(500) safety cap; removed Python-side paused skip in run_checks() |
| Mar 9, 2026 | #6 Heartbeat ping token | `ping_token` generated at creation, validated in receive_heartbeat(), 403 on missing/wrong token, backwards-compat for legacy monitors |
