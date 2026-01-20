"""
Unified AI API - Main Application Entry Point.

This module creates and configures the FastAPI application.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from unified_ai.api.routes import completion, health
from unified_ai.config import get_settings
from unified_ai.core.fallback import FallbackChain, create_provider_chain
from unified_ai.storage.session import create_session_storage

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
        if get_settings().log_format == "console"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Sets up and tears down application state:
    - Creates LLM provider chain
    - Creates session storage
    - Logs startup/shutdown
    """
    settings = get_settings()

    logger.info(
        "Starting Unified AI API",
        version=settings.api_version,
        debug=settings.api_debug,
    )

    # Create provider chain
    providers = create_provider_chain(settings)
    app.state.fallback_chain = FallbackChain(providers)

    logger.info(
        "Provider chain initialized",
        providers=[p.name.value for p in providers],
    )

    # Create session storage
    app.state.session_storage = create_session_storage(settings.redis_url)

    storage_type = "redis" if settings.redis_url else "in-memory"
    logger.info("Session storage initialized", type=storage_type)

    yield  # Application runs here

    # Cleanup
    logger.info("Shutting down Unified AI API")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        description="""
# Unified AI API

A unified API gateway for multiple AI-powered products.

## Features

- **Multiple Products**: Chatbot, Writing Helper, Code Reviewer, Support Bot, Content Summarizer
- **Provider Fallback**: Automatic failover between Groq, Gemini, OpenAI, and Anthropic
- **Session Management**: Conversation history with in-memory or Redis storage
- **Cost Tracking**: Real-time cost estimation for each request
- **Observability**: Structured logging and metrics

## Quick Start

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/completion",
    headers={"X-API-Key": "your-api-key"},
    json={
        "product": "chatbot",
        "session_id": "my-session",
        "message": "Hello!"
    }
)
print(response.json()["response"])
```

## Products

| Product | Description |
|---------|-------------|
| `chatbot` | General-purpose assistant |
| `writing_helper` | Grammar and style suggestions |
| `code_reviewer` | Professional code review |
| `support_bot` | Customer support agent |
| `content_summarizer` | Content summarization |
        """,
        version=settings.api_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router)
    app.include_router(completion.router)

    # Serve frontend
    frontend_path = Path(__file__).parent.parent.parent.parent / "frontend"
    if frontend_path.exists():

        @app.get("/demo", include_in_schema=False)
        async def serve_demo():
            return FileResponse(frontend_path / "index.html")

    return app


# Create the application instance
app = create_app()


def run() -> None:
    """Run the application with uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "unified_ai.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
    )


if __name__ == "__main__":
    run()
