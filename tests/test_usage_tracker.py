"""
Tests for usage tracking service

Tests usage logging, quota checking, and usage statistics:
- Usage log creation
- Quota enforcement (daily and monthly)
- Team and API key usage statistics
- Recent usage retrieval
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

from app.models.database import APIKey, Team, UsageLog
from app.services.usage_tracker import UsageTracker


@pytest.fixture
def mock_db():
    """Mock database session"""
    return MagicMock()


@pytest.fixture
def mock_team():
    """Mock team object"""
    team = Mock(spec=Team)
    team.id = 1
    team.display_name = "Test Team"
    team.platform_name = "test_platform"
    team.daily_quota = 1000
    team.monthly_quota = 20000
    team.is_active = True
    return team


@pytest.fixture
def mock_api_key(mock_team):
    """Mock API key object"""
    key = Mock(spec=APIKey)
    key.id = 1
    key.key_prefix = "sk_test_"
    key.team_id = mock_team.id
    key.team = mock_team
    key.daily_quota = None  # Use team quota
    key.monthly_quota = None  # Use team quota
    key.is_active = True
    return key


@pytest.fixture
def mock_api_key_with_quota(mock_team):
    """Mock API key with custom quota"""
    key = Mock(spec=APIKey)
    key.id = 2
    key.key_prefix = "sk_custom_"
    key.team_id = mock_team.id
    key.team = mock_team
    key.daily_quota = 500  # Custom daily quota
    key.monthly_quota = 10000  # Custom monthly quota
    key.is_active = True
    return key


class TestLogUsage:
    """Tests for usage logging"""

    @patch("app.services.usage_tracker.get_friendly_model_name")
    def test_log_usage_success(self, mock_get_friendly, mock_db):
        """Test logging successful API usage"""
        mock_get_friendly.return_value = "GPT-4.1"

        result = UsageTracker.log_usage(
            db=mock_db,
            api_key_id=1,
            team_id=100,
            session_id="session_abc123",
            platform="telegram",
            model_used="openai/gpt-4.1",
            success=True,
            response_time_ms=250,
            tokens_used=150,
            estimated_cost=0.005,
        )

        # Verify database calls
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        # Verify usage log created
        added_log = mock_db.add.call_args[0][0]
        assert isinstance(added_log, UsageLog)
        assert added_log.api_key_id == 1
        assert added_log.team_id == 100
        assert added_log.session_id == "session_abc123"
        assert added_log.platform == "telegram"
        assert added_log.model_used == "GPT-4.1"  # Friendly name
        assert added_log.success is True
        assert added_log.response_time_ms == 250
        assert added_log.tokens_used == 150
        assert added_log.estimated_cost == 0.005
        assert added_log.error_message is None

    @patch("app.services.usage_tracker.get_friendly_model_name")
    def test_log_usage_failure(self, mock_get_friendly, mock_db):
        """Test logging failed API usage"""
        mock_get_friendly.return_value = "Claude Sonnet 4"

        result = UsageTracker.log_usage(
            db=mock_db,
            api_key_id=2,
            team_id=101,
            session_id="session_xyz789",
            platform="internal",
            model_used="anthropic/claude-sonnet-4-5",
            success=False,
            error_message="Rate limit exceeded",
        )

        # Verify usage log created with error
        added_log = mock_db.add.call_args[0][0]
        assert added_log.success is False
        assert added_log.error_message == "Rate limit exceeded"
        assert added_log.tokens_used is None
        assert added_log.response_time_ms is None

    @patch("app.services.usage_tracker.get_friendly_model_name")
    def test_log_usage_minimal_data(self, mock_get_friendly, mock_db):
        """Test logging with minimal required data"""
        mock_get_friendly.return_value = "Gemini 2.0 Flash"

        result = UsageTracker.log_usage(
            db=mock_db,
            api_key_id=3,
            team_id=102,
            session_id="session_min",
            platform="telegram",
            model_used="google/gemini-2.0-flash-001",
            success=True,
        )

        # Verify optional fields are None
        added_log = mock_db.add.call_args[0][0]
        assert added_log.response_time_ms is None
        assert added_log.tokens_used is None
        assert added_log.estimated_cost is None
        assert added_log.error_message is None


class TestCheckQuota:
    """Tests for quota checking"""

    def test_check_daily_quota_unlimited(self, mock_db, mock_team):
        """Test daily quota when unlimited"""
        # Team has no daily quota
        mock_team.daily_quota = None

        api_key = Mock(spec=APIKey)
        api_key.daily_quota = None
        api_key.team = mock_team

        result = UsageTracker.check_quota(mock_db, api_key, period="daily")

        assert result["allowed"] is True
        assert result["current_usage"] == 0
        assert result["quota_limit"] is None
        assert result["quota_source"] == "unlimited"
        assert result["reset_time"] is None

    def test_check_daily_quota_allowed(self, mock_db, mock_api_key):
        """Test daily quota when under limit"""
        # Mock current usage count
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 500  # 500 requests today

        result = UsageTracker.check_quota(mock_db, mock_api_key, period="daily")

        assert result["allowed"] is True
        assert result["current_usage"] == 500
        assert result["quota_limit"] == 1000  # Team quota
        assert result["quota_source"] == "team"
        assert result["reset_time"] is not None

    def test_check_daily_quota_exceeded(self, mock_db, mock_api_key):
        """Test daily quota when exceeded"""
        # Mock current usage count
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 1000  # At limit

        result = UsageTracker.check_quota(mock_db, mock_api_key, period="daily")

        assert result["allowed"] is False
        assert result["current_usage"] == 1000
        assert result["quota_limit"] == 1000

    def test_check_daily_quota_custom_key_quota(self, mock_db, mock_api_key_with_quota):
        """Test daily quota using custom API key quota"""
        # Mock current usage count
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 100

        result = UsageTracker.check_quota(mock_db, mock_api_key_with_quota, period="daily")

        assert result["allowed"] is True
        assert result["current_usage"] == 100
        assert result["quota_limit"] == 500  # API key quota, not team quota
        assert result["quota_source"] == "api_key"

    def test_check_monthly_quota_allowed(self, mock_db, mock_api_key):
        """Test monthly quota when under limit"""
        # Mock current usage count
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 10000  # 10k requests this month

        result = UsageTracker.check_quota(mock_db, mock_api_key, period="monthly")

        assert result["allowed"] is True
        assert result["current_usage"] == 10000
        assert result["quota_limit"] == 20000  # Team quota
        assert result["quota_source"] == "team"

    def test_check_monthly_quota_exceeded(self, mock_db, mock_api_key):
        """Test monthly quota when exceeded"""
        # Mock current usage count
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 20000  # At limit

        result = UsageTracker.check_quota(mock_db, mock_api_key, period="monthly")

        assert result["allowed"] is False
        assert result["current_usage"] == 20000
        assert result["quota_limit"] == 20000

    @patch("app.services.usage_tracker.datetime")
    def test_check_monthly_quota_december_year_rollover(self, mock_datetime, mock_db, mock_api_key):
        """Test monthly quota reset time calculation in December (year rollover)"""
        # Mock datetime to return December
        december_date = datetime(2024, 12, 15, 10, 30, 0)
        mock_datetime.utcnow.return_value = december_date
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # Mock current usage count
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 5000

        result = UsageTracker.check_quota(mock_db, mock_api_key, period="monthly")

        assert result["allowed"] is True
        assert result["current_usage"] == 5000
        # Verify reset_time is in January of next year
        assert result["reset_time"] is not None
        reset_time_str = result["reset_time"].isoformat() if hasattr(result["reset_time"], 'isoformat') else str(result["reset_time"])
        assert "2025-01" in reset_time_str

    def test_check_quota_invalid_period(self, mock_db, mock_api_key):
        """Test invalid period raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            UsageTracker.check_quota(mock_db, mock_api_key, period="yearly")

        assert "Invalid period" in str(exc_info.value)
        assert "yearly" in str(exc_info.value)


