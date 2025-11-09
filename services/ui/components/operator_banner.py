from __future__ import annotations

from typing import Iterable, Sequence

import streamlit as st

from services.ui.theme_manager import get_palette


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
) -> None:
    """Render the operator hero plus simple metric cards."""
    pal = get_palette()

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
