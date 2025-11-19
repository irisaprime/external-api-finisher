"""
Tests for Pydantic schemas
"""

import pytest
from pydantic import ValidationError

from app.core.constants import MessageType
from app.models.schemas import BotResponse, IncomingMessage, MessageAttachment


class TestMessageAttachment:
    """Tests for MessageAttachment schema"""

    def test_attachment_valid_base64(self):
        """Test attachment with valid base64 data"""
        attachment = MessageAttachment(
            type=MessageType.IMAGE,
            data="SGVsbG8gV29ybGQ=",  # Valid base64
            mime_type="image/png"
        )
        assert attachment.data == "SGVsbG8gV29ybGQ="

    def test_attachment_invalid_base64(self):
        """Test attachment with invalid base64 data raises error"""
        with pytest.raises(ValidationError) as exc_info:
            MessageAttachment(
                type=MessageType.IMAGE,
                data="Invalid@#$%Base64!!!",  # Invalid base64
                mime_type="image/png"
            )
        assert "Invalid base64 data" in str(exc_info.value)

    def test_attachment_none_data(self):
        """Test attachment with None data (allowed)"""
        attachment = MessageAttachment(
            type=MessageType.IMAGE,
            data=None,
            mime_type="image/png"
        )
        assert attachment.data is None


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
