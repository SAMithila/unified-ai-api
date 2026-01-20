"""
OpenAI LLM provider implementation.

OpenAI is the most widely used LLM provider, offering GPT-4 and GPT-3.5 models.
"""

import time
from collections.abc import AsyncIterator

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError

from unified_ai.core.llm_client import (
    CompletionResult,
    LLMClient,
    Message,
    ProviderError,
    ProviderName,
)

# OpenAI pricing per 1M tokens (as of Jan 2025)
# https://openai.com/pricing
OPENAI_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "o1": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 3.00, "output": 12.00},
}

DEFAULT_PRICING = {"input": 5.00, "output": 15.00}


class OpenAIClient(LLMClient):
    """
    OpenAI LLM provider.

    OpenAI's GPT models are industry standard, with gpt-4o-mini
    offering excellent price/performance for most tasks.

    Example:
        >>> client = OpenAIClient(api_key="...", model="gpt-4o-mini")
        >>> result = await client.complete([Message(role="user", content="Hello")])
        >>> print(result.content)
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model to use (default: gpt-4o-mini)
        """
        super().__init__(api_key, model)
        self._client = AsyncOpenAI(api_key=api_key)

    @property
    def name(self) -> ProviderName:
        """Get provider name."""
        return ProviderName.OPENAI

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> CompletionResult:
        """
        Generate a completion using OpenAI.

        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            CompletionResult with generated content

        Raises:
            ProviderError: If OpenAI API fails
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

            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

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
        except APIConnectionError as e:
            raise ProviderError(
                provider=self.name,
                message=f"Connection error: {e}",
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
        Stream a completion using OpenAI.

        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            String chunks as generated

        Raises:
            ProviderError: If OpenAI API fails
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
                retryable=True,
            )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for an OpenAI request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pricing = OPENAI_PRICING.get(self.model, DEFAULT_PRICING)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost
