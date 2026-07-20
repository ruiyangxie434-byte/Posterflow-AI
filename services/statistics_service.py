"""Dashboard, finance, and customer statistics queries."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.models import Client, Order, Payment
from utils.constants import ORDER_STATUSES


ZERO = Decimal("0.00")


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Decimal) -> float:
    return round(float(value), 2)


def _calendar_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def _signed_payment(payment: Payment) -> Decimal:
    amount = abs(_decimal(payment.amount))
    return -amount if payment.payment_type == "退款" else amount


def _order_due(order: Order) -> Decimal:
    revision_fees = sum((_decimal(item.extra_fee) for item in order.revisions), ZERO)
    return max(ZERO, _decimal(order.price) + revision_fees)


def _load_orders(session: Session) -> list[Order]:
    statement = select(Order).options(
        selectinload(Order.client), selectinload(Order.payments), selectinload(Order.revisions)
    )
    return list(session.scalars(statement).all())


def get_upcoming_orders(session: Session, *, days: int = 7, today: date | None = None) -> list[Order]:
    base = today or date.today()
    end = base + timedelta(days=days)
    return [
        order
        for order in _load_orders(session)
        if order.status not in {"已完成", "已取消"}
        and (deadline := _calendar_date(order.deadline)) is not None
        and base <= deadline <= end
    ]


def get_monthly_income_trend(
    session: Session, *, months: int = 12, today: date | None = None
) -> list[dict[str, Any]]:
    if months <= 0:
        return []
    base = today or date.today()
    month_keys: list[str] = []
    year, month = base.year, base.month
    for offset in range(months - 1, -1, -1):
        absolute = year * 12 + month - 1 - offset
        month_keys.append(f"{absolute // 12:04d}-{absolute % 12 + 1:02d}")
    totals: dict[str, Decimal] = {key: ZERO for key in month_keys}
    for payment in session.scalars(select(Payment)).all():
        paid_on = _calendar_date(payment.payment_date)
        if paid_on is None:
            continue
        key = f"{paid_on.year:04d}-{paid_on.month:02d}"
        if key in totals:
            totals[key] += _signed_payment(payment)
    return [{"month": key, "income": _money(totals[key])} for key in month_keys]


def get_financial_statistics(session: Session, *, today: date | None = None) -> dict[str, Any]:
    orders = _load_orders(session)
    active_orders = [order for order in orders if order.status != "已取消"]
    net_income = sum((_signed_payment(item) for order in active_orders for item in order.payments), ZERO)
    total_contract_value = sum((_order_due(order) for order in active_orders), ZERO)
    outstanding = ZERO
    for order in active_orders:
        paid = sum((_signed_payment(item) for item in order.payments), ZERO)
        outstanding += max(ZERO, _order_due(order) - paid)

    base = today or date.today()
    month_income = sum(
        (
            _signed_payment(payment)
            for order in active_orders
            for payment in order.payments
            if (paid_on := _calendar_date(payment.payment_date)) is not None
            and paid_on.year == base.year
            and paid_on.month == base.month
        ),
        ZERO,
    )
    by_design_type: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_client_source: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for order in active_orders:
        received = sum((_signed_payment(item) for item in order.payments), ZERO)
        by_design_type[order.design_type or "其他"] += received
        by_client_source[(order.client.source if order.client else "其他") or "其他"] += received

    average = total_contract_value / len(active_orders) if active_orders else ZERO
    return {
        "total_contract_value": _money(total_contract_value),
        "total_income": _money(net_income),
        "month_income": _money(month_income),
        "outstanding_amount": _money(outstanding),
        "average_order_value": _money(average),
        "revenue_by_design_type": [
            {"design_type": key, "income": _money(value)}
            for key, value in sorted(by_design_type.items(), key=lambda item: (-item[1], item[0]))
        ],
        "revenue_by_client_source": [
            {"source": key, "income": _money(value)}
            for key, value in sorted(by_client_source.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def get_dashboard_statistics(session: Session, *, today: date | None = None) -> dict[str, Any]:
    orders = _load_orders(session)
    base = today or date.today()
    active_orders = [order for order in orders if order.status != "已取消"]
    month_orders = [
        order
        for order in orders
        if (created := _calendar_date(order.created_at)) is not None
        and created.year == base.year
        and created.month == base.month
    ]
    completed_orders = [order for order in orders if order.status == "已完成"]
    pending_orders = [order for order in orders if order.status not in {"已完成", "已取消"}]
    revision_total = sum((len(order.revisions) for order in active_orders), 0)
    finance = get_financial_statistics(session, today=base)

    type_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    status_counts: dict[str, int] = {status: 0 for status in ORDER_STATUSES}
    for order in orders:
        type_counts[order.design_type or "其他"] += 1
        source_counts[(order.client.source if order.client else "其他") or "其他"] += 1
        status_counts[order.status or "待沟通"] = status_counts.get(order.status or "待沟通", 0) + 1

    return {
        "total_orders": len(orders),
        "month_orders": len(month_orders),
        "total_income": finance["total_income"],
        "month_income": finance["month_income"],
        "pending_orders": len(pending_orders),
        "completed_orders": len(completed_orders),
        "average_order_value": finance["average_order_value"],
        "average_revisions": round(revision_total / len(active_orders), 2) if active_orders else 0.0,
        "outstanding_amount": finance["outstanding_amount"],
        "monthly_income_trend": get_monthly_income_trend(session, today=base),
        "orders_by_design_type": [
            {"design_type": key, "count": value} for key, value in sorted(type_counts.items())
        ],
        "orders_by_client_source": [
            {"source": key, "count": value} for key, value in sorted(source_counts.items())
        ],
        "orders_by_status": [
            {"status": key, "count": value} for key, value in status_counts.items() if value
        ],
    }


def get_customer_statistics(session: Session, client_id: int) -> dict[str, Any]:
    client = session.scalar(
        select(Client)
        .where(Client.id == client_id)
        .options(selectinload(Client.orders).selectinload(Order.payments), selectinload(Client.orders).selectinload(Order.revisions))
    )
    if client is None:
        raise ValueError("客户不存在")
    # A customer's history includes cancelled work; spending still reflects only
    # actual payment records (refund records are subtracted).
    historical_orders = list(client.orders)
    total_spent = sum(
        (_signed_payment(item) for order in historical_orders for item in order.payments), ZERO
    )
    revision_count = sum((len(order.revisions) for order in historical_orders), 0)
    average_revisions = revision_count / len(historical_orders) if historical_orders else 0.0
    latest = max((_calendar_date(order.created_at) for order in historical_orders), default=None)
    exceeded_orders = sum(
        (1 for order in historical_orders if len(order.revisions) > order.revision_limit), 0
    )
    return {
        "client_id": client.id,
        "name": client.name,
        "contact": client.contact,
        "source": client.source,
        "order_count": len(historical_orders),
        "total_spent": _money(total_spent),
        "average_revisions": round(average_revisions, 2),
        "high_revision_client": average_revisions >= 2 or exceeded_orders >= 2,
        "last_cooperation_date": latest.isoformat() if latest else None,
    }


def get_clients_overview(session: Session) -> list[dict[str, Any]]:
    client_ids = session.scalars(select(Client.id).order_by(Client.created_at.desc())).all()
    return [get_customer_statistics(session, client_id) for client_id in client_ids]
