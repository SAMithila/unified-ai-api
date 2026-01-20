"""
Health check endpoints.

Provides health status for the API and its dependencies.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from unified_ai.api.schemas import HealthResponse, ProductInfo, ProductListResponse
from unified_ai.config import Settings, get_settings
from unified_ai.core.fallback import FallbackChain
from unified_ai.core.products import list_products

router = APIRouter(tags=["health"])


async def get_fallback_chain(request: Request) -> FallbackChain:
    """Get the fallback chain from app state."""
    return request.app.state.fallback_chain


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health of the API and its LLM providers.",
)
async def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
    fallback_chain: Annotated[FallbackChain, Depends(get_fallback_chain)],
) -> HealthResponse:
    """
    Check API health.
    
    Returns the health status of the API and each configured LLM provider.
    """
    # Check provider health
    provider_health = await fallback_chain.health_check()

    # Overall status
    any_healthy = any(provider_health.values()) if provider_health else False
    status = "healthy" if any_healthy else "degraded"

    return HealthResponse(
        status=status,
        version=settings.api_version,
        providers=provider_health,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/",
    summary="Root endpoint",
    description="Basic info about the API.",
)
async def root(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Root endpoint with basic API info."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health",
    }


@router.get(
    "/products",
    response_model=ProductListResponse,
    summary="List products",
    description="List all available AI products.",
)
async def get_products() -> ProductListResponse:
    """List all available products."""
    products = [ProductInfo(**p) for p in list_products()]
    return ProductListResponse(products=products)
