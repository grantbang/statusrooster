"""
Billing routes — Stripe Checkout, webhooks, and Customer Portal.
"""

import stripe
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from app.config import settings
from app.database import get_db
from app.models.user import get_user_by_id, update_user
from app.services.auth import decode_access_token

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(tags=["billing"], include_in_schema=False)


# ---------------------------------------------------------------------------
# Helper: get current user from cookie
# ---------------------------------------------------------------------------

def _get_user_from_cookie(request: Request) -> dict | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        db = get_db()
        return get_user_by_id(db, payload["sub"])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Checkout: redirect user to Stripe Checkout
# ---------------------------------------------------------------------------

@router.post("/api/billing/checkout")
async def create_checkout_session(request: Request):
    user = _get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = get_db()

    # Get or create Stripe customer
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            metadata={"user_id": user["id"]},
        )
        customer_id = customer.id
        update_user(db, user["id"], {"stripe_customer_id": customer_id})

    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{
            "price": settings.STRIPE_PRICE_ID_PRO,
            "quantity": 1,
        }],
        success_url=f"{settings.APP_URL}/dashboard?msg=Welcome+to+Pro!&msg_type=success",
        cancel_url=f"{settings.APP_URL}/dashboard?msg=Upgrade+cancelled&msg_type=error",
        metadata={"user_id": user["id"]},
    )

    return RedirectResponse(url=session.url, status_code=303)


# ---------------------------------------------------------------------------
# Webhook: handle Stripe events
# ---------------------------------------------------------------------------

@router.post("/api/billing/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    db = get_db()

    # ---- checkout.session.completed → upgrade to Pro ----
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        customer_id = session.get("customer")

        if user_id:
            update_user(db, user_id, {
                "plan": "pro",
                "stripe_customer_id": customer_id,
            })
            print(f"✅ User {user_id} upgraded to Pro")

        # Log revenue event
        _log_revenue_event(db, event["type"], user_id=user_id,
                           customer_id=customer_id, amount=900)

    # ---- customer.subscription.deleted → downgrade to Free ----
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")

        # Find user by stripe_customer_id
        user_id = None
        users = (
            db.collection("users")
            .where("stripe_customer_id", "==", customer_id)
            .limit(1)
            .get()
        )
        for doc in users:
            update_user(db, doc.id, {"plan": "free"})
            user_id = doc.id
            print(f"⬇️ User {doc.id} downgraded to Free")

        _log_revenue_event(db, event["type"], user_id=user_id,
                           customer_id=customer_id, amount=0)

    # ---- invoice.payment_succeeded → track actual payment ----
    elif event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        amount = invoice.get("amount_paid", 0)  # in cents
        _log_revenue_event(db, event["type"], customer_id=customer_id,
                           amount=amount)

    return JSONResponse({"status": "ok"})


def _log_revenue_event(db, event_type: str, user_id: str | None = None,
                       customer_id: str | None = None, amount: int = 0):
    """Log a Stripe event to admin_revenue collection for tracking."""
    from datetime import datetime, timezone
    try:
        db.collection("admin_revenue").add({
            "event_type": event_type,
            "user_id": user_id,
            "customer_id": customer_id,
            "amount": amount,
            "currency": "usd",
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception as e:
        print(f"[billing] Failed to log revenue event: {e}")


# ---------------------------------------------------------------------------
# Customer Portal: manage subscription
# ---------------------------------------------------------------------------

@router.post("/api/billing/portal")
async def customer_portal(request: Request):
    user = _get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        return RedirectResponse(
            url="/dashboard?msg=No+active+subscription&msg_type=error",
            status_code=302,
        )

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.APP_URL}/dashboard",
    )

    return RedirectResponse(url=session.url, status_code=303)
