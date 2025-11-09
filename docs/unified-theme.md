## Unified Theme Management

A single macOS‑style dark/light system keeps all Streamlit agents visually aligned. This note explains the structure, runtime flow, and how to extend or override the shared palette.

---

### 1. File Layout

| Path | Responsibility |
| --- | --- |
| `services/ui/theme_manager.py` | Source of truth for palettes, CSS injection, and helpers (`init_theme`, `apply_theme`, `render_theme_toggle`, `get_palette`, etc.). |
| `services/ui/app.py` | Calls `init_theme()` when the user navigates away from the landing page and renders the global navbar toggle. |
| `services/ui/pages/asset_appraisal.py` | Invokes `apply_theme()` on load, exposes the toggle in-page, and layers extra CSS using `get_palette()`. |
| `services/ui/pages/credit_appraisal.py` | Same pattern as asset: shared helper + per-agent styling via the palette. |
| `services/ui/pages/anti_fraud_kyc.py` | Imports the manager, wraps `_apply_theme(get_theme())`, and reuses the toggle on both login and main screens. |
| `services/ui/utils/style.py` | Legacy utility updated to delegate to `theme_manager`, so older imports get the unified experience; also stores the historical CSS block. |

> Legacy CSS blocks remain at the bottom of the asset/credit files (`LEGACY_*_THEME_SNIPPET`) and in `services/ui/utils/style.py` (`LEGACY_STYLE_THEME_CSS`) so you can bring them back if desired.

---

### 2. Runtime Flow

1. **Session defaults** – `ensure_theme()` makes sure `st.session_state["ui_theme"]` (and legacy `["theme"]`) exist; default is `"dark"`.
2. **CSS injection** – `apply_theme()` grabs the palette and injects the base CSS (background, typography, tables, inputs, etc.) into Streamlit.
3. **User toggles** – `render_theme_toggle()` displays a Streamlit toggle tied to `ui_theme`. When flipped, it updates state, reapplies CSS, and reruns the app.
4. **Page hooks** – Each agent imports the helpers (`apply_theme`, `render_theme_toggle`, optionally `get_palette`) to remain in sync while still supporting agent-specific accents.
5. **Landing page exception** – `app.py` only calls `init_theme()` when `stage != "landing"`, so the landing page keeps its bespoke styling.

---

### 3. Adding the Theme to a New Page

```python
import streamlit as st
from services.ui.theme_manager import apply_theme, render_theme_toggle, get_palette

st.set_page_config(page_title="My Agent", layout="wide")
apply_theme()  # ensures CSS + session keys

pal = get_palette()  # optional per-page accents

with st.sidebar:
    render_theme_toggle(key="my_agent_theme_toggle")
```

If your page has its own navbar, place `render_theme_toggle()` there instead (give it a unique `key`). Use `pal["accent"]`, `pal["card"]`, etc., for any extra HTML/CSS you render manually.

---

### 4. Custom / Legacy Themes

- The previous macOS blue theme is stored in each agent file and in `services/ui/utils/style.py`. To restore it, import the snippet, call its helper, and skip `apply_theme()`.
- Because the legacy versions are just strings/constants, they do not affect runtime unless you explicitly use them.

---

### 5. Troubleshooting

| Issue | Fix |
| --- | --- |
| Toggle causes infinite reruns | Ensure you render it once per page and use unique `key` values if multiple toggles exist. |
| Custom CSS shows stale colors | Call `get_palette()` after `apply_theme()` and reference those colors, rather than hard-coding hex codes. |
| Landing page suddenly dark | Confirm `app.py` still guards `init_theme()` with `if st.session_state.stage != "landing"`. |

Questions or improvements? Open an issue or mention it in review before editing `services/ui/theme_manager.py`, since it drives every agent UI. 

---

### Mercedes-Benz Style AI Dashboard (HTML + CSS)

