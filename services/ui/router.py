# services/ui/router.py
# ─────────────────────────────────────────────
# Centralized Page Router for Streamlit UI
# Handles navigation between:
#   - Landing Page
#   - Credit Appraisal Workflow
#   - Asset Appraisal Workflow
# ─────────────────────────────────────────────
import streamlit as st

def navigate():
    """Detect ?agent= query parameter and route user to correct Streamlit page."""
    try:
        qp = st.experimental_get_query_params()
        if not qp:
            return  # no query params → stay on landing page

        if "agent" in qp:
            agent_param = qp["agent"][0].lower()

            # ─────────────────────────────────────────────
            # Agent Routing
            # ─────────────────────────────────────────────
            if "credit" in agent_param:
                st.switch_page("services/ui/app.py")  # Credit Appraisal Workflow
            elif "asset" in agent_param:
                st.switch_page("services/ui/asset_appraisal.py")  # Asset Appraisal Workflow
            else:
                st.warning(f"⚠️ Unknown agent type: {agent_param}")
                return

    except Exception as e:
        st.error(f"Router error: {e}")
