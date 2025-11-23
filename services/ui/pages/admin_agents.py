#!/usr/bin/env python3
"""🔧 Admin Page for Managing Landing Page Agents"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any

import streamlit as st

# Set page config
st.set_page_config(
    page_title="🔧 Agent Manager Admin",
    page_icon="🔧",
    layout="wide",
)

# Add custom styling
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    }
    h1 {
        color: #60a5fa;
        text-align: center;
        margin-bottom: 1rem;
    }
    .stButton > button {
        background: linear-gradient(90deg, #3b82f6, #2563eb);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #2563eb, #1d4ed8);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Path to agents data file
AGENTS_DATA_FILE = Path(__file__).parent.parent / "data" / "agents.json"

# Status options
STATUS_OPTIONS = ["Available", "NEW", "Coming Soon", "WIP", "Being Built"]

def load_agents() -> List[Dict[str, Any]]:
    """Load agents from JSON file."""
    if AGENTS_DATA_FILE.exists():
        try:
            with open(AGENTS_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading agents: {e}")
            return []
    return []

def save_agents(agents: List[Dict[str, Any]]) -> bool:
    """Save agents to JSON file."""
    try:
        AGENTS_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AGENTS_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(agents, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving agents: {e}")
        return False

def main():
    st.title("🔧 Agent Manager Admin")
    st.markdown("**Manage agents displayed on the landing page**")
    st.markdown("Add, edit, or delete agents. Changes are saved to `services/ui/data/agents.json`")
    st.markdown("---")
    
    # Load agents
    agents = load_agents()
    
    # Initialize session state
    if "agents" not in st.session_state:
        st.session_state.agents = agents
    if "editing_index" not in st.session_state:
        st.session_state.editing_index = None
    if "show_add_form" not in st.session_state:
        st.session_state.show_add_form = False
    
    # Sidebar for actions
    with st.sidebar:
        st.header("Actions")
        if st.button("➕ Add New Agent", use_container_width=True):
            st.session_state.editing_index = None
            st.session_state.show_add_form = True
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Info")
        st.info(f"Total Agents: {len(st.session_state.agents)}")
        
        if st.button("🔄 Reload from File", use_container_width=True):
            st.session_state.agents = load_agents()
            st.session_state.editing_index = None
            st.rerun()
    
    # Main content area
    tab1, tab2 = st.tabs(["📋 Agent List", "➕ Add/Edit Agent"])
    
    with tab1:
        st.header("📋 Agent List")
        
        if not st.session_state.agents:
            st.info("No agents found. Add a new agent to get started.")
        else:
            # Search and filter
            search_term = st.text_input("🔍 Search agents", placeholder="Search by name, sector, or industry...")
            
            # Filter agents
            filtered_agents = st.session_state.agents
            if search_term:
                search_lower = search_term.lower()
                filtered_agents = [
                    agent for agent in st.session_state.agents
                    if search_lower in agent.get('agent', '').lower() or
                       search_lower in agent.get('sector', '').lower() or
                       search_lower in agent.get('industry', '').lower() or
                       search_lower in agent.get('description', '').lower()
                ]
            
            st.markdown(f"**Showing {len(filtered_agents)} of {len(st.session_state.agents)} agents**")
            st.markdown("---")
            
            # Display agents
            for idx, agent in enumerate(st.session_state.agents):
                # Find the actual index in the full list
                actual_idx = st.session_state.agents.index(agent) if agent in st.session_state.agents else None
                if actual_idx is None:
                    continue
                
                # Skip if filtered out
                if search_term and agent not in filtered_agents:
                    continue
                
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 1.5, 1])
                    
                    with col1:
                        st.markdown(f"**{agent.get('agent', 'N/A')}** {agent.get('emoji', '🤖')}")
                        st.caption(f"{agent.get('sector', '')} → {agent.get('industry', '')}")
                    
                    with col2:
                        desc = agent.get('description', 'N/A')
                        st.markdown(f"📝 {desc[:60]}{'...' if len(desc) > 60 else ''}")
                    
                    with col3:
                        status = agent.get('status', 'N/A')
                        status_colors = {
                            "Available": ("🟢", "#22c55e"),
                            "NEW": ("🔵", "#3b82f6"),
                            "Coming Soon": ("🟡", "#f59e0b"),
                            "WIP": ("🟣", "#f472b6"),
                            "Being Built": ("🟠", "#f97316")
                        }
                        status_emoji, status_color = status_colors.get(status, ("⚪", "#94a3b8"))
                        st.markdown(f"{status_emoji} **{status}**")
                        # Show login requirement
                        if agent.get('requires_login', False):
                            st.markdown("🔐 **Login Required**", help="Users must login to access this agent")
                        else:
                            st.markdown("🔓 **No Login**", help="Direct access without login")
                    
                    with col4:
                        col_edit, col_del = st.columns(2)
                        with col_edit:
                            if st.button("✏️", key=f"edit_{actual_idx}", help="Edit agent"):
                                st.session_state.editing_index = actual_idx
                                st.session_state.show_add_form = True
                                st.rerun()
                        with col_del:
                            if st.button("🗑️", key=f"delete_{actual_idx}", help="Delete agent"):
                                st.session_state.agents.pop(actual_idx)
                                if save_agents(st.session_state.agents):
                                    st.success("✅ Agent deleted successfully!")
                                    st.rerun()
                    
                    st.markdown("---")
    
    with tab2:
        if st.session_state.editing_index is not None:
            st.header("✏️ Edit Agent")
            agent_data = st.session_state.agents[st.session_state.editing_index]
        else:
            st.header("➕ Add New Agent")
            agent_data = {}
        
        with st.form("agent_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            
            with col1:
                sector = st.text_input(
                    "🏭 Sector",
                    value=agent_data.get("sector", ""),
                    placeholder="e.g., 🏦 Banking & Finance"
                )
                industry = st.text_input(
                    "🧩 Industry",
                    value=agent_data.get("industry", ""),
                    placeholder="e.g., 💰 Retail Banking Suite"
                )
                agent_name = st.text_input(
                    "🤖 Agent Name",
                    value=agent_data.get("agent", ""),
                    placeholder="e.g., 💳 Credit Appraisal Agent"
                )
            
            with col2:
                emoji = st.text_input(
                    "😀 Emoji",
                    value=agent_data.get("emoji", ""),
                    placeholder="e.g., 💳",
                    help="Single emoji for the agent"
                )
                status = st.selectbox(
                    "📶 Status",
                    options=STATUS_OPTIONS,
                    index=STATUS_OPTIONS.index(agent_data.get("status", "Available")) if agent_data.get("status") in STATUS_OPTIONS else 0
                )
                requires_login = st.checkbox(
                    "🔐 Requires Login",
                    value=agent_data.get("requires_login", False),
                    help="If enabled, users must login before accessing this agent"
                )
                description = st.text_area(
                    "📝 Description",
                    value=agent_data.get("description", ""),
                    placeholder="Brief description of what the agent does",
                    height=100
                )
            
            col_submit, col_cancel = st.columns(2)
            with col_submit:
                submitted = st.form_submit_button(
                    "💾 Save Agent" if is_editing else "➕ Add Agent",
                    use_container_width=True
                )
            with col_cancel:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state.editing_index = None
                    st.session_state.show_add_form = False
                    st.rerun()
            
            if submitted:
                # Validation
                if not all([sector, industry, agent_name, emoji, description]):
                    st.error("❌ Please fill in all fields!")
                elif len(emoji.strip()) > 2:
                    st.error("❌ Emoji should be a single emoji character")
                else:
                    new_agent = {
                        "sector": sector.strip(),
                        "industry": industry.strip(),
                        "agent": agent_name.strip(),
                        "description": description.strip(),
                        "status": status,
                        "emoji": emoji.strip(),
                        "requires_login": requires_login
                    }
                    
                    is_editing = st.session_state.editing_index is not None
                    if is_editing:
                        # Update existing agent
                        st.session_state.agents[st.session_state.editing_index] = new_agent
                        action = "updated"
                    else:
                        # Add new agent
                        st.session_state.agents.append(new_agent)
                        action = "added"
                    
                    if save_agents(st.session_state.agents):
                        st.success(f"✅ Agent {action} successfully!")
                        st.session_state.editing_index = None
                        st.session_state.show_add_form = False
                        st.rerun()
                    else:
                        st.error("❌ Failed to save agent!")

if __name__ == "__main__":
    main()
