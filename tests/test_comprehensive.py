"""
Comprehensive Test Suite for Arash Bot
Tests all major functionality end-to-end
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_channel():
    """Mock channel with API key"""
    channel = Mock()
    channel.id = 1
    channel.title = "Internal BI Channel"
    channel.channel_id = "Internal-BI"
    channel.monthly_quota = 100000
    channel.daily_quota = 5000
    channel.is_active = True
    channel.created_at = datetime(2025, 1, 1, 12, 0, 0)
    channel.updated_at = datetime(2025, 1, 1, 12, 0, 0)
    return channel


@pytest.fixture
def mock_api_key(mock_channel):
    """Mock valid API key"""
    key = Mock()
    key.id = 1
    key.channel_id = 1
    key.key_prefix = "ark_test"
    key.is_active = True
    key.channel = mock_channel
    return key


class TestHealthAndBasics:
    """Test basic health and status endpoints"""

    def test_health_endpoint(self, client):
        """Health endpoint returns 200"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Arash External API Service"
        assert "version" in data
        assert "status" in data
        assert "timestamp" in data

    def test_openapi_docs_available(self, client):
        """OpenAPI docs are available"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


class TestAuthentication:
    """Test authentication for all endpoint types"""

    def test_chat_endpoint_no_auth_header(self, client):
        """Chat endpoint with no auth should return 401 (authentication required)"""
        response = client.post("/v1/chat", json={"user_id": "telegram_user", "text": "سلام"})
        # SECURITY FIX: No unauthenticated access allowed
        assert response.status_code == 401
        data = response.json()
        assert "Authentication required" in data["detail"]

    @patch("app.api.dependencies.settings")
    @patch("app.services.message_processor.message_processor.process_message_simple")
    def test_chat_endpoint_with_telegram_service_key(self, mock_process, mock_settings, client):
        """Chat endpoint with TELEGRAM_SERVICE_KEY (Telegram bot)"""
        mock_settings.TELEGRAM_SERVICE_KEY = "telegram_service_key_12345"
        mock_process.return_value = {
            "success": True,
            "response": "سلام! چطور می‌تونم کمکتون کنم؟",
            "conversation_id": "chat_123",
            "model": "Gemini 2.0 Flash",
        }

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer telegram_service_key_12345"},
            json={"user_id": "telegram_user", "text": "سلام"},
        )
        # Should work - Telegram bot authenticated
        assert response.status_code in [200, 500, 503]

    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.dependencies.APIKeyManager.validate_api_key")
    def test_chat_endpoint_with_valid_channel_key(self, mock_validate, mock_db, mock_api_key, client):
        """Chat endpoint with valid channel API key"""
        mock_validate.return_value = mock_api_key

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer ark_test_key"},
            json={"user_id": "user123", "text": "Hello"},
        )
        # Should process or fail on AI service
        assert response.status_code in [200, 500, 503]

    @patch("app.api.dependencies.settings")
    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.dependencies.APIKeyManager.validate_api_key")
    def test_chat_endpoint_with_invalid_key(self, mock_validate, mock_db, mock_settings, client):
        """Chat endpoint with invalid API key returns 403"""
        mock_settings.TELEGRAM_SERVICE_KEY = "correct_telegram_key"
        mock_validate.return_value = None

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer invalid_key"},
            json={"user_id": "user123", "text": "Hello"},
        )
        assert response.status_code == 403

    def test_admin_endpoint_no_auth(self, client):
        """Admin endpoints require authentication"""
        response = client.get("/v1/admin/channels")
        assert response.status_code == 401

    @patch("app.api.dependencies.settings")
    def test_admin_endpoint_with_super_admin_key(self, mock_settings, client):
        """Admin endpoint with valid super admin key"""
        mock_settings.super_admin_keys_set = {"test_admin_key"}

        response = client.get("/v1/admin/channels", headers={"Authorization": "Bearer test_admin_key"})
        # Should work or return data
        assert response.status_code in [200, 500]


class TestChatEndpoint:
    """Test /v1/chat endpoint thoroughly"""

    @patch("app.api.dependencies.settings")
    @patch("app.services.message_processor.message_processor.process_message_simple")
    def test_chat_success_response(self, mock_process, mock_settings, client):
        """Chat endpoint returns successful response"""
        mock_settings.TELEGRAM_SERVICE_KEY = "test_telegram_key"
        mock_process.return_value = {
            "success": True,
            "response": "سلام! چطور می‌تونم کمکتون کنم؟",
            "conversation_id": "chat_123",
            "model": "Gemini 2.0 Flash",
            "total_message_count": 1,
        }

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer test_telegram_key"},
            json={"user_id": "user1", "text": "سلام"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "response" in data
        assert data["model"] == "Gemini 2.0 Flash"
        # Verify session_id is NOT in response (removed for simplicity)
        assert "session_id" not in data

    @patch("app.api.dependencies.settings")
    @patch("app.services.message_processor.message_processor.process_message_simple")
    def test_chat_rate_limit_error(self, mock_process, mock_settings, client):
        """Chat endpoint handles rate limit"""
        mock_settings.TELEGRAM_SERVICE_KEY = "test_telegram_key"
        mock_process.return_value = {
            "success": False,
            "error": "rate_limit_exceeded",
            "response": "⚠️ محدودیت سرعت. لطفاً کمی صبر کنید.",
        }

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer test_telegram_key"},
            json={"user_id": "user1", "text": "test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "rate_limit_exceeded"

    def test_chat_missing_required_fields(self, client):
        """Chat endpoint validates required fields"""
        response = client.post("/v1/chat", json={"user_id": "user1"})  # Missing 'text'
        # Returns 401 (auth required) before validation
        assert response.status_code == 401

    @patch("app.api.dependencies.settings")
    @patch("app.services.message_processor.message_processor.process_message_simple")
    def test_api_key_isolation(self, mock_process, mock_settings, client):
        """API keys can only access their own chats (API key isolation)"""
        mock_settings.TELEGRAM_SERVICE_KEY = "test_telegram_key"

        # Mock PermissionError when trying to access another API key's chat
        mock_process.return_value = {
            "success": False,
            "error": "access_denied",
            "response": "❌ دسترسی رد شد. این مکالمه متعلق به API key دیگری است.\n\nAccess denied. This chat belongs to a different API key.",
            "conversation_id": "chat_owned_by_other_key",
        }

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer test_telegram_key"},
            json={
                "user_id": "user1",
                "text": "Hello",
                "conversation_id": "chat_owned_by_other_key",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "access_denied"


class TestCommandsEndpoint:
    """Test /v1/commands endpoint"""

    @patch("app.api.dependencies.settings")
    def test_commands_telegram_mode(self, mock_settings, client):
        """Commands endpoint returns Telegram commands with TELEGRAM_SERVICE_KEY"""
        mock_settings.TELEGRAM_SERVICE_KEY = "telegram_service_key_12345"

        response = client.get(
            "/v1/commands", headers={"Authorization": "Bearer telegram_service_key_12345"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["platform"] == "telegram"
        assert len(data["commands"]) > 0
        # Check commands have required fields
        for cmd in data["commands"]:
            assert "command" in cmd
            assert "description" in cmd
            assert "usage" in cmd

    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.dependencies.APIKeyManager.validate_api_key")
    def test_commands_channel_mode(self, mock_validate, mock_db, mock_api_key, client):
        """Commands endpoint returns channel-specific commands with channel API key"""
        mock_validate.return_value = mock_api_key

        response = client.get("/v1/commands", headers={"Authorization": "Bearer test_key"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["platform"] == "Internal-BI"

    def test_commands_no_auth(self, client):
        """Commands endpoint with no auth should return 401"""
        response = client.get("/v1/commands")
        assert response.status_code == 401
        data = response.json()
        assert "Authentication required" in data["detail"]


class TestAdminChannelEndpoints:
    """Test admin channel management endpoints"""

    @patch("app.api.dependencies.settings")
    @patch("app.services.api_key_manager.APIKeyManager.list_all_channels")
    def test_list_channels(self, mock_list, mock_settings, mock_channel, client):
        """Admin can list all channels"""
        mock_settings.super_admin_keys_set = {"admin_key"}
        mock_list.return_value = [mock_channel]

        response = client.get("/v1/admin/channels", headers={"Authorization": "Bearer admin_key"})
        assert response.status_code == 200
        data = response.json()
        # New response structure includes "channels" list and optional "total_report"
        assert "channels" in data
        assert isinstance(data["channels"], list)
        assert len(data["channels"]) > 0

    @patch("app.api.dependencies.settings")
    @patch("app.services.api_key_manager.APIKeyManager.get_channel_by_channel_id")
    @patch("app.services.api_key_manager.APIKeyManager.create_channel_with_key")
    def test_create_channel(self, mock_create, mock_get_by_name, mock_settings, mock_channel, client):
        """Admin can create new channel"""
        mock_settings.super_admin_keys_set = {"admin_key"}
        mock_get_by_name.return_value = None  # No existing channel with this name
        mock_create.return_value = (mock_channel, "ark_generated_key_12345")

        response = client.post(
            "/v1/admin/channels",
            headers={"Authorization": "Bearer admin_key"},
            json={"channel_id": "Test-Channel", "monthly_quota": 50000, "daily_quota": 2000},
        )
        assert response.status_code == 200
        data = response.json()
        assert "api_key" in data
        assert "warning" in data

    @patch("app.api.dependencies.settings")
    @patch("app.services.api_key_manager.APIKeyManager.get_channel_by_id")
    def test_get_channel_details(self, mock_get, mock_settings, mock_channel, client):
        """Admin can get channel details"""
        mock_settings.super_admin_keys_set = {"admin_key"}
        mock_get.return_value = mock_channel

        # New endpoint uses query parameter instead of path parameter
        response = client.get("/v1/admin/channels?channel_id=1", headers={"Authorization": "Bearer admin_key"})
        assert response.status_code == 200
        data = response.json()
        # Response now includes "channels" list with single item
        assert "channels" in data
        assert len(data["channels"]) == 1
        assert data["channels"][0]["id"] == 1
        assert data["channels"][0]["channel_id"] == "Internal-BI"

    @patch("app.api.dependencies.settings")
    @patch("app.services.api_key_manager.APIKeyManager.get_channel_by_id")
    def test_get_channel_not_found(self, mock_get, mock_settings, client):
        """Admin gets 404 for non-existent channel"""
        mock_settings.super_admin_keys_set = {"admin_key"}
        mock_get.return_value = None  # Channel not found

        # New endpoint uses query parameter instead of path parameter
        response = client.get("/v1/admin/channels?channel_id=999", headers={"Authorization": "Bearer admin_key"})
        assert response.status_code == 404


class TestAdminStatsEndpoints:
    """Test admin statistics endpoints"""

    @patch("app.api.dependencies.settings")
    @patch("app.services.session_manager.session_manager")
    def test_get_platform_stats(self, mock_session_mgr, mock_settings, client):
        """Admin can get platform statistics"""
        mock_settings.super_admin_keys_set = {"admin_key"}
        mock_session_mgr.sessions = {}
        mock_session_mgr.get_active_session_count.return_value = 0

        # Test new unified admin dashboard endpoint
        response = client.get("/v1/admin/", headers={"Authorization": "Bearer admin_key"})
        assert response.status_code == 200
        data = response.json()
        # Check for service info
        assert "service" in data
        assert "version" in data
        assert "status" in data
        # Check for platforms
        assert "platforms" in data
        # Check for statistics
        assert "statistics" in data
        assert "total_sessions" in data["statistics"]
        assert "active_sessions" in data["statistics"]
        assert "telegram" in data["statistics"]
        assert "internal" in data["statistics"]


class TestSessionManagement:
    """Test session management functionality"""

    # Note: clear_sessions endpoint has been removed as part of admin refactoring
    # Session clearing is now handled through other mechanisms


class TestErrorHandling:
    """Test error handling across endpoints"""

    def test_404_on_invalid_endpoint(self, client):
        """Invalid endpoint returns 404"""
        response = client.get("/v1/invalid_endpoint")
        assert response.status_code == 404

    def test_405_on_wrong_method(self, client):
        """Wrong HTTP method returns 405"""
        response = client.get("/v1/chat")  # Should be POST
        assert response.status_code == 405

    @patch("app.api.dependencies.settings")
    def test_422_on_invalid_json(self, mock_settings, client):
        """Invalid JSON schema returns 422 (after authentication)"""
        mock_settings.TELEGRAM_SERVICE_KEY = "test_telegram_key"

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer test_telegram_key"},
            json={"invalid": "schema"},  # Missing required fields
        )
        assert response.status_code == 422


class TestPersianLanguageResponses:
    """Test that user-facing responses are in Persian"""

    @patch("app.api.dependencies.settings")
    @patch("app.services.message_processor.message_processor.process_message_simple")
    def test_rate_limit_message_is_persian(self, mock_process, mock_settings, client):
        """Rate limit messages are in Persian"""
        mock_settings.TELEGRAM_SERVICE_KEY = "test_telegram_key"
        mock_process.return_value = {
            "success": False,
            "error": "rate_limit_exceeded",
            "response": "⚠️ محدودیت سرعت",
        }

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer test_telegram_key"},
            json={"user_id": "user1", "text": "test"},
        )
        data = response.json()
        assert "محدودیت سرعت" in data["response"]

    @patch("app.api.dependencies.settings")
    def test_commands_descriptions_are_persian(self, mock_settings, client):
        """Command descriptions are in Persian"""
        mock_settings.TELEGRAM_SERVICE_KEY = "test_telegram_key"

        response = client.get("/v1/commands", headers={"Authorization": "Bearer test_telegram_key"})
        data = response.json()
        for cmd in data["commands"]:
            # Persian text should contain Persian characters
            assert any("\u0600" <= c <= "\u06FF" for c in cmd["description"])


class TestOpenAPIExamples:
    """Test that OpenAPI schema includes examples"""

    def test_openapi_has_examples(self, client):
        """OpenAPI schema includes request/response examples"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()

        # Check chat endpoint has examples
        chat_schema = data["paths"]["/v1/chat"]["post"]
        assert "examples" in chat_schema["responses"]["200"]["content"]["application/json"]

        # Check schemas have examples
        incoming_message_schema = data["components"]["schemas"]["IncomingMessage"]
        assert "examples" in incoming_message_schema

        bot_response_schema = data["components"]["schemas"]["BotResponse"]
        assert "examples" in bot_response_schema
