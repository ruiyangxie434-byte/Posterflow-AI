"""Small reusable components shared by Streamlit pages."""

from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st


def render_sidebar_brand() -> None:
    """Render the compact product wordmark in the sidebar."""

    with st.sidebar:
        st.markdown(
            """
            <div class="pf-brand">
                <div class="pf-brand-name">PosterFlow <span>AI</span></div>
                <div class="pf-brand-caption">海报接单与交付管理</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def page_header(title: str, subtitle: str = "") -> None:
    """Render a page title and one-line supporting description."""

    subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f'<div class="pf-page-head"><h1>{escape(title)}</h1>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


def section_title(title: str) -> None:
    """Render a lightweight section heading matching the selected mockup."""

    st.markdown(
        f'<div class="pf-section-title">{escape(title)}</div>',
        unsafe_allow_html=True,
    )


def panel_start() -> None:
    st.markdown('<div class="pf-panel">', unsafe_allow_html=True)


def panel_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def money(value: Any) -> str:
    """Format a numeric value as a concise renminbi amount."""

    try:
        return f"¥{float(value or 0):,.2f}".replace(".00", "")
    except (TypeError, ValueError):
        return "¥0"


def status_label(status: str) -> str:
    """Return a readable status label while tolerating empty database values."""

    return status or "待沟通"

