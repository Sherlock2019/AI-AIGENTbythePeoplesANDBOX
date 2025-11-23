"""
🧠 AI Troubleshooter Agent — First Principles + Case Memory
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict
import random
from textwrap import dedent

import pandas as pd
import streamlit as st

from services.ui.theme_manager import (
    apply_theme as apply_global_theme,
    render_theme_toggle,
)
from services.ui.components.operator_banner import render_operator_banner
from services.ui.components.feedback import render_feedback_tab
try:
    from services.ui.components.chat_assistant import render_chat_assistant
except ImportError:
    render_chat_assistant = None


STAGE_KEYS = [
    "intake",
    "ticket",
    "appraisal",
    "problem",
    "decision",
    "potential",
    "ai_plan",
    "human_review",
    "training",
    "deployment",
]

STAGE_LABELS = {
    "intake": "Ticket Intake",
    "ticket": "Ticket Generator",
    "appraisal": "Situation Appraisal",
    "problem": "Problem Analysis",
    "decision": "Decision Analysis",
    "potential": "Potential Problems",
    "ai_plan": "AI Troubleshooting Plan",
    "human_review": "Human Review",
    "training": "Training & Escalation",
    "deployment": "Deployment & Feedback",
}


DEFAULT_INCIDENTS = [
    {
        "id": "INC-87342",
        "source": "ServiceNow",
        "service": "Payments API",
        "severity": "P1",
        "status": "Investigating",
        "summary": "Spike in 504 errors from payments cluster A",
    },
    {
        "id": "INC-87318",
        "source": "Jira",
        "service": "Customer Portal",
        "severity": "P2",
        "status": "Pending RCA",
        "summary": "Login redirect loop impacting 12% of sessions",
    },
    {
        "id": "INC-87291",
        "source": "ServiceNow",
        "service": "Core Messaging",
        "severity": "P1",
        "status": "Mitigated",
        "summary": "Kafka consumer lag alerts firing for shard-5",
    },
]

SYNTHETIC_TEMPLATES = [
    {
        "service": "Data Lake",
        "summary": "ETL latency spike after schema change",
        "severity": "P2",
        "status": "Open",
        "source": "Synthetic",
    },
    {
        "service": "Identity Platform",
        "summary": "SSO redirect loop for mobile Safari users",
        "severity": "P1",
        "status": "Investigating",
        "source": "Synthetic",
    },
    {
        "service": "Notifications",
        "summary": "Push queue backlog exceeded SLO for APAC region",
        "severity": "P2",
        "status": "Pending RCA",
        "source": "Synthetic",
    },
]

CASE_MEMORY = pd.DataFrame(
    [
        {
            "case_id": "CASE-101",
            "service": "Payments API",
            "root_cause": "Expired TLS cert on load-balancer",
            "fix_time": "28 min",
            "lessons": "Add cert-expiry alert + self-check",
        },
        {
            "case_id": "CASE-099",
            "service": "Customer Portal",
            "root_cause": "Redis cache replication stall",
            "fix_time": "41 min",
            "lessons": "Auto scale read replicas during deploys",
        },
        {
            "case_id": "CASE-095",
            "service": "Core Messaging",
            "root_cause": "Misconfigured consumer group offset reset",
            "fix_time": "33 min",
            "lessons": "Guard rails on offset reset CLI",
        },
    ]
)

TROUBLESHOOTER_FAQ = [
    "List the last 10 incidents reviewed by the Troubleshooter agent.",
    "Where do I find the latest .tmp_runs artifacts for troubleshooting?",
    "Show the workflow stages A→F for this agent.",
    "What are the standard questions for Situation Appraisal?",
    "How do I escalate a ticket after Stage 9?",
    "Summarize decision alternatives for the current ticket.",
    "Show me the lessons learned from the last 10 resolved cases.",
    "How do I rerun the AI troubleshooting plan?",
    "Where are escalation packages stored after deployment?",
    "What evidence is required before moving to Human Review?",
]

def _build_troubleshooter_chat_context() -> Dict[str, Any]:
    ss = st.session_state
    ticket = ss.get("ts_selected_ticket") or {}
    ready_map = ss.get("ts_stage_ready", {})
    context = {
        "agent_type": "troubleshooter",
        "stage": ss.get("stage"),
        "active_ticket": ticket.get("id"),
        "service": ticket.get("service"),
        "severity": ticket.get("severity"),
        "completed_stages": ", ".join(k for k, v in ready_map.items() if v),
        "open_incidents": len(ss.get("ts_incidents", DEFAULT_INCIDENTS)),
    }
    return {k: v for k, v in context.items() if v not in (None, "", [])}


def _set_query_params_safe(**kwargs):
    """Best-effort query param setter for cross-version Streamlit support."""
    try:
        for k, v in kwargs.items():
            st.query_params[k] = v
        return True
    except Exception:
        pass
    try:
        st.experimental_set_query_params(**kwargs)
        return True
    except Exception:
        return False


def _go_stage(target_stage: str) -> None:
    """Hop back into the main landing/agents flow."""
    st.session_state["stage"] = target_stage
    try:
        st.switch_page("app.py")
        return
    except Exception:
        pass
    _set_query_params_safe(stage=target_stage)
    st.rerun()


def render_troubleshooter_nav() -> None:
    stage = st.session_state.get("stage", "landing")
    c1, c2, c3 = st.columns([1, 1, 2.5])

    with c1:
        if st.button("🏠 Back to Home", key=f"tr_home_{stage}"):
            _go_stage("landing")
            st.stop()

    with c2:
        if st.button("🤖 Back to Agents", key=f"tr_agents_{stage}"):
            _go_stage("agents")
            st.stop()

    with c3:
        render_theme_toggle("🌗 Dark mode", key="troubleshooter_theme_toggle_nav")

    st.markdown("---")


def _init_stage_tracker():
    ss = st.session_state
    if "ts_stage_ready" not in ss:
        ss["ts_stage_ready"] = {key: False for key in STAGE_KEYS}
    else:
        for key in STAGE_KEYS:
            ss["ts_stage_ready"].setdefault(key, False)


def _dependencies_met(stage_key: str) -> bool:
    idx = STAGE_KEYS.index(stage_key)
    required = STAGE_KEYS[:idx]
    ready = st.session_state.get("ts_stage_ready", {})
    missing = [STAGE_LABELS[k] for k in required if not ready.get(k)]
    if missing:
        st.info(f"Please complete {', '.join(missing)} before working on this stage.")
        return False
    return True


def _render_stage_completion(stage_key: str):
    ready = st.session_state["ts_stage_ready"]
    if ready.get(stage_key):
        st.success(f"{STAGE_LABELS[stage_key]} marked complete. You can revisit to edit.")
        return
    if st.button(f"Mark {STAGE_LABELS[stage_key]} complete ✅", key=f"complete_{stage_key}"):
        ready[stage_key] = True
        st.success(f"{STAGE_LABELS[stage_key]} completed — proceed to the next tab.")


def _init_state():
    ss = st.session_state
    _init_stage_tracker()
    ss.setdefault("ts_ticket_source", "ServiceNow")
    ss.setdefault("ts_selected_ticket", DEFAULT_INCIDENTS[0])
    ss.setdefault("troubleshooter_demo_loaded", True)  # Demo data already loaded
    ss.setdefault(
        "ts_appraisal",
        {
            "issues": ["Customer Impact", "Regulatory"],
            "concerns": "Customers in SEA unable to complete checkout; regulators pinged for SLA breach.",
            "urgency": 4,
            "impact": 4,
            "notes": "Need status update for leadership within 30 minutes.",
        },
    )
    ss.setdefault(
        "ts_problem",
        {
            "what": "Increased 504 responses on Payments API cluster A",
            "where": "apac-cluster-a, az2",
            "when": "Started 05:42 UTC, recurs every deploy",
            "extent": "8% of traffic, mostly card payments",
            "is_conditions": "Only cluster A, only card transactions, only API v2",
            "is_not_conditions": "Cluster B unaffected, ACH unaffected, API v1 stable",
            "hypotheses": "LB cert expired; node draining mis-config; new WAF rule",
            "tests": "Compare cert expiry dates; replay traffic via staging; disable WAF rule temporarily",
        },
    )
    ss.setdefault(
        "ts_decision",
        {
            "must": "Restore sub-2s latency; keep compliance logging intact.",
            "nice": "Avoid full region failover; no customer comms if possible.",
            "alternatives": [
                {"name": "Rotate LB cert", "benefit": 5, "risk": 2},
                {"name": "Fail traffic to cluster B", "benefit": 4, "risk": 3},
            ],
        },
    )
    ss.setdefault(
        "ts_potential",
        {
            "risks": "Cluster B overload, cert rotation fails, new regression hidden.",
            "preventive": "Warm extra nodes; backup cert ready; post-deploy synthetic checks.",
            "contingency": "If rotation fails, failover to DR; notify comms team.",
            "opportunities": "Automate cert renewal alerts; capture playbook for training.",
        },
    )
    if "ts_ai_candidates" not in ss:
        ss["ts_ai_candidates"] = [
            {
                "case_id": row.case_id,
                "cause": row.root_cause,
                "confidence": round(0.65 - idx * 0.07, 2),
                "lessons": row.lessons,
                "status": "pending",
            }
            for idx, row in enumerate(CASE_MEMORY.itertuples())
        ]
    ss.setdefault("ts_ai_attempts", 0)
    ss.setdefault("ts_ai_solution", None)
    ss.setdefault("ts_escalated", False)
    ss.setdefault("ts_feedback_log", [])
    ss.setdefault("ts_ai_plan", [])
    ss.setdefault("ts_human_reviews", [])
    ss.setdefault("ts_training_records", [])
    ss.setdefault(
        "ts_deployment_meta",
        {"exported": False, "timestamp": None, "notes": "", "feedback": []},
    )
    ss.setdefault(
        "ts_ticket_payload",
        {
            "title": "Payments API 504 surge",
            "impact": "Checkout latency degraded for 8% of SEA customers",
            "resolution": "Rotated LB cert + drained bad node",
            "channel": "ServiceNow",
            "appraisal": None,
            "problem": None,
            "decision": None,
            "potential": None,
            "ai_solution": None,
            "escalation": None,
        },
    )


def render_ticket_intake_stage():
    ss = st.session_state
    if not _dependencies_met("intake"):
        return
    st.subheader("① Import Ticket & Context")
    col_a, col_b = st.columns([1.2, 1])

    with col_a:
        src = st.radio(
            "Ticket source",
            ("ServiceNow", "Jira", "CSV Upload", "Manual Entry"),
            key="ts_ticket_source_radio",
        )

        if src in {"ServiceNow", "Jira"}:
            env = st.selectbox("Environment", ["Production", "Staging", "DR"])
            ticket_map = {
                f"{item['id']} · {item['service']}": item for item in DEFAULT_INCIDENTS
            }
            selection = st.selectbox("Recent incidents", list(ticket_map.keys()))
            if st.button("📥 Load ticket", key="ts_load_ticket"):
                ss["ts_ticket_source"] = src
                ss["ts_selected_ticket"] = ticket_map[selection]
                ss["ts_selected_ticket"]["environment"] = env
                _hydrate_from_ticket(ss["ts_selected_ticket"])
                st.success(f"Loaded {selection} from {src}")

        elif src == "CSV Upload":
            uploaded = st.file_uploader("Upload CSV export", type=["csv"])
            if uploaded:
                try:
                    df = pd.read_csv(uploaded)
                    st.dataframe(df.head(), use_container_width=True)
                    st.info("Pick a row and press 'Load ticket' to continue.")
                except Exception as exc:
                    st.error(f"Could not read CSV: {exc}")
        else:
            manual_id = st.text_input("Ticket ID")
            manual_summary = st.text_area("Summary")
            if st.button("Save manual ticket", key="ts_manual_ticket"):
                ss["ts_selected_ticket"] = {
                    "id": manual_id or "INC-manual",
                    "source": "Manual",
                    "service": "Custom",
                    "severity": "Triage",
                    "status": "Draft",
                    "summary": manual_summary or "Operator entered ticket",
                }
                _hydrate_from_ticket(ss["ts_selected_ticket"])
                st.success("Manual ticket saved.")

    with col_b:
        st.caption("Live intake feed")
        st.dataframe(pd.DataFrame(DEFAULT_INCIDENTS), use_container_width=True, height=240)
        st.info("Need a synthetic practice ticket? Use the dedicated Ticket Generator stage right after this intake step.")

    ticket = ss.get("ts_selected_ticket")
    if isinstance(ticket, dict):
        summary = ticket.get("summary", "N/A")
        service = ticket.get("service", "N/A")
        severity = ticket.get("severity", "N/A")
        status = ticket.get("status", "N/A")
        environment = ticket.get("environment", "Production")
        st.success(
            dedent(
                f"""
                **Active Ticket**: {ticket.get('id', 'INC-draft')} ({environment})
                - Service: {service} | Severity: {severity} | Status: {status}
                - Summary: {summary}
                """
            )
        )
        st.json(ticket, expanded=False)
    _render_stage_completion("intake")


def render_situation_appraisal_stage():
    ss = st.session_state
    if not _dependencies_met("appraisal"):
        return
    st.subheader("② Situation Appraisal (Kepner-Tregoe)")
    issues = st.multiselect(
        "Concerns / issues in scope",
        ["Customer Impact", "Regulatory", "Security", "Capacity", "Observability", "Vendors"],
        default=ss["ts_appraisal"]["issues"],
    )
    concerns = st.text_area(
        "Describe the situation",
        ss["ts_appraisal"]["concerns"],
        height=120,
    )
    col_u, col_i = st.columns(2)
    with col_u:
        urgency = st.slider("Urgency (time pressure)", 1, 5, ss["ts_appraisal"]["urgency"])
    with col_i:
        impact = st.slider("Impact (blast radius)", 1, 5, ss["ts_appraisal"]["impact"])
    notes = st.text_area(
        "Other notes / stakeholders / next updates",
        ss["ts_appraisal"]["notes"],
        height=100,
    )
    if st.button("Save appraisal"):
        ss["ts_appraisal"] = {
            "issues": issues,
            "concerns": concerns,
            "urgency": urgency,
            "impact": impact,
            "notes": notes,
        }
        st.success("Situation appraisal captured.")
        _cascade_from_appraisal()

    priority = urgency * impact
    if priority >= 16:
        label = "Critical"
    elif priority >= 9:
        label = "High"
    elif priority >= 4:
        label = "Medium"
    else:
        label = "Low"
    st.metric("Priority score", f"{priority}/25", label)
    st.caption(
        "Higher urgency × impact indicates which concerns need deeper analysis right now."
    )
    _render_stage_completion("appraisal")


def render_problem_analysis_stage():
    ss = st.session_state
    if not _dependencies_met("problem"):
        return
    st.subheader("③ Problem Analysis (Define & Decompose)")
    col_main, col_is = st.columns([1.2, 0.8])

    st.session_state.setdefault("ts_problem_is", ss["ts_problem"]["is_conditions"])
    st.session_state.setdefault("ts_problem_is_not", ss["ts_problem"]["is_not_conditions"])

    with col_main:
        what = st.text_input("What is wrong?", ss["ts_problem"]["what"])
        where = st.text_input("Where does it occur?", ss["ts_problem"]["where"])
        when = st.text_input("When is it observed?", ss["ts_problem"]["when"])
        extent = st.text_input("Extent / magnitude", ss["ts_problem"]["extent"])
        hypotheses = st.text_area(
            "Possible causes (decompose into smallest parts)",
            ss["ts_problem"]["hypotheses"],
            height=120,
        )
        tests = st.text_area(
            "Experiments / diagnostics to run",
            ss["ts_problem"]["tests"],
            height=120,
        )
        if st.button("Save problem analysis"):
            ss["ts_problem"] = {
                "what": what,
                "where": where,
                "when": when,
                "extent": extent,
                "is_conditions": st.session_state.get("ts_problem_is"),
                "is_not_conditions": st.session_state.get("ts_problem_is_not"),
                "hypotheses": hypotheses,
                "tests": tests,
            }
            st.success("Problem analysis updated.")
            _cascade_from_problem()

    with col_is:
        is_conditions = st.text_area(
            "IS (conditions present)",
            ss["ts_problem"]["is_conditions"],
            height=140,
            key="ts_problem_is",
        )
        is_not_conditions = st.text_area(
            "IS NOT (conditions absent)",
            ss["ts_problem"]["is_not_conditions"],
            height=140,
            key="ts_problem_is_not",
        )
        st.caption(
            "Compare IS vs IS NOT to quickly eliminate causes that don't match all observed conditions."
        )
    _render_stage_completion("problem")


def render_decision_analysis_stage():
    ss = st.session_state
    if not _dependencies_met("decision"):
        return
    st.subheader("④ Decision Analysis (Choose Action)")
    must = st.text_area("Must-have objectives", ss["ts_decision"]["must"], height=120)
    nice = st.text_area("Nice-to-have objectives", ss["ts_decision"]["nice"], height=120)

    st.markdown("##### Alternatives")
    new_alt = st.text_input("Alternative name")
    benefit = st.slider("Benefit score", 1, 5, 3)
    risk = st.slider("Risk score (lower is safer)", 1, 5, 3)
    if st.button("Add alternative"):
        ss["ts_decision"]["alternatives"].append(
            {"name": new_alt or f"Option {len(ss['ts_decision']['alternatives'])+1}", "benefit": benefit, "risk": risk}
        )
        st.success("Alternative added.")

    if ss["ts_decision"]["alternatives"]:
        df = pd.DataFrame(ss["ts_decision"]["alternatives"])
        df["score"] = df["benefit"] - df["risk"]
        st.dataframe(df, hide_index=True, use_container_width=True)
        best = df.sort_values("score", ascending=False).iloc[0]
        st.info(f"Current best option: {best['name']} (score {best['score']})")

    if st.button("Save decision analysis"):
        ss["ts_decision"]["must"] = must
        ss["ts_decision"]["nice"] = nice
        st.success("Decision analysis saved.")
        _cascade_from_decision()
    _render_stage_completion("decision")


def render_potential_problem_stage():
    ss = st.session_state
    if not _dependencies_met("potential"):
        return
    st.subheader("⑤ Potential Problem / Opportunity Analysis + AI Suggestions")
    risks = st.text_area("What could go wrong?", ss["ts_potential"]["risks"], height=120)
    preventive = st.text_area(
        "Preventive actions",
        ss["ts_potential"]["preventive"],
        height=120,
    )
    contingency = st.text_area(
        "Contingency plan if risk happens",
        ss["ts_potential"]["contingency"],
        height=120,
    )
    opportunities = st.text_area(
        "Opportunities to amplify",
        ss["ts_potential"]["opportunities"],
        height=120,
    )
    if st.button("Save potential problem analysis"):
        ss["ts_potential"] = {
            "risks": risks,
            "preventive": preventive,
            "contingency": contingency,
            "opportunities": opportunities,
        }
        st.success("Plan saved.")

    st.markdown("##### AI Suggested Root Causes / Leads")
    candidates = ss["ts_ai_candidates"]
    if candidates:
        st.dataframe(
            pd.DataFrame(candidates)[["case_id", "cause", "confidence", "status"]],
            hide_index=True,
            use_container_width=True,
        )
    solution = ss.get("ts_ai_solution")
    escalated = ss.get("ts_escalated")
    if solution:
        st.success(
            f"AI-confirmed cause: {solution['cause']} (case {solution['case_id']}). Include lessons in your plan."
        )
    elif escalated:
        st.warning("AI exhausted local cases; incident escalated to Level 3 (Kira / eService).")
    else:
        options = [c["case_id"] for c in candidates if c["status"] != "rejected"]
        if not options:
            st.error("No more AI candidates. Consider escalating.")
        else:
            selected = st.selectbox("Review AI candidate", options, key="ts_ai_selected")
            current = next(c for c in candidates if c["case_id"] == selected)
            st.markdown(
                f"**Hypothesis:** {current['cause']}  \n**Lessons learned:** {current['lessons']}"
            )
            rating = st.slider(
                "Does this match what you're seeing?",
                1,
                5,
                4,
                key="ts_ai_rating",
            )
            feedback = st.text_input(
                "Feedback to AI (evidence, contradicting clues)",
                key="ts_ai_feedback",
            )
            col_accept, col_reject = st.columns(2)
            if col_accept.button("👍 Accept and apply fix", key="ts_ai_accept"):
                current["status"] = "confirmed"
                ss["ts_ai_solution"] = {
                    "cause": current["cause"],
                    "case_id": current["case_id"],
                    "lessons": current["lessons"],
                }
                st.success("Root cause accepted. Capture mitigation in Decision stage.")
            if col_reject.button("👎 Doesn't match", key="ts_ai_reject"):
                current["status"] = "rejected"
                current["confidence"] = max(0.1, current["confidence"] - 0.15 * (6 - rating))
                ss["ts_ai_attempts"] += 1
                ss["ts_feedback_log"].insert(
                    0,
                    {
                        "case_id": current["case_id"],
                        "rating": rating,
                        "feedback": feedback or "No comment",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
                st.warning("Feedback saved; AI candidate list updated.")
        attempts = ss["ts_ai_attempts"]
        if attempts >= 3 and not ss.get("ts_ai_solution"):
            with st.expander("🔍 Research checklist (Quora / vendor forums)"):
                st.markdown(
                    """
                    - Search Quora, vendor communities, or public postmortems for similar incidents.  
                    - Ask LLM copilots for alternate hypotheses given your telemetry.  
                    - Feed new clues back into the candidate selector above.
                    """
                )
        if attempts >= 5 and not ss.get("ts_ai_solution") and not ss.get("ts_escalated"):
            if st.button("Escalate to Level 3 (Kira / eService)", key="ts_escalate_l3"):
                ss["ts_escalated"] = True
                st.success("Escalation recorded; include summary in final ticket.")

    _render_stage_completion("potential")


def render_ai_plan_stage():
    ss = st.session_state
    if not _dependencies_met("ai_plan"):
        return
    st.subheader("⑥ AI Assisted Troubleshooting Plan")
    st.caption("AI proposes structured steps for each hypothesis; adjust owners & status before execution.")
    plan = ss["ts_ai_plan"] or _generate_ai_plan()
    df = pd.DataFrame(plan) if plan else pd.DataFrame(
        [{"Hypothesis": "No hypothesis captured", "Troubleshooting Step": "", "Owner": "Ops", "Status": "Pending"}]
    )
    edited = st.data_editor(
        df,
        num_rows="dynamic",
        column_config={
            "Hypothesis": st.column_config.TextColumn(width="medium"),
            "Troubleshooting Step": st.column_config.TextColumn(width="large"),
            "Owner": st.column_config.TextColumn(width="small"),
            "Status": st.column_config.SelectboxColumn(options=["Pending", "In Progress", "Done"]),
        },
        use_container_width=True,
    )
    if st.button("Save AI troubleshooting plan"):
        ss["ts_ai_plan"] = edited.to_dict("records")
        st.success("Troubleshooting plan saved.")
    st.caption("Tip: mark steps as you execute them; human review will evaluate these entries.")
    _render_stage_completion("ai_plan")


def render_human_review_stage():
    ss = st.session_state
    if not _dependencies_met("human_review"):
        return
    st.subheader("⑦ Human Review — Validate AI Plan")
    plan = ss.get("ts_ai_plan", [])
    if not plan:
        st.warning("No AI plan available. Complete the previous stage first.")
        return
    df = pd.DataFrame(plan)
    if "ReviewStatus" not in df.columns:
        df["ReviewStatus"] = "Pending"
    if "ReviewerNotes" not in df.columns:
        df["ReviewerNotes"] = ""
    edited = st.data_editor(
        df,
        column_config={
            "ReviewStatus": st.column_config.SelectboxColumn(
                options=["Pending", "Working", "Not Working"], label="Review Status"
            ),
            "ReviewerNotes": st.column_config.TextColumn(width="large"),
        },
        use_container_width=True,
        num_rows="dynamic",
    )
    if st.button("Save human review results"):
        records = edited.to_dict("records")
        ss["ts_ai_plan"] = records
        ss["ts_human_reviews"] = records
        st.success("Human review saved.")
        if any(r["ReviewStatus"] == "Working" for r in records):
            ss["ts_ai_solution"] = {
                "cause": records[0].get("Hypothesis", "Hypothesis"),
                "case_id": "AD-HOC",
                "lessons": "Validated by human reviewer",
            }
    if not ss.get("ts_escalated") and ss.get("ts_human_reviews"):
        all_fail = all(r.get("ReviewStatus") == "Not Working" for r in ss["ts_human_reviews"])
        if all_fail:
            if st.button("Escalate to Level 3 (Kira / eService)", key="ts_escalate_human"):
                ss["ts_escalated"] = True
                st.success("Escalation recorded for engineering support.")
    _render_stage_completion("human_review")


def render_training_stage():
    ss = st.session_state
    if not _dependencies_met("training"):
        return
    st.subheader("⑧ Training & Escalation Package")
    reviews = ss.get("ts_human_reviews", [])
    if reviews:
        st.markdown("##### Latest troubleshooting session")
        st.dataframe(pd.DataFrame(reviews), use_container_width=True, hide_index=True)
    history = _history_payload()
    st.markdown("##### Troubleshooting history snapshot")
    st.json(history, expanded=False)

    col_left, col_right = st.columns(2)
    with col_left:
        label = st.text_input("Training example title", value=history["ticket"].get("title", "Unnamed incident"))
        outcome = st.selectbox("Outcome", ["Resolved", "Mitigated", "Escalated", "Unresolved"])
        if st.button("Add to training dataset"):
            ss["ts_training_records"].append(
                {
                    "title": label,
                    "outcome": outcome,
                    "timestamp": datetime.utcnow().isoformat(),
                    "plan_steps": len(ss.get("ts_ai_plan", [])),
                }
            )
            st.success("Logged to training dataset.")
    with col_right:
        if not ss.get("ts_escalated"):
            escalate_note = st.text_area("Escalation summary (if needed)")
            if st.button("Escalate to engineering with full history"):
                ss["ts_escalated"] = True
                ss["ts_training_records"].append(
                    {
                        "title": f"Escalated - {label}",
                        "outcome": "Escalated",
                        "timestamp": datetime.utcnow().isoformat(),
                        "notes": escalate_note,
                    }
                )
                st.success("Escalation package prepared.")
        else:
            st.info("Escalation already triggered for this incident.")
    st.markdown("##### Training dataset")
    if ss["ts_training_records"]:
        st.dataframe(pd.DataFrame(ss["ts_training_records"]), use_container_width=True, hide_index=True)
    else:
        st.caption("No training records yet.")
    _render_stage_completion("training")


def render_deployment_stage():
    ss = st.session_state
    if not _dependencies_met("deployment"):
        return
    st.subheader("⑨ Deployment & Feedback")
    records = ss.get("ts_training_records", [])
    if records:
        st.dataframe(pd.DataFrame(records).tail(5), use_container_width=True, hide_index=True)
    export_col, feedback_col = st.columns(2)
    with export_col:
        if ss["ts_deployment_meta"]["exported"]:
            st.success(f"Playbook exported on {ss['ts_deployment_meta']['timestamp']}")
        if st.button("Export troubleshooting model to production"):
            ss["ts_deployment_meta"]["exported"] = True
            ss["ts_deployment_meta"]["timestamp"] = datetime.utcnow().isoformat()
            st.success("Playbook exported and ready for reuse.")
    with feedback_col:
        rating = st.slider("How effective was this session?", 1, 5, 4)
        comment = st.text_area("Final feedback / lessons learned")
        if st.button("Submit feedback"):
            entry = {
                "rating": rating,
                "comment": comment,
                "timestamp": datetime.utcnow().isoformat(),
            }
            ss["ts_deployment_meta"]["feedback"].append(entry)
            ss["ts_feedback_log"].append(comment or "No comment")
            st.success("Feedback captured.")
    if ss["ts_deployment_meta"]["feedback"]:
        st.markdown("##### Recent feedback")
        st.json(ss["ts_deployment_meta"]["feedback"][-3:], expanded=False)
    _render_stage_completion("deployment")
def render_ticket_generator_stage():
    ss = st.session_state
    if not _dependencies_met("ticket"):
        return
    st.subheader("② Ticket Generator & Import")
    payload = ss["ts_ticket_payload"]

    col_left, col_right = st.columns([1.2, 0.8])
    with col_left:
        title = st.text_input("Ticket title", payload.get("title", "Incident summary"))
        impact = st.text_area("Business impact", payload.get("impact", ""), height=120)
        resolution = st.text_area(
            "Resolution / next steps",
            payload.get("resolution", ""),
            height=160,
        )
        channels = ["ServiceNow", "Jira", "Slack Bridge"]
        default_idx = (
            channels.index(payload.get("channel", "ServiceNow"))
            if payload.get("channel", "ServiceNow") in channels
            else 0
        )
        channel = st.selectbox("Handoff channel", channels, index=default_idx)
        ai_solution = ss.get("ts_ai_solution")
        escalation = ss["ts_escalated"]
        if st.button("Generate ticket payload / import"):
            ticket_record = {
                "title": title,
                "impact": impact,
                "resolution": resolution,
                "channel": channel,
                "appraisal": ss.get("ts_appraisal"),
                "problem": ss.get("ts_problem"),
                "decision": ss.get("ts_decision"),
                "potential": ss.get("ts_potential"),
                "ai_solution": ai_solution,
                "escalation": escalation,
                "id": ss.get("ts_selected_ticket", {}).get("id") or f"INC-DRAFT-{datetime.utcnow().strftime('%H%M%S')}",
                "service": ss.get("ts_selected_ticket", {}).get("service", "Unknown"),
                "severity": ss.get("ts_selected_ticket", {}).get("severity", "P2"),
                "status": "Draft",
                "source": "Generated",
            }
            ss["ts_ticket_payload"] = ticket_record
            ss["ts_selected_ticket"] = ticket_record
            _hydrate_from_ticket(ticket_record)
            st.success(f"Draft ready for {channel} and synced with Situation Appraisal.")

    with col_right:
        if ss.get("ts_ai_solution"):
            st.success(
                f"AI-confirmed fix: {ss['ts_ai_solution']['cause']} (case {ss['ts_ai_solution']['case_id']})"
            )
        elif ss.get("ts_escalated"):
            st.warning("Status: Escalated to Level 3 support (Kira / eService).")
        else:
            st.caption("AI is still investigating — capture current notes before sending.")
        st.markdown("##### Rendered payload")
        st.json(ss["ts_ticket_payload"])
        st.caption("Copy/paste into your ITSM of choice or push via API.")
    _render_stage_completion("ticket")


def render_howto_stage():
    st.subheader("📘 How-To Guide")
    st.markdown(
        """
        Welcome to the KT-guided Troubleshooter preview. Follow these steps in order:

        1. **Ticket Intake** — import from ServiceNow/Jira, upload CSV, or generate a synthetic ticket for practice.
        2. **Situation Appraisal** — capture concerns, urgency, and impact to know what deserves attention.
        3. **Problem Analysis** — decompose the deviation into _WHAT/WHERE/WHEN/EXTENT_ plus IS vs IS NOT grids.
        4. **Decision Analysis** — compare remediation options using must/nice objectives and benefit–risk scoring.
        5. **Potential Problems** — anticipate downstream risks and define preventive / contingency actions.
        6. **AI Assist** — let the agent suggest root causes from case memory, then refine via your feedback.
        7. **Ticket Generator** — export the entire KT+AI context or escalate to Level 3 (Kira / eService).

        Each tab ships with pre-filled examples—update them as you gather real telemetry. Use the completion buttons
        to unlock the next stage. If AI cannot converge, consult the research checklist or escalate so Level 3 receives
        a complete package.
        """
    )
    st.caption("Tip: Need a quick scenario? Use the synthetic ticket generator in Stage 1 to practice the full loop.")


def _generate_synthetic_ticket():
    template = random.choice(SYNTHETIC_TEMPLATES)
    suffix = datetime.utcnow().strftime("%H%M%S")
    return {
        "id": f"INC-SYN-{suffix}",
        "source": template["source"],
        "service": template["service"],
        "severity": template["severity"],
        "status": template["status"],
        "summary": template["summary"],
        "environment": random.choice(["Production", "Staging"]),
    }


def _generate_ai_plan():
    ss = st.session_state
    hypotheses_raw = ss["ts_problem"].get("hypotheses", "")
    hypotheses = [h.strip() for h in hypotheses_raw.replace("\n", ";").split(";") if h.strip()]
    plan = []
    for idx, hypo in enumerate(hypotheses or ["Investigate primary hypothesis"]):
        plan.append(
            {
                "Hypothesis": hypo,
                "Troubleshooting Step": f"Run diagnostic #{idx+1} for {hypo.lower()}",
                "Owner": "Ops",
                "Status": "Pending",
            }
        )
    return plan


def _history_payload():
    ss = st.session_state
    return {
        "ticket": ss.get("ts_selected_ticket", {}),
        "appraisal": ss.get("ts_appraisal"),
        "problem": ss.get("ts_problem"),
        "decision": ss.get("ts_decision"),
        "potential": ss.get("ts_potential"),
        "ai_plan": ss.get("ts_ai_plan"),
        "human_review": ss.get("ts_human_reviews"),
        "escalated": ss.get("ts_escalated"),
    }


def _hydrate_from_ticket(ticket: dict):
    if not ticket:
        return
    ss = st.session_state
    concerns = f"{ticket.get('summary','')} | Service: {ticket.get('service','N/A')} ({ticket.get('environment','Production')})"
    notes = f"Severity {ticket.get('severity','P3')} • Source {ticket.get('source','Unknown')} • Status {ticket.get('status','Open')}"
    ss["ts_appraisal"].update(
        {
            "concerns": concerns,
            "notes": notes,
            "issues": ["Customer Impact", "Capacity"],
        }
    )
    ss["ts_problem"].update(
        {
            "what": ticket.get("summary", ss["ts_problem"]["what"]),
            "where": f"{ticket.get('service','Unknown')} / {ticket.get('environment','Production')}",
            "extent": f"Severity {ticket.get('severity','P3')}",
            "when": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
    )
    _cascade_from_appraisal()


def _cascade_from_appraisal():
    ss = st.session_state
    ticket = ss.get("ts_selected_ticket", {})
    ss["ts_problem"].setdefault("what", ticket.get("summary", ""))
    if not ss["ts_problem"].get("hypotheses"):
        ss["ts_problem"]["hypotheses"] = "Potential LB issue; Possible deployment regression; Capacity imbalance"
    if not ss["ts_problem"].get("tests"):
        ss["ts_problem"]["tests"] = "Compare metrics across clusters; replay failing requests; inspect recent deploy diff"


def _cascade_from_problem():
    ss = st.session_state
    hypotheses = ss["ts_problem"].get("hypotheses", "")
    ideas = [h.strip() for h in hypotheses.replace("\n", ";").split(";") if h.strip()]
    if ideas:
        ss["ts_decision"]["alternatives"] = [
            {"name": idea[:60], "benefit": min(5, 3 + idx), "risk": max(1, 3 - idx)}
            for idx, idea in enumerate(ideas[:3])
        ]


def _cascade_from_decision():
    ss = st.session_state
    alts = ss["ts_decision"].get("alternatives", [])
    if alts:
        best = sorted(alts, key=lambda x: x["benefit"] - x["risk"], reverse=True)[0]
        ss["ts_potential"]["risks"] = f"Executing {best['name']} may introduce regression elsewhere."
        ss["ts_potential"]["preventive"] = "Add canary checks + feature flags."
        ss["ts_potential"]["contingency"] = "Roll back change or fail traffic to stable cluster."
        ss["ts_potential"]["opportunities"] = f"Document {best['name']} as reusable runbook."


st.set_page_config(page_title="AI Troubleshooter Agent", layout="wide")
apply_global_theme()
_init_state()

render_troubleshooter_nav()

st.title("🧠 AI Troubleshooter Agent (Public Preview)")
st.caption("Import tickets → walk the KT method → let AI refine causes with your feedback → escalate or hand off with confidence.")

render_operator_banner(
    operator_name="Ops Engineer",
    title="Troubleshooter Agent",
    summary="Kepner-Tregoe guided incident responder with live ticket import, AI hypothesis refinement, and structured handoff.",
    bullets=[
        "Progress through Situation, Problem, Decision, and Potential analyses with pre-filled guidance.",
        "AI assistant narrows probable causes using case memory plus your real-time feedback.",
        "Human review, training/export, and escalation packaging ensure fixes reach production or Level 3 support.",
    ],
    metrics=[
        {
            "label": "Status",
            "value": "Being Built",
            "context": "Workflow wiring is live; backend execution coming next.",
        },
        {
            "label": "AI Playbooks",
            "value": f"{len(CASE_MEMORY)} fixtures",
            "context": "Grows whenever you log a new root cause and lessons learned.",
        },
    ],
    icon="🧠",
)

st.info(
    "Follow the KT questionnaires in order, capture AI feedback at each step, and finish with either a validated fix "
    "or an escalation package ready for Kira / eService."
)

if render_chat_assistant is not None:
    render_chat_assistant(
        page_id="troubleshooter_agent",
        context=_build_troubleshooter_chat_context(),
        faq_questions=TROUBLESHOOTER_FAQ,
    )

stage_tabs = st.tabs(
    [
        "📘 How-To",
        "1️⃣ Ticket Intake",
        "2️⃣ Ticket Generator",
        "3️⃣ Situation Appraisal",
        "4️⃣ Problem Analysis",
        "5️⃣ Decision Analysis",
        "6️⃣ Potential Problems",
        "7️⃣ AI Plan",
        "8️⃣ Human Review",
        "9️⃣ Training & Escalation",
        "🔟 Deployment & Feedback",
        "🗣️ Feedback & Feature Requests",
    ]
)

with stage_tabs[0]:
    render_howto_stage()
with stage_tabs[1]:
    render_ticket_intake_stage()
with stage_tabs[2]:
    render_ticket_generator_stage()
with stage_tabs[3]:
    render_situation_appraisal_stage()
with stage_tabs[4]:
    render_problem_analysis_stage()
with stage_tabs[5]:
    render_decision_analysis_stage()
with stage_tabs[6]:
    render_potential_problem_stage()
with stage_tabs[7]:
    render_ai_plan_stage()
with stage_tabs[8]:
    render_human_review_stage()
with stage_tabs[9]:
    render_training_stage()
with stage_tabs[10]:
    render_deployment_stage()
with stage_tabs[11]:
    render_feedback_tab("🧠 IT Troubleshooter Agent")
