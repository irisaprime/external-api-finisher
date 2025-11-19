#!/usr/bin/env python3
"""
CLI tool for managing teams and API keys
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import argparse
from datetime import datetime
from tabulate import tabulate

from app.models.database import get_database
from app.services.api_key_manager import APIKeyManager
from app.services.usage_tracker import UsageTracker


def init_database():
    """Initialize the database"""
    print("Initializing database...")
    db_instance = get_database()
    db_instance.create_tables()
    print("[OK] Database initialized successfully")


def create_team(name: str, daily_quota: int = None, monthly_quota: int = None):
    """Create a new team"""
    db = get_database()
    session = next(db.get_session())

    try:
        team = APIKeyManager.create_team(
            db=session,
            name=name,
            daily_quota=daily_quota,
            monthly_quota=monthly_quota,
        )
        print(f"[OK] Team created successfully!")
        print(f"  ID: {team.id}")
        print(f"  Display Name: {team.display_name}")
        print(f"  Platform: {team.platform_name}")
        print(f"  Daily Quota: {team.daily_quota or 'Unlimited'}")
        print(f"  Monthly Quota: {team.monthly_quota or 'Unlimited'}")
    except Exception as e:
        print(f"[ERROR] Error creating team: {e}")
        sys.exit(1)


def list_teams():
    """List all teams"""
    db = get_database()
    session = next(db.get_session())

    teams = APIKeyManager.list_all_teams(session, active_only=False)

    if not teams:
        print("No teams found")
        return

    table_data = []
    for team in teams:
        table_data.append([
            team.id,
            team.display_name,
            team.platform_name,
            team.daily_quota or "unlimited",
            team.monthly_quota or "unlimited",
            "active" if team.is_active else "inactive",
            team.created_at.strftime("%Y-%m-%d"),
        ])

    headers = ["ID", "Display Name", "Platform", "Daily Quota", "Monthly Quota", "Active", "Created"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))


def delete_team(team_id: int, force: bool = False):
    """Delete a team"""
    db = get_database()
    session = next(db.get_session())

    try:
        # Get team name before deletion
        team = APIKeyManager.get_team_by_id(session, team_id)
        if not team:
            print(f"[ERROR] Team with ID {team_id} not found")
            sys.exit(1)

        team_name = team.display_name

        # Confirm deletion
        if not force:
            response = input(f"Are you sure you want to delete team '{team_name}' (ID: {team_id})? [y/N]: ")
            if response.lower() != 'y':
                print("Deletion cancelled")
                return

        success = APIKeyManager.delete_team(session, team_id, force=force)

        if success:
            print(f"[OK] Team '{team_name}' deleted successfully (ID: {team_id})")
        else:
            print(f"[ERROR] Failed to delete team")
            sys.exit(1)

    except ValueError as e:
        print(f"[ERROR] {e}")
        print("\nUse --force to delete team along with all API keys and usage logs")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error deleting team: {e}")
        sys.exit(1)


def create_api_key(
    team_id: int,
    name: str,
    description: str = None,
    expires_in_days: int = None,
):
    """
    Create a new API key for external teams (clients)

    TWO-PATH AUTHENTICATION:
    - This creates API keys for EXTERNAL TEAMS (clients using chat service)
    - Super admin access is via SUPER_ADMIN_API_KEYS environment variable (NOT database)

    All database API keys have EQUAL access:
    - Can access: /api/v1/chat endpoint only
    - Cannot access: /api/v1/admin/* endpoints (super admin only)

    For super admin access, set SUPER_ADMIN_API_KEYS in environment:
    export SUPER_ADMIN_API_KEYS="your_secret_key_1,your_secret_key_2"
    """
    db = get_database()
    session = next(db.get_session())

    try:
        # Verify team exists
        team = APIKeyManager.get_team_by_id(session, team_id)
        if not team:
            print(f"[ERROR] Team with ID {team_id} not found")
            sys.exit(1)

        api_key_string, api_key_obj = APIKeyManager.create_api_key(
            db=session,
            team_id=team_id,
            name=name,
            description=description,
            expires_in_days=expires_in_days,
            created_by="cli-script",
        )

        print("[OK] Team API Key created successfully!")
        print()
        print("=" * 60)
        print("IMPORTANT: Save this API key securely!")
        print("It will not be shown again.")
        print("=" * 60)
        print()
        print(f"API Key: {api_key_string}")
        print()
        print("=" * 60)
        print()
        print(f"  Key Prefix: {api_key_obj.key_prefix}")
        print(f"  Name: {api_key_obj.name}")
        print(f"  Team: {team.display_name} (ID: {team_id})")
        print(f"  Expires: {api_key_obj.expires_at or 'Never'}")
        print()
        print("  ℹ️  ACCESS: /api/v1/chat endpoint only (external team)")
        print("  ℹ️  Cannot access /api/v1/admin/* endpoints")
        print()
        print("  NOTE: Super admin access is via SUPER_ADMIN_API_KEYS environment variable")

    except Exception as e:
        print(f"[ERROR] Error creating API key: {e}")
        sys.exit(1)


def list_api_keys(team_id: int = None):
    """List API keys"""
    db = get_database()
    session = next(db.get_session())

    if team_id:
        keys = APIKeyManager.list_team_api_keys(session, team_id)
    else:
        # List all teams and their keys
        teams = APIKeyManager.list_all_teams(session)
        keys = []
        for team in teams:
            keys.extend(APIKeyManager.list_team_api_keys(session, team.id))

    if not keys:
        print("No API keys found")
        return

    table_data = []
    for key in keys:
        table_data.append([
            key.id,
            key.key_prefix,
            key.name,
            key.team.display_name,
            "active" if key.is_active else "inactive",
            key.last_used_at.strftime("%Y-%m-%d %H:%M") if key.last_used_at else "Never",
            key.expires_at.strftime("%Y-%m-%d") if key.expires_at else "Never",
        ])

    headers = ["ID", "Prefix", "Name", "Team", "Active", "Last Used", "Expires"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print()
    print("NOTE: All database API keys are for external teams (chat service only)")
    print("      Super admin access is via SUPER_ADMIN_API_KEYS environment variable")


def revoke_api_key(key_id: int, permanent: bool = False):
    """Revoke or delete an API key"""
    db = get_database()
    session = next(db.get_session())

    try:
        if permanent:
            success = APIKeyManager.delete_api_key(session, key_id)
            action = "deleted"
        else:
            success = APIKeyManager.revoke_api_key(session, key_id)
            action = "revoked"

        if success:
            print(f"[OK] API key {action} successfully (ID: {key_id})")
        else:
            print(f"[ERROR] API key not found (ID: {key_id})")
            sys.exit(1)

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        sys.exit(1)


def show_usage(team_id: int = None, api_key_id: int = None, days: int = 30):
    """Show usage statistics"""
    db = get_database()
    session = next(db.get_session())

    if team_id:
        stats = UsageTracker.get_team_usage_stats(session, team_id)
        print(f"\nUsage Statistics for Team ID {team_id}")
        print("=" * 60)
        print(f"Period: {stats['period']['start']} to {stats['period']['end']}")
        print(f"\nRequests:")
        print(f"  Total: {stats['requests']['total']}")
        print(f"  Successful: {stats['requests']['successful']}")
        print(f"  Failed: {stats['requests']['failed']}")
        print(f"  Success Rate: {stats['requests']['success_rate']:.1f}%")
        print(f"\nPerformance:")
        print(f"  Avg Response Time: {stats['performance']['avg_response_time_ms']:.0f}ms")

        if stats['models']:
            print(f"\nTop Models Used:")
            for model_stat in stats['models'][:5]:
                print(f"  {model_stat['model']}: {model_stat['requests']} requests")

    elif api_key_id:
        stats = UsageTracker.get_api_key_usage_stats(session, api_key_id)
        print(f"\nUsage Statistics for API Key ID {api_key_id}")
        print("=" * 60)
        print(f"Period: {stats['period']['start']} to {stats['period']['end']}")
        print(f"\nRequests:")
        print(f"  Total: {stats['requests']['total']}")
        print(f"  Successful: {stats['requests']['successful']}")
        print(f"  Failed: {stats['requests']['failed']}")


def main():
    parser = argparse.ArgumentParser(description="Manage teams and API keys")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Init database
    subparsers.add_parser("init", help="Initialize the database")

    # Team commands
    team_parser = subparsers.add_parser("team", help="Team management")
    team_subparsers = team_parser.add_subparsers(dest="subcommand")

    team_create = team_subparsers.add_parser("create", help="Create a new team")
    team_create.add_argument("name", help="Team name")
    team_create.add_argument("--daily-quota", type=int, help="Daily request quota")
    team_create.add_argument("--monthly-quota", type=int, help="Monthly request quota")

    team_subparsers.add_parser("list", help="List all teams")

    team_delete = team_subparsers.add_parser("delete", help="Delete a team")
    team_delete.add_argument("team_id", type=int, help="Team ID")
    team_delete.add_argument("--force", action="store_true", help="Force delete (removes all keys and usage logs)")

    # API Key commands
    key_parser = subparsers.add_parser("key", help="API key management")
    key_subparsers = key_parser.add_subparsers(dest="subcommand")

    key_create = key_subparsers.add_parser("create", help="Create a new API key")
    key_create.add_argument("team_id", type=int, help="Team ID")
    key_create.add_argument("name", help="Key name")
    key_create.add_argument("--level", choices=["user", "team_lead", "admin"], default="user", help="Access level")
    key_create.add_argument("--description", help="Key description")
    key_create.add_argument("--expires", type=int, help="Expiration in days")

    key_list = key_subparsers.add_parser("list", help="List API keys")
    key_list.add_argument("--team-id", type=int, help="Filter by team ID")

    key_revoke = key_subparsers.add_parser("revoke", help="Revoke an API key")
    key_revoke.add_argument("key_id", type=int, help="API key ID")
    key_revoke.add_argument("--permanent", action="store_true", help="Permanently delete (instead of just revoking)")

    # Usage commands
    usage_parser = subparsers.add_parser("usage", help="View usage statistics")
    usage_parser.add_argument("--team-id", type=int, help="Team ID")
    usage_parser.add_argument("--key-id", type=int, help="API Key ID")
    usage_parser.add_argument("--days", type=int, default=30, help="Number of days to look back")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute commands
    if args.command == "init":
        init_database()

    elif args.command == "team":
        if args.subcommand == "create":
            create_team(args.name, args.daily_quota, args.monthly_quota)
        elif args.subcommand == "list":
            list_teams()
        elif args.subcommand == "delete":
            delete_team(args.team_id, args.force)
        else:
            team_parser.print_help()

    elif args.command == "key":
        if args.subcommand == "create":
            create_api_key(args.team_id, args.name, args.level, args.description, args.expires)
        elif args.subcommand == "list":
            list_api_keys(args.team_id)
        elif args.subcommand == "revoke":
            revoke_api_key(args.key_id, args.permanent)
        else:
            key_parser.print_help()

    elif args.command == "usage":
        show_usage(args.team_id, args.key_id, args.days)


if __name__ == "__main__":
    main()
