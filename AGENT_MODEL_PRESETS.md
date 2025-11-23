# Agent Model Presets Configuration

## Overview

This system automatically preselects recommended models for each agent type based on their specific use cases. Models are chosen to optimize for:
- **Performance**: Best accuracy for the task
- **Speed**: Fast inference for real-time workflows
- **Explainability**: Clear reasoning for regulatory compliance
- **Resource efficiency**: CPU vs GPU requirements

## Configuration Files

### 1. `config/agent_model_presets.yaml`
Main configuration file defining recommended models for each agent.

### 2. `config/model_registry.yaml`
Extended model registry with agent-specific recommendations.

## Agent Model Presets

### 💳 Credit Appraisal Agent

**Tabular Model (Scoring):**
- **Primary**: `LightGBM` - Best for credit risk with imbalanced data
- **Fallback**: `RandomForest` - Good explainability
- **Alternatives**: `XGBoost`, `LogisticRegression`

**LLM Model (Narratives):**
- **Primary**: `mistral:7b-instruct` - Balanced performance for credit explanations
- **Fallback**: `phi3:3.8b` - CPU-friendly
- **Alternatives**: `gemma2:9b`, `llama3:8b-instruct`

**Why**: LightGBM excels at credit scoring with mixed feature types and imbalanced classes. Mistral provides good quality explanations without being too slow.

---

### 🏦 Asset Appraisal Agent

**Tabular Model (Valuation):**
- **Primary**: `LightGBM` - Good for regression/valuation tasks
- **Fallback**: `RandomForest`
- **Alternatives**: `XGBoost`

**LLM Model (Narratives):**
- **Primary**: `mistral:7b-instruct` - Good for valuation narratives
- **Fallback**: `phi3:3.8b`
- **Alternatives**: `gemma2:9b`, `llama3:8b-instruct`, `qwen2:7b-instruct`

**Why**: LightGBM handles numeric features well for asset valuation. Mistral handles financial narratives with good context understanding.

---

### 🛡️ Anti-Fraud & KYC Agent

**Tabular Model (Fraud Detection):**
- **Primary**: `RandomForest` - Good explainability for fraud alerts
- **Fallback**: `LogisticRegression`
- **Alternatives**: `LightGBM`, `XGBoost`

**LLM Model (Narratives):**
- **Primary**: `phi3:3.8b` - Fast for real-time fraud alerts
- **Fallback**: `mistral:7b-instruct`
- **Alternatives**: `gemma2:2b`

**Why**: RandomForest provides good explainability for fraud detection. Phi-3 Mini is fast enough for real-time workflows.

---

### ⚖️ Legal Compliance Agent

**LLM Model (Narratives):**
- **Primary**: `mistral:7b-instruct` - Good for regulatory text understanding
- **Fallback**: `phi3:3.8b`
- **Alternatives**: `llama3:8b-instruct`

**Why**: Mistral handles complex regulatory language well.

---

### 💬 Chatbot Assistant

**LLM Model (Narratives):**
- **Primary**: `mistral:7b-instruct` - Best general-purpose chat
- **Fallback**: `phi3:3.8b`
- **Alternatives**: `gemma2:9b`, `llama3:8b-instruct`

**Why**: Mistral provides best conversational quality for banking chatbot.

---

### 🧩 Unified Risk Agent

**Tabular Model (Scoring):**
- **Primary**: `LightGBM` - Best overall performance
- **Fallback**: `RandomForest`
- **Alternatives**: `XGBoost`

**LLM Model (Narratives):**
- **Primary**: `mistral:7b-instruct` - Good for combined risk narratives
- **Fallback**: `phi3:3.8b`
- **Alternatives**: `gemma2:9b`

**Why**: LightGBM provides best accuracy for combined risk scoring. Mistral handles complex multi-factor risk explanations.

---

### 📊 Credit Scoring Agent

**LLM Model (Narratives):**
- **Primary**: `phi3:3.8b` - Fast for score explanations
- **Fallback**: `mistral:7b-instruct`
- **Alternatives**: `gemma2:2b`

**Why**: Phi-3 Mini is sufficient for quick score explanations.

---

## Embedding & Reranker Models

### Embeddings (for RAG)
- **Default**: `BAAI/bge-small-en-v1.5` - Better than all-MiniLM-L6-v2
- **Multilingual**: `intfloat/multilingual-e5-base` - For VN/EN support
- **High Quality**: `BAAI/bge-base-en-v1.5` - When quality > speed

### Reranker (for improving RAG results)
- **Default**: `BAAI/bge-reranker-v2-base` - Better than mini version
- **High Quality**: `BAAI/bge-reranker-large` - Best quality (needs GPU)

---

## How It Works

1. **On Page Load**: Each agent page checks for recommended models in `agent_model_presets.yaml`
2. **Model Selection**: The UI automatically preselects the recommended model
3. **Fallback Logic**: If primary model is unavailable, falls back to secondary, then alternatives
4. **User Override**: Users can still manually select any available model

## Usage

### For Developers

Models are automatically preselected when:
- Opening an agent page for the first time
- No previous selection exists in session state
- Recommended model is available

### For Users

- **Recommended models** are shown with a ⭐ badge
- You can still change the selection manually
- The system remembers your choice for the session

## Updating Presets

Edit `config/agent_model_presets.yaml` to change recommendations:

```yaml
tabular_models:
  credit_appraisal:
    primary: "LightGBM"
    fallback: "RandomForest"
    alternatives: ["XGBoost", "LogisticRegression"]
    reason: "Your reason here"
```

Then restart the Streamlit server for changes to take effect.

---

**Last Updated**: 2025-11-20
**Status**: ✅ Active - All agents configured with recommended models
