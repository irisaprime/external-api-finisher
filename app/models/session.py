"""
Chat session model
"""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ChatSession(BaseModel):
    """
    Chat session model with team isolation.

    Architecture:
    - One conversation per user per platform/team (no conversation_id)
    - session_id format: "platform:team_id:user_id" or "platform:user_id"
    - total_message_count tracks ALL messages ever (persists through /clear)
    - history is in-memory cache (resets after /clear, server restart)
    - Actual messages stored in database
    """

    session_id: str
    platform: str
    platform_config: Dict[str, Any]
    user_id: str
    current_model: str
    history: List[Dict[str, str]] = Field(
        default_factory=list
    )  # In-memory cache for AI context
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    total_message_count: int = 0  # Total messages ever (loaded from DB). Excludes commands - only actual chat messages
    is_admin: bool = False

    # Team isolation fields - CRITICAL for security
    team_id: int | None = None  # Team that owns this session
    api_key_id: int | None = None  # API key used to create this session
    api_key_prefix: str | None = None  # For logging/debugging (first 8 chars)

    def add_message(self, role: str, content: str):
        """
        Add message to in-memory history (AI context cache).
        Note: total_message_count is managed separately and loaded from database.
        """
        self.history.append({"role": role, "content": content})
        self.last_activity = datetime.utcnow()

    def clear_history(self):
        """
        Clear in-memory conversation history (for AI context).
        Note: Actual messages remain in database, only AI context is cleared.
        total_message_count is NOT reset (tracks all messages ever).
        """
        self.history.clear()

    def get_recent_history(self, max_messages: int) -> List[Dict[str, str]]:
        """Get recent history up to max_messages"""
        return self.history[-max_messages:] if self.history else []

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()

    def get_uptime_seconds(self) -> float:
        """Get session uptime in seconds"""
        return (datetime.utcnow() - self.created_at).total_seconds()

    def is_expired(self, timeout_minutes: int) -> bool:
        """Check if session is expired"""
        from datetime import timedelta

        timeout = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        return self.last_activity < timeout

    @property
    def current_model_friendly(self) -> str:
        """
        Get current model as friendly display name.

        Returns:
            Friendly model name (e.g., "Gemini 2.0 Flash" instead of "google/gemini-2.0-flash-001")
        """
        from app.core.name_mapping import get_friendly_model_name

        return get_friendly_model_name(self.current_model)
