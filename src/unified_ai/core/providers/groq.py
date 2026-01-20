"""
Groq LLM provider implementation.

Groq provides fast inference for open-source models like Llama.
It's often the fastest and cheapest option for development.
"""

import time
from collections.abc import AsyncIterator

from groq import APIError, AsyncGroq, RateLimitError

from unified_ai.core.llm_client import (
    CompletionResult,
    LLMClient,
    Message,
    ProviderError,
    ProviderName,
)

# Groq pricing per 1M tokens (as of Jan 2025)
# https://groq.com/pricing/
GROQ_PRICING = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},
    "gemma2-9b-it": {"input": 0.20, "output": 0.20},
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 0.50, "output": 0.50}


class GroqClient(LLMClient):
    """
    Groq LLM provider.

    Groq is known for extremely fast inference speeds using their
    custom LPU (Language Processing Unit) hardware.

    Example:
        >>> client = GroqClient(api_key="...", model="llama-3.3-70b-versatile")
        >>> result = await client.complete([Message(role="user", content="Hello")])
        >>> print(result.content)
    """

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        """
        Initialize Groq client.

        Args:
            api_key: Groq API key
            model: Model to use (default: llama-3.3-70b-versatile)
        """
        super().__init__(api_key, model)
        self._client = AsyncGroq(api_key=api_key)

    @property
    def name(self) -> ProviderName:
        """Get provider name."""
        return ProviderName.GROQ

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> CompletionResult:
        """
        Generate a completion using Groq.

        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            CompletionResult with generated content

        Raises:
            ProviderError: If Groq API fails
        """
        start_time = time.perf_counter()

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[m.to_dict() for m in messages],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract token counts
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            # Calculate cost
            cost = self.estimate_cost(input_tokens, output_tokens)

            return CompletionResult(
                content=response.choices[0].message.content or "",
                provider=self.name,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=cost,
            )

        except RateLimitError as e:
            raise ProviderError(
                provider=self.name,
                message=f"Rate limit exceeded: {e}",
                status_code=429,
                retryable=True,
            )
        except APIError as e:
            raise ProviderError(
                provider=self.name,
                message=str(e),
                status_code=getattr(e, "status_code", None),
                retryable=getattr(e, "status_code", 500) >= 500,
            )
        except Exception as e:
            raise ProviderError(
                provider=self.name,
                message=f"Unexpected error: {e}",
                retryable=False,
            )

    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream a completion using Groq.

        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            String chunks as generated

        Raises:
            ProviderError: If Groq API fails
        """
        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=[m.to_dict() for m in messages],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except RateLimitError as e:
            raise ProviderError(
                provider=self.name,
                message=f"Rate limit exceeded: {e}",
                status_code=429,
                retryable=True,
            )
        except APIError as e:
            raise ProviderError(
                provider=self.name,
                message=str(e),
                status_code=getattr(e, "status_code", None),
                retryable=getattr(e, "status_code", 500) >= 500,
            )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for a Groq request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pricing = GROQ_PRICING.get(self.model, DEFAULT_PRICING)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost
