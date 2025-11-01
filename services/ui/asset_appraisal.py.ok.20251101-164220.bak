# services/ui/asset_appraisal.py
# ────────────────────────────────
# 🏦 Asset Appraisal Agent UI
# Built on same Streamlit framework as Credit Agent
# ────────────────────────────────
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import json
import io
import requests
import os

st.set_page_config(page_title="🏦 Asset Appraisal Agent", layout="wide")

st.title("🏦 AI Asset Appraisal Platform")
st.caption("Generate, inspect, and appraise assets using AI-driven valuation + human insight.")

# Tabs
tab_gen, tab_field, tab_ai, tab_review, tab_train, tab_feedback = st.tabs([
    "🏗 Synthetic Asset Generator",
    "🧾 Field Inspection & Data Validation",
    "🤖 Asset Valuation by AI Agent",
    "🧑‍⚖️ Human Review & Verification",
    "🔁 Training (Feedback → Retrain)",
    "💬 Feedback & Improvement"
])

# Base directories
BASE_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/ui")
RUNS_DIR = os.path.join(BASE_DIR, ".runs")
os.makedirs(RUNS_DIR, exist_ok=True)
API_URL = os.getenv("API_URL", "http://localhost:8090")

# ───────────────────────────────
# Utilities
MONEY_FIELDS_COMMON = {
    "base_value_hint", "market_value", "estimated_value", "requested_amount", "monthly_rent", "deposit_amount"
}

FX_TABLE = {
    # 1 unit of target currency in USD terms (approx; edit as you wish).
    # We’ll convert from USD-ish synthetic into target by dividing by usd_per_unit.
    "USD": 1.00,
    "EUR": 1.08,
    "GBP": 1.25,
    "JPY": 0.0067,
    "VND": 0.000039
}

def scale_currency(df: pd.DataFrame, currency_code: str) -> pd.DataFrame:
    """Scale money fields from implicit-USD to the chosen currency."""
    if currency_code not in FX_TABLE:
        return df
    usd_per_unit = FX_TABLE[currency_code]  # 1 currency unit equals this many USD
    factor = 1.0 / usd_per_unit            # convert USD-ish -> target units
    for col in df.columns:
        if col in MONEY_FIELDS_COMMON and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = (df[col] * factor).round(2)
    df["currency_code"] = currency_code
    return df

def csv_download(name: str, df: pd.DataFrame):
    return df.to_csv(index=False).encode("utf-8"), name, "text/csv"

