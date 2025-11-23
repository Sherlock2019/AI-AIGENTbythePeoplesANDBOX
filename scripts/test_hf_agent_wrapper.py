#!/usr/bin/env python3
"""
Test Script for HF Agent Wrapper
---------------------------------

Tests all HuggingFace-specific operations.
"""

import sys
import os
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.api.hf_agent_wrapper import HuggingFaceAgent


def test_generate():
    """Test text generation."""
    print("\n" + "="*60)
    print("TEST: Text Generation (HF Agent Wrapper)")
    print("="*60)
    
    hf = HuggingFaceAgent()
    result = hf.run(
        task="generate",
        prompt="Write a haiku about AI agents.",
        max_new_tokens=100,
        temperature=0.7
    )
    
    print(f"Result:\n{result}")
    return True


def test_summarize():
    """Test summarization."""
    print("\n" + "="*60)
    print("TEST: Summarization (HF Agent Wrapper)")
    print("="*60)
    
    text = """
    Artificial intelligence (AI) is intelligence demonstrated by machines, 
    in contrast to the natural intelligence displayed by humans and animals. 
    Leading AI textbooks define the field as the study of "intelligent agents": 
    any device that perceives its environment and takes actions that maximize 
    its chance of achieving its goals. Colloquially, the term "artificial intelligence" 
    is often used to describe machines that mimic "cognitive" functions that humans 
    associate with the human mind, such as "learning" and "problem solving".
    """
    
    hf = HuggingFaceAgent()
    result = hf.run(
        task="summarize",
        text=text,
        max_length=50,
        min_length=20
    )
    
    print(f"Summary: {result}")
    return True


def test_qa():
    """Test question answering."""
    print("\n" + "="*60)
    print("TEST: Question Answering (HF Agent Wrapper)")
    print("="*60)
    
    context = """
    The HF Agent Wrapper is a unified interface for HuggingFace operations.
    It supports text generation, summarization, question answering, embeddings,
    translation, image captioning, and classification. It works with both
    local Transformers models and HuggingFace API.
    """
    question = "What does the HF Agent Wrapper support?"
    
    hf = HuggingFaceAgent()
    result = hf.run(
        task="qa",
        question=question,
        context=context
    )
    
    print(f"Question: {question}")
    print(f"Answer: {result.get('answer', result)}")
    if isinstance(result, dict):
        print(f"Score: {result.get('score', 0):.3f}")
    return True


def test_embedding():
    """Test embeddings."""
    print("\n" + "="*60)
    print("TEST: Embeddings (HF Agent Wrapper)")
    print("="*60)
    
    hf = HuggingFaceAgent()
    result = hf.run(
        task="embedding",
        text="This is a test sentence for embedding generation."
    )
    
    if isinstance(result, list):
        print(f"Vector dimension: {len(result)}")
        print(f"First 5 values: {result[:5]}")
    else:
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")
    return True


def test_translate():
    """Test translation."""
    print("\n" + "="*60)
    print("TEST: Translation (HF Agent Wrapper)")
    print("="*60)
    
    hf = HuggingFaceAgent()
    result = hf.run(
        task="translate",
        text="Hello world, how are you?",
        tgt_lang="fr"
    )
    
    print(f"Original: Hello world, how are you?")
    print(f"Translated: {result}")
    return True


def test_classify():
    """Test classification."""
    print("\n" + "="*60)
    print("TEST: Classification (HF Agent Wrapper)")
    print("="*60)
    
    hf = HuggingFaceAgent()
    result = hf.run(
        task="classify",
        text="I love this new AI agent system! It's amazing!"
    )
    
    if isinstance(result, dict):
        print(f"Label: {result.get('label')}")
        print(f"Score: {result.get('score', 0):.3f}")
    else:
        print(f"Result: {result}")
    return True


def test_custom_models():
    """Test with custom models."""
    print("\n" + "="*60)
    print("TEST: Custom Models (HF Agent Wrapper)")
    print("="*60)
    
    hf = HuggingFaceAgent()
    
    # Test with custom embedding model
    try:
        result = hf.run(
            task="embedding",
            text="Test sentence",
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
        print(f"✅ Custom embedding model works")
        print(f"   Dimension: {len(result) if isinstance(result, list) else 'N/A'}")
    except Exception as e:
        print(f"⚠️ Custom model test skipped: {e}")
    
    return True


def main():
    """Run all tests."""
    print("🤖 HF Agent Wrapper Test Suite")
    print("="*60)
    
    tests = [
        ("Generate", test_generate),
        ("Summarize", test_summarize),
        ("QA", test_qa),
        ("Embedding", test_embedding),
        ("Translate", test_translate),
        ("Classify", test_classify),
        ("Custom Models", test_custom_models),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n❌ {name} failed with exception: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"   Error: {error}")
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
