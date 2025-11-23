"""
Agent Builder Utilities — Templates, Blocks, and Code Generation
----------------------------------------------------------------

Provides a library of drag-and-drop blocks, ready-to-use templates,
and code generation helpers for the no-code Agent Builder.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Block Library (drag-and-drop building blocks)
# ---------------------------------------------------------------------------

BLOCK_LIBRARY: Dict[str, Dict[str, Any]] = {
    "data_ingest_csv": {
        "id": "data_ingest_csv",
        "name": "Data Ingestion · CSV / Sheets",
        "icon": "📥",
        "category": "Data Pipeline",
        "description": "Upload borrower, asset, or transaction data from CSV/Sheets/S3.",
        "default_config": {
            "source_type": "CSV Upload",
            "refresh_schedule": "manual",
            "schema_validation": True,
            "expected_rows": "auto",
        },
        "config_fields": [
            {
                "key": "source_type",
                "label": "Source Type",
                "type": "select",
                "options": ["CSV Upload", "Google Sheet", "S3 Bucket", "Database"],
                "help": "Where the raw data is fetched from.",
            },
            {
                "key": "refresh_schedule",
                "label": "Refresh Schedule",
                "type": "select",
                "options": ["manual", "hourly", "daily"],
            },
            {
                "key": "schema_validation",
                "label": "Schema Validation",
                "type": "checkbox",
                "help": "Reject files with missing or extra columns.",
            },
            {
                "key": "expected_rows",
                "label": "Expected Rows (per batch)",
                "type": "text",
                "help": "Helps detect incomplete uploads. Use 'auto' to infer.",
            },
        ],
    },
    "data_ingest_api": {
        "id": "data_ingest_api",
        "name": "Data Ingestion · API / CRM",
        "icon": "🔌",
        "category": "Data Pipeline",
        "description": "Pull structured data from CRMs, LOS, or REST APIs.",
        "default_config": {
            "endpoint": "https://api.example.com/loans",
            "auth_method": "API Key",
            "batch_size": 500,
            "retry_policy": "standard",
        },
        "config_fields": [
            {"key": "endpoint", "label": "Endpoint URL", "type": "text"},
            {
                "key": "auth_method",
                "label": "Auth Method",
                "type": "select",
                "options": ["API Key", "OAuth2", "Service Account"],
            },
            {"key": "batch_size", "label": "Batch Size", "type": "number"},
            {
                "key": "retry_policy",
                "label": "Retry Policy",
                "type": "select",
                "options": ["standard", "aggressive", "custom"],
            },
        ],
    },
    "data_cleaning": {
        "id": "data_cleaning",
        "name": "Data Cleaning & QA",
        "icon": "🧼",
        "category": "Data Pipeline",
        "description": "Handle missing values, outliers, and schema drift.",
        "default_config": {
            "missing_strategy": "median",
            "outlier_detection": True,
            "drift_alerts": True,
        },
        "config_fields": [
            {
                "key": "missing_strategy",
                "label": "Missing Value Strategy",
                "type": "select",
                "options": ["drop", "median", "mean", "model"],
            },
            {
                "key": "outlier_detection",
                "label": "Detect Outliers",
                "type": "checkbox",
            },
            {"key": "drift_alerts", "label": "Schema Drift Alerts", "type": "checkbox"},
        ],
    },
    "data_anonymization": {
        "id": "data_anonymization",
        "name": "Data Anonymization",
        "icon": "🛡️",
        "category": "Data Pipeline",
        "description": "Mask PII and sensitive features before AI processing.",
        "default_config": {
            "masking_level": "balanced",
            "hash_ids": True,
            "enable_tokenization": False,
        },
        "config_fields": [
            {
                "key": "masking_level",
                "label": "Masking Level",
                "type": "select",
                "options": ["light", "balanced", "strict"],
            },
            {"key": "hash_ids", "label": "Hash Identifiers", "type": "checkbox"},
            {"key": "enable_tokenization", "label": "Tokenize PII", "type": "checkbox"},
        ],
    },
    "feature_engineering": {
        "id": "feature_engineering",
        "name": "Feature Engineering",
        "icon": "🧬",
        "category": "Data Pipeline",
        "description": "Build ratios, aggregates, and explainable features.",
        "default_config": {
            "feature_sets": ["behavioral", "financial"],
            "lag_features": True,
            "explainability_tags": True,
        },
        "config_fields": [
            {
                "key": "feature_sets",
                "label": "Feature Sets",
                "type": "multiselect",
                "options": ["behavioral", "financial", "macro", "custom"],
            },
            {"key": "lag_features", "label": "Create Lag Features", "type": "checkbox"},
            {
                "key": "explainability_tags",
                "label": "Tag Features For Explainability",
                "type": "checkbox",
            },
        ],
    },
    "hf_generation": {
        "id": "hf_generation",
        "name": "LLM · HF Text Generation",
        "icon": "🤖",
        "category": "AI Reasoning",
        "description": "Use Hugging Face Agent Wrapper for narratives or advisories.",
        "function_ref": "hf_generate",
        "default_config": {
            "max_new_tokens": 400,
            "temperature": 0.35,
            "top_p": 0.9,
        },
        "config_fields": [
            {"key": "max_new_tokens", "label": "Max Tokens", "type": "number"},
            {"key": "temperature", "label": "Temperature", "type": "number"},
            {"key": "top_p", "label": "Top P", "type": "number"},
        ],
    },
    "hf_summarization": {
        "id": "hf_summarization",
        "name": "LLM · HF Summarization",
        "icon": "📝",
        "category": "AI Reasoning",
        "description": "Summaries, memos, and quick briefs using HF pipelines.",
        "function_ref": "hf_summarize",
        "default_config": {
            "max_length": 220,
            "min_length": 80,
        },
        "config_fields": [
            {"key": "max_length", "label": "Max Length", "type": "number"},
            {"key": "min_length", "label": "Min Length", "type": "number"},
        ],
    },
    "manager_failover": {
        "id": "manager_failover",
        "name": "Agent Manager · Multi-Engine",
        "icon": "🎯",
        "category": "AI Reasoning",
        "description": "Automatic failover (Local → Ollama → HF API) for mission-critical tasks.",
        "function_ref": "manager_generate_with_failover",
        "default_config": {
            "engine": "auto",
            "max_new_tokens": 256,
            "temperature": 0.2,
        },
        "config_fields": [
            {
                "key": "engine",
                "label": "Engine Preference",
                "type": "select",
                "options": ["auto", "local", "ollama", "hf_api"],
            },
            {"key": "max_new_tokens", "label": "Max Tokens", "type": "number"},
            {"key": "temperature", "label": "Temperature", "type": "number"},
        ],
    },
    "risk_scoring": {
        "id": "risk_scoring",
        "name": "Risk Scoring & Decisions",
        "icon": "📊",
        "category": "Decisioning",
        "description": "Credit, asset, or fraud risk scoring with thresholds.",
        "function_ref": "agent_credit_appraisal",
        "default_config": {
            "scorecard": "credit_appraisal",
            "decision_threshold": 0.62,
            "explanations": True,
        },
        "config_fields": [
            {
                "key": "scorecard",
                "label": "Scorecard",
                "type": "select",
                "options": ["credit_appraisal", "asset_appraisal", "fraud_detection"],
            },
            {
                "key": "decision_threshold",
                "label": "Decision Threshold",
                "type": "number",
                "help": "Approve if probability >= threshold.",
            },
            {"key": "explanations", "label": "Surface SHAP Explanations", "type": "checkbox"},
        ],
    },
    "model_training": {
        "id": "model_training",
        "name": "Model Training",
        "icon": "🏗️",
        "category": "ML Ops",
        "description": "Train models (XGBoost, LightGBM, HF) with experiment tracking.",
        "default_config": {
            "algorithm": "xgboost",
            "train_schedule": "on_demand",
            "auto_hyperparam": True,
        },
        "config_fields": [
            {
                "key": "algorithm",
                "label": "Algorithm",
                "type": "select",
                "options": ["xgboost", "lightgbm", "catboost", "transformer"],
            },
            {
                "key": "train_schedule",
                "label": "Retrain Schedule",
                "type": "select",
                "options": ["on_demand", "weekly", "monthly"],
            },
            {"key": "auto_hyperparam", "label": "Auto Hyperparameter Search", "type": "checkbox"},
        ],
    },
    "model_evaluation": {
        "id": "model_evaluation",
        "name": "Model Evaluation & Drift",
        "icon": "🧪",
        "category": "ML Ops",
        "description": "Track ROC, KS, PSI, and fairness metrics.",
        "default_config": {
            "monitor_metrics": ["roc_auc", "ks", "psi"],
            "alert_channels": ["email"],
        },
        "config_fields": [
            {
                "key": "monitor_metrics",
                "label": "Metrics",
                "type": "multiselect",
                "options": ["roc_auc", "ks", "psi", "f1", "fairness"],
            },
            {
                "key": "alert_channels",
                "label": "Alert Channels",
                "type": "multiselect",
                "options": ["email", "slack", "ops_hook"],
            },
        ],
    },
    "report_builder": {
        "id": "report_builder",
        "name": "Narrative Report Builder",
        "icon": "📄",
        "category": "Outputs",
        "description": "Generate PDF/HTML reports with recommendations.",
        "default_config": {
            "format": ["pdf", "html"],
            "branding": "Open AIgents",
            "include_explanations": True,
        },
        "config_fields": [
            {
                "key": "format",
                "label": "Output Formats",
                "type": "multiselect",
                "options": ["pdf", "html", "json"],
            },
            {"key": "branding", "label": "Branding / Footer", "type": "text"},
            {
                "key": "include_explanations",
                "label": "Include Explainability Section",
                "type": "checkbox",
            },
        ],
    },
    "dashboard_output": {
        "id": "dashboard_output",
        "name": "Dashboard & API Output",
        "icon": "📊",
        "category": "Outputs",
        "description": "Expose the agent through dashboards, REST, or Streamlit.",
        "default_config": {
            "destinations": ["Streamlit", "REST"],
            "cache_results": True,
            "role_based_access": True,
        },
        "config_fields": [
            {
                "key": "destinations",
                "label": "Destinations",
                "type": "multiselect",
                "options": ["Streamlit", "REST", "Webhook", "Notebook"],
            },
            {"key": "cache_results", "label": "Cache Responses", "type": "checkbox"},
            {"key": "role_based_access", "label": "Role-Based Access", "type": "checkbox"},
        ],
    },
}

BLOCK_LOOKUP = {block_id: deepcopy(cfg) for block_id, cfg in BLOCK_LIBRARY.items()}
BLUEPRINT_DIR = Path("agents/blueprints")


def _ensure_blueprint_dir() -> Path:
    path = BLUEPRINT_DIR
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug or f"agent-{uuid.uuid4().hex[:6]}"

# ---------------------------------------------------------------------------
# Ready-to-use Templates
# ---------------------------------------------------------------------------

AGENT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "credit_appraisal",
        "name": "Credit Appraisal Agent",
        "icon": "🏦",
        "industry": "Banking & Finance",
        "sector": "🏦 Banking & Finance",
        "status": "NEW",
        "emoji": "💳",
        "tagline": "Loan origination + risk scoring with explainable credit decisions.",
        "description": "Loan origination + risk scoring with explainable credit decisions.",
        "default_agent_name": "credit_appraisal_agent",
        "blocks": [
            {"block_id": "data_ingest_csv", "config_overrides": {"source_type": "CSV Upload"}},
            {"block_id": "data_cleaning"},
            {"block_id": "data_anonymization"},
            {"block_id": "feature_engineering"},
            {"block_id": "risk_scoring", "config_overrides": {"scorecard": "credit_appraisal"}},
            {"block_id": "report_builder"},
            {"block_id": "dashboard_output"},
        ],
    },
    {
        "id": "asset_appraisal",
        "name": "Asset Valuation Agent",
        "icon": "🏢",
        "industry": "Asset & Real Estate",
        "sector": "🏢 Asset & Real Estate",
        "status": "NEW",
        "emoji": "🏢",
        "tagline": "Collateral valuation with market comps and HF narrative reports.",
        "description": "Collateral valuation with market comps and HF narrative reports.",
        "default_agent_name": "asset_appraisal_agent",
        "blocks": [
            {"block_id": "data_ingest_api", "config_overrides": {"endpoint": "https://api.example.com/assets"}},
            {"block_id": "data_cleaning"},
            {"block_id": "feature_engineering", "config_overrides": {"feature_sets": ["financial", "macro"]}},
            {"block_id": "hf_summarization"},
            {"block_id": "report_builder", "config_overrides": {"format": ["pdf"]}},
            {"block_id": "dashboard_output"},
        ],
    },
    {
        "id": "anti_fraud",
        "name": "Anti-Fraud + KYC Agent",
        "icon": "🕵️",
        "industry": "Security",
        "sector": "🛡️ Security & Trust",
        "status": "NEW",
        "emoji": "🛡️",
        "tagline": "Ingest transactions, anonymize data, and run fraud scoring with alerts.",
        "description": "Ingests transactions, anonymizes data, and runs fraud scoring with alerts.",
        "default_agent_name": "anti_fraud_guardian",
        "blocks": [
            {"block_id": "data_ingest_api"},
            {"block_id": "data_cleaning", "config_overrides": {"outlier_detection": True}},
            {"block_id": "data_anonymization", "config_overrides": {"masking_level": "strict"}},
            {"block_id": "risk_scoring", "config_overrides": {"scorecard": "fraud_detection"}},
            {"block_id": "manager_failover"},
            {"block_id": "dashboard_output", "config_overrides": {"destinations": ["REST", "Webhook"]}},
        ],
    },
]


def _deepcopy_block(block_id: str) -> Dict[str, Any]:
    if block_id not in BLOCK_LOOKUP:
        raise ValueError(f"Unknown block id: {block_id}")
    return deepcopy(BLOCK_LOOKUP[block_id])


def create_block_instance(
    block_id: str,
    *,
    config_overrides: Optional[Dict[str, Any]] = None,
    alias: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a concrete block instance with its own UUID."""
    base = _deepcopy_block(block_id)
    instance = {
        "instance_id": uuid.uuid4().hex[:8],
        "block_id": block_id,
        "alias": alias or base["name"],
        "name": base["name"],
        "icon": base.get("icon", ""),
        "category": base["category"],
        "description": base["description"],
        "config_fields": base.get("config_fields", []),
        "config": {**base.get("default_config", {}), **(config_overrides or {})},
        "enabled": True,
        "notes": "",
        "function_ref": base.get("function_ref"),
    }
    return instance


