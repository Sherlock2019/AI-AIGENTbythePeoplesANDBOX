from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence

import streamlit as st

UI_DIR = Path(__file__).resolve().parents[1]
FEEDBACK_FILE = UI_DIR / "agents_feedback.json"

DEFAULT_FEEDBACK = {
    "🛡️ Anti-Fraud & KYC Agent": {
        "rating": 4.5,
        "users": 12,
        "comments": [
            "💡 Suggestion: Add real-time document verification API integration for faster processing",
            "Excellent fraud detection accuracy! Saved us from 3 high-risk cases this week.",
            "💡 Suggestion: Include biometric verification options (face recognition, fingerprint)",
            "The dashboard is intuitive and the risk scoring is spot-on.",
            "💡 Suggestion: Add multi-language support for international customers",
            "Streamlined our onboarding process significantly. Great work!",
        ],
    },
    "💳 Credit Score Agent": {
        "rating": 4.7,
        "users": 8,
        "comments": [
            "💡 Suggestion: Add explainable AI feature to show why score changed",
            "Accurate credit scoring! The 300-850 range is industry standard.",
            "💡 Suggestion: Include trend analysis showing score improvement over time",
            "Love the quick turnaround time. Much faster than traditional methods.",
            "💡 Suggestion: Add credit score simulation tool for 'what-if' scenarios",
            "Helped us approve more loans with confidence. Excellent tool!",
        ],
    },
    "🏦 Asset Appraisal Agent": {
        "rating": 4.6,
        "users": 15,
        "comments": [
            "💡 Suggestion: Integrate Real Estate Evaluator map directly into appraisal workflow",
            "The 3D map visualization is fantastic! Makes location analysis much easier.",
            "💡 Suggestion: Add automated market trend analysis and price forecasting",
            "Market-driven valuations are accurate and well-documented.",
            "💡 Suggestion: Include photo upload and OCR for property condition assessment",
            "The human review stage with Real Estate Evaluator integration is a game-changer!",
            "Great tool for collateral valuation. Saved us hours of manual work.",
        ],
    },
    "💳 Credit Appraisal Agent": {
        "rating": 4.8,
        "users": 20,
        "comments": [
            "💡 Suggestion: Add loan recommendation engine based on credit profile",
            "Explainable AI feature is excellent! Helps us justify decisions to customers.",
            "💡 Suggestion: Include automated document generation for loan offers",
            "The decision pipeline is clear and transparent. Love it!",
            "💡 Suggestion: Add integration with credit bureau APIs for real-time data",
            "Reduced our loan processing time by 60%. Highly recommended!",
            "The model training feature allows us to improve accuracy over time.",
        ],
    },
    "⚖️ Legal Compliance Agent": {
        "rating": 4.4,
        "users": 10,
        "comments": [
            "💡 Suggestion: Add automated regulatory update notifications",
            "Sanctions and PEP checks are comprehensive and up-to-date.",
            "💡 Suggestion: Include compliance report generation for audits",
            "Helps us stay compliant with minimal effort. Great peace of mind.",
            "💡 Suggestion: Add multi-jurisdiction compliance checking",
            "The licensing verification feature caught 2 expired licenses this month.",
        ],
    },
    "🧩 Unified Risk Orchestration Agent": {
        "rating": 4.9,
        "users": 5,
        "comments": [
            "💡 Suggestion: Add customizable risk weightings per business unit",
            "Combining asset+credit+fraud into one decision is brilliant!",
            "💡 Suggestion: Include real-time risk dashboard with alerts",
            "This is exactly what we needed - a unified view of all risks.",
            "💡 Suggestion: Add risk scenario modeling and stress testing",
            "The orchestration logic is sophisticated and well-designed.",
        ],
    },
    "💬 Chatbot Assistant": {
        "rating": 4.3,
        "users": 7,
        "comments": [
            "💡 Suggestion: Add voice input/output support for hands-free interaction",
            "Context-aware responses are impressive. Very natural conversation flow.",
            "💡 Suggestion: Include multi-language support and translation",
            "The RAG system provides accurate answers from policy documents.",
            "💡 Suggestion: Add sentiment analysis to detect customer frustration",
            "Great for answering common questions. Reduces support workload.",
        ],
    },
    "🏠 Real Estate Evaluator Agent": {
        "rating": 4.7,
        "users": 6,
        "comments": [
            "💡 Suggestion: Add historical price trend charts for each property",
            "The interactive 3D map with price zones is visually stunning!",
            "💡 Suggestion: Include property comparison tool side-by-side",
            "Market price comparison feature is accurate and helpful.",
            "💡 Suggestion: Add neighborhood analytics (schools, amenities, crime rates)",
            "Love the zone analysis feature. Makes market research much easier.",
        ],
    },
    "🧠 IT Troubleshooter Agent": {
        "rating": 4.5,
        "users": 9,
        "comments": [
            "💡 Suggestion: Add integration with ticketing systems (Jira, ServiceNow)",
            "First-principles approach combined with case memory is powerful.",
            "💡 Suggestion: Include automated solution testing before suggesting fixes",
            "Helped us resolve 80% of incidents faster. Great tool!",
            "💡 Suggestion: Add knowledge base learning from resolved tickets",
            "The escalation logic is smart and prevents unnecessary escalations.",
        ],
    },
    "🧑‍🚀 Persona Strategy Room": {
        "rating": 4.8,
        "users": 6,
        "comments": [
            "💡 Suggestion: Add ability to save and replay previous strategy sessions",
            "Love the multi-persona collaboration! Makes complex decisions much easier.",
            "💡 Suggestion: Include real-time voting/consensus mechanism for decisions",
            "The transcript export feature is perfect for audit trails.",
            "💡 Suggestion: Add visual decision tree showing how personas reached conclusions",
            "This is exactly what we needed - a unified view from all risk domains.",
            "💡 Suggestion: Include historical case comparison in the room",
            "The pre-populated FAQs are very helpful for getting started quickly.",
        ],
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
