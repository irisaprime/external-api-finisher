"""
Session Management Tests

Tests for:
- Session creation and management
- Team isolation at session level
- Session key generation
- Session history management
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.session import ChatSession
from app.services.session_manager import SessionManager


@pytest.fixture
def session_manager():
    """Create fresh session manager for each test"""
    # Mock the database to avoid needing a real database in tests
    with patch("app.services.session_manager.get_db_session") as mock_db:
        mock_db.return_value = MagicMock()
        mock_db.return_value.query.return_value.filter.return_value.scalar.return_value = 0
        mock_db.return_value.query.return_value.filter.return_value.all.return_value = []
        yield SessionManager()


class TestSessionCreation:
    """Test session creation"""

    def test_create_session_with_team_id(self, session_manager):
        """Test creating session with team_id"""
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        assert session is not None
        assert session.platform == "internal"
        assert session.user_id == "user1"
        assert session.team_id == 100
        assert session.api_key_id == 1
        assert session.api_key_prefix == "sk_test_"

    def test_create_session_without_team_id(self, session_manager):
        """Test creating session without team_id (Telegram bot)"""
        session = session_manager.get_or_create_session(
            platform="telegram",
            user_id="tg_user1",
            team_id=None,
            api_key_id=None,
            api_key_prefix=None,
        )

        assert session is not None
        assert session.platform == "telegram"
        assert session.team_id is None
        assert session.api_key_id is None


class TestSessionKeyGeneration:
    """Test session key generation for team isolation"""

    def test_session_key_format_with_team(self, session_manager):
        """Test session key format includes team_id"""
        key = session_manager.get_session_key(
            platform="internal", user_id="user123", team_id=100
        )

        assert key == "internal:100:user123"

    def test_session_key_format_without_team(self, session_manager):
        """Test session key format without team_id"""
        key = session_manager.get_session_key(
            platform="telegram", user_id="user123", team_id=None
        )

        assert key == "telegram:user123"

    def test_session_key_collision_prevention(self, session_manager):
        """Test that different teams with same user_id get different keys"""
        key_team_1 = session_manager.get_session_key("internal", "user123", team_id=1)
        key_team_2 = session_manager.get_session_key("internal", "user123", team_id=2)

        assert key_team_1 != key_team_2
        assert key_team_1 == "internal:1:user123"
        assert key_team_2 == "internal:2:user123"


class TestSessionIsolation:
    """Test team isolation at session level"""

    def test_different_teams_cannot_share_sessions(self, session_manager):
        """Test that sessions are isolated by team_id"""
        # Team 1 creates session for user123
        session_team_1 = session_manager.get_or_create_session(
            platform="internal",
            user_id="user123",
            team_id=1,
            api_key_id=10,
            api_key_prefix="sk_team1_",
        )

        # Team 2 creates session for same user123
        session_team_2 = session_manager.get_or_create_session(
            platform="internal",
            user_id="user123",
            team_id=2,
            api_key_id=20,
            api_key_prefix="sk_team2_",
        )

        # Sessions must be different
        assert session_team_1.session_id != session_team_2.session_id
        assert session_team_1.team_id == 1
        assert session_team_2.team_id == 2
        assert session_team_1.api_key_id == 10
        assert session_team_2.api_key_id == 20

    def test_get_sessions_by_team(self, session_manager):
        """Test filtering sessions by team_id"""
        # Create sessions for team 100
        session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_t100_",
        )

        session_manager.get_or_create_session(
            platform="internal",
            user_id="user2",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_t100_",
        )

        # Create session for team 200
        session_manager.get_or_create_session(
            platform="internal",
            user_id="user3",
            team_id=200,
            api_key_id=2,
            api_key_prefix="sk_t200_",
        )

        # Get sessions for team 100
        team_100_sessions = session_manager.get_sessions_by_team(100)
        assert len(team_100_sessions) == 2
        for session in team_100_sessions:
            assert session.team_id == 100

        # Get sessions for team 200
        team_200_sessions = session_manager.get_sessions_by_team(200)
        assert len(team_200_sessions) == 1
        assert team_200_sessions[0].team_id == 200


class TestSessionRetrieval:
    """Test session retrieval"""

    def test_get_existing_session(self, session_manager):
        """Test retrieving existing session"""
        # Create session
        session1 = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        # Retrieve same session (same user, platform, team)
        session2 = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        # Should be the same session
        assert session1.session_id == session2.session_id

    def test_get_session_by_id(self, session_manager):
        """Test getting session by session_id"""
        # Create session
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        # Retrieve by session_id
        retrieved = session_manager.get_session_by_id(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_nonexistent_session(self, session_manager):
        """Test getting session that doesn't exist"""
        retrieved = session_manager.get_session_by_id("nonexistent_session_id")
        assert retrieved is None


