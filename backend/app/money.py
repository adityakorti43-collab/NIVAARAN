"""Decimal-safe money helpers. Final currency values never use binary floating point."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

PAISA = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value) -> Decimal:
    """Parse a money value (str/int/Decimal; floats are rejected) and quantize to paise."""
    if isinstance(value, float):
        raise TypeError("Monetary values must not be floats; pass str, int or Decimal")
    if isinstance(value, str):
        value = value.replace(",", "").replace("INR", "").replace("Rs.", "").replace("₹", "").strip()
    try:
        return Decimal(value).quantize(PAISA, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid monetary amount: {value!r}") from exc


def q(value: Decimal) -> Decimal:
    return value.quantize(PAISA, rounding=ROUND_HALF_UP)


def fmt(value: Decimal) -> str:
    return f"{q(value):,.2f}"


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` across `weights` proportionally in whole paise using the largest-remainder method.

    The parts always sum exactly to `total`, so claim-level amounts reconcile with item-level amounts.
    """
    total = q(total)
    n = len(weights)
    if n == 0:
        return []
    wsum = sum(weights, ZERO)
    if wsum <= 0 or total == 0:
        return [ZERO] * n
    total_paise = int(total / PAISA)
    raw = [Decimal(total_paise) * w / wsum for w in weights]
    floors = [int(r) for r in raw]
    remainder = total_paise - sum(floors)
    # Deterministic tie-break: larger fractional part first, then lower index.
    order = sorted(range(n), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in order[:remainder]:
        floors[i] += 1
    return [Decimal(p) * PAISA for p in floors]
