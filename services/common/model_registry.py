"""Shared catalog of local + Hugging Face models for every agent."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List
from services.common.llm_profiles_loader import get_llm_profiles

# Ensure project root is in Python path for data module imports
try:
    _PROJECT_ROOT = Path(__file__).resolve().parents[2]  # services/common -> project root
except NameError:
    # Fallback if __file__ is not available (shouldn't happen in normal execution)
    _PROJECT_ROOT = Path.cwd()
_PROJECT_ROOT_STR = str(_PROJECT_ROOT.resolve())
if _PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_STR)

model_full = get_llm_profiles()

CPU_FRIENDLY_TIERS = {"cpu", "balanced"}
HF_MODEL_TABLE: List[Dict[str, str]] = [
    {
        "Model": entry["model"],
        "Type": entry["type"],
        "GPU": entry["gpu"],
        "Notes": entry["notes"],
        "Value": entry["value"],
    }
    for entry in model_full
]

HF_MODEL_LOOKUP = {row["Model"]: row for row in HF_MODEL_TABLE}

LLM_MODEL_OPTIONS: List[Dict[str, str]] = [
    {
        "label": "CPU — phi3:3.8b · Phi‑3 Mini (8 GB sweet spot)",
        "value": "phi3:3.8b",
        "hint": "Happiest on 8 GB RAM; great for fast narrative stubs.",
        "tier": "cpu",
    },
    {
        "label": "CPU/GPU — mistral:7b-instruct · Mistral 7B",
        "value": "mistral:7b-instruct",
        "hint": "Still usable on beefy CPUs or modest GPUs; solid default.",
        "tier": "balanced",
    },
    {
        "label": "CPU — gemma2:2b · Gemma‑2 2B (chat/light reasoning)",
        "value": "gemma2:2b",
        "hint": "Ultra-light assistant model; runs anywhere for stage Q&A.",
        "tier": "cpu",
    },
    {
        "label": "GPU — gemma2:9b · Gemma‑2 9B",
        "value": "gemma2:9b",
        "hint": "Sweet spot for richer explainability; needs ≥12 GB VRAM.",
        "tier": "gpu",
    },
    {
        "label": "GPU — llama3:8b-instruct · LLaMA‑3 8B",
        "value": "llama3:8b-instruct",
        "hint": "Excellent context window; prefers ≥12 GB VRAM.",
        "tier": "gpu",
    },
    {
        "label": "GPU — qwen2:7b-instruct · Qwen‑2 7B",
        "value": "qwen2:7b-instruct",
        "hint": "Multilingual nuance, similar ≥12 GB GPU appetite.",
        "tier": "gpu",
    },
    {
        "label": "GPU Heavy — mixtral:8x7b-instruct · Mixtral 8×7B",
        "value": "mixtral:8x7b-instruct",
        "hint": "MoE heavy hitter; reserve ≥24 GB VRAM (A10/L40), ideally 48 GB.",
        "tier": "gpu_large",
    },
]

VALUE_TO_HF_MODEL = {entry["value"]: entry["model"] for entry in model_full}

MODEL_TEMPLATE_SET = {
    "cpu": [
        {
            "id": "phi3:3.8b",
            "label": "phi3:3.8b · Phi‑3 Mini",
            "description": "Happiest on ~8 GB RAM; great for quick narrative stubs.",
        },
        {
            "id": "mistral:7b-instruct",
            "label": "mistral:7b-instruct · Mistral 7B",
            "description": "Still usable on beefy CPUs or modest GPUs; solid default.",
        },
        {
            "id": "gemma2:2b",
            "label": "gemma2:2b · Gemma‑2 2B",
            "description": "Ultra-light assistant / chat model; runs anywhere.",
        },
        {
            "id": "tabular_baseline",
            "label": "LightAutoML / LightGBM / LR",
            "description": "Pure CPU baselines powering FMV + credit scores.",
        },
    ],
    "gpu": [
        {
            "id": "gemma2:9b",
            "label": "gemma2:9b · Gemma‑2 9B",
            "description": "Rich explainability; needs ≥12 GB VRAM.",
        },
        {
            "id": "llama3:8b-instruct",
            "label": "llama3:8b-instruct · LLaMA‑3 8B",
            "description": "Excellent context window; prefers ≥12 GB VRAM.",
        },
        {
            "id": "qwen2:7b-instruct",
            "label": "qwen2:7b-instruct · Qwen‑2 7B",
            "description": "Multilingual nuance; similar ≥12 GB GPU appetite.",
        },
        {
            "id": "mixtral:8x7b-instruct",
            "label": "mixtral:8x7b-instruct · Mixtral 8×7B",
            "description": "MoE heavy hitter; reserve ≥24 GB VRAM (A10/L40), ideally 48 GB.",
        },
    ],
}


def get_hf_models() -> List[Dict[str, str]]:
    """Return the canonical HF model table."""
    return list(HF_MODEL_TABLE)


def get_llm_models(cpu_first: bool = True) -> List[Dict[str, str]]:
    """Return the local/Ollama-compatible models (CPU tiers first by default)."""
    models = list(LLM_MODEL_OPTIONS)
    if not cpu_first:
        return models
    cpu_like = [m for m in models if m["tier"] in CPU_FRIENDLY_TIERS]
    gpu_like = [m for m in models if m["tier"] not in CPU_FRIENDLY_TIERS]
    return cpu_like + gpu_like


def get_llm_lookup(cpu_first: bool = True) -> Dict[str, Dict[str, str]]:
    """Convenience lookup bundle for Streamlit selectboxes."""
    ordered = get_llm_models(cpu_first=cpu_first)
    labels = [m["label"] for m in ordered]
    value_by_label = {m["label"]: m["value"] for m in ordered}
    hint_by_label = {m["label"]: m["hint"] for m in ordered}
    return {
        "ordered": ordered,
        "labels": labels,
        "value_by_label": value_by_label,
        "hint_by_label": hint_by_label,
        "tier_by_label": {m["label"]: m["tier"] for m in ordered},
    }


def get_model_template_set() -> Dict[str, List[Dict[str, str]]]:
    """Expose the curated CPU/GPU template list."""
    return MODEL_TEMPLATE_SET


def get_llm_display_info(value: str | None) -> Dict[str, str] | None:
    """Return formatted display text + notes for a given LLM value."""
    if not value:
        return None
    hf_name = VALUE_TO_HF_MODEL.get(value)
    if not hf_name:
        return None
    info = HF_MODEL_LOOKUP.get(hf_name)
    if not info:
        return None
    display = f"{info['Model']} — {info['Type']} — GPU: {info['GPU']}"
    notes = info.get("Notes", "")
    return {"display": display, "notes": notes}
