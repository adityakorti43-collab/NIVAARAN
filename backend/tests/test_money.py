"""Direct unit tests for app/money.py (Decimal-safe money helpers)."""
from decimal import Decimal as D

import pytest

from app.money import allocate, fmt, money

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

def test_allocate_splits_exactly_and_sums_to_total():
    parts = allocate(D("100.00"), [D("1"), D("1"), D("1")])
    # 100.00 can't split evenly 3 ways, so the leftover paisa goes to the first item
    assert parts == [D("33.34"), D("33.33"), D("33.33")]
    # The key money rule: the parts always add up to the exact total, no paisa lost
    assert sum(parts) == D("100.00")

def test_allocate_handles_empty_and_zero_inputs():
    # No weights means nothing to split
    assert allocate(D("100.00"), []) == []
    # Weights that are all zero can't share anything, so everyone gets 0.00
    assert allocate(D("100.00"), [D("0"), D("0")]) == [D("0.00"), D("0.00")]
    # A zero total splits into zeros
    assert allocate(D("0"), [D("1")]) == [D("0.00")]

def test_allocate_respects_unequal_weights():
    parts = allocate(D("10.00"), [D("1"), D("2"), D("3")])
    # Exact shares are 1.666.., 3.333.., 5.00: the first item has the biggest
    # fractional part, so it gets the leftover paisa
    assert parts == [D("1.67"), D("3.33"), D("5.00")]
    # Parts must always reconcile to the exact total
    assert sum(parts) == D("10.00")


def test_allocate_tie_goes_to_lower_index():
    # One paisa shared by two equal weights: the tie-break gives it to the first item
    assert allocate(D("0.01"), [D("1"), D("1")]) == [D("0.01"), D("0.00")]


@pytest.mark.parametrize(
    "total, weights",
    [
        ("100.00", ["1", "1", "1"]),
        ("0.02", ["1", "1", "1"]),
        ("999.99", ["3", "7", "11", "13"]),
        ("1.00", ["0.1", "0.2", "0.7"]),
    ],
)
def test_allocate_always_sums_to_total(total, weights):
    # Whatever the inputs, no paisa may be created or lost
    parts = allocate(D(total), [D(w) for w in weights])
    assert sum(parts) == D(total)
    # Every part is a whole number of paise (exactly 2 decimal places)
    assert all(p == p.quantize(D("0.01")) for p in parts)


def test_money_accepts_int_and_decimal():
    assert money(5) == D("5.00")
    assert money(D("2.345")) == D("2.35")  # rounds half up


def test_money_rejects_floats():
    # Floats are banned on purpose: binary floating point can't represent money exactly
    with pytest.raises(TypeError):
        money(0.1)


def test_fmt_uses_two_decimals_and_thousands_separator():
    assert fmt(D("1234567.8")) == "1,234,567.80"