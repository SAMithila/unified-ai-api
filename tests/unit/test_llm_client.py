"""
Unit tests for LLM client abstraction.
"""

from unified_ai.core.llm_client import Message, ProviderName


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        msg = Message(role="assistant", content="Hi there!")
        result = msg.to_dict()
        assert result == {"role": "assistant", "content": "Hi there!"}

    def test_system_message(self):
        """Test system message."""
        msg = Message(role="system", content="You are helpful.")
        assert msg.to_dict()["role"] == "system"


class TestProviderName:
    """Tests for ProviderName enum."""

    def test_provider_values(self):
        """Test provider enum values."""
        assert ProviderName.GROQ.value == "groq"
        assert ProviderName.GEMINI.value == "gemini"
        assert ProviderName.OPENAI.value == "openai"
        assert ProviderName.ANTHROPIC.value == "anthropic"

    def test_provider_is_string(self):
        """Test providers can be used as strings."""
        assert str(ProviderName.GROQ) == "ProviderName.GROQ"
        assert ProviderName.GROQ.value == "groq"
