# 🤗 Recommended Hugging Face Models for Credit/Asset Appraisal

## ✅ Already Installed

### Core Libraries
- ✅ **transformers** (4.57.1) - For LLM models
- ✅ **sentence-transformers** (2.7.0) - For embeddings and reranking
- ✅ **huggingface-hub** - For downloading models
- ✅ **datasets** - For loading HF datasets
- ✅ **accelerate** - For faster inference
- ✅ **bitsandbytes** - For model quantization (8-bit/4-bit)

### ML Models
- ✅ **LightGBM** (4.6.0) - Gradient boosting for tabular data
- ✅ **XGBoost** (3.1.1) - Advanced gradient boosting
- ✅ **scikit-learn** - RandomForest, LogisticRegression

---

## 🚀 Recommended Hugging Face Models to Use

### 1. **Better Embedding Models** (for RAG)

**Current:** `all-MiniLM-L6-v2` (good, but can be improved)

**Recommended upgrades:**

#### **BGE Models** (Best for English)
- `BAAI/bge-small-en-v1.5` - **384 dim**, better quality than MiniLM, still fast
- `BAAI/bge-base-en-v1.5` - **768 dim**, higher quality, slightly slower
- `BAAI/bge-large-en-v1.5` - **1024 dim**, best quality, needs GPU

**Why:** Better semantic understanding, improved RAG retrieval quality

#### **Multilingual Models** (if you need VN/EN)
- `intfloat/multilingual-e5-base` - **768 dim**, supports 100+ languages
- `BAAI/bge-m3` - **1024 dim**, multilingual, supports dense + sparse retrieval

**Usage:** Set `SENTENCE_TRANSFORMER_MODEL` environment variable:
```bash
export SENTENCE_TRANSFORMER_MODEL="BAAI/bge-small-en-v1.5"
```

---

### 2. **Better Reranker Models** (for improving RAG results)

**Current:** `BAAI/bge-reranker-v2-m3` (mini version)

**Recommended upgrades:**

- `BAAI/bge-reranker-v2-base` - **Better quality**, still CPU-friendly
- `BAAI/bge-reranker-large` - **Best quality**, needs GPU

**Why:** Better reranking = more relevant answers from RAG

---

### 3. **Tabular Models** (for Credit/Asset Scoring)

#### **TabNet** (Transformer-based tabular)
```bash
pip install pytorch-tabnet
```
- Model: `dreamquark-ai/TabNet` - Attention-based, great for credit scoring
- **Why:** Can capture complex feature interactions better than tree models

#### **AutoGluon** (AutoML for tabular)
```bash
pip install autogluon.tabular
```
- **Why:** Automatically finds best model ensemble, great for production

---

### 4. **Financial Domain LLMs** (for better banking responses)

#### **FinGPT Models**
- `FinGPT/fingpt-forecaster_dow30_llama2-7b-lora` - Financial forecasting
- `FinGPT/fingpt-analyzer` - Financial analysis

#### **BloombergGPT** (if available)
- Domain-specific financial language model

---

### 5. **Document Understanding** (for PDF/image processing)

- `microsoft/table-transformer` - Extract tables from PDFs
- `layoutlmv3` - Document understanding
- `donut` - OCR-free document understanding

---

## 📦 Quick Install Commands

### For Better Embeddings:
```bash
# These download automatically when first used
# Just set environment variable:
export SENTENCE_TRANSFORMER_MODEL="BAAI/bge-small-en-v1.5"
```

### For Tabular Models:
```bash
pip install pytorch-tabnet  # TabNet transformer
pip install autogluon.tabular  # AutoML
```

### For Document Processing:
```bash
pip install transformers[torch]  # Already installed
# Models download automatically when used
```

---

## 🎯 Recommended Priority

1. **High Priority:**
   - ✅ Upgrade embedding model to `BAAI/bge-small-en-v1.5` (easy, big improvement)
   - ✅ Upgrade reranker to `BAAI/bge-reranker-v2-base` (better RAG quality)

2. **Medium Priority:**
   - Install TabNet for advanced tabular modeling
   - Consider AutoGluon for automated model selection

3. **Low Priority:**
   - Financial domain LLMs (if you need specialized financial knowledge)
   - Document understanding models (if processing PDFs/images)

---

## 💡 How to Use

### Upgrade Embedding Model:
1. Set environment variable: `export SENTENCE_TRANSFORMER_MODEL="BAAI/bge-small-en-v1.5"`
2. Restart API server
3. Model downloads automatically on first use

### Upgrade Reranker:
Edit `services/api/rag/reranker.py`:
```python
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-base"  # Instead of -m3
```

### Add TabNet to Training:
Add to `credit_appraisal.py` model options (after installing pytorch-tabnet)

---

## 📊 Model Comparison

| Model Type | Current | Recommended | Improvement |
|------------|---------|------------|-------------|
| **Embeddings** | all-MiniLM-L6-v2 | BAAI/bge-small-en-v1.5 | +15-20% retrieval quality |
| **Reranker** | bge-reranker-v2-m3 | bge-reranker-v2-base | +10-15% relevance |
| **Tabular** | LightGBM/RF | TabNet (optional) | Better feature interactions |
| **LLM** | Ollama models | Same (Ollama is fine) | - |

---

## 🔧 Environment Variables

Add to your `.env` or startup script:
```bash
# Better embeddings
export SENTENCE_TRANSFORMER_MODEL="BAAI/bge-small-en-v1.5"

# Better reranker (optional)
export RERANKER_MODEL="BAAI/bge-reranker-v2-base"

# HF cache directory
export HF_HOME="/root/newsandbox/Hugmesandbox/.cache/huggingface"
```

---

**Last Updated:** 2025-11-20
**Status:** ✅ All core libraries installed, ready for model upgrades
