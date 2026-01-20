"""
Pytest configuration and fixtures.
"""

import pytest
from fastapi.testclient import TestClient

from unified_ai.core.fallback import FallbackChain
from unified_ai.core.llm_client import (
    CompletionResult,
    LLMClient,
    Message,
    ProviderName,
)
from unified_ai.main import create_app
from unified_ai.storage.session import InMemorySessionStorage


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(
        self,
        response: str = "Mock response",
        should_fail: bool = False,
        fail_message: str = "Mock failure",
    ):
        super().__init__(api_key="mock-key", model="mock-model")
        self._response = response
        self._should_fail = should_fail
        self._fail_message = fail_message

    @property
    def name(self) -> ProviderName:
        return ProviderName.GROQ  # Use GROQ as placeholder

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> CompletionResult:
        if self._should_fail:
            from unified_ai.core.llm_client import ProviderError

            raise ProviderError(
                provider=self.name,
                message=self._fail_message,
            )

        return CompletionResult(
            content=self._response,
            provider=self.name,
            model=self.model,
            input_tokens=10,
            output_tokens=5,
            latency_ms=100.0,
            cost_usd=0.0001,
        )

    async def stream(self, messages, max_tokens=1000, temperature=0.7):
        yield self._response

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0001


@pytest.fixture
def mock_client():
    """Create a mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def mock_failing_client():
    """Create a mock LLM client that fails."""
    return MockLLMClient(should_fail=True)


@pytest.fixture
def mock_fallback_chain(mock_client):
    """Create a fallback chain with mock client."""
    return FallbackChain(providers=[mock_client])


@pytest.fixture
def session_storage():
    """Create in-memory session storage."""
    return InMemorySessionStorage()


@pytest.fixture
def app(mock_fallback_chain, session_storage):
    """Create test application with mock dependencies."""
    app = create_app()
    app.state.fallback_chain = mock_fallback_chain
    app.state.session_storage = session_storage
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)
