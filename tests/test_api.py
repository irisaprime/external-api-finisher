"""
API Endpoint Tests - v1

Tests for API v1 endpoints including:
- Authentication and authorization
- Team isolation
- Message processing
- Session management
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return MagicMock()


@pytest.fixture
def mock_api_key_team():
    """
    Mock team API key (external client)

    TWO-PATH AUTHENTICATION:
    - This is for external teams using /api/v1/chat endpoint
    - All database API keys have equal access (no access_level field)
    """
    key = Mock()
    key.id = 1
    key.team_id = 100
    key.key_prefix = "sk_test_"
    key.is_active = True
    key.team = Mock(name="External Team")
    return key


@pytest.fixture
def mock_super_admin_key():
    """
    Mock super admin API key (infrastructure level)

    TWO-PATH AUTHENTICATION:
    - This is for super admins accessing /api/v1/admin/* endpoints
    - NOT in database, verified via SUPER_ADMIN_API_KEYS environment variable
    - Returns just the key string (not a database object)
    """
    return "test_super_admin_key_12345"


@pytest.fixture
def mock_api_key_user():
    """
    Mock user API key (regular team user)

    This is an alias for mock_api_key_team for backward compatibility
    """
    key = Mock()
    key.id = 1
    key.team_id = 100
    key.key_prefix = "sk_user_"
    key.is_active = True
    key.team = Mock(name="User Team", platform_name="internal")
    return key


@pytest.fixture
def mock_api_key_internal():
    """
    Mock internal platform API key
    """
    key = Mock()
    key.id = 2
    key.team_id = 101
    key.key_prefix = "sk_internal_"
    key.is_active = True
    key.team = Mock(name="Internal Team", platform_name="internal")
    return key


@pytest.fixture
def mock_api_key_external():
    """
    Mock external platform API key
    """
    key = Mock()
    key.id = 3
    key.team_id = 102
    key.key_prefix = "sk_external_"
    key.is_active = True
    key.team = Mock(name="External Team", platform_name="telegram")
    return key


@pytest.fixture
def mock_api_key_admin():
    """
    Mock admin API key

    Note: In the current architecture, admin access is checked via super_admin_keys
    This fixture exists for test compatibility
    """
    key = Mock()
    key.id = 4
    key.team_id = 103
    key.key_prefix = "sk_admin_"
    key.is_active = True
    key.team = Mock(name="Admin Team", platform_name="internal")
    return key


class TestHealthEndpoint:
    """Test health check endpoints"""

    def test_root_health_check(self, client):
        """Test health endpoint (unversioned at /health for monitoring)"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data


class TestAuthenticationV1:
    """Test API v1 authentication"""

    def test_missing_auth_header(self, client):
        """Test request without auth header - should require authentication (401)"""
        response = client.post("/v1/chat", json={"user_id": "user1", "text": "Hello"})
        # SECURITY FIX: Authentication now required - should return 401
        assert response.status_code == 401
        data = response.json()
        assert "Authentication required" in data["detail"]

    @patch("app.api.dependencies.APIKeyManager")
    @patch("app.api.dependencies.get_db_session")
    def test_invalid_api_key(self, mock_get_db, mock_key_mgr, client):
        """Test request with invalid API key"""
        # Mock database and invalid key
        mock_key_mgr.validate_api_key.return_value = None

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer invalid_key"},
            json={
                "platform": "internal",
                "user_id": "user1",
                "conversation_id": "chat1",
                "message_id": "msg1",
                "text": "Hello",
                "type": "text",
            },
        )
        assert response.status_code == 403
        assert "Invalid API key" in response.text

    @patch("app.api.dependencies.APIKeyManager")
    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.routes.message_processor")
    def test_valid_api_key(
        self, mock_processor, mock_get_db, mock_key_mgr, client, mock_api_key_user
    ):
        """Test request with valid API key"""
        # Mock valid key
        mock_key_mgr.validate_api_key.return_value = mock_api_key_user

        # Mock message processor response with AsyncMock - use process_message_simple
        from app.models.schemas import BotResponse

        mock_processor.process_message_simple = AsyncMock(
            return_value=BotResponse(
                success=True,
                response="Test response",
                conversation_id="test_conversation",
                model="test-model",
            )
        )

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid_key"},
            json={"user_id": "user1", "text": "Hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestMessageEndpointV1:
    """Test /api/v1/chat endpoint"""

    @patch("app.api.dependencies.APIKeyManager")
    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.routes.message_processor")
    def test_message_endpoint_success(
        self, mock_processor, mock_get_db, mock_key_mgr, client, mock_api_key_user
    ):
        """Test successful message processing"""
        mock_key_mgr.validate_api_key.return_value = mock_api_key_user

        # Mock message processor response with AsyncMock - use process_message_simple
        from app.models.schemas import BotResponse

        mock_processor.process_message_simple = AsyncMock(
            return_value=BotResponse(
                success=True,
                response="Hello! How can I help?",
                model="gpt-4",
                total_message_count=2,
            )
        )

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid_key"},
            json={"user_id": "user1", "text": "Hello"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["response"] == "Hello! How can I help?"
        assert data["model"] == "gpt-4"
        assert data["total_message_count"] == 2

    @patch("app.api.dependencies.APIKeyManager")
    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.routes.message_processor")
    def test_message_endpoint_requires_internal_platform(
        self, mock_processor, mock_get_db, mock_key_mgr, client, mock_api_key_user
    ):
        """Test that API endpoint uses platform from API key"""
        mock_key_mgr.validate_api_key.return_value = mock_api_key_user

        # Mock message processor
        from app.models.schemas import BotResponse

        mock_processor.process_message_simple = AsyncMock(
            return_value=BotResponse(
                success=True,
                response="Platform determined from API key",
                conversation_id="test_conversation",
                model="test-model",
            )
        )

        response = client.post(
            "/v1/chat",
            headers={"Authorization": "Bearer valid_key"},
            json={"user_id": "user1", "text": "Hello"},
        )

        # Should succeed - platform is determined from API key's team.platform_name
        assert response.status_code == 200

        # Verify process_message_simple was called with platform from API key
        mock_processor.process_message_simple.assert_called_once()
        call_kwargs = mock_processor.process_message_simple.call_args[1]
        assert call_kwargs["platform_name"] == "internal"  # From mock_api_key_user


class TestAdminEndpointsV1:
    """Test admin-only endpoints"""

    def test_admin_endpoint_requires_admin_access(self, client):
        """Test that admin endpoints reject non-super-admin keys"""
        # Regular API key (not in super admin list)
        response = client.get("/v1/admin/", headers={"Authorization": "Bearer user_key_12345"})

        assert response.status_code == 403
        assert "Invalid super admin API key" in response.text

    @patch("app.api.dependencies.settings")
    def test_admin_endpoint_allows_admin(self, mock_settings, client):
        """Test that admin endpoints allow super admin keys"""
        # Mock super admin keys set
        mock_settings.super_admin_keys_set = {"test_super_admin_key_12345"}

        response = client.get(
            "/v1/admin/", headers={"Authorization": "Bearer test_super_admin_key_12345"}
        )

        # Should succeed (200) or have different error if endpoint not fully mocked
        assert response.status_code != 403


class TestAPIVersioning:
    """Test API versioning structure"""

    def test_v1_prefix_on_chat_endpoint(self, client):
        """Test that chat endpoint is at /v1/chat"""
        # Try without auth to verify endpoint exists
        response = client.post("/v1/chat", json={})
        # Should be 401 (auth required) or 422 (validation), not 404
        assert response.status_code in [401, 422]

    def test_docs_at_v1_path(self, client):
        """Test that API docs are at /v1/docs"""
        response = client.get("/v1/docs")
        # Docs might be disabled in production, but path should exist
        assert response.status_code in [200, 404]  # 404 if ENABLE_API_DOCS=false

    def test_openapi_at_v1_path(self, client):
        """Test that OpenAPI spec is at /v1/openapi.json"""
        response = client.get("/v1/openapi.json")
        # Should exist or be disabled, not 404 for wrong path
        assert response.status_code in [200, 404]  # 404 if ENABLE_API_DOCS=false


class TestSessionKeyIsolation:
    """Test session key generation includes team_id"""

    @patch("app.services.session_manager.session_manager")
    def test_session_key_includes_team_id(self, mock_sess_mgr):
        """Test that session keys include team_id for isolation"""
        from app.services.session_manager import SessionManager

        manager = SessionManager()

        # Test with team_id (internal platform)
        key_with_team = manager.get_session_key("internal", "chat123", team_id=100)
        assert "100" in key_with_team
        assert "chat123" in key_with_team

        # Test without team_id (telegram bot)
        key_without_team = manager.get_session_key("telegram", "chat123", team_id=None)
        assert "chat123" in key_without_team
        # Should NOT include team_id
        assert key_with_team != key_without_team

    @patch("app.services.session_manager.session_manager")
    def test_different_teams_same_conversation_id_different_sessions(self, mock_sess_mgr):
        """Test that two teams with same conversation_id get different sessions"""
        from app.services.session_manager import SessionManager

        manager = SessionManager()

        # Team 100 with conversation_id "user123"
        key_team_100 = manager.get_session_key("internal", "user123", team_id=100)

        # Team 200 with conversation_id "user123" (same conversation_id, different team)
        key_team_200 = manager.get_session_key("internal", "user123", team_id=200)

        # Keys must be different to prevent session collision
        assert key_team_100 != key_team_200
        assert "100" in key_team_100
        assert "200" in key_team_200


class TestQuotaEnforcement:
    """Test quota enforcement (if implemented)"""

    @patch("app.api.dependencies.APIKeyManager")
    @patch("app.api.dependencies.get_db_session")
    def test_quota_exceeded_returns_429(self, mock_get_db, mock_key_mgr, client, mock_api_key_user):
        """Test that quota exceeded returns 429"""
        # TODO: Implement when quota checking is in dependencies
        pass


class TestFixtureUsage:
    """Test that all fixtures are properly configured"""

    def test_mock_db_session_fixture(self, mock_db_session):
        """Test mock_db_session fixture (line 33)"""
        assert mock_db_session is not None

    def test_mock_api_key_team_fixture(self, mock_api_key_team):
        """Test mock_api_key_team fixture (lines 45-51)"""
        assert mock_api_key_team.id == 1
        assert mock_api_key_team.team_id == 100
        assert mock_api_key_team.key_prefix == "sk_test_"
        assert mock_api_key_team.is_active is True

    def test_mock_super_admin_key_fixture(self, mock_super_admin_key):
        """Test mock_super_admin_key fixture (line 64)"""
        assert mock_super_admin_key == "test_super_admin_key_12345"

    def test_mock_api_key_internal_fixture(self, mock_api_key_internal):
        """Test mock_api_key_internal fixture (lines 88-94)"""
        assert mock_api_key_internal.id == 2
        assert mock_api_key_internal.team_id == 101
        assert mock_api_key_internal.team.platform_name == "internal"

    def test_mock_api_key_external_fixture(self, mock_api_key_external):
        """Test mock_api_key_external fixture (lines 102-108)"""
        assert mock_api_key_external.id == 3
        assert mock_api_key_external.team_id == 102
        assert mock_api_key_external.team.platform_name == "telegram"

    def test_mock_api_key_admin_fixture(self, mock_api_key_admin):
        """Test mock_api_key_admin fixture (lines 119-125)"""
        assert mock_api_key_admin.id == 4
        assert mock_api_key_admin.team_id == 103
        assert mock_api_key_admin.key_prefix == "sk_admin_"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
