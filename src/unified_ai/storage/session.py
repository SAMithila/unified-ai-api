"""
Session storage for conversation history.

This module provides both in-memory (development) and Redis (production)
storage backends for maintaining conversation state.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from unified_ai.core.llm_client import Message
from unified_ai.core.products import ProductType


@dataclass
class Session:
    """A conversation session."""

    session_id: str
    product: ProductType
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    @property
    def message_count(self) -> int:
        """Number of messages in session."""
        return len(self.messages)

    def add_message(self, message: Message) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()


class SessionStorage(ABC):
    """Abstract base for session storage."""

    @abstractmethod
    async def get(self, session_id: str, product: ProductType) -> Session | None:
        """Get a session by ID and product."""
        pass

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Save a session."""
        pass

    @abstractmethod
    async def delete(self, session_id: str, product: ProductType) -> bool:
        """Delete a session. Returns True if deleted."""
        pass

    @abstractmethod
    async def list_sessions(
        self, product: ProductType | None = None, limit: int = 100
    ) -> list[Session]:
        """List sessions, optionally filtered by product."""
        pass


class InMemorySessionStorage(SessionStorage):
    """
    In-memory session storage for development.
    
    WARNING: Data is lost when the server restarts.
    Use Redis in production.
    """

    def __init__(self, max_sessions: int = 10000):
        """
        Initialize in-memory storage.
        
        Args:
            max_sessions: Maximum sessions to store (LRU eviction)
        """
        self._sessions: dict[str, Session] = {}
        self._max_sessions = max_sessions

    def _make_key(self, session_id: str, product: ProductType) -> str:
        """Create storage key from session ID and product."""
        return f"{product.value}:{session_id}"

    async def get(self, session_id: str, product: ProductType) -> Session | None:
        """Get a session."""
        key = self._make_key(session_id, product)
        return self._sessions.get(key)

    async def save(self, session: Session) -> None:
        """Save a session."""
        key = self._make_key(session.session_id, session.product)

        # Simple LRU: remove oldest if at capacity
        if key not in self._sessions and len(self._sessions) >= self._max_sessions:
            oldest_key = min(
                self._sessions.keys(),
                key=lambda k: self._sessions[k].updated_at,
            )
            del self._sessions[oldest_key]

        self._sessions[key] = session

    async def delete(self, session_id: str, product: ProductType) -> bool:
        """Delete a session."""
        key = self._make_key(session_id, product)
        if key in self._sessions:
            del self._sessions[key]
            return True
        return False

    async def list_sessions(
        self, product: ProductType | None = None, limit: int = 100
    ) -> list[Session]:
        """List sessions."""
        sessions = list(self._sessions.values())

        if product:
            sessions = [s for s in sessions if s.product == product]

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions[:limit]


# Redis implementation placeholder
class RedisSessionStorage(SessionStorage):
    """
    Redis session storage for production.
    
    Provides persistent, distributed session storage.
    """

    def __init__(self, redis_url: str, ttl_seconds: int = 86400):
        """
        Initialize Redis storage.
        
        Args:
            redis_url: Redis connection URL
            ttl_seconds: Session TTL in seconds (default: 24 hours)
        """
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._client = None  # Lazy initialization

    async def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            import redis.asyncio as redis

            self._client = redis.from_url(self._redis_url)
        return self._client

    def _make_key(self, session_id: str, product: ProductType) -> str:
        """Create Redis key."""
        return f"session:{product.value}:{session_id}"

    async def get(self, session_id: str, product: ProductType) -> Session | None:
        """Get a session from Redis."""
        import json

        client = await self._get_client()
        key = self._make_key(session_id, product)

        data = await client.get(key)
        if not data:
            return None

        # Deserialize
        session_data = json.loads(data)
        return Session(
            session_id=session_data["session_id"],
            product=ProductType(session_data["product"]),
            messages=[Message(**m) for m in session_data["messages"]],
            created_at=datetime.fromisoformat(session_data["created_at"]),
            updated_at=datetime.fromisoformat(session_data["updated_at"]),
            metadata=session_data.get("metadata", {}),
        )

    async def save(self, session: Session) -> None:
        """Save a session to Redis."""
        import json

        client = await self._get_client()
        key = self._make_key(session.session_id, session.product)

        # Serialize
        data = {
            "session_id": session.session_id,
            "product": session.product.value,
            "messages": [m.to_dict() for m in session.messages],
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "metadata": session.metadata,
        }

        await client.setex(key, self._ttl, json.dumps(data))

    async def delete(self, session_id: str, product: ProductType) -> bool:
        """Delete a session from Redis."""
        client = await self._get_client()
        key = self._make_key(session_id, product)
        result = await client.delete(key)
        return result > 0

    async def list_sessions(
        self, product: ProductType | None = None, limit: int = 100
    ) -> list[Session]:
        """List sessions from Redis."""
        client = await self._get_client()

        pattern = f"session:{product.value if product else '*'}:*"
        keys = []

        async for key in client.scan_iter(match=pattern, count=limit):
            keys.append(key)
            if len(keys) >= limit:
                break

        sessions = []
        for key in keys:
            # Extract session_id and product from key
            parts = key.decode().split(":")
            if len(parts) == 3:
                _, prod, sess_id = parts
                session = await self.get(sess_id, ProductType(prod))
                if session:
                    sessions.append(session)

        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]


def create_session_storage(redis_url: str | None = None) -> SessionStorage:
    """
    Create appropriate session storage based on configuration.
    
    Args:
        redis_url: Redis URL (if None, uses in-memory storage)
        
    Returns:
        SessionStorage instance
    """
    if redis_url:
        return RedisSessionStorage(redis_url)
    return InMemorySessionStorage()
