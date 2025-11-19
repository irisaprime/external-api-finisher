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
from app.services.platform_manager import platform_manager

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages chat sessions with platform-aware configuration"""

    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        self.rate_limits: Dict[str, List[float]] = defaultdict(list)

    def get_session_key(self, platform: str, user_id: str, team_id: int | None = None) -> str:
        """
        Generate unique session key with team isolation.

        SECURITY: Includes team_id to prevent session collision between teams.
        If Team A and Team B both use user_id="user123", they get DIFFERENT sessions.

        Format:
        - Telegram (no team): "telegram:user123"
        - Team-based: "Internal-BI:5:user123"
        """
        if team_id is not None:
            return f"{platform}:{team_id}:{user_id}"
        return f"{platform}:{user_id}"

    def get_or_create_session(
        self,
        platform: str,
        user_id: str,
        team_id: int | None = None,
        api_key_id: int | None = None,
        api_key_prefix: str | None = None,
    ) -> ChatSession:
        """
        Get existing session or create new one with platform-specific config and team isolation.

        Architecture:
        - One session per user per platform/team (no conversation_id)
        - Loads total_message_count from database
        - Loads uncleared messages into history for AI context

        SECURITY: API key isolation - each API key can only access sessions it created
        """
        # SECURITY: Include team_id in key to prevent session collision between teams
        key = self.get_session_key(platform, user_id, team_id)

        if key not in self.sessions:
            # Load channel if available (for config overrides)
            channel = None
            if team_id:  # param name kept for backward compat
                db = get_db_session()
                try:
                    from app.models.database import Channel
                    channel = db.query(Channel).filter(Channel.id == team_id).first()
                except Exception as e:
                    logger.error(f"Error loading channel {team_id}: {e}")

            # Get config with channel-specific overrides
            config = platform_manager.get_config(platform, team=channel)  # param name kept for backward compat

            # Load message history from database
            db = get_db_session()
            try:
                # Count total messages for this user (including cleared)
                total_count = (
                    db.query(func.count(Message.id))
                    .filter(
                        Message.platform == platform,
                        Message.user_id == user_id,
                        Message.team_id == team_id if team_id else Message.team_id.is_(None),
                    )
                    .scalar()
                    or 0
                )

                # Load uncleared messages for AI context
                uncleared_messages = (
                    db.query(Message)
                    .filter(
                        Message.platform == platform,
                        Message.user_id == user_id,
                        Message.team_id == team_id if team_id else Message.team_id.is_(None),
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
                platform=platform,
                platform_config=config.dict(),
                user_id=user_id,
                current_model=config.model,
                history=history,  # Pre-loaded from DB
                total_message_count=total_count,  # Total messages including cleared
                is_admin=platform_manager.is_admin(platform, user_id),
                # Team isolation - CRITICAL for security
                team_id=team_id,
                api_key_id=api_key_id,
                api_key_prefix=api_key_prefix,
            )

            friendly_platform = get_friendly_platform_name(platform)
            masked_id = mask_session_id(self.sessions[key].session_id)
            team_info = f" (team: {team_id}, key: {api_key_prefix})" if team_id else ""
            logger.info(
                f"Created session for {friendly_platform} user={user_id} (session: {masked_id}){team_info} "
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

    def get_session(self, platform: str, user_id: str, team_id: int | None = None) -> ChatSession:
        """Get existing session by platform, user_id, and team_id"""
        key = self.get_session_key(platform, user_id, team_id)
        return self.sessions.get(key)

    def get_session_by_id(self, session_id: str) -> ChatSession | None:
        """Get existing session by session_id"""
        for session in self.sessions.values():
            if session.session_id == session_id:
                return session
        return None

    def delete_session(self, platform: str, user_id: str, team_id: int | None = None) -> bool:
        """Delete a session (in-memory only - DB messages remain)"""
        key = self.get_session_key(platform, user_id, team_id)
        if key in self.sessions:
            del self.sessions[key]
            logger.info(f"Deleted session: {key}")
            return True
        return False

    def check_rate_limit(self, platform: str, user_id: str) -> bool:
        """Check if user exceeded rate limit for their platform"""
        now = time.time()
        minute_ago = now - 60
        rate_limit = platform_manager.get_rate_limit(platform)

        key = f"{platform}:{user_id}"

        # Clean old entries
        self.rate_limits[key] = [t for t in self.rate_limits[key] if t > minute_ago]

        # Check limit
        if len(self.rate_limits[key]) >= rate_limit:
            logger.warning(f"Rate limit exceeded for {key}")
            return False

        # Add current request
        self.rate_limits[key].append(now)
        return True

    def get_rate_limit_remaining(self, platform: str, user_id: str) -> int:
        """Get remaining rate limit for user"""
        now = time.time()
        minute_ago = now - 60
        rate_limit = platform_manager.get_rate_limit(platform)

        key = f"{platform}:{user_id}"

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

    def get_all_sessions(self, platform: str = None) -> List[ChatSession]:
        """Get all sessions, optionally filtered by platform"""
        if platform:
            return [session for session in self.sessions.values() if session.platform == platform]
        return list(self.sessions.values())

    def get_session_count(self, platform: str = None) -> int:
        """Get count of sessions"""
        if platform:
            return len([s for s in self.sessions.values() if s.platform == platform])
        return len(self.sessions)

    def get_active_session_count(self, minutes: int = 5) -> int:
        """Get count of recently active sessions"""
        threshold = datetime.utcnow() - timedelta(minutes=minutes)
        return len([s for s in self.sessions.values() if s.last_activity > threshold])

    def get_sessions_by_team(self, team_id: int) -> List[ChatSession]:
        """Get all sessions for a specific team (for team isolation)"""
        return [session for session in self.sessions.values() if session.team_id == team_id]

    def get_session_count_by_team(self, team_id: int) -> int:
        """Get count of sessions for a specific team"""
        return len(self.get_sessions_by_team(team_id))


# Global instance
session_manager = SessionManager()