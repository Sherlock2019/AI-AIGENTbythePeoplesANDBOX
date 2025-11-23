# 🛠️ HF Tools Box — Quick Reference

## What You Have

### 1. **HF Agent Wrapper** (`hf_agent_wrapper.py`)
**Pure HuggingFace operations** - Local HF models + HF API

### 2. **Agent Manager** (`agent_manager.py`)
**Multi-engine with failover** - HF + Ollama + Local models

---

## 🚀 Quick Usage

### HF Agent Wrapper (HF-only)

```python
from services.api.hf_agent_wrapper import HuggingFaceAgent

hf = HuggingFaceAgent()

# All tasks
hf.run(task="generate", prompt="Hello")
hf.run(task="summarize", text="...")
hf.run(task="qa", question="...", context="...")
hf.run(task="embedding", text="...")
hf.run(task="translate", text="...", tgt_lang="fr")
hf.run(task="classify", text="...")
hf.run(task="image_caption", image="...")
```

### Agent Manager (Multi-engine)

```python
from services.api.agent_manager import get_agent_manager

manager = get_agent_manager()

# Same interface, but with automatic failover
manager.run(task="generate", prompt="Hello")
# Tries: local → ollama → hf_api automatically
```

---

## 📋 Task Reference

| Task | Parameters | Returns |
|------|------------|---------|
| `generate` | `prompt`, `max_new_tokens`, `temperature` | `str` |
| `summarize` | `text`, `max_length`, `min_length` | `str` |
| `qa` | `question`, `context` | `dict` with `answer` |
| `embedding` | `text` | `list` (vector) |
| `translate` | `text`, `tgt_lang`, `src_lang` | `str` |
| `classify` | `text` | `dict` with `label`, `score` |
| `image_caption` | `image` | `str` |

---

## 🎯 When to Use Which?

**Use HF Agent Wrapper:**
- ✅ Need specific HF models
- ✅ HF-only operations
- ✅ Lightweight solution

**Use Agent Manager:**
- ✅ Need failover (local → ollama → hf_api)
- ✅ Multi-engine support
- ✅ Offline capability

---

## 🧪 Test It

```bash
# Test HF Agent Wrapper
python scripts/test_hf_agent_wrapper.py

# Test Agent Manager
python scripts/test_agent_manager.py
```

---

## 📚 Full Docs

- **HF Tools Guide**: `HF_TOOLS_BOX_GUIDE.md`
- **Agent Manager**: `AGENT_MANAGER_QUICKSTART.md`
- **Code**: `services/api/hf_agent_wrapper.py`
- **Code**: `services/api/agent_manager.py`
