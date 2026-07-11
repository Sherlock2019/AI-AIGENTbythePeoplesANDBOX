"""Default Ollama value ↔ Hugging Face model catalog (override with data/llm_profiles.py)."""
from __future__ import annotations

from typing import Dict, List

# Keys: model (HF repo id), type, gpu, notes, value (Ollama tag) — keep in sync with model_registry.LLM_MODEL_OPTIONS
model_full: List[Dict[str, str]] = [
    {
        "model": "microsoft/Phi-3-mini-4k-instruct",
        "type": "Compact instruction LLM",
        "gpu": "≤ 8 GB",
        "notes": "Fast lightweight narrative; happiest on ~8 GB RAM.",
        "value": "phi3:3.8b",
    },
    {
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "type": "Reasoning / valuation narrative",
        "gpu": "≥ 8 GB",
        "notes": "Strong default for CPU or modest GPU.",
        "value": "mistral:7b-instruct",
    },
    {
        "model": "google/gemma-2-2b-it",
        "type": "Instruction-tuned chat (light)",
        "gpu": "CPU OK",
        "notes": "Ultra-light assistant; runs almost anywhere.",
        "value": "gemma2:2b",
    },
    {
        "model": "google/gemma-2-9b-it",
        "type": "Instruction-tuned financial reports",
        "gpu": "≥ 12 GB",
        "notes": "Richer explanations; prefers discrete GPU.",
        "value": "gemma2:9b",
    },
    {
        "model": "meta-llama/Meta-Llama-3-8B-Instruct",
        "type": "Valuation summarization",
        "gpu": "≥ 12 GB",
        "notes": "Strong context; good accuracy vs. hallucination tradeoff.",
        "value": "llama3:8b-instruct",
    },
    {
        "model": "Qwen/Qwen2-7B-Instruct",
        "type": "Multilingual reasoning (VN + EN)",
        "gpu": "≥ 12 GB",
        "notes": "Excellent for mixed-language appraisal copy.",
        "value": "qwen2:7b-instruct",
    },
    {
        "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "type": "MoE premium reasoning",
        "gpu": "≥ 24 GB",
        "notes": "Heavy MoE; reserve 24–48 GB VRAM for comfort.",
        "value": "mixtral:8x7b-instruct",
    },
]

__all__ = ["model_full"]