# ───────────────────────────────
# 🏗 Synthetic Data Generator (type-aware + FX + auto-feed)
with tab_gen:
    st.subheader("🏗 Generate Synthetic Asset Dataset (type-aware)")

    # Controls
    c1, c2, c3, c4 = st.columns([1.1, 1, 1, 1])
    with c1:
        n = st.slider("Number of assets", 50, 5000, 400, step=50)
    with c2:
        currency = st.selectbox("Currency", list(FX_TABLE.keys()), index=0)
    with c3:
        seed = st.number_input("Random seed", 0, 10_000, 42, step=1)
    with c4:
        mix = st.multiselect(
            "Asset types",
            ["Apartment", "House", "Condo", "Shop", "Factory", "Land Plot", "Car", "Deposit"],
            default=["Apartment", "Condo", "House", "Land Plot", "Car"]
        )

    rng = np.random.default_rng(seed)

    # Small pools for coarse locations (no PII)
    cities = [
        ("US", "New York", 40.71, -74.01),
        ("US", "San Jose", 37.34, -121.89),
        ("UK", "London", 51.50, -0.12),
        ("FR", "Paris", 48.86, 2.35),
        ("DE", "Berlin", 52.52, 13.41),
        ("VN", "Ho Chi Minh", 10.78, 106.70),
        ("VN", "Hanoi", 21.02, 105.84),
        ("JP", "Tokyo", 35.68, 139.69),
    ]

    def choose_city(k: int):
        c = cities[k % len(cities)]
        jlat = c[2] + rng.normal(0, 0.02)
        jlon = c[3] + rng.normal(0, 0.02)
        return c[0], c[1], round(jlat, 5), round(jlon, 5)

    def quality_from_location(q):
        return {"A": 0.90, "B": 0.75, "C": 0.55, "D": 0.40}[q]

    def draw_location_quality():
        return rng.choice(["A", "B", "C", "D"], p=[0.2, 0.35, 0.30, 0.15])

    def base_value_by_type(t):
        priors = {
            "Apartment": (80_000, 250_000),
            "House": (120_000, 500_000),
            "Condo": (90_000, 300_000),
            "Shop": (150_000, 800_000),
            "Factory": (300_000, 2_000_000),
            "Land Plot": (30_000, 400_000),
            "Car": (5_000, 70_000),
            "Deposit": (10_000, 300_000),
        }
        lo, hi = priors.get(t, (50_000, 250_000))
        return rng.integers(lo, hi)

    def depreciation_for_real_estate(age):
        return np.clip(1.0 - 0.012 * age + rng.normal(0, 0.02), 0.65, 1.05)

    def depreciation_for_car(year):
        age = max(0, datetime.datetime.now().year - year)
        return np.clip(0.85 ** (age / 2.0) + rng.normal(0, 0.03), 0.25, 1.05)

    def make_vehicle_name():
        makes = ["Toyota", "Honda", "BMW", "Mercedes", "Ford", "Hyundai", "Kia", "Mazda"]
        models = ["Civic", "Corolla", "CX-5", "3 Series", "C-Class", "F-150", "Elantra", "Sportage"]
        return f"{rng.choice(makes)} {rng.choice(models)}"

    rows = []
    chosen_types = mix or ["Apartment"]

    for i in range(1, n + 1):
        t = rng.choice(chosen_types)
        country, city, lat, lon = choose_city(i)
        loc_q = draw_location_quality()

        # Common
        row = {
            "asset_id": f"A-{i:06d}",
            "asset_type": t,
            "country": country,
            "city": city,
            "geo_lat": lat,
            "geo_lon": lon,
            "location_quality": loc_q,
            "currency_code": "USD",  # start as USD-ish; we scale later
            "inspection_needed": bool(rng.integers(0, 2)),
            "legal_status": rng.choice(["Clean", "Disputed", "Pending Verification"], p=[0.84, 0.08, 0.08]),
            "ownership_verified": bool(rng.integers(0, 2)),
            "lien_count": int(rng.choice([0, 0, 0, 1, 1, 2])),
            "registry_id": f"REG-{rng.integers(10**8, 10**9-1)}",
            "valuation_date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "age_years": int(rng.integers(0, 60)),
            "base_value_hint": int(base_value_by_type(t)),
        }

        # Type-specific
        if t in {"Apartment", "House", "Condo", "Shop", "Factory"}:
            row.update({
                "year_built": int(datetime.datetime.now().year - row["age_years"]),
                "floor": int(rng.integers(1, 25)) if t in {"Apartment", "Condo"} else 0,
                "floors_total": int(rng.integers(1, 40)) if t in {"Apartment", "Condo"} else int(rng.integers(1, 6)),
                "bedrooms": int(rng.integers(0, 6)) if t in {"Apartment", "House", "Condo"} else 0,
                "bathrooms": int(rng.integers(1, 4)) if t in {"Apartment", "House", "Condo"} else int(rng.integers(1, 3)),
                "parking_slots": int(rng.integers(0, 3)),
                "area_m2": int(rng.integers(25, 400) if t in {"Apartment", "Condo"} else rng.integers(60, 3000)),
                "land_area_m2": int(rng.integers(0, 1000) if t in {"Apartment", "Condo"} else rng.integers(80, 5000)),
                "frontage_m": float(np.round(rng.uniform(4, 30), 2)),
                "road_width_m": float(np.round(rng.uniform(3, 30), 2)),
                "zoning": rng.choice(["Residential", "Commercial", "Industrial", "Mixed"]),
                "condition_grade": rng.choice(["A", "B", "C", "D", "E"], p=[0.10, 0.35, 0.35, 0.15, 0.05]),
                "occupancy": rng.choice(["owner", "tenant", "vacant"], p=[0.45, 0.40, 0.15]),
                "monthly_rent": int(rng.integers(0, 6000)),
                "flood_risk_zone": int(rng.choice([0, 0, 0, 1])),
                "school_dist_km": float(np.round(abs(rng.normal(2.0, 1.0)), 2)),
                "metro_dist_km": float(np.round(abs(rng.normal(1.2, 0.8)), 2)),
            })
            dep = depreciation_for_real_estate(row["age_years"])
            base = row["base_value_hint"] * quality_from_location(loc_q)
            market_value = base * dep * rng.uniform(0.9, 1.1)

        elif t == "Land Plot":
            row.update({
                "land_area_m2": int(rng.integers(60, 8000)),
                "frontage_m": float(np.round(rng.uniform(5, 60), 2)),
                "zoning": rng.choice(["Residential", "Commercial", "Industrial", "Agricultural"]),
                "shape_quality": rng.choice(["A", "B", "C", "D"], p=[0.25, 0.45, 0.20, 0.10]),
                "road_access": bool(rng.integers(0, 2)),
            })
            shape_factor = {"A": 1.0, "B": 0.95, "C": 0.9, "D": 0.85}[row["shape_quality"]]
            base = row["base_value_hint"] * (row["land_area_m2"] / 300.0) * shape_factor * quality_from_location(loc_q)
            market_value = base * rng.uniform(0.8, 1.2)

        elif t == "Car":
            veh_year = int(rng.integers(datetime.datetime.now().year - 15, datetime.datetime.now().year + 1))
            row.update({
                "year_make_model": f"{veh_year} {make_vehicle_name()}",
                "vehicle_year": veh_year,
                "odometer_km": int(rng.integers(5_000, 250_000)),
                "engine_cc": int(rng.integers(980, 4500)),
                "accident_history": int(rng.choice([0, 0, 1], p=[0.7, 0.15, 0.15])),
                "service_records_count": int(rng.integers(0, 15)),
                "ownership_count": int(rng.integers(1, 4)),
            })
            dep = depreciation_for_car(veh_year)
            accident_pen = 0.90 if row["accident_history"] else 1.0
            base = row["base_value_hint"] * dep * accident_pen
            market_value = base * rng.uniform(0.9, 1.1)

        elif t == "Deposit":
            amt = int(rng.integers(10_000, 500_000))
            row.update({
                "deposit_amount": amt,
                "interest_rate_apy": float(np.round(rng.uniform(0.5, 6.0), 2)),
                "maturity_months": int(rng.integers(3, 36)),
            })
            market_value = amt  # cash-backed

        else:
            market_value = row["base_value_hint"] * rng.uniform(0.85, 1.15)

        # Derived & risk
        requested_amount = int(max(1_000, market_value * rng.uniform(0.3, 0.8)))
        estimated_value = float(np.round(market_value * rng.normal(1.0, 0.05), 2))
        ltv = float(np.round(requested_amount / max(estimated_value, 1e-6), 4))
        ccr = float(np.round(estimated_value / max(requested_amount, 1e-6), 4))

        row.update({
            "market_value": float(np.round(market_value, 2)),
            "estimated_value": estimated_value,
            "requested_amount": requested_amount,
            "LTV": ltv,
            "CCR": ccr,
            "quality_score": float(np.round(
                0.5 * quality_from_location(loc_q) +
                0.2 * (1.0 - min(row.get("flood_risk_zone", 0), 1) * 0.5) +
                0.3 * rng.uniform(0.6, 1.0), 3)),
        })

        rows.append(row)

    df_raw_usd = pd.DataFrame(rows)
    df = scale_currency(df_raw_usd.copy(), currency)

    # Nice ordering
    preferred = [
        "asset_id","asset_type","country","city","geo_lat","geo_lon","location_quality","currency_code",
        "valuation_date","age_years","base_value_hint",
        "year_built","floor","floors_total","bedrooms","bathrooms","parking_slots",
        "area_m2","land_area_m2","frontage_m","road_width_m","zoning","condition_grade","occupancy",
        "monthly_rent","flood_risk_zone","school_dist_km","metro_dist_km",
        "shape_quality","road_access",
        "year_make_model","vehicle_year","odometer_km","engine_cc","accident_history",
        "service_records_count","ownership_count",
        "deposit_amount","interest_rate_apy","maturity_months",
        "inspection_needed","legal_status","ownership_verified","lien_count","registry_id",
        "requested_amount","market_value","estimated_value","LTV","CCR","quality_score"
    ]
    df = df[[c for c in preferred if c in df.columns]]

    st.dataframe(df.head(15), use_container_width=True)

    # Persist to session so AI tab can consume without re-upload
    st.session_state["asset_df_input"] = df.copy()

    # Save + download
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_name = f"synthetic_assets_{ts}_{currency}.csv"
    csv_bytes, dl_name, dl_mime = csv_download(out_name, df)
    st.download_button("⬇️ Download Synthetic Asset CSV", csv_bytes, dl_name, dl_mime)

    # Also store in .runs/
    try:
        run_path = os.path.join(RUNS_DIR, out_name)
        with open(run_path, "wb") as f:
            f.write(csv_bytes)
        st.caption(f"Saved to: {run_path}")
    except Exception as e:
        st.caption(f"Could not save to runs dir: {e}")

    # One-click run from generator
    if st.button("🚀 Run AI valuation now (use generated dataset)"):
        try:
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            files = {"file": ("assets.csv", buf.getvalue().encode("utf-8"), "text/csv")}
            r = requests.post(f"{API_URL}/v1/agents/asset_appraisal/run", files=files, timeout=120)
            if r.ok:
                st.success("✅ AI Valuation completed!")
                res = r.json()
                st.json(res.get("summary", {}))
                st.session_state["last_asset_valuation"] = res
            else:
                st.error(f"Error: {r.status_code} — {r.text}")
        except Exception as e:
            st.exception(e)

    st.divider()
    st.markdown("### 📋 Field Intake Template (for inspectors)")
    st.caption("Give this CSV to field teams. It matches the minimal columns your backend expects; add extras as needed.")
    template_cols = [
        "asset_id","asset_type","country","city","geo_lat","geo_lon",
        "location_quality","currency_code","valuation_date",
        "age_years","year_built","area_m2","land_area_m2","zoning",
        "condition_grade","occupancy","monthly_rent",
        "legal_status","ownership_verified","lien_count","registry_id",
        "requested_amount"
    ]
    example_row = {
        "asset_id": "A-EX0001",
        "asset_type": "Apartment",
        "country": "VN",
        "city": "Ho Chi Minh",
        "geo_lat": 10.78,
        "geo_lon": 106.70,
        "location_quality": "B",
        "currency_code": currency,
        "valuation_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "age_years": 12,
        "year_built": datetime.datetime.now().year - 12,
        "area_m2": 76,
        "land_area_m2": 0,
        "zoning": "Residential",
        "condition_grade": "B",
        "occupancy": "tenant",
        "monthly_rent": 800,
        "legal_status": "Clean",
        "ownership_verified": True,
        "lien_count": 0,
        "registry_id": "REG-123456789",
        "requested_amount": 120000,
    }
    intake_template_df = pd.DataFrame([example_row], columns=template_cols)
    st.dataframe(intake_template_df, use_container_width=True)
    t_bytes, t_name, t_mime = csv_download("asset_field_intake_template.csv", intake_template_df)
    st.download_button("⬇️ Download Intake Template CSV", t_bytes, t_name, t_mime)

