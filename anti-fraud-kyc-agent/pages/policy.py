"""Policy tab for Anti-Fraud agent."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

POLICIES = [
    "Follow FATF travel rule requirements when sharing payments data.",
    "Retain KYC documentation for at least 7 years or per regulator guidance.",
    "Escalate politically exposed persons (PEPs) to senior compliance within 24h.",
    "Refresh KYC for high-risk customers every 12 months.",
    "Log all overrides with analyst notes for auditability.",
]


def render_policy_tab(ss, runs_dir: Path) -> None:
    runs_dir = Path(runs_dir)
    st.header("E) Policy & Controls")
    st.caption("Summaries and evidence that policy controls are firing for the scored applicants.")

    fraud_df = ss.get("afk_fraud_df")
    if not isinstance(fraud_df, pd.DataFrame) or fraud_df.empty:
        st.info("Run Stage D to populate data for policy attestation.")
    else:
        autopct = (fraud_df["fraud_action"] == "Auto-Clear").mean()
        pep_cases = int(fraud_df.get("pep_flag", pd.Series(False)).sum())
        sanctions = int(fraud_df.get("sanctions_hit", pd.Series(False)).sum())

        c1, c2, c3 = st.columns(3)
        c1.metric("Auto-cleared %", f"{autopct*100:.1f}%")
        c2.metric("PEP flags", pep_cases)
        c3.metric("Sanctions hits", sanctions)

        st.dataframe(
            fraud_df[
                [
                    "applicant_id",
                    "country",
                    "risk_score",
                    "pep_flag",
                    "sanctions_hit",
                    "fraud_action",
                ]
            ].head(200),
            use_container_width=True,
        )
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / "stage_e_policy.csv").write_bytes(fraud_df.to_csv(index=False).encode("utf-8"))

    st.markdown("### 📋 Control reminders")
    for idx, policy in enumerate(POLICIES, start=1):
        st.markdown(f"**{idx}. {policy}**")
