#!/usr/bin/env python3
"""
Test Script for Agent Manager
------------------------------

Tests all agent tasks through the unified interface.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.api.agent_manager import get_agent_manager


def test_generate():
    """Test text generation."""
    print("\n" + "="*60)
    print("TEST: Text Generation")
    print("="*60)
    
    manager = get_agent_manager()
    result = manager.run(
        task="generate",
        prompt="Write a haiku about AI agents.",
        max_new_tokens=100,
        temperature=0.7
    )
    
    print(f"Source: {result.get('source')}")
    print(f"Latency: {result.get('latency')}s")
    print(f"Result:\n{result.get('result')}")
    return result.get("error") is None


def test_summarize():
    """Test summarization."""
    print("\n" + "="*60)
    print("TEST: Summarization")
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
    
    manager = get_agent_manager()
    result = manager.run(
        task="summarize",
        text=text,
        max_length=50,
        min_length=20
    )
    
    print(f"Source: {result.get('source')}")
    print(f"Latency: {result.get('latency')}s")
    print(f"Summary: {result.get('result')}")
    return result.get("error") is None


def test_qa():
    """Test question answering."""
    print("\n" + "="*60)
    print("TEST: Question Answering")
    print("="*60)
    
    context = """
    The Agent Manager is a unified interface for all model operations.
    It supports text generation, summarization, question answering, embeddings,
    translation, image captioning, and classification. It automatically handles
    failover between local models, Ollama, and HuggingFace API.
    """
    question = "What does the Agent Manager support?"
    
    manager = get_agent_manager()
    result = manager.run(
        task="qa",
        question=question,
        context=context
    )
    
    print(f"Source: {result.get('source')}")
    print(f"Latency: {result.get('latency')}s")
    qa_result = result.get("result", {})
    if isinstance(qa_result, dict):
        print(f"Answer: {qa_result.get('answer')}")
        print(f"Score: {qa_result.get('score', 0):.3f}")
    else:
        print(f"Result: {qa_result}")
    return result.get("error") is None


def test_embedding():
    """Test embeddings."""
    print("\n" + "="*60)
    print("TEST: Embeddings")
    print("="*60)
    
    manager = get_agent_manager()
    result = manager.run(
        task="embedding",
        text="This is a test sentence for embedding generation."
    )
    
    print(f"Source: {result.get('source')}")
    print(f"Latency: {result.get('latency')}s")
    embedding = result.get("result", [])
    if isinstance(embedding, list):
        print(f"Vector dimension: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")
    return result.get("error") is None


def test_classify():
    """Test classification."""
    print("\n" + "="*60)
    print("TEST: Classification (Sentiment Analysis)")
    print("="*60)
    
    manager = get_agent_manager()
    result = manager.run(
        task="classify",
        text="I love this new AI agent system! It's amazing!"
    )
    
    print(f"Source: {result.get('source')}")
    print(f"Latency: {result.get('latency')}s")
    classification = result.get("result", {})
    if isinstance(classification, dict):
        print(f"Label: {classification.get('label')}")
        print(f"Score: {classification.get('score', 0):.3f}")
    else:
        print(f"Result: {classification}")
    return result.get("error") is None


def test_health():
    """Test health check."""
    print("\n" + "="*60)
    print("TEST: Health Check")
    print("="*60)
    
    manager = get_agent_manager()
    print(f"Device: {manager.device}")
    print(f"Models loaded: {json.dumps(manager.loaded_models, indent=2)}")
    return True


def main():
    """Run all tests."""
    print("🤖 Agent Manager Test Suite")
    print("="*60)
    
    tests = [
        ("Health Check", test_health),
        ("Generate", test_generate),
        ("Summarize", test_summarize),
        ("QA", test_qa),
        ("Embedding", test_embedding),
        ("Classify", test_classify),
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
