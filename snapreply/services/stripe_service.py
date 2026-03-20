"""Stripe subscription management service."""
import logging
import stripe
from config import settings

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_checkout_session(business_id: str, plan: str, annual: bool = False) -> str:
    """Create a Stripe checkout session. Returns the checkout URL."""
    price_id = settings.get_stripe_price_id(plan, annual)

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        subscription_data={"trial_period_days": 7},
        metadata={"business_id": str(business_id), "plan": plan},
        success_url=settings.BASE_URL + "/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=settings.BASE_URL + "/pricing",
    )
    logger.info(f"Checkout session created for business {str(business_id)[-8:]}, plan={plan}")
    return session.url


async def create_billing_portal_session(stripe_customer_id: str) -> str:
    """Return a Stripe billing portal URL for self-serve plan management."""
    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=settings.BASE_URL + "/dashboard",
    )
    return session.url


async def get_subscription_status(stripe_customer_id: str) -> dict:
    """Return subscription status details for a customer."""
    try:
        subscriptions = stripe.Subscription.list(customer=stripe_customer_id, limit=1)
        if not subscriptions.data:
            return {"status": "none"}

        sub = subscriptions.data[0]
        return {
            "status": sub.status,
            "plan": sub.metadata.get("plan", "starter"),
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }
    except Exception as e:
        logger.error(f"Failed to get subscription status: {e}")
        return {"status": "unknown"}


async def cancel_subscription(stripe_subscription_id: str, immediately: bool = False) -> bool:
    """Cancel a Stripe subscription immediately or at period end."""
    try:
        if immediately:
            stripe.Subscription.cancel(stripe_subscription_id)
        else:
            stripe.Subscription.modify(
                stripe_subscription_id,
                cancel_at_period_end=True,
            )
        logger.info(f"Subscription {stripe_subscription_id[-8:]} cancelled (immediate={immediately})")
        return True
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        return False
