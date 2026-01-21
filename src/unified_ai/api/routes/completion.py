"""
Main completion endpoint.

This is the core endpoint that powers all AI products.
"""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from unified_ai.api.schemas import CompletionRequest, CompletionResponse, ErrorResponse
from unified_ai.core.fallback import AllProvidersFailedError, FallbackChain
from unified_ai.core.llm_client import Message
from unified_ai.core.products import ProductType, get_product_config
from unified_ai.storage.session import Session, SessionStorage

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["completion"])


async def get_fallback_chain(request: Request) -> FallbackChain:
    """Get the fallback chain from app state."""
    return request.app.state.fallback_chain


async def get_session_storage(request: Request) -> SessionStorage:
    """Get session storage from app state."""
    return request.app.state.session_storage


@router.post(
    "/completion",
    response_model=CompletionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        503: {"model": ErrorResponse, "description": "All providers unavailable"},
    },
    summary="Generate AI completion",
    description="""
    Generate a completion using the specified AI product.

    The completion endpoint is the core of the Unified AI API. It:
    - Routes to the appropriate product configuration
    - Maintains conversation history via sessions
    - Falls back through providers on failure
    - Tracks usage and costs

    **Products Available:**
    - `chatbot`: General-purpose assistant
    - `writing_helper`: Grammar, clarity, and style suggestions
    - `code_reviewer`: Professional code review
    - `support_bot`: Customer support agent
    - `content_summarizer`: Content summarization
    """,
)
async def create_completion(
    request: CompletionRequest,
    fallback_chain: Annotated[FallbackChain, Depends(get_fallback_chain)],
    session_storage: Annotated[SessionStorage, Depends(get_session_storage)],
) -> CompletionResponse:
    """
    Generate a completion for the given product and message.

    This endpoint:
    1. Retrieves or creates the conversation session
    2. Adds the system prompt and user message
    3. Calls the LLM provider (with fallback)
    4. Saves the response to the session
    5. Returns the response with metrics
    """
    request_id = str(uuid.uuid4())[:8]

    logger.info(
        "Completion request",
        request_id=request_id,
        product=request.product.value,
        session_id=request.session_id,
        message_length=len(request.message),
    )

    # Get product configuration
    product_config = get_product_config(request.product)

    # Get or create session
    session = await session_storage.get(request.session_id, request.product)

    if session is None:
        # Create new session with system prompt
        session = Session(
            session_id=request.session_id,
            product=request.product,
            messages=[Message(role="system", content=product_config.system_prompt)],
        )

    # Add user message
    session.add_message(Message(role="user", content=request.message))

    # Determine parameters (request overrides > product defaults)
    max_tokens = request.max_tokens or product_config.max_tokens
    temperature = (
        request.temperature
        if request.temperature is not None
        else product_config.temperature
    )

    try:
        # Generate completion
        fallback_result = await fallback_chain.complete(
            messages=session.messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        result = fallback_result.result

        # Add assistant response to session
        session.add_message(Message(role="assistant", content=result.content))

        # Save updated session
        await session_storage.save(session)

        logger.info(
            "Completion successful",
            request_id=request_id,
            provider=result.provider.value,
            latency_ms=result.latency_ms,
            tokens=result.total_tokens,
            fallback_used=fallback_result.fallback_used,
        )

        return CompletionResponse(
            response=result.content,
            session_id=request.session_id,
            product=request.product.value,
            provider=result.provider.value,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
            fallback_used=fallback_result.fallback_used,
        )

    except AllProvidersFailedError as e:
        logger.error(
            "All providers failed",
            request_id=request_id,
            attempts=len(e.attempts),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "All providers unavailable",
                "detail": str(e),
                "request_id": request_id,
            },
        )


@router.delete(
    "/session/{product}/{session_id}",
    summary="Delete a session",
    description="Delete a conversation session and all its history.",
)
async def delete_session(
    product: ProductType,
    session_id: str,
    session_storage: Annotated[SessionStorage, Depends(get_session_storage)],
) -> dict:
    """Delete a session."""
    deleted = await session_storage.delete(session_id, product)

    if deleted:
        logger.info("Session deleted", product=product.value, session_id=session_id)
        return {"status": "deleted", "session_id": session_id, "product": product.value}

    raise HTTPException(
        status_code=404,
        detail={"error": "Session not found", "session_id": session_id},
    )


@router.get(
    "/session/{product}/{session_id}",
    summary="Get session info",
    description="Get information about a session including message count.",
)
async def get_session(
    product: ProductType,
    session_id: str,
    session_storage: Annotated[SessionStorage, Depends(get_session_storage)],
) -> dict:
    """Get session information."""
    session = await session_storage.get(session_id, product)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Session not found", "session_id": session_id},
        )

    return {
        "session_id": session.session_id,
        "product": session.product.value,
        "message_count": session.message_count,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }
