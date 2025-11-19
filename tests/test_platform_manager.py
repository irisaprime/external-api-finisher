"""
Tests for Platform Manager service
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

from app.core.constants import Platform, PlatformType
from app.services.platform_manager import PlatformConfig, PlatformManager, platform_manager


@pytest.fixture
def manager():
    """Create a fresh platform manager instance for testing"""
    return PlatformManager()


class TestPlatformConfig:
    """Tests for PlatformConfig"""

    def test_platform_config_initialization(self):
        """Test platform config is initialized correctly"""
        config = PlatformConfig(
            type=PlatformType.PUBLIC,
            model="test-model",
            available_models=["model1", "model2"],
            rate_limit=30,
            commands=["start", "help"],
            allow_model_switch=True,
            requires_auth=False,
            api_key=None,
            max_history=20,
        )

        assert config.type == PlatformType.PUBLIC
        assert config.model == "test-model"
        assert config.available_models == ["model1", "model2"]
        assert config.rate_limit == 30
        assert config.commands == ["start", "help"]
        assert config.allow_model_switch is True
        assert config.requires_auth is False
        assert config.api_key is None
        assert config.max_history == 20

    def test_platform_config_defaults(self):
        """Test platform config default values"""
        config = PlatformConfig(type=PlatformType.PUBLIC, model="test-model")

        assert config.available_models == ["test-model"]
        assert config.commands == []
        assert config.rate_limit == 30
        assert config.allow_model_switch is False
        assert config.requires_auth is False

    def test_platform_config_dict(self):
        """Test converting platform config to dictionary"""
        config = PlatformConfig(
            type=PlatformType.PRIVATE,
            model="test-model",
            available_models=["model1"],
            rate_limit=60,
            commands=["start"],
            allow_model_switch=True,
            requires_auth=True,
            max_history=30,
        )

        result = config.dict()

        assert result["type"] == PlatformType.PRIVATE
        assert result["model"] == "test-model"
        assert result["available_models"] == ["model1"]
        assert result["rate_limit"] == 60
        assert result["commands"] == ["start"]
        assert result["allow_model_switch"] is True
        assert result["requires_auth"] is True
        assert result["max_history"] == 30
        assert "api_key" not in result


class TestPlatformManager:
    """Tests for PlatformManager"""

    def test_manager_initialization(self, manager):
        """Test manager is initialized with configs"""
        assert Platform.TELEGRAM in manager.configs
        assert Platform.INTERNAL in manager.configs

    def test_get_config_telegram(self, manager):
        """Test getting Telegram config"""
        config = manager.get_config(Platform.TELEGRAM)

        assert config is not None
        assert config.type == PlatformType.PUBLIC
        assert config.requires_auth is False

    def test_get_config_internal(self, manager):
        """Test getting Internal config"""
        config = manager.get_config(Platform.INTERNAL)

        assert config is not None
        assert config.type == PlatformType.PRIVATE
        assert config.requires_auth is True

    def test_get_config_case_insensitive(self, manager):
        """Test config lookup is case insensitive"""
        config1 = manager.get_config("TELEGRAM")
        config2 = manager.get_config("telegram")
        config3 = manager.get_config("Telegram")

        assert config1 is config2
        assert config2 is config3

    def test_get_config_unknown_platform_defaults_to_telegram(self, manager):
        """Test unknown platform defaults to Telegram"""
        config = manager.get_config("unknown_platform")

        assert config is manager.configs[Platform.TELEGRAM]

    def test_is_private_platform_telegram(self, manager):
        """Test Telegram is not a private platform"""
        assert manager.is_private_platform(Platform.TELEGRAM) is False

    def test_is_private_platform_internal(self, manager):
        """Test Internal is a private platform"""
        assert manager.is_private_platform(Platform.INTERNAL) is True

    def test_can_switch_models_telegram(self, manager):
        """Test Telegram allows model switching"""
        assert manager.can_switch_models(Platform.TELEGRAM) is True

    def test_can_switch_models_internal(self, manager):
        """Test Internal allows model switching"""
        assert manager.can_switch_models(Platform.INTERNAL) is True

    def test_get_available_models_telegram(self, manager):
        """Test getting available models for Telegram"""
        models = manager.get_available_models(Platform.TELEGRAM)

        assert isinstance(models, list)
        assert len(models) > 0

    def test_get_available_models_internal(self, manager):
        """Test getting available models for Internal"""
        models = manager.get_available_models(Platform.INTERNAL)

        assert isinstance(models, list)
        assert len(models) > 0

    def test_get_default_model_telegram(self, manager):
        """Test getting default model for Telegram"""
        model = manager.get_default_model(Platform.TELEGRAM)

        assert model is not None
        assert isinstance(model, str)

    def test_get_default_model_internal(self, manager):
        """Test getting default model for Internal"""
        model = manager.get_default_model(Platform.INTERNAL)

        assert model is not None
        assert isinstance(model, str)

    def test_get_rate_limit_telegram(self, manager):
        """Test getting rate limit for Telegram"""
        rate_limit = manager.get_rate_limit(Platform.TELEGRAM)

        assert isinstance(rate_limit, int)
        assert rate_limit > 0

    def test_get_rate_limit_internal(self, manager):
        """Test getting rate limit for Internal"""
        rate_limit = manager.get_rate_limit(Platform.INTERNAL)

        assert isinstance(rate_limit, int)
        assert rate_limit > 0

    def test_get_allowed_commands_telegram(self, manager):
        """Test getting allowed commands for Telegram"""
        commands = manager.get_allowed_commands(Platform.TELEGRAM)

        assert isinstance(commands, list)
        assert len(commands) > 0

    def test_get_allowed_commands_internal(self, manager):
        """Test getting allowed commands for Internal"""
        commands = manager.get_allowed_commands(Platform.INTERNAL)

        assert isinstance(commands, list)
        assert len(commands) > 0

    def test_get_max_history_telegram(self, manager):
        """Test getting max history for Telegram"""
        max_history = manager.get_max_history(Platform.TELEGRAM)

        assert isinstance(max_history, int)
        assert max_history > 0

    def test_get_max_history_internal(self, manager):
        """Test getting max history for Internal"""
        max_history = manager.get_max_history(Platform.INTERNAL)

        assert isinstance(max_history, int)
        assert max_history > 0

    def test_requires_auth_telegram(self, manager):
        """Test Telegram doesn't require auth"""
        assert manager.requires_auth(Platform.TELEGRAM) is False

    def test_requires_auth_internal(self, manager):
        """Test Internal requires auth"""
        assert manager.requires_auth(Platform.INTERNAL) is True

    def test_validate_auth_no_auth_required(self, manager):
        """Test validation passes when auth not required"""
        result = manager.validate_auth(Platform.TELEGRAM, "any_token")

        assert result is True

    def test_validate_auth_with_correct_token(self, manager):
        """Test validation passes with correct token"""
        config = manager.get_config(Platform.INTERNAL)
        if config.api_key:
            result = manager.validate_auth(Platform.INTERNAL, config.api_key)
            assert result is True

    def test_validate_auth_with_incorrect_token(self, manager):
        """Test validation fails with incorrect token"""
        result = manager.validate_auth(Platform.INTERNAL, "wrong_token")

        assert result is False

    @patch("app.services.platform_manager.settings")
    def test_is_admin_telegram_admin_user(self, mock_settings, manager):
        """Test Telegram admin user check"""
        mock_settings.telegram_admin_users_set = {"12345"}

        assert manager.is_admin(Platform.TELEGRAM, "12345") is True
        assert manager.is_admin(Platform.TELEGRAM, "67890") is False

    @patch("app.services.platform_manager.settings")
    def test_is_admin_internal_admin_user(self, mock_settings, manager):
        """Test Internal admin user check"""
        mock_settings.internal_admin_users_set = {"admin123"}

        assert manager.is_admin(Platform.INTERNAL, "admin123") is True
        assert manager.is_admin(Platform.INTERNAL, "user456") is False

    def test_is_admin_unknown_platform(self, manager):
        """Test admin check for unknown platform returns False"""
        assert manager.is_admin("unknown", "any_user") is False

    def test_is_model_available_true(self, manager):
        """Test model availability check returns True for available model"""
        available_models = manager.get_available_models(Platform.TELEGRAM)
        if available_models:
            result = manager.is_model_available(Platform.TELEGRAM, available_models[0])
            assert result is True

    def test_is_model_available_false(self, manager):
        """Test model availability check returns False for unavailable model"""
        result = manager.is_model_available(Platform.TELEGRAM, "nonexistent/model")

        assert result is False

    @patch("app.services.platform_manager.get_friendly_model_name")
    def test_get_available_models_friendly(self, mock_friendly, manager):
        """Test getting friendly model names"""
        mock_friendly.side_effect = lambda x: f"Friendly {x}"
        manager.configs[Platform.TELEGRAM].available_models = ["model1", "model2"]

        result = manager.get_available_models_friendly(Platform.TELEGRAM)

        assert result == ["Friendly model1", "Friendly model2"]
        assert mock_friendly.call_count == 2

    @patch("app.services.platform_manager.get_friendly_model_name")
    def test_get_default_model_friendly(self, mock_friendly, manager):
        """Test getting friendly default model name"""
        mock_friendly.return_value = "Friendly Model"
        manager.configs[Platform.TELEGRAM].model = "technical/model"

        result = manager.get_default_model_friendly(Platform.TELEGRAM)

        assert result == "Friendly Model"
        mock_friendly.assert_called_once_with("technical/model")

    def test_resolve_model_name_technical_id(self, manager):
        """Test resolving model name with technical ID"""
        available_models = manager.get_available_models(Platform.TELEGRAM)
        if available_models:
            technical_model = available_models[0]
            result = manager.resolve_model_name(technical_model, Platform.TELEGRAM)
            assert result == technical_model

    @patch("app.services.platform_manager.get_technical_model_name")
    def test_resolve_model_name_friendly_name(self, mock_technical, manager):
        """Test resolving model name with friendly name"""
        available_models = manager.get_available_models(Platform.TELEGRAM)
        if available_models:
            mock_technical.return_value = available_models[0]

            result = manager.resolve_model_name("Friendly Name", Platform.TELEGRAM)

            assert result == available_models[0]

    @patch("app.core.constants.TELEGRAM_MODEL_ALIASES", {"gemini": "Gemini Flash"})
    @patch("app.services.platform_manager.get_technical_model_name")
    def test_resolve_model_name_alias(self, mock_technical, manager):
        """Test resolving model name with alias"""
        available_models = manager.get_available_models(Platform.TELEGRAM)
        if available_models:
            mock_technical.return_value = available_models[0]

            result = manager.resolve_model_name("gemini", Platform.TELEGRAM)

            if result:
                assert result == available_models[0]

    @patch("app.services.platform_manager.get_technical_model_name")
    def test_resolve_model_name_not_found(self, mock_technical, manager):
        """Test resolving model name returns None for unknown model"""
        mock_technical.return_value = "unknown/model"

        result = manager.resolve_model_name("Unknown Model", Platform.TELEGRAM)

        assert result is None

    def test_resolve_model_name_strips_whitespace(self, manager):
        """Test resolving model name strips whitespace"""
        available_models = manager.get_available_models(Platform.TELEGRAM)
        if available_models:
            technical_model = available_models[0]
            result = manager.resolve_model_name(f"  {technical_model}  ", Platform.TELEGRAM)
            assert result == technical_model

    def test_resolve_model_name_alias_internal_platform(self, manager):
        """Test resolving model name with alias for internal platform (non-telegram)"""
        # Get an available model for internal platform
        available_models = manager.get_available_models(Platform.INTERNAL)

        if available_models and len(available_models) > 0:
            # Use a real model that exists (technical name)
            technical_model = available_models[0]
            friendly_name = "Test Friendly Name"

            # Patch the aliases to map alias -> friendly name
            # Mock get_technical_model_name to:
            # 1. Return input unchanged for "testalias" (not recognized as friendly)
            # 2. Return technical_model for the friendly_name
            def mock_get_technical(name):
                if name == friendly_name:
                    return technical_model
                return name  # Return unchanged if not recognized

            with patch("app.core.constants.MODEL_ALIASES", {"testalias": friendly_name}):
                with patch("app.services.platform_manager.get_technical_model_name", side_effect=mock_get_technical):
                    result = manager.resolve_model_name("testalias", Platform.INTERNAL)

                    # Should resolve: alias -> friendly -> technical
                    assert result == technical_model


class TestGlobalInstance:
    """Tests for global platform_manager instance"""

    def test_global_instance_exists(self):
        """Test that global instance is created"""
        assert platform_manager is not None
        assert isinstance(platform_manager, PlatformManager)

    def test_global_instance_has_configs(self):
        """Test global instance has platform configs loaded"""
        assert len(platform_manager.configs) >= 2
        assert Platform.TELEGRAM in platform_manager.configs
        assert Platform.INTERNAL in platform_manager.configs
