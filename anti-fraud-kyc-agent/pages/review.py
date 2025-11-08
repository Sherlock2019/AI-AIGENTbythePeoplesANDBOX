"""Review tab for Anti-Fraud agent."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

FEEDBACK_FILENAME = "stage_f_feedback.csv"


def _load_reviews(runs_dir: Path) -> pd.DataFrame:
    logfile = Path(runs_dir) / "review_log.csv"
    if logfile.exists():
        return pd.read_csv(logfile)
    return pd.DataFrame(columns=["case", "analyst", "decision", "notes", "timestamp"])


def _append_review(case: str, analyst: str, decision: str, notes: str, runs_dir: Path) -> None:
    logfile = Path(runs_dir) / "review_log.csv"
    df = _load_reviews(runs_dir)
    df = pd.concat(
        [
            df,
            pd.DataFrame(
                [
                    {
                        "case": case,
                        "analyst": analyst,
                        "decision": decision,
                        "notes": notes,
                        "timestamp": pd.Timestamp.utcnow().isoformat(),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    df.to_csv(logfile, index=False)


def _feedback_path(runs_dir: Path) -> Path:
    return Path(runs_dir) / FEEDBACK_FILENAME


def _load_feedback(runs_dir: Path) -> pd.DataFrame:
    path = _feedback_path(runs_dir)
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _save_feedback(df: pd.DataFrame, runs_dir: Path) -> Path:
    path = _feedback_path(runs_dir)
    df.to_csv(path, index=False)
    return path


def render_review_tab(ss, runs_dir: Path) -> None:
    runs_dir = Path(runs_dir)
    st.header("F) Human Review")
    st.caption("Surface high-risk alerts, capture analyst decisions, and push overrides into the training loop.")

    action_a, action_b = st.columns(2)
    with action_a:
        if st.button("⬅️ Import from Stage D", use_container_width=True):
            st.success("Latest Stage D escalations loaded below.")
    with action_b:
        if st.button("➡️ Send feedback to Stage G", use_container_width=True):
            st.success("Saved feedback automatically feeds the training stage.")

    fraud_df = ss.get("afk_fraud_df")
    pending = (
        fraud_df[fraud_df["fraud_action"] == "Review"]
        if isinstance(fraud_df, pd.DataFrame) and not fraud_df.empty
        else pd.DataFrame()
    )

    feedback_existing = _load_feedback(runs_dir)
    if isinstance(feedback_existing, pd.DataFrame) and not feedback_existing.empty:
        ss["afk_feedback_df"] = feedback_existing.copy()

    if pending.empty and (not isinstance(feedback_existing, pd.DataFrame) or feedback_existing.empty):
        st.info("No escalations awaiting review. Once Stage D flags cases, they appear here.")
        return

    st.markdown("### 📝 Editable feedback table")
    if pending.empty:
        base_table = feedback_existing.copy()
    else:
        base_table = pending[
            [
                "applicant_id",
                "country",
                "transaction_amount",
                "risk_score",
                "pep_flag",
                "fraud_score",
                "fraud_action",
            ]
        ].copy()
        base_table["human_decision"] = base_table["fraud_action"]
        base_table["human_notes"] = ""

    if isinstance(ss.get("afk_feedback_df"), pd.DataFrame) and not ss["afk_feedback_df"].empty:
        base_table = ss["afk_feedback_df"].copy()

    for col in ["human_notes", "human_decision"]:
        if col in base_table.columns:
            base_table[col] = base_table[col].astype(str)
    base_table["human_notes"] = base_table.get("human_notes", "").astype(str)

    edited = st.data_editor(
        base_table,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key="afk_feedback_editor",
        column_config={
            "human_decision": st.column_config.SelectboxColumn(
                "Human decision",
                options=["Review", "Auto-Clear", "Request Info", "Reject", "Approve"],
                help="Select the analyst action to store for training.",
            ),
            "human_notes": st.column_config.TextColumn("Human rationale"),
            "fraud_action": st.column_config.TextColumn("AI decision", disabled=True),
        },
    )

    save_col, download_col = st.columns(2)
    with save_col:
        if st.button("💾 Save feedback table", use_container_width=True):
            path = _save_feedback(pd.DataFrame(edited), runs_dir)
            ss["afk_feedback_df"] = pd.DataFrame(edited)
            st.success(f"Feedback saved → `{path.name}`")
    with download_col:
        st.download_button(
            "⬇️ Download feedback CSV",
            data=pd.DataFrame(edited).to_csv(index=False).encode("utf-8"),
            file_name="afk_human_feedback.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if isinstance(edited, pd.DataFrame) and not edited.empty:
        st.markdown("### 📊 AI vs Human alignment")
        ai_dec = edited["fraud_action"].astype(str).str.lower()
        hu_dec = edited["human_decision"].astype(str).str.lower()
        agreement = (ai_dec == hu_dec).mean() * 100
        review_gap = (hu_dec.eq("review").mean() - ai_dec.eq("review").mean()) * 100
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number+delta",
                value=agreement,
                number={"suffix": "%"},
                delta={"reference": 100, "valueformat": ".1f"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#38bdf8"},
                    "steps": [
                        {"range": [0, 60], "color": "#fee2e2"},
                        {"range": [60, 85], "color": "#fef9c3"},
                        {"range": [85, 100], "color": "#dcfce7"},
                    ],
                },
                title={"text": "Agreement"},
            )
        )
        st.plotly_chart(fig, use_container_width=True)
        st.metric("Human review delta vs AI (Review rate)", f"{review_gap:+.1f} pp")

        changes = pd.DataFrame(edited)[ai_dec != hu_dec]
        if not changes.empty:
            st.markdown("### 🔄 Overrides & reasons")
            st.dataframe(
                changes[
                    [
                        "applicant_id",
                        "fraud_score",
                        "fraud_action",
                        "human_decision",
                        "human_notes",
                    ]
                ],
                use_container_width=True,
            )

    st.markdown("### 🗂️ Analyst log (optional)")
    if pending.empty:
        st.info("No escalations listed, but you can still log manual reviews below.")

    with st.form("afk_review_form"):
        case_id = st.selectbox(
            "Case ID",
            options=pending["applicant_id"].tolist() if not pending.empty else [],
            format_func=lambda x: x if x else "Manual entry",
        )
        manual_case = st.text_input("Or enter case ID manually")
        analyst = st.text_input("Analyst", value=ss.get("afk_user", {}).get("name", ""))
        decision = st.selectbox("Decision", ["Approve", "Reject", "Request Info", "Review"])
        notes = st.text_area("Notes / justification")
        submitted = st.form_submit_button("Log review")

    selected_case = (manual_case or "").strip() or case_id
    if submitted:
        if not selected_case:
            st.error("Provide a case ID.")
        else:
            _append_review(selected_case, analyst.strip(), decision, notes.strip(), runs_dir)
            st.success(f"Review logged for {selected_case}.")

    reviews = _load_reviews(runs_dir)
    ss["afk_review_df"] = reviews
    st.markdown("### 🗂️ Latest manual entries")
    st.dataframe(reviews.tail(50), use_container_width=True)
