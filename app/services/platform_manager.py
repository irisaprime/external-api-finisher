"""
Platform configuration manager
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.constants import Platform, PlatformType
from app.core.name_mapping import get_friendly_model_name, get_technical_model_name

logger = logging.getLogger(__name__)


class PlatformConfig:
    """Platform configuration"""

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

    def copy(self) -> 'PlatformConfig':
        """Create a copy of this config"""
        return PlatformConfig(
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


class PlatformManager:
    """Manages platform-specific configurations with database-driven overrides"""

    def __init__(self):
        # Default configurations for platform types
        self.default_configs: Dict[str, PlatformConfig] = {}
        # Keep backward compatibility configs
        self.configs: Dict[str, PlatformConfig] = {}
        self._load_configurations()

    def _load_configurations(self):
        """Load default platform type configurations"""

        # Public platform defaults (Telegram, Discord, etc.)
        public_config = PlatformConfig(
            type=PlatformType.PUBLIC,
            model=settings.TELEGRAM_DEFAULT_MODEL,
            available_models=settings.telegram_models_list,
            rate_limit=settings.TELEGRAM_RATE_LIMIT,
            commands=settings.telegram_commands_list,
            allow_model_switch=settings.TELEGRAM_ALLOW_MODEL_SWITCH,
            requires_auth=False,
            max_history=settings.TELEGRAM_MAX_HISTORY,
        )

        # Private platform defaults (Customer integrations)
        private_config = PlatformConfig(
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

        logger.info("Platform configurations loaded successfully")
        logger.info(f"  - Public: {public_config.model} + {len(public_config.available_models)} models")
        logger.info(f"  - Private: {len(private_config.available_models)} models")

    def get_config(self, platform: str, team: Optional[Any] = None) -> PlatformConfig:
        """
        Get configuration for a platform with optional channel-specific overrides.

        Args:
            platform: Platform name (e.g., "telegram", "popak", "avand")
            team: Optional Channel object with configuration overrides (param kept for backward compat)

        Returns:
            PlatformConfig with defaults and channel-specific overrides applied
        """
        # If channel provided, build custom config with overrides
        if team:  # Keep param name 'team' for backward compat
            # Start with default config for access type
            config = self.default_configs[team.access_type].copy()

            # Apply channel-specific overrides
            if team.rate_limit is not None:
                config.rate_limit = team.rate_limit

            if team.max_history is not None:
                config.max_history = team.max_history

            if team.default_model is not None:
                config.model = team.default_model

            if team.available_models is not None:
                # Parse CSV string to list
                try:
                    config.available_models = [m.strip() for m in team.available_models.split(",") if m.strip()]
                except (AttributeError, TypeError):
                    # If not valid string, keep default
                    pass

            if team.allow_model_switch is not None:
                config.allow_model_switch = team.allow_model_switch

            return config

        # Fallback: determine type by platform name (backward compatibility)
        platform_lower = platform.lower()

        if platform_lower in self.configs:
            return self.configs[platform_lower]

        # Unknown platforms default to private config
        return self.default_configs['private']

    def is_private_platform(self, platform: str) -> bool:
        """Check if platform is private"""
        config = self.get_config(platform)
        return config.type == PlatformType.PRIVATE

    def can_switch_models(self, platform: str) -> bool:
        """Check if platform allows model switching"""
        config = self.get_config(platform)
        return config.allow_model_switch

    def get_available_models(self, platform: str) -> List[str]:
        """Get available models for platform"""
        config = self.get_config(platform)
        return config.available_models

    def get_default_model(self, platform: str) -> str:
        """Get default model for platform"""
        config = self.get_config(platform)
        return config.model

    def get_rate_limit(self, platform: str) -> int:
        """Get rate limit for platform"""
        config = self.get_config(platform)
        return config.rate_limit

    def get_allowed_commands(self, platform: str) -> List[str]:
        """Get allowed commands for platform"""
        config = self.get_config(platform)
        return config.commands

    def get_max_history(self, platform: str) -> int:
        """Get maximum history length for platform"""
        config = self.get_config(platform)
        return config.max_history

    def requires_auth(self, platform: str) -> bool:
        """Check if platform requires authentication"""
        config = self.get_config(platform)
        return config.requires_auth

    def validate_auth(self, platform: str, token: str) -> bool:
        """Validate authentication for platform"""
        config = self.get_config(platform)
        if not config.requires_auth:
            return True
        return config.api_key and token == config.api_key

    def is_admin(self, platform: str, user_id: str) -> bool:
        """Check if user is admin for platform"""
        if platform == Platform.TELEGRAM:
            return user_id in settings.telegram_admin_users_set
        elif platform == Platform.INTERNAL:
            return user_id in settings.internal_admin_users_set
        return False

    def is_model_available(self, platform: str, model: str) -> bool:
        """Check if model is available for platform"""
        available_models = self.get_available_models(platform)
        return model in available_models

    def get_available_models_friendly(self, platform: str) -> List[str]:
        """
        Get available models as friendly display names.

        Args:
            platform: Platform name

        Returns:
            List of friendly model names (e.g., ["Gemini 2.0 Flash", "GPT-4o Mini"])
        """
        technical_models = self.get_available_models(platform)
        return [get_friendly_model_name(m) for m in technical_models]

    def get_default_model_friendly(self, platform: str) -> str:
        """
        Get default model as friendly display name.

        Args:
            platform: Platform name

        Returns:
            Friendly model name (e.g., "Gemini 2.0 Flash")
        """
        technical = self.get_default_model(platform)
        return get_friendly_model_name(technical)

    def resolve_model_name(self, model_input: str, platform: str) -> Optional[str]:
        """
        Convert any model name format (friendly, alias, or technical) to technical ID.
        Validates that the model is available on the specified platform.

        Args:
            model_input: User input - can be friendly name, alias, or technical ID
            platform: Platform name

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
        if self.is_model_available(platform, model_input):
            return model_input

        # Try as friendly name -> technical
        technical = get_technical_model_name(model_input)
        if self.is_model_available(platform, technical):
            return technical

        # Try as alias -> friendly -> technical
        from app.core.constants import MODEL_ALIASES, TELEGRAM_MODEL_ALIASES

        aliases = TELEGRAM_MODEL_ALIASES if platform == "telegram" else MODEL_ALIASES

        model_lower = model_input.lower()
        if model_lower in aliases:
            friendly = aliases[model_lower]
            technical = get_technical_model_name(friendly)
            if self.is_model_available(platform, technical):
                return technical

        return None


# Global instance
platform_manager = PlatformManager()