class TestSessionDeletion:
    """Test session deletion"""

    def test_delete_session_with_team_id(self, session_manager):
        """Test deleting session with team_id"""
        # Create session
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        # Delete session
        success = session_manager.delete_session(
            platform="internal", user_id="user1", team_id=100
        )

        assert success is True

        # Verify deleted
        retrieved = session_manager.get_session_by_id(session.session_id)
        assert retrieved is None

    def test_delete_session_without_team_id(self, session_manager):
        """Test deleting session without team_id (Telegram)"""
        # Create session
        session_manager.get_or_create_session(
            platform="telegram",
            user_id="tg_user",
            team_id=None,
            api_key_id=None,
            api_key_prefix=None,
        )

        # Delete session
        success = session_manager.delete_session(
            platform="telegram", user_id="tg_user", team_id=None
        )

        assert success is True


class TestSessionHistory:
    """Test session history management"""

    def test_add_message_to_history(self, session_manager):
        """Test adding messages to session history"""
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        # Add user message
        session.add_message("user", "Hello")
        assert len(session.history) == 1
        assert session.history[0]["role"] == "user"
        assert session.history[0]["content"] == "Hello"

        # Add assistant message
        session.add_message("assistant", "Hi there!")
        assert len(session.history) == 2
        assert session.history[1]["role"] == "assistant"
        assert session.history[1]["content"] == "Hi there!"

    def test_history_max_limit(self, session_manager):
        """Test that history respects max_history limit"""
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        # Add more messages than max_history
        for i in range(10):
            session.add_message("user", f"Message {i}")

        # History should be limited when retrieving recent history
        max_history = 5
        history = session.get_recent_history(max_messages=max_history)
        assert len(history) <= max_history

    def test_clear_history(self, session_manager):
        """Test clearing session history"""
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        # Add messages
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi")
        assert len(session.history) == 2

        # Clear history
        session.clear_history()
        assert len(session.history) == 0


class TestSessionExpiration:
    """Test session expiration"""

    def test_session_is_not_expired(self, session_manager):
        """Test that recent session is not expired"""
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        # Recent session should not be expired
        assert session.is_expired(timeout_minutes=30) is False

    def test_session_is_expired(self, session_manager):
        """Test that old session is expired"""
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        # Manually set last_activity to 2 hours ago
        session.last_activity = datetime.utcnow() - timedelta(hours=2)

        # Should be expired with 30 min timeout
        assert session.is_expired(timeout_minutes=30) is True


class TestChatSession:
    """Test ChatSession model"""

    def test_session_model_creation(self):
        """Test creating ChatSession model"""
        session = ChatSession(
            session_id="test_123",
            platform="internal",
            platform_config={"type": "private", "model": "gpt-4"},
            user_id="user1",
            current_model="gpt-4",
            team_id=100,
            api_key_id=1,
            api_key_prefix="sk_test_",
        )

        assert session.session_id == "test_123"
        assert session.platform == "internal"
        assert session.team_id == 100
        assert session.api_key_id == 1

    def test_session_model_without_team(self):
        """Test ChatSession without team (Telegram bot)"""
        session = ChatSession(
            session_id="tg_123",
            platform="telegram",
            platform_config={"type": "private", "model": "gemini-2.0-flash"},
            user_id="tg_user",
            current_model="gemini-2.0-flash",
            team_id=None,
            api_key_id=None,
            api_key_prefix=None,
        )

        assert session.platform == "telegram"
        assert session.team_id is None
        assert session.api_key_id is None

    def test_session_get_uptime_seconds(self):
        """Test getting session uptime in seconds"""
        import time

        session = ChatSession(
            session_id="uptime_test",
            platform="internal",
            platform_config={"type": "private", "model": "gpt-4"},
            user_id="user1",
            current_model="gpt-4",
        )

        # Wait a small amount
        time.sleep(0.1)

        uptime = session.get_uptime_seconds()
        assert uptime >= 0.1
        assert uptime < 1.0  # Should be less than 1 second


