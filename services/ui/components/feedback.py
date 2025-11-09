from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence

import streamlit as st

UI_DIR = Path(__file__).resolve().parents[1]
FEEDBACK_FILE = UI_DIR / "agents_feedback.json"

DEFAULT_FEEDBACK = {
    "💳 Credit Appraisal Agent": {
        "rating": 5,
        "users": 1,
        "comments": ["Great starting point!"],
    },
    "🏦 Asset Appraisal Agent": {
        "rating": 5,
        "users": 1,
        "comments": ["Loving the dashboard."],
    },
    "🛡️ Anti-Fraud & KYC Agent": {
        "rating": 5,
        "users": 1,
        "comments": ["Helps us clear risky cases very quickly."],
    },
}


def _ensure_agents(data: dict, agents: Iterable[str]) -> dict:
    for agent in agents:
        data.setdefault(agent, {"rating": 5, "users": 0, "comments": []})
    return data


def load_feedback_data() -> dict:
    try:
        with FEEDBACK_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    return _ensure_agents(data, DEFAULT_FEEDBACK.keys())


def save_feedback_data(data: dict) -> None:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def render_feedback_tab(
    primary_agent: str,
    agent_choices: Sequence[str] | None = None,
) -> None:
    """Shared Streamlit UI for the feedback tab on every agent page."""
    agent_list = list(agent_choices or DEFAULT_FEEDBACK.keys())
    if primary_agent not in agent_list:
        agent_list.insert(0, primary_agent)

    feedback_data = load_feedback_data()
    _ensure_agents(feedback_data, agent_list)
    st.session_state["feedback_data"] = feedback_data

    st.subheader("🗣️ Share Your Feedback and Feature Ideas")

    st.markdown("### 💬 Current Agent Reviews & Ratings")
    for agent in agent_list:
        fb = feedback_data.get(agent, {"rating": 0, "users": 0, "comments": []})
        comments = fb.get("comments", [])
        rating = fb.get("rating", 0)
        users = fb.get("users", 0)
        with st.expander(f"⭐ {agent} — {rating}/5  |  👥 {users} users"):
            if comments:
                st.markdown("#### Recent Comments:")
                for comment in reversed(comments):
                    st.markdown(f"- {comment}")
            else:
                st.caption("No feedback yet.")
            st.markdown("---")

    st.markdown("### ✍️ Submit Your Own Feedback or Feature Request")
    agent_choice = st.selectbox(
        "Select Agent",
        agent_list,
        index=agent_list.index(primary_agent) if primary_agent in agent_list else 0,
        key=f"feedback_select_{primary_agent}",
    )
    new_comment = st.text_area(
        "Your Comment or Feature Suggestion",
        placeholder="e.g. Add multi-language support for reports...",
        key=f"feedback_comment_{primary_agent}",
    )
    new_rating = st.slider(
        "Your Rating",
        1,
        5,
        5,
        key=f"feedback_rating_{primary_agent}",
    )

    if st.button("📨 Submit Feedback", key=f"submit_feedback_{primary_agent}"):
        if not new_comment.strip():
            st.warning("Please enter a comment before submitting.")
            return

        fb = feedback_data.get(agent_choice, {"rating": 0, "users": 0, "comments": []})
        current_users = fb.get("users", 0)
        fb["comments"] = fb.get("comments", []) + [new_comment.strip()]
        if current_users > 0:
            fb["rating"] = round(
                (fb.get("rating", 0) * current_users + new_rating) / (current_users + 1),
                2,
            )
        else:
            fb["rating"] = float(new_rating)
        fb["users"] = current_users + 1
        feedback_data[agent_choice] = fb
        save_feedback_data(feedback_data)
        st.session_state["feedback_data"] = feedback_data
        st.success("✅ Feedback submitted successfully!")
        st.rerun()
