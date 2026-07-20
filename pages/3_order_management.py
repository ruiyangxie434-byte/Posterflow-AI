"""Order list, detail editing, revisions, payments and design versions."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import streamlit as st
from sqlalchemy import delete, select, update

from database.db import get_session, init_db
from database.models import Client, DesignVersion, Order, Payment, Quote, Revision
from ui.components import page_header, section_title
from ui.theme import apply_theme
from utils import constants as app_constants


DESIGN_TYPES = list(
    getattr(
        app_constants,
        "DESIGN_TYPES",
        [
            "商业海报",
            "活动海报",
            "校园海报",
            "小红书封面",
            "朋友圈配图",
            "门店宣传",
            "大型背景墙",
            "PPT美化",
            "其他",
        ],
    )
)
ORDER_STATUSES = list(
    getattr(
        app_constants,
        "ORDER_STATUSES",
        [
            "待沟通",
            "待报价",
            "待付款",
            "设计中",
            "待客户确认",
            "修改中",
            "待尾款",
            "已完成",
            "已取消",
        ],
    )
)
CLIENT_SOURCES = list(
    getattr(
        app_constants,
        "CLIENT_SOURCES",
        ["小红书", "闲鱼", "微信", "朋友圈", "同学介绍", "老客户", "其他"],
    )
)
REVISION_TYPES = list(
    getattr(
        app_constants,
        "REVISION_TYPES",
        ["文字修改", "颜色修改", "排版修改", "图片替换", "尺寸调整", "整体方案重做", "其他"],
    )
)
PAYMENT_TYPES = list(
    getattr(
        app_constants,
        "PAYMENT_TYPES",
        ["定金", "尾款", "全款", "额外修改费", "退款"],
    )
)
PAYMENT_METHODS = list(
    getattr(
        app_constants,
        "PAYMENT_METHODS",
        ["微信", "支付宝", "银行卡", "现金", "其他"],
    )
)
REVISION_STATUSES = list(
    getattr(app_constants, "REVISION_STATUSES", ["待处理", "处理中", "已完成", "已取消"])
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = (PROJECT_ROOT / "uploads" / "design_versions").resolve()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_VERSION_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    sign = "-" if amount < 0 else ""
    return f"{sign}¥{abs(amount):,.2f}".replace(".00", "")


def _html(value: Any) -> str:
    """Escape database-backed text before inserting it into custom markup."""

    return escape(str(value or ""))


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            pass
    return date.today()


def _format_date(value: Any, fallback: str = "—") -> str:
    if value is None:
        return fallback
    try:
        return _as_date(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _load_orders() -> tuple[list[dict[str, Any]], str | None]:
    try:
        with get_session() as session:
            records = session.execute(
                select(Order, Client)
                .join(Client, Order.client_id == Client.id)
                .order_by(Order.created_at.desc(), Order.id.desc())
            ).all()
            return [
                {
                    "id": order.id,
                    "title": order.title,
                    "client_name": client.name,
                    "client_contact": client.contact or "",
                    "client_source": client.source or "其他",
                    "design_type": order.design_type,
                    "status": order.status,
                    "price": _safe_float(order.price),
                    "deadline_raw": order.deadline,
                    "deadline": _format_date(order.deadline),
                    "revision_used": int(order.revision_used or 0),
                    "revision_limit": int(order.revision_limit or 0),
                    "created_at": order.created_at,
                }
                for order, client in records
            ], None
    except Exception:
        return [], "订单数据暂时无法读取，请检查数据库连接后重试。"


def _load_detail(order_id: int) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with get_session() as session:
            record = session.execute(
                select(Order, Client)
                .join(Client, Order.client_id == Client.id)
                .where(Order.id == order_id)
            ).first()
            if record is None:
                return None, "该订单不存在或已被删除。"

            order, client = record
            quote = session.scalar(
                select(Quote)
                .where(Quote.order_id == order_id)
                .order_by(Quote.created_at.desc(), Quote.id.desc())
                .limit(1)
            )
            revision_records = session.scalars(
                select(Revision)
                .where(Revision.order_id == order_id)
                .order_by(Revision.created_at.desc(), Revision.id.desc())
            ).all()
            payment_records = session.scalars(
                select(Payment)
                .where(Payment.order_id == order_id)
                .order_by(Payment.payment_date.desc(), Payment.id.desc())
            ).all()
            version_records = session.scalars(
                select(DesignVersion)
                .where(DesignVersion.order_id == order_id)
                .order_by(DesignVersion.created_at.desc(), DesignVersion.id.desc())
            ).all()

            snapshot = {
                "order": {
                    "id": order.id,
                    "client_id": client.id,
                    "title": order.title,
                    "design_type": order.design_type,
                    "original_requirement": order.original_requirement or "",
                    "structured_requirement": order.structured_requirement or "",
                    "usage": order.usage or "",
                    "size": order.size or "",
                    "style": order.style or "",
                    "main_color": order.main_color or "",
                    "status": order.status or ORDER_STATUSES[0],
                    "price": _safe_float(order.price),
                    "deadline": order.deadline,
                    "urgent": bool(order.urgent),
                    "source_file_required": bool(order.source_file_required),
                    "print_required": bool(order.print_required),
                    "revision_limit": int(order.revision_limit or 0),
                    "revision_used": int(order.revision_used or 0),
                    "notes": order.notes or "",
                    "created_at": order.created_at,
                    "updated_at": order.updated_at,
                },
                "client": {
                    "id": client.id,
                    "name": client.name,
                    "contact": client.contact or "",
                    "source": client.source or "其他",
                    "notes": client.notes or "",
                },
                "quote": (
                    {
                        "base_price": _safe_float(quote.base_price),
                        "urgent_fee": _safe_float(quote.urgent_fee),
                        "source_file_fee": _safe_float(quote.source_file_fee),
                        "print_fee": _safe_float(quote.print_fee),
                        "complex_cutout_fee": _safe_float(quote.complex_cutout_fee),
                        "redesign_fee": _safe_float(quote.redesign_fee),
                        "oversized_fee": _safe_float(quote.oversized_fee),
                        "complexity_fee": _safe_float(quote.complexity_fee),
                        "manual_adjustment": _safe_float(quote.manual_adjustment),
                        "final_price": _safe_float(quote.final_price),
                    }
                    if quote
                    else None
                ),
                "revisions": [
                    {
                        "id": item.id,
                        "created_at": item.created_at,
                        "customer_feedback": item.customer_feedback,
                        "revision_type": item.revision_type,
                        "is_free": bool(item.is_free),
                        "extra_fee": _safe_float(item.extra_fee),
                        "status": item.status,
                        "notes": item.notes or "",
                    }
                    for item in revision_records
                ],
                "payments": [
                    {
                        "id": item.id,
                        "payment_type": item.payment_type,
                        "amount": _safe_float(item.amount),
                        "payment_method": item.payment_method or "其他",
                        "payment_date": item.payment_date,
                        "notes": item.notes or "",
                    }
                    for item in payment_records
                ],
                "versions": [
                    {
                        "id": item.id,
                        "version_number": item.version_number,
                        "file_name": item.file_name,
                        "file_path": item.file_path,
                        "description": item.description or "",
                        "is_final": bool(item.is_final),
                        "created_at": item.created_at,
                    }
                    for item in version_records
                ],
            }
            return snapshot, None
    except Exception:
        return None, "订单详情暂时无法读取，请稍后重试。"


def _payment_status(total_price: float, payments: list[dict[str, Any]]) -> tuple[str, float, float]:
    paid = sum(_safe_float(item["amount"]) for item in payments)
    outstanding = max(total_price - paid, 0.0)
    if not payments:
        status = "未付款"
    elif paid <= 0 and any(item["payment_type"] == "退款" for item in payments):
        status = "已退款"
    elif paid >= total_price and total_price > 0:
        status = "已付清"
    elif any(item["payment_type"] == "定金" for item in payments):
        status = "已付定金"
    else:
        status = "部分付款"
    return status, paid, outstanding


def _sync_payment_status(session: Any, order: Order) -> None:
    """Keep the denormalized order status aligned with payment records."""

    records = session.execute(
        select(Payment.payment_type, Payment.amount).where(Payment.order_id == order.id)
    ).all()
    payment_rows = [
        {"payment_type": payment_type, "amount": _safe_float(amount)}
        for payment_type, amount in records
    ]
    order.payment_status = _payment_status(_safe_float(order.price), payment_rows)[0]


def _filter_orders(
    orders: list[dict[str, Any]],
    *,
    keyword: str,
    status: str,
    design_type: str,
    use_date_filter: bool,
    start_date: date,
    end_date: date,
    due_soon_only: bool,
) -> list[dict[str, Any]]:
    keyword_normalized = keyword.strip().casefold()
    filtered: list[dict[str, Any]] = []
    today = date.today()
    due_limit = today + timedelta(days=3)
    for order in orders:
        deadline = _as_date(order["deadline_raw"])
        haystack = " ".join(
            [
                str(order["id"]),
                order["title"],
                order["client_name"],
                order["client_contact"],
            ]
        ).casefold()
        if keyword_normalized and keyword_normalized not in haystack:
            continue
        if status != "全部状态" and order["status"] != status:
            continue
        if design_type != "全部类型" and order["design_type"] != design_type:
            continue
        if use_date_filter and not (start_date <= deadline <= end_date):
            continue
        if due_soon_only:
            if order["status"] in {"已完成", "已取消"} or not (today <= deadline <= due_limit):
                continue
        filtered.append(order)
    return filtered


def _save_basic_info(order_id: int, values: dict[str, Any]) -> None:
    with get_session() as session:
        order = session.get(Order, order_id)
        if order is None:
            raise ValueError("order_not_found")
        client = session.get(Client, order.client_id)
        if client is None:
            raise ValueError("client_not_found")

        client.name = values["client_name"].strip()
        client.contact = values["client_contact"].strip()
        client.source = values["client_source"]
        order.title = values["title"].strip()
        order.design_type = values["design_type"]
        order.original_requirement = values["original_requirement"].strip()
        order.usage = values["usage"].strip()
        order.size = values["size"].strip()
        order.style = values["style"].strip()
        order.main_color = values["main_color"].strip()
        order.status = values["status"]
        order.price = values["price"]
        order.deadline = datetime.combine(values["deadline"], time.max)
        order.urgent = values["urgent"]
        order.source_file_required = values["source_file_required"]
        order.print_required = values["print_required"]
        order.revision_limit = values["revision_limit"]
        order.notes = values["notes"].strip()
        _sync_payment_status(session, order)


def _delete_order(order_id: int) -> None:
    with get_session() as session:
        # Delete dependent records explicitly so the page also works when a local
        # SQLite database was created without cascade constraints.
        session.execute(delete(DesignVersion).where(DesignVersion.order_id == order_id))
        session.execute(delete(Revision).where(Revision.order_id == order_id))
        session.execute(delete(Payment).where(Payment.order_id == order_id))
        session.execute(delete(Quote).where(Quote.order_id == order_id))
        order = session.get(Order, order_id)
        if order is not None:
            session.delete(order)


def _add_revision(
    order_id: int,
    *,
    feedback: str,
    revision_type: str,
    is_free: bool,
    extra_fee: float,
    status: str,
    notes: str,
    add_to_total: bool,
) -> None:
    with get_session() as session:
        order = session.get(Order, order_id)
        if order is None:
            raise ValueError("order_not_found")
        charged_fee = 0.0 if is_free else float(extra_fee)
        session.add(
            Revision(
                order_id=order_id,
                customer_feedback=feedback.strip(),
                revision_type=revision_type,
                is_free=is_free,
                extra_fee=charged_fee,
                status=status,
                notes=notes.strip(),
            )
        )
        order.revision_used = int(order.revision_used or 0) + 1
        if add_to_total and charged_fee > 0:
            order.price = _safe_float(order.price) + charged_fee
        _sync_payment_status(session, order)


def _add_payment(
    order_id: int,
    *,
    payment_type: str,
    amount: float,
    payment_method: str,
    payment_date: date,
    notes: str,
) -> None:
    signed_amount = -abs(amount) if payment_type == "退款" else abs(amount)
    with get_session() as session:
        order = session.get(Order, order_id)
        if order is None:
            raise ValueError("order_not_found")
        session.add(
            Payment(
                order_id=order_id,
                payment_type=payment_type,
                amount=signed_amount,
                payment_method=payment_method,
                payment_date=datetime.combine(payment_date, time.min),
                notes=notes.strip(),
            )
        )
        session.flush()
        _sync_payment_status(session, order)


def _safe_existing_upload(file_path: str) -> Path | None:
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        candidate.relative_to(UPLOAD_ROOT)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _save_version(
    order_id: int,
    *,
    version_number: str,
    uploaded_file: Any,
    description: str,
    is_final: bool,
) -> None:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in ALLOWED_VERSION_SUFFIXES:
        raise ValueError("invalid_file_type")
    payload = uploaded_file.getvalue()
    if not payload:
        raise ValueError("empty_file")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError("file_too_large")

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    safe_name = f"order-{order_id}-{uuid4().hex}{suffix}"
    destination = (UPLOAD_ROOT / safe_name).resolve()
    destination.relative_to(UPLOAD_ROOT)
    destination.write_bytes(payload)

    try:
        with get_session() as session:
            if session.get(Order, order_id) is None:
                raise ValueError("order_not_found")
            if is_final:
                session.execute(
                    update(DesignVersion)
                    .where(DesignVersion.order_id == order_id)
                    .values(is_final=False)
                )
            session.add(
                DesignVersion(
                    order_id=order_id,
                    version_number=version_number.strip(),
                    file_name=uploaded_file.name,
                    file_path=str(destination),
                    description=description.strip(),
                    is_final=is_final,
                )
            )
    except Exception:
        destination.unlink(missing_ok=True)
        raise


apply_theme()

try:
    init_db()
except Exception:
    st.error("数据库暂时无法连接，请检查数据库文件权限后重试。")
    st.stop()

st.markdown(
    """
    <style>
    .pf-order-title-line {display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;margin:.1rem 0 .25rem}
    .pf-order-title-line h2 {margin:0!important}
    .pf-status-chip {display:inline-flex;padding:.22rem .58rem;border-radius:999px;background:var(--pf-orange-soft);color:var(--pf-orange-dark);font-size:.78rem;font-weight:680}
    .pf-info-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem 1rem;margin:.4rem 0 1rem}
    .pf-info-item {padding:.72rem .82rem;background:#faf9f7;border:1px solid var(--pf-line);border-radius:10px}
    .pf-info-item span {display:block;color:var(--pf-muted);font-size:.76rem;margin-bottom:.25rem}
    .pf-info-item strong {color:var(--pf-text);font-weight:650;word-break:break-word}
    @media (max-width:700px){.pf-info-grid{grid-template-columns:1fr}}
    </style>
    """,
    unsafe_allow_html=True,
)

if message := st.session_state.pop("pf_order_management_success", None):
    st.success(message)

page_header("订单管理", "筛选订单、跟进状态，并集中记录修改、收款与交付版本。")

orders, orders_error = _load_orders()
if orders_error:
    st.error(orders_error)
    st.stop()

section_title("筛选订单")
filter_row_1 = st.columns([1.35, 1, 1, .8])
with filter_row_1[0]:
    keyword = st.text_input(
        "搜索",
        placeholder="客户、联系方式、订单名称或编号",
        label_visibility="collapsed",
    )
with filter_row_1[1]:
    status_filter = st.selectbox(
        "状态",
        ["全部状态", *ORDER_STATUSES],
        label_visibility="collapsed",
    )
with filter_row_1[2]:
    type_filter = st.selectbox(
        "设计类型",
        ["全部类型", *DESIGN_TYPES],
        label_visibility="collapsed",
    )
with filter_row_1[3]:
    due_soon_only = st.toggle("即将截止", help="仅显示未来 3 天内截止且尚未完成的订单。")

use_date_filter = st.checkbox("按截止日期筛选")
if use_date_filter:
    date_col_1, date_col_2, _ = st.columns([1, 1, 2])
    with date_col_1:
        start_date = st.date_input("开始日期", value=date.today() - timedelta(days=30))
    with date_col_2:
        end_date = st.date_input("结束日期", value=date.today() + timedelta(days=30))
else:
    start_date = date.today() - timedelta(days=3650)
    end_date = date.today() + timedelta(days=3650)

if start_date > end_date:
    st.warning("开始日期不能晚于结束日期。")
    filtered_orders: list[dict[str, Any]] = []
else:
    filtered_orders = _filter_orders(
        orders,
        keyword=keyword,
        status=status_filter,
        design_type=type_filter,
        use_date_filter=use_date_filter,
        start_date=start_date,
        end_date=end_date,
        due_soon_only=due_soon_only,
    )

metric_1, metric_2, metric_3, metric_4 = st.columns(4)
metric_1.metric("筛选结果", f"{len(filtered_orders)} 单")
metric_2.metric("订单金额", _money(sum(order["price"] for order in filtered_orders)))
metric_3.metric(
    "进行中",
    f'{sum(order["status"] not in {"已完成", "已取消"} for order in filtered_orders)} 单',
)
metric_4.metric(
    "3天内截止",
    f'{sum(date.today() <= _as_date(order["deadline_raw"]) <= date.today() + timedelta(days=3) and order["status"] not in {"已完成", "已取消"} for order in filtered_orders)} 单',
)

section_title("订单列表")
if not filtered_orders:
    st.info("当前筛选条件下没有订单。可以调整筛选条件，或先去新建一笔订单。")
    st.stop()

table_frame = pd.DataFrame(
    [
        {
            "订单号": f'#{order["id"]}',
            "订单名称": order["title"],
            "客户": order["client_name"],
            "类型": order["design_type"],
            "状态": order["status"],
            "截止日期": order["deadline"],
            "修改": f'{order["revision_used"]}/{order["revision_limit"]}',
            "金额": order["price"],
        }
        for order in filtered_orders
    ]
)
st.dataframe(
    table_frame,
    hide_index=True,
    width="stretch",
    column_config={
        "订单号": st.column_config.TextColumn(width="small"),
        "订单名称": st.column_config.TextColumn(width="large"),
        "金额": st.column_config.NumberColumn(format="¥ %.0f"),
    },
)

order_labels = {
    order["id"]: f'#{order["id"]} · {order["title"]} · {order["client_name"]}'
    for order in filtered_orders
}
selected_order_id = st.selectbox(
    "查看订单详情",
    list(order_labels),
    format_func=lambda order_id: order_labels[order_id],
)

detail, detail_error = _load_detail(int(selected_order_id))
if detail_error or detail is None:
    st.error(detail_error or "订单详情读取失败。")
    st.stop()

order = detail["order"]
client = detail["client"]
payment_status, paid_amount, outstanding_amount = _payment_status(order["price"], detail["payments"])

st.divider()
st.markdown(
    f'<div class="pf-order-title-line"><h2>{_html(order["title"])}</h2><span class="pf-status-chip">{_html(order["status"])}</span></div>',
    unsafe_allow_html=True,
)
st.caption(f'订单 #{order["id"]} · {client["name"]} · 截止 {_format_date(order["deadline"])}')

summary_1, summary_2, summary_3, summary_4 = st.columns(4)
summary_1.metric("订单总价", _money(order["price"]))
summary_2.metric("已收金额", _money(paid_amount))
summary_3.metric("待收金额", _money(outstanding_amount))
summary_4.metric("修改进度", f'{order["revision_used"]}/{order["revision_limit"]} 次')

overview_tab, revision_tab, payment_tab, version_tab = st.tabs(
    ["订单详情", "修改记录", "收款记录", "设计版本"]
)

with overview_tab:
    left_detail, right_detail = st.columns([1.15, 1], gap="large")
    with left_detail:
        section_title("需求与客户")
        st.markdown(
            f"""
            <div class="pf-info-grid">
                <div class="pf-info-item"><span>客户</span><strong>{_html(client["name"])}</strong></div>
                <div class="pf-info-item"><span>联系方式</span><strong>{_html(client["contact"] or "未填写")}</strong></div>
                <div class="pf-info-item"><span>设计类型</span><strong>{_html(order["design_type"])}</strong></div>
                <div class="pf-info-item"><span>使用场景</span><strong>{_html(order["usage"] or "未填写")}</strong></div>
                <div class="pf-info-item"><span>设计尺寸</span><strong>{_html(order["size"] or "未填写")}</strong></div>
                <div class="pf-info-item"><span>风格 / 主色</span><strong>{_html(order["style"] or "未填写")} / {_html(order["main_color"] or "未填写")}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("**客户原始需求**")
        st.info(order["original_requirement"] or "尚未填写客户需求。")
        if order["structured_requirement"]:
            st.markdown("**结构化需求**")
            st.write(order["structured_requirement"])
        if order["notes"]:
            st.markdown("**订单备注**")
            st.write(order["notes"])

    with right_detail:
        section_title("报价与交付")
        quote = detail["quote"]
        if quote:
            quote_frame = pd.DataFrame(
                [
                    ("基础价格", quote["base_price"]),
                    ("加急费", quote["urgent_fee"]),
                    ("源文件费", quote["source_file_fee"]),
                    ("印刷处理费", quote["print_fee"]),
                    ("复杂抠图", quote["complex_cutout_fee"]),
                    ("整体方案重做", quote["redesign_fee"]),
                    ("超大尺寸", quote["oversized_fee"]),
                    ("手动调整", quote["manual_adjustment"]),
                    ("参考总价", quote["final_price"]),
                ],
                columns=["费用项目", "金额"],
            )
            st.dataframe(
                quote_frame,
                hide_index=True,
                width="stretch",
                column_config={"金额": st.column_config.NumberColumn(format="¥ %.0f")},
            )
        else:
            st.info("该订单还没有报价记录。")
        st.caption(
            f'付款状态：{payment_status} · 源文件：{"需要" if order["source_file_required"] else "不需要"} · 印刷：{"需要" if order["print_required"] else "不需要"}'
        )

    st.divider()
    section_title("编辑订单")
    current_design_types = DESIGN_TYPES if order["design_type"] in DESIGN_TYPES else [order["design_type"], *DESIGN_TYPES]
    current_statuses = ORDER_STATUSES if order["status"] in ORDER_STATUSES else [order["status"], *ORDER_STATUSES]
    current_source_index = CLIENT_SOURCES.index(client["source"]) if client["source"] in CLIENT_SOURCES else 0
    with st.form(f"edit_order_{order['id']}"):
        edit_col_1, edit_col_2 = st.columns(2)
        with edit_col_1:
            edit_client_name = st.text_input("客户姓名 *", value=client["name"])
            edit_client_contact = st.text_input("联系方式", value=client["contact"])
            edit_client_source = st.selectbox("客户来源", CLIENT_SOURCES, index=current_source_index)
            edit_title = st.text_input("订单名称 *", value=order["title"])
            edit_design_type = st.selectbox(
                "设计类型",
                current_design_types,
                index=current_design_types.index(order["design_type"]),
            )
            edit_status = st.selectbox(
                "订单状态",
                current_statuses,
                index=current_statuses.index(order["status"]),
            )
        with edit_col_2:
            edit_usage = st.text_input("使用场景", value=order["usage"])
            edit_size = st.text_input("设计尺寸", value=order["size"])
            edit_style = st.text_input("风格", value=order["style"])
            edit_main_color = st.text_input("主色调", value=order["main_color"])
            edit_deadline = st.date_input("截止日期 *", value=_as_date(order["deadline"]))
            edit_price = st.number_input(
                "订单总价",
                min_value=0.0,
                max_value=10000000.0,
                value=float(order["price"]),
                step=10.0,
            )

        edit_original_requirement = st.text_area(
            "客户原始需求 *", value=order["original_requirement"], height=120
        )
        option_col_1, option_col_2, option_col_3, option_col_4 = st.columns(4)
        with option_col_1:
            edit_urgent = st.checkbox("加急订单", value=order["urgent"])
        with option_col_2:
            edit_source_file = st.checkbox("需要源文件", value=order["source_file_required"])
        with option_col_3:
            edit_print = st.checkbox("需要印刷处理", value=order["print_required"])
        with option_col_4:
            edit_revision_limit = st.number_input(
                "免费修改次数",
                min_value=0,
                max_value=20,
                value=int(order["revision_limit"]),
                step=1,
            )
        edit_notes = st.text_area("订单备注", value=order["notes"], height=86)
        save_basic = st.form_submit_button("保存订单修改", type="primary", width="stretch")

    if save_basic:
        basic_errors: list[str] = []
        if not edit_client_name.strip():
            basic_errors.append("客户姓名不能为空。")
        if not edit_title.strip():
            basic_errors.append("订单名称不能为空。")
        if not edit_original_requirement.strip():
            basic_errors.append("客户原始需求不能为空。")
        if basic_errors:
            st.error("\n\n".join(basic_errors))
        else:
            try:
                _save_basic_info(
                    int(order["id"]),
                    {
                        "client_name": edit_client_name,
                        "client_contact": edit_client_contact,
                        "client_source": edit_client_source,
                        "title": edit_title,
                        "design_type": edit_design_type,
                        "status": edit_status,
                        "usage": edit_usage,
                        "size": edit_size,
                        "style": edit_style,
                        "main_color": edit_main_color,
                        "deadline": edit_deadline,
                        "price": float(edit_price),
                        "urgent": edit_urgent,
                        "source_file_required": edit_source_file,
                        "print_required": edit_print,
                        "revision_limit": int(edit_revision_limit),
                        "original_requirement": edit_original_requirement,
                        "notes": edit_notes,
                    },
                )
            except Exception:
                st.error("订单修改保存失败，原数据没有改变，请稍后重试。")
            else:
                st.session_state["pf_order_management_success"] = "订单信息已更新。"
                st.rerun()

    with st.expander("删除订单"):
        st.warning("删除后订单、报价、修改与收款记录将无法恢复；已上传的本地文件会保留。")
        confirm_delete = st.checkbox(
            f'我确认删除“{order["title"]}”', key=f"confirm_delete_{order['id']}"
        )
        if st.button(
            "永久删除订单",
            type="secondary",
            disabled=not confirm_delete,
            key=f"delete_order_{order['id']}",
        ):
            try:
                _delete_order(int(order["id"]))
            except Exception:
                st.error("订单删除失败，数据没有改变，请稍后重试。")
            else:
                st.session_state["pf_order_management_success"] = "订单已删除。"
                st.rerun()

with revision_tab:
    free_limit = int(order["revision_limit"])
    used_count = int(order["revision_used"])
    exceeded_count = max(used_count - free_limit, 0)
    recommend_fee = exceeded_count * 10
    rev_metric_1, rev_metric_2, rev_metric_3, rev_metric_4 = st.columns(4)
    rev_metric_1.metric("免费修改次数", f"{free_limit} 次")
    rev_metric_2.metric("已使用", f"{used_count} 次")
    rev_metric_3.metric("超出次数", f"{exceeded_count} 次")
    rev_metric_4.metric("建议累计加收", _money(recommend_fee))

    section_title("记录客户修改")
    default_is_free = used_count < free_limit
    feedback = st.text_area(
        "客户原话 *",
        height=110,
        placeholder="完整记录客户提出的修改内容，方便后续核对范围。",
        key=f"revision_feedback_{order['id']}",
    )
    rev_col_1, rev_col_2, rev_col_3 = st.columns(3)
    with rev_col_1:
        revision_type = st.selectbox(
            "修改类型", REVISION_TYPES, key=f"revision_type_{order['id']}"
        )
    with rev_col_2:
        revision_status = st.selectbox(
            "处理状态", REVISION_STATUSES, key=f"revision_status_{order['id']}"
        )
    with rev_col_3:
        is_free = st.checkbox(
            "属于免费修改",
            value=default_is_free,
            key=f"revision_free_{order['id']}",
            help="系统按免费额度给出默认判断，你仍可按实际约定调整。",
        )

    if is_free:
        st.text_input("额外收费", value="¥0（免费修改）", disabled=True)
        extra_fee = 0.0
        add_to_total = False
    else:
        fee_col, add_col = st.columns(2)
        with fee_col:
            extra_fee = st.number_input(
                "额外收费",
                min_value=0.0,
                max_value=100000.0,
                value=10.0,
                step=10.0,
                key=f"revision_fee_{order['id']}",
            )
        with add_col:
            add_to_total = st.checkbox(
                "计入订单总价",
                value=True,
                key=f"revision_add_total_{order['id']}",
            )
    revision_notes = st.text_input(
        "备注", placeholder="处理说明（选填）", key=f"revision_notes_{order['id']}"
    )
    if st.button(
        "保存修改记录",
        type="primary",
        width="stretch",
        key=f"save_revision_{order['id']}",
    ):
        if not feedback.strip():
            st.error("请填写客户原话。")
        else:
            try:
                _add_revision(
                    int(order["id"]),
                    feedback=feedback,
                    revision_type=revision_type,
                    is_free=is_free,
                    extra_fee=float(extra_fee),
                    status=revision_status,
                    notes=revision_notes,
                    add_to_total=add_to_total,
                )
            except Exception:
                st.error("修改记录保存失败，请稍后重试。")
            else:
                st.session_state["pf_order_management_success"] = "修改记录已保存，次数统计已更新。"
                st.rerun()

    section_title("历史修改")
    if detail["revisions"]:
        revision_frame = pd.DataFrame(
            [
                {
                    "时间": _format_date(item["created_at"]),
                    "客户反馈": item["customer_feedback"],
                    "类型": item["revision_type"],
                    "额度": "免费" if item["is_free"] else "收费",
                    "费用": item["extra_fee"],
                    "状态": item["status"],
                    "备注": item["notes"],
                }
                for item in detail["revisions"]
            ]
        )
        st.dataframe(
            revision_frame,
            hide_index=True,
            width="stretch",
            column_config={"费用": st.column_config.NumberColumn(format="¥ %.0f")},
        )
    else:
        st.info("还没有修改记录。第一次反馈到来时，在上方完整记录即可。")

with payment_tab:
    pay_metric_1, pay_metric_2, pay_metric_3 = st.columns(3)
    pay_metric_1.metric("付款状态", payment_status)
    pay_metric_2.metric("已收金额", _money(paid_amount))
    pay_metric_3.metric("未收金额", _money(outstanding_amount))

    section_title("新增收款记录")
    pay_col_1, pay_col_2, pay_col_3 = st.columns(3)
    with pay_col_1:
        payment_type = st.selectbox(
            "款项类型", PAYMENT_TYPES, key=f"payment_type_{order['id']}"
        )
    with pay_col_2:
        default_payment = outstanding_amount if outstanding_amount > 0 else 0.0
        payment_amount = st.number_input(
            "金额",
            min_value=0.0,
            max_value=10000000.0,
            value=float(default_payment),
            step=10.0,
            key=f"payment_amount_{order['id']}",
            help="选择退款时，请填写正数，系统会自动记为负向金额。",
        )
    with pay_col_3:
        payment_method = st.selectbox(
            "支付方式", PAYMENT_METHODS, key=f"payment_method_{order['id']}"
        )
    pay_date_col, pay_note_col = st.columns(2)
    with pay_date_col:
        payment_date = st.date_input(
            "收款日期", value=date.today(), key=f"payment_date_{order['id']}"
        )
    with pay_note_col:
        payment_notes = st.text_input(
            "备注", placeholder="例如：微信转账（选填）", key=f"payment_notes_{order['id']}"
        )

    if st.button(
        "保存收款记录",
        type="primary",
        width="stretch",
        key=f"save_payment_{order['id']}",
    ):
        if payment_amount <= 0:
            st.error("收款或退款金额必须大于 0。")
        else:
            try:
                _add_payment(
                    int(order["id"]),
                    payment_type=payment_type,
                    amount=float(payment_amount),
                    payment_method=payment_method,
                    payment_date=payment_date,
                    notes=payment_notes,
                )
            except Exception:
                st.error("收款记录保存失败，请稍后重试。")
            else:
                st.session_state["pf_order_management_success"] = "收款记录已保存。"
                st.rerun()

    section_title("历史收款")
    if detail["payments"]:
        payment_frame = pd.DataFrame(
            [
                {
                    "日期": _format_date(item["payment_date"]),
                    "类型": item["payment_type"],
                    "金额": item["amount"],
                    "支付方式": item["payment_method"],
                    "备注": item["notes"],
                }
                for item in detail["payments"]
            ]
        )
        st.dataframe(
            payment_frame,
            hide_index=True,
            width="stretch",
            column_config={"金额": st.column_config.NumberColumn(format="¥ %.0f")},
        )
    else:
        st.info("还没有收款记录。收到定金或尾款后请及时登记。")

with version_tab:
    st.caption("仅支持 PNG、JPG、WEBP、PDF，单个文件不超过 20MB；本项目默认不交付 PSD / AI 源文件。")
    section_title("上传设计版本")
    version_col_1, version_col_2 = st.columns(2)
    with version_col_1:
        version_number = st.text_input(
            "版本编号 *",
            value=f'V{len(detail["versions"]) + 1}',
            key=f"version_number_{order['id']}",
        )
    with version_col_2:
        is_final_version = st.checkbox(
            "设为最终版本", key=f"version_final_{order['id']}"
        )
    version_file = st.file_uploader(
        "选择设计文件 *",
        type=["png", "jpg", "jpeg", "webp", "pdf"],
        key=f"version_file_{order['id']}",
    )
    version_description = st.text_input(
        "版本说明",
        placeholder="例如：V2 调整主色并替换人物图",
        key=f"version_description_{order['id']}",
    )
    if st.button(
        "保存设计版本",
        type="primary",
        width="stretch",
        key=f"save_version_{order['id']}",
    ):
        version_errors: list[str] = []
        if not version_number.strip():
            version_errors.append("请填写版本编号。")
        if version_file is None:
            version_errors.append("请选择要上传的文件。")
        elif version_file.size > MAX_UPLOAD_BYTES:
            version_errors.append("文件不能超过 20MB。")
        if version_errors:
            st.error("\n\n".join(version_errors))
        else:
            try:
                _save_version(
                    int(order["id"]),
                    version_number=version_number,
                    uploaded_file=version_file,
                    description=version_description,
                    is_final=is_final_version,
                )
            except ValueError as exc:
                message_by_error = {
                    "invalid_file_type": "文件格式不受支持，请上传 PNG、JPG、WEBP 或 PDF。",
                    "empty_file": "上传的文件为空，请重新选择。",
                    "file_too_large": "文件超过 20MB，请压缩后重试。",
                }
                st.error(message_by_error.get(str(exc), "设计版本保存失败，请重试。"))
            except Exception:
                st.error("设计版本保存失败，文件与数据库记录均未保留，请稍后重试。")
            else:
                st.session_state["pf_order_management_success"] = "设计版本已上传。"
                st.rerun()

    section_title("版本历史")
    if not detail["versions"]:
        st.info("还没有上传设计版本。初稿完成后可在这里保存 V1。")
    else:
        for version in detail["versions"]:
            with st.container(border=True):
                title_col, action_col = st.columns([3, 1])
                with title_col:
                    final_label = " · 最终版本" if version["is_final"] else ""
                    st.markdown(f'**{version["version_number"]}{final_label}**')
                    st.caption(
                        f'{version["file_name"]} · {_format_date(version["created_at"])}'
                    )
                    if version["description"]:
                        st.write(version["description"])
                with action_col:
                    safe_path = _safe_existing_upload(version["file_path"])
                    if safe_path is None:
                        st.warning("文件不存在")
                    else:
                        st.download_button(
                            "下载文件",
                            data=safe_path.read_bytes(),
                            file_name=version["file_name"],
                            width="stretch",
                            key=f'download_version_{version["id"]}',
                        )
