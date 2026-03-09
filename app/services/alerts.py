"""
Alert service — central dispatcher for all notification channels.
Easy to extend: just add a new function and call it from send_down_alert / send_recovery_alert.
"""

import httpx
import asyncio
from datetime import datetime, timezone
from app.config import settings


def _get_user_plan(user_id: str) -> str:
    """Look up a user's plan from Firestore. Returns 'free' or 'pro'."""
    if not user_id:
        return "free"
    try:
        from app.database import get_db
        db = get_db()
        user_ref = db.collection("users").document(user_id).get()
        if user_ref.exists:
            return user_ref.to_dict().get("plan", "free")
    except Exception:
        pass
    return "free"


# ---------------------------------------------------------------------------
# SendGrid email alerts — with retry + rate-limit resilience
# ---------------------------------------------------------------------------

_email_fail_count = 0  # Track consecutive failures for circuit-breaker

async def send_email(to: str, subject: str, html_body: str, max_retries: int = 3) -> bool:
    """
    Send an email via SendGrid API with retry and exponential backoff.
    Handles 429 rate limits, 5xx server errors, and network failures.
    Returns True on success.
    """
    global _email_fail_count
    api_key = settings.SENDGRID_API_KEY
    from_email = settings.SENDGRID_FROM_EMAIL

    if not api_key or not from_email:
        print("[alert] SendGrid not configured — skipping email")
        return False

    # Circuit breaker: if we've failed 10+ times in a row, back off
    if _email_fail_count >= 10:
        print(f"[alert] Email circuit breaker open ({_email_fail_count} consecutive failures) — skipping")
        return False

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_email, "name": "StatusRooster 🐓"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}],
    }

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=15.0,
                )
                if resp.status_code in (200, 202):
                    _email_fail_count = 0  # Reset circuit breaker on success
                    print(f"[alert] Email sent to {to}: {subject}")
                    return True
                elif resp.status_code == 429:
                    # Rate limited — back off and retry
                    wait = min(2 ** attempt * 5, 30)  # 5s, 10s, 20s
                    print(f"[alert] SendGrid rate limited (429) — retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(wait)
                    continue
                elif resp.status_code >= 500:
                    # Server error — retry with backoff
                    wait = 2 ** attempt * 2  # 2s, 4s, 8s
                    print(f"[alert] SendGrid server error {resp.status_code} — retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(wait)
                    continue
                else:
                    # 4xx client error (bad request, invalid email, etc.) — don't retry
                    _email_fail_count += 1
                    print(f"[alert] SendGrid error {resp.status_code}: {resp.text[:200]}")
                    return False
        except httpx.TimeoutException:
            wait = 2 ** attempt * 2
            print(f"[alert] SendGrid timeout — retrying in {wait}s (attempt {attempt+1}/{max_retries})")
            await asyncio.sleep(wait)
            continue
        except Exception as e:
            _email_fail_count += 1
            print(f"[alert] SendGrid exception: {e}")
            return False

    _email_fail_count += 1
    print(f"[alert] SendGrid failed after {max_retries} retries for {to}: {subject}")
    return False


# ---------------------------------------------------------------------------
# Slack webhook alerts
# ---------------------------------------------------------------------------

async def send_slack(webhook_url: str, message: str) -> bool:
    """Send a message to a Slack webhook. Returns True on success."""
    if not webhook_url:
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                webhook_url,
                json={"text": message},
                timeout=10.0,
            )
            if resp.status_code == 200:
                print(f"[alert] Slack message sent")
                return True
            else:
                print(f"[alert] Slack error {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"[alert] Slack exception: {e}")
        return False


# ---------------------------------------------------------------------------
# SMS alerts via Twilio
# ---------------------------------------------------------------------------

async def send_sms(phone: str, message: str) -> bool:
    """Send an SMS alert via Twilio REST API. Returns True on success."""
    if not phone:
        return False

    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_FROM_NUMBER

    if not account_sid or not auth_token or not from_number:
        print(f"[alert] Twilio not configured — skipping SMS to {phone}")
        return False

    # Clean phone number (ensure E.164 format)
    clean_phone = phone.strip()
    if not clean_phone.startswith("+"):
        clean_phone = f"+1{clean_phone}"  # Default to US

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={
                    "To": clean_phone,
                    "From": from_number,
                    "Body": message[:1600],  # Twilio max
                },
                auth=(account_sid, auth_token),
                timeout=15.0,
            )
            if resp.status_code in (200, 201):
                print(f"[alert] SMS sent to {phone}: {message[:50]}...")
                return True
            else:
                print(f"[alert] Twilio error {resp.status_code}: {resp.text[:200]}")
                return False
    except Exception as e:
        print(f"[alert] Twilio exception: {e}")
        return False


# ---------------------------------------------------------------------------
# High-level alert dispatchers
# ---------------------------------------------------------------------------

def _format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        remaining = seconds % 3600
        minutes = remaining // 60
        return f"{hours}h {minutes}m"


async def send_down_alert(monitor: dict, incident: dict) -> dict:
    """
    Send DOWN alerts through all configured channels.
    Called when a monitor transitions from UP/pending → DOWN.
    Returns dict of {channel: bool} indicating delivery success.
    """
    name = monitor.get("name", monitor.get("url", "Unknown"))
    url = monitor.get("url", "")
    monitor_id = monitor.get("id", "")
    user_id = monitor.get("user_id", "")
    user_plan = _get_user_plan(user_id)
    status_code = incident.get("status_code", "N/A")
    response_ms = monitor.get("last_response_ms")
    response_str = f"{response_ms:.0f}ms" if response_ms else "Timeout"
    time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    app_url = settings.APP_URL or "https://statusrooster.com"
    detail_url = f"{app_url}/monitors/{monitor_id}"

    results: dict[str, bool] = {}

    # --- Email ---
    alert_email = monitor.get("alert_email", "")
    if alert_email:
        subject = f"🔴 DOWN: {name} is not responding"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto;">
            <h2 style="color: #ef4444;">🔴 {name} is DOWN</h2>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px 0; color: #666;">URL</td><td style="padding: 8px 0;"><a href="{url}">{url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Status Code</td><td style="padding: 8px 0;"><strong>{status_code}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Response Time</td><td style="padding: 8px 0;">{response_str}</td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Detected</td><td style="padding: 8px 0;">{time_str}</td></tr>
            </table>
            <p><a href="{detail_url}" style="display: inline-block; background: #6366f1; color: #fff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Monitor Details →</a></p>
            <p style="color: #888; font-size: 13px; margin-top: 24px;">We'll notify you when it recovers.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
            <p style="color: #aaa; font-size: 12px;">StatusRooster 🐓 — Uptime monitoring for developers</p>
        </div>
        """
        results["email"] = await send_email(alert_email, subject, html)

    # --- Slack (Pro only) ---
    slack_webhook = monitor.get("alert_slack_webhook", "")
    if slack_webhook and user_plan == "pro":
        message = (
            f"🔴 *DOWN: {name}*\n"
            f"URL: {url}\n"
            f"Status Code: {status_code}\n"
            f"Response: {response_str}\n"
            f"Detected: {time_str}\n"
            f"<{detail_url}|View on StatusRooster →>"
        )
        results["slack"] = await send_slack(slack_webhook, message)

    # --- SMS (Pro only) ---
    sms_number = monitor.get("alert_sms", "")
    if sms_number and user_plan == "pro":
        results["sms"] = await send_sms(sms_number, f"DOWN: {name} ({url}) — Status {status_code}")

    return results


async def send_recovery_alert(monitor: dict, incident: dict) -> dict:
    """
    Send RECOVERY alerts through all configured channels.
    Called when a monitor transitions from DOWN → UP.
    Returns dict of {channel: bool} indicating delivery success.
    """
    name = monitor.get("name", monitor.get("url", "Unknown"))
    url = monitor.get("url", "")
    monitor_id = monitor.get("id", "")
    user_id = monitor.get("user_id", "")
    user_plan = _get_user_plan(user_id)
    duration_sec = incident.get("duration_seconds", 0) or 0
    duration_str = _format_duration(duration_sec)
    response_ms = monitor.get("last_response_ms")
    response_str = f"{response_ms:.0f}ms" if response_ms else "N/A"
    time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    app_url = settings.APP_URL or "https://statusrooster.com"
    detail_url = f"{app_url}/monitors/{monitor_id}"

    results: dict[str, bool] = {}

    # --- Email ---
    alert_email = monitor.get("alert_email", "")
    if alert_email:
        subject = f"🟢 RECOVERED: {name} is back up"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto;">
            <h2 style="color: #22c55e;">🟢 {name} is back UP</h2>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px 0; color: #666;">URL</td><td style="padding: 8px 0;"><a href="{url}">{url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Downtime</td><td style="padding: 8px 0;"><strong>{duration_str}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Response Time</td><td style="padding: 8px 0;">{response_str}</td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Recovered</td><td style="padding: 8px 0;">{time_str}</td></tr>
            </table>
            <p><a href="{detail_url}" style="display: inline-block; background: #6366f1; color: #fff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Monitor Details →</a></p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
            <p style="color: #aaa; font-size: 12px;">StatusRooster 🐓 — Uptime monitoring for developers</p>
        </div>
        """
        results["email"] = await send_email(alert_email, subject, html)

    # --- Slack (Pro only) ---
    slack_webhook = monitor.get("alert_slack_webhook", "")
    if slack_webhook and user_plan == "pro":
        message = (
            f"🟢 *RECOVERED: {name}*\n"
            f"URL: {url}\n"
            f"Downtime: {duration_str}\n"
            f"Response: {response_str}\n"
            f"Recovered: {time_str}\n"
            f"<{detail_url}|View on StatusRooster →>"
        )
        results["slack"] = await send_slack(slack_webhook, message)

    # --- SMS (Pro only) ---
    sms_number = monitor.get("alert_sms", "")
    if sms_number and user_plan == "pro":
        results["sms"] = await send_sms(sms_number, f"UP: {name} ({url}) — back up after {duration_str}")

    return results


# ---------------------------------------------------------------------------
# SSL Expiry Alert
# ---------------------------------------------------------------------------

async def send_ssl_expiry_alert(monitor: dict, days_left: int, expiry_date) -> None:
    """Send SSL certificate expiry warning through all configured channels."""
    name = monitor.get("name", monitor.get("url", "Unknown"))
    url = monitor.get("url", "")
    monitor_id = monitor.get("id", "")
    user_id = monitor.get("user_id", "")
    user_plan = _get_user_plan(user_id)
    app_url = settings.APP_URL or "https://statusrooster.com"
    detail_url = f"{app_url}/monitors/{monitor_id}"
    expiry_str = expiry_date.strftime("%b %d, %Y") if expiry_date else "Unknown"

    urgency = "⚠️" if days_left > 7 else "🚨"

    # --- Email ---
    alert_email = monitor.get("alert_email", "")
    if alert_email:
        subject = f"{urgency} SSL Certificate expires in {days_left} days: {name}"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto;">
            <h2 style="color: #e76f51;">{urgency} SSL Certificate Expiring Soon</h2>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px 0; color: #666;">Monitor</td><td style="padding: 8px 0;"><strong>{name}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">URL</td><td style="padding: 8px 0;"><a href="{url}">{url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Expires</td><td style="padding: 8px 0;"><strong>{expiry_str}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Days Left</td><td style="padding: 8px 0;"><strong style="color: #ef4444;">{days_left} days</strong></td></tr>
            </table>
            <p>Renew your SSL certificate before it expires to avoid downtime.</p>
            <p><a href="{detail_url}" style="display: inline-block; background: #e76f51; color: #fff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Monitor →</a></p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
            <p style="color: #aaa; font-size: 12px;">StatusRooster 🐓 — Uptime monitoring for developers</p>
        </div>
        """
        await send_email(alert_email, subject, html)

    # --- Slack (Pro only) ---
    slack_webhook = monitor.get("alert_slack_webhook", "")
    if slack_webhook and user_plan == "pro":
        message = (
            f"{urgency} *SSL Certificate Expiring: {name}*\n"
            f"URL: {url}\n"
            f"Expires: {expiry_str} ({days_left} days left)\n"
            f"<{detail_url}|View on StatusRooster →>"
        )
        await send_slack(slack_webhook, message)


# ---------------------------------------------------------------------------
# Keyword Missing Alert
# ---------------------------------------------------------------------------

async def send_keyword_alert(monitor: dict, keyword: str) -> None:
    """Send alert when expected keyword is not found on the page."""
    name = monitor.get("name", monitor.get("url", "Unknown"))
    url = monitor.get("url", "")
    monitor_id = monitor.get("id", "")
    user_id = monitor.get("user_id", "")
    user_plan = _get_user_plan(user_id)
    app_url = settings.APP_URL or "https://statusrooster.com"
    detail_url = f"{app_url}/monitors/{monitor_id}"
    time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # --- Email ---
    alert_email = monitor.get("alert_email", "")
    if alert_email:
        subject = f"🔍 Keyword missing on {name}"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto;">
            <h2 style="color: #e76f51;">🔍 Keyword Not Found</h2>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px 0; color: #666;">Monitor</td><td style="padding: 8px 0;"><strong>{name}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">URL</td><td style="padding: 8px 0;"><a href="{url}">{url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Expected Keyword</td><td style="padding: 8px 0;"><code>{keyword}</code></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Detected</td><td style="padding: 8px 0;">{time_str}</td></tr>
            </table>
            <p>The page responded with 200 OK but the expected keyword was not found in the response body.</p>
            <p><a href="{detail_url}" style="display: inline-block; background: #e76f51; color: #fff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Monitor →</a></p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
            <p style="color: #aaa; font-size: 12px;">StatusRooster 🐓 — Uptime monitoring for developers</p>
        </div>
        """
        await send_email(alert_email, subject, html)

    # --- Slack (Pro only) ---
    slack_webhook = monitor.get("alert_slack_webhook", "")
    if slack_webhook and user_plan == "pro":
        message = (
            f"🔍 *Keyword Missing: {name}*\n"
            f"URL: {url}\n"
            f"Expected: `{keyword}`\n"
            f"Detected: {time_str}\n"
            f"<{detail_url}|View on StatusRooster →>"
        )
        await send_slack(slack_webhook, message)


# ---------------------------------------------------------------------------
# Response Time Threshold Alert
# ---------------------------------------------------------------------------

async def send_threshold_alert(monitor: dict, actual_ms: float, threshold_ms) -> None:
    """Send alert when response time violates user-defined threshold condition."""
    name = monitor.get("name", monitor.get("url", "Unknown"))
    url = monitor.get("url", "")
    monitor_id = monitor.get("id", "")
    user_id = monitor.get("user_id", "")
    user_plan = _get_user_plan(user_id)
    app_url = settings.APP_URL or "https://statusrooster.com"
    detail_url = f"{app_url}/monitors/{monitor_id}"
    time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    condition_str = str(threshold_ms)

    # --- Email ---
    alert_email = monitor.get("alert_email", "")
    if alert_email:
        subject = f"🐢 Response threshold violated on {name}: {actual_ms:.0f}ms"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto;">
            <h2 style="color: #e76f51;">🐢 Response Threshold Violated</h2>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px 0; color: #666;">Monitor</td><td style="padding: 8px 0;"><strong>{name}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">URL</td><td style="padding: 8px 0;"><a href="{url}">{url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Response Time</td><td style="padding: 8px 0;"><strong style="color: #ef4444;">{actual_ms:.0f}ms</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Condition</td><td style="padding: 8px 0;"><code>{condition_str}</code></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Detected</td><td style="padding: 8px 0;">{time_str}</td></tr>
            </table>
            <p><a href="{detail_url}" style="display: inline-block; background: #e76f51; color: #fff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Monitor →</a></p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
            <p style="color: #aaa; font-size: 12px;">StatusRooster 🐓 — Uptime monitoring for developers</p>
        </div>
        """
        await send_email(alert_email, subject, html)

    # --- Slack (Pro only) ---
    slack_webhook = monitor.get("alert_slack_webhook", "")
    if slack_webhook and user_plan == "pro":
        message = (
            f"🐢 *Response Threshold Violated: {name}*\n"
            f"URL: {url}\n"
            f"Response: {actual_ms:.0f}ms (condition: `{condition_str}`)\n"
            f"Detected: {time_str}\n"
            f"<{detail_url}|View on StatusRooster →>"
        )
        await send_slack(slack_webhook, message)


# ---------------------------------------------------------------------------
# Webhook Notification (Pro feature)
# ---------------------------------------------------------------------------

async def send_webhook_notification(monitor: dict, event: str, check_result: dict) -> bool:
    """Send a webhook POST to user's configured URL on status change."""
    webhook_url = monitor.get("webhook_url", "")
    if not webhook_url:
        return False

    payload = {
        "event": event,
        "monitor_name": monitor.get("name", ""),
        "monitor_url": monitor.get("url", ""),
        "status": "up" if check_result.get("is_up") else "down",
        "status_code": check_result.get("status_code"),
        "response_ms": check_result.get("response_ms"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json", "User-Agent": "StatusRooster/1.0"},
                timeout=10.0,
            )
            if resp.status_code < 400:
                print(f"[alert] Webhook sent to {webhook_url}: {event}")
                return True
            else:
                print(f"[alert] Webhook error {resp.status_code}: {resp.text[:200]}")
                return False
    except Exception as e:
        print(f"[alert] Webhook exception: {e}")
        return False


# ---------------------------------------------------------------------------
# Test Alert (send a test notification to verify config)
# ---------------------------------------------------------------------------

async def send_test_alert(monitor: dict, user_plan: str = "free") -> dict:
    """
    Send a test alert through all configured channels.
    Returns dict of results per channel.
    """
    name = monitor.get("name", monitor.get("url", "Unknown"))
    url = monitor.get("url", "")
    monitor_id = monitor.get("id", "")
    app_url = settings.APP_URL or "https://statusrooster.com"
    detail_url = f"{app_url}/monitors/{monitor_id}"
    time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    results = {"email": False, "slack": False, "sms": False, "webhook": False}

    # --- Email ---
    alert_email = monitor.get("alert_email", "")
    if alert_email:
        subject = f"🧪 Test Alert: {name}"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto;">
            <h2 style="color: #22c55e;">🧪 Test Alert — It Works!</h2>
            <p>This is a test notification from StatusRooster. Your alert configuration is working correctly.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px 0; color: #666;">Monitor</td><td style="padding: 8px 0;"><strong>{name}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">URL</td><td style="padding: 8px 0;"><a href="{url}">{url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Sent At</td><td style="padding: 8px 0;">{time_str}</td></tr>
            </table>
            <p><a href="{detail_url}" style="display: inline-block; background: #6366f1; color: #fff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Monitor →</a></p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
            <p style="color: #aaa; font-size: 12px;">StatusRooster 🐓 — Uptime monitoring for developers</p>
        </div>
        """
        results["email"] = await send_email(alert_email, subject, html)

    # --- Slack ---
    slack_webhook = monitor.get("alert_slack_webhook", "")
    if slack_webhook:
        message = (
            f"🧪 *Test Alert: {name}*\n"
            f"This is a test notification — your Slack alerts are working!\n"
            f"URL: {url}\n"
            f"Sent: {time_str}\n"
            f"<{detail_url}|View on StatusRooster →>"
        )
        results["slack"] = await send_slack(slack_webhook, message)

    # --- SMS (Pro only) ---
    sms_number = monitor.get("alert_sms", "")
    if sms_number and user_plan == "pro":
        results["sms"] = await send_sms(sms_number, f"Test alert from StatusRooster: {name} — your SMS alerts are working!")

    # --- Webhook (Pro only) ---
    webhook_url = monitor.get("webhook_url", "")
    if webhook_url and user_plan != "free":
        payload = {
            "event": "test",
            "monitor_name": name,
            "monitor_url": url,
            "status": "test",
            "status_code": None,
            "response_ms": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "StatusRooster/1.0"},
                    timeout=10.0,
                )
                results["webhook"] = resp.status_code < 400
        except Exception:
            results["webhook"] = False

    return results
