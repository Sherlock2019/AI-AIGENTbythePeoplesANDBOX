#!/usr/bin/env python3
"""Test all 10 chatbot FAQs and verify formatting."""
import json
import requests
import time

API_URL = "http://localhost:8090"

FAQS = [
    "Explain the lexical definitions for PD, DTI, LTV, and other credit terms.",
    "What is Probability of Default (PD) and how is it calculated?",
    "What is Debt-to-Income Ratio (DTI) and what are acceptable ranges?",
    "What is Loan-to-Value Ratio (LTV) and why does it matter?",
    "How does credit scoring work?",
    "What factors affect credit approval decisions?",
    "What is the difference between FMV and realizable value?",
    "How does fraud detection work in banking?",
    "What is KYC and why is it important?",
    "How are risk scores calculated?",
]

def test_faq(faq: str, index: int):
    """Test a single FAQ."""
    print(f"\n{'='*80}")
    print(f"FAQ {index + 1}/10: {faq}")
    print(f"{'='*80}")
    
    payload = {
        "message": faq,
        "page_id": "chatbot_assistant",
        "context": {"agent_type": "chatbot"},
        "model": "gemma2:2b",
        "agent_id": "chatbot",
    }
    
    try:
        start = time.time()
        resp = requests.post(f"{API_URL}/v1/chat", json=payload, timeout=120)
        elapsed = time.time() - start
        
        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("reply", "")
            source = data.get("source_type", "unknown")
            confidence = data.get("confidence", "unknown")
            
            print(f"\n✅ Response ({elapsed:.1f}s):")
            print(f"Source: {source} | Confidence: {confidence}")
            print(f"\n{reply}")
            
            # Check formatting
            has_bullets = "- " in reply or "* " in reply or "• " in reply
            has_bold = "**" in reply
            has_key_points = "Key Points" in reply or "key points" in reply.lower()
            
            print(f"\n📊 Formatting Check:")
            print(f"  - Has bullet points: {'✅' if has_bullets else '❌'}")
            print(f"  - Has bold text: {'✅' if has_bold else '❌'}")
            print(f"  - Has 'Key Points': {'✅' if has_key_points else '❌'}")
            
            if not has_bullets:
                print(f"  ⚠️  WARNING: Response lacks bullet points!")
            
        else:
            print(f"❌ Error {resp.status_code}: {resp.text[:500]}")
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout after 120s")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    time.sleep(1)  # Rate limiting

if __name__ == "__main__":
    print("Testing all 10 Chatbot FAQs...")
    print(f"API URL: {API_URL}")
    print(f"Model: gemma2:2b")
    
    for idx, faq in enumerate(FAQS):
        test_faq(faq, idx)
        if idx < len(FAQS) - 1:
            print("\n" + "-"*80 + "\n")
    
    print(f"\n{'='*80}")
    print("Testing complete!")
    print(f"{'='*80}")
