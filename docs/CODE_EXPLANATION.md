# 📚 Unified AI API - Code Walkthrough

This document explains every part of the codebase so you can understand and discuss it confidently in interviews.

---

## 🏗️ Architecture Overview

```
unified-ai-api/
├── src/unified_ai/
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── api/                 # HTTP layer
│   │   ├── routes/          # API endpoints
│   │   └── schemas.py       # Request/Response models
│   ├── core/                # Business logic
│   │   ├── llm_client.py    # Abstract LLM interface
│   │   ├── providers/       # Groq, Gemini, OpenAI implementations
│   │   ├── fallback.py      # Automatic failover logic
│   │   └── products.py      # AI product definitions
│   └── storage/             # Data persistence
│       └── session.py       # Conversation history
└── tests/                   # Test suite
```

---

## 1️⃣ Configuration Management (`config.py`)

### What It Does
Loads settings from environment variables with type safety and validation.

### Key Concepts

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Type hints + defaults
    api_port: int = 8000
    groq_api_key: str | None = None
    
    model_config = SettingsConfigDict(
        env_file=".env",  # Load from .env file
    )
```

### Why This Pattern?

| Old Way | Our Way |
|---------|---------|
| `os.getenv("PORT")` returns string | `settings.api_port` returns int |
| No validation | Pydantic validates types |
| Scattered across code | Centralized in one place |
| No IDE autocomplete | Full autocomplete support |


---

## 2️⃣ Abstract LLM Client (`core/llm_client.py`)

### What It Does
Defines a **contract** that all LLM providers must follow.

### Key Concepts: Abstraction

```python
from abc import ABC, abstractmethod

class LLMClient(ABC):
    """Abstract base - cannot be instantiated directly."""
    
    @abstractmethod
    async def complete(self, messages: list[Message]) -> CompletionResult:
        """Every provider MUST implement this."""
        pass
    
    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Every provider MUST implement this."""
        pass
```

### Why Abstraction?

```python
# WITHOUT abstraction - tightly coupled
def chat(provider: str, message: str):
    if provider == "groq":
        # Groq-specific code
    elif provider == "openai":
        # OpenAI-specific code
    # Adding new provider = modify this function!

# WITH abstraction - loosely coupled
def chat(client: LLMClient, message: str):
    return client.complete(message)  # Works with ANY provider!
    # Adding new provider = just create new class
```

### Data Classes

```python
@dataclass
class Message:
    role: str      # "system", "user", "assistant"
    content: str
    
@dataclass  
class CompletionResult:
    content: str           # The generated text
    provider: ProviderName # Who generated it
    input_tokens: int      # For cost tracking
    output_tokens: int     # For cost tracking
    latency_ms: float      # Performance metric
    cost_usd: float        # Money tracking
```

---

## 3️⃣ Provider Implementations (`core/providers/`)

### What They Do
Concrete implementations of the LLMClient interface for each provider.

### Groq Example (`providers/groq.py`)

```python
class GroqClient(LLMClient):
    """Inherits from LLMClient, MUST implement all abstract methods."""
    
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        self._client = AsyncGroq(api_key=api_key)  # Official SDK
    
    @property
    def name(self) -> ProviderName:
        return ProviderName.GROQ  # Identify this provider
    
    async def complete(self, messages, max_tokens, temperature) -> CompletionResult:
        start_time = time.perf_counter()  # Start timing
        
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[m.to_dict() for m in messages],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Extract metrics from response
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            
            return CompletionResult(
                content=response.choices[0].message.content,
                provider=self.name,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=self.estimate_cost(input_tokens, output_tokens),
            )
            
        except RateLimitError as e:
            # Convert to our custom exception
            raise ProviderError(
                provider=self.name,
                message=str(e),
                status_code=429,
                retryable=True,  # Can retry this error
            )
```

### Cost Calculation

```python
GROQ_PRICING = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},  # per 1M tokens
}

def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
    pricing = GROQ_PRICING.get(self.model, DEFAULT_PRICING)
    
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    
    return input_cost + output_cost
```
---

## 4️⃣ Fallback Chain (`core/fallback.py`)

### What It Does
Tries providers in order until one succeeds. Key for **high availability**.

### The Algorithm

```python
class FallbackChain:
    def __init__(self, providers: list[LLMClient]):
        self.providers = providers  # e.g., [groq, gemini, openai]
    
    async def complete(self, messages) -> FallbackResult:
        attempts = []  # Track what we tried
        
        for provider in self.providers:
            try:
                result = await provider.complete(messages)
                
                # Success! Record and return
                attempts.append(FallbackAttempt(provider=provider.name, success=True))
                return FallbackResult(result=result, attempts=attempts)
                
            except ProviderError as e:
                # Failed - record and try next
                attempts.append(FallbackAttempt(
                    provider=provider.name, 
                    success=False,
                    error=str(e)
                ))
                
                # Log for observability
                logger.warning("Provider failed, trying next", 
                              provider=provider.name, error=str(e))
        
        # All failed
        raise AllProvidersFailedError(attempts)
```

### Visual Flow

```
Request comes in
       │
       ▼
┌─────────────┐
│    Groq     │──── Success? ──▶ Return result
└─────────────┘
       │ Fail
       ▼
┌─────────────┐
│   Gemini    │──── Success? ──▶ Return result
└─────────────┘
       │ Fail
       ▼
┌─────────────┐
│   OpenAI    │──── Success? ──▶ Return result
└─────────────┘
       │ Fail
       ▼
   Raise Error
```

---

## 5️⃣ Product Definitions (`core/products.py`)

### What It Does
Defines different AI applications, each with its own system prompt.

### Product Config

```python
class ProductType(str, Enum):
    CHATBOT = "chatbot"
    CODE_REVIEWER = "code_reviewer"
    # etc.

@dataclass(frozen=True)
class ProductConfig:
    name: str
    system_prompt: str    # The magic that makes each product unique
    version: str          # For A/B testing prompts
    max_tokens: int       # Product-specific limit
    temperature: float    # Product-specific creativity
```

### System Prompts - The Secret Sauce

```python
PRODUCTS = {
    ProductType.CODE_REVIEWER: ProductConfig(
        name="Code Reviewer",
        system_prompt="""You are a senior software engineer conducting code review.

