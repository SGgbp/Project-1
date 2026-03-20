"""
Stripe webhook handler.
SECURITY: Always validates stripe-signature header before processing.
"""
import logging
import stripe

from fastapi import APIRouter, HTTPException, Request, Response
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/webhooks/stripe/events")
async def handle_stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.SignatureVerificationError:
        logger.error("Invalid Stripe signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(status_code=400, detail="Bad request")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Stripe event received: {event_type}")

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)

    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data)

    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data)

    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data)

    elif event_type == "invoice.payment_succeeded":
        logger.info(f"Payment succeeded for customer: {data.get('customer')}")

    return Response(status_code=200)


async def _handle_checkout_completed(session: dict):
    from database.connection import AsyncSessionLocal
    from database.models import Business, Subscription
    from services.whatsapp_service import send_whatsapp_message
    from services.email_service import send_welcome_email
    from sqlalchemy import select

    metadata = session.get("metadata", {})
    business_id = metadata.get("business_id")
    plan = metadata.get("plan", "starter")
    stripe_customer_id = session.get("customer")
    stripe_subscription_id = session.get("subscription")

    if not business_id:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business).where(Business.id == business_id))
        business = result.scalar_one_or_none()
        if not business:
            return

        # Update subscription
        sub_result = await db.execute(
            select(Subscription).where(Subscription.business_id == business.id)
        )
        subscription = sub_result.scalar_one_or_none()
        if subscription:
            subscription.status = "active"
            subscription.plan = plan
            subscription.stripe_customer_id = stripe_customer_id
            subscription.stripe_subscription_id = stripe_subscription_id
        else:
            subscription = Subscription(
                business_id=business.id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                status="active",
                plan=plan,
            )
            db.add(subscription)

        business.plan = plan
        await db.commit()

        # Welcome messages
        plan_label = plan.title()
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"🎉 *Welcome to SnapReply {plan_label}!*\n\n"
            f"Your subscription is now active. Your AI assistant is working 24/7.\n\n"
            f"Text *HELP* to see all commands. Let's get those enquiries converting! 🚀"
        )
        await send_welcome_email(business.email, business.owner_name, plan)
        logger.info(f"Checkout completed for business {str(business.id)[-8:]}, plan={plan}")


async def _handle_subscription_updated(subscription: dict):
    from database.connection import AsyncSessionLocal
    from database.models import Business, Subscription
    from services.whatsapp_service import send_whatsapp_message
    from sqlalchemy import select

    stripe_customer_id = subscription.get("customer")
    new_plan = _extract_plan_from_subscription(subscription)
    status = subscription.get("status", "active")

    async with AsyncSessionLocal() as db:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id)
        )
        sub = sub_result.scalar_one_or_none()
        if not sub:
            return

        old_plan = sub.plan
        sub.plan = new_plan
        sub.status = status

        biz_result = await db.execute(select(Business).where(Business.id == sub.business_id))
        business = biz_result.scalar_one_or_none()
        if business:
            business.plan = new_plan
        await db.commit()

        if business and old_plan != new_plan:
            await send_whatsapp_message(
                business.owner_whatsapp,
                f"✅ You've upgraded to SnapReply *{new_plan.title()}*! "
                f"Your new features are now active 🚀"
            )


async def _handle_subscription_deleted(subscription: dict):
    from database.connection import AsyncSessionLocal
    from database.models import Business, Subscription
    from services.whatsapp_service import send_whatsapp_message
    from sqlalchemy import select
    from datetime import datetime, timezone

    stripe_customer_id = subscription.get("customer")

    async with AsyncSessionLocal() as db:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id)
        )
        sub = sub_result.scalar_one_or_none()
        if not sub:
            return

        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(timezone.utc)

        biz_result = await db.execute(select(Business).where(Business.id == sub.business_id))
        business = biz_result.scalar_one_or_none()
        if business:
            business.active = False
        await db.commit()

        if business:
            await send_whatsapp_message(
                business.owner_whatsapp,
                f"😢 Your SnapReply subscription has been cancelled, {business.first_name}.\n\n"
                f"Your data is retained for 90 days. We'd love to have you back — "
                f"visit {settings.BASE_URL} anytime to resubscribe."
            )


async def _handle_payment_failed(invoice: dict):
    from database.connection import AsyncSessionLocal
    from database.models import Business, Subscription
    from services.notification_service import notify_owner_payment_failed
    from sqlalchemy import select

    stripe_customer_id = invoice.get("customer")

    async with AsyncSessionLocal() as db:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id)
        )
        sub = sub_result.scalar_one_or_none()
        if not sub:
            return

        sub.status = "past_due"
        await db.commit()

        biz_result = await db.execute(select(Business).where(Business.id == sub.business_id))
        business = biz_result.scalar_one_or_none()
        if business:
            await notify_owner_payment_failed(business)


def _extract_plan_from_subscription(subscription: dict) -> str:
    """Extract plan name from Stripe subscription items."""
    try:
        items = subscription.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id", "")
            if "growth" in price_id.lower():
                return "growth"
            if "pro" in price_id.lower():
                return "pro"
    except Exception:
        pass
    return "starter"
