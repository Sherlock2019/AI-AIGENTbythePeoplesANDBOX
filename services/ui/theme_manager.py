"""Centralized dark/light theme helpers shared across all Streamlit agents."""
from __future__ import annotations

import streamlit as st

DEFAULT_THEME = "dark"

PALETTE = {
    "dark": {
        "bg": "#05070d",
        "bg_alt": "#0b1220",
        "text": "#ffffff",
        "subtext": "#cbd5e1",
        "muted": "#9fb3d0",
        "annotation": "#e2e8f0",
        "card": "#0f172a",
        "border": "rgba(148,163,184,0.35)",
        "accent": "#3b82f6",
        "accent_alt": "#10b981",
        "tab_bg": "#111827",
        "tab_active_bg": "#2563eb",
        "tab_hover_bg": "rgba(37,99,235,0.25)",
        "table_bg": "#0f172a",
        "table_head_bg": "#1b2b46",
        "table_head_tx": "#f8fafc",
        "table_hover_bg": "rgba(37,99,235,0.18)",
        "sidebar_bg": "linear-gradient(180deg,#05070d,#0e1527)",
        "sidebar_border": "rgba(148,163,184,0.35)",
        "input_bg": "#111b2f",
        "input_border": "rgba(148,163,184,0.55)",
        "json_bg": "#0d1526",
        "json_text": "#f8fafc",
        "shadow": "0 18px 50px rgba(2,6,23,0.65)",
    },
    "light": {
        "bg": "#f5f7fa",
        "bg_alt": "#ffffff",
        "text": "#0f172a",
        "subtext": "#475569",
        "muted": "#64748b",
        "annotation": "#1e293b",
        "card": "#ffffff",
        "border": "rgba(148,163,184,0.35)",
        "accent": "#007aff",
        "accent_alt": "#0f9d58",
        "tab_bg": "#eef2ff",
        "tab_active_bg": "#007aff",
        "tab_hover_bg": "rgba(59,130,246,0.15)",
        "table_bg": "#ffffff",
        "table_head_bg": "#e2e8f0",
        "table_head_tx": "#111827",
        "table_hover_bg": "rgba(0,122,255,0.08)",
        "sidebar_bg": "linear-gradient(180deg,#f8fafc,#edf2ff)",
        "sidebar_border": "rgba(148,163,184,0.5)",
        "input_bg": "#ffffff",
        "input_border": "rgba(148,163,184,0.6)",
        "json_bg": "#f8fafc",
        "json_text": "#0f172a",
        "shadow": "0 8px 24px rgba(15,23,42,0.12)",
    },
}


def _normalize_theme(theme: str | None) -> str:
    if not theme:
        return DEFAULT_THEME
    candidate = str(theme).lower()
    return candidate if candidate in PALETTE else DEFAULT_THEME


def ensure_theme(default: str = DEFAULT_THEME) -> str:
    """Ensure ui_theme/session state keys exist and return active theme."""
    normalized = _normalize_theme(st.session_state.get("ui_theme", default))
    st.session_state.setdefault("ui_theme", normalized)
    st.session_state.setdefault("theme", normalized)  # backward compatibility
    return normalized


def get_theme() -> str:
    """Return the currently selected theme."""
    return ensure_theme()


def set_theme(theme: str) -> str:
    """Update the shared theme state."""
    normalized = _normalize_theme(theme)
    st.session_state["ui_theme"] = normalized
    st.session_state["theme"] = normalized
    return normalized


def get_palette(theme: str | None = None) -> dict[str, str]:
    """Expose palette so agents can style custom components."""
    normalized = _normalize_theme(theme or get_theme())
    return PALETTE[normalized]


