"""Visual tokens and global Streamlit styling."""

from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """Apply the warm, lightweight visual system selected for the MVP."""

    st.markdown(
        """
        <style>
        :root {
            --pf-canvas: #fbfaf8;
            --pf-surface: #ffffff;
            --pf-surface-soft: #fff7f2;
            --pf-text: #1f2328;
            --pf-muted: #767b83;
            --pf-line: #ece9e5;
            --pf-orange: #ff5b24;
            --pf-orange-dark: #e94712;
            --pf-orange-soft: #fff0e9;
            --pf-mint: #eaf8ef;
            --pf-green: #18966b;
            --pf-red: #d84a4a;
            --pf-radius: 10px;
        }

        html, body, [class*="st-"] {
            font-family: Inter, "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
        }

        [data-testid="stElementContainer"]:has(style) {
            display: none;
        }

        .stApp,
        [data-testid="stAppViewContainer"] {
            background: var(--pf-canvas);
            color: var(--pf-text);
        }

        [data-testid="stHeader"] {
            display: none;
        }

        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
            display: none;
        }

        [data-testid="stIconMaterial"] {
            display: none !important;
        }

        [data-testid="stSidebar"] {
            background: var(--pf-surface);
            border-right: 1px solid var(--pf-line);
            min-width: 244px;
            max-width: 244px;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.1rem;
        }

        [data-testid="stSidebarNav"] {
            padding-top: 0.5rem;
        }

        [data-testid="stSidebarNav"] a {
            border-radius: 9px;
            margin: 0.18rem 0.55rem;
            color: #50555d;
            min-height: 44px;
        }

        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background: var(--pf-orange-soft);
            color: var(--pf-orange-dark);
            font-weight: 650;
        }

        .block-container {
            max-width: 1480px;
            padding: 1.7rem 2.5rem 4rem;
        }

        h1, h2, h3 {
            color: var(--pf-text);
            letter-spacing: -0.02em;
        }

        h1 { font-size: 2rem !important; font-weight: 760 !important; }
        h2 { font-size: 1.3rem !important; font-weight: 720 !important; }
        h3 { font-size: 1.05rem !important; font-weight: 680 !important; }

        p, label, [data-testid="stCaptionContainer"] {
            color: var(--pf-muted);
        }

        div[data-testid="stTextInputRootElement"],
        div[data-testid="stNumberInputContainer"],
        div[data-baseweb="select"] > div,
        div[data-testid="stDateInput"] > div,
        textarea {
            border-radius: var(--pf-radius) !important;
        }

        div[data-testid="stTextInputRootElement"]:focus-within,
        div[data-testid="stNumberInputContainer"]:focus-within,
        div[data-baseweb="select"] > div:focus-within,
        textarea:focus {
            border-color: var(--pf-orange) !important;
            box-shadow: 0 0 0 1px var(--pf-orange) !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {
            border-radius: var(--pf-radius);
            min-height: 42px;
            font-weight: 650;
            border-color: #dedbd7;
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
        }

        .stButton > button p,
        .stDownloadButton > button p,
        [data-testid="stFormSubmitButton"] > button p {
            color: inherit !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            border-color: var(--pf-orange);
            color: var(--pf-orange-dark);
            transform: translateY(-1px);
        }

        .stButton > button[kind="primary"],
        [data-testid="stFormSubmitButton"] > button[kind="primary"] {
            background: var(--pf-orange);
            border-color: var(--pf-orange);
            color: #ffffff;
            box-shadow: 0 6px 16px rgba(255, 91, 36, 0.16);
        }

        .stButton > button[kind="primary"]:hover,
        [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
            background: var(--pf-orange-dark);
            border-color: var(--pf-orange-dark);
            color: #ffffff;
        }

        div[data-testid="stMetric"] {
            background: var(--pf-surface);
            border: 1px solid var(--pf-line);
            border-radius: 12px;
            padding: 1rem 1.05rem;
        }

        div[data-testid="stMetricValue"] {
            color: var(--pf-text);
            font-weight: 760;
            letter-spacing: -0.02em;
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            border: 1px solid var(--pf-line);
            border-radius: 12px;
            overflow: hidden;
        }

        [data-testid="stExpander"] {
            background: var(--pf-surface);
            border: 1px solid var(--pf-line);
            border-radius: 12px;
        }

        [data-testid="stAlert"] {
            border-radius: 10px;
        }

        .pf-brand {
            padding: 0.15rem 0.8rem 1.15rem;
            border-bottom: 1px solid var(--pf-line);
            margin-bottom: 0.4rem;
        }

        .pf-brand-name {
            font-size: 1.18rem;
            line-height: 1.25;
            font-weight: 790;
            color: var(--pf-text);
            letter-spacing: -0.025em;
        }

        .pf-brand-name span { color: var(--pf-orange); }
        .pf-brand-caption { color: var(--pf-muted); font-size: 0.76rem; margin-top: 0.28rem; }

        .pf-page-head {
            margin: 0 0 1.5rem;
        }

        .pf-page-head h1 {
            margin: 0;
            line-height: 1.25;
        }

        .pf-page-head p {
            margin: 0.42rem 0 0;
            font-size: 0.95rem;
        }

        .pf-section-title {
            display: flex;
            align-items: center;
            gap: 0.58rem;
            margin: 1rem 0 0.8rem;
            font-size: 1.05rem;
            font-weight: 720;
            color: var(--pf-text);
        }

        .pf-section-title::before {
            content: "";
            width: 3px;
            height: 20px;
            border-radius: 99px;
            background: var(--pf-orange);
        }

        .pf-panel {
            background: var(--pf-surface);
            border: 1px solid var(--pf-line);
            border-radius: 12px;
            padding: 1.1rem 1.2rem;
        }

        .pf-quote-total {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            border-top: 1px solid var(--pf-line);
            padding-top: 1rem;
            margin-top: 0.6rem;
            font-weight: 700;
        }

        .pf-quote-total strong {
            color: var(--pf-orange);
            font-size: 1.8rem;
            letter-spacing: -0.03em;
        }

        .pf-success-strip {
            background: var(--pf-mint);
            color: var(--pf-green);
            border-radius: 10px;
            padding: 0.8rem 0.9rem;
            font-size: 0.9rem;
            margin-top: 0.8rem;
        }

        .pf-muted { color: var(--pf-muted); }
        .pf-orange { color: var(--pf-orange); }

        @media (max-width: 920px) {
            .block-container { padding: 1.35rem 1rem 3rem; }
            [data-testid="stSidebar"] { min-width: 220px; max-width: 220px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
