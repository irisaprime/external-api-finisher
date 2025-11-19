"""
Unit tests for AI Service Client

Tests retry logic, error handling, and client lifecycle
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import httpx

from app.services.ai_client import AIServiceClient


@pytest.fixture
def ai_client():
    """Create AI client instance"""
    return AIServiceClient()


class TestAIClientInitialization:
    """Tests for AI client initialization"""

    def test_client_initialization(self, ai_client):
        """Test client is initialized with correct settings"""
        assert ai_client is not None
        assert ai_client.max_retries == 3
        assert ai_client.client is not None


class TestSendChatRequest:
    """Tests for send_chat_request method"""

    @pytest.mark.asyncio
    async def test_send_chat_request_success(self, ai_client):
        """Test successful chat request"""
        mock_response = Mock()
        mock_response.json.return_value = {"Response": "Test response"}
        mock_response.raise_for_status = Mock()

        ai_client.client.post = AsyncMock(return_value=mock_response)

        result = await ai_client.send_chat_request(
            session_id="test_session",
            query="Hello",
            history=[],
            pipeline="google/gemini-2.0-flash-001",
            files=None
        )

        assert result == {"Response": "Test response"}
        ai_client.client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_chat_request_with_history(self, ai_client):
        """Test chat request with conversation history (line 51 coverage)"""
        mock_response = Mock()
        mock_response.json.return_value = {"Response": "Response with history"}
        mock_response.raise_for_status = Mock()

        ai_client.client.post = AsyncMock(return_value=mock_response)

        history = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second message"}
        ]

        result = await ai_client.send_chat_request(
            session_id="test_session",
            query="Third message",
            history=history,
            pipeline="google/gemini-2.0-flash-001"
        )

        assert result == {"Response": "Response with history"}

        # Verify the payload includes formatted history
        call_args = ai_client.client.post.call_args
        payload = call_args.kwargs['json']
        assert len(payload['History']) == 4  # system prompt + 3 history messages

    @pytest.mark.asyncio
    async def test_send_chat_request_timeout_with_retry(self, ai_client):
        """Test timeout exception with retry (lines 89-95 coverage)"""
        mock_response = Mock()
        mock_response.json.return_value = {"Response": "Success after retry"}
        mock_response.raise_for_status = Mock()

        # First call times out, second succeeds
        ai_client.client.post = AsyncMock(
            side_effect=[httpx.TimeoutException("Timeout"), mock_response]
        )

        result = await ai_client.send_chat_request(
            session_id="test_session",
            query="Hello",
            history=[],
            pipeline="google/gemini-2.0-flash-001"
        )

        assert result == {"Response": "Success after retry"}
        assert ai_client.client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_chat_request_http_error_4xx(self, ai_client):
        """Test HTTP 4xx error (no retry) - lines 98-106 coverage"""
        mock_response = Mock()
        mock_response.status_code = 400

        error = httpx.HTTPStatusError(
            "Bad Request",
            request=Mock(),
            response=mock_response
        )

        ai_client.client.post = AsyncMock(side_effect=error)

        with pytest.raises(httpx.HTTPStatusError):
            await ai_client.send_chat_request(
                session_id="test_session",
                query="Bad request",
                history=[],
                pipeline="google/gemini-2.0-flash-001"
            )

        # Should not retry on 4xx errors
        assert ai_client.client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_chat_request_http_error_5xx_with_retry(self, ai_client):
        """Test HTTP 5xx error with retry (lines 98-106 coverage)"""
        mock_response_error = Mock()
        mock_response_error.status_code = 500

        mock_response_success = Mock()
        mock_response_success.json.return_value = {"Response": "Success after 500"}
        mock_response_success.raise_for_status = Mock()

        error = httpx.HTTPStatusError(
            "Server Error",
            request=Mock(),
            response=mock_response_error
        )

        # First call returns 500, second succeeds
        ai_client.client.post = AsyncMock(
            side_effect=[error, mock_response_success]
        )

        result = await ai_client.send_chat_request(
            session_id="test_session",
            query="Hello",
            history=[],
            pipeline="google/gemini-2.0-flash-001"
        )

        assert result == {"Response": "Success after 500"}
        assert ai_client.client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_chat_request_all_retries_failed(self, ai_client):
        """Test all retries failed (lines 118-120 coverage)"""
        # All 3 attempts timeout
        ai_client.client.post = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(Exception) as exc_info:
            await ai_client.send_chat_request(
                session_id="test_session",
                query="Hello",
                history=[],
                pipeline="google/gemini-2.0-flash-001"
            )

        assert "Failed after 3 attempts" in str(exc_info.value)
        assert ai_client.client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_chat_request_with_files(self, ai_client):
        """Test chat request with file attachments"""
        mock_response = Mock()
        mock_response.json.return_value = {"Response": "Response with files"}
        mock_response.raise_for_status = Mock()

        ai_client.client.post = AsyncMock(return_value=mock_response)

        files = [{"name": "test.pdf", "data": "base64data"}]

        result = await ai_client.send_chat_request(
            session_id="test_session",
            query="Analyze this file",
            history=[],
            pipeline="google/gemini-2.0-flash-001",
            files=files
        )

        assert result == {"Response": "Response with files"}

        # Verify files included in payload
        call_args = ai_client.client.post.call_args
        payload = call_args.kwargs['json']
        assert payload['Files'] == files

    @pytest.mark.asyncio
    async def test_send_chat_request_generic_exception_with_retry(self, ai_client):
        """Test generic exception with retry (lines 108-115 coverage)"""
        mock_response = Mock()
        mock_response.json.return_value = {"Response": "Success after generic error"}
        mock_response.raise_for_status = Mock()

        # First call raises generic exception, second succeeds
        ai_client.client.post = AsyncMock(
            side_effect=[Exception("Generic error"), mock_response]
        )

        result = await ai_client.send_chat_request(
            session_id="test_session",
            query="Hello",
            history=[],
            pipeline="google/gemini-2.0-flash-001"
        )

        assert result == {"Response": "Success after generic error"}
        assert ai_client.client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_chat_request_5xx_all_retries_failed(self, ai_client):
        """Test 5xx error on all retries (line 105 branch coverage)"""
        mock_response = Mock()
        mock_response.status_code = 503

        error = httpx.HTTPStatusError(
            "Service Unavailable",
            request=Mock(),
            response=mock_response
        )

        # All 3 attempts fail with 5xx error
        ai_client.client.post = AsyncMock(side_effect=error)

        with pytest.raises(Exception) as exc_info:
            await ai_client.send_chat_request(
                session_id="test_session",
                query="Hello",
                history=[],
                pipeline="google/gemini-2.0-flash-001"
            )

        assert "Failed after 3 attempts" in str(exc_info.value)
        assert ai_client.client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_chat_request_generic_exception_all_retries_failed(self, ai_client):
        """Test generic exception on all retries (line 114 branch coverage)"""
        # All 3 attempts fail with generic exception
        ai_client.client.post = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        with pytest.raises(Exception) as exc_info:
            await ai_client.send_chat_request(
                session_id="test_session",
                query="Hello",
                history=[],
                pipeline="google/gemini-2.0-flash-001"
            )

        assert "Failed after 3 attempts" in str(exc_info.value)
        assert ai_client.client.post.call_count == 3


class TestHealthCheck:
    """Tests for health_check method"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, ai_client):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.status_code = 200

        ai_client.client.get = AsyncMock(return_value=mock_response)

        result = await ai_client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, ai_client):
        """Test health check failure"""
        ai_client.client.get = AsyncMock(side_effect=Exception("Connection error"))

        result = await ai_client.health_check()

        assert result is False


class TestClientLifecycle:
    """Tests for client lifecycle methods"""

    @pytest.mark.asyncio
    async def test_close_client(self, ai_client):
        """Test closing the client (lines 133-134 coverage)"""
        ai_client.client.aclose = AsyncMock()

        await ai_client.close()

        ai_client.client.aclose.assert_called_once()
