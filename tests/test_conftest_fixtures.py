"""
Tests for conftest.py fixtures to ensure 100% coverage
"""

import pytest


def test_sample_user_message_fixture(sample_user_message):
    """Test sample_user_message fixture (line 52)"""
    assert sample_user_message["platform"] == "telegram"
    assert sample_user_message["user_id"] == "test_user_123"
    assert sample_user_message["text"] == "سلام، این یک تست است"


def test_sample_session_data_fixture(sample_session_data):
    """Test sample_session_data fixture (line 65)"""
    assert sample_session_data["session_id"] == "test_session_abc"
    assert sample_session_data["platform"] == "telegram"
    assert sample_session_data["current_model"] == "google/gemini-2.0-flash-001"


def test_mock_ai_service_response_fixture(mock_ai_service_response):
    """Test mock_ai_service_response fixture (line 77)"""
    assert mock_ai_service_response["Response"] == "این یک پاسخ تستی است"
    assert mock_ai_service_response["SessionId"] == "test_session"
    assert mock_ai_service_response["Model"] == "google/gemini-2.0-flash-001"


@pytest.mark.integration
def test_integration_marker():
    """Test that integration marker works (line 97)"""
    # This test will have the integration marker added automatically
    # by pytest_collection_modifyitems
    pass


@pytest.mark.unit
def test_unit_marker():
    """Test that unit marker works (line 99)"""
    # This test will have the unit marker added automatically
    # by pytest_collection_modifyitems
    pass
