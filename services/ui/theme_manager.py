"""Centralized dark/light theme helpers shared across all Streamlit agents.

The look is deliberately restrained: neutral graphite/slate surfaces, a single
muted accent, flat fills (no gradients or glows) and thin hairline borders.
"""
from __future__ import annotations

import streamlit as st

DEFAULT_THEME = "dark"

PALETTE = {
    "dark": {
        "bg": "#0f1115",
        "bg_alt": "#0f1115",
        "text": "#e6e8eb",
        "subtext": "#b3b9c2",
        "muted": "#8a919c",
        "annotation": "#c9ced5",
        "card": "#161a20",
        "border": "#272c35",
        "accent": "#6b8bb0",
        "accent_alt": "#7d9a8a",
        "tab_bg": "transparent",
        "tab_active_bg": "transparent",
        "tab_hover_bg": "rgba(255,255,255,0.04)",
        "table_bg": "#161a20",
        "table_head_bg": "#1c2128",
        "table_head_tx": "#c9ced5",
        "table_hover_bg": "rgba(255,255,255,0.03)",
        "sidebar_bg": "#12151a",
        "sidebar_border": "#272c35",
        "input_bg": "#12151a",
        "input_border": "#323844",
        "json_bg": "#12151a",
        "json_text": "#d6dae0",
        "shadow": "0 1px 2px rgba(0,0,0,0.35)",
        "button_bg": "#1c2128",
        "button_hover_bg": "#232931",
        "button_text": "#e6e8eb",
    },
    "light": {
        "bg": "#f6f7f9",
        "bg_alt": "#f6f7f9",
        "text": "#1a1f27",
        "subtext": "#4a5361",
        "muted": "#6b7380",
        "annotation": "#2d3440",
        "card": "#ffffff",
        "border": "#dfe3e8",
        "accent": "#2f4f75",
        "accent_alt": "#3f6b55",
        "tab_bg": "transparent",
        "tab_active_bg": "transparent",
        "tab_hover_bg": "rgba(15,23,42,0.04)",
        "table_bg": "#ffffff",
        "table_head_bg": "#f1f3f6",
        "table_head_tx": "#2d3440",
        "table_hover_bg": "rgba(15,23,42,0.03)",
        "sidebar_bg": "#ffffff",
        "sidebar_border": "#dfe3e8",
        "input_bg": "#ffffff",
        "input_border": "#cfd5dc",
        "json_bg": "#f6f7f9",
        "json_text": "#1a1f27",
        "shadow": "0 1px 2px rgba(15,23,42,0.06)",
        "button_bg": "#ffffff",
        "button_hover_bg": "#f1f3f6",
        "button_text": "#1a1f27",
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        html, body, [data-testid="stAppViewContainer"], .stApp {{
            background: {pal['bg']} !important;
            color: {pal['text']} !important;
            font-family: "Inter","Segoe UI",system-ui,-apple-system,sans-serif !important;
            font-feature-settings: "cv11","ss01";
        }}
        [data-testid="stHeader"] {{
            background: {pal['bg']} !important;
            border-bottom: 1px solid {pal['border']} !important;
        }}
        .block-container {{
            padding-top: 2.5rem !important;
        }}
        h1,h2,h3,h4,h5,h6 {{
            color: {pal['text']} !important;
            letter-spacing: -0.015em !important;
            font-weight: 600 !important;
        }}
        h1 {{ font-size: 1.85rem !important; }}
        h2 {{ font-size: 1.45rem !important; }}
        h3 {{ font-size: 1.2rem !important; }}
        p, li, span, label, .stMarkdown {{
            color: {pal['subtext']} !important;
        }}
        small, .stCaption, [data-testid="stCaptionContainer"] {{
            color: {pal['muted']} !important;
        }}
        a, a:link, a:visited {{
            color: {pal['accent']} !important;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        a:focus-visible, button:focus-visible {{
            outline: 2px solid {pal['accent']} !important;
            outline-offset: 2px;
        }}
        hr {{
            border: none !important;
            height: 1px !important;
            background: {pal['border']} !important;
            margin: 1.25rem 0 !important;
        }}

        /* Card chrome is opt-in. Applying it to .stMarkdown wrapped every
           st.caption/st.write — and every `---` rule — in its own box. */
        .stAlert, [class*="stCard"], .ai-card,
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: {pal['card']} !important;
            border: 1px solid {pal['border']} !important;
            border-radius: 8px !important;
            box-shadow: {pal['shadow']} !important;
        }}
        /* Nested bordered containers stay flat so cards don't stack shadows. */
        [data-testid="stVerticalBlockBorderWrapper"]
            [data-testid="stVerticalBlockBorderWrapper"] {{
            background: transparent !important;
            box-shadow: none !important;
        }}

        /* Buttons: neutral by default, solid accent only for primary actions. */
        .stButton>button, .stDownloadButton>button, .stFormSubmitButton>button {{
            background: {pal['button_bg']} !important;
            color: {pal['button_text']} !important;
            border: 1px solid {pal['input_border']} !important;
            border-radius: 6px !important;
            font-weight: 500 !important;
            font-size: 0.92rem !important;
            padding: 0.45rem 1rem !important;
            box-shadow: none !important;
            transition: background 0.15s ease, border-color 0.15s ease !important;
        }}
        .stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover {{
            background: {pal['button_hover_bg']} !important;
            border-color: {pal['accent']} !important;
            filter: none !important;
            transform: none !important;
        }}
        .stButton>button p, .stDownloadButton>button p {{
            color: inherit !important;
        }}
        button[kind="primary"], button[data-testid="baseButton-primary"],
        button[data-testid="stBaseButton-primary"] {{
            background: {pal['accent']} !important;
            border-color: {pal['accent']} !important;
            color: #ffffff !important;
        }}
        button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {{
            filter: brightness(1.08) !important;
        }}

        .stTextInput>div>div>input,
        .stNumberInput input,
        textarea, input[type="text"] {{
            background: {pal['input_bg']} !important;
            color: {pal['text']} !important;
            border: 1px solid {pal['input_border']} !important;
            border-radius: 6px !important;
            padding: 6px 10px !important;
        }}
        .stTextInput>div>div>input:focus, textarea:focus {{
            border-color: {pal['accent']} !important;
            box-shadow: none !important;
        }}
        .stSelectbox>div>div {{
            background: {pal['input_bg']} !important;
            color: {pal['text']} !important;
            border-radius: 6px !important;
        }}
        ::placeholder {{
            color: {pal['muted']} !important;
        }}
        div[data-baseweb="select"] > div {{
            background: {pal['input_bg']} !important;
            color: {pal['text']} !important;
            border: 1px solid {pal['input_border']} !important;
            border-radius: 6px !important;
        }}
        div[data-baseweb="select"] input,
        div[data-baseweb="select"] span {{
            color: {pal['text']} !important;
        }}
        [data-baseweb="popover"], [role="listbox"],
        ul[role="listbox"], div[role="listbox"] {{
            background: {pal['card']} !important;
            border: 1px solid {pal['border']} !important;
            color: {pal['text']} !important;
        }}
        [data-baseweb="menu-item"], [role="option"],
        ul[role="listbox"] li, div[role="listbox"] * {{
            background: {pal['card']} !important;
            color: {pal['text']} !important;
        }}
        [data-baseweb="menu-item"]:hover, [role="option"]:hover,
        [role="option"][aria-selected="true"] {{
            background: {pal['button_hover_bg']} !important;
            color: {pal['text']} !important;
        }}
        ul[role="listbox"] li {{
            line-height: 1.45rem !important;
            white-space: pre-wrap !important;
        }}

        /* Tabs: plain labels with an accent underline on the active tab. */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.25rem !important;
            border-bottom: 1px solid {pal['border']} !important;
        }}
        .stTabs [data-baseweb="tab-list"] button,
        [data-testid="stTabs"] [data-baseweb="tab"] {{
            background: transparent !important;
            color: {pal['muted']} !important;
            border: none !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            margin-right: 0 !important;
            padding: 0.6rem 1rem !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
        }}
        .stTabs [data-baseweb="tab-list"] button:hover {{
            color: {pal['text']} !important;
            background: {pal['tab_hover_bg']} !important;
            box-shadow: none !important;
        }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"],
        [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {{
            background: transparent !important;
            color: {pal['text']} !important;
            border-bottom: 2px solid {pal['accent']} !important;
            box-shadow: none !important;
        }}
        .stTabs [data-baseweb="tab-list"] button p {{
            color: inherit !important;
            font-size: inherit !important;
        }}
        .stTabs [data-baseweb="tab-highlight"] {{
            background: {pal['accent']} !important;
        }}

        [data-testid="stDataFrame"] {{
            background: {pal['table_bg']} !important;
            border: 1px solid {pal['border']} !important;
            border-radius: 8px !important;
            box-shadow: none !important;
        }}
        [data-testid="stDataFrame"] thead tr th {{
            background: {pal['table_head_bg']} !important;
            color: {pal['table_head_tx']} !important;
            font-weight: 600 !important;
            border-bottom: 1px solid {pal['border']} !important;
        }}
        [data-testid="stDataFrame"] tbody tr:hover {{
            background: {pal['table_hover_bg']} !important;
        }}

        [data-testid="stJson"], [data-testid="stCodeBlock"], pre, code {{
            background: {pal['json_bg']} !important;
            color: {pal['json_text']} !important;
            border: 1px solid {pal['border']} !important;
            border-radius: 6px !important;
            font-family: "JetBrains Mono","SF Mono","Consolas",monospace !important;
            font-size: 0.86rem !important;
            padding: 0.65rem 0.75rem !important;
        }}
        [data-testid="stJson"] pre {{
            padding: 0.75rem !important;
        }}
        pre code {{
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
        }}

        section[data-testid="stSidebar"] {{
            background: {pal['sidebar_bg']} !important;
            border-right: 1px solid {pal['sidebar_border']} !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: {pal['text']} !important;
        }}

        [data-testid="stMetric"] {{
            background: {pal['card']};
            border: 1px solid {pal['border']};
            border-radius: 8px;
            padding: 0.8rem 1rem;
        }}
        [data-testid="stMetricValue"] {{
            color: {pal['text']} !important;
            font-weight: 600 !important;
        }}
        [data-testid="stMetricLabel"], .metric-label {{
            color: {pal['muted']} !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-size: 0.75rem !important;
        }}
        .metric-title {{
            font-size: 1.1rem !important;
            font-weight: 600 !important;
            margin-bottom: 0.5rem !important;
        }}
        .metric-explain {{
            font-size: 0.92rem !important;
            color: {pal['muted']} !important;
            margin-bottom: 1.2rem !important;
        }}

        /* Legacy "neon" classes still used by some pages: render them flat. */
        .stApp .neon-header {{
            background: transparent !important;
            color: {pal['text']} !important;
            text-shadow: none !important;
            box-shadow: none !important;
            border: none !important;
            border-bottom: 1px solid {pal['border']} !important;
            border-radius: 0 !important;
            text-align: left !important;
            font-size: 1.15rem !important;
            font-weight: 600 !important;
            padding: 0 0 0.6rem 0 !important;
            margin-bottom: 1rem !important;
        }}
        .stApp .neon-frame {{
            background: {pal['card']} !important;
            border: 1px solid {pal['border']} !important;
            border-radius: 8px !important;
            box-shadow: none !important;
            animation: none !important;
        }}
        .stApp .launchbtn, .stApp .macbtn, .stApp a.macbtn {{
            display: inline-block;
            background: {pal['button_bg']} !important;
            color: {pal['button_text']} !important;
            border: 1px solid {pal['input_border']} !important;
            border-radius: 6px !important;
            box-shadow: none !important;
            text-shadow: none !important;
            font-weight: 500 !important;
            text-decoration: none !important;
            transform: none !important;
        }}
        .stApp .launchbtn:hover, .stApp .macbtn:hover {{
            background: {pal['button_hover_bg']} !important;
            border-color: {pal['accent']} !important;
            text-decoration: none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    return normalized


def render_theme_toggle(
    label: str = "Dark mode",
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
