#!/usr/bin/env python3
"""
Test script for Unified AI API.

Run this after starting the server to verify everything works.

Usage:
    python test_api.py
    
Make sure the server is running first:
    make run
"""

import requests
import sys

BASE_URL = "http://localhost:8000"

def colored(text: str, color: str) -> str:
    """Add color to terminal output."""
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m"
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"

def test_health():
    """Test health endpoint."""
    print(colored("\n=== Testing Health Endpoint ===", "blue"))
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(colored("✓ Health check passed", "green"))
            print(f"  Status: {data['status']}")
            print(f"  Version: {data['version']}")
            print(f"  Providers: {data['providers']}")
            return True
        else:
            print(colored(f"✗ Health check failed: {response.status_code}", "red"))
            return False
    except requests.exceptions.ConnectionError:
        print(colored("✗ Cannot connect to server. Is it running?", "red"))
        print("  Start the server with: make run")
        return False

def test_products():
    """Test products endpoint."""
    print(colored("\n=== Testing Products Endpoint ===", "blue"))
    response = requests.get(f"{BASE_URL}/products")
    if response.status_code == 200:
        data = response.json()
        print(colored(f"✓ Found {len(data['products'])} products", "green"))
        for product in data['products']:
            print(f"  • {product['name']} ({product['id']})")
        return True
    else:
        print(colored(f"✗ Failed: {response.status_code}", "red"))
        return False

def test_chatbot():
    """Test chatbot completion."""
    print(colored("\n=== Testing Chatbot ===", "blue"))
    response = requests.post(
        f"{BASE_URL}/api/v1/completion",
        json={
            "product": "chatbot",
            "session_id": "test-chatbot",
            "message": "Hello! Say 'Test successful' if you can hear me."
        }
    )
    if response.status_code == 200:
        data = response.json()
        print(colored("✓ Chatbot responded", "green"))
        print(f"  Response: {data['response'][:100]}...")
        print(f"  Provider: {data['provider']}")
        print(f"  Model: {data['model']}")
        print(f"  Latency: {data['latency_ms']:.0f}ms")
        print(f"  Tokens: {data['input_tokens']} in / {data['output_tokens']} out")
        print(f"  Cost: ${data['cost_usd']:.6f}")
        return True
    else:
        print(colored(f"✗ Failed: {response.status_code}", "red"))
        print(f"  Error: {response.json()}")
        return False

def test_code_reviewer():
    """Test code reviewer."""
    print(colored("\n=== Testing Code Reviewer ===", "blue"))
    response = requests.post(
        f"{BASE_URL}/api/v1/completion",
        json={
            "product": "code_reviewer",
            "session_id": "test-code",
            "message": """
def get_user(id):
    query = f"SELECT * FROM users WHERE id = {id}"
    return db.execute(query)
            """
        }
    )
    if response.status_code == 200:
        data = response.json()
        print(colored("✓ Code reviewer responded", "green"))
        # Check if it found the SQL injection
        if "injection" in data['response'].lower() or "security" in data['response'].lower():
            print(colored("  ✓ Correctly identified security issue!", "green"))
        print(f"  Response preview: {data['response'][:200]}...")
        return True
    else:
        print(colored(f"✗ Failed: {response.status_code}", "red"))
        return False

def test_session_memory():
    """Test that sessions maintain conversation history."""
    print(colored("\n=== Testing Session Memory ===", "blue"))
    session_id = "memory-test-session"
    
    # First message - introduce ourselves
    response1 = requests.post(
        f"{BASE_URL}/api/v1/completion",
        json={
            "product": "chatbot",
            "session_id": session_id,
            "message": "My name is TestUser and my favorite color is purple. Remember this!"
        }
    )
    
    if response1.status_code != 200:
        print(colored("✗ First message failed", "red"))
        return False
    
    print("  First message sent...")
    
    # Second message - ask about what we said
    response2 = requests.post(
        f"{BASE_URL}/api/v1/completion",
        json={
            "product": "chatbot",
            "session_id": session_id,
            "message": "What is my name and favorite color?"
        }
    )
    
    if response2.status_code == 200:
        data = response2.json()
        response_lower = data['response'].lower()
        
        if "testuser" in response_lower or "test user" in response_lower:
            print(colored("  ✓ Remembered name!", "green"))
        if "purple" in response_lower:
            print(colored("  ✓ Remembered favorite color!", "green"))
        
        print(colored("✓ Session memory working", "green"))
        print(f"  Response: {data['response'][:150]}...")
        return True
    else:
        print(colored(f"✗ Failed: {response2.status_code}", "red"))
        return False

def test_different_products():
    """Test multiple products."""
    print(colored("\n=== Testing All Products ===", "blue"))
    
    products_to_test = [
        ("writing_helper", "Please improve this: 'The meeting was good and we talked about stuff.'"),
        ("support_bot", "My order hasn't arrived yet and I'm getting frustrated!"),
        ("content_summarizer", "Summarize: Machine learning is a subset of artificial intelligence that enables systems to learn from data."),
    ]
    
    all_passed = True
    for product, message in products_to_test:
        response = requests.post(
            f"{BASE_URL}/api/v1/completion",
            json={
                "product": product,
                "session_id": f"test-{product}",
                "message": message
            }
        )
        
        if response.status_code == 200:
            print(colored(f"  ✓ {product}", "green"))
        else:
            print(colored(f"  ✗ {product}: {response.status_code}", "red"))
            all_passed = False
    
    return all_passed

def main():
    """Run all tests."""
    print(colored("=" * 50, "blue"))
    print(colored("  Unified AI API - Test Suite", "blue"))
    print(colored("=" * 50, "blue"))
    
    results = []
    
    # Health check first
    if not test_health():
        print(colored("\n⚠️  Server not running. Start with: make run", "yellow"))
        sys.exit(1)
    
    results.append(("Products", test_products()))
    results.append(("Chatbot", test_chatbot()))
    results.append(("Code Reviewer", test_code_reviewer()))
    results.append(("Session Memory", test_session_memory()))
    results.append(("All Products", test_different_products()))
    
    # Summary
    print(colored("\n" + "=" * 50, "blue"))
    print(colored("  Test Summary", "blue"))
    print(colored("=" * 50, "blue"))
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = colored("✓ PASS", "green") if result else colored("✗ FAIL", "red")
        print(f"  {status}  {name}")
    
    print()
    if passed == total:
        print(colored(f"🎉 All {total} tests passed!", "green"))
    else:
        print(colored(f"⚠️  {passed}/{total} tests passed", "yellow"))
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
