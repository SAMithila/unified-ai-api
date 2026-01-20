"""
Abstract base class for LLM providers.

This module defines the interface that all LLM providers must implement,
enabling easy swapping of providers and fallback chains.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncIterator


class ProviderName(str, Enum):
    """Supported LLM providers."""

    GROQ = "groq"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "system", "user", or "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for API calls."""
        return {"role": self.role, "content": self.content}


@dataclass
class CompletionResult:
    """Result of a completion request."""

    content: str
    provider: ProviderName
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


@dataclass
class ProviderError(Exception):
    """Exception raised when a provider fails."""

    provider: ProviderName
    message: str
    status_code: int | None = None
    retryable: bool = True

    def __str__(self) -> str:
        return f"{self.provider.value}: {self.message}"


class LLMClient(ABC):
    """
    Abstract base class for LLM providers.
    
    All provider implementations must inherit from this class and implement
    the required methods. This enables:
    - Easy provider swapping
    - Fallback chains
    - Consistent interface across providers
    - Proper cost tracking
    """

    def __init__(self, api_key: str, model: str):
        """
        Initialize the LLM client.
        
        Args:
            api_key: API key for the provider
            model: Model identifier to use
        """
        self.api_key = api_key
        self.model = model

    @property
    @abstractmethod
    def name(self) -> ProviderName:
        """Get the provider name."""
        pass

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> CompletionResult:
        """
        Generate a completion from the given messages.
        
        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            CompletionResult with the generated content and metadata
            
        Raises:
            ProviderError: If the provider fails
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream a completion from the given messages.
        
        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)
            
        Yields:
            String chunks as they are generated
            
        Raises:
            ProviderError: If the provider fails
        """
        pass

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate the cost in USD for a request.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        pass

    async def health_check(self) -> bool:
        """
        Check if the provider is healthy.
        
        Returns:
            True if provider is available, False otherwise
        """
        try:
            # Send a minimal request to check connectivity
            await self.complete(
                messages=[Message(role="user", content="Hi")],
                max_tokens=5,
            )
            return True
        except ProviderError:
            return False
