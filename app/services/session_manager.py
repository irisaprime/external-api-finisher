"""
Session manager with rate limiting and database-backed message persistence
"""

import hashlib
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import func

from app.core.config import settings
from app.core.name_mapping import get_friendly_platform_name, mask_session_id
from app.models.database import Message, get_db_session
from app.models.session import ChatSession
from app.services.channel_manager import channel_manager

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages chat sessions with channel-aware configuration"""

    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        self.rate_limits: Dict[str, List[float]] = defaultdict(list)

    def get_session_key(self, channel_identifier: str, user_id: str, channel_id: int | None = None) -> str:
        """
        Generate unique session key with channel isolation.

        SECURITY: Includes channel_id to prevent session collision between channels.
        If Channel A and Channel B both use user_id="user123", they get DIFFERENT sessions.

        Format:
        - Telegram (no channel): "telegram:user123"
        - Channel-based: "Internal-BI:5:user123"
        """
        if channel_id is not None:
            return f"{channel_identifier}:{channel_id}:{user_id}"
        return f"{channel_identifier}:{user_id}"

    def get_or_create_session(
        self,
        channel_identifier: str,
        user_id: str,
        channel_id: int | None = None,
        api_key_id: int | None = None,
        api_key_prefix: str | None = None,
    ) -> ChatSession:
        """
        Get existing session or create new one with channel-specific config and channel isolation.

        Architecture:
        - One session per user per channel (no conversation_id)
        - Loads total_message_count from database
        - Loads uncleared messages into history for AI context

        SECURITY: API key isolation - each API key can only access sessions it created
        """
        # SECURITY: Include channel_id in key to prevent session collision between channels
        key = self.get_session_key(channel_identifier, user_id, channel_id)

        if key not in self.sessions:
            # Load channel if available (for config overrides)
            channel = None
            if channel_id:
                db = get_db_session()
                try:
                    from app.models.database import Channel
                    channel = db.query(Channel).filter(Channel.id == channel_id).first()
                except Exception as e:
                    logger.error(f"Error loading channel {channel_id}: {e}")

            # Get config with channel-specific overrides
            config = channel_manager.get_config(channel_identifier, channel=channel)

            # Load message history from database
            db = get_db_session()
            try:
                # Count total messages for this user (including cleared)
                total_count = (
                    db.query(func.count(Message.id))
                    .filter(
                        Message.channel_identifier == channel_identifier,
                        Message.user_id == user_id,
                        Message.channel_id == channel_id if channel_id else Message.channel_id.is_(None),
                    )
                    .scalar()
                    or 0
                )

                # Load uncleared messages for AI context
                uncleared_messages = (
                    db.query(Message)
                    .filter(
                        Message.channel_identifier == channel_identifier,
                        Message.user_id == user_id,
                        Message.channel_id == channel_id if channel_id else Message.channel_id.is_(None),
                        Message.cleared_at.is_(None),  # Only uncleared messages
                    )
                    .order_by(Message.created_at)
                    .all()
                )

                # Build history from DB messages
                history = [{"role": msg.role, "content": msg.content} for msg in uncleared_messages]

            except Exception as e:
                logger.error(f"Error loading message history from DB: {e}")
                total_count = 0
                history = []

            self.sessions[key] = ChatSession(
                session_id=hashlib.md5(key.encode()).hexdigest(),
                channel_identifier=channel_identifier,
                channel_config=config.dict(),
                user_id=user_id,
                current_model=config.model,
                history=history,  # Pre-loaded from DB
                total_message_count=total_count,  # Total messages including cleared
                is_admin=channel_manager.is_admin(channel_identifier, user_id),
                # Channel isolation - CRITICAL for security
                channel_id=channel_id,
                api_key_id=api_key_id,
                api_key_prefix=api_key_prefix,
            )

            friendly_platform = get_friendly_platform_name(channel_identifier)
            masked_id = mask_session_id(self.sessions[key].session_id)
            channel_info = f" (channel: {channel_id}, key: {api_key_prefix})" if channel_id else ""
            logger.info(
                f"Created session for {friendly_platform} user={user_id} (session: {masked_id}){channel_info} "
                f"with {total_count} total messages ({len(history)} in context)"
            )
        else:
            # Existing session found - verify API key ownership
            existing_session = self.sessions[key]

            # SECURITY: API key isolation - verify this API key owns this session
            if api_key_id is not None and existing_session.api_key_id != api_key_id:
                logger.warning(
                    f"[SECURITY] API key {api_key_prefix} attempted to access user_id={user_id} "
                    f"owned by API key ID {existing_session.api_key_id}"
                )
                raise PermissionError(
                    "Access denied. This user's conversation belongs to a different API key."
                )

            # Update last activity
            existing_session.update_activity()

        return self.sessions[key]

    def get_session(self, channel_identifier: str, user_id: str, channel_id: int | None = None) -> ChatSession:
        """Get existing session by channel_identifier, user_id, and channel_id"""
        key = self.get_session_key(channel_identifier, user_id, channel_id)
        return self.sessions.get(key)

    def get_session_by_id(self, session_id: str) -> ChatSession | None:
        """Get existing session by session_id"""
        for session in self.sessions.values():
            if session.session_id == session_id:
                return session
        return None

    def delete_session(self, channel_identifier: str, user_id: str, channel_id: int | None = None) -> bool:
        """Delete a session (in-memory only - DB messages remain)"""
        key = self.get_session_key(channel_identifier, user_id, channel_id)
        if key in self.sessions:
            del self.sessions[key]
            logger.info(f"Deleted session: {key}")
            return True
        return False

    def check_rate_limit(self, channel_identifier: str, user_id: str) -> bool:
        """Check if user exceeded rate limit for their channel"""
        now = time.time()
        minute_ago = now - 60
        rate_limit = channel_manager.get_rate_limit(channel_identifier)

        key = f"{channel_identifier}:{user_id}"

        # Clean old entries
        self.rate_limits[key] = [t for t in self.rate_limits[key] if t > minute_ago]

        # Check limit
        if len(self.rate_limits[key]) >= rate_limit:
            logger.warning(f"Rate limit exceeded for {key}")
            return False

        # Add current request
        self.rate_limits[key].append(now)
        return True

    def get_rate_limit_remaining(self, channel_identifier: str, user_id: str) -> int:
        """Get remaining rate limit for user"""
        now = time.time()
        minute_ago = now - 60
        rate_limit = channel_manager.get_rate_limit(channel_identifier)

        key = f"{channel_identifier}:{user_id}"

        # Clean old entries
        self.rate_limits[key] = [t for t in self.rate_limits[key] if t > minute_ago]

        return max(0, rate_limit - len(self.rate_limits[key]))

    def clear_old_sessions(self):
        """Clear expired sessions"""
        timeout_minutes = settings.SESSION_TIMEOUT_MINUTES
        timeout = datetime.utcnow() - timedelta(minutes=timeout_minutes)

        keys_to_remove = [
            key for key, session in self.sessions.items() if session.last_activity < timeout
        ]

        for key in keys_to_remove:
            del self.sessions[key]

        if keys_to_remove:
            logger.info(f"Cleaned {len(keys_to_remove)} expired sessions")

        return len(keys_to_remove)

    def clear_rate_limits(self):
        """Clear old rate limit entries"""
        now = time.time()
        minute_ago = now - 60

        for key in list(self.rate_limits.keys()):
            self.rate_limits[key] = [t for t in self.rate_limits[key] if t > minute_ago]

            # Remove empty entries
            if not self.rate_limits[key]:
                del self.rate_limits[key]

    def get_all_sessions(self, channel_identifier: str = None) -> List[ChatSession]:
        """Get all sessions, optionally filtered by channel"""
        if channel_identifier:
            return [session for session in self.sessions.values() if session.channel_identifier == channel_identifier]
        return list(self.sessions.values())

    def get_session_count(self, channel_identifier: str = None) -> int:
        """Get count of sessions"""
        if channel_identifier:
            return len([s for s in self.sessions.values() if s.channel_identifier == channel_identifier])
        return len(self.sessions)

    def get_active_session_count(self, minutes: int = 5) -> int:
        """Get count of recently active sessions"""
        threshold = datetime.utcnow() - timedelta(minutes=minutes)
        return len([s for s in self.sessions.values() if s.last_activity > threshold])

    def get_sessions_by_channel(self, channel_id: int) -> List[ChatSession]:
        """Get all sessions for a specific channel (for channel isolation)"""
        return [session for session in self.sessions.values() if session.channel_id == channel_id]

    def get_session_count_by_channel(self, channel_id: int) -> int:
        """Get count of sessions for a specific channel"""
        return len(self.get_sessions_by_channel(channel_id))


# Global instance
session_manager = SessionManager()