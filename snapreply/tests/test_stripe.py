"""
Stripe service tests — tests config helper, mocks Stripe calls.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import settings


def test_get_stripe_price_id_starter_monthly():
    pid = settings.get_stripe_price_id("starter", False)
    assert pid == settings.STRIPE_PRICE_ID_STARTER


def test_get_stripe_price_id_growth_monthly():
    pid = settings.get_stripe_price_id("growth", False)
    assert pid == settings.STRIPE_PRICE_ID_GROWTH


def test_get_stripe_price_id_pro_monthly():
    pid = settings.get_stripe_price_id("pro", False)
    assert pid == settings.STRIPE_PRICE_ID_PRO


def test_get_stripe_price_id_starter_annual():
    pid = settings.get_stripe_price_id("starter", True)
    assert pid == settings.STRIPE_PRICE_ID_STARTER_ANNUAL


def test_get_stripe_price_id_growth_annual():
    pid = settings.get_stripe_price_id("growth", True)
    assert pid == settings.STRIPE_PRICE_ID_GROWTH_ANNUAL


def test_get_stripe_price_id_pro_annual():
    pid = settings.get_stripe_price_id("pro", True)
    assert pid == settings.STRIPE_PRICE_ID_PRO_ANNUAL
