"""
Tests for API dependencies (authentication)

Tests three authentication functions:
- require_admin_access (super admin)
- require_team_access (team API keys)
- require_chat_access (Telegram + team API keys)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import require_admin_access, require_team_access, require_chat_access


class TestRequireAdminAccess:
    """Tests for require_admin_access dependency"""

    def test_admin_access_no_authorization(self):
        """Test admin access with no authorization header"""
        with pytest.raises(HTTPException) as exc_info:
            require_admin_access(authorization=None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    @patch("app.api.dependencies.settings")
    def test_admin_access_no_keys_configured(self, mock_settings):
        """Test admin access when super admin keys not configured (lines 84-85 coverage)"""
        mock_settings.super_admin_keys_set = set()  # Empty set - no keys configured

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_key")

        with pytest.raises(HTTPException) as exc_info:
            require_admin_access(authorization=auth)

        assert exc_info.value.status_code == 401
        assert "not configured" in exc_info.value.detail

    @patch("app.api.dependencies.settings")
    def test_admin_access_invalid_key(self, mock_settings):
        """Test admin access with invalid super admin key"""
        mock_settings.super_admin_keys_set = {"valid_admin_key"}

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid_key")

        with pytest.raises(HTTPException) as exc_info:
            require_admin_access(authorization=auth)

        assert exc_info.value.status_code == 403
        assert "Invalid super admin" in exc_info.value.detail

    @patch("app.api.dependencies.settings")
    def test_admin_access_valid_key(self, mock_settings):
        """Test admin access with valid super admin key"""
        valid_key = "valid_admin_key_12345"
        mock_settings.super_admin_keys_set = {valid_key}

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_key)

        result = require_admin_access(authorization=auth)

        assert result == valid_key


class TestRequireTeamAccess:
    """Tests for require_team_access dependency"""

    def test_team_access_no_authorization(self):
        """Test team access with no authorization header (line 143-144 coverage)"""
        with pytest.raises(HTTPException) as exc_info:
            require_team_access(authorization=None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.dependencies.APIKeyManager")
    def test_team_access_invalid_key(self, mock_api_key_mgr, mock_get_db):
        """Test team access with invalid API key (lines 148-151 coverage)"""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        # validate_api_key returns None for invalid key
        mock_api_key_mgr.validate_api_key.return_value = None

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid_team_key")

        with pytest.raises(HTTPException) as exc_info:
            require_team_access(authorization=auth)

        assert exc_info.value.status_code == 403
        assert "Invalid API key" in exc_info.value.detail

    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.dependencies.APIKeyManager")
    def test_team_access_valid_key(self, mock_api_key_mgr, mock_get_db):
        """Test team access with valid API key (lines 148-156 coverage)"""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        # Mock valid API key
        mock_api_key = Mock()
        mock_api_key.key_prefix = "ak_team_"
        mock_api_key.team = Mock()
        mock_api_key.team.display_name = "Test Team"

        mock_api_key_mgr.validate_api_key.return_value = mock_api_key

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid_team_key")

        result = require_team_access(authorization=auth)

        assert result == mock_api_key
        mock_api_key_mgr.validate_api_key.assert_called_once_with(mock_db, "valid_team_key")

    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.dependencies.APIKeyManager")
    def test_team_access_database_error(self, mock_api_key_mgr, mock_get_db):
        """Test team access with database error (lines 160-162 coverage)"""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        # Simulate database error
        mock_api_key_mgr.validate_api_key.side_effect = Exception("Database connection error")

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_key")

        with pytest.raises(HTTPException) as exc_info:
            require_team_access(authorization=auth)

        assert exc_info.value.status_code == 500
        assert "Error validating API key" in exc_info.value.detail


class TestRequireChatAccess:
    """Tests for require_chat_access dependency"""

    def test_chat_access_no_authorization(self):
        """Test chat access with no authorization header"""
        with pytest.raises(HTTPException) as exc_info:
            require_chat_access(authorization=None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    @patch("app.api.dependencies.settings")
    def test_chat_access_telegram_service_key(self, mock_settings):
        """Test chat access with Telegram service key"""
        telegram_key = "telegram_service_key_12345"
        mock_settings.TELEGRAM_SERVICE_KEY = telegram_key

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials=telegram_key)

        result = require_chat_access(authorization=auth)

        assert result == "telegram"

    @patch("app.api.dependencies.settings")
    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.dependencies.APIKeyManager")
    def test_chat_access_valid_team_key(self, mock_api_key_mgr, mock_get_db, mock_settings):
        """Test chat access with valid team API key"""
        mock_settings.TELEGRAM_SERVICE_KEY = "different_telegram_key"

        mock_db = Mock()
        mock_get_db.return_value = mock_db

        # Mock valid API key
        mock_api_key = Mock()
        mock_api_key.key_prefix = "ak_team_"
        mock_api_key.team = Mock()
        mock_api_key.team.platform_name = "Internal-BI"

        mock_api_key_mgr.validate_api_key.return_value = mock_api_key

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid_team_key")

        result = require_chat_access(authorization=auth)

        assert result == mock_api_key

    @patch("app.api.dependencies.settings")
    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.dependencies.APIKeyManager")
    def test_chat_access_invalid_key(self, mock_api_key_mgr, mock_get_db, mock_settings):
        """Test chat access with invalid key"""
        mock_settings.TELEGRAM_SERVICE_KEY = "telegram_key"

        mock_db = Mock()
        mock_get_db.return_value = mock_db

        # validate_api_key returns None
        mock_api_key_mgr.validate_api_key.return_value = None

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid_key")

        with pytest.raises(HTTPException) as exc_info:
            require_chat_access(authorization=auth)

        assert exc_info.value.status_code == 403
        assert "Invalid API key" in exc_info.value.detail

    @patch("app.api.dependencies.settings")
    @patch("app.api.dependencies.get_db_session")
    @patch("app.api.dependencies.APIKeyManager")
    def test_chat_access_database_error(self, mock_api_key_mgr, mock_get_db, mock_settings):
        """Test chat access with database error (lines 233-235 coverage)"""
        mock_settings.TELEGRAM_SERVICE_KEY = "telegram_key"

        mock_db = Mock()
        mock_get_db.return_value = mock_db

        # Simulate database error
        mock_api_key_mgr.validate_api_key.side_effect = Exception("Database error")

        auth = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_key")

        with pytest.raises(HTTPException) as exc_info:
            require_chat_access(authorization=auth)

        assert exc_info.value.status_code == 500
        assert "Error validating API key" in exc_info.value.detail
