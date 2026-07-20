"""Centralized and testable quotation rules."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite
from typing import Any

from utils.constants import BASE_PRICES, QUOTE_FEES


MONEY_PLACES = Decimal("0.01")


def _money(value: Any, field_name: str) -> Decimal:
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是有效数字") from exc
    if not amount.is_finite():
        raise ValueError(f"{field_name} 必须是有限数字")
    return amount.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def _number(value: Decimal) -> int | float:
    """Return UI-friendly JSON-serializable money values."""

    if value == value.to_integral_value():
        return int(value)
    return float(value)


def get_base_price(design_type: str, custom_base_price: int | float | Decimal | None = None) -> int | float:
    """Resolve a design type to its base price.

    Unknown types intentionally use the ``其他`` price so a new form option does
    not break quotation.  A manual base price is allowed but cannot be negative.
    """

    if custom_base_price is not None:
        price = _money(custom_base_price, "基础价格")
        if price < 0:
            raise ValueError("基础价格不能小于 0")
        return _number(price)
    return BASE_PRICES.get((design_type or "").strip(), BASE_PRICES["其他"])


def calculate_quote(
    design_type: str,
    *,
    urgent: bool = False,
    hours_until_deadline: float | int | None = None,
    urgent_hours: float | int | None = None,
    source_file_required: bool = False,
    print_required: bool = False,
    complex_cutout: bool = False,
    overall_redesign: bool = False,
    redesign: bool | None = None,
    oversized: bool = False,
    manual_adjustment: int | float | Decimal = 0,
    base_price: int | float | Decimal | None = None,
) -> dict[str, int | float]:
    """Calculate a complete, itemized reference quote.

    ``urgent_hours`` is accepted as a friendly alias for
    ``hours_until_deadline``.  When a deadline distance of 24 hours or less is
    supplied, it is treated as urgent even if the separate checkbox was not
    toggled.  If only ``urgent=True`` is known, the conservative 24-hour fee is
    used.  The final price is always floored at zero after manual adjustment.
    """

    resolved_base = _money(get_base_price(design_type, base_price), "基础价格")

    hours = hours_until_deadline if hours_until_deadline is not None else urgent_hours
    urgent_fee = Decimal("0")
    if hours is not None:
        try:
            hours_value = float(hours)
        except (TypeError, ValueError) as exc:
            raise ValueError("加急小时数必须是有效数字") from exc
        if not isfinite(hours_value):
            raise ValueError("加急小时数必须是有限数字")
        if hours_value < 0:
            hours_value = 0
        if hours_value <= 12:
            urgent_fee = Decimal(str(QUOTE_FEES["urgent_12h"]))
        elif hours_value <= 24:
            urgent_fee = Decimal(str(QUOTE_FEES["urgent_24h"]))
    elif urgent:
        urgent_fee = Decimal(str(QUOTE_FEES["urgent_24h"]))

    source_fee = Decimal(str(QUOTE_FEES["source_file"] if source_file_required else 0))
    print_fee = Decimal(str(QUOTE_FEES["print_processing"] if print_required else 0))
    cutout_fee = Decimal(str(QUOTE_FEES["complex_cutout"] if complex_cutout else 0))
    do_redesign = overall_redesign if redesign is None else bool(redesign)
    redesign_fee = Decimal(str(QUOTE_FEES["overall_redesign"] if do_redesign else 0))
    oversized_fee = Decimal(str(QUOTE_FEES["oversized"] if oversized else 0))
    complexity_fee = cutout_fee + redesign_fee + oversized_fee
    adjustment = _money(manual_adjustment, "手动调整金额")

    raw_total = resolved_base + urgent_fee + source_fee + print_fee + complexity_fee + adjustment
    final_price = max(Decimal("0"), raw_total).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)

    return {
        "base_price": _number(resolved_base),
        "urgent_fee": _number(urgent_fee),
        "source_file_fee": _number(source_fee),
        "print_fee": _number(print_fee),
        "complex_cutout_fee": _number(cutout_fee),
        "redesign_fee": _number(redesign_fee),
        "oversized_fee": _number(oversized_fee),
        "complexity_fee": _number(complexity_fee),
        "manual_adjustment": _number(adjustment),
        "final_price": _number(final_price),
    }
