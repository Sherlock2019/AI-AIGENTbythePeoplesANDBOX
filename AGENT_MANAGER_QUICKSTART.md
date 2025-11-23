# 🚀 Agent Manager — What We Just Deployed & How to Use It

## 📦 What Did We Deploy?

We just deployed a **unified Agent Manager system** that acts as a **single interface** for all your AI model operations. Instead of writing different code for HuggingFace, Ollama, and local models, you now have **one simple API** that handles everything.

### What It Does

The Agent Manager:
- ✅ **Unifies** all model operations (HF, Ollama, Local) into one interface
- ✅ **Automatically fails over** if one engine is unavailable
- ✅ **Supports 7 tasks**: generate, summarize, QA, embeddings, translate, caption, classify
- ✅ **Intelligently selects** the best engine based on your needs
- ✅ **Works offline** (local models) and online (HF API)

### Files Created

1. **`services/api/agent_manager.py`** - Core manager class
2. **`services/api/routers/agent_manager_routes.py`** - REST API endpoints
3. **`services/api/supervisor_agent.py`** - Smart engine selection
4. **`services/ui/pages/hf_inspector.py`** - Web UI for testing
5. **`scripts/test_agent_manager.py`** - Python test script
6. **`scripts/test_agent_manager_api.sh`** - API test script

---

## 🎯 How to Use It

### Method 1: Python Code (Direct)

```python
from services.api.agent_manager import get_agent_manager

# Get the manager (singleton)
manager = get_agent_manager()

# Generate text
result = manager.run(
    task="generate",
    prompt="Write a haiku about AI agents",
    max_new_tokens=100
)
print(result["result"])  # The generated text
print(result["source"])  # Which engine was used: "local", "ollama", or "hf_api"

# Summarize text
result = manager.run(
    task="summarize",
    text="Long document text here...",
    max_length=150
)
print(result["result"])  # The summary

# Question Answering
result = manager.run(
    task="qa",
    question="What is the main topic?",
    context="Document context here..."
)
print(result["result"]["answer"])  # The answer

# Get embeddings
result = manager.run(
    task="embedding",
    text="Text to embed"
)
print(len(result["result"]))  # Vector dimension

# Translate
result = manager.run(
    task="translate",
    text="Hello world",
    tgt_lang="fr"
)
print(result["result"])  # "Bonjour le monde"

# Classify sentiment
result = manager.run(
    task="classify",
    text="I love this system!"
)
print(result["result"]["label"])  # "POSITIVE"
```

### Method 2: REST API (HTTP)

**Start your API server first:**
```bash
# If not already running
./newstart.sh
# or
uvicorn services.api.main:app --host 0.0.0.0 --port 8000
```

**Then use curl or any HTTP client:**

```bash
# 1. Check health
curl http://localhost:8000/agent/health

# 2. Generate text
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "generate",
    "payload": {
      "prompt": "Write a haiku about AI",
      "max_new_tokens": 100
    }
  }'

# 3. Summarize
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "summarize",
    "payload": {
      "text": "Long document text...",
      "max_length": 150
    }
  }'

# 4. Question Answering
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "qa",
    "payload": {
      "question": "What is this about?",
      "context": "Document context..."
    }
  }'

# 5. Force specific engine
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "generate",
    "engine": "ollama",
    "payload": {
      "prompt": "Hello"
    }
  }'
```

### Method 3: Web UI (Streamlit)

1. **Start the UI:**
   ```bash
   streamlit run services/ui/app.py
   ```

2. **Navigate to:** `http://localhost:8501` (or your UI port)

3. **Open the "HF Agent Inspector" page** from the sidebar

4. **Use the interactive interface:**
   - Select a task (generate, summarize, QA, etc.)
   - Enter your input
   - Click the button
   - See results with latency and engine used

### Method 4: In Your Existing Agents

**Example: Use in Asset Appraisal Agent**

```python
from services.api.agent_manager import get_agent_manager

manager = get_agent_manager()

# Summarize contract PDFs
def process_contract(ocr_text):
    summary = manager.run(
        task="summarize",
        text=ocr_text
    )["result"]
    return summary

# Embed evidence for RAG
def embed_document(document_text):
    embedding = manager.run(
        task="embedding",
        text=document_text
    )["result"]
    return embedding

# Q&A on legal documents
def answer_question(question, contract_text):
    answer = manager.run(
        task="qa",
        question=question,
        context=contract_text
    )["result"]["answer"]
    return answer

# Translate foreign documents
def translate_document(text, target_lang="en"):
    translated = manager.run(
        task="translate",
        text=text,
        tgt_lang=target_lang
    )["result"]
    return translated
```

---

## 🧪 Testing

