"""
Agent Builder — No-Code Builder with Templates and Lego Blocks
--------------------------------------------------------------

Allows users to import ready-made agent templates (credit, asset, fraud),
customize blocks (data ingestion, anonymization, AI, training) without code,
and optionally export the configuration or implementation code.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import streamlit as st

from services.ui.theme_manager import init_theme, apply_theme, get_theme
from services.ui.utils.style import render_nav_bar_app
from services.ui.utils.agent_builder_utils import (
    create_block_instance,
    generate_agent_code,
    get_agent_templates,
    get_block_library,
    get_function_lookup,
    instantiate_template,
    list_saved_blueprints,
    load_blueprint,
    save_agent_code,
    save_blueprint,
)

# ---------------------------------------------------------------------------
# Theme & Layout
# ---------------------------------------------------------------------------

init_theme()
theme = get_theme()
apply_theme(theme)

st.set_page_config(page_title="Agent Builder", page_icon="🧩", layout="wide")
render_nav_bar_app()

st.title("🧩 Agent Builder — No-Code")
st.caption("Load a template, drag blocks, configure, and deploy without touching Python.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Session State Helpers
# ---------------------------------------------------------------------------


def _ensure_state() -> None:
    ss = st.session_state
    ss.setdefault("builder_blocks", [])
    ss.setdefault("agent_name", "custom_agent")
    ss.setdefault("agent_description", "")
    ss.setdefault("selected_template_id", None)
    ss.setdefault("generated_code", None)
    ss.setdefault("agent_sector", "🛠️ AI Tools & Infrastructure")
    ss.setdefault("agent_industry", "🧩 Custom Blueprints")
    ss.setdefault("agent_status", "NEW")
    ss.setdefault("agent_emoji", "✨")
    ss.setdefault("agent_tagline", "")
    ss.setdefault("loaded_blueprint_slug", None)


def _rerun():
    st.session_state.pop("__tmp__", None)
    st.rerun()


def _hydrate_blocks(raw_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    hydrated = []
    for raw in raw_blocks or []:
        block_id = raw.get("block_id")
        if not block_id:
            continue
        overrides = raw.get("config") or {}
        alias = raw.get("alias")
        try:
            block = create_block_instance(block_id, config_overrides=overrides, alias=alias)
        except ValueError:
            # skip unknown blocks but keep fallback structure
            continue
        block["enabled"] = raw.get("enabled", True)
        block["notes"] = raw.get("notes", "")
        hydrated.append(block)
    return hydrated


def _load_blueprint_into_state(blueprint: Dict[str, Any]) -> None:
    blocks = _hydrate_blocks(blueprint.get("blocks", []))
    meta = blueprint.get("metadata", {})
    st.session_state.builder_blocks = blocks
    st.session_state.agent_name = blueprint.get("agent_name", st.session_state.agent_name)
    st.session_state.agent_description = meta.get("description") or blueprint.get("description", "")
    st.session_state.agent_sector = meta.get("sector", st.session_state.agent_sector)
    st.session_state.agent_industry = meta.get("industry", st.session_state.agent_industry)
    st.session_state.agent_status = meta.get("status", st.session_state.agent_status)
    st.session_state.agent_emoji = meta.get("emoji", st.session_state.agent_emoji)
    st.session_state.agent_tagline = meta.get("tagline", st.session_state.agent_tagline)
    st.session_state.selected_template_id = meta.get("template_id")
    st.session_state.loaded_blueprint_slug = blueprint.get("slug") or meta.get("slug")


def _load_from_query_params():
    params = getattr(st, "query_params", None)
    if params is None:
        params = st.experimental_get_query_params()
    blueprint_param = params.get("blueprint")
    if isinstance(blueprint_param, list):
        blueprint_param = blueprint_param[0] if blueprint_param else None
    if not blueprint_param:
        return
    slug = blueprint_param.strip().lower()
    if not slug or slug == st.session_state.get("loaded_blueprint_slug"):
        return
    try:
        blueprint = load_blueprint(slug)
        _load_blueprint_into_state(blueprint)
        st.session_state.loaded_blueprint_slug = slug
        st.success(f"Loaded blueprint '{blueprint.get('agent_name', slug)}' from dashboard.")
    except Exception as exc:
        st.warning(f"Unable to load blueprint '{slug}': {exc}")


def _move_block(idx: int, direction: int) -> None:
    blocks = st.session_state.builder_blocks
    new_idx = idx + direction
    if 0 <= new_idx < len(blocks):
        blocks[idx], blocks[new_idx] = blocks[new_idx], blocks[idx]
        _rerun()


def _remove_block(idx: int) -> None:
    st.session_state.builder_blocks.pop(idx)
    _rerun()


def _render_block_editor(idx: int, block: Dict[str, Any]) -> None:
    header = f"{idx + 1}. {block.get('icon', '🔧')} {block.get('alias', block['name'])}"
    with st.expander(header, expanded=True):
        col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])
        with col_a:
            block["enabled"] = st.checkbox(
                "Enabled",
                value=block.get("enabled", True),
                key=f"enabled_{block['instance_id']}",
            )
        with col_b:
            if st.button("⬆️ Move Up", disabled=idx == 0, key=f"up_{block['instance_id']}"):
                _move_block(idx, -1)
        with col_c:
            if st.button(
                "⬇️ Move Down",
                disabled=idx == len(st.session_state.builder_blocks) - 1,
                key=f"down_{block['instance_id']}",
            ):
                _move_block(idx, 1)
        with col_d:
            if st.button("🗑️ Remove", key=f"remove_{block['instance_id']}"):
                _remove_block(idx)

        block["alias"] = st.text_input(
            "Display Label",
            value=block.get("alias", block["name"]),
            key=f"alias_{block['instance_id']}",
        )
        block["notes"] = st.text_area(
            "Notes",
            value=block.get("notes", ""),
            key=f"notes_{block['instance_id']}",
            height=60,
        )

        st.markdown("**Configuration**")
        for field in block.get("config_fields", []):
            key = field["key"]
            widget_key = f"{block['instance_id']}_{key}"
            current_value = block["config"].get(key)
            field_type = field.get("type", "text")
            label = field.get("label", key)
            help_text = field.get("help")

            if field_type == "select":
                options = field.get("options", [])
                index = options.index(current_value) if current_value in options else 0
                block["config"][key] = st.selectbox(
                    label,
                    options,
                    index=index if options else 0,
                    key=widget_key,
                    help=help_text,
                )
            elif field_type == "multiselect":
                options = field.get("options", [])
                default = current_value if isinstance(current_value, list) else []
                block["config"][key] = st.multiselect(
                    label,
                    options,
                    default=default,
                    key=widget_key,
                    help=help_text,
                )
            elif field_type == "number":
                default_value = current_value if isinstance(current_value, (int, float)) else 0.0
                block["config"][key] = st.number_input(
                    label,
                    value=float(default_value),
                    key=widget_key,
                    help=help_text,
                )
            elif field_type == "checkbox":
                block["config"][key] = st.checkbox(
                    label,
                    value=bool(current_value),
                    key=widget_key,
                    help=help_text,
                )
            else:
                block["config"][key] = st.text_input(
                    label,
                    value=current_value if current_value is not None else "",
                    key=widget_key,
                    help=help_text,
                )

        st.markdown("---")
        st.caption(f"Block ID: `{block['block_id']}` · Function link: {block.get('function_ref', '—')}")


_ensure_state()
_load_from_query_params()

block_library = get_block_library()
templates = get_agent_templates()
function_lookup = get_function_lookup()
saved_blueprints = list_saved_blueprints()

# Flatten block options for add selector
block_options = {
    f"{blk['category']} · {blk['name']}": blk["id"]
    for blk in block_library
}

# ---------------------------------------------------------------------------
# Tabs: Templates | Builder Canvas | Preview & Export
# ---------------------------------------------------------------------------

tab_templates, tab_canvas, tab_preview = st.tabs([
    "1️⃣ Template Library",
    "2️⃣ Builder Canvas",
    "3️⃣ Preview & Export",
])

# --- Templates Tab ---
with tab_templates:
    st.subheader("Ready-to-Use Blueprints")
    st.write("Load a template, then fine-tune it under Builder Canvas.")
    for template in templates:
        with st.container():
            st.markdown(
                f"""
                <div style='border:1px solid rgba(99,102,241,0.4); padding:1rem; border-radius:12px; margin-bottom:1rem;'>
                    <div style='display:flex;justify-content:space-between;align-items:center;'>
                        <div>
                            <h4 style='margin:0;color:#a78bfa;'>{template['icon']} {template['name']}</h4>
                            <small style='color:#94a3b8;'>{template['industry']}</small>
                            <p style='color:#cbd5e1;margin-top:0.5rem;'>{template['description']}</p>
                        </div>
                        <div>
                            <span style='color:#94a3b8;font-size:0.9rem;'>Blocks: {len(template['blocks'])}</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                f"📥 Load {template['name']}",
                key=f"load_template_{template['id']}",
                use_container_width=True,
            ):
                meta, blocks = instantiate_template(template["id"])
                st.session_state.builder_blocks = blocks
                st.session_state.agent_name = meta.get("default_agent_name", "custom_agent")
                st.session_state.agent_description = meta.get("description", "")
                st.session_state.selected_template_id = template["id"]
                st.session_state.agent_sector = meta.get("sector", st.session_state.agent_sector)
                st.session_state.agent_industry = meta.get("industry", st.session_state.agent_industry)
                st.session_state.agent_status = meta.get("status", st.session_state.agent_status)
                st.session_state.agent_emoji = meta.get("emoji", st.session_state.agent_emoji)
                st.session_state.agent_tagline = meta.get("tagline", st.session_state.agent_description)
                st.session_state.loaded_blueprint_slug = None
                st.success(f"Loaded template: {template['name']}")
                _rerun()

    st.markdown("### Your Deployed Blueprints")
    if not saved_blueprints:
        st.info("Deploy a blueprint to see it listed here.")
    else:
        for blueprint in saved_blueprints:
            meta = blueprint.get("metadata", {})
            slug = blueprint.get("slug") or meta.get("slug") or blueprint.get("agent_name", "")
            name = blueprint.get("agent_name", slug)
            tagline = meta.get("tagline") or meta.get("description") or blueprint.get("description") or "Custom agent blueprint."
            saved_at = blueprint.get("saved_at", "")
            launch_path = meta.get("launch_path", f"/agent_builder?blueprint={slug}")
            st.markdown(
                f"""
                <div style='border:1px solid rgba(16,185,129,0.4); padding:1rem; border-radius:12px; margin-bottom:0.8rem;'>
                    <div style='display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;'>
                        <div style='flex:3;'>
                            <h4 style='margin:0;color:#34d399;'>{meta.get("emoji", "✨")} {name}</h4>
                            <small style='color:#94a3b8;'>Slug: {slug} · Saved: {saved_at}</small>
                            <p style='color:#cbd5e1;margin-top:0.4rem;'>{tagline}</p>
                        </div>
                        <div style='flex:1;text-align:right;'>
                            <a href="{launch_path}" style='color:#60a5fa;' target="_self">Launch ↗</a>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"📂 Load {name}", key=f"load_bp_{slug}", use_container_width=True):
                _load_blueprint_into_state(blueprint)
                st.success(f"Loaded blueprint: {name}")
                _rerun()

# --- Builder Canvas Tab ---
with tab_canvas:
    left, right = st.columns([1, 2])

    with left:
        st.subheader("Add Blocks")
        selected_label = st.selectbox("Block Library", list(block_options.keys()))
        if st.button("➕ Add Block", use_container_width=True):
            new_block = create_block_instance(block_options[selected_label])
            st.session_state.builder_blocks.append(new_block)
            _rerun()

        st.markdown("---")
        st.subheader("Agent Details")
        st.session_state.agent_name = st.text_input(
            "Agent Name",
            value=st.session_state.agent_name,
            help="Used in blueprints and generated classes",
        )
        st.session_state.agent_description = st.text_area(
            "Agent Description",
            value=st.session_state.agent_description,
            height=120,
        )
        st.session_state.agent_sector = st.text_input(
            "Sector",
            value=st.session_state.agent_sector,
            help="Displayed on the dashboard (e.g., 🏦 Banking & Finance)",
        )
        st.session_state.agent_industry = st.text_input(
            "Industry / Line of Business",
            value=st.session_state.agent_industry,
            help="Shown under the Industry column.",
        )
        status_options = ["NEW", "Available", "Being Built", "WIP", "Coming Soon"]
        status_value = st.session_state.agent_status if st.session_state.agent_status in status_options else "NEW"
        st.session_state.agent_status = st.selectbox(
            "Status Badge",
            status_options,
            index=status_options.index(status_value),
        )
        st.session_state.agent_emoji = st.text_input(
            "Agent Emoji",
            value=st.session_state.agent_emoji,
            max_chars=4,
        )
        st.session_state.agent_tagline = st.text_input(
            "Tagline / Elevator Pitch",
            value=st.session_state.agent_tagline,
            help="Short blurb that appears in the dashboard table.",
        )
        st.markdown("---")
        st.info("Use the arrows on each block to reorder (drag-and-drop free).")

    with right:
        st.subheader("Pipeline Blocks")
        if not st.session_state.builder_blocks:
            st.warning("Load a template or add blocks to start building.")
        else:
            for idx, block in enumerate(st.session_state.builder_blocks):
                _render_block_editor(idx, block)

# --- Preview & Export Tab ---
with tab_preview:
    blocks = st.session_state.builder_blocks
    st.subheader("Pipeline Timeline")
    if not blocks:
        st.info("No blocks yet. Load a template or add blocks first.")
    else:
        timeline_html = "<ol style='line-height:1.8;'>"
        for idx, block in enumerate(blocks, start=1):
            state = "Enabled" if block.get("enabled", True) else "Disabled"
            timeline_html += (
                f"<li><strong>{block.get('alias', block['name'])}</strong>"
                f" <span style='color:#94a3b8;'>({block['category']} · {state})</span>"
                f"<br><small style='color:#64748b;'>{block['description']}</small></li>"
            )
        timeline_html += "</ol>"
        st.markdown(timeline_html, unsafe_allow_html=True)

        st.markdown("### Blueprint JSON")
        metadata = {
            "description": st.session_state.agent_description,
            "sector": st.session_state.agent_sector,
            "industry": st.session_state.agent_industry,
            "status": st.session_state.agent_status,
            "emoji": st.session_state.agent_emoji,
            "tagline": st.session_state.agent_tagline or st.session_state.agent_description,
            "template_id": st.session_state.get("selected_template_id"),
        }
        blueprint_payload = {
            "agent_name": st.session_state.agent_name,
            "description": st.session_state.agent_description,
            "template_id": st.session_state.get("selected_template_id"),
            "metadata": metadata,
            "blocks": blocks,
        }
        st.json(blueprint_payload)

        has_functions = any(block.get("function_ref") for block in blocks)
        col_save, col_deploy, col_download, col_code = st.columns(4)
        with col_save:
            if st.button("💾 Save Blueprint"):
                save_metadata = dict(metadata)
                path = save_blueprint(
                    st.session_state.agent_name,
                    blocks,
                    metadata=save_metadata,
                )
                st.session_state.loaded_blueprint_slug = save_metadata.get("slug")
                st.success(f"Blueprint saved to `{path}`")
        with col_deploy:
            if st.button("🚀 Deploy to Dashboard"):
                deploy_metadata = dict(metadata)
                path = save_blueprint(
                    st.session_state.agent_name,
                    blocks,
                    metadata=deploy_metadata,
                )
                slug = deploy_metadata.get("slug")
                st.session_state.loaded_blueprint_slug = slug
                st.success("Deployed! Refresh the landing page to see it in the Global AI Agent Library.")
        with col_download:
            st.download_button(
                label="📥 Download Blueprint",
                data=json.dumps(blueprint_payload, indent=2),
                file_name=f"{st.session_state.agent_name}_blueprint.json",
                mime="application/json",
            )
        with col_code:
            if st.button("🧪 Generate Implementation Code", disabled=not has_functions):
                lookup = get_function_lookup()
                selected_functions = []
                for block in blocks:
                    func_id = block.get("function_ref")
                    if func_id and func_id in lookup:
                        selected_functions.append(lookup[func_id])
                if not selected_functions:
                    st.error("No blocks are linked to a code function yet.")
                else:
                    code = generate_agent_code(
                        agent_name=st.session_state.agent_name,
                        selected_functions=selected_functions,
                        agent_description=st.session_state.agent_description,
                    )
                    st.session_state.generated_code = code
                    st.success("Implementation code generated below.")

    if st.session_state.get("generated_code"):
        st.markdown("---")
        st.subheader("Generated Agent Code (optional)")
        st.code(st.session_state.generated_code, language="python")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("💾 Save Agent Code"):
                path = save_agent_code(
                    st.session_state.agent_name,
                    st.session_state.generated_code,
                )
                st.success(f"Saved to `{path}`")
        with col_b:
            st.download_button(
                label="📥 Download Code",
                data=st.session_state.generated_code,
                file_name=f"{st.session_state.agent_name}_agent.py",
                mime="text/x-python",
            )

st.markdown("---")
st.caption("Need more power? Add ML Ops blocks, re-run, and deploy — still no code required.")
