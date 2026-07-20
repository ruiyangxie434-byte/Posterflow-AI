"""Create orders with a live quotation preview."""

from __future__ import annotations

from datetime import date, datetime, time
from html import escape
from typing import Any

import streamlit as st
from sqlalchemy import and_, select

from database.db import get_session, init_db
from database.models import Client, Order, Quote
from services.quote_service import calculate_quote
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
CLIENT_SOURCES = list(
    getattr(
        app_constants,
        "CLIENT_SOURCES",
        ["小红书", "闲鱼", "微信", "朋友圈", "同学介绍", "老客户", "其他"],
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
USAGE_SCENARIOS = list(
    getattr(
        app_constants,
        "USAGE_SCENARIOS",
        ["朋友圈宣传", "小红书发布", "线上活动", "线下活动", "门店展示", "印刷宣传", "其他"],
    )
)


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"¥{amount:,.2f}".replace(".00", "")


def _load_clients() -> list[dict[str, Any]]:
    """Load detached client summaries for the existing-client picker."""

    try:
        with get_session() as session:
            clients = session.scalars(select(Client).order_by(Client.name.asc())).all()
            return [
                {
                    "id": client.id,
                    "name": client.name,
                    "contact": client.contact or "",
                    "source": client.source or "其他",
                    "notes": client.notes or "",
                }
                for client in clients
            ]
    except Exception:
        st.warning("暂时无法读取已有客户，仍可先创建新客户。")
        return []


def _quote_or_default(**kwargs: Any) -> tuple[dict[str, float], str | None]:
    try:
        raw_quote = calculate_quote(**kwargs)
        quote = {
            key: float(raw_quote.get(key, 0) or 0)
            for key in (
                "base_price",
                "urgent_fee",
                "source_file_fee",
                "print_fee",
                "complex_cutout_fee",
                "redesign_fee",
                "oversized_fee",
                "complexity_fee",
                "manual_adjustment",
                "final_price",
            )
        }
        return quote, None
    except Exception:
        return {
            "base_price": 0.0,
            "urgent_fee": 0.0,
            "source_file_fee": 0.0,
            "print_fee": 0.0,
            "complex_cutout_fee": 0.0,
            "redesign_fee": 0.0,
            "oversized_fee": 0.0,
            "complexity_fee": 0.0,
            "manual_adjustment": float(kwargs.get("manual_adjustment", 0) or 0),
            "final_price": 0.0,
        }, "报价计算暂时不可用，请检查报价规则后重试。"


def _quote_rows_html(quote: dict[str, float]) -> str:
    rows = [
        ("基础价格", quote["base_price"]),
        ("加急费", quote["urgent_fee"]),
        ("源文件（PSD / AI）", quote["source_file_fee"]),
        ("印刷文件处理", quote["print_fee"]),
        ("复杂度费用", quote["complexity_fee"]),
    ]
    return "".join(
        f'<div class="pf-fee-row"><span>{escape(label)}</span><strong>{_money(amount)}</strong></div>'
        for label, amount in rows
    )


def _validate(
    *,
    client_name: str,
    order_title: str,
    original_requirement: str,
    deadline: date | None,
    revision_limit: int,
    final_price: float,
) -> list[str]:
    errors: list[str] = []
    if not client_name.strip():
        errors.append("请填写客户姓名。")
    if not order_title.strip():
        errors.append("请填写订单名称。")
    if not original_requirement.strip():
        errors.append("请填写客户原始需求。")
    if deadline is None:
        errors.append("请选择截止日期。")
    if revision_limit < 0:
        errors.append("免费修改次数不能小于 0。")
    if final_price < 0:
        errors.append("最终报价不能小于 0。")
    return errors


def _save_order(
    *,
    existing_client_id: int | None,
    client_name: str,
    client_contact: str,
    client_source: str,
    client_notes: str,
    title: str,
    design_type: str,
    original_requirement: str,
    usage: str,
    design_size: str,
    style: str,
    main_color: str,
    deadline: date,
    urgent: bool,
    source_file_required: bool,
    print_required: bool,
    revision_limit: int,
    notes: str,
    quote: dict[str, float],
    status: str,
) -> int:
    with get_session() as session:
        client: Client | None = None
        if existing_client_id is not None:
            client = session.get(Client, existing_client_id)

        if client is None:
            conditions = [Client.name == client_name.strip()]
            if client_contact.strip():
                conditions.append(Client.contact == client_contact.strip())
            client = session.scalar(select(Client).where(and_(*conditions)).limit(1))

        if client is None:
            client = Client(
                name=client_name.strip(),
                contact=client_contact.strip(),
                source=client_source,
                notes=client_notes.strip(),
            )
            session.add(client)
            session.flush()

        order = Order(
            client_id=client.id,
            title=title.strip(),
            design_type=design_type,
            original_requirement=original_requirement.strip(),
            structured_requirement="",
            usage=usage.strip(),
            size=design_size.strip(),
            style=style.strip(),
            main_color=main_color.strip(),
            status=status,
            price=quote["final_price"],
            deadline=datetime.combine(deadline, time.max),
            urgent=urgent,
            source_file_required=source_file_required,
            print_required=print_required,
            revision_limit=int(revision_limit),
            revision_used=0,
            notes=notes.strip(),
        )
        session.add(order)
        session.flush()

        session.add(
            Quote(
                order_id=order.id,
                base_price=quote["base_price"],
                urgent_fee=quote["urgent_fee"],
                source_file_fee=quote["source_file_fee"],
                print_fee=quote["print_fee"],
                complex_cutout_fee=quote["complex_cutout_fee"],
                redesign_fee=quote["redesign_fee"],
                oversized_fee=quote["oversized_fee"],
                complexity_fee=quote["complexity_fee"],
                manual_adjustment=quote["manual_adjustment"],
                final_price=quote["final_price"],
            )
        )
        session.flush()
        return int(order.id)


apply_theme()

try:
    init_db()
except Exception:
    st.error("数据库暂时无法连接，请检查数据库文件权限后重试。")
    st.stop()

st.markdown(
    """
    <style>
    .pf-fee-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: .72rem 0;
        color: var(--pf-muted);
        border-bottom: 1px solid rgba(236, 233, 229, .62);
    }
    .pf-fee-row:last-child { border-bottom: 0; }
    .pf-fee-row strong { color: var(--pf-text); font-weight: 650; }
    .pf-live-pill {
        display: inline-flex;
        margin-left: .45rem;
        padding: .2rem .52rem;
        border-radius: 999px;
        background: var(--pf-mint);
        color: var(--pf-green);
        font-size: .75rem;
        font-weight: 650;
        vertical-align: middle;
    }
    .pf-order-hint {
        margin: -.25rem 0 .7rem;
        color: var(--pf-muted);
        font-size: .82rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if success_message := st.session_state.pop("pf_new_order_success", None):
    st.success(success_message)

page_header("新建订单", "填写客户需求，系统将按规则自动生成参考报价。")

clients = _load_clients()
main_column, quote_column = st.columns([2.15, 1], gap="large")

with main_column:
    section_title("客户信息")
    client_mode_options = ["新建客户"] + (["选择已有客户"] if clients else [])
    client_mode = st.segmented_control(
        "客户录入方式",
        client_mode_options,
        default=client_mode_options[0],
        label_visibility="collapsed",
    )

    selected_client: dict[str, Any] | None = None
    existing_client_id: int | None = None
    if client_mode == "选择已有客户":
        client_labels = {
            client["id"]: f'{client["name"]} · {client["contact"] or "暂无联系方式"}'
            for client in clients
        }
        existing_client_id = st.selectbox(
            "选择客户 *",
            list(client_labels),
            format_func=lambda client_id: client_labels[client_id],
        )
        selected_client = next(
            (client for client in clients if client["id"] == existing_client_id), None
        )

    client_col, contact_col = st.columns(2)
    with client_col:
        client_name = st.text_input(
            "客户姓名 *",
            value=(selected_client or {}).get("name", ""),
            disabled=selected_client is not None,
            placeholder="例如：张同学",
        )
    with contact_col:
        client_contact = st.text_input(
            "联系方式",
            value=(selected_client or {}).get("contact", ""),
            disabled=selected_client is not None,
            placeholder="手机号 / 微信 / 其他联系方式（选填）",
        )

    with st.expander("更多客户信息"):
        source_col, client_note_col = st.columns(2)
        with source_col:
            selected_source = (selected_client or {}).get("source", CLIENT_SOURCES[0])
            source_index = CLIENT_SOURCES.index(selected_source) if selected_source in CLIENT_SOURCES else 0
            client_source = st.selectbox(
                "客户来源",
                CLIENT_SOURCES,
                index=source_index,
                disabled=selected_client is not None,
            )
        with client_note_col:
            client_notes = st.text_input(
                "客户备注",
                value=(selected_client or {}).get("notes", ""),
                disabled=selected_client is not None,
                placeholder="例如：偏好简洁风格（选填）",
            )

    order_title = st.text_input("订单名称 *", placeholder="例如：校园音乐节海报设计")

    st.divider()
    section_title("项目需求")

    design_col, usage_col = st.columns(2)
    with design_col:
        design_type = st.selectbox("设计类型 *", DESIGN_TYPES)
    with usage_col:
        usage = st.selectbox("使用场景 *", USAGE_SCENARIOS)

    original_requirement = st.text_area(
        "客户原始需求 *",
        height=132,
        max_chars=2000,
        placeholder="粘贴客户的原话，包括主题、时间、地点、文案、尺寸和风格偏好……",
    )

    size_col, style_col, color_col = st.columns(3)
    with size_col:
        design_size = st.text_input("设计尺寸", placeholder="例如：1080×1440px")
    with style_col:
        style = st.text_input("风格", placeholder="例如：青春、有活力")
    with color_col:
        main_color = st.text_input("主色调", placeholder="例如：橙色、米白")

    deadline_col, urgent_col = st.columns(2)
    with deadline_col:
        deadline = st.date_input(
            "截止日期 *",
            value=date.today(),
            min_value=date.today(),
            format="YYYY-MM-DD",
        )
    with urgent_col:
        urgency_choice = st.radio(
            "交付时效",
            ["不加急", "24小时内加急", "12小时内加急"],
            horizontal=True,
        )

    source_file_col, print_col = st.columns(2)
    with source_file_col:
        source_file_choice = st.radio(
            "需要源文件",
            ["不需要", "需要（PSD / AI 源文件）"],
            index=0,
            horizontal=True,
            help="默认仅交付 PNG、JPG 或 PDF 成品文件，不提供 PSD / AI 可编辑源文件。",
        )
    with print_col:
        print_choice = st.radio(
            "需要印刷文件处理",
            ["不需要", "需要（含印刷检查）"],
            index=0,
            horizontal=True,
        )

    with st.expander("更多报价与交付设置"):
        option_col_1, option_col_2, option_col_3 = st.columns(3)
        with option_col_1:
            complex_cutout = st.checkbox("包含复杂抠图")
        with option_col_2:
            redesign = st.checkbox("包含整体方案重做")
        with option_col_3:
            oversized = st.checkbox("超大尺寸设计")

        revision_limit = st.number_input(
            "免费修改次数",
            min_value=0,
            max_value=20,
            value=1,
            step=1,
        )
        notes = st.text_area("订单备注", height=90, placeholder="内部备注，不会展示给客户（选填）")

urgent = urgency_choice != "不加急"
hours_until_deadline = 12 if urgency_choice == "12小时内加急" else (24 if urgent else None)
source_file_required = source_file_choice.startswith("需要")
print_required = print_choice.startswith("需要")

base_quote, base_quote_error = _quote_or_default(
    design_type=design_type,
    urgent=urgent,
    hours_until_deadline=hours_until_deadline,
    source_file_required=source_file_required,
    print_required=print_required,
    complex_cutout=complex_cutout,
    redesign=redesign,
    oversized=oversized,
    manual_adjustment=0,
)

with quote_column:
    with st.container(border=True):
        st.markdown('### 参考报价 <span class="pf-live-pill">规则自动计算</span>', unsafe_allow_html=True)
        st.markdown('<div class="pf-order-hint">根据当前需求生成，提交前仍可微调。</div>', unsafe_allow_html=True)
        st.markdown(_quote_rows_html(base_quote), unsafe_allow_html=True)
        st.markdown(
            f'<div class="pf-quote-total"><span>参考报价</span><strong>{_money(base_quote["final_price"])}</strong></div>',
            unsafe_allow_html=True,
        )
        manual_adjustment = st.number_input(
            "手动调整（元）",
            min_value=-100000.0,
            max_value=100000.0,
            value=0.0,
            step=10.0,
            help="可输入优惠（负数）或额外费用（正数）。",
        )
        final_quote, final_quote_error = _quote_or_default(
            design_type=design_type,
            urgent=urgent,
            hours_until_deadline=hours_until_deadline,
            source_file_required=source_file_required,
            print_required=print_required,
            complex_cutout=complex_cutout,
            redesign=redesign,
            oversized=oversized,
            manual_adjustment=manual_adjustment,
        )
        st.markdown(
            f"""
            <div style="background:var(--pf-orange-soft);border:1px solid #ffd8c8;border-radius:10px;padding:.9rem 1rem;margin-top:.7rem">
                <div style="display:flex;align-items:center;justify-content:space-between;color:var(--pf-text);font-weight:650">
                    <span>调整后报价</span><strong style="color:var(--pf-orange);font-size:1.55rem">{_money(final_quote["final_price"])}</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if base_quote_error or final_quote_error:
            st.warning(base_quote_error or final_quote_error)
        else:
            st.markdown(
                '<div class="pf-success-strip">报价已自动计算完成<br><span class="pf-muted">源文件默认不提供，因此不会计入源文件费。</span></div>',
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
    draft_col, create_col = st.columns(2)
    save_draft = draft_col.button("保存草稿", width="stretch")
    create_order = create_col.button("创建订单", type="primary", width="stretch")

if save_draft or create_order:
    requested_status = "待沟通" if save_draft else ("待报价" if "待报价" in ORDER_STATUSES else ORDER_STATUSES[0])
    validation_errors = _validate(
        client_name=client_name,
        order_title=order_title,
        original_requirement=original_requirement,
        deadline=deadline,
        revision_limit=int(revision_limit),
        final_price=final_quote["final_price"],
    )
    if base_quote_error or final_quote_error:
        validation_errors.append("参考报价尚未成功计算，暂时无法保存订单。")

    if validation_errors:
        st.error("订单尚未保存，请先处理以下问题：\n\n- " + "\n- ".join(validation_errors))
    else:
        try:
            order_id = _save_order(
                existing_client_id=existing_client_id,
                client_name=client_name,
                client_contact=client_contact,
                client_source=client_source,
                client_notes=client_notes,
                title=order_title,
                design_type=design_type,
                original_requirement=original_requirement,
                usage=usage,
                design_size=design_size,
                style=style,
                main_color=main_color,
                deadline=deadline,
                urgent=urgent,
                source_file_required=source_file_required,
                print_required=print_required,
                revision_limit=int(revision_limit),
                notes=notes,
                quote=final_quote,
                status=requested_status,
            )
        except Exception:
            st.error("订单保存失败，数据没有写入。请检查必填信息或数据库连接后重试。")
        else:
            action = "草稿已保存" if save_draft else "订单创建成功"
            st.session_state["pf_new_order_success"] = f"{action}，订单编号为 #{order_id}。"
            st.rerun()