class TestTeamUsageStats:
    """Tests for team usage statistics"""

    def test_get_team_usage_stats_basic(self, mock_db):
        """Test getting basic team usage stats"""
        # Mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 100  # Default value for counts

        # Mock model usage query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [("GPT-4.1", 50), ("Claude Sonnet 4", 30)]

        result = UsageTracker.get_team_usage_stats(mock_db, team_id=1)

        assert result["team_id"] == 1
        assert "period" in result
        assert "requests" in result
        assert "tokens" in result
        assert "cost" in result
        assert "performance" in result
        assert "models" in result

    def test_get_team_usage_stats_with_dates(self, mock_db):
        """Test getting team stats with custom date range"""
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 31)

        # Mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 50
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = UsageTracker.get_team_usage_stats(
            mock_db, team_id=1, start_date=start_date, end_date=end_date
        )

        assert result["period"]["start"] == start_date.isoformat()
        assert result["period"]["end"] == end_date.isoformat()

    def test_get_team_usage_stats_success_rate(self, mock_db):
        """Test success rate calculation"""
        # Mock query to return different values for total and successful requests
        call_count = 0

        def mock_scalar_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 100  # Total requests
            elif call_count == 2:
                return 80  # Successful requests
            else:
                return 0  # Other queries

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.side_effect = mock_scalar_side_effect
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = UsageTracker.get_team_usage_stats(mock_db, team_id=1)

        assert result["requests"]["total"] == 100
        assert result["requests"]["successful"] == 80
        assert result["requests"]["failed"] == 20
        assert result["requests"]["success_rate"] == 80.0

    def test_get_team_usage_stats_zero_requests(self, mock_db):
        """Test stats with zero requests"""
        # Mock query to return 0 for all counts
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = UsageTracker.get_team_usage_stats(mock_db, team_id=1)

        assert result["requests"]["total"] == 0
        assert result["requests"]["successful"] == 0
        assert result["requests"]["failed"] == 0
        assert result["requests"]["success_rate"] == 0
        assert result["tokens"]["average_per_request"] == 0
        assert result["cost"]["average_per_request"] == 0


