"""
API Key Management Service
Handles creation, validation, and management of API keys for channel-based access control.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.database import APIKey, Channel, UsageLog

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manages API keys for channel-based access control"""

    @staticmethod
    def generate_api_key() -> Tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            Tuple of (api_key, key_hash, key_prefix)
            - api_key: Full API key to give to user (show only once)
            - key_hash: SHA256 hash to store in database
            - key_prefix: First 8 characters for identification
        """
        # Generate a secure random key (32 bytes = 64 hex characters)
        api_key = f"ak_{secrets.token_urlsafe(32)}"

        # Create SHA256 hash for storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Extract prefix for identification
        key_prefix = api_key[:12]  # "ak_" + first 8 chars

        return api_key, key_hash, key_prefix

    @staticmethod
    def hash_key(api_key: str) -> str:
        """
        Hash an API key for comparison.

        Args:
            api_key: The API key to hash

        Returns:
            SHA256 hash of the key
        """
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def create_api_key(
        db: Session,
        channel_id: int,
        name: str,
        created_by: Optional[str] = None,
        description: Optional[str] = None,
        monthly_quota: Optional[int] = None,
        daily_quota: Optional[int] = None,
        expires_in_days: Optional[int] = None,
    ) -> Tuple[str, APIKey]:
        """
        Create a new API key for a channel.

        NOTE: This creates API keys for channels only (chat service access).
        Super admin authentication is handled separately via SUPER_ADMIN_API_KEYS environment variable.

        Args:
            db: Database session
            channel_id: Channel ID
            name: Friendly name for the key
            created_by: User who created the key
            description: Description of the key
            monthly_quota: Monthly quota override (None = use channel quota)
            daily_quota: Daily quota override (None = use channel quota)
            expires_in_days: Days until expiration (None = never expires)

        Returns:
            Tuple of (api_key_string, api_key_object)
            - api_key_string: Full API key (show only once to user)
            - api_key_object: Database object
        """
        # Generate the key
        api_key_string, key_hash, key_prefix = APIKeyManager.generate_api_key()

        # Calculate expiration date
        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create database record
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            channel_id=channel_id,
            monthly_quota=monthly_quota,
            daily_quota=daily_quota,
            created_by=created_by,
            description=description,
            expires_at=expires_at,
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        logger.info(f"Created API key: {name} (prefix: {key_prefix}) for channel ID {channel_id}")

        return api_key_string, api_key

    @staticmethod
    def validate_api_key(db: Session, api_key: str) -> Optional[APIKey]:
        """
        Validate an API key and return the key object if valid.

        Args:
            db: Database session
            api_key: API key to validate

        Returns:
            APIKey object if valid, None otherwise
        """
        key_hash = APIKeyManager.hash_key(api_key)

        # Find the key
        db_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

        if not db_key:
            logger.warning(f"Invalid API key attempted (hash: {key_hash[:16]}...)")
            return None

        # Check if key is active
        if not db_key.is_active:
            logger.warning(f"Inactive API key attempted (prefix: {db_key.key_prefix})")
            return None

        # Check if key has expired
        if db_key.is_expired:
            logger.warning(f"Expired API key attempted (prefix: {db_key.key_prefix})")
            return None

        # Check if channel is active
        if not db_key.channel.is_active:
            logger.warning(
                f"API key from inactive channel attempted (prefix: {db_key.key_prefix}, channel: {db_key.channel.title})"
            )
            return None

        # Update last used timestamp
        db_key.last_used_at = datetime.utcnow()
        db.commit()

        logger.debug(f"API key validated (prefix: {db_key.key_prefix}, channel: {db_key.channel.title})")
        return db_key

    @staticmethod
    def revoke_api_key(db: Session, key_id: int) -> bool:
        """
        Revoke (deactivate) an API key.

        Args:
            db: Database session
            key_id: API key ID

        Returns:
            True if revoked, False if not found
        """
        db_key = db.query(APIKey).filter(APIKey.id == key_id).first()

        if not db_key:
            return False

        db_key.is_active = False
        db.commit()

        logger.info(f"Revoked API key (prefix: {db_key.key_prefix})")
        return True

    @staticmethod
    def delete_api_key(db: Session, key_id: int) -> bool:
        """
        Permanently delete an API key.

        Args:
            db: Database session
            key_id: API key ID

        Returns:
            True if deleted, False if not found
        """
        db_key = db.query(APIKey).filter(APIKey.id == key_id).first()

        if not db_key:
            return False

        key_prefix = db_key.key_prefix
        db.delete(db_key)
        db.commit()

        logger.info(f"Deleted API key (prefix: {key_prefix})")
        return True

    @staticmethod
    def list_channel_api_keys(db: Session, channel_id: int) -> List[APIKey]:
        """
        List all API keys for a channel.

        Args:
            db: Database session
            channel_id: Channel ID

        Returns:
            List of API keys
        """
        return db.query(APIKey).filter(APIKey.channel_id == channel_id).all()

    @staticmethod
    def get_channel_by_id(db: Session, channel_id: int) -> Optional[Channel]:
        """
        Get channel by ID.

        Args:
            db: Database session
            channel_id: Channel ID

        Returns:
            Channel object if found, None otherwise
        """
        return db.query(Channel).filter(Channel.id == channel_id).first()

    @staticmethod
    def get_channel_by_channel_id(db: Session, channel_id_str: str) -> Optional[Channel]:
        """
        Get channel by channel_id (technical identifier).

        Args:
            db: Database session
            channel_id_str: Channel identifier (e.g., "telegram", "popak", "avand")

        Returns:
            Channel object if found, None otherwise
        """
        return db.query(Channel).filter(Channel.channel_id == channel_id_str).first()

    @staticmethod
    def get_channel_by_title(db: Session, title: str) -> Optional[Channel]:
        """
        Get channel by human-friendly title.

        Args:
            db: Database session
            title: Channel title

        Returns:
            Channel object if found, None otherwise
        """
        return db.query(Channel).filter(Channel.title == title).first()

    @staticmethod
    def create_channel_with_key(
        db: Session,
        channel_id: str,
        monthly_quota: Optional[int] = None,
        daily_quota: Optional[int] = None,
        title: Optional[str] = None,
        access_type: str = "private",
        rate_limit: Optional[int] = None,
        max_history: Optional[int] = None,
        default_model: Optional[str] = None,
        available_models: Optional[List[str]] = None,
        allow_model_switch: Optional[bool] = None,
    ) -> Tuple[Channel, str]:
        """
        Create a new channel with auto-generated API key (one key per channel).

        Args:
            db: Database session
            channel_id: System identifier for routing (e.g., "telegram", "popak", "avand")
            monthly_quota: Monthly request quota (None = unlimited)
            daily_quota: Daily request quota (None = unlimited)
            title: Human-friendly display name (defaults to channel_id if not provided)
            access_type: 'public' or 'private' (default: 'private')
            rate_limit: Override default rate limit (None = use access_type default)
            max_history: Override max conversation history (None = use access_type default)
            default_model: Override default AI model (None = use access_type default)
            available_models: Override available models list (None = use access_type default)
            allow_model_switch: Override model switch permission (None = use access_type default)

        Returns:
            Tuple of (channel, api_key_string)
            - channel: Created channel object
            - api_key_string: Full API key (show only once to user)
        """
        # Create channel with configuration
        channel = Channel(
            title=title or channel_id,  # Default to channel_id if not provided
            channel_id=channel_id,
            access_type=access_type,
            monthly_quota=monthly_quota,
            daily_quota=daily_quota,
            # Channel config overrides (NULL = use defaults)
            rate_limit=rate_limit,
            max_history=max_history,
            default_model=default_model,
            available_models=",".join(available_models) if available_models else None,  # Store as CSV
            allow_model_switch=allow_model_switch,
        )
        db.add(channel)
        db.flush()  # Flush to get channel.id before creating key

        # Auto-generate API key for this channel
        api_key_string, key_hash, key_prefix = APIKeyManager.generate_api_key()

        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=f"API Key for {channel_id}",  # Auto-generated name
            channel_id=channel.id,
            monthly_quota=None,  # Use channel quotas
            daily_quota=None,  # Use channel quotas
            created_by="system",  # Auto-created by system
            description=f"Auto-generated key for {channel_id}",
        )
        db.add(api_key)
        db.commit()
        db.refresh(channel)

        logger.info(
            f"Created channel '{channel_id}' (ID: {channel.id}, type: {access_type}) with auto-generated API key (prefix: {key_prefix})"
        )

        return channel, api_key_string

    @staticmethod
    def list_all_channels(db: Session, active_only: bool = True) -> List[Channel]:
        """
        List all channels.

        Args:
            db: Database session
            active_only: Only return active channels

        Returns:
            List of channels
        """
        query = db.query(Channel)
        if active_only:
            query = query.filter(Channel.is_active)
        return query.all()

    @staticmethod
    def update_channel(
        db: Session,
        channel_id: int,
        title: Optional[str] = None,
        channel_id_str: Optional[str] = None,
        access_type: Optional[str] = None,
        monthly_quota: Optional[int] = None,
        daily_quota: Optional[int] = None,
        is_active: Optional[bool] = None,
        rate_limit: Optional[int] = None,
        max_history: Optional[int] = None,
        default_model: Optional[str] = None,
        available_models: Optional[List[str]] = None,
        allow_model_switch: Optional[bool] = None,
    ) -> Optional[Channel]:
        """
        Update channel settings.

        Args:
            db: Database session
            channel_id: Channel ID (integer primary key)
            title: New human-friendly display name
            channel_id_str: New channel identifier
            access_type: New access type ('public' or 'private')
            monthly_quota: New monthly quota
            daily_quota: New daily quota
            is_active: Active status
            rate_limit: Override rate limit (None = keep existing)
            max_history: Override max history (None = keep existing)
            default_model: Override default model (None = keep existing)
            available_models: Override available models (None = keep existing)
            allow_model_switch: Override model switch permission (None = keep existing)

        Returns:
            Updated channel if found, None otherwise
        """
        channel = db.query(Channel).filter(Channel.id == channel_id).first()

        if not channel:
            return None

        if title is not None:
            channel.title = title
        if channel_id_str is not None:
            channel.channel_id = channel_id_str
        if access_type is not None:
            channel.access_type = access_type
        if monthly_quota is not None:
            channel.monthly_quota = monthly_quota
        if daily_quota is not None:
            channel.daily_quota = daily_quota
        if is_active is not None:
            channel.is_active = is_active

        # Channel configuration overrides
        if rate_limit is not None:
            channel.rate_limit = rate_limit
        if max_history is not None:
            channel.max_history = max_history
        if default_model is not None:
            channel.default_model = default_model
        if available_models is not None:
            channel.available_models = ",".join(available_models) if available_models else None
        if allow_model_switch is not None:
            channel.allow_model_switch = allow_model_switch

        channel.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(channel)

        logger.info(
            f"Updated channel: {channel.title} / {channel.channel_id} (ID: {channel.id}, type: {channel.access_type})"
        )
        return channel

    @staticmethod
    def delete_channel(db: Session, channel_id: int, force: bool = False) -> bool:
        """
        Delete a channel. By default, only deletes if no active API keys exist.

        Args:
            db: Database session
            channel_id: Channel ID to delete
            force: If True, delete channel and all associated API keys and usage logs

        Returns:
            True if deleted, False if not found or has active keys
        """
        channel = db.query(Channel).filter(Channel.id == channel_id).first()

        if not channel:
            logger.warning(f"Channel not found for deletion: ID {channel_id}")
            return False

        # Check for active API keys
        active_keys = db.query(APIKey).filter(APIKey.channel_id == channel_id, APIKey.is_active).count()

        if active_keys > 0 and not force:
            logger.warning(
                f"Cannot delete channel {channel.title}: has {active_keys} active API keys. Use force=True to delete anyway."
            )
            raise ValueError(
                f"Channel has {active_keys} active API keys. Revoke them first or use --force flag."
            )

        channel_name = channel.title

        # If force, delete all associated API keys and usage logs
        if force:
            # Delete usage logs first (foreign key dependency)
            deleted_logs = db.query(UsageLog).filter(UsageLog.channel_id == channel_id).delete()

            # Delete API keys
            deleted_keys = db.query(APIKey).filter(APIKey.channel_id == channel_id).delete()

            logger.info(
                f"Force deleting channel {channel_name}: removed {deleted_keys} keys and {deleted_logs} usage logs"
            )

        # Delete the channel
        db.delete(channel)
        db.commit()

        logger.info(f"Deleted channel: {channel_name} (ID: {channel_id})")
        return True
