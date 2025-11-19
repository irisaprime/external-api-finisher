"""
Pytest configuration and shared fixtures
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import Base, Team


@pytest.fixture(scope="function")
def test_db():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def test_team(test_db: Session):
    """Create a test team"""
    team = Team(
        display_name="Test Team",
        platform_name="Test-Platform",
        monthly_quota=100000,
        daily_quota=5000,
        is_active=True,
    )
    test_db.add(team)
    test_db.commit()
    test_db.refresh(team)
    return team


@pytest.fixture
def sample_user_message():
    """Sample user message for testing"""
    return {
        "platform": "telegram",
        "user_id": "test_user_123",
        "conversation_id": "test_chat_456",
        "message_id": "test_msg_789",
        "text": "سلام، این یک تست است",
        "type": "text",
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing"""
    return {
        "session_id": "test_session_abc",
        "platform": "telegram",
        "user_id": "test_user_123",
        "conversation_id": "test_chat_456",
        "current_model": "google/gemini-2.0-flash-001",
    }


@pytest.fixture
def mock_ai_service_response():
    """Mock AI service API response"""
    return {
        "Response": "این یک پاسخ تستی است",
        "SessionId": "test_session",
        "Model": "google/gemini-2.0-flash-001",
    }


def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "ai_service: marks tests that require AI service")


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    # Add markers automatically based on test location
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        if "unit" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        if "ai_service" in item.nodeid:
            item.add_marker(pytest.mark.ai_service)
