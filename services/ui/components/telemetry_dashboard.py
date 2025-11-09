from __future__ import annotations
import logging
import os
from pathlib import Path
import math
from html import escape
from typing import Sequence
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------
_LOG_PATH = Path(os.getenv("TELEMETRY_DASHBOARD_LOG", "logs/telemetry_dashboard.log"))
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
_logger = logging.getLogger("telemetry_dashboard")
if not _logger.handlers:
    handler = logging.FileHandler(_LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(os.getenv("TELEMETRY_DASHBOARD_LOG_LEVEL", "INFO").upper())

_DEBUG_HTML_DUMP = os.getenv("TELEMETRY_DASHBOARD_DEBUG_HTML", "0").lower() in {"1", "true", "yes"}


# ---------------------------------------------------------
# UTILITY HELPERS (unchanged)
# ---------------------------------------------------------
def _clamp(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.6
    return max(0.0, min(1.0, numeric))


def _arc_gradient(color: str, fill: float) -> str:
    fill = _clamp(fill)
    base = 220.0
    span = 50.0 + fill * 240.0
    end = base + span
    return (
        f"conic-gradient(from {base}deg, transparent 0deg {base}deg, "
        f"rgba(255,255,255,0.05) {base}deg {base + 6:.1f}deg, "
        f"{color} {base + 6:.1f}deg {end:.1f}deg, transparent {end:.1f}deg 360deg)"
    )


def _format_perf_value(value: str) -> tuple[str, str]:
    text = str(value or "—").strip()
    if text.endswith("%") and len(text) > 1:
        return text[:-1], "%"
    return text or "—", ""


def _normalize_metric_value(value: object, unit: object) -> tuple[str, str]:
    value_text = str(value or "—").strip()
    unit_text = str(unit or "").strip()

    if unit_text and value_text.lower().endswith(unit_text.lower()):
        value_text = value_text[: -len(unit_text)].rstrip(" :")
    if not value_text:
        value_text = "—"
    return value_text, unit_text


def _dump_debug_html(headline: str, html_block: str) -> None:
    """Optionally dump rendered HTML for debugging Streamlit sanitization issues."""
    if not _DEBUG_HTML_DUMP:
        return
    safe_name = headline.lower().replace(" ", "_").replace("/", "_")
    dump_file = _LOG_PATH.parent / f"{_LOG_PATH.stem}_{safe_name}.html"
    try:
        dump_file.write_text(html_block, encoding="utf-8")
        _logger.info("Wrote debug HTML dump to %s", dump_file)
    except Exception as exc:  # pragma: no cover
        _logger.warning("Failed to write telemetry HTML dump: %s", exc)


# ---------------------------------------------------------
# MAIN FUNCTION — PIXEL PERFECT
# ---------------------------------------------------------
def render_telemetry_dashboard(
    *,
    headline: str,
    metrics: Sequence[dict],
    performance_value: str,
    performance_label: str,
    performance_gradient: str | None = None,
):
    """Render a pixel-perfect Mercedes-Benz style telemetry dashboard."""

    # -----------------------------------------------------
    #  PIXEL-PERFECT CSS
    # -----------------------------------------------------
    _logger.info(
        "Render requested for headline=%s metrics=%s", headline, len(metrics)
    )

    styles_block = """
<style>

    /* Main shell */
    .ai-mercedes-shell {
        width: 100%;
        display: flex;
        justify-content: center;
        padding: 0 clamp(1rem, 4vw, 3rem);
    }

    /* Dashboard container */
    .ai-mercedes-dashboard {
        width: min(1400px, 96%);
        position: relative;
        margin: clamp(1.5rem, 3vw, 3rem) auto clamp(2.5rem, 5vw, 4rem);
        padding: clamp(2rem, 5vw, 4rem) clamp(1.5rem, 4vw, 3rem) clamp(3rem, 5vw, 4.2rem);
        border-radius: 38px;
        background: radial-gradient(circle at center, #0b0f19 0%, #05070c 100%);
        overflow: visible !important;
        min-height: 520px !important;
        padding-top: 60px !important;
        padding-bottom: 60px !important;
        color: #e8eefc;
        text-align: center;
        font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        box-shadow:
            inset 0 0 35px rgba(255, 255, 255, 0.03),
            0 35px 95px rgba(0, 0, 0, 0.85);
    }

    /* Ambient glows (blue + rose) */
    .ai-mercedes-dashboard::before,
    .ai-mercedes-dashboard::after {
        content: "";
        position: absolute;
        width: 360px;
        height: 360px;
        border-radius: 50%;
        filter: blur(40px);
        opacity: 0.65;
        pointer-events: none;
    }
    .ai-mercedes-dashboard::before {
        inset: -15% auto auto -10%;
        background: radial-gradient(circle, rgba(0, 195, 255, 0.28), transparent 70%);
    }
    .ai-mercedes-dashboard::after {
        inset: auto -18% -30% auto;
        background: radial-gradient(circle, rgba(255, 90, 150, 0.3), transparent 70%);
    }

    /* Title */
    .ai-mercedes-title {
        margin: 0;
        font-size: clamp(1.7rem, 4vw, 2.6rem);
        font-weight: 300;
        letter-spacing: 0.2rem;
        text-transform: uppercase;
        color: #dce4f7;
        text-shadow: 0 0 18px rgba(74, 163, 255, 0.5);
        position: relative;
        z-index: 2;
    }

    /* Gauge grid */
    .dashboard-grid {
        margin-top: 40px !important;
        padding-top: 40px;
        display: flex;
        justify-content: center;
        gap: clamp(1.8rem, 4vw, 3.8rem);
        flex-wrap: wrap;
        position: relative;
        z-index: 2;
        overflow: visible !important;
    }

    /* GAUGE BODY — pixel-perfect */
    .ai-mercedes-gauge {
        width: 300px;
        height: 300px;
        border-radius: 50%;
        position: relative;
        background: rgba(12, 16, 24, 0.55);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        padding-top: 12px;

        box-shadow:
            inset 0 0 32px rgba(255,255,255,0.06),
            inset 0 0 14px rgba(255,255,255,0.03),
            0 0 42px rgba(0,160,255,0.35),
            0 0 95px rgba(0,0,0,0.85);

        display: flex;
        justify-content: center;
        align-items: center;
        overflow: visible;
    }

    .dashboard-grid > article,
    .dashboard-grid > div,
    .dashboard-grid > * {
        min-height: 340px !important;
        overflow: visible !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .ai-mercedes-gauge::before {
        content: "";
        position: absolute;
        inset: 12%;
        border-radius: 50%;
        background:
            repeating-conic-gradient(
                from 180deg,
                rgba(255,255,255,0.25) 0deg 2deg,
                transparent 2deg 12deg
            );
        mask: radial-gradient(circle, transparent 63%, black 66%);
        opacity: 0.5;
        filter: drop-shadow(0 0 12px rgba(0,0,0,0.7));
        pointer-events: none;
    }
    .ai-mercedes-gauge::after {
        content: "";
        position: absolute;
        inset: 18%;
        border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.22), rgba(0,0,0,0) 55%);
        opacity: 0.4;
        pointer-events: none;
    }

    /* ARC — pixel perfect thickness + curvature */
    .ai-mercedes-gauge .arc {
        position: absolute;
        width: 92%;
        height: 92%;
        top: 6%;
        left: 4%;
        border-radius: 50%;
        clip-path: polygon(0 0, 100% 0, 100% 62%, 0 62%);
        filter: blur(.6px) drop-shadow(0 0 48px rgba(0,0,0,0.65));
        opacity: 0.98;
    }

    /* VALUE TEXT — exact glow & weight */
    .ai-mercedes-gauge .value {
        font-size: clamp(2.5rem, 5.6vw, 3.5rem);
        font-weight: 650;
        letter-spacing: -0.5px;
        margin: 10px 0 0;
        text-shadow:
            0 0 14px rgba(255,255,255,0.55),
            0 0 32px rgba(255,255,255,0.25),
            0 0 55px rgba(255,255,255,0.22);
    }

    /* UNIT TEXT */
    .ai-mercedes-gauge .unit {
        margin-top: -6px;
        font-size: 1rem;
        opacity: 0.68;
        letter-spacing: 0.14rem;
    }

    /* LABEL TEXT */
    .ai-mercedes-gauge .label {
        position: absolute;
        bottom: 18px;
        width: 80%;
        left: 10%;
        color: #d5d9e6;
        text-shadow:
            0 0 8px rgba(0,0,0,0.35),
            0 0 16px rgba(0,0,0,0.65);
    }
    .ai-mercedes-gauge .label-title {
        font-size: 0.95rem;
        font-weight: 600;
        letter-spacing: 0.08rem;
        text-transform: uppercase;
        opacity: 0.92;
    }
    .ai-mercedes-gauge .label-detail {
        font-size: 0.85rem;
        letter-spacing: 0.04rem;
        opacity: 0.78;
        margin-top: 0.2rem;
    }

    /* PERFORMANCE DOME — pixel perfect */
    .ai-mercedes-performance {
        margin: clamp(2rem, 4vw, 3.5rem) auto 0;
        width: min(520px, 90%);
        height: clamp(220px, 34vw, 270px);
        border-radius: 600px 600px 0 0;
        background: rgba(12,16,24,0.55);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);

        padding-top: clamp(2rem, 4vw, 3.5rem);
        position: relative;

        box-shadow:
            inset 0 0 42px rgba(255,255,255,0.06),
            0 0 55px rgba(0,150,255,0.32),
            0 0 120px rgba(0,0,0,0.9);

        overflow: hidden;
        z-index: 2;
    }

    /* PERFORMANCE ARC — AMG rainbow sweep */
    .ai-mercedes-performance .performance-arc {
        position: absolute;
        top: -15px;
        left: 0;
        width: 100%;
        height: 110%;
        border-radius: inherit;

        background: conic-gradient(
            from 180deg,
            rgba(255,0,120,0.92) 0deg,
            rgba(150,0,255,0.95) 90deg,
            rgba(0,110,255,0.95) 170deg,
            rgba(0,220,255,0.93) 260deg,
            rgba(0,255,180,0.90) 320deg
        );

        clip-path: polygon(0 0, 100% 0, 100% 70%, 0 70%);
        filter: blur(.4px) drop-shadow(0 0 68px rgba(0,150,255,0.4));
    }

    /* PERFORMANCE VALUE */
    .ai-mercedes-performance .performance-value {
        font-size: clamp(3rem, 6.4vw, 4.6rem);
        font-weight: 650;
        position: relative;
        z-index: 3;

        text-shadow:
            0 0 24px rgba(255,255,255,0.55),
            0 0 55px rgba(255,255,255,0.3),
            0 0 95px rgba(255,255,255,0.25);
    }

    .ai-mercedes-performance .performance-label {
        font-size: 1.2rem;
        opacity: 0.85;
        margin-top: 0.5rem;
        letter-spacing: 0.1rem;
        z-index: 3;
        position: relative;
        text-shadow: 0 0 16px rgba(255,255,255,0.2);
    }

    /* Final overrides */
    .ai-mercedes-performance {
        height: 240px !important;
        overflow: visible !important;
    }
    .gauge-ticks,
    .tick,
    .gauge-label,
    .gauge-number {
        display: none !important;
    }

</style>
"""

    # -----------------------------------------------------
    # RENDER GAUGES (with patched CSS)
    # -----------------------------------------------------
    gauge_markup: list[str] = []

    for metric in metrics:
        color = metric.get("color") or "rgba(0,255,224,0.95)"
        gradient = metric.get("gradient") or _arc_gradient(color, metric.get("percent", 0.7))
        glow = metric.get("glow") or color

        display_value, display_unit = _normalize_metric_value(metric.get("value"), metric.get("unit"))
        value_html = escape(display_value)

        unit_html = f'<div class="unit">{escape(display_unit)}</div>' if display_unit else ""

        label_text = escape(str(metric.get("label", "Metric")))
        delta = escape(str(metric.get("delta", "") or ""))
        context = escape(str(metric.get("context", "")).strip())

        detail_lines = [
            f'<div class="label-detail">{line}</div>'
            for line in (delta, context)
            if line and line.strip()
        ]
        details_html = "".join(detail_lines)

        gauge_markup.append(
            f"""
            <article class="ai-mercedes-gauge">
                <div class="arc" style="background:{gradient}; box-shadow:0 0 40px {glow};"></div>
                <div>
                    <div class="value">{value_html}</div>
                    {unit_html}
                </div>
                <div class="label">
                    <div class="label-title">{label_text}</div>
                    {details_html}
                </div>
            </article>
            """
        )

    # PERFORMANCE DOME
    perf_gradient = performance_gradient or (
        "conic-gradient(from 180deg, rgba(255,0,120,0.92) 0deg, "
        "rgba(150,0,255,0.95) 90deg, rgba(0,110,255,0.95) 170deg, "
        "rgba(0,220,255,0.93) 260deg, rgba(0,255,180,0.90) 320deg)"
    )

    perf_value, perf_suffix = _format_perf_value(performance_value)
    perf_label = escape(str(performance_label or "AI Agent Performance"))

    # -----------------------------------------------------
    # FINAL RENDER
    # -----------------------------------------------------
    html_block = f"""
        <div class="ai-mercedes-shell">
            <section class="ai-mercedes-dashboard">
                <h2 class="ai-mercedes-title">{escape(headline)}</h2>

                <div class="dashboard-grid">
                    {''.join(gauge_markup)}
                </div>

                <article class="ai-mercedes-performance">
                    <div class="performance-arc" style="background:{perf_gradient};"></div>
                    <div class="performance-value">
                        {escape(perf_value)}<span>{escape(perf_suffix)}</span>
                    </div>
                    <div class="performance-label">{perf_label}</div>
                </article>

            </section>
        </div>
    """

    if "<section" not in html_block:
        _logger.error(
            "Telemetry HTML missing <section> wrapper; dashboard will not render properly."
        )

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
{styles_block}
</head>
<body>
{html_block}
</body>
</html>
"""

    gauges = max(1, len(metrics))
    rows = math.ceil(gauges / 3)
    base_height = 900  # tuned to avoid iframe scrolling with one row
    row_extra = 260
    component_height = base_height + max(0, rows - 1) * row_extra

    try:
        components.html(
            full_html,
            height=component_height,
            scrolling=False,
        )
        _logger.info(
            "Rendered telemetry dashboard headline=%s height=%s", headline, component_height
        )
    except Exception as exc:  # pragma: no cover
        _logger.exception(
            "Failed to render telemetry dashboard headline=%s", headline
        )
        st.error(
            f"Telemetry dashboard failed to render for '{headline}'. "
            f"Check {_LOG_PATH} for details."
        )
        return

    _dump_debug_html(headline, full_html)
