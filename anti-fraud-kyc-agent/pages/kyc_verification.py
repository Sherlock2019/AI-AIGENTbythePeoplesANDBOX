"""KYC verification tab for Anti-Fraud agent."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


def _ensure_risk(df: pd.DataFrame) -> pd.Series:
    if "risk_score" in df.columns:
        return pd.to_numeric(df["risk_score"], errors="coerce").fillna(25)
    return pd.Series(np.clip(np.random.normal(35, 20, len(df)), 0, 100), index=df.index)


def render_kyc_tab(ss, runs_dir: Path) -> None:
    runs_dir = Path(runs_dir)
    st.header("C) KYC Verification")
    st.caption("Automate IDV, sanctions screening, and PEP detection. Output flows directly to fraud scoring.")

    source_df = ss.get("afk_anonymized_df")
    if not isinstance(source_df, pd.DataFrame) or source_df.empty:
        st.info("Run Stage B (Anonymization) first to populate KYC checks.")
        return

    df = source_df.copy().reset_index(drop=True)
    risk = _ensure_risk(df)
    rng = np.random.default_rng(7)

    df["id_doc_verified"] = np.where(risk > 70, rng.random(len(df)) > 0.2, True)
    df["selfie_match"] = rng.random(len(df)) > 0.05
    df["address_verified"] = rng.random(len(df)) > 0.1
    df["sanctions_hit"] = np.where(risk > 80, rng.random(len(df)) < 0.15, rng.random(len(df)) < 0.02)
    df["pep_flag"] = np.where(risk > 85, True, False)

    df["kyc_status"] = np.where(
        df["sanctions_hit"] | (~df["id_doc_verified"]) | (~df["address_verified"]),
        "Review",
        "Auto-Clear",
    )

    ss["afk_kyc_df"] = df
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "stage_c_kyc.csv").write_bytes(df.to_csv(index=False).encode("utf-8"))

    col1, col2, col3 = st.columns(3)
    col1.metric("Pending cases", len(df))
    col2.metric("Auto-cleared", int((df["kyc_status"] == "Auto-Clear").sum()))
    col3.metric("Requires review", int((df["kyc_status"] == "Review").sum()))

    with st.expander("🔍 Sample KYC outputs", expanded=True):
        st.dataframe(
            df[
                [
                    "applicant_id",
                    "country",
                    "transaction_amount",
                    "risk_score",
                    "id_doc_verified",
                    "sanctions_hit",
                    "pep_flag",
                    "kyc_status",
                ]
            ].head(200),
            use_container_width=True,
        )

    st.download_button(
        "⬇️ Download KYC decisions",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="afk_kyc_results.csv",
        mime="text/csv",
    )
