"""
Core module for LLM client abstraction and provider implementations.
"""

from unified_ai.core.fallback import (
    AllProvidersFailedError,
    FallbackChain,
    FallbackResult,
    create_provider,
    create_provider_chain,
)
from unified_ai.core.llm_client import (
    CompletionResult,
    LLMClient,
    Message,
    ProviderError,
    ProviderName,
)
from unified_ai.core.products import (
    ProductConfig,
    ProductType,
    get_product_config,
    list_products,
)

__all__ = [
    "AllProvidersFailedError",
    "CompletionResult",
    "FallbackChain",
    "FallbackResult",
    "LLMClient",
    "Message",
    "ProductConfig",
    "ProductType",
    "ProviderError",
    "ProviderName",
    "create_provider",
    "create_provider_chain",
    "get_product_config",
    "list_products",
]
