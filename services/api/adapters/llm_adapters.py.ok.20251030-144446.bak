# services/api/adapters/llm_adapters.py
from __future__ import annotations

LLM_CATALOG = [
    {"label": "Phi-3 Mini (3.8B) — CPU OK", "value": "phi3:3.8b", "hint": "CPU 8GB RAM"},
    {"label": "Mistral 7B Instruct — CPU slow / GPU OK", "value": "mistral:7b-instruct", "hint": "CPU 16GB / GPU 8GB+"},
    {"label": "Gemma-2 7B — CPU slow / GPU OK", "value": "gemma2:7b", "hint": "CPU 16GB / GPU"},
    {"label": "LLaMA-3 8B — GPU recommended", "value": "llama3:8b-instruct", "hint": "GPU 12GB+"},
    {"label": "Qwen2 7B — GPU recommended", "value": "qwen2:7b-instruct", "hint": "GPU 12GB+"},
    {"label": "Mixtral 8x7B — GPU only (big)", "value": "mixtral:8x7b-instruct", "hint": "GPU 24–48GB"},
]

def choose_backend(model_value: str) -> dict:
    # Placeholder adapter selection
    return {"provider": "ollama_or_local", "model": model_value}