# ───────────────────────────────
# 🧾 Field Inspection Upload
with tab_field:
    st.subheader("🧾 Upload Field Inspection Data")
    st.markdown("Field inspectors submit verified data or notes from local authorities.")
    uploaded = st.file_uploader("Upload Inspection CSV", type=["csv"])
    if uploaded:
        try:
            insp_df = pd.read_csv(uploaded)
            st.success(f"Loaded {len(insp_df)} inspection records.")
            st.dataframe(insp_df.head(10), use_container_width=True)
            st.session_state["inspection_df"] = insp_df
            # Also expose as current input
            st.session_state["asset_df_input"] = insp_df.copy()
        except Exception as e:
            st.error(f"Error reading file: {e}")

# ───────────────────────────────
# 🤖 AI Valuation
with tab_ai:
    st.subheader("🤖 Asset Appraisal by AI Agent")
    # Prefer last generated dataset if available
    data_options = []
    if "asset_df_input" in st.session_state:
        data_options.append("Last Generated (from Generator)")
    data_options.extend(["Synthetic Data (fresh generate above)", "Field Inspection Upload"])
    data_source = st.selectbox("Data source", data_options)

    if st.button("🚀 Run AI Valuation", use_container_width=True):
        try:
            if data_source == "Last Generated (from Generator)" and "asset_df_input" in st.session_state:
                df_input = st.session_state["asset_df_input"]
            elif data_source == "Field Inspection Upload":
                df_input = st.session_state.get("inspection_df")
                if df_input is None:
                    st.error("No field inspection data found. Upload it in the previous tab.")
                    st.stop()
            else:
                # fallback: generate a tiny synthetic sample if nothing else is present
                df_input = st.session_state.get("asset_df_input")
                if df_input is None:
                    st.error("No generated dataset in session. Generate in the first tab.")
                    st.stop()

            buf = io.StringIO()
            df_input.to_csv(buf, index=False)
            files = {"file": ("assets.csv", buf.getvalue().encode("utf-8"), "text/csv")}
            r = requests.post(f"{API_URL}/v1/agents/asset_appraisal/run", files=files, timeout=120)
            if r.ok:
                res = r.json()
                st.success("✅ AI Valuation completed!")
                st.json(res.get("summary", {}))
                st.session_state["last_asset_valuation"] = res
            else:
                st.error(f"Error: {r.status_code} — {r.text}")
        except Exception as e:
            st.exception(e)

