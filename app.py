"""PosterFlow AI Streamlit application entry point."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from database.db import init_db
from utils.constants import APP_VERSION


st.set_page_config(
    page_title="PosterFlow AI",
    page_icon="assets/posterflow-icon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    init_db()
except Exception as exc:  # pragma: no cover - defensive UI boundary
    st.error("数据库初始化失败，请检查数据库文件权限后重试。")
    st.caption(f"错误信息：{exc}")
    st.stop()

st.logo(
    "assets/posterflow-wordmark.png",
    size="large",
    icon_image="assets/posterflow-icon.png",
)
st.sidebar.caption(f"v{APP_VERSION} · 本地优先")

pages = [
    st.Page(
        "pages/1_dashboard.py",
        title="数据看板",
        default=True,
    ),
    st.Page(
        "pages/2_new_order.py",
        title="新建订单",
    ),
    st.Page(
        "pages/3_order_management.py",
        title="订单管理",
    ),
    st.Page(
        "pages/4_image_checker.py",
        title="图片检测",
    ),
    st.Page(
        "pages/5_customer_management.py",
        title="客户管理",
    ),
    st.Page(
        "pages/6_finance.py",
        title="收入统计",
    ),
]

navigation = st.navigation(pages, position="sidebar")
navigation.run()
