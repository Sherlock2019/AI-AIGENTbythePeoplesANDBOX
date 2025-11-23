#!/usr/bin/env python3
"""Test LLM models - works with Ollama directly or via API."""
import sys
import json
import time
import requests
from typing import Dict, List, Optional, Tuple

OLLAMA_URL = "http://localhost:11434"
API_URL = "http://localhost:8090"
TEST_PROMPT = "What is credit appraisal? Answer in one sentence."
TIMEOUT = 30


def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except:
        return False


def check_api() -> bool:
    """Check if API server is running."""
    try:
        resp = requests.get(f"{API_URL}/v1/chat/models", timeout=3)
        return resp.status_code == 200
    except:
        return False


def get_models_via_ollama() -> List[str]:
    """Get models directly from Ollama."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception as e:
        print(f"❌ Failed to fetch models from Ollama: {e}")
        return []


def get_models_via_api() -> List[str]:
    """Get models via API."""
    try:
        resp = requests.get(f"{API_URL}/v1/chat/models", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get("models", [])
    except Exception as e:
        print(f"❌ Failed to fetch models from API: {e}")
        return []


def test_model_ollama(model: str) -> Tuple[str, str, float]:
    """Test a model directly via Ollama."""
    start_time = time.time()
    
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": TEST_PROMPT,
                "stream": False,
                "options": {
                    "num_predict": 50,
                    "temperature": 0.7,
                },
            },
            timeout=TIMEOUT,
        )
        
        duration = time.time() - start_time
        
        if resp.status_code != 200:
            return ("ERROR", f"HTTP {resp.status_code}", duration)
        
        data = resp.json()
        response_text = data.get("response", "")
        done = data.get("done", False)
        
        if response_text:
            preview = response_text[:150].replace("\n", " ")
            status = "SUCCESS" if done else "PARTIAL"
            return (status, preview, duration)
        else:
            return ("NO_RESPONSE", "No response text", duration)
            
    except requests.exceptions.Timeout:
        duration = time.time() - start_time
        return ("TIMEOUT", f"Timeout after {TIMEOUT}s", duration)
    except requests.exceptions.ConnectionError:
        duration = time.time() - start_time
        return ("CONNECTION_ERROR", "Cannot connect to Ollama", duration)
    except Exception as e:
        duration = time.time() - start_time
        return ("ERROR", str(e)[:100], duration)


def test_model_api(model: str) -> Tuple[str, str, float]:
    """Test a model via API."""
    start_time = time.time()
    
    try:
        resp = requests.post(
            f"{API_URL}/v1/chat",
            json={
                "message": TEST_PROMPT,
                "page_id": "test",
                "model": model,
            },
            timeout=TIMEOUT,
        )
        
        duration = time.time() - start_time
        
        if resp.status_code != 200:
            return ("ERROR", f"HTTP {resp.status_code}", duration)
        
        data = resp.json()
        reply = data.get("reply", "")
        
        if reply:
            preview = reply[:150].replace("\n", " ")
            return ("SUCCESS", preview, duration)
        else:
            return ("NO_RESPONSE", "No reply in response", duration)
            
    except requests.exceptions.Timeout:
        duration = time.time() - start_time
        return ("TIMEOUT", f"Timeout after {TIMEOUT}s", duration)
    except requests.exceptions.ConnectionError:
        duration = time.time() - start_time
        return ("CONNECTION_ERROR", "Cannot connect to API", duration)
    except Exception as e:
        duration = time.time() - start_time
        return ("ERROR", str(e)[:100], duration)


def main():
    """Main test function."""
    print("🧪 Model Testing Tool")
    print("=" * 60)
    print(f"Test Prompt: {TEST_PROMPT}")
    print(f"Timeout: {TIMEOUT}s per model")
    print("=" * 60)
    print()
    
    # Check what's available
    ollama_available = check_ollama()
    api_available = check_api()
    
    print("📡 Checking services...")
    print(f"   Ollama: {'✅ Running' if ollama_available else '❌ Not running'}")
    print(f"   API: {'✅ Running' if api_available else '❌ Not running'}")
    print()
    
    if not ollama_available and not api_available:
        print("❌ Neither Ollama nor API is running!")
        print()
        print("To start services:")
        print("  1. Start Ollama: ollama serve")
        print("  2. Start API: python services/api/main.py")
        sys.exit(1)
    
    # Get models
    models = []
    use_api = False
    
    if api_available:
        print("📋 Fetching models from API...")
        models = get_models_via_api()
        use_api = True
    elif ollama_available:
        print("📋 Fetching models from Ollama...")
        models = get_models_via_ollama()
        use_api = False
    
    if not models:
        print("❌ No models found")
        sys.exit(1)
    
    print(f"✅ Found {len(models)} model(s)")
    print()
    
    # Test each model
    print("🚀 Testing models...")
    print()
    
    results: List[Dict[str, any]] = []
    success_count = 0
    fail_count = 0
    timeout_count = 0
    
    for model in models:
        print("─" * 60)
        print(f"Testing: {model}")
        print("─" * 60)
        
        if use_api:
            status, preview, duration = test_model_api(model)
        else:
            status, preview, duration = test_model_ollama(model)
        
        if status == "SUCCESS":
            print(f"✅ SUCCESS ({duration:.2f}s)")
            print(f"Response: {preview}...")
            success_count += 1
        elif status == "PARTIAL":
            print(f"⚠️  PARTIAL ({duration:.2f}s)")
            print(f"Response: {preview}...")
            success_count += 1
        elif status == "TIMEOUT":
            print(f"⏱️  TIMEOUT ({duration:.2f}s)")
            timeout_count += 1
        else:
            print(f"❌ {status} ({duration:.2f}s)")
            print(f"Details: {preview}")
            fail_count += 1
        
        results.append({
            "model": model,
            "status": status,
            "duration": duration,
            "preview": preview,
        })
        print()
    
    # Summary
    print("=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print()
    print(f"Total Models Tested: {len(models)}")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"⏱️  Timeouts: {timeout_count}")
    print()
    
    if success_count > 0:
        print("✅ Working Models:")
        for r in results:
            if r["status"] in ("SUCCESS", "PARTIAL"):
                print(f"   - {r['model']} ({r['duration']:.2f}s)")
        print()
    
    if timeout_count > 0:
        print("⏱️  Timed Out Models:")
        for r in results:
            if r["status"] == "TIMEOUT":
                print(f"   - {r['model']}")
        print()
    
    if fail_count > 0:
        print("❌ Failed Models:")
        for r in results:
            if r["status"] not in ("SUCCESS", "PARTIAL", "TIMEOUT"):
                print(f"   - {r['model']}: {r['status']}")
        print()
    
    # Detailed results table
    print("=" * 60)
    print("📋 DETAILED RESULTS")
    print("=" * 60)
    print(f"{'Model':<25} {'Status':<15} {'Duration':<10} {'Preview'}")
    print("-" * 60)
    for r in results:
        preview = r["preview"][:25] + "..." if len(r["preview"]) > 25 else r["preview"]
        print(f"{r['model']:<25} {r['status']:<15} {r['duration']:<10.2f} {preview}")
    
    # Exit code
    if success_count == 0:
        print()
        print("❌ No models working")
        sys.exit(1)
    elif fail_count > 0 or timeout_count > 0:
        print()
        print("⚠️  Some models have issues")
        sys.exit(2)
    else:
        print()
        print("✅ All models working correctly!")
        sys.exit(0)


if __name__ == "__main__":
    main()
