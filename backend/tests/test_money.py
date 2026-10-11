"""Direct unit tests for app/money.py (Decimal-safe money helpers)."""
from decimal import Decimal as D

import pytest

from app.money import allocate, money


def test_money_strips_currency_markers():
    # Prefixes and commas are removed before parsing
    assert money("Rs. 1,250.5") == D("1250.50")
    assert money("INR 99") == D("99.00")
    assert money("₹10") == D("10.00")


def test_money_rounds_half_up():
    assert money("0.005") == D("0.01")


def test_money_rejects_garbage():
    # pytest.raises checks that the expected error is thrown
    with pytest.raises(ValueError):
        money("abc")
    with pytest.raises(ValueError):
        money("")
