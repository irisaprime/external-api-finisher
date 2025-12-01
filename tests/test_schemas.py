"""
Tests for Pydantic schemas
"""

from app.models.schemas import BotResponse, IncomingMessage


class TestIncomingMessage:
    """Tests for IncomingMessage schema"""

    def test_incoming_message_basic(self):
        """Test creating basic incoming message"""
        message = IncomingMessage(
            user_id="user123",
            text="Hello, world!"
        )
        assert message.user_id == "user123"
        assert message.text == "Hello, world!"

    def test_incoming_message_with_user_id_formats(self):
        """Test creating message with different user ID formats"""
        # Telegram user ID
        message = IncomingMessage(
            user_id="telegram_456",
            text="Hello"
        )
        assert message.user_id == "telegram_456"

        # Email as user ID
        message = IncomingMessage(
            user_id="user@example.com",
            text="Hello"
        )
        assert message.user_id == "user@example.com"


class TestBotResponse:
    """Tests for BotResponse schema"""

    def test_bot_response_success(self):
        """Test successful bot response"""
        response = BotResponse(
            success=True,
            response="AI response here"
        )
        assert response.success is True
        assert response.response == "AI response here"
        assert response.error is None

    def test_bot_response_error(self):
        """Test error bot response"""
        response = BotResponse(
            success=False,
            error="rate_limit",
            response="Rate limit exceeded"
        )
        assert response.success is False
        assert response.error == "rate_limit"
        assert response.response == "Rate limit exceeded"

    def test_bot_response_with_metadata(self):
        """Test bot response with metadata fields"""
        response = BotResponse(
            success=True,
            response="Response text",
            model="gpt-4",
            total_message_count=5
        )
        assert response.model == "gpt-4"
        assert response.total_message_count == 5
        assert response.success is True
