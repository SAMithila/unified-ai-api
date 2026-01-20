"""
API request and response schemas using Pydantic.

These models define the contract for the API, providing automatic
validation and documentation.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from unified_ai.core.products import ProductType


# =============================================================================
# Request Models
# =============================================================================


class CompletionRequest(BaseModel):
    """Request for the unified completion endpoint."""

    product: ProductType = Field(
        description="Which AI product to use for this request"
    )
    session_id: str = Field(
        description="Session ID for conversation continuity",
        min_length=1,
        max_length=128,
        examples=["user-123", "chat-abc-456"],
    )
    message: str = Field(
        description="User message to send",
        min_length=1,
        max_length=100000,  # ~25k tokens max
    )
    max_tokens: int | None = Field(
        default=None,
        description="Override default max tokens for this product",
        ge=1,
        le=4000,
    )
    temperature: float | None = Field(
        default=None,
        description="Override default temperature for this product",
        ge=0.0,
        le=2.0,
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "product": "chatbot",
                    "session_id": "user-123",
                    "message": "Hello! How are you today?",
                },
                {
                    "product": "code_reviewer",
                    "session_id": "pr-456",
                    "message": "def add(a, b): return a + b",
                    "temperature": 0.2,
                },
            ]
        }
    }


class SessionDeleteRequest(BaseModel):
    """Request to delete a session."""

    product: ProductType
    session_id: str


# =============================================================================
# Response Models
# =============================================================================


class CompletionResponse(BaseModel):
    """Response from the completion endpoint."""

    response: str = Field(description="Generated response")
    session_id: str = Field(description="Session ID used")
    product: str = Field(description="Product used")
    provider: str = Field(description="LLM provider that generated the response")
    model: str = Field(description="Model used")

    # Metrics (for observability)
    input_tokens: int = Field(description="Number of input tokens")
    output_tokens: int = Field(description="Number of output tokens")
    latency_ms: float = Field(description="Response latency in milliseconds")
    cost_usd: float = Field(description="Estimated cost in USD")

    # Fallback info
    fallback_used: bool = Field(
        default=False,
        description="Whether fallback provider was used",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "Hello! I'm doing great, thanks for asking!",
                "session_id": "user-123",
                "product": "chatbot",
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "input_tokens": 45,
                "output_tokens": 12,
                "latency_ms": 234.5,
                "cost_usd": 0.000034,
                "fallback_used": False,
            }
        }
    }


class SessionResponse(BaseModel):
    """Response containing session info."""

    session_id: str
    product: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    """Response from health check endpoint."""

    status: str = Field(description="Overall health status")
    version: str = Field(description="API version")
    providers: dict[str, bool] = Field(
        description="Health status of each LLM provider"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProductInfo(BaseModel):
    """Information about an available product."""

    id: str
    name: str
    description: str
    version: str


class ProductListResponse(BaseModel):
    """List of available products."""

    products: list[ProductInfo]


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(description="Error message")
    detail: str | None = Field(default=None, description="Detailed error info")
    request_id: str | None = Field(default=None, description="Request ID for tracking")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "Rate limit exceeded",
                "detail": "Please retry after 60 seconds",
                "request_id": "req-abc-123",
            }
        }
    }


class UsageStats(BaseModel):
    """Usage statistics."""

    total_requests: int
    total_tokens: int
    total_cost_usd: float
    requests_by_product: dict[str, int]
    requests_by_provider: dict[str, int]
    period_start: datetime
    period_end: datetime
