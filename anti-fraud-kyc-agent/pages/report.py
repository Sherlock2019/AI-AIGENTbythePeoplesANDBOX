"""Reporting tab for Anti-Fraud agent."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


def render_report_tab(ss, runs_dir: Path) -> None:
    runs_dir = Path(runs_dir)
    st.header("H) Reports & Audit Trail")
    st.caption("Bundle all stage outputs for regulators, auditors, or downstream teams.")

    datasets = {
        "stage_a_intake": ss.get("afk_intake_df"),
        "stage_b_anonymized": ss.get("afk_anonymized_df"),
        "stage_c_kyc": ss.get("afk_kyc_df"),
        "stage_d_fraud": ss.get("afk_fraud_df"),
        "stage_f_review": ss.get("afk_review_df"),
    }

    fraud_df = datasets.get("stage_d_fraud")
    if isinstance(fraud_df, pd.DataFrame) and not fraud_df.empty:
        st.markdown("### 📊 Fraud summary dashboard")
        col1, col2, col3 = st.columns(3)
        col1.metric("Escalations", int((fraud_df["fraud_action"] == "Review").sum()))
        col2.metric("Auto-clears", int((fraud_df["fraud_action"] == "Auto-Clear").sum()))
        col3.metric("Avg fraud score", f"{fraud_df['fraud_score'].mean():.1f}")

        fig_hist = px.histogram(fraud_df, x="fraud_score", color="fraud_action", nbins=40, title="Fraud score distribution")
        st.plotly_chart(fig_hist, use_container_width=True)
        if "country" in fraud_df.columns:
            fig_country = px.bar(
                fraud_df.groupby("country", dropna=False)["fraud_score"].mean().reset_index(),
                x="country",
                y="fraud_score",
                title="Avg fraud score by country",
            )
            st.plotly_chart(fig_country, use_container_width=True)

    for name, df in datasets.items():
        st.markdown(f"### {name.replace('_', ' ').title()}")
        if isinstance(df, pd.DataFrame) and not df.empty:
            st.caption(f"Rows: {len(df):,}")
            st.dataframe(df.head(200), use_container_width=True)
            st.download_button(
                f"⬇️ Download {name}.csv",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"{name}.csv",
                mime="text/csv",
                key=f"download_{name}",
            )
        else:
            st.info(f"{name} dataset empty.")

    if any(isinstance(df, pd.DataFrame) and not df.empty for df in datasets.values()):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, df in datasets.items():
                if isinstance(df, pd.DataFrame) and not df.empty:
                    zf.writestr(f"{name}.csv", df.to_csv(index=False))
        st.download_button(
            "⬇️ Download full audit ZIP",
            data=buf.getvalue(),
            file_name="afk_audit_bundle.zip",
            mime="application/zip",
        )
