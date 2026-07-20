"""客户创建、画像与历史合作页面。"""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

import pandas as pd
import streamlit as st
from sqlalchemy import select

from database.db import get_session, init_db
from database.models import Client, Order, Payment, Revision
from ui.components import page_header, section_title
from ui.theme import apply_theme
from utils import constants


DEFAULT_CLIENT_SOURCES = ["小红书", "闲鱼", "微信", "朋友圈", "同学介绍", "老客户", "其他"]
CLIENT_SOURCES = list(getattr(constants, "CLIENT_SOURCES", DEFAULT_CLIENT_SOURCES))
HIGH_FREQUENCY_THRESHOLD = float(
    getattr(constants, "HIGH_FREQUENCY_REVISION_THRESHOLD", 2.0)
)


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
        return datetime.combine(value, datetime.min.time())
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.to_pydatetime()


def _load_customer_data() -> tuple[list[dict[str, Any]], ...]:
    with _session_scope() as session:
        clients = session.execute(select(Client).order_by(Client.id.desc())).scalars().all()
        orders = session.execute(select(Order).order_by(Order.id.desc())).scalars().all()
        payments = session.execute(select(Payment)).scalars().all()
        revisions = session.execute(select(Revision)).scalars().all()

        client_rows = [
            {
                "id": client.id,
                "name": getattr(client, "name", "未命名客户"),
                "contact": getattr(client, "contact", None) or "—",
                "source": getattr(client, "source", None) or "其他",
                "notes": getattr(client, "notes", None) or "",
                "created_at": _as_datetime(getattr(client, "created_at", None)),
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
                "updated_at": _as_datetime(getattr(order, "updated_at", None)),
            }
            for order in orders
        ]
        payment_rows = [
            {
                "order_id": getattr(payment, "order_id", None),
                "amount": _signed_payment_amount(
                    getattr(payment, "payment_type", None), getattr(payment, "amount", 0)
                ),
            }
            for payment in payments
        ]
        revision_rows = [
            {"order_id": getattr(revision, "order_id", None)} for revision in revisions
        ]
    return client_rows, order_rows, payment_rows, revision_rows


def _metric(label: str, value: str, helper: str = "") -> None:
    with st.container(border=True):
        st.caption(label)
        st.markdown(f"### {value}")
        if helper:
            st.caption(helper)


def _create_client(name: str, contact: str, source: str, notes: str) -> None:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("客户姓名不能为空。")
    with _session_scope() as session:
        client = Client(
            name=clean_name,
            contact=contact.strip(),
            source=source,
            notes=notes.strip(),
        )
        session.add(client)
        session.commit()


apply_theme()
init_db()
page_header("客户管理", "沉淀每次合作，用订单和修改数据识别更值得长期经营的客户。")

list_tab, create_tab = st.tabs(["客户列表", "新增客户"])

with create_tab:
    section_title("建立客户档案")
    st.caption("先保存客户，再创建订单；客户来源会自动进入经营分析。")
    with st.form("create_client_form", clear_on_submit=True):
        first_col, second_col = st.columns(2)
        with first_col:
            client_name = st.text_input("客户姓名 *", max_chars=80, placeholder="例如：林同学")
            client_source = st.selectbox("客户来源", CLIENT_SOURCES)
        with second_col:
            client_contact = st.text_input(
                "联系方式", max_chars=120, placeholder="微信号、手机号或平台昵称"
            )
            client_notes = st.text_area(
                "备注", max_chars=500, placeholder="偏好、沟通习惯、开票要求等"
            )
        submitted = st.form_submit_button("保存客户", type="primary", width="stretch")

    if submitted:
        try:
            _create_client(client_name, client_contact, client_source, client_notes)
        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error("客户暂时无法保存，请稍后重试。")
            st.caption(f"错误摘要：{exc}")
        else:
            st.success("客户档案已创建，可以继续新建订单。")