def apply_theme(theme: str | None = None) -> str:
    """Inject CSS for the requested theme (defaulting to session state)."""
    normalized = set_theme(theme or get_theme())
    pal = get_palette(normalized)

    st.markdown(
        f"""
        <style>
        html, body, [data-testid="stAppViewContainer"], .stApp {{
            background: radial-gradient(circle at 20% 20%, {pal['bg']}, {pal['bg_alt']}) !important;
            color: {pal['text']} !important;
            font-family: "Inter","SF Pro Display","Segoe UI",system-ui,sans-serif !important;
        }}
        h1,h2,h3,h4,h5,h6 {{
            color: {pal['text']} !important;
            letter-spacing: -0.02em !important;
        }}
        p, li, span, label, .stMarkdown {{
            color: {pal['subtext']} !important;
        }}
        small, .stCaption {{
            color: {pal['muted']} !important;
        }}
        a, a:link, a:visited {{
            color: {pal['accent']} !important;
        }}
        a:hover {{
            color: {pal['accent_alt']} !important;
            text-decoration: underline;
        }}
        hr {{
            border: none !important;
            height: 1px !important;
            background: linear-gradient(90deg,transparent,{pal['accent']},transparent) !important;
        }}

        .stMarkdown, .stContainer, .stAlert, [class*="stCard"], .block-container {{
            background: {pal['card']} !important;
            border: 1px solid {pal['border']} !important;
            border-radius: 12px !important;
            box-shadow: {pal['shadow']} !important;
        }}

        .stButton>button, button[kind="primary"], .stDownloadButton>button {{
            background: linear-gradient(180deg,{pal['accent']},{pal['accent_alt']}) !important;
            color: #ffffff !important;
            border: 1px solid {pal['accent']} !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.25s ease-in-out !important;
        }}
        .stButton>button:hover {{
            filter: brightness(1.05);
            transform: translateY(-1px);
        }}

        .stTextInput>div>div>input,
        .stNumberInput input,
        textarea, input[type="text"] {{
            background: {pal['input_bg']} !important;
            color: {pal['text']} !important;
            border: 1px solid {pal['input_border']} !important;
            border-radius: 8px !important;
            padding: 6px 10px !important;
        }}
        .stSelectbox>div>div {{
            background: {pal['input_bg']} !important;
            color: {pal['text']} !important;
            border: 1px solid {pal['input_border']} !important;
            border-radius: 8px !important;
        }}
        ::placeholder {{
            color: {pal['muted']} !important;
        }}
        [data-baseweb="select"] > div {{
            background: {pal['input_bg']} !important;
            color: {pal['text']} !important;
            border-radius: 8px !important;
        }}
        [data-baseweb="popover"], [role="listbox"] {{
            background: {pal['card']} !important;
            border: 1px solid {pal['border']} !important;
            color: {pal['text']} !important;
        }}
        [data-baseweb="menu-item"] {{
            background: {pal['card']} !important;
            color: {pal['text']} !important;
        }}
        [data-baseweb="menu-item"]:hover {{
            background: {pal['tab_hover_bg'] if 'tab_hover_bg' in pal else pal['table_hover_bg']} !important;
            color: {pal['text']} !important;
        }}

        .stTabs [data-baseweb="tab-list"] button {{
            background: {pal['tab_bg']} !important;
            color: {pal['text']} !important;
            border-radius: 8px !important;
            border: 1px solid {pal['border']} !important;
            margin-right: 6px !important;
        }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
            background: {pal['tab_active_bg']} !important;
            color: #fff !important;
        }}

        [data-testid="stDataFrame"] {{
            background: {pal['table_bg']} !important;
            border: 1px solid {pal['border']} !important;
            border-radius: 12px !important;
            box-shadow: inset 0 0 12px rgba(0,0,0,0.35);
        }}
        [data-testid="stDataFrame"] thead tr th {{
            background: {pal['table_head_bg']} !important;
            color: {pal['table_head_tx']} !important;
            font-weight: 600 !important;
            border-bottom: 2px solid {pal['accent']} !important;
        }}
        [data-testid="stDataFrame"] tbody tr:hover {{
            background: {pal['table_hover_bg']} !important;
        }}

        [data-testid="stJson"], [data-testid="stCodeBlock"], pre, code {{
            background: {pal['json_bg']} !important;
            color: {pal['json_text']} !important;
            border: 1px solid {pal['border']} !important;
            border-radius: 8px !important;
            font-family: "SF Mono","Menlo","Consolas",monospace !important;
            font-size: 0.9rem !important;
            padding: 0.65rem 0.75rem !important;
        }}
        [data-testid="stJson"] pre {{
            padding: 0.75rem !important;
        }}
        pre code {{
            background: transparent !important;
            padding: 0 !important;
        }}

        section[data-testid="stSidebar"] {{
            background: {pal['sidebar_bg']} !important;
            border-right: 1px solid {pal['sidebar_border']} !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: {pal['text']} !important;
        }}

        [data-testid="stMetricValue"] {{
            color: {pal['text']} !important;
        }}
        [data-testid="stMetricLabel"], .metric-label {{
            color: {pal['annotation']} !important;
        }}
<<<<<<< HEAD
=======
        .metric-title {{
            font-size: 1.3rem !important;
            font-weight: 700 !important;
            margin-bottom: 0.5rem !important;
        }}
        .metric-explain {{
            font-size: 0.95rem !important;
            opacity: 0.85 !important;
            margin-bottom: 1.4rem !important;
        }}
        ul[role="listbox"] li {{
            font-size: 1.15rem !important;
            line-height: 1.45rem !important;
            white-space: pre-wrap !important;
        }}
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /* Global selectbox/listbox color overrides */
        div[data-baseweb="select"] > div {
            color: #000000 !important;
            background-color: #ffffff !important;
        }
        div[data-baseweb="select"] input {
            color: #000000 !important;
        }
        div[data-baseweb="select"] span {
            color: #000000 !important;
        }
        ul[role="listbox"],
        div[role="listbox"] {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        ul[role="listbox"] li,
        div[role="option"],
        div[role="listbox"] * {
            color: #000000 !important;
        }
        [role="option"]:hover {
            color: #000000 !important;
            background-color: #f1f5f9 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    return normalized


def render_theme_toggle(
    label: str = "🌗 Dark mode",
    key: str = "ui_theme_toggle",
    *,
    help: str | None = None,
    rerun: bool = True,
) -> str:
    """
    Render a toggle widget that keeps the shared theme in sync.

    Returns the selected theme so callers can branch on it if needed.
    """
    current = get_theme()
    is_dark = current == "dark"
    new_is_dark = st.toggle(label, value=is_dark, key=key, help=help)
    selected = "dark" if new_is_dark else "light"
    if selected != current:
        set_theme(selected)
        apply_theme(selected)
        if rerun:
            st.rerun()
    return selected


def init_theme(*, auto_sidebar_toggle: bool = False, toggle_key: str = "ui_theme_toggle") -> str:
    """Call once per page to inject CSS and optionally expose a sidebar toggle."""
    theme = apply_theme()
    if auto_sidebar_toggle:
        with st.sidebar:
            render_theme_toggle(key=toggle_key)
    return theme
