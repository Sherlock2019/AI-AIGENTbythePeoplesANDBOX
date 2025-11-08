#!/usr/bin/env python3
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

import pandas as pd
import streamlit as st
from utils.data_loaders import load_hf_dataset_as_df, download_kaggle_dataset
from pages.intake import render_intake_tab
from pages.anonymize import render_anonymize_tab
from pages.kyc_verification import render_kyc_tab
from pages.fraud_detection import render_fraud_tab
from pages.policy import render_policy_tab
from pages.review import render_review_tab
from pages.train import render_train_tab
from pages.report import render_report_tab

st.set_page_config(page_title="Anti-Fraud & KYC Agent", layout="wide")
ss = st.session_state
ss.setdefault("afk_logged_in", False)
ss.setdefault("afk_user", {"name": "Guest"})
RUNS_DIR = os.path.abspath("./.tmp_runs"); os.makedirs(RUNS_DIR, exist_ok=True)

if not ss["afk_logged_in"]:
    st.title("🔐 Login")
    u = st.text_input("Username")
    e = st.text_input("Email")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u.strip():
            ss["afk_logged_in"] = True
            ss["afk_user"] = {"name": u, "email": e}
            st.rerun()  # ✅ new API (was st.experimental_rerun)
        else:
            st.error("Enter username")
            st.stop()
    st.stop()

st.title("🔒 Anti-Fraud & KYC Agent")
nav = st.sidebar.radio(
    "Navigation",
    ["A) Intake", "B) Privacy", "C) KYC Verify", "D) Fraud", "E) Policy", "F) Train", "G) Report"]
)

if nav.startswith("A"): render_intake_tab(ss, RUNS_DIR)
elif nav.startswith("B"): render_anonymize_tab(ss, RUNS_DIR)
elif nav.startswith("C"): render_kyc_tab(ss, RUNS_DIR)
elif nav.startswith("D"): render_fraud_tab(ss, RUNS_DIR)
elif nav.startswith("E"): render_policy_tab(ss, RUNS_DIR)
elif nav.startswith("F"): render_train_tab(ss, RUNS_DIR)
elif nav.startswith("G"): render_report_tab(ss, RUNS_DIR)
