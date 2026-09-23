"""Local CSS and page layout helpers."""

import streamlit as st


def apply_theme(dark: bool) -> None:
    """Set a consistent local theme without loading remote scripts or fonts."""
    if dark:
        background = "#101923"
        surface = "#172430"
        surface_alt = "#1d2c39"
        text = "#e7eef5"
        muted = "#a2b2c1"
        border = "#314252"
        accent = "#72d4c2"
        sidebar = "#111d28"
    else:
        background = "#f4f7f9"
        surface = "#ffffff"
        surface_alt = "#f0f5f7"
        text = "#1d2b3a"
        muted = "#657587"
        border = "#dce4ea"
        accent = "#137f76"
        sidebar = "#f9fbfc"

    st.markdown(
        f"""
        <style>
        :root {{
          --canvas: {background}; --surface: {surface}; --surface-alt: {surface_alt};
          --ink: {text}; --muted: {muted}; --line: {border}; --accent: {accent};
        }}
        html, body, [data-testid="stAppViewContainer"] {{ background: var(--canvas); color: var(--ink); }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stSidebar"] {{ background: {sidebar}; border-right: 1px solid var(--line); }}
        [data-testid="stSidebar"] > div:first-child {{ padding-top: 1.35rem; }}
        .block-container {{ max-width: 1500px; padding: 2.1rem 2.6rem 3rem; }}
        h1, h2, h3, h4 {{ color: var(--ink) !important; letter-spacing: -0.025em; }}
        p, li, label {{ color: var(--ink); }}
        [data-testid="stCaptionContainer"] p, .muted {{ color: var(--muted) !important; }}
        div[data-testid="stMetric"] {{ background: var(--surface); border: 1px solid var(--line); padding: 1rem 1.1rem; border-radius: 14px; }}
        div[data-testid="stMetricLabel"] p {{ color: var(--muted) !important; font-size: .82rem; }}
        div[data-testid="stMetricValue"] {{ color: var(--ink) !important; font-weight: 700; }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{ background: var(--surface); border-color: var(--line); border-radius: 16px; }}
        div[data-testid="stAlert"] {{ border-radius: 12px; }}
        .brand-row {{ display:flex; align-items:center; gap:11px; margin: 0 0 1.55rem; }}
        .brand-mark {{ width:40px; height:40px; display:grid; place-items:center; border-radius:13px; color:#fff; background:linear-gradient(145deg,#197e76,#1d5e75); font-size:19px; font-weight:800; }}
        .brand-title {{ color:var(--ink); font-weight:750; font-size:15px; line-height:1.15; }}
        .brand-subtitle {{ color:var(--muted); font-size:10px; margin-top:4px; letter-spacing:.08em; text-transform:uppercase; }}
        .eyebrow {{ color: var(--accent); font-size: .75rem; font-weight: 750; text-transform: uppercase; letter-spacing: .11em; margin-bottom: .35rem; }}
        .page-title {{ font-size: 2rem; line-height:1.16; font-weight:760; letter-spacing:-.045em; margin:0 0 .4rem; color:var(--ink); }}
        .page-subtitle {{ color:var(--muted); font-size:.98rem; margin:0 0 1.5rem; }}
        .panel-title {{ color:var(--ink); font-weight:700; font-size:1.04rem; margin:0 0 .35rem; }}
        .panel-copy {{ color:var(--muted); font-size:.88rem; line-height:1.55; }}
        .summary-card {{ background:linear-gradient(135deg, rgba(19,127,118,.10), rgba(19,127,118,.025)); border:1px solid rgba(19,127,118,.20); border-left:4px solid var(--accent); border-radius:15px; padding:1.15rem 1.35rem; margin:.35rem 0 1rem; }}
        .summary-card p {{ margin:.35rem 0; line-height:1.55; }}
        .status-pill {{ display:inline-block; background:var(--surface-alt); border:1px solid var(--line); border-radius:999px; padding:.28rem .65rem; color:var(--muted); font-size:.76rem; font-weight:650; }}
        .drop-note {{ color:var(--muted); background:var(--surface-alt); border:1px dashed var(--line); padding:.8rem 1rem; border-radius:12px; font-size:.84rem; line-height:1.5; }}
        .transcript-line {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:.8rem 1rem; margin:.45rem 0; }}
        .transcript-speaker {{ color:var(--accent); font-size:.76rem; font-weight:750; margin-bottom:.25rem; }}
        .transcript-text {{ color:var(--ink); line-height:1.55; }}
        .deadline-overdue {{ color:#c64040; font-weight:700; }}
        .deadline-soon {{ color:#c64040; font-weight:700; }}
        .deadline-ok {{ color:var(--accent); font-weight:700; }}
        .small-foot {{ color:var(--muted); font-size:.76rem; }}
        button[kind="primary"] {{ background:linear-gradient(135deg,#157e76,#17687b); border:0; }}
        button[kind="primary"], button[kind="primary"] p {{ color:#fff !important; }}
        button[kind="secondary"], [data-testid="stFormSubmitButton"] button[kind="secondary"] {{
            background:var(--surface); color:var(--ink); border:1px solid var(--line);
        }}
        button[kind="secondary"] p {{ color:var(--ink) !important; }}
        button:disabled {{ opacity:.55; }}
        [data-baseweb="input"], [data-baseweb="base-input"],
        [data-baseweb="select"] > div, [data-baseweb="textarea"] {{
            background:var(--surface-alt) !important; color:var(--ink) !important; border-color:var(--line) !important;
        }}
        input, textarea {{ color:var(--ink) !important; }}
        [data-baseweb="menu"], [role="listbox"], [role="option"] {{
            background:var(--surface) !important; color:var(--ink) !important;
        }}
        [data-testid="stFileUploaderDropzone"] {{ background:var(--surface-alt); border:1px dashed var(--line); }}
        [data-baseweb="tab"] {{ color:var(--muted); }}
        [data-baseweb="tab"][aria-selected="true"] {{ color:var(--accent); }}
        [data-testid="stForm"], [data-testid="stExpander"] {{ border-color:var(--line); }}
        [data-testid="stDataFrame"] {{ filter: {"invert(.89) hue-rotate(180deg)" if dark else "none"}; }}
        [data-testid="stFileUploader"] {{ background:var(--surface); border-radius:14px; }}
        [data-testid="stDataEditor"] {{ background:var(--surface); border-radius:12px; }}
        @media (max-width: 820px) {{ .block-container {{ padding: 1.2rem 1rem 2rem; }} .page-title {{ font-size:1.6rem; }} }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="eyebrow">{eyebrow}</div><div class="page-title">{title}</div><div class="page-subtitle">{subtitle}</div>',
        unsafe_allow_html=True,
    )
