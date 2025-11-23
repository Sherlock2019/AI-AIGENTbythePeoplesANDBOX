# 🤖 HF Tools Box Agents — Complete Guide

## 📦 What We Have: Two Complementary Tools

You have **two powerful tools** that work together:

### 1. **HF Agent Wrapper** (`hf_agent_wrapper.py`)
- **Purpose**: HuggingFace-specific operations (HF local models + HF API)
- **Focus**: Pure HuggingFace ecosystem
- **Use when**: You specifically need HF models/pipelines

### 2. **Agent Manager** (`agent_manager.py`) 
- **Purpose**: Unified interface for ALL model types (HF + Ollama + Local)
- **Focus**: Multi-engine with automatic failover
- **Use when**: You want flexibility across different model providers

---

## 🎯 When to Use Which?

### Use **HF Agent Wrapper** when:
- ✅ You only need HuggingFace models
- ✅ You want a lightweight, HF-focused solution
- ✅ You're working with HF-specific pipelines
- ✅ You want direct HF API access

### Use **Agent Manager** when:
- ✅ You want automatic failover (Local → Ollama → HF API)
- ✅ You need to support multiple model providers
- ✅ You want intelligent engine selection
- ✅ You need offline capability (Ollama/local models)

---

## 🚀 Using HF Agent Wrapper

### Basic Usage

```python
from services.api.hf_agent_wrapper import HuggingFaceAgent

# Initialize
hf = HuggingFaceAgent(
    local_model="microsoft/phi-2",  # Optional: use local model
    api_model="mistralai/Mistral-7B-Instruct-v0.2",  # HF API model
    hf_token="hf_your_token",  # Optional
    device="cpu"  # or "cuda"
)

# Text Generation
result = hf.run(task="generate", prompt="Hello world", max_new_tokens=200)
print(result)

# Summarization
result = hf.run(task="summarize", text="Long document...", max_length=150)
print(result)

# Question Answering
result = hf.run(task="qa", question="What is this?", context="Document...")
print(result)

# Embeddings
result = hf.run(task="embedding", text="Text to embed")
print(result)

# Translation
result = hf.run(task="translate", text="Hello", tgt_lang="fr")
print(result)

# Image Captioning
result = hf.run(task="image_caption", image="path/to/image.jpg")
print(result)

# Classification
result = hf.run(task="classify", text="I love this!")
print(result)
```

### Advanced: Custom Models

```python
# Use specific models for each task
hf = HuggingFaceAgent()

# Custom summarization model
summary = hf.run(
    task="summarize",
    text="...",
    model="facebook/bart-large-cnn"  # Override default
)

# Custom QA model
answer = hf.run(
    task="qa",
    question="...",
    context="...",
    model="deepset/roberta-base-squad2"  # Override default
)

# Custom embedding model
embedding = hf.run(
    task="embedding",
    text="...",
    model="sentence-transformers/all-mpnet-base-v2"  # Override default
)
```

---

## 🔄 Integration: Using Both Together

You can use **both** tools together for maximum flexibility:

```python
from services.api.hf_agent_wrapper import HuggingFaceAgent
from services.api.agent_manager import get_agent_manager

# HF-specific operations
hf_agent = HuggingFaceAgent()

# Multi-engine operations with failover
agent_manager = get_agent_manager()

# Use HF Agent for HF-specific tasks
hf_result = hf_agent.run(task="summarize", text="...")

# Use Agent Manager for tasks that need failover
manager_result = agent_manager.run(
    task="generate",
    prompt="...",
    engine="auto"  # Will try local → ollama → hf_api
)
```

---

## 📋 Complete Task Reference

### HF Agent Wrapper Tasks

| Task | Method | Parameters | Returns |
|------|--------|------------|---------|
| `generate` | `_generate()` | `prompt`, `max_new_tokens`, `temperature` | `str` |
| `summarize` | `_summarize()` | `text`, `max_length`, `min_length`, `model` | `str` |
| `qa` | `_qa()` | `question`, `context`, `model` | `dict` |
| `embedding` | `_embedding()` | `text`, `model`, `normalize` | `list` |
| `translate` | `_translate()` | `text`, `tgt_lang`, `src_lang`, `model` | `str` |
| `image_caption` | `_image_caption()` | `image`, `model` | `str` |
| `classify` | `_classify()` | `text`, `model`, `return_all_scores` | `dict` |

---

## 💡 Real-World Examples

### Example 1: Document Processing Pipeline

```python
from services.api.hf_agent_wrapper import HuggingFaceAgent

hf = HuggingFaceAgent()

# Step 1: Summarize long document
document = read_file("long_contract.pdf")
summary = hf.run(
    task="summarize",
    text=document,
    max_length=200
)

# Step 2: Extract key information via QA
questions = [
    "What is the contract value?",
    "What is the termination date?",
    "Who are the parties?"
]

answers = {}
for question in questions:
    answer = hf.run(
        task="qa",
        question=question,
        context=document
    )
    answers[question] = answer["answer"]

# Step 3: Embed for similarity search
embedding = hf.run(
    task="embedding",
    text=document
)

# Step 4: Classify sentiment
sentiment = hf.run(
    task="classify",
    text=summary
)
```

