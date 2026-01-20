"""
Google Gemini LLM provider implementation.

Gemini is Google's multimodal AI model, offering good performance
at competitive pricing.
"""

import time
from typing import AsyncIterator

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from unified_ai.core.llm_client import (
    CompletionResult,
    LLMClient,
    Message,
    ProviderError,
    ProviderName,
)


# Gemini pricing per 1M tokens (as of Jan 2025)
# https://ai.google.dev/pricing
GEMINI_PRICING = {
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.0-flash-exp": {"input": 0.00, "output": 0.00},  # Free during preview
}

DEFAULT_PRICING = {"input": 0.50, "output": 1.50}


class GeminiClient(LLMClient):
    """
    Google Gemini LLM provider.
    
    Gemini offers multimodal capabilities and competitive pricing.
    The flash models are particularly cost-effective.
    
    Example:
        >>> client = GeminiClient(api_key="...", model="gemini-1.5-flash")
        >>> result = await client.complete([Message(role="user", content="Hello")])
        >>> print(result.content)
    """

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Google API key
            model: Model to use (default: gemini-1.5-flash)
        """
        super().__init__(api_key, model)
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)

    @property
    def name(self) -> ProviderName:
        """Get provider name."""
        return ProviderName.GEMINI

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
        """
        Convert messages to Gemini format.
        
        Gemini uses a different format: system instruction is separate,
        and messages use "user" and "model" roles.
        
        Args:
            messages: Standard messages
            
        Returns:
            Tuple of (system_instruction, history)
        """
        system_instruction = None
        history = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                history.append({"role": "user", "parts": [msg.content]})
            elif msg.role == "assistant":
                history.append({"role": "model", "parts": [msg.content]})

        return system_instruction, history

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> CompletionResult:
        """
        Generate a completion using Gemini.
        
        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            CompletionResult with generated content
            
        Raises:
            ProviderError: If Gemini API fails
        """
        start_time = time.perf_counter()

        try:
            system_instruction, history = self._convert_messages(messages)

            # Create model with system instruction if provided
            model = (
                genai.GenerativeModel(
                    self.model, system_instruction=system_instruction
                )
                if system_instruction
                else self._model
            )

            # Configure generation
            generation_config = genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            # Get the last user message
            if not history:
                raise ProviderError(
                    provider=self.name,
                    message="No user message provided",
                    retryable=False,
                )

            # Start chat with history (except last message)
            chat = model.start_chat(history=history[:-1] if len(history) > 1 else [])

            # Send the last message
            last_message = history[-1]["parts"][0]
            response = await chat.send_message_async(
                last_message, generation_config=generation_config
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract token counts from usage metadata
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata"):
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
                output_tokens = getattr(
                    response.usage_metadata, "candidates_token_count", 0
                )

            cost = self.estimate_cost(input_tokens, output_tokens)

            return CompletionResult(
                content=response.text,
                provider=self.name,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=cost,
            )

        except google_exceptions.ResourceExhausted as e:
            raise ProviderError(
                provider=self.name,
                message=f"Rate limit exceeded: {e}",
                status_code=429,
                retryable=True,
            )
        except google_exceptions.InvalidArgument as e:
            raise ProviderError(
                provider=self.name,
                message=f"Invalid request: {e}",
                status_code=400,
                retryable=False,
            )
        except google_exceptions.GoogleAPIError as e:
            raise ProviderError(
                provider=self.name,
                message=str(e),
                retryable=True,
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
        Stream a completion using Gemini.
        
        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Yields:
            String chunks as generated
            
        Raises:
            ProviderError: If Gemini API fails
        """
        try:
            system_instruction, history = self._convert_messages(messages)

            model = (
                genai.GenerativeModel(
                    self.model, system_instruction=system_instruction
                )
                if system_instruction
                else self._model
            )

            generation_config = genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            if not history:
                raise ProviderError(
                    provider=self.name,
                    message="No user message provided",
                    retryable=False,
                )

            chat = model.start_chat(history=history[:-1] if len(history) > 1 else [])
            last_message = history[-1]["parts"][0]

            response = await chat.send_message_async(
                last_message,
                generation_config=generation_config,
                stream=True,
            )

            async for chunk in response:
                if chunk.text:
                    yield chunk.text

        except google_exceptions.ResourceExhausted as e:
            raise ProviderError(
                provider=self.name,
                message=f"Rate limit exceeded: {e}",
                status_code=429,
                retryable=True,
            )
        except google_exceptions.GoogleAPIError as e:
            raise ProviderError(
                provider=self.name,
                message=str(e),
                retryable=True,
            )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for a Gemini request.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost in USD
        """
        pricing = GEMINI_PRICING.get(self.model, DEFAULT_PRICING)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost
