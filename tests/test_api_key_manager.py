"""
Tests for API Key Manager service
"""

import hashlib
import re
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.database import APIKey, Channel, UsageLog
from app.services.api_key_manager import APIKeyManager


class TestAPIKeyGeneration:
    """Tests for API key generation"""

    def test_generate_api_key_format(self):
        """Test API key generation returns correct format"""
        api_key, key_hash, key_prefix = APIKeyManager.generate_api_key()

        assert api_key.startswith("ark_")
        assert len(api_key) > 40
        assert key_prefix == api_key[:12]
        assert len(key_hash) == 64
        assert re.match(r"^[a-f0-9]{64}$", key_hash)

    def test_generate_api_key_unique(self):
        """Test that generated API keys are unique"""
        key1, hash1, prefix1 = APIKeyManager.generate_api_key()
        key2, hash2, prefix2 = APIKeyManager.generate_api_key()

        assert key1 != key2
        assert hash1 != hash2
        assert prefix1 != prefix2

    def test_hash_key(self):
        """Test hashing an API key"""
        test_key = "ark_testkey12345"
        hashed = APIKeyManager.hash_key(test_key)

        assert len(hashed) == 64
        assert hashed == hashlib.sha256(test_key.encode()).hexdigest()

    def test_hash_key_consistency(self):
        """Test that hashing the same key produces the same hash"""
        test_key = "ark_testkey12345"
        hash1 = APIKeyManager.hash_key(test_key)
        hash2 = APIKeyManager.hash_key(test_key)

        assert hash1 == hash2


class TestChannelManagement:
    """Tests for channel CRUD operations"""

    def test_create_channel_with_key(self, test_db: Session):
        """Test creating a channel with auto-generated API key"""
        channel, api_key_string = APIKeyManager.create_channel_with_key(
            db=test_db,
            channel_id="Internal-Marketing",
            monthly_quota=150000,
            daily_quota=7500,
        )

        assert channel.id is not None
        assert channel.title == "Internal-Marketing"
        assert channel.channel_id == "Internal-Marketing"
        assert channel.monthly_quota == 150000
        assert channel.daily_quota == 7500

        assert api_key_string.startswith("ark_")

        keys = APIKeyManager.list_channel_api_keys(db=test_db, channel_id=channel.id)
        assert len(keys) == 1
        assert keys[0].name == "API Key for Internal-Marketing"
        assert keys[0].created_by == "system"

    def test_get_channel_by_id(self, test_db: Session, test_channel: Channel):
        """Test retrieving a channel by ID"""
        channel = APIKeyManager.get_channel_by_id(db=test_db, channel_id=test_channel.id)

        assert channel is not None
        assert channel.id == test_channel.id
        assert channel.title == test_channel.title

    def test_get_channel_by_id_not_found(self, test_db: Session):
        """Test retrieving non-existent channel returns None"""
        channel = APIKeyManager.get_channel_by_id(db=test_db, channel_id=99999)

        assert channel is None

    def test_get_channel_by_title(self, test_db: Session, test_channel: Channel):
        """Test retrieving a channel by title"""
        channel = APIKeyManager.get_channel_by_title(db=test_db, title=test_channel.title)

        assert channel is not None
        assert channel.id == test_channel.id
        assert channel.title == test_channel.title

    def test_get_channel_by_channel_id(self, test_db: Session):
        """Test retrieving a channel by channel_id"""
        channel, _ = APIKeyManager.create_channel_with_key(
            db=test_db,
            channel_id="Internal-BI",
        )

        found_channel = APIKeyManager.get_channel_by_channel_id(db=test_db, channel_id="Internal-BI")

        assert found_channel is not None
        assert found_channel.id == channel.id
        assert found_channel.channel_id == "Internal-BI"

    def test_list_all_channels(self, test_db: Session):
        """Test listing all channels"""
        channel1, _ = APIKeyManager.create_channel_with_key(db=test_db, channel_id="Channel-1")
        channel2, _ = APIKeyManager.create_channel_with_key(db=test_db, channel_id="Channel-2")

        channels = APIKeyManager.list_all_channels(db=test_db, active_only=False)

        assert len(channels) >= 2
        channel_ids = [c.id for c in channels]
        assert channel1.id in channel_ids
        assert channel2.id in channel_ids

    def test_list_all_channels_active_only(self, test_db: Session):
        """Test listing only active channels"""
        active_channel, _ = APIKeyManager.create_channel_with_key(db=test_db, channel_id="Active-Channel")
        inactive_channel, _ = APIKeyManager.create_channel_with_key(db=test_db, channel_id="Inactive-Channel")
        inactive_channel.is_active = False
        test_db.commit()

        channels = APIKeyManager.list_all_channels(db=test_db, active_only=True)

        channel_ids = [c.id for c in channels]
        assert active_channel.id in channel_ids
        assert inactive_channel.id not in channel_ids

    def test_update_channel(self, test_db: Session, test_channel: Channel):
        """Test updating channel settings"""
        original_title = test_channel.title

        updated_channel = APIKeyManager.update_channel(
            db=test_db,
            channel_id=test_channel.id,
            new_channel_id="Updated-Platform",
            monthly_quota=200000,
            daily_quota=10000,
            is_active=False,
        )

        assert updated_channel is not None
        assert updated_channel.channel_id == "Updated-Platform"
        assert updated_channel.title == original_title  # title should NOT change when updating channel_id
        assert updated_channel.monthly_quota == 200000
        assert updated_channel.daily_quota == 10000
        assert updated_channel.is_active is False

    def test_update_channel_partial(self, test_db: Session, test_channel: Channel):
        """Test updating only some channel fields"""
        original_channel_id = test_channel.channel_id

        updated_channel = APIKeyManager.update_channel(
            db=test_db, channel_id=test_channel.id, monthly_quota=500000
        )

        assert updated_channel is not None
        assert updated_channel.channel_id == original_channel_id
        assert updated_channel.monthly_quota == 500000

    def test_update_channel_without_monthly_quota(self, test_db: Session, test_channel: Channel):
        """Test updating channel without changing monthly_quota"""
        original_monthly = test_channel.monthly_quota

        updated_channel = APIKeyManager.update_channel(
            db=test_db, channel_id=test_channel.id, daily_quota=3000
        )

        assert updated_channel is not None
        assert updated_channel.monthly_quota == original_monthly
        assert updated_channel.daily_quota == 3000

    def test_update_channel_not_found(self, test_db: Session):
        """Test updating non-existent channel returns None"""
        result = APIKeyManager.update_channel(db=test_db, channel_id=99999, monthly_quota=100000)

        assert result is None

    def test_update_channel_id_independent_of_title(self, test_db: Session):
        """Test that updating channel_id doesn't modify the title field

        This test verifies that channel_id and title are independent fields.
        """
        # Create a channel
        channel, _ = APIKeyManager.create_channel_with_key(db=test_db, channel_id="Original-Channel")
        assert channel.title == "Original-Channel"
        assert channel.channel_id == "Original-Channel"

        # Update only the channel_id
        updated_channel = APIKeyManager.update_channel(
            db=test_db, channel_id=channel.id, new_channel_id="Updated-Platform"
        )

        # Verify channel_id changed but title did NOT change
        assert updated_channel is not None
        assert updated_channel.channel_id == "Updated-Platform"
        assert updated_channel.title == "Original-Channel"  # title should remain unchanged

    def test_delete_channel_with_no_keys(self, test_db: Session):
        """Test deleting a channel with no API keys"""
        channel, _ = APIKeyManager.create_channel_with_key(db=test_db, channel_id="Deletable-Channel")
        channel_id = channel.id

        result = APIKeyManager.delete_channel(db=test_db, channel_id=channel_id)

        assert result is True
        assert APIKeyManager.get_channel_by_id(db=test_db, channel_id=channel_id) is None

    def test_delete_channel_with_active_keys(self, test_db: Session, test_channel: Channel):
        """Test deleting a channel with active API keys fails without force"""
        api_key_string, api_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Test Key"
        )

        with pytest.raises(ValueError, match="active API keys"):
            APIKeyManager.delete_channel(db=test_db, channel_id=test_channel.id, force=False)

    def test_delete_channel_with_force(self, test_db: Session):
        """Test force deleting a channel with active keys"""
        channel, _ = APIKeyManager.create_channel_with_key(db=test_db, channel_id="Force-Delete-Channel")
        api_key_string, api_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=channel.id, name="Test Key"
        )

        api_key_id = api_key.id
        channel_id = channel.id

        usage_log = UsageLog(
            channel_id=channel_id,
            api_key_id=api_key_id,
            platform="test",
            session_id="session123",
            model_used="test-model",
            request_count=1,
            tokens_used=30,
            success=True,
        )
        test_db.add(usage_log)
        test_db.commit()

        result = APIKeyManager.delete_channel(db=test_db, channel_id=channel_id, force=True)

        assert result is True
        assert APIKeyManager.get_channel_by_id(db=test_db, channel_id=channel_id) is None
        assert test_db.query(APIKey).filter(APIKey.id == api_key_id).first() is None
        assert test_db.query(UsageLog).filter(UsageLog.channel_id == channel_id).first() is None

    def test_delete_channel_not_found(self, test_db: Session):
        """Test deleting non-existent channel returns False"""
        result = APIKeyManager.delete_channel(db=test_db, channel_id=99999)

        assert result is False


