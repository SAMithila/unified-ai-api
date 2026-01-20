# 🧪 Local Testing Guide

This guide helps you test the Unified AI API on your local machine.

---

## Prerequisites

- Python 3.10 or higher
- At least ONE LLM API key (Groq recommended - it's free!)

---

## Step 1: Get API Keys

### Option A: Groq (Recommended - Free & Fast)
1. Go to https://console.groq.com/keys
2. Sign up / Log in
3. Create new API key
4. Copy the key

### Option B: Google Gemini (You already have this!)
1. Go to https://aistudio.google.com/app/apikey
2. Create/copy your API key

### Option C: OpenAI
1. Go to https://platform.openai.com/api-keys
2. Create new key

---

## Step 2: Setup Project

```bash
# Navigate to project folder
cd /Users/mithila/unified-ai-api

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On Mac/Linux
# OR
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -e ".[dev]"
```

---

## Step 3: Configure Environment

```bash
# Copy the template
cp .env.example .env

# Edit .env file and add your API key(s)
# nano .env  OR  open with any text editor
```

**Minimum .env file:**
```bash
# At least ONE of these:
GROQ_API_KEY=gsk_your_groq_key_here
# OR
GOOGLE_API_KEY=your_google_key_here
# OR
OPENAI_API_KEY=sk-your_openai_key_here
```

---

## Step 4: Run the Server

```bash
# Using Makefile
make run

# OR directly
uvicorn unified_ai.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Provider configured provider=groq model=llama-3.3-70b-versatile
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 5: Test the API

### Option A: Interactive Docs (Easiest)
1. Open http://localhost:8000/docs
2. You'll see all endpoints
3. Click "Try it out" on any endpoint
4. Fill in parameters and "Execute"

### Option B: Frontend Demo
1. Open http://localhost:8000/demo
2. Select a product
3. Start chatting!

### Option C: cURL Commands

**Health Check:**
```bash
curl http://localhost:8000/health
```

Expected:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "providers": {"groq": true}
}
```

**List Products:**
```bash
curl http://localhost:8000/products
```

**Chat with Chatbot:**
```bash
curl -X POST http://localhost:8000/api/v1/completion \
  -H "Content-Type: application/json" \
  -d '{
    "product": "chatbot",
    "session_id": "test-123",
    "message": "Hello! What can you help me with?"
  }'
```

Expected Response:
```json
{
  "response": "Hello! I'm here to help you with...",
  "session_id": "test-123",
  "product": "chatbot",
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "input_tokens": 52,
  "output_tokens": 87,
  "latency_ms": 234.5,
  "cost_usd": 0.000099,
  "fallback_used": false
}
```

**Code Review:**
```bash
curl -X POST http://localhost:8000/api/v1/completion \
  -H "Content-Type: application/json" \
  -d '{
    "product": "code_reviewer",
    "session_id": "pr-456",
    "message": "def calculate_average(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total / len(nums)"
  }'
```

### Option D: Python Script

Create `test_api.py`:
```python
import requests

BASE_URL = "http://localhost:8000"

# Health check
print("=== Health Check ===")
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# Chat
print("\n=== Chatbot ===")
response = requests.post(
    f"{BASE_URL}/api/v1/completion",
    json={
        "product": "chatbot",
        "session_id": "my-session",
        "message": "What is machine learning in simple terms?"
    }
)
data = response.json()
print(f"Response: {data['response'][:200]}...")
print(f"Provider: {data['provider']}")
print(f"Latency: {data['latency_ms']:.0f}ms")
print(f"Cost: ${data['cost_usd']:.6f}")

# Code Review
print("\n=== Code Reviewer ===")
response = requests.post(
    f"{BASE_URL}/api/v1/completion",
    json={
        "product": "code_reviewer",
        "session_id": "pr-review",
        "message": """
def get_user(id):
    query = f"SELECT * FROM users WHERE id = {id}"
    return db.execute(query)
        """
    }
)
data = response.json()
print(f"Review: {data['response'][:500]}...")

# Test session continuity
print("\n=== Session Memory Test ===")
session = "memory-test"

# First message
requests.post(f"{BASE_URL}/api/v1/completion", json={
    "product": "chatbot",
    "session_id": session,
    "message": "My name is Mithila and I'm learning AI."
})

# Second message - should remember
response = requests.post(f"{BASE_URL}/api/v1/completion", json={
    "product": "chatbot",
    "session_id": session,
    "message": "What is my name?"
})
print(f"Memory test: {response.json()['response']}")
```

Run it:
```bash
python test_api.py
```

---

## Step 6: Run Tests

```bash
# Run all tests
make test

# Run only unit tests
make test-unit

# Run with verbose output
pytest tests/ -v
```

Expected output:
```
tests/unit/test_llm_client.py::TestMessage::test_message_creation PASSED
tests/unit/test_llm_client.py::TestMessage::test_message_to_dict PASSED
tests/unit/test_products.py::TestProductType::test_product_values PASSED
tests/integration/test_api_endpoints.py::TestHealthEndpoints::test_root_endpoint PASSED
...

================== 15 passed in 2.34s ==================
```

---

## Troubleshooting

### "No LLM providers configured"
- Check your `.env` file has at least one API key
- Make sure the key name matches: `GROQ_API_KEY`, `GOOGLE_API_KEY`, etc.

### "Connection refused"
- Make sure the server is running (`make run`)
- Check you're using the right port (default: 8000)

### "Rate limit exceeded"
- Groq has generous free limits, but you might hit them with rapid testing
- Wait a minute and try again
- Or add another provider as fallback

### "Import error"
- Make sure you installed with `pip install -e ".[dev]"`
- Make sure your virtual environment is activated

---

## Next Steps

Once testing works locally:

1. **Push to GitHub** (see main README)
2. **Add more tests** for edge cases
3. **Try the frontend demo** at http://localhost:8000/demo
4. **Deploy** (Railway, Render, or Docker)

---

## Quick Reference

| Command | What it does |
|---------|--------------|
| `make run` | Start development server |
| `make test` | Run all tests |
| `make lint` | Check code style |
| `make format` | Auto-format code |
| `curl localhost:8000/health` | Check API status |
| `open localhost:8000/docs` | Interactive API docs |
| `open localhost:8000/demo` | Frontend demo |