### Example 2: Multi-Language Document Processing

```python
hf = HuggingFaceAgent()

# Translate foreign document
polish_doc = "Akt własności nieruchomości..."
english_doc = hf.run(
    task="translate",
    text=polish_doc,
    src_lang="pl",
    tgt_lang="en"
)

# Now process in English
summary = hf.run(
    task="summarize",
    text=english_doc
)
```

### Example 3: Image + Text Analysis

```python
hf = HuggingFaceAgent()

# Caption image
image_path = "property_photo.jpg"
caption = hf.run(
    task="image_caption",
    image=image_path
)

# Combine with text analysis
property_description = read_file("property_details.txt")
combined_text = f"{caption}\n\n{property_description}"

# Summarize combined content
summary = hf.run(
    task="summarize",
    text=combined_text
)
```

---

## 🔧 Configuration Options

### HF Agent Wrapper Configuration

```python
hf = HuggingFaceAgent(
    # Local model (optional)
    local_model="microsoft/phi-2",
    
    # HF API model (default)
    api_model="mistralai/Mistral-7B-Instruct-v0.2",
    
    # HF token (optional, can use HF_TOKEN env var)
    hf_token="hf_your_token_here",
    
    # Device
    device="cuda"  # or "cpu"
)
```

### Environment Variables

```bash
# HuggingFace token
export HF_TOKEN="hf_your_token_here"

# Device preference
export CUDA_VISIBLE_DEVICES="0"  # For GPU
```

---

## 🆚 Comparison: HF Wrapper vs Agent Manager

| Feature | HF Agent Wrapper | Agent Manager |
|---------|------------------|---------------|
| **Engines** | HF Local + HF API | HF + Ollama + Local |
| **Failover** | No | Yes (automatic) |
| **Offline** | Local models only | Local + Ollama |
| **Lightweight** | ✅ Yes | ⚠️ More features |
| **HF-specific** | ✅ Focused | ⚠️ General purpose |
| **API Endpoints** | ❌ No | ✅ Yes (`/agent/run`) |
| **Supervisor** | ❌ No | ✅ Yes (smart selection) |

---

## 🎯 Recommended Usage Pattern

### For Your Agents (Asset, Credit, etc.)

**Use Agent Manager** for most cases (automatic failover):

```python
from services.api.agent_manager import get_agent_manager

manager = get_agent_manager()

# This will automatically try: local → ollama → hf_api
result = manager.run(
    task="summarize",
    text=contract_text
)
```

**Use HF Agent Wrapper** when you need specific HF models:

```python
from services.api.hf_agent_wrapper import HuggingFaceAgent

hf = HuggingFaceAgent()

# Use specific HF model
result = hf.run(
    task="summarize",
    text=contract_text,
    model="facebook/bart-large-cnn"  # Specific model
)
```

---

## 📚 API Integration

### Add HF Wrapper to FastAPI Routes

```python
from fastapi import APIRouter
from services.api.hf_agent_wrapper import HuggingFaceAgent

router = APIRouter()
hf_agent = HuggingFaceAgent()

@router.post("/hf/summarize")
def summarize_hf(text: str):
    result = hf_agent.run(task="summarize", text=text)
    return {"summary": result}

@router.post("/hf/embed")
def embed_hf(text: str):
    result = hf_agent.run(task="embedding", text=text)
    return {"embedding": result}
```

---

## 🧪 Testing

### Test HF Agent Wrapper

```python
from services.api.hf_agent_wrapper import HuggingFaceAgent

hf = HuggingFaceAgent()

# Test all tasks
tasks = [
    ("generate", {"prompt": "Hello", "max_new_tokens": 50}),
    ("summarize", {"text": "Long text here...", "max_length": 50}),
    ("qa", {"question": "What?", "context": "Context here..."}),
    ("embedding", {"text": "Test"}),
    ("classify", {"text": "I love this!"}),
]

for task, params in tasks:
    try:
        result = hf.run(task=task, **params)
        print(f"✅ {task}: Success")
        print(f"   Result: {str(result)[:100]}...")
    except Exception as e:
        print(f"❌ {task}: Failed - {e}")
```

---

## 🚀 Quick Start

### 1. Use HF Agent Wrapper

```python
from services.api.hf_agent_wrapper import HuggingFaceAgent

hf = HuggingFaceAgent()
result = hf.run(task="generate", prompt="Hello world")
```

### 2. Use Agent Manager (with failover)

```python
from services.api.agent_manager import get_agent_manager

manager = get_agent_manager()
result = manager.run(task="generate", prompt="Hello world")
```

### 3. Use Both Together

```python
from services.api.hf_agent_wrapper import HuggingFaceAgent
from services.api.agent_manager import get_agent_manager

hf = HuggingFaceAgent()  # For HF-specific tasks
manager = get_agent_manager()  # For multi-engine tasks
```

---

## 📖 Files Reference

- **HF Agent Wrapper**: `services/api/hf_agent_wrapper.py`
- **Agent Manager**: `services/api/agent_manager.py`
- **Agent Manager Routes**: `services/api/routers/agent_manager_routes.py`
- **Supervisor**: `services/api/supervisor_agent.py`

---

**Both tools are ready to use! Choose based on your needs.** 🎉
