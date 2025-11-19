"""
Tests for command processor

Tests command handling including:
- Command parsing and validation
- Platform-specific command access control
- Command execution for different platforms
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from app.models.session import ChatSession
from app.services.command_processor import CommandProcessor


@pytest.fixture
def command_processor():
    """Create command processor instance"""
    return CommandProcessor()


@pytest.fixture
def telegram_session():
    """Create Telegram session for testing"""
    return ChatSession(
        session_id="test_session_telegram",
        platform="telegram",
        platform_config={
            "type": "public",
            "rate_limit": 20,
            "max_history": 10,
            "available_models": [
                "google/gemini-2.0-flash-001",
                "deepseek/deepseek-v3",
                "openai/gpt-4o-mini",
            ],
        },
        user_id="telegram_user_123",
        conversation_id="telegram_chat_456",
        current_model="google/gemini-2.0-flash-001",
        is_admin=False,
    )


@pytest.fixture
def internal_session():
    """Create internal session for testing"""
    return ChatSession(
        session_id="test_session_internal",
        platform="internal",
        platform_config={
            "type": "private",
            "rate_limit": 60,
            "max_history": 20,
            "available_models": [
                "anthropic/claude-sonnet-4-5",
                "openai/gpt-5",
                "openai/gpt-4.1",
                "openai/gpt-4o-mini",
            ],
        },
        user_id="internal_user_789",
        conversation_id="internal_chat_012",
        current_model="anthropic/claude-sonnet-4-5",
        is_admin=True,
    )


class TestCommandParsing:
    """Tests for command parsing"""

    def test_is_command_with_slash(self, command_processor):
        """Test command detection with slash prefix"""
        assert command_processor.is_command("/start") is True
        assert command_processor.is_command("/help") is True
        assert command_processor.is_command("/model gemini") is True

    def test_is_command_with_exclamation(self, command_processor):
        """Test command detection with exclamation prefix"""
        assert command_processor.is_command("!start") is True
        assert command_processor.is_command("!help") is True
        assert command_processor.is_command("!model gemini") is True

    def test_is_command_without_prefix(self, command_processor):
        """Test non-command text"""
        assert command_processor.is_command("start") is False
        assert command_processor.is_command("help") is False
        assert command_processor.is_command("regular message") is False

    def test_is_command_with_empty_string(self, command_processor):
        """Test empty string"""
        assert command_processor.is_command("") is False
        assert command_processor.is_command(None) is False

    def test_parse_command_simple(self, command_processor):
        """Test parsing simple command"""
        command, args = command_processor.parse_command("/start")
        assert command == "start"
        assert args == []

    def test_parse_command_with_args(self, command_processor):
        """Test parsing command with arguments"""
        command, args = command_processor.parse_command("/model gemini")
        assert command == "model"
        assert args == ["gemini"]

    def test_parse_command_with_multiple_args(self, command_processor):
        """Test parsing command with multiple arguments"""
        command, args = command_processor.parse_command("/model Gemini 2.0 Flash")
        assert command == "model"
        assert args == ["Gemini", "2.0", "Flash"]

    def test_parse_command_case_insensitive(self, command_processor):
        """Test command parsing is case insensitive"""
        command, args = command_processor.parse_command("/START")
        assert command == "start"  # Should be lowercase

        command, args = command_processor.parse_command("/HeLp")
        assert command == "help"  # Should be lowercase

    def test_parse_command_with_exclamation(self, command_processor):
        """Test parsing command with exclamation prefix"""
        command, args = command_processor.parse_command("!help")
        assert command == "help"
        assert args == []

    def test_parse_command_with_spaces(self, command_processor):
        """Test parsing command with extra spaces"""
        command, args = command_processor.parse_command("/  model   gemini  ")
        assert command == "model"
        assert args == ["gemini"]

    def test_parse_command_empty_after_prefix(self, command_processor):
        """Test parsing command with only prefix"""
        command, args = command_processor.parse_command("/")
        assert command is None
        assert args == []

    def test_parse_non_command(self, command_processor):
        """Test parsing non-command text"""
        command, args = command_processor.parse_command("regular text")
        assert command is None
        assert args == []


class TestCommandAccessControl:
    """Tests for platform-specific command access control"""

    @patch("app.services.command_processor.platform_manager")
    def test_can_use_command_allowed(self, mock_platform_manager, command_processor):
        """Test command is allowed for platform"""
        mock_platform_manager.get_allowed_commands.return_value = [
            "start",
            "help",
            "status",
        ]

        assert command_processor.can_use_command("start", "telegram") is True
        assert command_processor.can_use_command("help", "telegram") is True

    @patch("app.services.command_processor.platform_manager")
    def test_can_use_command_not_allowed(self, mock_platform_manager, command_processor):
        """Test command is not allowed for platform"""
        mock_platform_manager.get_allowed_commands.return_value = ["start", "help"]

        assert command_processor.can_use_command("settings", "telegram") is False
        assert command_processor.can_use_command("admin", "telegram") is False


class TestStartCommand:
    """Tests for /start command"""

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_start_telegram(self, mock_platform_manager, command_processor, telegram_session):
        """Test /start command on Telegram"""
        mock_platform_manager.get_config.return_value = Mock(rate_limit=20)

        response = await command_processor.handle_start(telegram_session, [])

        assert response is not None
        assert "Gemini" in response  # Should show current model
        assert "20" in response or "۲۰" in response  # Should show rate limit

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_start_internal(self, mock_platform_manager, command_processor, internal_session):
        """Test /start command on internal platform"""
        mock_platform_manager.get_config.return_value = Mock(rate_limit=60)

        response = await command_processor.handle_start(internal_session, [])

        assert response is not None
        assert "Claude" in response  # Should show current model

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_start_internal_non_admin(
        self, mock_platform_manager, command_processor, internal_session
    ):
        """Test /start for non-admin internal user (line 90->92 branch)"""
        mock_platform_manager.get_config.return_value = Mock(rate_limit=60)
        internal_session.is_admin = False  # Explicitly test False branch

        response = await command_processor.handle_start(internal_session, [])

        assert response is not None
        assert "Claude" in response  # Should show current model
        # Should NOT contain admin message
        assert "ادمین" not in response

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_start_internal_admin(
        self, mock_platform_manager, command_processor, internal_session
    ):
        """Test /start command for admin user"""
        mock_platform_manager.get_config.return_value = Mock(rate_limit=60)
        internal_session.is_admin = True

        response = await command_processor.handle_start(internal_session, [])

        assert response is not None
        assert "ادمین" in response or "admin" in response.lower()


class TestHelpCommand:
    """Tests for /help command"""

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_help_telegram(self, mock_platform_manager, command_processor, telegram_session):
        """Test /help command on Telegram"""
        mock_platform_manager.get_allowed_commands.return_value = [
            "start",
            "help",
            "status",
            "model",
        ]
        mock_platform_manager.get_config.return_value = Mock(
            rate_limit=20, max_history=10, available_models=["model1", "model2"]
        )

        response = await command_processor.handle_help(telegram_session, [])

        assert response is not None
        assert "دستورات" in response  # Persian for "commands"
        assert "/start" in response
        assert "/help" in response
        assert "/model" in response

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_help_internal(self, mock_platform_manager, command_processor, internal_session):
        """Test /help command on internal platform"""
        mock_platform_manager.get_allowed_commands.return_value = [
            "start",
            "help",
            "status",
            "model",
            "settings",
        ]
        mock_platform_manager.get_config.return_value = Mock(
            rate_limit=60, max_history=20, available_models=["model1", "model2", "model3"]
        )

        response = await command_processor.handle_help(internal_session, [])

        assert response is not None
        assert "دستورات" in response
        assert "/settings" in response  # Internal-only command

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_help_with_unknown_command(
        self, mock_platform_manager, command_processor, telegram_session
    ):
        """Test /help with unknown command not in COMMAND_DESCRIPTIONS (line 106 branch)"""
        # Include a command that's not in COMMAND_DESCRIPTIONS
        mock_platform_manager.get_allowed_commands.return_value = [
            "start",
            "help",
            "unknown_cmd",  # This command is not in COMMAND_DESCRIPTIONS
        ]
        mock_platform_manager.get_config.return_value = Mock(
            rate_limit=20, max_history=10, available_models=["model1"]
        )

        response = await command_processor.handle_help(telegram_session, [])

        assert response is not None
        assert "دستورات" in response
        # Should still show the unknown command in the copy-ready section
        assert "/unknown_cmd" in response


class TestStatusCommand:
    """Tests for /status command"""

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_status_telegram(self, mock_platform_manager, command_processor, telegram_session):
        """Test /status command on Telegram"""
        mock_platform_manager.get_config.return_value = Mock(type="public", rate_limit=20)
        telegram_session.total_message_count = 5

        response = await command_processor.handle_status(telegram_session, [])

        assert response is not None
        assert "وضعیت" in response  # Persian for "status"
        assert "telegram" in response.lower()
        assert "5" in response or "۵" in response  # Message count

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_status_admin(self, mock_platform_manager, command_processor, internal_session):
        """Test /status command for admin user"""
        mock_platform_manager.get_config.return_value = Mock(type="private", rate_limit=60)
        internal_session.is_admin = True

        response = await command_processor.handle_status(internal_session, [])

        assert response is not None
        assert "ادمین" in response  # Should show admin role


class TestClearCommand:
    """Tests for /clear command"""

    @pytest.mark.asyncio
    async def test_clear_history(self, command_processor, telegram_session):
        """Test /clear command clears in-memory history (AI context)"""
        # Add some messages to in-memory history
        telegram_session.add_message("user", "Test message 1")
        telegram_session.add_message("assistant", "Response 1")
        telegram_session.add_message("user", "Test message 2")

        assert len(telegram_session.history) == 3

        response = await command_processor.handle_clear(telegram_session, [])

        assert response is not None
        # History (AI context) should be cleared
        assert len(telegram_session.history) == 0
        # total_message_count persists (tracks DB messages, not affected by /clear)
        # This is expected per architecture: total_message_count tracks all messages ever


class TestModelCommand:
    """Tests for /model command"""

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_model_without_args(self, mock_platform_manager, command_processor, telegram_session):
        """Test /model command without arguments shows current model"""
        mock_platform_manager.get_available_models_friendly.return_value = [
            "Gemini 2.0 Flash",
            "DeepSeek v3",
            "GPT-4o Mini",
        ]

        response = await command_processor.handle_model(telegram_session, [])

        assert response is not None
        assert "Gemini" in response  # Should show current model
        assert "DeepSeek" in response  # Should show available models

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_model_switch_valid(self, mock_platform_manager, command_processor, telegram_session):
        """Test switching to valid model"""
        mock_platform_manager.resolve_model_name.return_value = "deepseek/deepseek-v3"

        response = await command_processor.handle_model(telegram_session, ["deepseek"])

        assert response is not None
        assert telegram_session.current_model == "deepseek/deepseek-v3"
        assert "deepseek" in response.lower()  # Should confirm switch (case-insensitive)

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_model_switch_invalid(self, mock_platform_manager, command_processor, telegram_session):
        """Test switching to invalid model"""
        mock_platform_manager.resolve_model_name.return_value = None
        mock_platform_manager.get_available_models_friendly.return_value = [
            "Gemini 2.0 Flash",
            "DeepSeek v3",
        ]

        response = await command_processor.handle_model(telegram_session, ["invalid_model"])

        assert response is not None
        assert "invalid_model" in response.lower()  # Should mention invalid model
        assert telegram_session.current_model == "google/gemini-2.0-flash-001"  # Should not change

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_model_multi_word_name(self, mock_platform_manager, command_processor, telegram_session):
        """Test switching with multi-word model name"""
        mock_platform_manager.resolve_model_name.return_value = "google/gemini-2.5-flash"

        response = await command_processor.handle_model(
            telegram_session, ["Gemini", "2.5", "Flash"]
        )

        assert response is not None
        assert telegram_session.current_model == "google/gemini-2.5-flash"


class TestModelsCommand:
    """Tests for /models command"""

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_models_telegram(self, mock_platform_manager, command_processor, telegram_session):
        """Test /models command on Telegram"""
        mock_platform_manager.get_available_models_friendly.return_value = [
            "Gemini 2.0 Flash",
            "DeepSeek v3",
            "GPT-4o Mini",
        ]

        response = await command_processor.handle_models(telegram_session, [])

        assert response is not None
        assert "Gemini" in response
        assert "DeepSeek" in response
        assert "GPT-4o Mini" in response
        assert "فعلی" in response  # Should mark current model

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_models_internal(self, mock_platform_manager, command_processor, internal_session):
        """Test /models command on internal platform"""
        mock_platform_manager.get_available_models_friendly.return_value = [
            "Claude Sonnet 4",
            "GPT-5",
            "Grok 4",
        ]

        response = await command_processor.handle_models(internal_session, [])

        assert response is not None
        assert "Claude" in response
        assert "GPT-5" in response
        assert "داخلی" in response  # Should mention internal


class TestSettingsCommand:
    """Tests for /settings command"""

    @pytest.mark.asyncio
    async def test_settings_internal(self, command_processor, internal_session):
        """Test /settings command on internal platform"""
        response = await command_processor.handle_settings(internal_session, [])

        assert response is not None
        assert "تنظیمات" in response  # Persian for "settings"
        assert internal_session.user_id in response

    @pytest.mark.asyncio
    async def test_settings_telegram_not_allowed(self, command_processor, telegram_session):
        """Test /settings command not allowed on Telegram"""
        response = await command_processor.handle_settings(telegram_session, [])

        assert response is not None
        assert "داخلی" in response  # Should say internal only


class TestCommandProcessor:
    """Integration tests for command processor"""

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_process_valid_command(self, mock_platform_manager, command_processor, telegram_session):
        """Test processing valid command"""
        mock_platform_manager.get_allowed_commands.return_value = ["start", "help", "status"]
        mock_platform_manager.get_config.return_value = Mock(rate_limit=20)

        response = await command_processor.process_command(telegram_session, "/start")

        assert response is not None
        assert "Gemini" in response

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_process_command_not_allowed(self, mock_platform_manager, command_processor, telegram_session):
        """Test processing command not allowed for platform"""
        mock_platform_manager.get_allowed_commands.return_value = ["start", "help"]

        response = await command_processor.process_command(telegram_session, "/settings")

        assert response is not None
        assert "settings" in response.lower()
        assert "telegram" in response.lower()

    @pytest.mark.asyncio
    async def test_process_unknown_command(self, command_processor, telegram_session):
        """Test processing unknown command"""
        with patch("app.services.command_processor.platform_manager") as mock_pm:
            mock_pm.get_allowed_commands.return_value = [
                "start",
                "help",
                "status",
                "unknown_cmd",
            ]

            response = await command_processor.process_command(telegram_session, "/unknown_cmd")

            assert response is not None
            assert "unknown_cmd" in response.lower()

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_process_command_with_error(self, mock_platform_manager, command_processor, telegram_session):
        """Test command processing with error"""
        mock_platform_manager.get_allowed_commands.return_value = ["start"]
        mock_platform_manager.get_config.side_effect = Exception("Test error")

        response = await command_processor.process_command(telegram_session, "/start")

        assert response is not None
        assert "خطا" in response  # Persian for "error"

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_process_empty_command(self, mock_platform_manager, command_processor, telegram_session):
        """Test processing empty command (line 62 coverage)"""
        mock_platform_manager.get_allowed_commands.return_value = ["start", "help"]

        # Send just the slash with no command
        response = await command_processor.process_command(telegram_session, "/")

        assert response is not None
        assert len(response) > 0  # Should return unknown command message

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_model_without_args_internal(self, mock_platform_manager, command_processor, internal_session):
        """Test /model command without arguments on internal platform (lines 183-187 coverage)"""
        mock_platform_manager.get_available_models_friendly.return_value = [
            "Claude Sonnet 4",
            "GPT-5",
            "GPT-4.1",
            "GPT-4o Mini",
        ]

        response = await command_processor.handle_model(internal_session, [])

        assert response is not None
        assert "Claude" in response or "claude" in response  # Should show models
        # Should show internal platform model suggestions (lines 183-187)
        assert "claude" in response.lower() or "gpt5" in response.lower()

    @pytest.mark.asyncio
    @patch("app.services.command_processor.platform_manager")
    async def test_model_switch_invalid_internal(self, mock_platform_manager, command_processor, internal_session):
        """Test switching to invalid model on internal platform (line 208 coverage)"""
        mock_platform_manager.resolve_model_name.return_value = None
        mock_platform_manager.get_available_models_friendly.return_value = [
            "Claude Sonnet 4",
            "GPT-5",
        ]

        response = await command_processor.handle_model(internal_session, ["invalid_model"])

        assert response is not None
        assert "invalid_model" in response.lower()  # Should mention invalid model
        # Should show internal platform quick commands (line 208)
        assert "claude" in response.lower() or "gpt" in response.lower()
        assert internal_session.current_model == "anthropic/claude-sonnet-4-5"  # Should not change