class TestAPIKeyManagement:
    """Tests for API key CRUD operations"""

    def test_create_api_key(self, test_db: Session, test_channel: Channel):
        """Test creating an API key"""
        api_key_string, api_key = APIKeyManager.create_api_key(
            db=test_db,
            channel_id=test_channel.id,
            name="Test Key",
            created_by="admin",
            description="Test Description",
            monthly_quota=50000,
            daily_quota=2500,
        )

        assert api_key_string.startswith("ark_")
        assert api_key.id is not None
        assert api_key.name == "Test Key"
        assert api_key.channel_id == test_channel.id
        assert api_key.created_by == "admin"
        assert api_key.description == "Test Description"
        assert api_key.monthly_quota == 50000
        assert api_key.daily_quota == 2500
        assert api_key.is_active is True
        assert api_key.expires_at is None

    def test_create_api_key_with_expiration(self, test_db: Session, test_channel: Channel):
        """Test creating an API key with expiration"""
        api_key_string, api_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Expiring Key", expires_in_days=30
        )

        assert api_key.expires_at is not None
        expected_expiry = datetime.utcnow() + timedelta(days=30)
        assert abs((api_key.expires_at - expected_expiry).total_seconds()) < 5

    def test_validate_api_key_success(self, test_db: Session, test_channel: Channel):
        """Test validating a valid API key"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Valid Key"
        )

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key is not None
        assert validated_key.id == created_key.id
        assert validated_key.last_used_at is not None

    def test_validate_api_key_invalid(self, test_db: Session):
        """Test validating an invalid API key returns None"""
        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key="ark_invalid_key_12345")

        assert validated_key is None

    def test_validate_api_key_inactive(self, test_db: Session, test_channel: Channel):
        """Test validating an inactive API key returns None"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Inactive Key"
        )

        created_key.is_active = False
        test_db.commit()

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key is None

    def test_validate_api_key_expired(self, test_db: Session, test_channel: Channel):
        """Test validating an expired API key returns None"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Expired Key"
        )

        created_key.expires_at = datetime.utcnow() - timedelta(days=1)
        test_db.commit()

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key is None

    def test_validate_api_key_inactive_channel(self, test_db: Session, test_channel: Channel):
        """Test validating an API key from inactive channel returns None"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Channel Inactive Key"
        )

        test_channel.is_active = False
        test_db.commit()

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key is None

    def test_revoke_api_key(self, test_db: Session, test_channel: Channel):
        """Test revoking an API key"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Revoke Test Key"
        )

        result = APIKeyManager.revoke_api_key(db=test_db, key_id=created_key.id)

        assert result is True

        test_db.refresh(created_key)
        assert created_key.is_active is False

    def test_revoke_api_key_not_found(self, test_db: Session):
        """Test revoking non-existent API key returns False"""
        result = APIKeyManager.revoke_api_key(db=test_db, key_id=99999)

        assert result is False

    def test_delete_api_key(self, test_db: Session, test_channel: Channel):
        """Test permanently deleting an API key"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Delete Test Key"
        )
        key_id = created_key.id

        result = APIKeyManager.delete_api_key(db=test_db, key_id=key_id)

        assert result is True
        assert test_db.query(APIKey).filter(APIKey.id == key_id).first() is None

    def test_delete_api_key_not_found(self, test_db: Session):
        """Test deleting non-existent API key returns False"""
        result = APIKeyManager.delete_api_key(db=test_db, key_id=99999)

        assert result is False

    def test_list_channel_api_keys(self, test_db: Session, test_channel: Channel):
        """Test listing all API keys for a channel"""
        api_key1_string, api_key1 = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Key 1"
        )
        api_key2_string, api_key2 = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Key 2"
        )

        keys = APIKeyManager.list_channel_api_keys(db=test_db, channel_id=test_channel.id)

        assert len(keys) >= 2
        key_ids = [k.id for k in keys]
        assert api_key1.id in key_ids
        assert api_key2.id in key_ids

    def test_list_channel_api_keys_empty(self, test_db: Session):
        """Test listing API keys for channel with no keys"""
        new_channel, _ = APIKeyManager.create_channel_with_key(db=test_db, channel_id="Empty-Channel")
        # Delete the auto-created key
        keys = APIKeyManager.list_channel_api_keys(db=test_db, channel_id=new_channel.id)
        for key in keys:
            APIKeyManager.delete_api_key(db=test_db, key_id=key.id)

        keys = APIKeyManager.list_channel_api_keys(db=test_db, channel_id=new_channel.id)

        assert len(keys) == 0


class TestAPIKeyValidation:
    """Tests for API key validation edge cases"""

    def test_validate_updates_last_used_at(self, test_db: Session, test_channel: Channel):
        """Test that validation updates last_used_at timestamp"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Timestamp Test Key"
        )

        original_last_used = created_key.last_used_at

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key.last_used_at is not None
        if original_last_used is not None:
            assert validated_key.last_used_at >= original_last_used

    def test_hash_consistency_with_generated_key(self, test_db: Session, test_channel: Channel):
        """Test that hash validation works with generated keys"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, channel_id=test_channel.id, name="Hash Test Key"
        )

        manual_hash = APIKeyManager.hash_key(api_key_string)
        assert manual_hash == created_key.key_hash
