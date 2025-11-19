#!/usr/bin/env python3
"""Test script to verify chatbot agent functionality."""
import sys
import json
import requests
from pathlib import Path

API_URL = "http://localhost:8090"
OLLAMA_URL = "http://localhost:11434"

def test_api_health():
    """Test API health endpoint."""
    print("1. Testing API health...")
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        if resp.status_code == 200:
            print(f"   ✅ API is healthy: {resp.json()}")
            return True
        else:
            print(f"   ❌ API health check failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ API health check error: {e}")
        return False

def test_chat_models():
    """Test chat models endpoint."""
    print("\n2. Testing chat models endpoint...")
    try:
        resp = requests.get(f"{API_URL}/v1/chat/models", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("models", [])
            print(f"   ✅ Models endpoint working: {len(models)} models available")
            print(f"   📋 Available models: {', '.join(models[:5])}")
            return True
        else:
            print(f"   ❌ Models endpoint failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Models endpoint error: {e}")
        return False

def test_chat_endpoint():
    """Test chat endpoint."""
    print("\n3. Testing chat endpoint...")
    try:
        payload = {
            "message": "What is credit appraisal?",
            "page_id": "credit_appraisal",
            "context": {"agent_type": "credit"}
        }
        resp = requests.post(
            f"{API_URL}/v1/chat",
            json=payload,
            timeout=60
        )
        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("reply", "")
            retrieved = data.get("retrieved", [])
            print(f"   ✅ Chat endpoint working")
            print(f"   💬 Reply length: {len(reply)} chars")
            print(f"   📚 Retrieved documents: {len(retrieved)}")
            if retrieved:
                print(f"   📄 Top match: {retrieved[0].get('title', 'N/A')} (score: {retrieved[0].get('score', 0):.3f})")
            return True
        else:
            print(f"   ❌ Chat endpoint failed: {resp.status_code} - {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Chat endpoint error: {e}")
        return False

def test_ollama_connection():
    """Test Ollama connection."""
    print("\n4. Testing Ollama connection...")
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("models", [])
            print(f"   ✅ Ollama is running: {len(models)} models available")
            model_names = [m.get("name", "") for m in models[:3]]
            print(f"   🤖 Models: {', '.join(model_names)}")
            return True
        else:
            print(f"   ⚠️  Ollama connection issue: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ⚠️  Ollama not available: {e}")
        print("   ℹ️  Chatbot will use fallback mode (RAG only)")
        return False

def test_rag_store():
    """Test RAG store availability."""
    print("\n5. Testing RAG store...")
    try:
        rag_store_path = Path(__file__).parent / "services" / "api" / ".rag_store"
        embeddings_path = rag_store_path / "embeddings.npy"
        metadata_path = rag_store_path / "metadata.json"
        
        if embeddings_path.exists() and metadata_path.exists():
            import json
            with open(metadata_path) as f:
                metadata = json.load(f)
            print(f"   ✅ RAG store exists: {len(metadata)} documents indexed")
            return True
        else:
            print(f"   ⚠️  RAG store not initialized (embeddings: {embeddings_path.exists()}, metadata: {metadata_path.exists()})")
            print("   ℹ️  Chatbot will use TF-IDF fallback")
            return False
    except Exception as e:
        print(f"   ⚠️  RAG store check error: {e}")
        return False

def test_file_upload():
    """Test file upload endpoint."""
    print("\n6. Testing file upload endpoint...")
    try:
        # Create a test file
        test_content = "This is a test document for chatbot ingestion.\nIt contains sample text about credit appraisal."
        files = {
            "file": ("test.txt", test_content, "text/plain")
        }
        data = {"max_rows": 500}
        resp = requests.post(
            f"{API_URL}/v1/chat/upload",
            files=files,
            data=data,
            timeout=30
        )
        if resp.status_code == 200:
            result = resp.json()
            print(f"   ✅ File upload working: {result.get('message', 'Success')}")
            return True
        else:
            print(f"   ⚠️  File upload failed: {resp.status_code} - {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"   ⚠️  File upload error: {e}")
        return False

def check_ui_files():
    """Check UI component files exist."""
    print("\n7. Checking UI component files...")
    base_path = Path(__file__).parent
    files_to_check = [
        "services/ui/pages/chatbot_assistant.py",
        "services/ui/components/chat_assistant.py",
        "services/api/routers/chat.py",
    ]
    all_exist = True
    for file_path in files_to_check:
        full_path = base_path / file_path
        if full_path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - MISSING")
            all_exist = False
    return all_exist

def main():
    """Run all tests."""
    print("=" * 60)
    print("Chatbot Agent Functionality Test")
    print("=" * 60)
    
    results = []
    results.append(("API Health", test_api_health()))
    results.append(("Chat Models", test_chat_models()))
    results.append(("Chat Endpoint", test_chat_endpoint()))
    results.append(("Ollama Connection", test_ollama_connection()))
    results.append(("RAG Store", test_rag_store()))
    results.append(("File Upload", test_file_upload()))
    results.append(("UI Files", check_ui_files()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Chatbot agent is fully working.")
        return 0
    elif passed >= total - 2:
        print("\n⚠️  Most tests passed. Chatbot should work with some limitations.")
        return 0
    else:
        print("\n❌ Multiple tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
