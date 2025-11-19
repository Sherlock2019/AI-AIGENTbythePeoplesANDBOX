# Chatbot Timeout Root Cause Analysis

## 🔍 Root Causes Identified

### 1. **Sequential Blocking LLM Calls** ⚠️ **CRITICAL**

**Location**: `services/api/routers/chat.py` lines 764-780

**Problem**: 
- The code makes **TWO sequential blocking LLM calls** that can take up to **60 seconds total**
- First call: `_maybe_generate_llm_reply()` with 30s timeout
- Second call: `_generate_gemma_fallback()` with 30s timeout (if first fails)
- Both are **synchronous** and **block the entire request**

**Code Flow**:
```python
# Line 765: First LLM call (blocks for up to 30s)
llm_reply = _maybe_generate_llm_reply(payload, retrieved, mode, model_to_use)

# Line 774: Second LLM call if first fails (blocks for another 30s)
generic_reply = _generate_gemma_fallback(payload, mode, model_to_use)
```

**Impact**: 
- **Worst case**: 60 seconds timeout (30s + 30s)
- **Typical case**: 30-60 seconds if Ollama is slow or model needs to load
- **User experience**: Request appears to hang/freeze

**Performance Test Results**:
- Ollama model loading: Can take 5-15 seconds on first request
- CPU inference: 10-30 seconds for response generation
- Total: Up to 60 seconds per request

---

### 2. **Model Loading on First Request** ⚠️ **MODERATE**

**Location**: `services/api/rag/embeddings.py` line 17

**Problem**:
- SentenceTransformer model loads **lazily on first request**
- First embedding generation takes **3.4 seconds**
- Subsequent calls are fast (0.23s)

**Code**:
```python
def _get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(DEFAULT_MODEL, device=_DEVICE)  # 3.4s on first call
    return _MODEL
```

**Impact**:
- First request after API restart: +3.4 seconds
- Subsequent requests: Fast (0.23s)

**Solution**: Pre-load model on API startup

---

### 3. **No True Async/Background Processing** ⚠️ **MODERATE**

**Location**: `services/api/routers/chat.py` line 762

**Problem**:
- Comment says "non-blocking approach" but code is **fully blocking**
- LLM calls are synchronous `requests.post()` calls
- No async/await or background tasks

**Code**:
```python
# Comment says "non-blocking" but it's actually blocking!
# Try to enhance with LLM in background (non-blocking approach)
llm_reply = _maybe_generate_llm_reply(...)  # Blocks here!
```

**Impact**:
- Request thread blocked during LLM generation
- Cannot handle concurrent requests efficiently
- No way to return fast response and enhance later

---

### 4. **TF-IDF Cache Expiry** ⚠️ **MINOR**

**Location**: `services/api/routers/chat.py` line 209

**Problem**:
- TF-IDF vectorizer rebuilds every 60 seconds (VECTOR_CACHE_TTL)
- Rebuilding takes 0.29 seconds
- Happens synchronously during request

**Impact**:
- Occasional 0.29s delay when cache expires
- Not a major issue but could be optimized

---

### 5. **Large RAG Store Query** ✅ **OPTIMIZED**

**Location**: `services/api/rag/local_store.py` line 61

**Status**: **Already optimized**
- Query time: 0.09 seconds (very fast)
- 64,675 documents queried efficiently
- No optimization needed

---

## 📊 Performance Breakdown

| Operation | First Call | Subsequent Calls | Status |
|-----------|------------|------------------|--------|
| Embedding Generation | 3.4s | 0.23s | ⚠️ Needs pre-loading |
| RAG Store Query | 0.09s | 0.09s | ✅ Optimized |
| TF-IDF Building | 0.29s | 0.29s (if cache expired) | ⚠️ Minor issue |
| LLM Call #1 | 10-30s | 10-30s | ⚠️ **CRITICAL** |
| LLM Call #2 | 10-30s | 10-30s | ⚠️ **CRITICAL** |
| **Total Worst Case** | **~60s** | **~60s** | ❌ **TIMEOUT** |

---

## 🎯 Optimization Recommendations

### Priority 1: Fix Sequential LLM Calls (CRITICAL)

**Current Flow**:
```
Request → RAG Query (0.09s) → LLM Call #1 (30s timeout) → LLM Call #2 (30s timeout) → Response
Total: Up to 60s
```

**Optimized Flow**:
```
Request → RAG Query (0.09s) → Lightweight Reply (instant) → Return Response
                                    ↓ (background)
                              LLM Enhancement (async, optional)
Total: <1s (with async LLM enhancement)
```

**Solution**:
1. Return lightweight reply immediately
2. Use FastAPI BackgroundTasks for LLM enhancement
3. Remove second LLM fallback call
4. Set shorter timeout (10s) for LLM calls

### Priority 2: Pre-load Embedding Model

**Solution**: Load SentenceTransformer model on API startup
```python
# In services/api/main.py
from services.api.rag.embeddings import _get_model
_get_model()  # Pre-load on startup
```

### Priority 3: Make LLM Calls Truly Async

**Solution**: Use FastAPI BackgroundTasks or async/await
```python
from fastapi import BackgroundTasks

@router.post("/v1/chat")
async def chat_endpoint(
    payload: ChatRequest,
    background_tasks: BackgroundTasks
) -> ChatResponse:
    # Return fast response
    reply_text = _compose_lightweight_reply(...)
    
    # Enhance in background (optional)
    background_tasks.add_task(enhance_with_llm, ...)
    
    return ChatResponse(reply=reply_text, ...)
```

---

## 🔧 Quick Fixes (Immediate)

1. **Remove second LLM call** - Only use one LLM call
2. **Reduce LLM timeout** - From 30s to 10s
3. **Return lightweight reply first** - Don't wait for LLM
4. **Pre-load embedding model** - On API startup

---

## 📈 Expected Performance After Fixes

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| First Request | ~60s | ~1s | **60x faster** |
| Subsequent Requests | ~60s | ~1s | **60x faster** |
| With LLM Enhancement | N/A | ~1s + async | **Non-blocking** |

---

## 🚀 Implementation Priority

1. **Immediate** (Fix timeout):
   - Remove second LLM call
   - Return lightweight reply immediately
   - Reduce LLM timeout to 10s

2. **Short-term** (Improve UX):
   - Pre-load embedding model
   - Use BackgroundTasks for LLM enhancement

3. **Long-term** (Scale):
   - Implement async LLM calls
   - Add response streaming
   - Cache LLM responses
