#!/bin/bash
# Test Agent Manager API endpoints

API_URL="${API_URL:-http://localhost:8000}"

echo "🤖 Testing Agent Manager API"
echo "API URL: $API_URL"
echo ""

# Health check
echo "1. Health Check"
echo "---------------"
curl -s "$API_URL/agent/health" | jq '.'
echo ""

# Models status
echo "2. Models Status"
echo "----------------"
curl -s "$API_URL/agent/models" | jq '.'
echo ""

# Test generation
echo "3. Text Generation"
echo "------------------"
curl -s -X POST "$API_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "generate",
    "payload": {
      "prompt": "Write a haiku about AI.",
      "max_new_tokens": 50
    }
  }' | jq '.'
echo ""

# Test summarization
echo "4. Summarization"
echo "----------------"
curl -s -X POST "$API_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "summarize",
    "payload": {
      "text": "Artificial intelligence is transforming the world. AI systems can now perform complex tasks that were once thought to be exclusive to humans. From natural language processing to computer vision, AI is revolutionizing industries across the globe.",
      "max_length": 50
    }
  }' | jq '.'
echo ""

# Test QA
echo "5. Question Answering"
echo "---------------------"
curl -s -X POST "$API_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "qa",
    "payload": {
      "question": "What is the Agent Manager?",
      "context": "The Agent Manager is a unified interface for all model operations. It supports multiple tasks and engines."
    }
  }' | jq '.'
echo ""

# Test embedding
echo "6. Embedding"
echo "------------"
curl -s -X POST "$API_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "embedding",
    "payload": {
      "text": "This is a test sentence."
    }
  }' | jq '.result | length'
echo ""

# Test classification
echo "7. Classification"
echo "-----------------"
curl -s -X POST "$API_URL/agent/run" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "classify",
    "payload": {
      "text": "I love this new system!"
    }
  }' | jq '.'
echo ""

echo "✅ Tests completed!"
