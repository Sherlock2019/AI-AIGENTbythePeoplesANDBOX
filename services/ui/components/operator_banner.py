from __future__ import annotations

from typing import Iterable, Sequence, Tuple

import streamlit as st

from services.ui.theme_manager import get_palette

_CHATBOT_POINTS: Tuple[Tuple[str, str], ...] = (
    (
        "RAG-first pipeline with fallback",
        "Every question first hits the Chroma store inside the selected persona namespace. "
        "When chunks match (score ≥ 0.30) the answer is composed entirely from that content; "
        "only empty searches fall back to the base model.",
    ),
    (
        "Rich ingestion coverage",
        "Agent UI pages, CSV artifacts, docs, and sidebar uploads are chunked + embedded. "
        "Uploads can be tagged to a persona so they land in the right namespace immediately.",
    ),
    (
        "One-click rebuild/reset",
        "“Refresh RAG DB” and “Hard Reset & Rebuild” wipe the local store, re-ingest fresh data, "
        "and keep just the five most recent .tmp_runs per agent.",
    ),
    (
        "Dynamic personas/namespaces",
        "The persona selector auto-discovers agents from the /agents directory, so new personas "
        "show up in both ingestion and retrieval flows without code edits.",
    ),
    (
        "Device-aware embeddings",
        "Embedding helpers call select_device() and use GPU when available or CPU otherwise so "
        "ingestion stays fast across laptops and servers.",
    ),
    (
        "Logging & observability",
        "Every ingestion start/finish, upload, namespace choice, and RAG/fallback decision is logged "
        "under `.logs/` for traceability.",
    ),
)

def _chunk(seq: Sequence, size: int) -> Iterable[Sequence]:
    for idx in range(0, len(seq), size):
        yield seq[idx : idx + size]


def render_operator_banner(
    *,
    operator_name: str,
    title: str,
    summary: str,
    bullets: Sequence[str],
    metrics: Sequence[dict] | None = None,
    icon: str = "👤",
    show_chatbot_brief: bool = True,
) -> None:
    """Render the operator hero plus simple metric cards."""
    pal = get_palette()

    chatbot_brief_html = ""
    if show_chatbot_brief:
        upgrade_items = "".join(
            f"<li><strong>{title}:</strong> {body}</li>" for title, body in _CHATBOT_POINTS
        )
        chatbot_brief_html = (
            "<div class='chatbot-brief'><p>"
            "Here’s how the upgraded chatbot behaves across every agent:</p>"
            f"<ul>{upgrade_items}</ul></div>"
        )

    st.markdown(
        f"""
        <style>
        .operator-hero {{
            background: radial-gradient(circle at 15% 20%, {pal['card']}, {pal['bg']});
            border: 1px solid {pal['border']};
            border-radius: 18px;
            padding: 1.4rem 1.8rem;
            box-shadow: {pal['shadow']};
            color: {pal['text']};
        }}
        .operator-hero h3 {{
            margin-bottom: 0.4rem;
            font-size: 1.2rem;
        }}
        .operator-hero ul {{
            margin: 0;
            padding-left: 1.2rem;
            color: {pal['subtext']};
        }}
        .chatbot-brief {{
            margin-top: 1rem;
            padding: 0.8rem 1rem;
            background: rgba(59, 130, 246, 0.08);
            border-left: 3px solid {pal['accent']};
            border-radius: 12px;
            font-size: 0.9rem;
        }}
        .chatbot-brief ul {{
            margin: 0.5rem 0 0;
            padding-left: 1.1rem;
            color: {pal['text']};
        }}
        .chatbot-brief li {{
            margin-bottom: 0.35rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([1.5, 1], gap="large")

    with left_col:
        bullet_html = "".join(f"<li>{line}</li>" for line in bullets)
        st.markdown(
            f"""
            <div class="operator-hero">
                <h3>{icon} {title}: {operator_name}</h3>
                <p style="color:{pal['subtext']}; margin-bottom:0.6rem;">{summary}</p>
                <ul>{bullet_html}</ul>
                {chatbot_brief_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    metrics = list(metrics or [])
    if not metrics:
        with right_col:
            st.info("Metrics will appear once data is available.")
        return

    with right_col:
        for row in _chunk(metrics, 2):
            cols = st.columns(len(row))
            for col, metric in zip(cols, row):
                label = metric.get("label", "Metric")
                value = metric.get("value", "—")
                delta = metric.get("delta")
                context = metric.get("context")
                unit = metric.get("unit", "")
                display_value = f"{value} {unit}".strip()

                with col:
                    st.metric(label, display_value, delta)
                    if context:
                        st.caption(context)