class TestAPIKeyUsageStats:
    """Tests for API key usage statistics"""

    def test_get_api_key_usage_stats(self, mock_db):
        """Test getting API key usage stats"""
        # Mock query chain
        call_count = 0

        def mock_scalar_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 50  # Total requests
            elif call_count == 2:
                return 45  # Successful requests
            else:
                return 0

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.side_effect = mock_scalar_side_effect

        result = UsageTracker.get_api_key_usage_stats(mock_db, api_key_id=1)

        assert result["api_key_id"] == 1
        assert "period" in result
        assert result["requests"]["total"] == 50
        assert result["requests"]["successful"] == 45
        assert result["requests"]["failed"] == 5

    def test_get_api_key_usage_stats_with_dates(self, mock_db):
        """Test API key stats with custom date range"""
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 15)

        # Mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 10

        result = UsageTracker.get_api_key_usage_stats(
            mock_db, api_key_id=1, start_date=start_date, end_date=end_date
        )

        assert result["period"]["start"] == start_date.isoformat()
        assert result["period"]["end"] == end_date.isoformat()


class TestRecentUsage:
    """Tests for recent usage retrieval"""

    def test_get_recent_usage_all(self, mock_db):
        """Test getting recent usage for all teams"""
        # Mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = UsageTracker.get_recent_usage(mock_db)

        # Verify query was not filtered by team
        mock_query.filter.assert_not_called()
        mock_query.limit.assert_called_once_with(100)

    def test_get_recent_usage_filtered_by_team(self, mock_db):
        """Test getting recent usage filtered by team"""
        # Mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = UsageTracker.get_recent_usage(mock_db, team_id=1)

        # Verify query was filtered by team
        mock_query.filter.assert_called_once()
        mock_query.limit.assert_called_once_with(100)

    def test_get_recent_usage_custom_limit(self, mock_db):
        """Test getting recent usage with custom limit"""
        # Mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = UsageTracker.get_recent_usage(mock_db, limit=50)

        # Verify custom limit was used
        mock_query.limit.assert_called_once_with(50)

    def test_get_recent_usage_with_results(self, mock_db):
        """Test getting recent usage with actual results"""
        # Create mock usage logs
        mock_logs = [
            Mock(spec=UsageLog, id=1, api_key_id=1, team_id=1, model_used="GPT-4.1"),
            Mock(spec=UsageLog, id=2, api_key_id=1, team_id=1, model_used="Claude Sonnet 4"),
            Mock(spec=UsageLog, id=3, api_key_id=2, team_id=2, model_used="Gemini 2.0 Flash"),
        ]

        # Mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_logs

        result = UsageTracker.get_recent_usage(mock_db, limit=10)

        assert len(result) == 3
        assert result[0].id == 1
        assert result[1].id == 2
        assert result[2].id == 3