def get_block_library() -> List[Dict[str, Any]]:
    """Return block definitions sorted by category then name."""
    return sorted(
        [_deepcopy_block(block_id) for block_id in BLOCK_LIBRARY],
        key=lambda blk: (blk["category"], blk["name"]),
    )


def get_agent_templates() -> List[Dict[str, Any]]:
    """Return ready-to-use agent templates."""
    return deepcopy(AGENT_TEMPLATES)


def instantiate_template(template_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Return template metadata and instantiated blocks."""
    template = next((t for t in AGENT_TEMPLATES if t["id"] == template_id), None)
    if not template:
        raise ValueError(f"Unknown template: {template_id}")
    blocks = [
        create_block_instance(
            block_cfg["block_id"],
            config_overrides=block_cfg.get("config_overrides"),
            alias=block_cfg.get("alias"),
        )
        for block_cfg in template.get("blocks", [])
    ]
    return deepcopy(template), blocks


def save_blueprint(
    agent_name: str,
    blocks: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
) -> Path:
    """Persist a blueprint (no-code pipeline) to disk as JSON."""
    output_path = Path(output_dir) if output_dir else _ensure_blueprint_dir()
    output_path.mkdir(parents=True, exist_ok=True)
    metadata = metadata or {}
    slug = metadata.get("slug") or _slugify(agent_name)
    metadata["slug"] = slug
    metadata.setdefault("status", "NEW")
    metadata.setdefault("sector", "🛠️ AI Tools & Infrastructure")
    metadata.setdefault("industry", "🧩 Custom Blueprints")
    metadata.setdefault("emoji", "✨")
    metadata.setdefault("tagline", metadata.get("description") or "")
    metadata.setdefault("launch_path", f"/agent_builder?blueprint={slug}")
    blueprint = {
        "agent_name": agent_name,
        "slug": slug,
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "metadata": metadata,
        "blocks": blocks,
    }
    file_path = output_path / f"{slug}.json"
    with file_path.open("w") as f:
        json.dump(blueprint, f, indent=2)
    return file_path


def list_saved_blueprints() -> List[Dict[str, Any]]:
    """Return all saved blueprints with metadata."""
    output_path = _ensure_blueprint_dir()
    blueprints: List[Dict[str, Any]] = []
    for blueprint_path in sorted(output_path.glob("*.json")):
        try:
            with blueprint_path.open() as f:
                data = json.load(f)
            data["_path"] = str(blueprint_path)
            blueprints.append(data)
        except Exception:
            continue
    return blueprints


def load_blueprint(identifier: str) -> Dict[str, Any]:
    """Load a blueprint by slug or agent name."""
    identifier = identifier.strip().lower()
    for blueprint in list_saved_blueprints():
        slug = (blueprint.get("slug") or blueprint.get("metadata", {}).get("slug") or "").lower()
        name = (blueprint.get("agent_name") or "").lower()
        if identifier in {slug, name}:
            return blueprint
    candidate = _ensure_blueprint_dir() / f"{identifier}.json"
    if candidate.exists():
        with candidate.open() as f:
            data = json.load(f)
        data["_path"] = str(candidate)
        return data
    raise FileNotFoundError(f"Blueprint '{identifier}' not found")


# ---------------------------------------------------------------------------
# Function Catalog (used for code generation)
# ---------------------------------------------------------------------------

HF_FUNCTIONS = {
    "generate": {
        "name": "generate",
        "description": "Text generation from prompt",
        "source": "hf_agent_wrapper",
        "parameters": ["prompt", "max_new_tokens", "temperature", "top_p", "top_k"],
        "returns": "str",
        "category": "Text Generation",
    },
    "summarize": {
        "name": "summarize",
        "description": "Summarize long text",
        "source": "hf_agent_wrapper",
        "parameters": ["text", "max_length", "min_length"],
        "returns": "str",
        "category": "Text Processing",
    },
    "qa": {
        "name": "qa",
        "description": "Question answering from context",
        "source": "hf_agent_wrapper",
        "parameters": ["question", "context"],
        "returns": "dict",
        "category": "Text Processing",
    },
    "embedding": {
        "name": "embedding",
        "description": "Generate text embeddings",
        "source": "hf_agent_wrapper",
        "parameters": ["text"],
        "returns": "list",
        "category": "Embeddings",
    },
    "translate": {
        "name": "translate",
        "description": "Translate text between languages",
        "source": "hf_agent_wrapper",
        "parameters": ["text", "src_lang", "tgt_lang"],
        "returns": "str",
        "category": "Text Processing",
    },
    "caption": {
        "name": "caption",
        "description": "Generate image captions",
        "source": "hf_agent_wrapper",
        "parameters": ["image"],
        "returns": "str",
        "category": "Vision",
    },
    "classify": {
        "name": "classify",
        "description": "Text classification/sentiment analysis",
        "source": "hf_agent_wrapper",
        "parameters": ["text", "return_all_scores"],
        "returns": "dict",
        "category": "Classification",
    },
}

AGENT_MANAGER_FUNCTIONS = {
    "generate_with_failover": {
        "name": "generate_with_failover",
        "description": "Text generation with automatic failover (Local → Ollama → HF API)",
        "source": "agent_manager",
        "parameters": ["prompt", "max_new_tokens", "temperature", "engine"],
        "returns": "dict",
        "category": "Text Generation",
    },
    "summarize_with_failover": {
        "name": "summarize_with_failover",
        "description": "Summarization with failover support",
        "source": "agent_manager",
        "parameters": ["text", "max_length", "min_length", "engine"],
        "returns": "dict",
        "category": "Text Processing",
    },
    "qa_with_failover": {
        "name": "qa_with_failover",
        "description": "QA with failover support",
        "source": "agent_manager",
        "parameters": ["question", "context", "engine"],
        "returns": "dict",
        "category": "Text Processing",
    },
    "embedding_with_failover": {
        "name": "embedding_with_failover",
        "description": "Embeddings with failover support",
        "source": "agent_manager",
        "parameters": ["text", "engine"],
        "returns": "dict",
        "category": "Embeddings",
    },
}

EXISTING_AGENT_FUNCTIONS = {
    "credit_score": {
        "name": "calculate_credit_score",
        "description": "Calculate credit score (300-850) for loan applications",
        "source": "credit_score_agent",
        "parameters": ["applicant_data"],
        "returns": "dict",
        "category": "Banking & Finance",
    },
    "credit_appraisal": {
        "name": "appraise_credit",
        "description": "AI-powered credit appraisal with explainability",
        "source": "credit_appraisal_agent",
        "parameters": ["applicant_data", "loan_amount"],
        "returns": "dict",
        "category": "Banking & Finance",
    },
    "asset_valuation": {
        "name": "valuate_asset",
        "description": "Market-driven asset/collateral valuation",
        "source": "asset_appraisal_agent",
        "parameters": ["asset_data"],
        "returns": "dict",
        "category": "Banking & Finance",
    },
    "fraud_detection": {
        "name": "detect_fraud",
        "description": "Fraud scoring and detection",
        "source": "anti_fraud_kyc_agent",
        "parameters": ["transaction_data", "user_profile"],
        "returns": "dict",
        "category": "Security",
    },
    "legal_compliance": {
        "name": "check_compliance",
        "description": "Regulatory compliance, sanctions, PEP checks",
        "source": "legal_compliance_agent",
        "parameters": ["entity_data", "check_type"],
        "returns": "dict",
        "category": "Legal",
    },
    "real_estate_evaluation": {
        "name": "evaluate_property",
        "description": "Real estate property evaluation with market analysis",
        "source": "real_estate_evaluator",
        "parameters": ["property_data", "location"],
        "returns": "dict",
        "category": "Real Estate",
    },
}


def get_all_available_functions() -> Dict[str, List[Dict[str, Any]]]:
    """Get all available functions organized by category."""
    all_functions: Dict[str, List[Dict[str, Any]]] = {}

    for func_name, func_info in HF_FUNCTIONS.items():
        category = func_info["category"]
        all_functions.setdefault(category, []).append(
            {**func_info, "id": f"hf_{func_name}", "display_name": f"HF: {func_info['name']}"}
        )

    for func_name, func_info in AGENT_MANAGER_FUNCTIONS.items():
        category = func_info["category"]
        all_functions.setdefault(category, []).append(
            {
                **func_info,
                "id": f"manager_{func_name}",
                "display_name": f"Manager: {func_info['name']}",
            }
        )

    for func_name, func_info in EXISTING_AGENT_FUNCTIONS.items():
        category = func_info["category"]
        all_functions.setdefault(category, []).append(
            {
                **func_info,
                "id": f"agent_{func_name}",
                "display_name": f"{func_info['source']}: {func_info['name']}",
            }
        )

    return all_functions


def get_function_lookup() -> Dict[str, Dict[str, Any]]:
    """Flatten function catalog keyed by function id."""
    lookup: Dict[str, Dict[str, Any]] = {}
    for functions in get_all_available_functions().values():
        for func in functions:
            lookup[func["id"]] = func
    return lookup


# ---------------------------------------------------------------------------
# Code generation helpers (legacy advanced mode)
# ---------------------------------------------------------------------------


def generate_agent_code(
    agent_name: str,
    selected_functions: List[Dict[str, Any]],
    agent_description: str = "",
) -> str:
    """Generate Python code for a new agent from selected functions."""

    imports = {"from typing import Any, Dict, Optional"}
    sources = set()
    for func in selected_functions:
        source = func.get("source", "")
        if "hf_agent_wrapper" in source or func["id"].startswith("hf_"):
            sources.add("hf")
        if "agent_manager" in source or func["id"].startswith("manager_"):
            sources.add("manager")
        if func["id"].startswith("agent_"):
            sources.add("existing_agents")

    if "hf" in sources:
        imports.add("from services.api.hf_agent_wrapper import HuggingFaceAgent")
    if "manager" in sources:
        imports.add("from services.api.agent_manager import get_agent_manager")
    if "existing_agents" in sources:
        imports.add("from services.api.routers.credit_score_agents import run_credit_score_agent")
        imports.add("from services.api.routers.credit_agents import run_credit_agent")
        imports.add("from services.api.routers.asset_agents import run_asset_agent")
        imports.add(
            "from services.api.routers.legal_compliance_agents import run_legal_compliance_agent"
        )

    imports_sorted = sorted(imports)

    class_code = f'''"""
{agent_name.replace("_", " ").title()} Agent
{"=" * 60}

{agent_description or f"Custom agent built from {len(selected_functions)} function(s)"}

Built with Agent Builder from:
{chr(10).join(f"  - {func.get('display_name', func['name'])}" for func in selected_functions)}
"""

{chr(10).join(imports_sorted)}


class {agent_name.replace("_", "").title()}Agent:
    """
    Custom agent built from selected functions.
    """
    
    def __init__(self):
        """Initialize the agent with required components."""
'''

    init_body = []
    if "hf" in sources:
        init_body.append("        self.hf_agent = HuggingFaceAgent()")
    if "manager" in sources:
        init_body.append("        self.agent_manager = get_agent_manager()")

    if init_body:
        class_code += "\n" + "\n".join(init_body)
    else:
        class_code += "        pass"

    class_code += "\n"

    for func in selected_functions:
        func_id = func["id"]
        func_name = func["name"]
        func_params = func.get("parameters", [])
        func_desc = func.get("description", "")
        func_returns = func.get("returns", "Any")
        method_name = (
            func_name.replace("_with_failover", "")
            .replace("calculate_", "")
            .replace("appraise_", "")
            .replace("valuate_", "")
            .replace("detect_", "")
            .replace("check_", "")
            .replace("evaluate_", "")
        )

        method_code = f'''
    def {method_name}(self, {", ".join(func_params)}):
        """
        {func_desc}
        
        Args:
{chr(10).join(f"            {param}: Parameter for {param}" for param in func_params)}
        
        Returns:
            {func_returns}: Result from {func.get('display_name', func_name)}
        """
'''

        if func_id.startswith("hf_"):
            task_name = func_name
            method_code += f'''        return self.hf_agent.run(
            task="{task_name}",
            {", ".join(f"{param}={param}" for param in func_params)}
        )
'''
        elif func_id.startswith("manager_"):
            task_name = func_name.replace("_with_failover", "")
            engine_param = "engine=engine" if "engine" in func_params else ""
            other_params = [p for p in func_params if p != "engine"]
            params_str = ", ".join(f"{p}={p}" for p in other_params)
            if engine_param and params_str:
                params_str += f", {engine_param}"
            elif engine_param:
                params_str = engine_param
            method_code += f'''        return self.agent_manager.run(
            task="{task_name}",
            {params_str}
        )
'''
        elif func_id.startswith("agent_"):
            agent_type = func_id.replace("agent_", "")
            method_code += "        # TODO: Integrate with existing agent router\n"
            method_code += "        return {\"status\": \"not_implemented\"}\n"

        class_code += method_code

    class_code += f'''
    def run(self, task: str, **kwargs) -> Any:
        """
        Universal entry point that routes to appropriate function.
        
        Args:
            task: Task name (one of: {", ".join(f.get("name", "") for f in selected_functions)})
            **kwargs: Task-specific parameters
        
        Returns:
            Result from the selected task function
        """
        task_map = {{
'''

    for func in selected_functions:
        func_name = func["name"]
        method_name = (
            func_name.replace("_with_failover", "")
            .replace("calculate_", "")
            .replace("appraise_", "")
            .replace("valuate_", "")
            .replace("detect_", "")
            .replace("check_", "")
            .replace("evaluate_", "")
        )
        class_code += f'            "{func_name}": self.{method_name},\n'

    class_code += "        }\n        \n        if task not in task_map:\n            raise ValueError(f\"Unknown task: {task}. Available tasks: {list(task_map.keys())}\")\n        \n        return task_map[task](**kwargs)\n"

    return class_code


def save_agent_code(agent_name: str, code: str, output_dir: str = "agents") -> str:
    """Save generated agent code to a file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    agent_dir = output_path / agent_name
    agent_dir.mkdir(exist_ok=True)

    file_path = agent_dir / "agent.py"
    with file_path.open("w") as f:
        f.write(code)

    init_file = agent_dir / "__init__.py"
    with init_file.open("w") as f:
        f.write(f'"""\n{agent_name.replace("_", " ").title()} Agent\n"""\n\n')
        f.write(f'from .agent import {agent_name.replace("_", "").title()}Agent\n')
        f.write(f'\n__all__ = ["{agent_name.replace("_", "").title()}Agent"]\n')

    return str(file_path)
