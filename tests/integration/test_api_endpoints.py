"""
Integration tests for API endpoints.
"""

import pytest


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "providers" in data
        assert "timestamp" in data

    def test_products_endpoint(self, client):
        """Test products listing endpoint."""
        response = client.get("/products")
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert len(data["products"]) > 0

        # Check product structure
        product = data["products"][0]
        assert "id" in product
        assert "name" in product
        assert "description" in product


class TestCompletionEndpoint:
    """Tests for the main completion endpoint."""

    def test_completion_basic(self, client):
        """Test basic completion request."""
        response = client.post(
            "/api/v1/completion",
            json={
                "product": "chatbot",
                "session_id": "test-session-1",
                "message": "Hello!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["session_id"] == "test-session-1"
        assert data["product"] == "chatbot"

    def test_completion_with_code_reviewer(self, client):
        """Test completion with code reviewer product."""
        response = client.post(
            "/api/v1/completion",
            json={
                "product": "code_reviewer",
                "session_id": "test-code-1",
                "message": "def add(a, b): return a + b",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["product"] == "code_reviewer"

    def test_completion_returns_metrics(self, client):
        """Test that completion returns usage metrics."""
        response = client.post(
            "/api/v1/completion",
            json={
                "product": "chatbot",
                "session_id": "test-metrics",
                "message": "Test message",
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Check metrics are present
        assert "input_tokens" in data
        assert "output_tokens" in data
        assert "latency_ms" in data
        assert "cost_usd" in data
        assert "provider" in data
        assert "model" in data

    def test_completion_invalid_product(self, client):
        """Test completion with invalid product."""
        response = client.post(
            "/api/v1/completion",
            json={
                "product": "invalid_product",
                "session_id": "test-invalid",
                "message": "Hello",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_completion_empty_message(self, client):
        """Test completion with empty message."""
        response = client.post(
            "/api/v1/completion",
            json={
                "product": "chatbot",
                "session_id": "test-empty",
                "message": "",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_session_continuity(self, client):
        """Test that sessions maintain conversation history."""
        session_id = "test-continuity"

        # First message
        response1 = client.post(
            "/api/v1/completion",
            json={
                "product": "chatbot",
                "session_id": session_id,
                "message": "My name is Alice.",
            },
        )
        assert response1.status_code == 200

        # Second message (should have context)
        response2 = client.post(
            "/api/v1/completion",
            json={
                "product": "chatbot",
                "session_id": session_id,
                "message": "What is my name?",
            },
        )
        assert response2.status_code == 200


class TestSessionEndpoints:
    """Tests for session management endpoints."""

    def test_get_session(self, client):
        """Test getting session info."""
        # Create a session first
        client.post(
            "/api/v1/completion",
            json={
                "product": "chatbot",
                "session_id": "test-get-session",
                "message": "Hello",
            },
        )

        # Get session info
        response = client.get("/api/v1/session/chatbot/test-get-session")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-get-session"
        assert data["product"] == "chatbot"
        assert data["message_count"] > 0

    def test_get_nonexistent_session(self, client):
        """Test getting a session that doesn't exist."""
        response = client.get("/api/v1/session/chatbot/nonexistent")
        assert response.status_code == 404

    def test_delete_session(self, client):
        """Test deleting a session."""
        # Create a session
        client.post(
            "/api/v1/completion",
            json={
                "product": "chatbot",
                "session_id": "test-delete",
                "message": "Hello",
            },
        )

        # Delete it
        response = client.delete("/api/v1/session/chatbot/test-delete")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify it's gone
        response = client.get("/api/v1/session/chatbot/test-delete")
        assert response.status_code == 404

    def test_delete_nonexistent_session(self, client):
        """Test deleting a session that doesn't exist."""
        response = client.delete("/api/v1/session/chatbot/nonexistent")
        assert response.status_code == 404