class TestRateLimiting:
    """Test rate limiting functionality"""

    def test_check_rate_limit_allows_first_requests(self, session_manager):
        """Test that rate limiting allows initial requests"""
        result = session_manager.check_rate_limit("telegram", "user1")
        assert result is True

        # Should allow multiple requests under limit
        for _ in range(5):
            result = session_manager.check_rate_limit("telegram", "user1")
            assert result is True

    def test_check_rate_limit_blocks_when_exceeded(self, session_manager):
        """Test that rate limiting blocks when limit exceeded"""
        # Telegram has rate limit of 20 per minute
        # Send 20 requests (at limit)
        for _ in range(20):
            result = session_manager.check_rate_limit("telegram", "user1")
            assert result is True

        # 21st request should fail
        result = session_manager.check_rate_limit("telegram", "user1")
        assert result is False

    def test_get_rate_limit_remaining(self, session_manager):
        """Test getting remaining rate limit"""
        # Start with full limit (20 for telegram)
        remaining = session_manager.get_rate_limit_remaining("telegram", "user1")
        assert remaining == 20

        # Use 5 requests
        for _ in range(5):
            session_manager.check_rate_limit("telegram", "user1")

        # Should have 15 remaining
        remaining = session_manager.get_rate_limit_remaining("telegram", "user1")
        assert remaining == 15

    def test_clear_rate_limits_removes_old_entries(self, session_manager):
        """Test that clear_rate_limits removes old entries"""
        # Add some requests
        session_manager.check_rate_limit("telegram", "user1")
        session_manager.check_rate_limit("telegram", "user2")

        # Clear old entries
        session_manager.clear_rate_limits()

        # Rate limits should still exist (not old enough)
        remaining = session_manager.get_rate_limit_remaining("telegram", "user1")
        assert remaining == 19  # 1 request used

    def test_clear_rate_limits_removes_empty_entries(self, session_manager):
        """Test that clear_rate_limits removes empty entries after cleanup (line 228)"""
        import time
        from unittest.mock import patch

        # Add request
        session_manager.check_rate_limit("telegram", "user1")
        assert "telegram:user1" in session_manager.rate_limits

        # Mock time to make entry old (more than 60 seconds ago)
        with patch('app.services.session_manager.time') as mock_time:
            # Current time is 100 seconds in the future
            mock_time.time.return_value = time.time() + 100

            # Clear old entries
            session_manager.clear_rate_limits()

            # Entry should be completely removed from rate_limits dict (line 228 coverage)
            assert "telegram:user1" not in session_manager.rate_limits


class TestSessionCleaning:
    """Test session cleaning functionality"""

    def test_clear_old_sessions(self, session_manager):
        """Test clearing expired sessions"""
        from datetime import datetime, timedelta

        # Create session
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=1,
            api_key_id=1,
            api_key_prefix="ak_test"
        )

        # Manually set last_activity to old time (beyond timeout)
        session.last_activity = datetime.utcnow() - timedelta(hours=2)

        # Clear old sessions
        count = session_manager.clear_old_sessions()

        # Should have cleared 1 session
        assert count == 1

        # Session should be gone
        result = session_manager.get_session("internal", "user1", team_id=1)
        assert result is None

    def test_clear_old_sessions_keeps_active(self, session_manager):
        """Test that clear_old_sessions keeps active sessions"""
        # Create active session
        session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=1,
            api_key_id=1,
            api_key_prefix="ak_test"
        )

        # Clear old sessions
        count = session_manager.clear_old_sessions()

        # Should not have cleared any
        assert count == 0

        # Session should still exist
        result = session_manager.get_session("internal", "user1", team_id=1)
        assert result is not None