The snippet below is a copy/paste-ready static dashboard that recreates the Mercedes-Benz cockpit aesthetic with three neon gauges plus the half-dome performance meter. Drop it into any static host (or Streamlit `st.components.v1.html`) to render the exact experience described in the brief.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI Agent Health & Telemetry</title>
  <style>
    :root {
      color-scheme: dark;
    }
    *,
    *::before,
    *::after {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Montserrat", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      background: radial-gradient(circle at 25% 20%, #0b1324, #05070c 70%);
      color: #f3f8ff;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: clamp(1.5rem, 3vw, 3.5rem);
      letter-spacing: 0.06em;
    }
    body::before {
      content: "";
      position: fixed;
      inset: auto auto 8% 10%;
      width: min(32vw, 420px);
      aspect-ratio: 1;
      background: radial-gradient(circle, rgba(0, 168, 255, 0.32), transparent 70%);
      filter: blur(30px);
      opacity: 0.6;
      pointer-events: none;
      z-index: 0;
    }
    p {
      margin: 0;
    }
    .mb-dashboard {
      position: relative;
      width: min(1200px, 100%);
      display: flex;
      flex-direction: column;
      gap: clamp(1.7rem, 3vw, 3rem);
      z-index: 1;
    }
    .mb-dashboard h1 {
      margin: 0;
      font-size: clamp(1.6rem, 4vw, 2.7rem);
      letter-spacing: 0.3rem;
      text-transform: uppercase;
      text-align: center;
      text-shadow: 0 0 30px rgba(0, 208, 255, 0.45);
    }
    .gauge-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: clamp(1rem, 2.5vw, 2.2rem);
      justify-items: center;
    }
    .gauge {
      --glass: rgba(8, 13, 24, 0.65);
      width: 100%;
      display: flex;
      justify-content: center;
    }
    .gauge-arc {
      position: relative;
      width: clamp(200px, 26vw, 260px);
      aspect-ratio: 1;
      border-radius: 50%;
      padding: 20px;
      background:
        radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.35), rgba(8, 10, 17, 0.65) 52%, rgba(0, 0, 0, 0.9) 70%),
        linear-gradient(145deg, rgba(7, 9, 16, 0.9), rgba(2, 3, 6, 0.95));
      border: 1px solid rgba(255, 255, 255, 0.04);
      box-shadow:
        inset 0 0 25px rgba(0, 0, 0, 0.7),
        0 0 40px var(--glow, rgba(0, 255, 240, 0.35));
      overflow: hidden;
    }
    .gauge-arc::before,
    .gauge-arc::after {
      content: "";
      position: absolute;
      inset: 2px;
      border-radius: 50%;
      pointer-events: none;
    }
    .gauge-arc::before {
      inset: -10px;
      background: var(--arc-gradient);
      filter: drop-shadow(0 0 25px var(--glow, rgba(0, 255, 240, 0.4)));
      mask: radial-gradient(circle, transparent 63%, black 65%);
      -webkit-mask: radial-gradient(circle, transparent 63%, black 65%);
    }
    .gauge-arc::after {
      background: radial-gradient(circle, rgba(255, 255, 255, 0.18), transparent 65%);
      filter: blur(35px);
      opacity: 0.4;
    }
    .gauge-glass {
      position: absolute;
      inset: 16%;
      border-radius: 50%;
      background: rgba(6, 10, 18, 0.72);
      border: 1px solid rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(22px) saturate(160%);
      -webkit-backdrop-filter: blur(22px) saturate(160%);
      display: grid;
      place-items: center;
      text-align: center;
      padding: 1.5rem;
    }
    .value {
      font-size: clamp(2rem, 4vw, 3rem);
      font-weight: 600;
      letter-spacing: 0.2rem;
      text-transform: uppercase;
      text-shadow: 0 0 22px currentColor;
    }
    .value span {
      display: block;
      font-size: 0.55em;
      letter-spacing: 0.5rem;
      color: #a6bedf;
    }
    .label {
      font-size: 0.8rem;
      letter-spacing: 0.4rem;
      text-transform: uppercase;
      margin-top: 1rem;
      color: #93a7c9;
    }
    .gauge-teal {
      --arc-gradient: conic-gradient(from 230deg, transparent 0deg 35deg, rgba(0, 255, 224, 0.25) 35deg 60deg, rgba(0, 255, 224, 0.95) 60deg 280deg, transparent 282deg 360deg);
      --glow: rgba(0, 255, 224, 0.45);
    }
    .gauge-blue {
      --arc-gradient: conic-gradient(from 220deg, transparent 0deg 25deg, rgba(64, 162, 255, 0.3) 25deg 80deg, rgba(64, 162, 255, 0.95) 80deg 300deg, transparent 302deg 360deg);
      --glow: rgba(64, 162, 255, 0.5);
    }
    .gauge-red {
      --arc-gradient: conic-gradient(from 240deg, transparent 0deg 50deg, rgba(255, 109, 78, 0.4) 50deg 100deg, rgba(255, 109, 78, 0.95) 100deg 320deg, transparent 322deg 360deg);
      --glow: rgba(255, 109, 78, 0.45);
    }
    .performance {
      position: relative;
      border-radius: 28px;
      padding: clamp(1.5rem, 3vw, 2.8rem);
      background: rgba(6, 10, 18, 0.65);
      border: 1px solid rgba(255, 255, 255, 0.04);
      box-shadow: 0 35px 80px rgba(0, 0, 0, 0.7);
      overflow: hidden;
    }
    .performance::after {
      content: "";
      position: absolute;
      inset: 15% auto auto 55%;
      width: 340px;
      height: 340px;
      background: radial-gradient(circle, rgba(255, 102, 196, 0.3), transparent 65%);
      filter: blur(40px);
      opacity: 0.6;
      pointer-events: none;
    }
    .performance-arc {
      position: relative;
      width: 100%;
      aspect-ratio: 2 / 1;
      border-radius: 100% 100% 0 0 / 100% 100% 0 0;
      background: linear-gradient(145deg, rgba(4, 6, 12, 0.95), rgba(5, 9, 16, 0.7));
      border: 1px solid rgba(255, 255, 255, 0.03);
      overflow: hidden;
      padding: 1.5rem;
    }
    .performance-arc::before {
      content: "";
      position: absolute;
      inset: -12% -5% 25% -5%;
      border-radius: inherit;
      background: conic-gradient(from 180deg, #ff66c4 0deg, #c449ff 80deg, #5663ff 150deg, #00e0ff 225deg, #2affb3 300deg, transparent 330deg 360deg);
      filter: drop-shadow(0 0 40px rgba(255, 102, 196, 0.45));
      mask: radial-gradient(circle at 50% 110%, transparent 58%, black 60%);
      -webkit-mask: radial-gradient(circle at 50% 110%, transparent 58%, black 60%);
    }
    .performance-glass {
      position: absolute;
      inset: 25% 12% 0 12%;
      background: rgba(5, 9, 16, 0.75);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-bottom: none;
      border-radius: 50% 50% 0 0 / 45% 45% 0 0;
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
      display: grid;
      place-items: center;
      padding-block: clamp(2.5rem, 5vw, 4rem);
      text-align: center;
    }
    .performance .value {
      font-size: clamp(3rem, 8vw, 5rem);
      letter-spacing: 0.12em;
    }
    .performance .value span {
      display: inline;
      font-size: 0.6em;
      letter-spacing: 0.15em;
      color: #cfd9f2;
    }
    .performance .label {
      letter-spacing: 0.35rem;
      margin-top: 0.5rem;
      color: #98b6db;
    }
    @media (max-width: 768px) {
      .mb-dashboard h1 {
        letter-spacing: 0.2rem;
      }
      .performance-glass {
        inset: 28% 8% 0 8%;
      }
    }
    @media (max-width: 540px) {
      .value {
        letter-spacing: 0.12rem;
      }
      .value span {
        letter-spacing: 0.35rem;
      }
      .gauge-grid {
        gap: 1rem;
      }
    }
  </style>
</head>
<body>
  <section class="mb-dashboard">
    <h1>AI Agent Health & Telemetry</h1>
    <div class="gauge-grid">
      <article class="gauge gauge-teal">
        <div class="gauge-arc">
          <div class="gauge-glass">
            <p class="value">14 <span>apps</span></p>
            <p class="label">Apps in Review</p>
          </div>
        </div>
      </article>
      <article class="gauge gauge-blue">
        <div class="gauge-arc">
          <div class="gauge-glass">
            <p class="value">39 <span>min</span></p>
            <p class="label">Avg Decision Time</p>
          </div>
        </div>
      </article>
      <article class="gauge gauge-red">
        <div class="gauge-arc">
          <div class="gauge-glass">
            <p class="value">1 <span>flag</span></p>
            <p class="label">Compliance Flags</p>
          </div>
        </div>
      </article>
    </div>
    <article class="performance">
      <div class="performance-arc">
        <div class="performance-glass">
          <p class="value">92<span>%</span></p>
          <p class="label">AI Agent Performance</p>
        </div>
      </div>
    </article>
  </section>
</body>
</html>
```
