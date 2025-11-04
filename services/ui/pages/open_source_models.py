import os, io, subprocess, pandas as pd, streamlit as st
from datasets import load_dataset

RUNS_DIR = os.path.join(os.getcwd(), "services", "ui", ".tmp_runs")
os.makedirs(RUNS_DIR, exist_ok=True)

def render_open_source_tab():
    st.subheader("🌍 Import Public Datasets (Kaggle / Hugging Face / OpenML / Portals)")

    src = st.radio("Select source", ["Kaggle (API)", "Hugging Face Datasets", "OpenML"], horizontal=True)
    keyword = st.text_input("🔎 Search keywords", placeholder="e.g. house prices real estate valuation")

    outdir = os.path.join(RUNS_DIR, "kaggle")
    os.makedirs(outdir, exist_ok=True)

    # -----------------------------
    # KAGGLE SEARCH
    # -----------------------------
    if src == "Kaggle (API)" and st.button("🔍 Search dataset", use_container_width=True):
        try:
            cmd = ["kaggle", "datasets", "list", "-s", keyword, "--csv"]
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            df = pd.read_csv(io.StringIO(result.stdout))
            st.session_state["kaggle_results"] = df
            st.success("✅ Kaggle API results shown.")
        except Exception as e:
            st.error(f"Kaggle CLI failed: {e}")
            return

    # -----------------------------
    # SHOW RESULTS + IMPORT UI
    # -----------------------------
    df = st.session_state.get("kaggle_results")
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True, height=400)

        # We use an expander to hold download options persistently
        with st.expander("⬇️ Import Selected Dataset", expanded=True):
            selected = st.selectbox(
                "Select a Kaggle dataset to download", 
                df["ref"].tolist(),
                key="selected_kaggle_dataset"
            )
            if st.button("📥 Download & Import Selected", use_container_width=True):
                try:
                    st.info(f"Downloading {selected} … please wait ⏳")
                    cmd = ["kaggle", "datasets", "download", "-d", selected, "-p", outdir, "--unzip"]
                    subprocess.run(cmd, check=True)

                    csvs = [f for f in os.listdir(outdir) if f.endswith(".csv")]
                    if csvs:
                        csv_path = os.path.join(outdir, csvs[0])
                        df_loaded = pd.read_csv(csv_path)
                        st.session_state["asset_intake_df"] = df_loaded
                        st.session_state["asset_intake_path"] = csv_path
                        st.session_state["asset_stage"] = "asset_flow"

                        st.success(f"✅ Imported {csvs[0]} ({len(df_loaded)} rows)")
                        st.dataframe(df_loaded.head())
                        st.toast("🚀 Moving to Normalize & Combine stage…", icon="✅")
                        st.rerun()
                    else:
                        st.warning("⚠️ No CSV file found after download.")
                except Exception as e:
                    st.error(f"❌ Download failed: {e}")

    # -----------------------------
    # HUGGING FACE FALLBACK
    # -----------------------------
    elif src == "Hugging Face Datasets" and st.button("🤗 Load from Hugging Face", use_container_width=True):
        try:
            ds = load_dataset("uciml/real-estate-valuation")
            df = ds["train"].to_pandas()
            st.session_state["asset_intake_df"] = df
            st.dataframe(df.head())
            st.toast("🤗 Hugging Face dataset loaded!", icon="🎯")
            st.session_state["asset_stage"] = "asset_flow"
            st.rerun()
        except Exception as e:
            st.error(f"Hugging Face load failed: {e}")
