"""
Tests for API Key Manager service
"""

import hashlib
import re
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.database import APIKey, Team, UsageLog
from app.services.api_key_manager import APIKeyManager


class TestAPIKeyGeneration:
    """Tests for API key generation"""

    def test_generate_api_key_format(self):
        """Test API key generation returns correct format"""
        api_key, key_hash, key_prefix = APIKeyManager.generate_api_key()

        assert api_key.startswith("ak_")
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
        test_key = "ak_testkey12345"
        hashed = APIKeyManager.hash_key(test_key)

        assert len(hashed) == 64
        assert hashed == hashlib.sha256(test_key.encode()).hexdigest()

    def test_hash_key_consistency(self):
        """Test that hashing the same key produces the same hash"""
        test_key = "ak_testkey12345"
        hash1 = APIKeyManager.hash_key(test_key)
        hash2 = APIKeyManager.hash_key(test_key)

        assert hash1 == hash2


class TestTeamManagement:
    """Tests for team CRUD operations"""

    def test_create_team(self, test_db: Session):
        """Test creating a team"""
        team = APIKeyManager.create_team(
            db=test_db,
            name="Test Team",
            monthly_quota=100000,
            daily_quota=5000,
        )

        assert team.id is not None
        assert team.display_name == "Test Team"
        assert team.monthly_quota == 100000
        assert team.daily_quota == 5000
        assert team.is_active is True

    def test_create_team_minimal(self, test_db: Session):
        """Test creating a team with minimal parameters"""
        team = APIKeyManager.create_team(db=test_db, name="Minimal Team")

        assert team.id is not None
        assert team.display_name == "Minimal Team"
        assert team.monthly_quota is None
        assert team.daily_quota is None
        assert team.is_active is True

    def test_get_team_by_id(self, test_db: Session, test_team: Team):
        """Test retrieving a team by ID"""
        team = APIKeyManager.get_team_by_id(db=test_db, team_id=test_team.id)

        assert team is not None
        assert team.id == test_team.id
        assert team.display_name == test_team.display_name

    def test_get_team_by_id_not_found(self, test_db: Session):
        """Test retrieving non-existent team returns None"""
        team = APIKeyManager.get_team_by_id(db=test_db, team_id=99999)

        assert team is None

    def test_get_team_by_name(self, test_db: Session, test_team: Team):
        """Test retrieving a team by name"""
        team = APIKeyManager.get_team_by_name(db=test_db, name=test_team.display_name)

        assert team is not None
        assert team.id == test_team.id
        assert team.display_name == test_team.display_name

    def test_get_team_by_platform_name(self, test_db: Session):
        """Test retrieving a team by platform name"""
        team = APIKeyManager.create_team(
            db=test_db,
            name="Internal-BI",
        )
        team.platform_name = "Internal-BI"
        test_db.commit()

        found_team = APIKeyManager.get_team_by_platform_name(db=test_db, platform_name="Internal-BI")

        assert found_team is not None
        assert found_team.id == team.id
        assert found_team.platform_name == "Internal-BI"

    def test_list_all_teams(self, test_db: Session):
        """Test listing all teams"""
        team1 = APIKeyManager.create_team(db=test_db, name="Team 1")
        team2 = APIKeyManager.create_team(db=test_db, name="Team 2")

        teams = APIKeyManager.list_all_teams(db=test_db, active_only=False)

        assert len(teams) >= 2
        team_ids = [t.id for t in teams]
        assert team1.id in team_ids
        assert team2.id in team_ids

    def test_list_all_teams_active_only(self, test_db: Session):
        """Test listing only active teams"""
        active_team = APIKeyManager.create_team(db=test_db, name="Active Team")
        inactive_team = APIKeyManager.create_team(db=test_db, name="Inactive Team")
        inactive_team.is_active = False
        test_db.commit()

        teams = APIKeyManager.list_all_teams(db=test_db, active_only=True)

        team_ids = [t.id for t in teams]
        assert active_team.id in team_ids
        assert inactive_team.id not in team_ids

    def test_update_team(self, test_db: Session, test_team: Team):
        """Test updating team settings"""
        original_display_name = test_team.display_name

        updated_team = APIKeyManager.update_team(
            db=test_db,
            team_id=test_team.id,
            platform_name="Updated-Platform",
            monthly_quota=200000,
            daily_quota=10000,
            is_active=False,
        )

        assert updated_team is not None
        assert updated_team.platform_name == "Updated-Platform"
        assert updated_team.display_name == original_display_name  # display_name should NOT change when updating platform_name
        assert updated_team.monthly_quota == 200000
        assert updated_team.daily_quota == 10000
        assert updated_team.is_active is False

    def test_update_team_partial(self, test_db: Session, test_team: Team):
        """Test updating only some team fields"""
        original_platform = test_team.platform_name

        updated_team = APIKeyManager.update_team(
            db=test_db, team_id=test_team.id, monthly_quota=500000
        )

        assert updated_team is not None
        assert updated_team.platform_name == original_platform
        assert updated_team.monthly_quota == 500000

    def test_update_team_without_monthly_quota(self, test_db: Session, test_team: Team):
        """Test updating team without changing monthly_quota (line 406 branch)"""
        original_monthly = test_team.monthly_quota

        updated_team = APIKeyManager.update_team(
            db=test_db, team_id=test_team.id, daily_quota=3000
        )

        assert updated_team is not None
        assert updated_team.monthly_quota == original_monthly
        assert updated_team.daily_quota == 3000

    def test_update_team_not_found(self, test_db: Session):
        """Test updating non-existent team returns None"""
        result = APIKeyManager.update_team(db=test_db, team_id=99999, monthly_quota=100000)

        assert result is None

    def test_update_team_platform_name_independent_of_name(self, test_db: Session):
        """Test that updating platform_name doesn't modify the name field (bug fix test)

        This test verifies the fix for the bug where updating platform_name would
        incorrectly sync the name field, causing unique constraint violations.
        """
        # Create a team - initially name and platform_name are the same
        team = APIKeyManager.create_team(db=test_db, name="Original-Team")
        assert team.display_name == "Original-Team"
        assert team.platform_name == "Original-Team"

        # Update only the platform_name
        updated_team = APIKeyManager.update_team(
            db=test_db, team_id=team.id, platform_name="Updated-Platform"
        )

        # Verify platform_name changed but name did NOT change
        assert updated_team is not None
        assert updated_team.platform_name == "Updated-Platform"
        assert updated_team.display_name == "Original-Team"  # display_name should remain unchanged

    def test_delete_team_with_no_keys(self, test_db: Session):
        """Test deleting a team with no API keys"""
        team = APIKeyManager.create_team(db=test_db, name="Deletable Team")
        team_id = team.id

        result = APIKeyManager.delete_team(db=test_db, team_id=team_id)

        assert result is True
        assert APIKeyManager.get_team_by_id(db=test_db, team_id=team_id) is None

    def test_delete_team_with_active_keys(self, test_db: Session, test_team: Team):
        """Test deleting a team with active API keys fails without force"""
        api_key_string, api_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Test Key"
        )

        with pytest.raises(ValueError, match="active API keys"):
            APIKeyManager.delete_team(db=test_db, team_id=test_team.id, force=False)

    def test_delete_team_with_force(self, test_db: Session):
        """Test force deleting a team with active keys"""
        team = APIKeyManager.create_team(db=test_db, name="Force Delete Team")
        api_key_string, api_key = APIKeyManager.create_api_key(
            db=test_db, team_id=team.id, name="Test Key"
        )

        api_key_id = api_key.id
        team_id = team.id

        usage_log = UsageLog(
            team_id=team_id,
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

        result = APIKeyManager.delete_team(db=test_db, team_id=team_id, force=True)

        assert result is True
        assert APIKeyManager.get_team_by_id(db=test_db, team_id=team_id) is None
        assert test_db.query(APIKey).filter(APIKey.id == api_key_id).first() is None
        assert test_db.query(UsageLog).filter(UsageLog.team_id == team_id).first() is None

    def test_delete_team_not_found(self, test_db: Session):
        """Test deleting non-existent team returns False"""
        result = APIKeyManager.delete_team(db=test_db, team_id=99999)

        assert result is False

    def test_create_team_with_key(self, test_db: Session):
        """Test creating a team with auto-generated API key"""
        team, api_key_string = APIKeyManager.create_team_with_key(
            db=test_db,
            platform_name="Internal-Marketing",
            monthly_quota=150000,
            daily_quota=7500,
        )

        assert team.id is not None
        assert team.display_name == "Internal-Marketing"
        assert team.platform_name == "Internal-Marketing"
        assert team.monthly_quota == 150000
        assert team.daily_quota == 7500

        assert api_key_string.startswith("ak_")

        keys = APIKeyManager.list_team_api_keys(db=test_db, team_id=team.id)
        assert len(keys) == 1
        assert keys[0].name == "API Key for Internal-Marketing"
        assert keys[0].created_by == "system"


class TestAPIKeyManagement:
    """Tests for API key CRUD operations"""

    def test_create_api_key(self, test_db: Session, test_team: Team):
        """Test creating an API key"""
        api_key_string, api_key = APIKeyManager.create_api_key(
            db=test_db,
            team_id=test_team.id,
            name="Test Key",
            created_by="admin",
            description="Test Description",
            monthly_quota=50000,
            daily_quota=2500,
        )

        assert api_key_string.startswith("ak_")
        assert api_key.id is not None
        assert api_key.name == "Test Key"
        assert api_key.team_id == test_team.id
        assert api_key.created_by == "admin"
        assert api_key.description == "Test Description"
        assert api_key.monthly_quota == 50000
        assert api_key.daily_quota == 2500
        assert api_key.is_active is True
        assert api_key.expires_at is None

    def test_create_api_key_with_expiration(self, test_db: Session, test_team: Team):
        """Test creating an API key with expiration"""
        api_key_string, api_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Expiring Key", expires_in_days=30
        )

        assert api_key.expires_at is not None
        expected_expiry = datetime.utcnow() + timedelta(days=30)
        assert abs((api_key.expires_at - expected_expiry).total_seconds()) < 5

    def test_validate_api_key_success(self, test_db: Session, test_team: Team):
        """Test validating a valid API key"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Valid Key"
        )

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key is not None
        assert validated_key.id == created_key.id
        assert validated_key.last_used_at is not None

    def test_validate_api_key_invalid(self, test_db: Session):
        """Test validating an invalid API key returns None"""
        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key="ak_invalid_key_12345")

        assert validated_key is None

    def test_validate_api_key_inactive(self, test_db: Session, test_team: Team):
        """Test validating an inactive API key returns None"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Inactive Key"
        )

        created_key.is_active = False
        test_db.commit()

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key is None

    def test_validate_api_key_expired(self, test_db: Session, test_team: Team):
        """Test validating an expired API key returns None"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Expired Key"
        )

        created_key.expires_at = datetime.utcnow() - timedelta(days=1)
        test_db.commit()

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key is None

    def test_validate_api_key_inactive_team(self, test_db: Session, test_team: Team):
        """Test validating an API key from inactive team returns None"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Team Inactive Key"
        )

        test_team.is_active = False
        test_db.commit()

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key is None

    def test_revoke_api_key(self, test_db: Session, test_team: Team):
        """Test revoking an API key"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Revoke Test Key"
        )

        result = APIKeyManager.revoke_api_key(db=test_db, key_id=created_key.id)

        assert result is True

        test_db.refresh(created_key)
        assert created_key.is_active is False

    def test_revoke_api_key_not_found(self, test_db: Session):
        """Test revoking non-existent API key returns False"""
        result = APIKeyManager.revoke_api_key(db=test_db, key_id=99999)

        assert result is False

    def test_delete_api_key(self, test_db: Session, test_team: Team):
        """Test permanently deleting an API key"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Delete Test Key"
        )
        key_id = created_key.id

        result = APIKeyManager.delete_api_key(db=test_db, key_id=key_id)

        assert result is True
        assert test_db.query(APIKey).filter(APIKey.id == key_id).first() is None

    def test_delete_api_key_not_found(self, test_db: Session):
        """Test deleting non-existent API key returns False"""
        result = APIKeyManager.delete_api_key(db=test_db, key_id=99999)

        assert result is False

    def test_list_team_api_keys(self, test_db: Session, test_team: Team):
        """Test listing all API keys for a team"""
        api_key1_string, api_key1 = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Key 1"
        )
        api_key2_string, api_key2 = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Key 2"
        )

        keys = APIKeyManager.list_team_api_keys(db=test_db, team_id=test_team.id)

        assert len(keys) >= 2
        key_ids = [k.id for k in keys]
        assert api_key1.id in key_ids
        assert api_key2.id in key_ids

    def test_list_team_api_keys_empty(self, test_db: Session, test_team: Team):
        """Test listing API keys for team with no keys"""
        new_team = APIKeyManager.create_team(db=test_db, name="Empty Team")

        keys = APIKeyManager.list_team_api_keys(db=test_db, team_id=new_team.id)

        assert len(keys) == 0


class TestAPIKeyValidation:
    """Tests for API key validation edge cases"""

    def test_validate_updates_last_used_at(self, test_db: Session, test_team: Team):
        """Test that validation updates last_used_at timestamp"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Timestamp Test Key"
        )

        original_last_used = created_key.last_used_at

        validated_key = APIKeyManager.validate_api_key(db=test_db, api_key=api_key_string)

        assert validated_key.last_used_at is not None
        if original_last_used is not None:
            assert validated_key.last_used_at >= original_last_used

    def test_hash_consistency_with_generated_key(self, test_db: Session, test_team: Team):
        """Test that hash validation works with generated keys"""
        api_key_string, created_key = APIKeyManager.create_api_key(
            db=test_db, team_id=test_team.id, name="Hash Test Key"
        )

        manual_hash = APIKeyManager.hash_key(api_key_string)
        assert manual_hash == created_key.key_hash
