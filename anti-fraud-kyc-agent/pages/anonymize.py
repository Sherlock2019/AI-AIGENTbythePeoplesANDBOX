"""Anonymization utilities for Anti-Fraud & KYC agent."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

DEFAULT_SENSITIVE_FIELDS = {"full_name", "email", "gov_id", "device_id"}


def _mask_value(value: str) -> str:
    if not value:
        return value
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def _mask_dataframe(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    masked = df.copy()
    for col in columns:
        if col in masked.columns:
            masked[col] = masked[col].astype(str).apply(_mask_value)
    return masked


def render_anonymize_tab(ss, runs_dir: Path) -> None:
    runs_dir = Path(runs_dir)
    st.header("B) Privacy & Anonymization")
    st.caption("Mask PII fields and produce a privacy-safe dataset for downstream KYC and fraud checks.")

    intake_df = ss.get("afk_intake_df")
    if not isinstance(intake_df, pd.DataFrame) or intake_df.empty:
        st.info("Stage A dataset not found. Load or generate intake data first.")
        return

    st.markdown("### 1. Choose fields to mask")
    available_cols = list(intake_df.columns)
    selected_cols = st.multiselect(
        "Sensitive columns",
        options=available_cols,
        default=[c for c in DEFAULT_SENSITIVE_FIELDS if c in available_cols],
        help="Selected columns will be hashed/masked before sharing with other teams.",
    )

    drop_notes = st.checkbox("Drop free-form notes column", value=False)
    if drop_notes and "notes" in intake_df.columns:
        working_df = intake_df.drop(columns=["notes"])
    else:
        working_df = intake_df.copy()

    anonymized_df = _mask_dataframe(working_df, selected_cols)
    ss["afk_anonymized_df"] = anonymized_df
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "stage_b_anonymized.csv").write_bytes(anonymized_df.to_csv(index=False).encode("utf-8"))

    st.success(f"Anonymized dataset ready ({len(anonymized_df):,} rows).")
    st.dataframe(anonymized_df.head(200), use_container_width=True)
    st.download_button(
        "⬇️ Download anonymized CSV",
        data=anonymized_df.to_csv(index=False).encode("utf-8"),
        file_name="afk_anonymized_dataset.csv",
        mime="text/csv",
    )
