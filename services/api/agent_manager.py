"""
Agent Manager — Central Controller for HF, Ollama, Local Models, RAG embeddings, and pipelines
----------------------------------------------------------------------------------------------

Unified interface for all model operations:
    agent_manager.run(task="generate", prompt="...")
    agent_manager.run(task="summarize", text="...")
    agent_manager.run(task="qa", question="...", context="...")
    agent_manager.run(task="embedding", text="...")
    agent_manager.run(task="translate", text="...")
    agent_manager.run(task="caption", image=...)
"""

import os
import time
import logging
from typing import Any, Dict, Optional, Union, List
from functools import lru_cache

from huggingface_hub import InferenceClient
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    pipeline,
)

# Import existing Ollama client
try:
    from services.api.llm.ollama_client import ollama_generate, OllamaError, OLLAMA_URL, OLLAMA_MODEL
except ImportError:
    # Fallback if Ollama client not available
    ollama_generate = None
    OllamaError = Exception
    OLLAMA_URL = "http://localhost:11434"
    OLLAMA_MODEL = "phi3:latest"

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Central controller for all model operations.
    Supports failover: Local → Ollama → HuggingFace API
    """

    def __init__(
        self,
        local_model: Optional[str] = None,
        api_model: Optional[str] = "mistralai/Mistral-7B-Instruct-v0.2",
        ollama_model: Optional[str] = None,
        hf_token: Optional[str] = None,
        device: Optional[str] = None,
        prefer_local: bool = True,
    ):
        """
        Initialize Agent Manager.
        
        Args:
            local_model: Local Transformers model path (optional)
            api_model: HuggingFace API model name
            ollama_model: Ollama model name (defaults to OLLAMA_MODEL env var)
            hf_token: HuggingFace token (or use HF_TOKEN env var)
            device: Device for local models ("cpu", "cuda", etc.) - auto-detects if None
            prefer_local: If True, try local models first
        """
        self.device = device or ("cuda" if self._has_gpu() else "cpu")
        self.local_model_name = local_model
        self.api_model_name = api_model
        self.ollama_model = ollama_model or OLLAMA_MODEL
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.prefer_local = prefer_local

        # Lazy-loaded components
        self._local_tokenizer = None
        self._local_model = None
        self._hf_client = None
        self._pipelines = {}  # Cache for pipelines

        # Track loaded models
        self.loaded_models = {
            "local": False,
            "ollama": False,
            "hf_api": False,
        }

        # Initialize HF client (lightweight, no model loading)
        try:
            self._hf_client = InferenceClient(
                model=self.api_model_name,
                token=self.hf_token
            )
            self.loaded_models["hf_api"] = True
            logger.info("✅ HF API client initialized")
        except Exception as e:
            logger.warning(f"⚠️ HF API client initialization failed: {e}")

        # Check Ollama availability
        if ollama_generate:
            try:
                import requests
                resp = requests.get(f"{OLLAMA_URL.rstrip('/')}/api/tags", timeout=2)
                if resp.status_code == 200:
                    self.loaded_models["ollama"] = True
                    logger.info("✅ Ollama server detected")
            except Exception:
                logger.warning("⚠️ Ollama server not available")

        logger.info(f"🤖 Agent Manager initialized (device: {self.device}, prefer_local: {self.prefer_local})")

    @staticmethod
    def _has_gpu() -> bool:
        """Check if GPU is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def _load_local_model(self):
        """Lazy-load local transformer model."""
        if self._local_model is not None:
            return
        
        if not self.local_model_name:
            return

        try:
            logger.info(f"📦 Loading local model: {self.local_model_name}")
            self._local_tokenizer = AutoTokenizer.from_pretrained(
                self.local_model_name,
                token=self.hf_token
            )
            self._local_model = AutoModelForCausalLM.from_pretrained(
                self.local_model_name,
                token=self.hf_token,
                device_map="auto" if self.device == "cuda" else None
            )
            if self.device == "cpu":
                self._local_model = self._local_model.to(self.device)
            self.loaded_models["local"] = True
            logger.info("✅ Local model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Error loading local model: {e}")
            self._local_model = None
            self._local_tokenizer = None

    def _get_pipeline(self, task: str, model: Optional[str] = None, **kwargs):
        """Get or create a pipeline (lazy-loaded, cached)."""
        cache_key = f"{task}:{model or 'default'}"
        if cache_key in self._pipelines:
            return self._pipelines[cache_key]

        try:
            device_map = -1 if self.device == "cpu" else 0
            pipe = pipeline(
                task,
                model=model,
                device=device_map,
                token=self.hf_token,
                **kwargs
            )
            self._pipelines[cache_key] = pipe
            logger.debug(f"✅ Pipeline loaded: {cache_key}")
            return pipe
        except Exception as e:
            logger.error(f"❌ Pipeline loading failed ({cache_key}): {e}")
            raise

    # --------------------------------------------------------
    # Public API: run()
    # --------------------------------------------------------
    def run(self, task: str, engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Universal entry point for all tasks.
        
        Args:
            task: Task type (generate, summarize, qa, embedding, translate, caption, classify)
            engine: Force specific engine ("local", "ollama", "hf_api") - auto-selects if None
            **kwargs: Task-specific parameters
            
        Returns:
            Dict with "result" and "source" keys
        """
        start_time = time.time()
        task = task.lower()

        try:
            # Dispatch to task-specific method
            if task in ["generate", "text-generation"]:
                result = self._generate(engine=engine, **kwargs)
            elif task in ["summarize", "summary"]:
                result = self._summarize(engine=engine, **kwargs)
            elif task in ["qa", "question_answering", "question-answering"]:
                result = self._qa(engine=engine, **kwargs)
            elif task in ["embedding", "embed"]:
                result = self._embedding(engine=engine, **kwargs)
            elif task in ["translate", "translation"]:
                result = self._translate(engine=engine, **kwargs)
            elif task in ["image_caption", "caption", "image-to-text"]:
                result = self._image_caption(engine=engine, **kwargs)
            elif task in ["classify", "classification", "sentiment"]:
                result = self._classify(engine=engine, **kwargs)
            else:
                raise ValueError(
                    f"Unknown task: {task}. Supported: generate, summarize, qa, embedding, translate, caption, classify"
                )

            latency = time.time() - start_time
            logger.info(f"✅ Task '{task}' completed in {latency:.2f}s (source: {result.get('source', 'unknown')})")

            return {
                "result": result.get("result"),
                "source": result.get("source"),
                "latency": round(latency, 3),
                "task": task,
            }

        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"❌ Task '{task}' failed after {latency:.2f}s: {e}")
            return {
                "result": None,
                "error": str(e),
                "source": "error",
                "latency": round(latency, 3),
                "task": task,
            }

    # --------------------------------------------------------
    # Task Implementations with Failover
    # --------------------------------------------------------
    def _generate(
        self,
        prompt: str,
        max_new_tokens: int = 200,
        temperature: float = 0.7,
        engine: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text with failover: local → ollama → hf_api."""
        if not prompt:
            raise ValueError("Prompt is required for generation")

        # Try local model first (if preferred and available)
        if (engine is None and self.prefer_local) or engine == "local":
            if self.local_model_name:
                try:
                    self._load_local_model()
                    if self._local_model is not None:
                        inputs = self._local_tokenizer(prompt, return_tensors="pt")
                        if self.device != "cpu":
                            inputs = {k: v.to(self.device) for k, v in inputs.items()}
                        
                        output = self._local_model.generate(
                            **inputs,
                            max_new_tokens=max_new_tokens,
                            temperature=temperature,
                            **kwargs
                        )
                        text = self._local_tokenizer.decode(output[0], skip_special_tokens=True)
                        return {"result": text, "source": "local"}
                except Exception as e:
                    logger.warning(f"Local generation failed: {e}")

        # Try Ollama
        if (engine is None) or engine == "ollama":
            if ollama_generate and self.loaded_models.get("ollama"):
                try:
                    text = ollama_generate(
                        prompt,
                        model=self.ollama_model,
                        timeout=60
                    )
                    return {"result": text, "source": "ollama"}
                except Exception as e:
                    logger.warning(f"Ollama generation failed: {e}")

        # Fallback to HF API
        if (engine is None) or engine == "hf_api":
            if self._hf_client:
                try:
                    text = self._hf_client.text_generation(
                        prompt,
                        max_new_tokens=max_new_tokens,
                        temperature=temperature,
                        **kwargs
                    )
                    return {"result": text, "source": "hf_api"}
                except Exception as e:
                    logger.warning(f"HF API generation failed: {e}")

        raise RuntimeError("All generation engines failed")

    def _summarize(
        self,
        text: str,
        max_length: int = 150,
        min_length: int = 30,
        model: Optional[str] = None,
        engine: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Summarize text using HF pipeline."""
        if not text:
            raise ValueError("Text is required for summarization")

        model_name = model or "facebook/bart-large-cnn"
        try:
            summarizer = self._get_pipeline("summarization", model=model_name)
            result = summarizer(text, max_length=max_length, min_length=min_length, **kwargs)
            return {"result": result[0]["summary_text"], "source": "hf_pipeline"}
        except Exception as e:
            raise RuntimeError(f"Summarization failed: {e}")

    def _qa(
        self,
        question: str,
        context: str,
        model: Optional[str] = None,
        engine: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Answer questions using HF pipeline."""
        if not question or not context:
            raise ValueError("Question and context are required for QA")

        model_name = model or "distilbert-base-uncased-distilled-squad"
        try:
            qa_pipe = self._get_pipeline("question-answering", model=model_name)
            result = qa_pipe({"question": question, "context": context}, **kwargs)
            return {"result": result, "source": "hf_pipeline"}
        except Exception as e:
            raise RuntimeError(f"QA failed: {e}")

    def _embedding(
        self,
        text: Union[str, List[str]],
        model: Optional[str] = None,
        engine: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate embeddings using sentence-transformers or HF pipeline."""
        if not text:
            raise ValueError("Text is required for embedding")

        model_name = model or "sentence-transformers/all-MiniLM-L6-v2"
        
        # Try sentence-transformers first (faster, better)
        try:
            from sentence_transformers import SentenceTransformer
            st_model = SentenceTransformer(model_name)
            embeddings = st_model.encode(text if isinstance(text, list) else [text])
            result = embeddings[0].tolist() if isinstance(text, str) else embeddings.tolist()
            return {"result": result, "source": "sentence_transformers"}
        except ImportError:
            logger.debug("sentence-transformers not available, using HF pipeline")
        except Exception as e:
            logger.warning(f"Sentence-transformers failed: {e}")

        # Fallback to HF pipeline
        try:
            emb_pipe = self._get_pipeline("feature-extraction", model=model_name)
            is_single = isinstance(text, str)
            texts = [text] if is_single else text
            
            embeddings = []
            for t in texts:
                emb = emb_pipe(t)[0]
                if isinstance(emb[0], list):
                    import numpy as np
                    emb = np.mean(emb, axis=0).tolist()
                embeddings.append(emb)
            
            result = embeddings[0] if is_single else embeddings
            return {"result": result, "source": "hf_pipeline"}
        except Exception as e:
            raise RuntimeError(f"Embedding failed: {e}")

    def _translate(
        self,
        text: str,
        tgt_lang: str = "fr",
        src_lang: str = "en",
        model: Optional[str] = None,
        engine: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Translate text between languages."""
        if not text:
            raise ValueError("Text is required for translation")

        # Model selection based on language pair
        if model is None:
            if src_lang == "en" and tgt_lang == "fr":
                model = "Helsinki-NLP/opus-mt-en-fr"
            elif src_lang == "en" and tgt_lang == "de":
                model = "Helsinki-NLP/opus-mt-en-de"
            elif src_lang == "en" and tgt_lang == "es":
                model = "Helsinki-NLP/opus-mt-en-es"
            else:
                model = "Helsinki-NLP/opus-mt-en-fr"  # Default fallback

        try:
            translator = self._get_pipeline("translation", model=model)
            result = translator(text, **kwargs)
            return {"result": result[0]["translation_text"], "source": "hf_pipeline"}
        except Exception as e:
            raise RuntimeError(f"Translation failed: {e}")

    def _image_caption(
        self,
        image: Union[str, Any],
        model: Optional[str] = None,
        engine: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate captions for images."""
        if image is None:
            raise ValueError("Image is required for captioning")

        model_name = model or "nlpconnect/vit-gpt2-image-captioning"
        try:
            captioner = self._get_pipeline("image-to-text", model=model_name)
            result = captioner(image, **kwargs)
            return {"result": result[0]["generated_text"], "source": "hf_pipeline"}
        except Exception as e:
            raise RuntimeError(f"Image captioning failed: {e}")

    def _classify(
        self,
        text: Union[str, List[str]],
        model: Optional[str] = None,
        engine: Optional[str] = None,
        return_all_scores: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Classify text (sentiment analysis by default)."""
        if not text:
            raise ValueError("Text is required for classification")

        model_name = model or "distilbert-base-uncased-finetuned-sst-2-english"
        try:
            classifier = self._get_pipeline(
                "sentiment-analysis",
                model=model_name,
                return_all_scores=return_all_scores
            )
            result = classifier(text, **kwargs)
            return {
                "result": result[0] if isinstance(text, str) and not return_all_scores else result,
                "source": "hf_pipeline"
            }
        except Exception as e:
            raise RuntimeError(f"Classification failed: {e}")


# Singleton instance
_manager_instance: Optional[AgentManager] = None


def get_agent_manager() -> AgentManager:
    """Get or create singleton AgentManager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AgentManager()
    return _manager_instance
