"""
Channel configuration manager
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.constants import Platform, PlatformType
from app.core.name_mapping import get_friendly_model_name, get_technical_model_name

logger = logging.getLogger(__name__)


class ChannelConfig:
    """Channel configuration"""

    def __init__(
        self,
        type: str,
        model: str,
        available_models: List[str] = None,
        rate_limit: int = 30,
        commands: List[str] = None,
        allow_model_switch: bool = False,
        requires_auth: bool = False,
        api_key: str = None,
        max_history: int = 20,
    ):
        self.type = type
        self.model = model
        self.available_models = available_models or [model]
        self.rate_limit = rate_limit
        self.commands = commands or []
        self.allow_model_switch = allow_model_switch
        self.requires_auth = requires_auth
        self.api_key = api_key
        self.max_history = max_history

    def copy(self) -> 'ChannelConfig':
        """Create a copy of this config"""
        return ChannelConfig(
            type=self.type,
            model=self.model,
            available_models=self.available_models.copy(),
            rate_limit=self.rate_limit,
            commands=self.commands.copy(),
            allow_model_switch=self.allow_model_switch,
            requires_auth=self.requires_auth,
            api_key=self.api_key,
            max_history=self.max_history,
        )

    def dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.type,
            "model": self.model,
            "available_models": self.available_models,
            "rate_limit": self.rate_limit,
            "commands": self.commands,
            "allow_model_switch": self.allow_model_switch,
            "requires_auth": self.requires_auth,
            "max_history": self.max_history,
        }


class ChannelManager:
    """Manages channel-specific configurations with database-driven overrides"""

    def __init__(self):
        # Default configurations for channel types
        self.default_configs: Dict[str, ChannelConfig] = {}
        # Keep backward compatibility configs
        self.configs: Dict[str, ChannelConfig] = {}
        self._load_configurations()

    def _load_configurations(self):
        """Load default channel type configurations"""

        # Public channel defaults (Telegram, Discord, etc.)
        public_config = ChannelConfig(
            type=PlatformType.PUBLIC,
            model=settings.TELEGRAM_DEFAULT_MODEL,
            available_models=settings.telegram_models_list,
            rate_limit=settings.TELEGRAM_RATE_LIMIT,
            commands=settings.telegram_commands_list,
            allow_model_switch=settings.TELEGRAM_ALLOW_MODEL_SWITCH,
            requires_auth=False,
            max_history=settings.TELEGRAM_MAX_HISTORY,
        )

        # Private channel defaults (Customer integrations)
        private_config = ChannelConfig(
            type=PlatformType.PRIVATE,
            model=settings.INTERNAL_DEFAULT_MODEL,
            available_models=settings.internal_models_list,
            rate_limit=settings.INTERNAL_RATE_LIMIT,
            commands=["start", "help", "status", "clear", "model", "models"],  # NO /settings
            allow_model_switch=True,
            requires_auth=True,
            api_key=settings.INTERNAL_API_KEY,
            max_history=settings.INTERNAL_MAX_HISTORY,
        )

        # Store by type
        self.default_configs['public'] = public_config
        self.default_configs['private'] = private_config

        # Backward compatibility - keep old structure
        self.configs[Platform.TELEGRAM] = public_config
        self.configs[Platform.INTERNAL] = private_config

        logger.info("Channel configurations loaded successfully")
        logger.info(f"  - Public: {public_config.model} + {len(public_config.available_models)} models")
        logger.info(f"  - Private: {len(private_config.available_models)} models")

    def get_config(self, channel_identifier: str, channel: Optional[Any] = None) -> ChannelConfig:
        """
        Get configuration for a channel with optional channel-specific overrides.

        Args:
            channel_identifier: Channel identifier (e.g., "telegram", "Internal-BI", "HOSCO-Popak")
            channel: Optional Channel object with configuration overrides

        Returns:
            ChannelConfig with defaults and channel-specific overrides applied
        """
        # If channel provided, build custom config with overrides
        if channel:
            # Start with default config for access type
            config = self.default_configs[channel.access_type].copy()

            # Apply channel-specific overrides
            if channel.rate_limit is not None:
                config.rate_limit = channel.rate_limit

            if channel.max_history is not None:
                config.max_history = channel.max_history

            if channel.default_model is not None:
                config.model = channel.default_model

            if channel.available_models is not None:
                # Parse CSV string to list
                try:
                    config.available_models = [m.strip() for m in channel.available_models.split(",") if m.strip()]
                except (AttributeError, TypeError):
                    # If not valid string, keep default
                    pass

            if channel.allow_model_switch is not None:
                config.allow_model_switch = channel.allow_model_switch

            return config

        # Fallback: determine type by channel identifier (backward compatibility)
        channel_lower = channel_identifier.lower()

        if channel_lower in self.configs:
            return self.configs[channel_lower]

        # Unknown channels default to private config
        return self.default_configs['private']

    def is_private_channel(self, channel_identifier: str) -> bool:
        """Check if channel is private"""
        config = self.get_config(channel_identifier)
        return config.type == PlatformType.PRIVATE

    def can_switch_models(self, channel_identifier: str) -> bool:
        """Check if channel allows model switching"""
        config = self.get_config(channel_identifier)
        return config.allow_model_switch

    def get_available_models(self, channel_identifier: str) -> List[str]:
        """Get available models for channel"""
        config = self.get_config(channel_identifier)
        return config.available_models

    def get_default_model(self, channel_identifier: str) -> str:
        """Get default model for channel"""
        config = self.get_config(channel_identifier)
        return config.model

    def get_rate_limit(self, channel_identifier: str) -> int:
        """Get rate limit for channel"""
        config = self.get_config(channel_identifier)
        return config.rate_limit

    def get_allowed_commands(self, channel_identifier: str) -> List[str]:
        """Get allowed commands for channel"""
        config = self.get_config(channel_identifier)
        return config.commands

    def get_max_history(self, channel_identifier: str) -> int:
        """Get maximum history length for channel"""
        config = self.get_config(channel_identifier)
        return config.max_history

    def requires_auth(self, channel_identifier: str) -> bool:
        """Check if channel requires authentication"""
        config = self.get_config(channel_identifier)
        return config.requires_auth

    def validate_auth(self, channel_identifier: str, token: str) -> bool:
        """Validate authentication for channel"""
        config = self.get_config(channel_identifier)
        if not config.requires_auth:
            return True
        return config.api_key and token == config.api_key

    def is_admin(self, channel_identifier: str, user_id: str) -> bool:
        """Check if user is admin for channel"""
        if channel_identifier == Platform.TELEGRAM:
            return user_id in settings.telegram_admin_users_set
        elif channel_identifier == Platform.INTERNAL:
            return user_id in settings.internal_admin_users_set
        return False

    def is_model_available(self, channel_identifier: str, model: str) -> bool:
        """Check if model is available for channel"""
        available_models = self.get_available_models(channel_identifier)
        return model in available_models

    def get_available_models_friendly(self, channel_identifier: str) -> List[str]:
        """
        Get available models as friendly display names.

        Args:
            channel_identifier: Channel identifier

        Returns:
            List of friendly model names (e.g., ["Gemini 2.0 Flash", "GPT-4o Mini"])
        """
        technical_models = self.get_available_models(channel_identifier)
        return [get_friendly_model_name(m) for m in technical_models]

    def get_default_model_friendly(self, channel_identifier: str) -> str:
        """
        Get default model as friendly display name.

        Args:
            channel_identifier: Channel identifier

        Returns:
            Friendly model name (e.g., "Gemini 2.0 Flash")
        """
        technical = self.get_default_model(channel_identifier)
        return get_friendly_model_name(technical)

    def resolve_model_name(self, model_input: str, channel_identifier: str) -> Optional[str]:
        """
        Convert any model name format (friendly, alias, or technical) to technical ID.
        Validates that the model is available on the specified channel.

        Args:
            model_input: User input - can be friendly name, alias, or technical ID
            channel_identifier: Channel identifier

        Returns:
            Technical model ID if valid and available, None otherwise

        Examples:
            resolve_model_name("Gemini 2.0 Flash", "telegram") -> "google/gemini-2.0-flash-001"
            resolve_model_name("gemini", "telegram") -> "google/gemini-2.5-flash"
            resolve_model_name("google/gemini-2.0-flash-001", "telegram") -> "google/gemini-2.0-flash-001"
        """
        # Normalize input
        model_input = model_input.strip()

        # Check if already technical ID and available
        if self.is_model_available(channel_identifier, model_input):
            return model_input

        # Try as friendly name -> technical
        technical = get_technical_model_name(model_input)
        if self.is_model_available(channel_identifier, technical):
            return technical

        # Try as alias -> friendly -> technical
        from app.core.constants import MODEL_ALIASES, TELEGRAM_MODEL_ALIASES

        aliases = TELEGRAM_MODEL_ALIASES if channel_identifier == "telegram" else MODEL_ALIASES

        model_lower = model_input.lower()
        if model_lower in aliases:
            friendly = aliases[model_lower]
            technical = get_technical_model_name(friendly)
            if self.is_model_available(channel_identifier, technical):
                return technical

        return None


# Global instance
channel_manager = ChannelManager()