### Quick Test (Python)

```bash
python scripts/test_agent_manager.py
```

This will test all tasks and show you which engines are working.

### API Test (Bash)

```bash
./scripts/test_agent_manager_api.sh
```

This tests all endpoints via HTTP.

---

## 🔧 Configuration

### Environment Variables

```bash
# HuggingFace token (for private models or API)
export HF_TOKEN="hf_your_token_here"

# Ollama configuration
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_MODEL="phi3:latest"

# Force local-only mode (no API calls)
export FORCE_LOCAL_ONLY="true"
```

### Custom Initialization

```python
from services.api.agent_manager import AgentManager

# Create custom manager
manager = AgentManager(
    local_model="microsoft/phi-2",  # Use specific local model
    api_model="mistralai/Mistral-7B-Instruct-v0.2",  # HF API model
    device="cuda",  # Use GPU if available
    prefer_local=True  # Try local first
)
```

---

## 🎛️ Available Tasks

| Task | Description | Example |
|------|-------------|---------|
| `generate` | Text generation | `{"prompt": "Hello", "max_new_tokens": 100}` |
| `summarize` | Text summarization | `{"text": "...", "max_length": 150}` |
| `qa` | Question answering | `{"question": "...", "context": "..."}` |
| `embedding` | Text embeddings | `{"text": "..."}` |
| `translate` | Translation | `{"text": "...", "tgt_lang": "fr"}` |
| `caption` | Image captioning | `{"image": "path_or_url"}` |
| `classify` | Classification | `{"text": "..."}` |

---

## 🚦 Engine Selection

The Agent Manager automatically selects the best engine:

1. **Local model** - Fast, no API cost, works offline
2. **Ollama** - Local LLM server, good for longer prompts
3. **HuggingFace API** - Cloud-based, always available

**You can force a specific engine:**
```python
# Force Ollama
result = manager.run(task="generate", prompt="...", engine="ollama")

# Force HF API
result = manager.run(task="generate", prompt="...", engine="hf_api")

# Force local
result = manager.run(task="generate", prompt="...", engine="local")
```

---

## 📊 API Endpoints

Once your API is running:

- **`GET /agent/health`** - Check status and available models
- **`GET /agent/models`** - List all available models
- **`POST /agent/run`** - Execute any task

**Full API docs:** `http://localhost:8000/docs`

---

## 💡 Real-World Examples

### Example 1: Summarize Contract PDFs

```python
from services.api.agent_manager import get_agent_manager

manager = get_agent_manager()

# After OCR extraction
contract_text = extract_text_from_pdf("contract.pdf")

# Summarize
summary = manager.run(
    task="summarize",
    text=contract_text,
    max_length=200
)["result"]

print(f"Contract Summary: {summary}")
```

### Example 2: Embed Documents for RAG

```python
# Embed multiple documents
documents = ["doc1.txt", "doc2.txt", "doc3.txt"]
embeddings = []

for doc in documents:
    text = read_file(doc)
    result = manager.run(task="embedding", text=text)
    embeddings.append(result["result"])

# Now use embeddings for similarity search
```

### Example 3: Q&A on Legal Documents

```python
legal_doc = read_file("legal_contract.txt")

# Answer questions
questions = [
    "What is the termination clause?",
    "What are the payment terms?",
    "Who are the parties involved?"
]

for question in questions:
    result = manager.run(
        task="qa",
        question=question,
        context=legal_doc
    )
    print(f"Q: {question}")
    print(f"A: {result['result']['answer']}\n")
```

### Example 4: Translate Foreign Documents

```python
# Translate Polish land registry to English
polish_text = "Akt własności nieruchomości..."

translated = manager.run(
    task="translate",
    text=polish_text,
    src_lang="pl",  # If supported
    tgt_lang="en"
)["result"]

print(f"Translated: {translated}")
```

---

## 🐛 Troubleshooting

### "Ollama not available"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

### "HF API errors"
- Check your `HF_TOKEN` environment variable
- Verify you have API access
- Check rate limits

### "Local model loading fails"
- Ensure model path is correct
- Check disk space
- Verify GPU availability (if using CUDA)

---

## 🎯 Next Steps

1. **Test it:** Run `python scripts/test_agent_manager.py`
2. **Try the UI:** Start Streamlit and use the HF Inspector page
3. **Integrate:** Use in your existing agents (Asset, Credit, etc.)
4. **Customize:** Adjust engine preferences based on your needs

---

## 📚 More Info

- Full documentation: `AGENT_MANAGER_README.md`
- API docs: `http://localhost:8000/docs` (when API is running)
- Code: `services/api/agent_manager.py`

---

**That's it! You now have a unified interface for all your AI model operations.** 🎉
