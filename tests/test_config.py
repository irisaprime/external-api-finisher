"""
Comprehensive tests for configuration management
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings, settings


class TestSettingsValidation:
    """Test settings validators"""

    def test_telegram_token_empty_raises_error(self):
        """Test TELEGRAM_BOT_TOKEN validator with empty token (line 102)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="a" * 32,
                INTERNAL_MODELS="model1,model2",
            )
        assert "TELEGRAM_BOT_TOKEN must be set" in str(exc_info.value)

    def test_telegram_token_placeholder_raises_error(self):
        """Test TELEGRAM_BOT_TOKEN validator with placeholder (line 102)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="a" * 32,
                INTERNAL_MODELS="model1,model2",
            )
        assert "TELEGRAM_BOT_TOKEN must be set" in str(exc_info.value)

    def test_telegram_token_invalid_format_raises_error(self):
        """Test TELEGRAM_BOT_TOKEN validator with invalid format (line 104)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="invalid_token_no_colon",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="a" * 32,
                INTERNAL_MODELS="model1,model2",
            )
        assert "Invalid Telegram bot token format" in str(exc_info.value)

    def test_internal_api_key_empty_raises_error(self):
        """Test INTERNAL_API_KEY validator with empty key (line 112)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="123:abc",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="",
                INTERNAL_MODELS="model1,model2",
            )
        assert "INTERNAL_API_KEY must be set" in str(exc_info.value)

    def test_internal_api_key_placeholder_raises_error(self):
        """Test INTERNAL_API_KEY validator with placeholder (line 112)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="123:abc",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="your_secure_random_api_key_here",
                INTERNAL_MODELS="model1,model2",
            )
        assert "INTERNAL_API_KEY must be set" in str(exc_info.value)

    def test_internal_api_key_too_short_raises_error(self):
        """Test INTERNAL_API_KEY validator with short key (line 114)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="123:abc",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="short_key_12345",  # Less than 32 chars
                INTERNAL_MODELS="model1,model2",
            )
        assert "must be at least 32 characters" in str(exc_info.value)

    def test_internal_models_empty_raises_error(self):
        """Test INTERNAL_MODELS validator with empty value (line 130)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="123:abc",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="a" * 32,
                INTERNAL_MODELS="",
            )
        assert "cannot be empty" in str(exc_info.value)

    def test_internal_models_json_array_valid(self):
        """Test INTERNAL_MODELS with valid JSON array (lines 134-140)"""
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS='["model1", "model2", "model3"]',
        )
        assert config.INTERNAL_MODELS == '["model1", "model2", "model3"]'

    def test_internal_models_json_not_list_type_raises_error(self):
        """Test INTERNAL_MODELS JSON that doesn't parse to list (line 137)"""
        # We need to mock json.loads to return non-list for this edge case
        import json as json_module
        from unittest.mock import patch

        with patch.object(json_module, "loads") as mock_loads:
            # Make json.loads return a string instead of list
            mock_loads.return_value = "not_a_list"

            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    TELEGRAM_BOT_TOKEN="123:abc",
                    AI_SERVICE_URL="http://test.com",
                    TELEGRAM_SERVICE_KEY="test_key",
                    INTERNAL_API_KEY="a" * 32,
                    INTERNAL_MODELS='["model1"]',  # Starts with [ but mocked to return non-list
                )
            assert "JSON must be an array" in str(exc_info.value)

    def test_internal_models_json_empty_array_raises_error(self):
        """Test INTERNAL_MODELS with empty JSON array (line 139)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="123:abc",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="a" * 32,
                INTERNAL_MODELS="[]",
            )
        assert "array cannot be empty" in str(exc_info.value)

    def test_internal_models_invalid_json_raises_error(self):
        """Test INTERNAL_MODELS with invalid JSON (line 142)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="123:abc",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="a" * 32,
                INTERNAL_MODELS='["invalid json',  # Malformed JSON
            )
        assert "invalid JSON" in str(exc_info.value)

    def test_internal_models_no_comma_or_slash_raises_error(self):
        """Test INTERNAL_MODELS without comma or slash (line 146)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_BOT_TOKEN="123:abc",
                AI_SERVICE_URL="http://test.com",
                TELEGRAM_SERVICE_KEY="test_key",
                INTERNAL_API_KEY="a" * 32,
                INTERNAL_MODELS="singlemodel",  # No comma or slash
            )
        assert "must be JSON array or comma-separated list" in str(exc_info.value)


class TestSettingsProperties:
    """Test settings properties"""

    @pytest.fixture
    def valid_settings(self):
        """Create valid settings instance"""
        return Settings(
            TELEGRAM_BOT_TOKEN="123456:ABC-DEF",
            AI_SERVICE_URL="http://ai.test.com",
            TELEGRAM_SERVICE_KEY="telegram_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS="model1,model2/variant,model3",
            SUPER_ADMIN_API_KEYS="admin_key_1,admin_key_2,admin_key_3",
            CORS_ORIGINS="http://localhost:3000,https://example.com",
            MAX_IMAGE_SIZE_MB=25,
        )

    def test_internal_models_list_json_format(self):
        """Test internal_models_list with JSON format (lines 170-171)"""
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS='["json_model1", "json_model2"]',
        )
        assert config.internal_models_list == ["json_model1", "json_model2"]

    def test_internal_models_list_json_decode_error_fallback(self):
        """Test internal_models_list handles JSON decode error (line 172-173)"""
        # Create settings with valid comma-separated, then mock JSON error
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS="model/a,model/b",
        )

        # Patch INTERNAL_MODELS to start with '[' but be invalid JSON
        with patch.object(config, "INTERNAL_MODELS", "[invalid"):
            # Should fall back to comma-separated parsing
            result = config.internal_models_list
            # Fallback should parse as comma-separated
            assert result == ["[invalid"]

    def test_super_admin_keys_set_empty(self, valid_settings):
        """Test super_admin_keys_set with empty value (line 192)"""
        valid_settings.SUPER_ADMIN_API_KEYS = ""
        assert valid_settings.super_admin_keys_set == set()

    def test_super_admin_keys_set_populated(self, valid_settings):
        """Test super_admin_keys_set with values"""
        assert valid_settings.super_admin_keys_set == {"admin_key_1", "admin_key_2", "admin_key_3"}

    def test_cors_origins_list_wildcard(self):
        """Test cors_origins_list with wildcard (line 199)"""
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS="model1,model2",
            CORS_ORIGINS="*",
        )
        assert config.cors_origins_list == ["*"]

    def test_cors_origins_list_comma_separated(self, valid_settings):
        """Test cors_origins_list with comma-separated (line 200)"""
        assert valid_settings.cors_origins_list == ["http://localhost:3000", "https://example.com"]

    def test_max_image_size_bytes(self, valid_settings):
        """Test max_image_size_bytes property (line 205)"""
        assert valid_settings.max_image_size_bytes == 25 * 1024 * 1024

    def test_database_url_property(self, valid_settings):
        """Test database_url property (lines 210-212)"""
        url = valid_settings.database_url
        assert "postgresql+asyncpg://" in url
        assert valid_settings.DB_USER in url
        assert str(valid_settings.DB_PORT) in url
        assert valid_settings.DB_NAME in url

    def test_is_development_true(self):
        """Test is_development property returns True (line 231)"""
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS="model1,model2",
            ENVIRONMENT="dev",
        )
        assert config.is_development is True

    def test_is_development_false(self):
        """Test is_development property returns False"""
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS="model1,model2",
            ENVIRONMENT="prod",
        )
        assert config.is_development is False

    def test_is_staging_true(self):
        """Test is_staging property returns True (line 236)"""
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS="model1,model2",
            ENVIRONMENT="stage",
        )
        assert config.is_staging is True

    def test_is_staging_alternate_name(self):
        """Test is_staging with 'staging' environment"""
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS="model1,model2",
            ENVIRONMENT="staging",
        )
        assert config.is_staging is True

    def test_enable_debug_features_in_dev(self):
        """Test enable_debug_features in development (line 241)"""
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS="model1,model2",
            ENVIRONMENT="dev",
        )
        assert config.enable_debug_features is True

    def test_enable_debug_features_in_prod(self):
        """Test enable_debug_features in production"""
        config = Settings(
            TELEGRAM_BOT_TOKEN="123:abc",
            AI_SERVICE_URL="http://test.com",
            TELEGRAM_SERVICE_KEY="test_key",
            INTERNAL_API_KEY="a" * 32,
            INTERNAL_MODELS="model1,model2",
            ENVIRONMENT="prod",
        )
        assert config.enable_debug_features is False


class TestGetSettings:
    """Test get_settings function"""

    def test_get_settings_returns_global_instance(self):
        """Test get_settings returns the global settings instance (line 251)"""
        result = get_settings()
        assert result is settings
        assert isinstance(result, Settings)
