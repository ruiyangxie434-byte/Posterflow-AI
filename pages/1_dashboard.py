"""PosterFlow AI 经营数据看板。"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import select

from database.db import get_session, init_db
from database.models import Client, Order, Payment, Revision
from ui.components import page_header, section_title
from ui.theme import apply_theme


COMPLETED_STATUSES = {"已完成"}
CANCELLED_STATUSES = {"已取消"}
ACCENT_COLORS = ["#F97316", "#FB923C", "#FDBA74", "#FED7AA", "#9A3412", "#C2410C"]


@contextmanager
def _session_scope() -> Iterator[Any]:
    """兼容返回 Session 或上下文管理器的 get_session。"""
    resource = get_session()
    if hasattr(resource, "__enter__"):
        with resource as session:
            yield session
        return

    try:
        yield resource
    finally:
        close = getattr(resource, "close", None)
        if callable(close):
            close()


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _signed_payment_amount(payment_type: Any, amount: Any) -> float:
    value = abs(_as_float(amount))
    return -value if str(payment_type or "").strip() == "退款" else value


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.to_pydatetime()


def _load_dashboard_data() -> tuple[list[dict[str, Any]], ...]:
    """一次读取页面所需数据，避免图表渲染期间反复访问数据库。"""
    with _session_scope() as session:
        clients = session.execute(select(Client)).scalars().all()
        orders = session.execute(select(Order)).scalars().all()
        payments = session.execute(select(Payment)).scalars().all()
        revisions = session.execute(select(Revision)).scalars().all()

        client_rows = [
            {
                "id": client.id,
                "name": getattr(client, "name", "未命名客户"),
                "source": getattr(client, "source", None) or "其他",
            }
            for client in clients
        ]
        order_rows = [
            {
                "id": order.id,
                "client_id": getattr(order, "client_id", None),
                "title": getattr(order, "title", "未命名订单"),
                "design_type": getattr(order, "design_type", None) or "其他",
                "status": getattr(order, "status", None) or "待沟通",
                "price": _as_float(getattr(order, "price", 0)),
                "deadline": _as_datetime(getattr(order, "deadline", None)),
                "revision_used": int(getattr(order, "revision_used", 0) or 0),
                "created_at": _as_datetime(getattr(order, "created_at", None)),
            }
            for order in orders
        ]
        payment_rows = [
            {
                "order_id": getattr(payment, "order_id", None),
                "amount": _signed_payment_amount(
                    getattr(payment, "payment_type", None), getattr(payment, "amount", 0)
                ),
                "payment_method": getattr(payment, "payment_method", None) or "未记录",
                "payment_date": _as_datetime(
                    getattr(payment, "payment_date", None)
                    or getattr(payment, "created_at", None)
                ),
            }
            for payment in payments
        ]
        revision_rows = [
            {
                "order_id": getattr(revision, "order_id", None),
                "extra_fee": _as_float(getattr(revision, "extra_fee", 0)),
            }
            for revision in revisions
        ]

    return client_rows, order_rows, payment_rows, revision_rows


def _metric(label: str, value: str, helper: str) -> None:
    with st.container(border=True):
        st.caption(label)
        st.markdown(f"### {value}")
        st.caption(helper)


def _style_chart(figure: Any) -> Any:
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#4A3528", "family": "Inter, PingFang SC, Microsoft YaHei"},
        margin={"l": 12, "r": 12, "t": 28, "b": 12},
        legend_title_text="",
        hoverlabel={"bgcolor": "#FFF7ED", "font_color": "#4A3528"},
    )
    figure.update_xaxes(showgrid=False, zeroline=False)
    figure.update_yaxes(gridcolor="#F3E8DE", zeroline=False)
    return figure


def _empty_chart(message: str) -> None:
    with st.container(border=True):
        st.markdown("#### 还没有足够的数据")
        st.caption(message)


apply_theme()
init_db()

page_header("数据看板", "订单、回款和交付风险集中在一张轻量工作台里。")

try:
    clients, orders, payments, revisions = _load_dashboard_data()
except Exception as exc:  # 数据库异常必须转为友好提示
    st.error("数据暂时无法读取，请稍后刷新页面。")
    st.caption(f"错误摘要：{exc}")
    st.stop()

today = date.today()
month_start = today.replace(day=1)
total_orders = len(orders)
month_orders = sum(
    1
    for order in orders
    if order["created_at"] and order["created_at"].date() >= month_start
)
active_order_ids = {
    order["id"] for order in orders if order["status"] not in CANCELLED_STATUSES
}
active_payments = [
    payment for payment in payments if payment["order_id"] in active_order_ids
]
total_income = sum(payment["amount"] for payment in active_payments)
month_income = sum(
    payment["amount"]
    for payment in active_payments
    if payment["payment_date"] and payment["payment_date"].date() >= month_start
)
pending_orders = sum(
    1 for order in orders if order["status"] not in COMPLETED_STATUSES | CANCELLED_STATUSES
)
completed_orders = sum(1 for order in orders if order["status"] in COMPLETED_STATUSES)
revision_counter = Counter(row["order_id"] for row in revisions)
revision_fees: dict[int, float] = Counter()
for row in revisions:
    revision_fees[row["order_id"]] += row["extra_fee"]
active_orders = [order for order in orders if order["status"] not in CANCELLED_STATUSES]
average_order_value = (
    sum(order["price"] + revision_fees[order["id"]] for order in active_orders)
    / len(active_orders)
    if active_orders
    else 0
)
revision_totals = [
    max(order["revision_used"], revision_counter.get(order["id"], 0))
    for order in active_orders
]
average_revisions = sum(revision_totals) / len(active_orders) if active_orders else 0

section_title("经营概览")
metric_columns = st.columns(4)
with metric_columns[0]:
    _metric("总订单", f"{total_orders} 单", f"本月新增 {month_orders} 单")
with metric_columns[1]:
    _metric("累计实收", f"¥{total_income:,.2f}", f"本月实收 ¥{month_income:,.2f}")
with metric_columns[2]:
    _metric("待处理", f"{pending_orders} 单", f"已完成 {completed_orders} 单")
with metric_columns[3]:
    _metric("平均客单价", f"¥{average_order_value:,.2f}", f"平均修改 {average_revisions:.1f} 次")

st.write("")
section_title("经营趋势")
trend_col, status_col = st.columns([1.6, 1])

with trend_col:
    st.markdown("#### 每月收入")
    if active_payments and any(row["payment_date"] for row in active_payments):
        revenue_df = pd.DataFrame(
            [
                {
                    "月份": row["payment_date"].strftime("%Y-%m"),
                    "实收金额": row["amount"],
                }
                for row in active_payments
                if row["payment_date"]
            ]
        )
        revenue_df = revenue_df.groupby("月份", as_index=False)["实收金额"].sum()
        revenue_df = revenue_df.sort_values("月份")
        revenue_fig = px.line(
            revenue_df,
            x="月份",
            y="实收金额",
            markers=True,
            color_discrete_sequence=["#F97316"],
        )
        revenue_fig.update_traces(line={"width": 3}, marker={"size": 8})
        st.plotly_chart(_style_chart(revenue_fig), width="stretch", config={"displayModeBar": False})
    else:
        _empty_chart("添加一笔收款后，这里会显示月度趋势。")

with status_col:
    st.markdown("#### 订单状态")
    if orders:
        status_df = pd.DataFrame(orders).groupby("status", as_index=False).size()
        status_df.columns = ["状态", "订单数"]
        status_fig = px.pie(
            status_df,
            names="状态",
            values="订单数",
            hole=0.66,
            color_discrete_sequence=ACCENT_COLORS,
        )
        status_fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(_style_chart(status_fig), width="stretch", config={"displayModeBar": False})
    else:
        _empty_chart("创建订单后，这里会展示订单所处阶段。")

type_col, source_col = st.columns(2)
with type_col:
    st.markdown("#### 设计类型")
    if orders:
        type_df = pd.DataFrame(orders).groupby("design_type", as_index=False).size()
        type_df.columns = ["设计类型", "订单数"]
        type_df = type_df.sort_values("订单数", ascending=True)
        type_fig = px.bar(
            type_df,
            x="订单数",
            y="设计类型",
            orientation="h",
            color_discrete_sequence=["#FB923C"],
        )
        type_fig.update_traces(marker_cornerradius=6)
        st.plotly_chart(_style_chart(type_fig), width="stretch", config={"displayModeBar": False})
    else:
        _empty_chart("不同业务类型的订单数量会显示在这里。")

with source_col:
    st.markdown("#### 客户来源")
    if clients:
        source_df = pd.DataFrame(clients).groupby("source", as_index=False).size()
        source_df.columns = ["来源", "客户数"]
        source_fig = px.pie(
            source_df,
            names="来源",
            values="客户数",
            hole=0.5,
            color_discrete_sequence=ACCENT_COLORS,
        )
        source_fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(_style_chart(source_fig), width="stretch", config={"displayModeBar": False})
    else:
        _empty_chart("添加客户后，这里会展示获客渠道。")

st.write("")
section_title("近期交付")
upcoming = [
    order
    for order in orders
    if order["deadline"]
    and order["status"] not in COMPLETED_STATUSES | CANCELLED_STATUSES
    and (order["deadline"].date() - today).days <= 7
]
upcoming.sort(key=lambda item: item["deadline"])

if not upcoming:
    with st.container(border=True):
        st.markdown("#### 未来 7 天没有临期订单")
        st.caption("可以从容安排下一份设计。")
else:
    source_by_client = {client["id"]: client["source"] for client in clients}
    upcoming_rows = []
    for order in upcoming:
        days_left = (order["deadline"].date() - today).days
        if days_left < 0:
            timing = f"已逾期 {abs(days_left)} 天"
        elif days_left == 0:
            timing = "今天截止"
        else:
            timing = f"剩余 {days_left} 天"
        upcoming_rows.append(
            {
                "订单": order["title"],
                "状态": order["status"],
                "截止日期": order["deadline"].strftime("%Y-%m-%d"),
                "时间提醒": timing,
                "客户来源": source_by_client.get(order["client_id"], "其他"),
            }
        )
    st.dataframe(pd.DataFrame(upcoming_rows), width="stretch", hide_index=True)
