#!/usr/bin/env python3
"""Test all Ollama models directly (standalone, no API)."""
import sys
import json
import time
import requests
from typing import Dict, List, Tuple

OLLAMA_URL = "http://localhost:11434"
TEST_PROMPT = "What is credit appraisal? Answer in one sentence."
TIMEOUT = 30


def get_available_models() -> List[str]:
    """Get list of available Ollama models."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        return models
    except Exception as e:
        print(f"❌ Failed to fetch models: {e}")
        sys.exit(1)


def test_model(model: str) -> Tuple[str, str, float]:
    """Test a single model and return (status, response_preview, duration)."""
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


def main():
    """Main test function."""
    print("🧪 Testing All Ollama Models Directly")
    print("=" * 60)
    print(f"Ollama URL: {OLLAMA_URL}")
    print(f"Test Prompt: {TEST_PROMPT}")
    print(f"Timeout: {TIMEOUT}s per model")
    print("=" * 60)
    print()
    
    # Get models
    print("📋 Step 1: Fetching available models...")
    models = get_available_models()
    if not models:
        print("❌ No models found")
        sys.exit(1)
    
    print(f"✅ Found {len(models)} model(s)")
    print()
    
    # Test each model
    print("🚀 Step 2: Testing each model...")
    print()
    
    results: List[Dict[str, any]] = []
    success_count = 0
    fail_count = 0
    timeout_count = 0
    
    for model in models:
        print("─" * 60)
        print(f"Testing: {model}")
        print("─" * 60)
        
        status, preview, duration = test_model(model)
        
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
    print(f"{'Model':<20} {'Status':<15} {'Duration':<10} {'Preview'}")
    print("-" * 60)
    for r in results:
        preview = r["preview"][:30] + "..." if len(r["preview"]) > 30 else r["preview"]
        print(f"{r['model']:<20} {r['status']:<15} {r['duration']:<10.2f} {preview}")
    
    # Exit code
    if success_count == 0:
        print()
        print("❌ No models working - check Ollama service")
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