class TestSessionQueries:
    """Test session query methods"""

    def test_get_all_sessions(self, session_manager):
        """Test getting all sessions"""
        # Create sessions on different platforms
        session_manager.get_or_create_session(
            platform="telegram", user_id="user1"
        )
        session_manager.get_or_create_session(
            platform="internal", user_id="user2", team_id=1, api_key_id=1, api_key_prefix="ak_test"
        )

        # Get all sessions
        all_sessions = session_manager.get_all_sessions()
        assert len(all_sessions) == 2

    def test_get_all_sessions_filtered_by_platform(self, session_manager):
        """Test getting sessions filtered by platform"""
        # Create sessions on different platforms
        session_manager.get_or_create_session(
            platform="telegram", user_id="user1"
        )
        session_manager.get_or_create_session(
            platform="telegram", user_id="user2"
        )
        session_manager.get_or_create_session(
            platform="internal", user_id="user3", team_id=1, api_key_id=1, api_key_prefix="ak_test"
        )

        # Get telegram sessions only
        telegram_sessions = session_manager.get_all_sessions(platform="telegram")
        assert len(telegram_sessions) == 2

        # Get internal sessions only
        internal_sessions = session_manager.get_all_sessions(platform="internal")
        assert len(internal_sessions) == 1

    def test_get_session_count(self, session_manager):
        """Test getting session count"""
        # Create sessions
        session_manager.get_or_create_session(
            platform="telegram", user_id="user1"
        )
        session_manager.get_or_create_session(
            platform="telegram", user_id="user2"
        )

        count = session_manager.get_session_count()
        assert count == 2

    def test_get_session_count_by_platform(self, session_manager):
        """Test getting session count filtered by platform"""
        # Create sessions on different platforms
        session_manager.get_or_create_session(
            platform="telegram", user_id="user1"
        )
        session_manager.get_or_create_session(
            platform="internal", user_id="user2", team_id=1, api_key_id=1, api_key_prefix="ak_test"
        )

        telegram_count = session_manager.get_session_count(platform="telegram")
        assert telegram_count == 1

        internal_count = session_manager.get_session_count(platform="internal")
        assert internal_count == 1

    def test_get_active_session_count(self, session_manager):
        """Test getting active session count"""
        from datetime import datetime, timedelta

        # Create session
        session = session_manager.get_or_create_session(
            platform="telegram", user_id="user1"
        )

        # Should count as active (just created)
        active_count = session_manager.get_active_session_count(minutes=5)
        assert active_count == 1

        # Make session old
        session.last_activity = datetime.utcnow() - timedelta(minutes=10)

        # Should not count as active
        active_count = session_manager.get_active_session_count(minutes=5)
        assert active_count == 0

    def test_get_session_count_by_team(self, session_manager):
        """Test getting session count for a specific team"""
        # Create sessions for different teams
        session_manager.get_or_create_session(
            platform="internal", user_id="user1", team_id=1, api_key_id=1, api_key_prefix="ak_test"
        )
        session_manager.get_or_create_session(
            platform="internal", user_id="user2", team_id=1, api_key_id=1, api_key_prefix="ak_test"
        )
        session_manager.get_or_create_session(
            platform="internal", user_id="user3", team_id=2, api_key_id=2, api_key_prefix="ak_other"
        )

        # Count for team 1
        team1_count = session_manager.get_session_count_by_team(team_id=1)
        assert team1_count == 2

        # Count for team 2
        team2_count = session_manager.get_session_count_by_team(team_id=2)
        assert team2_count == 1


class TestAPIKeyOwnership:
    """Test API key ownership validation"""

    def test_get_or_create_session_blocks_different_api_key(self, session_manager):
        """Test that different API key cannot access session"""
        # Create session with API key 1
        session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=1,
            api_key_id=1,
            api_key_prefix="ak_first"
        )

        # Try to access with API key 2 - should raise PermissionError
        with pytest.raises(PermissionError) as exc_info:
            session_manager.get_or_create_session(
                platform="internal",
                user_id="user1",
                team_id=1,
                api_key_id=2,
                api_key_prefix="ak_second"
            )

        assert "Access denied" in str(exc_info.value)


class TestDatabaseErrorHandling:
    """Test database error handling"""

    @patch("app.services.session_manager.get_db_session")
    def test_handle_db_error_gracefully(self, mock_db_session, session_manager):
        """Test that DB errors are handled gracefully during session creation"""
        # Mock DB session to raise exception
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Database connection failed")
        mock_db_session.return_value = mock_db

        # Should still create session with empty history
        session = session_manager.get_or_create_session(
            platform="internal",
            user_id="user1",
            team_id=1,
            api_key_id=1,
            api_key_prefix="ak_test"
        )

        assert session is not None
        assert session.total_message_count == 0
        assert len(session.history) == 0


class TestSessionReturnNone:
    """Test cases where methods return None"""

    def test_get_session_returns_none_when_not_found(self, session_manager):
        """Test that get_session returns None for non-existent session"""
        result = session_manager.get_session("internal", "nonexistent_user", team_id=1)
        assert result is None

    def test_delete_session_returns_false_when_not_found(self, session_manager):
        """Test that delete_session returns False for non-existent session"""
        result = session_manager.delete_session("internal", "nonexistent_user", team_id=1)
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
