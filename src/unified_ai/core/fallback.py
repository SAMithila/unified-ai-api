"""
Provider factory and fallback chain.

This module creates LLM clients from configuration and implements
the fallback chain for high availability.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import structlog

from unified_ai.config import Settings
from unified_ai.core.llm_client import (
    CompletionResult,
    LLMClient,
    Message,
    ProviderError,
    ProviderName,
)
from unified_ai.core.providers.gemini import GeminiClient
from unified_ai.core.providers.groq import GroqClient
from unified_ai.core.providers.openai import OpenAIClient

logger = structlog.get_logger()


@dataclass
class FallbackAttempt:
    """Record of a fallback attempt."""

    provider: ProviderName
    success: bool
    error: str | None = None
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FallbackResult:
    """Result from the fallback chain."""

    result: CompletionResult
    attempts: list[FallbackAttempt]

    @property
    def fallback_used(self) -> bool:
        """Whether fallback was needed."""
        return len(self.attempts) > 1


class AllProvidersFailedError(Exception):
    """Raised when all providers in the fallback chain fail."""

    def __init__(self, attempts: list[FallbackAttempt]):
        self.attempts = attempts
        errors = [f"{a.provider.value}: {a.error}" for a in attempts if a.error]
        super().__init__(f"All providers failed: {'; '.join(errors)}")


def create_provider(provider_name: str, settings: Settings) -> LLMClient | None:
    """
    Create an LLM client for the given provider.
    
    Args:
        provider_name: Name of the provider (groq, gemini, openai, anthropic)
        settings: Application settings
        
    Returns:
        LLMClient instance or None if API key not configured
    """
    provider_name = provider_name.lower()

    if provider_name == "groq" and settings.groq_api_key:
        return GroqClient(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
    elif provider_name == "gemini" and settings.google_api_key:
        return GeminiClient(
            api_key=settings.google_api_key,
            model=settings.gemini_model,
        )
    elif provider_name == "openai" and settings.openai_api_key:
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    # TODO: Add Anthropic provider
    # elif provider_name == "anthropic" and settings.anthropic_api_key:
    #     return AnthropicClient(...)

    return None


def create_provider_chain(settings: Settings) -> list[LLMClient]:
    """
    Create a list of LLM clients in fallback order.
    
    Args:
        settings: Application settings
        
    Returns:
        List of LLMClient instances in fallback order
    """
    providers = []

    for provider_name in settings.provider_order:
        client = create_provider(provider_name, settings)
        if client:
            providers.append(client)
            logger.info(
                "Provider configured",
                provider=provider_name,
                model=client.model,
            )
        else:
            logger.debug(
                "Provider skipped (no API key)",
                provider=provider_name,
            )

    if not providers:
        logger.warning("No LLM providers configured!")

    return providers


class FallbackChain:
    """
    Fallback chain for LLM providers.
    
    Tries providers in order until one succeeds. Tracks attempts
    for observability and debugging.
    
    Example:
        >>> chain = FallbackChain(providers=[groq_client, gemini_client])
        >>> result = await chain.complete(messages)
        >>> print(f"Used: {result.result.provider}")
        >>> if result.fallback_used:
        ...     print("Fallback was needed!")
    """

    def __init__(
        self,
        providers: list[LLMClient],
        on_fallback: Callable[[FallbackAttempt], None] | None = None,
    ):
        """
        Initialize fallback chain.
        
        Args:
            providers: List of LLM clients in fallback order
            on_fallback: Optional callback when fallback occurs
        """
        self.providers = providers
        self.on_fallback = on_fallback

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> FallbackResult:
        """
        Generate completion, falling back through providers on failure.
        
        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            FallbackResult with completion and attempt history
            
        Raises:
            AllProvidersFailedError: If all providers fail
        """
        attempts: list[FallbackAttempt] = []

        for provider in self.providers:
            start_time = time.perf_counter()

            try:
                result = await provider.complete(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                latency_ms = (time.perf_counter() - start_time) * 1000

                attempt = FallbackAttempt(
                    provider=provider.name,
                    success=True,
                    latency_ms=latency_ms,
                )
                attempts.append(attempt)

                if len(attempts) > 1:
                    logger.info(
                        "Fallback succeeded",
                        provider=provider.name.value,
                        attempts=len(attempts),
                    )

                return FallbackResult(result=result, attempts=attempts)

            except ProviderError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000

                attempt = FallbackAttempt(
                    provider=provider.name,
                    success=False,
                    error=str(e),
                    latency_ms=latency_ms,
                )
                attempts.append(attempt)

                logger.warning(
                    "Provider failed, trying next",
                    provider=provider.name.value,
                    error=str(e),
                    retryable=e.retryable,
                )

                if self.on_fallback:
                    self.on_fallback(attempt)

                # If not retryable and no more providers, fail fast
                if not e.retryable and provider == self.providers[-1]:
                    raise AllProvidersFailedError(attempts)

        raise AllProvidersFailedError(attempts)

    async def health_check(self) -> dict[str, bool]:
        """
        Check health of all providers.
        
        Returns:
            Dict mapping provider name to health status
        """
        results = {}

        async def check_provider(provider: LLMClient) -> tuple[str, bool]:
            try:
                healthy = await asyncio.wait_for(
                    provider.health_check(),
                    timeout=10.0,
                )
                return provider.name.value, healthy
            except asyncio.TimeoutError:
                return provider.name.value, False

        checks = await asyncio.gather(
            *[check_provider(p) for p in self.providers],
            return_exceptions=True,
        )

        for result in checks:
            if isinstance(result, Exception):
                continue
            name, healthy = result
            results[name] = healthy

        return results
