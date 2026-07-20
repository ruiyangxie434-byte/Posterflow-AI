"""订单收款记录与收入分析页面。"""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, time
from typing import Any, Iterator

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import select

from database.db import get_session, init_db
from database.models import Client, Order, Payment, Revision
from ui.components import page_header, section_title
from ui.theme import apply_theme
from utils import constants


PAYMENT_TYPES = list(
    getattr(constants, "PAYMENT_TYPES", ["定金", "尾款", "全款", "修改费", "退款"])
)
PAYMENT_METHODS = list(
    getattr(constants, "PAYMENT_METHODS", ["微信", "支付宝", "银行卡", "现金", "其他"])
)
ACCENT_COLORS = ["#F97316", "#FB923C", "#FDBA74", "#FED7AA", "#9A3412", "#C2410C"]


@contextmanager
def _session_scope() -> Iterator[Any]:
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
        return datetime.combine(value, time.min)
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.to_pydatetime()


def _load_finance_data() -> tuple[list[dict[str, Any]], ...]:
    with _session_scope() as session:
        clients = session.execute(select(Client)).scalars().all()
        orders = session.execute(select(Order).order_by(Order.id.desc())).scalars().all()
        payments = session.execute(select(Payment).order_by(Payment.id.desc())).scalars().all()
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
                "created_at": _as_datetime(getattr(order, "created_at", None)),
            }
            for order in orders
        ]
        payment_rows = [
            {
                "id": payment.id,
                "order_id": getattr(payment, "order_id", None),
                "payment_type": getattr(payment, "payment_type", None) or "其他收款",
                "amount": _signed_payment_amount(
                    getattr(payment, "payment_type", None), getattr(payment, "amount", 0)
                ),
                "payment_method": getattr(payment, "payment_method", None) or "未记录",
                "payment_date": _as_datetime(
                    getattr(payment, "payment_date", None)
                    or getattr(payment, "created_at", None)
                ),
                "notes": getattr(payment, "notes", None) or "",
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


def _save_payment(
    order_id: int,
    payment_type: str,
    amount: float,
    payment_method: str,
    payment_date: date,
    notes: str,
) -> None:
    if amount <= 0:
        raise ValueError("收款金额必须大于 0。")
    with _session_scope() as session:
        order_exists = session.get(Order, order_id)
        if order_exists is None:
            raise ValueError("所选订单不存在，请刷新页面后重试。")
        payment = Payment(
            order_id=order_id,
            payment_type=payment_type,
            amount=round(amount, 2),
            payment_method=payment_method,
            payment_date=datetime.combine(payment_date, time.min),
            notes=notes.strip(),
        )
        session.add(payment)
        session.flush()

        net_paid = sum(
            _signed_payment_amount(item.payment_type, item.amount)
            for item in order_exists.payments
        )
        total_due = _as_float(order_exists.price) + sum(
            _as_float(item.extra_fee) for item in order_exists.revisions
        )
        if payment_type == "退款" and net_paid <= 0:
            order_exists.payment_status = "已退款"
        elif total_due > 0 and net_paid >= total_due:
            order_exists.payment_status = "已付清"
        elif net_paid > 0 and any(item.payment_type == "定金" for item in order_exists.payments):
            order_exists.payment_status = "已付定金"
        elif net_paid > 0:
            order_exists.payment_status = "部分付款"
        else:
            order_exists.payment_status = "未付款"
        session.commit()


def _metric(label: str, value: str, helper: str = "") -> None:
    with st.container(border=True):
        st.caption(label)
        st.markdown(f"### {value}")
        if helper:
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
        st.markdown("#### 还没有收款数据")
        st.caption(message)


apply_theme()
init_db()
page_header("财务管理", "记录定金与尾款，随时看清实收、待收和收入结构。")

if st.session_state.pop("payment_saved", False):
    st.success("收款记录已保存，财务数据已更新。")

try:
    clients, orders, payments, revisions = _load_finance_data()
except Exception as exc:
    st.error("财务数据暂时无法读取，请稍后刷新页面。")
    st.caption(f"错误摘要：{exc}")
    st.stop()

client_by_id = {row["id"]: row for row in clients}
order_by_id = {row["id"]: row for row in orders}
paid_by_order: dict[int, float] = defaultdict(float)
payment_types_by_order: dict[int, set[str]] = defaultdict(set)
for payment in payments:
    paid_by_order[payment["order_id"]] += payment["amount"]
    payment_types_by_order[payment["order_id"]].add(payment["payment_type"])
revision_fees_by_order: dict[int, float] = defaultdict(float)
for revision in revisions:
    revision_fees_by_order[revision["order_id"]] += revision["extra_fee"]

today = date.today()
month_start = today.replace(day=1)
active_orders = [order for order in orders if order["status"] != "已取消"]
active_order_ids = {order["id"] for order in active_orders}
active_payments = [row for row in payments if row["order_id"] in active_order_ids]
total_income = sum(row["amount"] for row in active_payments)
month_income = sum(
    row["amount"]
    for row in active_payments
    if row["payment_date"] and row["payment_date"].date() >= month_start
)
due_by_order = {
    order["id"]: order["price"] + revision_fees_by_order[order["id"]]
    for order in active_orders
}
receivable = sum(
    max(due_by_order[order["id"]] - paid_by_order[order["id"]], 0)
    for order in active_orders
)
average_order_value = (
    sum(due_by_order[order["id"]] for order in active_orders) / len(active_orders)
    if active_orders
    else 0
)

section_title("资金概览")
metric_columns = st.columns(4)
with metric_columns[0]:
    _metric("累计实收", f"¥{total_income:,.2f}")
with metric_columns[1]:
    _metric("本月实收", f"¥{month_income:,.2f}")
with metric_columns[2]:
    _metric("待收金额", f"¥{receivable:,.2f}", "已排除取消订单")
with metric_columns[3]:
    _metric("平均客单价", f"¥{average_order_value:,.2f}")

overview_tab, payment_tab = st.tabs(["收入分析", "记一笔收款"])

with payment_tab:
    section_title("新增收款记录")
    if not orders:
        with st.container(border=True):
            st.markdown("#### 暂无可关联订单")
            st.caption("请先创建订单并填写报价，再记录定金或尾款。")
    else:
        selectable_orders = [order for order in orders if order["status"] != "已取消"] or orders
        with st.form("add_payment_form", clear_on_submit=True):
            selected_order_id = st.selectbox(
                "关联订单 *",
                options=[order["id"] for order in selectable_orders],
                format_func=lambda order_id: (
                    f"#{order_id} · {order_by_id[order_id]['title']} · "
                    f"{client_by_id.get(order_by_id[order_id]['client_id'], {}).get('name', '未关联客户')}"
                ),
            )
            selected_order = order_by_id[selected_order_id]
            already_paid = paid_by_order[selected_order_id]
            total_due = selected_order["price"] + revision_fees_by_order[selected_order_id]
            remaining = max(total_due - already_paid, 0)
            st.caption(
                f"应收 ¥{total_due:,.2f} · 已收 ¥{already_paid:,.2f} · 待收 ¥{remaining:,.2f}"
            )

            first_col, second_col = st.columns(2)
            with first_col:
                payment_type = st.selectbox("收款类型", PAYMENT_TYPES)
                amount = st.number_input(
                    "收款金额（元） *",
                    min_value=0.0,
                    max_value=1_000_000.0,
                    value=float(remaining) if 0 < remaining <= 1_000_000 else 0.0,
                    step=10.0,
                )
            with second_col:
                payment_method = st.selectbox("收款方式", PAYMENT_METHODS)
                received_date = st.date_input("收款日期", value=today, max_value=today)
            payment_notes = st.text_area(
                "备注", max_chars=500, placeholder="例如：微信已确认到账，尾款交付前结清。"
            )
            payment_submitted = st.form_submit_button(
                "保存收款", type="primary", width="stretch"
            )

        if payment_submitted:
            try:
                _save_payment(
                    selected_order_id,
                    payment_type,
                    amount,
                    payment_method,
                    received_date,
                    payment_notes,
                )
            except ValueError as exc:
                st.warning(str(exc))
            except Exception as exc:
                st.error("收款暂时无法保存，请稍后重试。")
                st.caption(f"错误摘要：{exc}")
            else:
                st.session_state["payment_saved"] = True
                st.rerun()

with overview_tab:
    st.write("")
    section_title("收入趋势与结构")
    trend_col, status_col = st.columns([1.55, 1])
    with trend_col:
        st.markdown("#### 每月实收")
        dated_payments = [row for row in active_payments if row["payment_date"]]
        if dated_payments:
            month_df = pd.DataFrame(
                [
                    {
                        "月份": row["payment_date"].strftime("%Y-%m"),
                        "实收金额": row["amount"],
                    }
                    for row in dated_payments
                ]
            )
            month_df = month_df.groupby("月份", as_index=False)["实收金额"].sum().sort_values("月份")
            month_fig = px.line(
                month_df,
                x="月份",
                y="实收金额",
                markers=True,
                color_discrete_sequence=["#F97316"],
            )
            month_fig.update_traces(line={"width": 3}, marker={"size": 8})
            st.plotly_chart(_style_chart(month_fig), width="stretch", config={"displayModeBar": False})
        else:
            _empty_chart("保存第一笔收款后，这里会展示月度收入。")

    with status_col:
        st.markdown("#### 付款状态")
        if active_orders:
            status_rows = []
            for order in active_orders:
                paid = paid_by_order[order["id"]]
                if due_by_order[order["id"]] > 0 and paid >= due_by_order[order["id"]]:
                    payment_status = "已付清"
                elif paid > 0 and "定金" in payment_types_by_order[order["id"]]:
                    payment_status = "已付定金"
                elif paid > 0:
                    payment_status = "部分付款"
                else:
                    payment_status = "未付款"
                status_rows.append({"支付状态": payment_status, "订单数": 1})
            status_df = pd.DataFrame(status_rows).groupby("支付状态", as_index=False)["订单数"].sum()
            status_fig = px.pie(
                status_df,
                names="支付状态",
                values="订单数",
                hole=0.62,
                color_discrete_sequence=ACCENT_COLORS,
            )
            status_fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(_style_chart(status_fig), width="stretch", config={"displayModeBar": False})
        else:
            _empty_chart("订单创建后会自动计算付款状态。")

    type_col, source_col = st.columns(2)
    income_rows = []
    for payment in active_payments:
        order = order_by_id.get(payment["order_id"])
        if not order:
            continue
        client = client_by_id.get(order["client_id"], {})
        income_rows.append(
            {
                "设计类型": order["design_type"],
                "客户来源": client.get("source", "其他"),
                "实收金额": payment["amount"],
            }
        )

    with type_col:
        st.markdown("#### 按设计类型")
        if income_rows:
            type_df = pd.DataFrame(income_rows).groupby("设计类型", as_index=False)["实收金额"].sum()
            type_df = type_df.sort_values("实收金额", ascending=True)
            type_fig = px.bar(
                type_df,
                x="实收金额",
                y="设计类型",
                orientation="h",
                color_discrete_sequence=["#FB923C"],
            )
            st.plotly_chart(_style_chart(type_fig), width="stretch", config={"displayModeBar": False})
        else:
            _empty_chart("收款会按订单类型归类。")

    with source_col:
        st.markdown("#### 按客户来源")
        if income_rows:
            source_df = pd.DataFrame(income_rows).groupby("客户来源", as_index=False)["实收金额"].sum()
            source_fig = px.pie(
                source_df,
                names="客户来源",
                values="实收金额",
                hole=0.5,
                color_discrete_sequence=ACCENT_COLORS,
            )
            source_fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(_style_chart(source_fig), width="stretch", config={"displayModeBar": False})
        else:
            _empty_chart("收款会按客户获客渠道归类。")

    st.write("")
    section_title("收款记录")
    if not payments:
        with st.container(border=True):
            st.markdown("#### 还没有收款记录")
            st.caption("切换到“记一笔收款”，录入定金、尾款或额外修改费。")
    else:
        payment_table = []
        for payment in payments:
            order = order_by_id.get(payment["order_id"], {})
            client = client_by_id.get(order.get("client_id"), {})
            payment_table.append(
                {
                    "日期": payment["payment_date"].strftime("%Y-%m-%d") if payment["payment_date"] else "—",
                    "订单": order.get("title", "已删除订单"),
                    "客户": client.get("name", "—"),
                    "类型": payment["payment_type"],
                    "金额": payment["amount"],
                    "方式": payment["payment_method"],
                    "备注": payment["notes"] or "—",
                }
            )
        st.dataframe(
            pd.DataFrame(payment_table),
            width="stretch",
            hide_index=True,
            column_config={"金额": st.column_config.NumberColumn(format="¥%.2f")},
        )