Focus on:
1. Bugs & Logic Errors
2. Security vulnerabilities
3. Performance issues
4. Readability

Prioritize issues: 🔴 Critical, 🟡 Important, 🟢 Nice-to-have""",
        
        version="1.3.0",      # Track prompt versions
        max_tokens=2000,      # Code reviews need more space
        temperature=0.3,      # Low = more consistent feedback
    ),
}
```

### Why Version System Prompts?

```python
# Version 1.0.0 - Original
system_prompt="Review this code."

# Version 1.1.0 - Added structure
system_prompt="Review for bugs, security, performance."

# Version 1.3.0 - Current (with priority levels)
system_prompt="... 🔴 Critical, 🟡 Important ..."

# Enables A/B testing: Which version gets better user feedback?
```

---

## 6️⃣ Session Storage (`storage/session.py`)

### What It Does
Maintains conversation history so users can have multi-turn conversations.

### The Interface

```python
class SessionStorage(ABC):
    @abstractmethod
    async def get(self, session_id: str, product: ProductType) -> Session | None:
        pass
    
    @abstractmethod
    async def save(self, session: Session) -> None:
        pass
```

### In-Memory Implementation (Development)

```python
class InMemorySessionStorage(SessionStorage):
    def __init__(self):
        self._sessions: dict[str, Session] = {}  # Simple dict
    
    async def get(self, session_id, product):
        key = f"{product.value}:{session_id}"
        return self._sessions.get(key)
    
    async def save(self, session):
        key = f"{session.product.value}:{session.session_id}"
        self._sessions[key] = session
```

### Redis Implementation (Production)

```python
class RedisSessionStorage(SessionStorage):
    async def get(self, session_id, product):
        key = f"session:{product.value}:{session_id}"
        data = await self._client.get(key)
        return deserialize(data) if data else None
    
    async def save(self, session):
        key = f"session:{session.product.value}:{session.session_id}"
        await self._client.setex(key, self._ttl, serialize(session))
```

### Why Two Implementations?

```
Development          Production
     │                    │
     ▼                    ▼
┌──────────┐        ┌──────────┐
│ In-Memory │       │  Redis   │
│   Fast    │       │ Persists │
│ No setup  │       │ Scalable │
│ Data lost │       │ Shared   │
└──────────┘        └──────────┘
```


---

## 7️⃣ API Layer (`api/`)

### Request/Response Schemas (`schemas.py`)

```python
class CompletionRequest(BaseModel):
    product: ProductType           # Which AI product
    session_id: str               # For conversation continuity
    message: str                  # User's message
    max_tokens: int | None        # Optional override
    temperature: float | None     # Optional override
    
    # Validation built-in!
    @field_validator('message')
    def message_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Message cannot be empty')
        return v
```

### The Main Endpoint (`routes/completion.py`)

```python
@router.post("/api/v1/completion")
async def create_completion(
    request: CompletionRequest,
    fallback_chain: FallbackChain = Depends(get_fallback_chain),
    session_storage: SessionStorage = Depends(get_session_storage),
):
    # 1. Get product config
    product_config = get_product_config(request.product)
    
    # 2. Get or create session
    session = await session_storage.get(request.session_id, request.product)
    if session is None:
        session = Session(
            session_id=request.session_id,
            product=request.product,
            messages=[Message(role="system", content=product_config.system_prompt)]
        )
    
    # 3. Add user message
    session.add_message(Message(role="user", content=request.message))
    
    # 4. Get AI response (with fallback!)
    fallback_result = await fallback_chain.complete(
        messages=session.messages,
        max_tokens=request.max_tokens or product_config.max_tokens,
        temperature=request.temperature or product_config.temperature,
    )
    
    # 5. Save response to session
    session.add_message(Message(role="assistant", content=result.content))
    await session_storage.save(session)
    
    # 6. Return with metrics
    return CompletionResponse(
        response=result.content,
        provider=result.provider,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        # etc.
    )
```

### Dependency Injection

```python
# FastAPI's Depends() injects dependencies
async def get_fallback_chain(request: Request) -> FallbackChain:
    return request.app.state.fallback_chain

@router.post("/completion")
async def create_completion(
    chain: FallbackChain = Depends(get_fallback_chain),  # Injected!
):
    ...
```

### Why Dependency Injection?

```python
# In tests, we can inject a MOCK:
def test_completion(mock_chain):
    app.state.fallback_chain = mock_chain  # No real API calls!
    response = client.post("/completion", ...)
    assert response.status_code == 200
```

---

## 8️⃣ Application Lifecycle (`main.py`)

### Startup/Shutdown

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP - runs before accepting requests
    settings = get_settings()
    
    # Create provider chain
    providers = create_provider_chain(settings)
    app.state.fallback_chain = FallbackChain(providers)
    
    # Create session storage
    app.state.session_storage = create_session_storage(settings.redis_url)
    
    logger.info("API started", providers=[p.name for p in providers])
    
    yield  # Application runs here, handling requests
    
    # SHUTDOWN - runs when stopping
    logger.info("API shutting down")
```

---

## 9️⃣ Testing Strategy

### Unit Tests - Test in Isolation

```python
# tests/unit/test_products.py
def test_all_products_have_configs():
    for product in ProductType:
        assert product in PRODUCTS  # No missing configs
        
def test_system_prompts_not_empty():
    for product, config in PRODUCTS.items():
        assert len(config.system_prompt) > 50  # Meaningful prompts
```

### Integration Tests - Test Together

```python
# tests/integration/test_api_endpoints.py
def test_completion_basic(client):
    response = client.post("/api/v1/completion", json={
        "product": "chatbot",
        "session_id": "test-123",
        "message": "Hello!"
    })
    assert response.status_code == 200
    assert "response" in response.json()
```

### Mock LLM for Tests

```python
# tests/conftest.py
class MockLLMClient(LLMClient):
    async def complete(self, messages, **kwargs):
        return CompletionResult(
            content="Mock response",
            provider=ProviderName.GROQ,
            # ... fake metrics
        )

@pytest.fixture
def client(mock_client):
    app.state.fallback_chain = FallbackChain([mock_client])
    return TestClient(app)
```

---

## 🎯 Key Patterns Summary

| Pattern | Where Used | Why |
|---------|------------|-----|
| **Abstract Factory** | `LLMClient` | Swap providers easily |
| **Strategy** | `FallbackChain` | Different fallback strategies |
| **Repository** | `SessionStorage` | Swap storage backends |
| **Dependency Injection** | FastAPI `Depends` | Testable code |
| **Configuration as Code** | `config.py` | Type-safe settings |

---


## 🚀 Next: Run It Locally!

See the next section for testing instructions.
