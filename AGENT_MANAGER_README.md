# Agent Manager — Unified Model Interface

## Overview

The Agent Manager provides a **unified interface** for all model operations across:
- **Local Transformers models** (CPU/GPU)
- **Ollama** (local LLM server)
- **HuggingFace API** (cloud inference)
- **HF Pipelines** (summarization, QA, embeddings, etc.)

## Quick Start

### Python API

```python
from services.api.agent_manager import get_agent_manager

manager = get_agent_manager()

# Text generation
result = manager.run(
    task="generate",
    prompt="Hello world",
    max_new_tokens=200
)

# Summarization
result = manager.run(
    task="summarize",
    text="Long document text...",
    max_length=150
)

# Question Answering
result = manager.run(
    task="qa",
    question="What is this?",
    context="Document context..."
)

# Embeddings
result = manager.run(
    task="embedding",
    text="Text to embed"
)

# Translation
result = manager.run(
    task="translate",
    text="Hello",
    tgt_lang="fr"
)

# Classification
result = manager.run(
    task="classify",
    text="I love this!"
)
```

### REST API

```bash
# Health check
curl http://localhost:8000/agent/health

# Text generation
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "generate",
    "payload": {
      "prompt": "Hello world",
      "max_new_tokens": 200
    }
  }'

# Summarization
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "summarize",
    "payload": {
      "text": "Long document...",
      "max_length": 150
    }
  }'
```

## Features

### ✅ Automatic Failover

The Agent Manager automatically tries engines in order:
1. **Local model** (if available and preferred)
2. **Ollama** (if server is running)
3. **HuggingFace API** (fallback)

### ✅ Intelligent Engine Selection

Use the Supervisor Agent for smart engine selection:

```python
from services.api.supervisor_agent import get_supervisor

supervisor = get_supervisor()
result = supervisor.run(
    task="generate",
    payload={"prompt": "..."},
    agent_type="credit"  # Applies credit agent policies
)
```

### ✅ Lazy Loading

Models and pipelines are loaded **on first use**, not at startup.

### ✅ Task Support

- `generate` - Text generation
- `summarize` - Text summarization
- `qa` - Question answering
- `embedding` - Text embeddings
- `translate` - Translation
- `caption` - Image captioning
- `classify` - Classification/sentiment analysis

## Configuration

### Environment Variables

```bash
# HuggingFace token (optional, for private models)
export HF_TOKEN="hf_..."

# Ollama configuration
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_MODEL="phi3:latest"

# Force local-only mode
export FORCE_LOCAL_ONLY="true"
```

### Initialization Options

```python
from services.api.agent_manager import AgentManager

manager = AgentManager(
    local_model="microsoft/phi-2",  # Local model path
    api_model="mistralai/Mistral-7B-Instruct-v0.2",  # HF API model
    ollama_model="phi3:latest",  # Ollama model
    hf_token="hf_...",  # HF token
    device="cuda",  # or "cpu"
    prefer_local=True  # Try local first
)
```

## Testing

### Python Tests

```bash
python scripts/test_agent_manager.py
```

### API Tests

```bash
./scripts/test_agent_manager_api.sh
```

### Streamlit UI

```bash
# Start Streamlit UI
streamlit run services/ui/app.py

# Navigate to: HF Agent Inspector page
```

## Integration Examples

### In Your Agents

```python
from services.api.agent_manager import get_agent_manager

manager = get_agent_manager()

# Summarize contract PDFs
summary = manager.run(
    task="summarize",
    text=ocr_text
)["result"]

# Embed evidence for RAG
embedding = manager.run(
    task="embedding",
    text=document_text
)["result"]

# Q&A on legal documents
answer = manager.run(
    task="qa",
    question="Does this asset have ownership issues?",
    context=contract_text
)["result"]

# Translate foreign documents
translated = manager.run(
    task="translate",
    text=polish_land_registry_doc,
    tgt_lang="en"
)["result"]
```

### In FastAPI Routes

```python
from services.api.agent_manager import get_agent_manager

@app.post("/my-endpoint")
def my_endpoint(request: MyRequest):
    manager = get_agent_manager()
    result = manager.run(
        task="generate",
        prompt=request.prompt
    )
    return {"result": result["result"]}
```

## Architecture

```
AgentManager
├── Local Models (Transformers)
├── Ollama Client
├── HuggingFace API Client
└── HF Pipelines (lazy-loaded)
    ├── Summarization
    ├── QA
    ├── Embeddings
    ├── Translation
    ├── Image Captioning
    └── Classification

SupervisorAgent
├── Engine Selection Logic
├── Safety Filters
└── Policy Enforcement
```

## API Endpoints

- `POST /agent/run` - Execute any task
- `GET /agent/health` - Health check and model status
- `GET /agent/models` - List available models

## Troubleshooting

### Ollama not available

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama (if installed)
ollama serve
```

### HF API errors

- Check `HF_TOKEN` environment variable
- Verify model name is correct
- Check API rate limits

### Local model loading fails

- Ensure model path is correct
- Check disk space
- Verify GPU availability (if using CUDA)

## License

Part of the AI Agent Sandbox project.
