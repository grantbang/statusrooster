"""
Alert service — central dispatcher for all notification channels.
Easy to extend: just add a new function and call it from send_down_alert / send_recovery_alert.
"""

import httpx
from datetime import datetime, timezone
from app.config import settings


# ---------------------------------------------------------------------------
# SendGrid email alerts
# ---------------------------------------------------------------------------

async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email via SendGrid API. Returns True on success."""
    api_key = settings.SENDGRID_API_KEY
    from_email = settings.SENDGRID_FROM_EMAIL

    if not api_key or not from_email:
        print("[alert] SendGrid not configured — skipping email")
        return False

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_email, "name": "StatusRooster 🐓"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}],
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
            if resp.status_code in (200, 202):
                print(f"[alert] Email sent to {to}: {subject}")
                return True
            else:
                print(f"[alert] SendGrid error {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"[alert] SendGrid exception: {e}")
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
# SMS alerts (placeholder — ready for Twilio integration)
# ---------------------------------------------------------------------------

async def send_sms(phone: str, message: str) -> bool:
    """Send an SMS alert. Placeholder for Twilio integration."""
    if not phone:
        return False
    # TODO: Implement Twilio SMS
    print(f"[alert] SMS not yet implemented — would send to {phone}")
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


async def send_down_alert(monitor: dict, incident: dict) -> None:
    """
    Send DOWN alerts through all configured channels.
    Called when a monitor transitions from UP/pending → DOWN.
    """
    name = monitor.get("name", monitor.get("url", "Unknown"))
    url = monitor.get("url", "")
    monitor_id = monitor.get("id", "")
    status_code = incident.get("status_code", "N/A")
    response_ms = monitor.get("last_response_ms")
    response_str = f"{response_ms:.0f}ms" if response_ms else "Timeout"
    time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    app_url = settings.APP_URL or "https://statusrooster.com"
    detail_url = f"{app_url}/monitors/{monitor_id}"

    # --- Email ---
    alert_email = monitor.get("alert_email", "")
    if alert_email:
        subject = f"🔴 DOWN: {name} is not responding"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto;">
            <h2 style="color: #e63946;">🔴 {name} is DOWN</h2>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px 0; color: #666;">URL</td><td style="padding: 8px 0;"><a href="{url}">{url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Status Code</td><td style="padding: 8px 0;"><strong>{status_code}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Response Time</td><td style="padding: 8px 0;">{response_str}</td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Detected</td><td style="padding: 8px 0;">{time_str}</td></tr>
            </table>
            <p><a href="{detail_url}" style="display: inline-block; background: #e63946; color: #fff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Monitor Details →</a></p>
            <p style="color: #888; font-size: 13px; margin-top: 24px;">We'll notify you when it recovers.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
            <p style="color: #aaa; font-size: 12px;">StatusRooster 🐓 — Uptime monitoring for developers</p>
        </div>
        """
        await send_email(alert_email, subject, html)

    # --- Slack ---
    slack_webhook = monitor.get("alert_slack_webhook", "")
    if slack_webhook:
        message = (
            f"🔴 *DOWN: {name}*\n"
            f"URL: {url}\n"
            f"Status Code: {status_code}\n"
            f"Response: {response_str}\n"
            f"Detected: {time_str}\n"
            f"<{detail_url}|View on StatusRooster →>"
        )
        await send_slack(slack_webhook, message)

    # --- SMS ---
    sms_number = monitor.get("alert_sms", "")
    if sms_number:
        await send_sms(sms_number, f"DOWN: {name} ({url}) — Status {status_code}")


async def send_recovery_alert(monitor: dict, incident: dict) -> None:
    """
    Send RECOVERY alerts through all configured channels.
    Called when a monitor transitions from DOWN → UP.
    """
    name = monitor.get("name", monitor.get("url", "Unknown"))
    url = monitor.get("url", "")
    monitor_id = monitor.get("id", "")
    duration_sec = incident.get("duration_seconds", 0) or 0
    duration_str = _format_duration(duration_sec)
    response_ms = monitor.get("last_response_ms")
    response_str = f"{response_ms:.0f}ms" if response_ms else "N/A"
    time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    app_url = settings.APP_URL or "https://statusrooster.com"
    detail_url = f"{app_url}/monitors/{monitor_id}"

    # --- Email ---
    alert_email = monitor.get("alert_email", "")
    if alert_email:
        subject = f"🟢 RECOVERED: {name} is back up"
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto;">
            <h2 style="color: #2a9d8f;">🟢 {name} is back UP</h2>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr><td style="padding: 8px 0; color: #666;">URL</td><td style="padding: 8px 0;"><a href="{url}">{url}</a></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Downtime</td><td style="padding: 8px 0;"><strong>{duration_str}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Response Time</td><td style="padding: 8px 0;">{response_str}</td></tr>
                <tr><td style="padding: 8px 0; color: #666;">Recovered</td><td style="padding: 8px 0;">{time_str}</td></tr>
            </table>
            <p><a href="{detail_url}" style="display: inline-block; background: #2a9d8f; color: #fff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Monitor Details →</a></p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
            <p style="color: #aaa; font-size: 12px;">StatusRooster 🐓 — Uptime monitoring for developers</p>
        </div>
        """
        await send_email(alert_email, subject, html)

    # --- Slack ---
    slack_webhook = monitor.get("alert_slack_webhook", "")
    if slack_webhook:
        message = (
            f"🟢 *RECOVERED: {name}*\n"
            f"URL: {url}\n"
            f"Downtime: {duration_str}\n"
            f"Response: {response_str}\n"
            f"Recovered: {time_str}\n"
            f"<{detail_url}|View on StatusRooster →>"
        )
        await send_slack(slack_webhook, message)

    # --- SMS ---
    sms_number = monitor.get("alert_sms", "")
    if sms_number:
        await send_sms(sms_number, f"UP: {name} ({url}) — back up after {duration_str}")