# ───────────────────────────────
# 🧑‍⚖️ Human Review
with tab_review:
    st.subheader("🧑‍⚖️ Human Review — Adjust Valuations")
    review_upload = st.file_uploader("Upload AI outputs CSV", type=["csv"], key="asset_review_csv")
    if review_upload:
        df_rev = pd.read_csv(review_upload)
        if "predicted_value" in df_rev.columns:
            df_rev["human_adjusted_value"] = df_rev["predicted_value"] * np.random.uniform(0.95, 1.05, len(df_rev))
        st.dataframe(df_rev.head(10), use_container_width=True)
        bytes_out = df_rev.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export Reviewed CSV", bytes_out, "reviewed_assets.csv")

# ───────────────────────────────
# 🔁 Training
with tab_train:
    st.subheader("🔁 Retrain Asset Model using Reviewed Data")
    train_up = st.file_uploader("Upload Reviewed CSV", type=["csv"], key="asset_train_csv")
    if train_up:
        try:
            df_train = pd.read_csv(train_up)
            st.write("Training with sample:", df_train.head(3))
            r = requests.post(f"{API_URL}/v1/training/train_asset", timeout=90)
            if r.ok:
                st.success("✅ Retraining triggered!")
            else:
                st.error(f"Error: {r.status_code} — {r.text}")
        except Exception as e:
            st.error(f"Training failed: {e}")

# ───────────────────────────────
# 💬 Feedback
with tab_feedback:
    st.subheader("💬 Feedback & Feature Requests")
    idea = st.text_area("What should we improve?")
    if st.button("📨 Submit"):
        st.success("Thank you for your feedback!")