with list_tab:
    try:
        clients, orders, payments, revisions = _load_customer_data()
    except Exception as exc:
        st.error("客户数据暂时无法读取，请稍后刷新页面。")
        st.caption(f"错误摘要：{exc}")
        st.stop()

    paid_by_order: dict[int, float] = defaultdict(float)
    for payment in payments:
        paid_by_order[payment["order_id"]] += payment["amount"]
    revision_count_by_order = Counter(row["order_id"] for row in revisions)

    client_summary: list[dict[str, Any]] = []
    for client in clients:
        client_orders = [
            order
            for order in orders
            if order["client_id"] == client["id"] and order["status"] != "已取消"
        ]
        received = sum(paid_by_order[order["id"]] for order in client_orders)
        revision_total = sum(
            max(order["revision_used"], revision_count_by_order.get(order["id"], 0))
            for order in client_orders
        )
        average_revision = revision_total / len(client_orders) if client_orders else 0
        cooperation_dates = [
            order["updated_at"] or order["created_at"]
            for order in client_orders
            if order["updated_at"] or order["created_at"]
        ]
        last_cooperation = max(cooperation_dates) if cooperation_dates else None
        client_summary.append(
            {
                **client,
                "order_count": len(client_orders),
                "received": received,
                "average_revision": average_revision,
                "high_frequency": bool(client_orders and average_revision >= HIGH_FREQUENCY_THRESHOLD),
                "last_cooperation": last_cooperation,
            }
        )

    section_title("客户概览")
    summary_columns = st.columns(4)
    repeat_clients = sum(1 for row in client_summary if row["order_count"] >= 2)
    high_frequency_clients = sum(1 for row in client_summary if row["high_frequency"])
    total_received = sum(row["received"] for row in client_summary)
    with summary_columns[0]:
        _metric("客户总数", f"{len(client_summary)} 位")
    with summary_columns[1]:
        _metric("复购客户", f"{repeat_clients} 位", "历史订单 ≥ 2")
    with summary_columns[2]:
        _metric("客户累计实收", f"¥{total_received:,.2f}")
    with summary_columns[3]:
        _metric("高频修改客户", f"{high_frequency_clients} 位", f"平均修改 ≥ {HIGH_FREQUENCY_THRESHOLD:g} 次")

    filter_col, source_col = st.columns([1.5, 1])
    with filter_col:
        search_keyword = st.text_input(
            "搜索客户", placeholder="输入姓名或联系方式", label_visibility="collapsed"
        ).strip().lower()
    with source_col:
        source_filter = st.selectbox(
            "来源筛选", ["全部来源", *CLIENT_SOURCES], label_visibility="collapsed"
        )

    filtered_clients = [
        row
        for row in client_summary
        if (
            not search_keyword
            or search_keyword in row["name"].lower()
            or search_keyword in row["contact"].lower()
        )
        and (source_filter == "全部来源" or row["source"] == source_filter)
    ]

    if not filtered_clients:
        with st.container(border=True):
            st.markdown("#### 没有匹配的客户")
            st.caption("调整搜索条件，或切换到“新增客户”建立第一份档案。")
    else:
        table_rows = [
            {
                "客户": row["name"],
                "联系方式": row["contact"],
                "来源": row["source"],
                "历史订单": row["order_count"],
                "累计实收": row["received"],
                "平均修改": round(row["average_revision"], 1),
                "标签": "高频修改" if row["high_frequency"] else "正常",
                "最近合作": row["last_cooperation"].strftime("%Y-%m-%d") if row["last_cooperation"] else "—",
            }
            for row in filtered_clients
        ]
        st.dataframe(
            pd.DataFrame(table_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "累计实收": st.column_config.NumberColumn(format="¥%.2f"),
                "平均修改": st.column_config.NumberColumn(format="%.1f 次"),
            },
        )

        st.write("")
        section_title("客户详情")
        selected_client_id = st.selectbox(
            "选择客户",
            options=[row["id"] for row in filtered_clients],
            format_func=lambda client_id: next(
                f"{row['name']} · {row['contact']}" for row in filtered_clients if row["id"] == client_id
            ),
        )
        selected = next(row for row in client_summary if row["id"] == selected_client_id)
        selected_orders = [order for order in orders if order["client_id"] == selected_client_id]

        detail_metric_cols = st.columns(4)
        with detail_metric_cols[0]:
            _metric("历史订单", f"{selected['order_count']} 单")
        with detail_metric_cols[1]:
            _metric("累计实收", f"¥{selected['received']:,.2f}")
        with detail_metric_cols[2]:
            _metric("平均修改", f"{selected['average_revision']:.1f} 次")
        with detail_metric_cols[3]:
            tag = "需要预留沟通成本" if selected["high_frequency"] else "修改频率正常"
            _metric("客户标签", "高频修改" if selected["high_frequency"] else "正常", tag)

        info_col, note_col = st.columns(2)
        with info_col:
            with st.container(border=True):
                st.markdown("#### 联系信息")
                st.markdown(f"**联系方式：** {selected['contact']}")
                st.markdown(f"**客户来源：** {selected['source']}")
                created_label = selected["created_at"].strftime("%Y-%m-%d") if selected["created_at"] else "—"
                st.markdown(f"**建档时间：** {created_label}")
        with note_col:
            with st.container(border=True):
                st.markdown("#### 客户备注")
                st.write(selected["notes"] or "暂未记录客户偏好或沟通备注。")

        st.markdown("#### 历史订单")
        if not selected_orders:
            st.caption("该客户还没有订单。")
        else:
            history_rows = []
            for order in selected_orders:
                revisions_used = max(
                    order["revision_used"], revision_count_by_order.get(order["id"], 0)
                )
                history_rows.append(
                    {
                        "订单": order["title"],
                        "类型": order["design_type"],
                        "状态": order["status"],
                        "报价": order["price"],
                        "已收": paid_by_order[order["id"]],
                        "修改次数": revisions_used,
                        "截止日期": order["deadline"].strftime("%Y-%m-%d") if order["deadline"] else "—",
                    }
                )
            st.dataframe(
                pd.DataFrame(history_rows),
                width="stretch",
                hide_index=True,
                column_config={
                    "报价": st.column_config.NumberColumn(format="¥%.2f"),
                    "已收": st.column_config.NumberColumn(format="¥%.2f"),
                },
            )
