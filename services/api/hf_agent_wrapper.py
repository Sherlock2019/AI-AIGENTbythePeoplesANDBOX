"""
HF Agent Wrapper — Unified Interface for Hugging Face Tasks
------------------------------------------------------------

Supports:
    - Text generation
    - Summarization
    - Question Answering
    - Embeddings
    - Translation
    - Image captioning
    - Classification
    - Custom pipelines

Use:
    hf = HuggingFaceAgent()
    result = hf.run(task="generate", prompt="Hello world")
"""

import os
from typing import Any, Dict, Optional, Union, List

from huggingface_hub import InferenceClient
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    pipeline,
)


class HuggingFaceAgent:

    def __init__(
        self,
        local_model: Optional[str] = None,
        api_model: Optional[str] = "mistralai/Mistral-7B-Instruct-v0.2",
        hf_token: Optional[str] = None,
        device: Optional[str] = "cpu"
    ):
        """
        Initialize HuggingFace Agent wrapper.
        
        Args:
            local_model: If set, use local model (Transformers)
            api_model: Default remote HF model for API inference
            hf_token: Hugging Face access token (optional, can use HF_TOKEN env var)
            device: Device to use for local models ("cpu", "cuda", etc.)
        """
        self.device = device
        self.local_model_name = local_model
        self.api_model_name = api_model
        self.hf_token = hf_token or os.getenv("HF_TOKEN")

        # Load remote inference client
        self.client = InferenceClient(
            model=self.api_model_name,
            token=self.hf_token
        )

        # Load local model if requested
        self.local_tokenizer = None
        self.local_model = None
        if self.local_model_name:
            self._load_local_llm()

        print("🤖 HF Agent Initialized")

    # --------------------------------------------------------
    # 1) Load local LLM
    # --------------------------------------------------------
    def _load_local_llm(self):
        """Load local transformer model and tokenizer."""
        print(f"📦 Loading local HF model: {self.local_model_name}")
        try:
            self.local_tokenizer = AutoTokenizer.from_pretrained(
                self.local_model_name,
                token=self.hf_token
            )
            self.local_model = AutoModelForCausalLM.from_pretrained(
                self.local_model_name,
                token=self.hf_token,
                device_map=self.device if self.device != "cpu" else None
            )
            if self.device == "cpu":
                self.local_model = self.local_model.to(self.device)
            print(f"✅ Local model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading local model: {e}")
            raise

    # --------------------------------------------------------
    # 2) Dispatch task
    # --------------------------------------------------------
    def run(self, task: str, **kwargs) -> Any:
        """
        Universal entry point for all HF tasks.
        
        Args:
            task: Task type (generate, summarize, qa, embedding, translate, etc.)
            **kwargs: Task-specific parameters
            
        Returns:
            Task-specific result
            
        Examples:
            hf.run(task="summarize", text="...")
            hf.run(task="qa", context="...", question="...")
            hf.run(task="generate", prompt="...")
        """
        task = task.lower()

        if task in ["generate", "text-generation"]:
            return self._generate(**kwargs)

        elif task in ["summarize", "summary"]:
            return self._summarize(**kwargs)

        elif task in ["qa", "question_answering", "question-answering"]:
            return self._qa(**kwargs)

        elif task in ["embedding", "embed"]:
            return self._embedding(**kwargs)

        elif task in ["translate", "translation"]:
            return self._translate(**kwargs)

        elif task in ["image_caption", "caption", "image-to-text"]:
            return self._image_caption(**kwargs)

        elif task in ["classify", "classification", "sentiment"]:
            return self._classify(**kwargs)

        else:
            raise ValueError(f"❌ Unknown HF Agent task: {task}. Supported tasks: generate, summarize, qa, embedding, translate, image_caption, classify")

    # --------------------------------------------------------
    # 3) Text Generation
    # --------------------------------------------------------
    def _generate(
        self, 
        prompt: str, 
        max_new_tokens: int = 200,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **kwargs
    ) -> str:
        """Generate text from a prompt."""
        if self.local_model_name and self.local_model is not None:
            inputs = self.local_tokenizer(prompt, return_tensors="pt")
            if self.device != "cpu":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            output = self.local_model.generate(
                **inputs, 
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                **kwargs
            )
            return self.local_tokenizer.decode(output[0], skip_special_tokens=True)

        # Remote API
        return self.client.text_generation(
            prompt, 
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            **kwargs
        )

    # --------------------------------------------------------
    # 4) Summarization
    # --------------------------------------------------------
    def _summarize(
        self, 
        text: str, 
        max_length: int = 150,
        min_length: int = 30,
        model: Optional[str] = None
    ) -> str:
        """Summarize text using BART or specified model."""
        model_name = model or "facebook/bart-large-cnn"
        device_map = -1 if self.device == "cpu" else 0
        
        try:
            summarizer = pipeline(
                "summarization",
                model=model_name,
                device=device_map,
                token=self.hf_token
            )
            result = summarizer(text, max_length=max_length, min_length=min_length)
            return result[0]["summary_text"]
        except Exception as e:
            print(f"❌ Summarization error: {e}")
            raise

    # --------------------------------------------------------
    # 5) Question Answering
    # --------------------------------------------------------
    def _qa(
        self, 
        question: str, 
        context: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Answer questions based on context."""
        model_name = model or "distilbert-base-uncased-distilled-squad"
        device_map = -1 if self.device == "cpu" else 0
        
        try:
            qa_pipe = pipeline(
                "question-answering",
                model=model_name,
                device=device_map,
                token=self.hf_token
            )
            result = qa_pipe({"question": question, "context": context})
            return result
        except Exception as e:
            print(f"❌ QA error: {e}")
            raise

    # --------------------------------------------------------
    # 6) Embeddings
    # --------------------------------------------------------
    def _embedding(
        self, 
        text: Union[str, List[str]], 
        model: Optional[str] = None,
        normalize: bool = True
    ) -> Union[List[float], List[List[float]]]:
        """Generate embeddings for text."""
        model_name = model or "sentence-transformers/all-MiniLM-L6-v2"
        device_map = -1 if self.device == "cpu" else 0
        
        try:
            emb_pipe = pipeline(
                "feature-extraction",
                model=model_name,
                device=device_map,
                token=self.hf_token
            )
            
            # Handle single text or list of texts
            is_single = isinstance(text, str)
            texts = [text] if is_single else text
            
            embeddings = []
            for t in texts:
                emb = emb_pipe(t)[0]
                # Average over token embeddings if needed
                if isinstance(emb[0], list):
                    import numpy as np
                    emb = np.mean(emb, axis=0).tolist()
                embeddings.append(emb)
            
            return embeddings[0] if is_single else embeddings
        except Exception as e:
            print(f"❌ Embedding error: {e}")
            raise

    # --------------------------------------------------------
    # 7) Translation
    # --------------------------------------------------------
    def _translate(
        self, 
        text: str, 
        tgt_lang: str = "fr",
        src_lang: str = "en",
        model: Optional[str] = None
    ) -> str:
        """Translate text between languages."""
        # Default model mapping
        if model is None:
            if src_lang == "en" and tgt_lang == "fr":
                model = "Helsinki-NLP/opus-mt-en-fr"
            elif src_lang == "en" and tgt_lang == "de":
                model = "Helsinki-NLP/opus-mt-en-de"
            elif src_lang == "en" and tgt_lang == "es":
                model = "Helsinki-NLP/opus-mt-en-es"
            else:
                # Fallback to generic model
                model = "Helsinki-NLP/opus-mt-en-fr"
        
        device_map = -1 if self.device == "cpu" else 0
        
        try:
            translator = pipeline(
                "translation",
                model=model,
                device=device_map,
                token=self.hf_token
            )
            result = translator(text)
            return result[0]["translation_text"]
        except Exception as e:
            print(f"❌ Translation error: {e}")
            raise

    # --------------------------------------------------------
    # 8) Image Captioning
    # --------------------------------------------------------
    def _image_caption(
        self, 
        image: Union[str, Any],
        model: Optional[str] = None
    ) -> str:
        """Generate captions for images."""
        model_name = model or "nlpconnect/vit-gpt2-image-captioning"
        
        try:
            captioner = pipeline(
                "image-to-text",
                model=model_name,
                token=self.hf_token
            )
            result = captioner(image)
            return result[0]["generated_text"]
        except Exception as e:
            print(f"❌ Image captioning error: {e}")
            raise

    # --------------------------------------------------------
    # 9) Classification
    # --------------------------------------------------------
    def _classify(
        self, 
        text: Union[str, List[str]],
        model: Optional[str] = None,
        return_all_scores: bool = False
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Classify text (sentiment analysis by default)."""
        model_name = model or "distilbert-base-uncased-finetuned-sst-2-english"
        device_map = -1 if self.device == "cpu" else 0
        
        try:
            classifier = pipeline(
                "sentiment-analysis",
                model=model_name,
                device=device_map,
                token=self.hf_token,
                return_all_scores=return_all_scores
            )
            result = classifier(text)
            return result[0] if isinstance(text, str) and not return_all_scores else result
        except Exception as e:
            print(f"❌ Classification error: {e}")
            raise
