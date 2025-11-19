"""
Tests for name mapping utilities
"""

import pytest

from app.core.name_mapping import (
    get_friendly_model_name,
    get_friendly_platform_name,
    get_technical_model_name,
    mask_session_id,
)


class TestFriendlyModelName:
    """Tests for get_friendly_model_name"""

    def test_get_friendly_model_name_known(self):
        """Test getting friendly name for known model"""
        result = get_friendly_model_name("google/gemini-2.0-flash-001")
        assert result == "Gemini 2.0 Flash"

    def test_get_friendly_model_name_unknown(self):
        """Test getting friendly name for unknown model returns formatted"""
        result = get_friendly_model_name("unknown/model")
        # The function extracts the last part and capitalizes it
        assert result == "Model"


class TestTechnicalModelName:
    """Tests for get_technical_model_name"""

    def test_get_technical_model_name_known(self):
        """Test getting technical name for known model"""
        result = get_technical_model_name("Gemini 2.0 Flash")
        assert result == "google/gemini-2.0-flash-001"

    def test_get_technical_model_name_unknown(self):
        """Test getting technical name for unknown model returns input"""
        result = get_technical_model_name("Unknown Model")
        assert result == "Unknown Model"


class TestFriendlyPlatformName:
    """Tests for get_friendly_platform_name"""

    def test_get_friendly_platform_name_telegram(self):
        """Test getting friendly platform name for telegram"""
        result = get_friendly_platform_name("telegram")
        assert result == "public-platform"

    def test_get_friendly_platform_name_internal(self):
        """Test getting friendly platform name for internal"""
        result = get_friendly_platform_name("internal")
        assert result == "private-platform"

    def test_get_friendly_platform_name_unknown(self):
        """Test getting friendly platform name for unknown platform"""
        result = get_friendly_platform_name("unknown_platform")
        assert result == "unknown-platform"


class TestMaskSessionId:
    """Tests for mask_session_id"""

    def test_mask_session_id_long(self):
        """Test masking long session ID"""
        session_id = "a1b2c3d4e5f6g7h8i9j0"
        result = mask_session_id(session_id)
        assert result == "a1b2c3d4..."
        assert len(result) == 11  # 8 chars + "..."

    def test_mask_session_id_short(self):
        """Test masking short session ID (not masked)"""
        session_id = "short"
        result = mask_session_id(session_id)
        assert result == "short"

    def test_mask_session_id_exact_length(self):
        """Test masking session ID with exact show_chars length"""
        session_id = "12345678"
        result = mask_session_id(session_id, show_chars=8)
        assert result == "12345678"

    def test_mask_session_id_custom_show_chars(self):
        """Test masking with custom show_chars"""
        session_id = "abcdefghijklmnop"
        result = mask_session_id(session_id, show_chars=4)
        assert result == "abcd..."
        assert len(result) == 7  # 4 chars + "..."

    def test_mask_session_id_empty(self):
        """Test masking empty session ID"""
        result = mask_session_id("")
        assert result == ""
