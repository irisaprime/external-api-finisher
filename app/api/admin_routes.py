"""
Admin API routes for channel and API key management

TWO-PATH AUTHENTICATION:
These endpoints are ONLY accessible to SUPER ADMINS (administrators).
Authentication via SUPER_ADMIN_API_KEYS environment variable (NOT database).

ADMIN ENDPOINTS (SUPER ADMINS ONLY):
- Channel management (create, list, update, delete channels)
- API key management (create, list, revoke API keys for any channel)
- Usage statistics (view ALL channels' usage)
- Platform information (Telegram + Internal platform config)
- System administration (clear sessions, webhook config, etc.)

SECURITY:
- All endpoints protected by require_admin_access dependency
- Exposes platform details including Telegram (admin-only information)
- External channels (CHANNEL level) have NO ACCESS to these endpoints
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import require_admin_access
from app.core.name_mapping import get_friendly_model_name
from app.models.database import APIKey, get_db_session
from app.services.api_key_manager import APIKeyManager
from app.services.channel_manager import channel_manager
from app.services.session_manager import session_manager
from app.services.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Channel Management & Administration"])


# ===========================
# Pydantic Models for Requests/Responses
# ===========================


class ChannelCreate(BaseModel):
    """
    Request model for creating a channel.

    Field Distinction:
    - title: Human-friendly name (supports Persian/Farsi) for admin UI and chat
    - channel_id: System identifier for routing (ASCII, no spaces)
    - access_type: 'public' (Telegram, Discord) or 'private' (customer integrations)
    - Platform config overrides: If NULL, uses defaults for access_type
    - Auto-generates API key on creation
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "تیم هوش مصنوعی داخلی",
                    "channel_id": "Internal-BI",
                    "access_type": "private",
                    "monthly_quota": 100000,
                    "daily_quota": 5000,
                },
                {
                    "title": "پلتفرم بازاریابی",
                    "channel_id": "External-Marketing",
                    "access_type": "private",
                    "monthly_quota": 50000,
                    "daily_quota": 2000,
                    "rate_limit": 40,
                    "max_history": 20,
                },
                {
                    "channel_id": "HOSCO-Popak",
                    "access_type": "private",
                    "monthly_quota": 75000,
                    "default_model": "openai/gpt-5-chat",
                    "available_models": ["openai/gpt-5-chat", "google/gemini-2.0-flash-001"],
                },
            ]
        }
    )

    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description=(
            "Human-friendly display name for the channel (supports Persian/Farsi and multilingual text). "
            "Used in admin UI, reports, and logs for easy identification. "
            "If not provided, defaults to channel_id value. "
            "Examples: 'تیم هوش مصنوعی داخلی', 'Internal BI Team', 'Marketing Platform'"
        ),
        examples=["تیم هوش مصنوعی داخلی", "Internal BI Team", "پلتفرم بازاریابی"],
    )
    channel_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description=(
            "Unique system identifier for routing and session isolation (ASCII only, no spaces). "
            "Used internally for session keys, logging, and API routing. "
            "Must be unique across all channels. "
            "Recommended format: PascalCase or kebab-case (e.g., 'Internal-BI', 'External-Marketing'). "
            "Cannot be changed after creation without breaking existing sessions."
        ),
        examples=["Internal-BI", "External-Marketing", "Data-Analytics", "Customer-Support"],
    )
    access_type: str = Field(
        "private",
        pattern=r"^(public|private)$",
        description=(
            "Platform access control type determining feature set and visibility. "
            "'public': Open access platforms (e.g., Telegram, Discord) with limited models and basic features. "
            "'private': Restricted access channels (e.g., customer integrations, internal teams) with full features, "
            "multiple AI models, and enterprise capabilities. "
            "Affects default configurations for rate limits, models, and commands."
        ),
        examples=["private", "public"],
    )
    monthly_quota: Optional[int] = Field(
        None,
        ge=0,
        description=(
            "Maximum number of requests allowed per calendar month for this channel. "
            "None or 0 = unlimited (use with caution). "
            "When exceeded, all requests return quota_exceeded error. "
            "Resets on the 1st of each month. "
            "Tracked across all users in this channel."
        ),
        examples=[100000, 50000, None],
    )
    daily_quota: Optional[int] = Field(
        None,
        ge=0,
        description=(
            "Maximum number of requests allowed per day (UTC) for this channel. "
            "None or 0 = unlimited (use with caution). "
            "When exceeded, all requests return quota_exceeded error. "
            "Resets daily at 00:00 UTC. "
            "Tracked across all users in this channel."
        ),
        examples=[5000, 2000, None],
    )

    # Platform configuration overrides (NULL = use defaults for access_type)
    rate_limit: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
        description=(
            "Override default rate limit in requests per minute per user. "
            "None = use access_type default (typically 20 for public, 60 for private). "
            "Prevents abuse by limiting how many messages a single user can send per minute. "
            "Tracked per user_id within this channel. "
            "Recommended: 20-60 for most use cases, higher for high-volume automation."
        ),
        examples=[20, 60, 80, None],
    )
    max_history: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description=(
            "Override maximum conversation history length (number of messages). "
            "None = use access_type default (typically 10 for public, 30 for private). "
            "Determines how many recent messages are sent to the AI model for context. "
            "Longer history = better context but higher token usage and costs. "
            "Messages beyond this limit are excluded from AI context but kept in database."
        ),
        examples=[10, 30, 50, None],
    )
    default_model: Optional[str] = Field(
        None,
        description=(
            "Override default AI model (technical ID format: 'provider/model-name'). "
            "None = use access_type default (typically 'google/gemini-2.0-flash-001' for public). "
            "This is the model users will use unless they switch with /model command. "
            "Must be in the available_models list. "
            "Examples: 'openai/gpt-5-chat', 'anthropic/claude-4.1', 'google/gemini-2.0-flash-001'"
        ),
        examples=["openai/gpt-5-chat", "google/gemini-2.0-flash-001", "anthropic/claude-4.1", None],
    )
    available_models: Optional[List[str]] = Field(
        None,
        description=(
            "Override list of available AI models (technical IDs). "
            "None = use access_type default. "
            "Users can switch between these models using the /model command (if allow_model_switch=true). "
            "Format: ['provider/model-name', ...]. "
            "Public channels typically have 1-2 models, private channels may have 5-10+."
        ),
        examples=[
            ["openai/gpt-5-chat", "google/gemini-2.0-flash-001"],
            ["anthropic/claude-4.1", "openai/gpt-5-chat", "google/gemini-2.5-flash-001"],
            None,
        ],
    )
    allow_model_switch: Optional[bool] = Field(
        None,
        description=(
            "Override whether users can switch AI models using /model command. "
            "None = use access_type default (typically False for public, True for private). "
            "If True, users can use '/model <alias>' to switch between available_models. "
            "If False, /model command is disabled and users are locked to default_model."
        ),
        examples=[True, False, None],
    )


class ChannelUpdate(BaseModel):
    """
    Request model for updating a channel.

    Field Distinction:
    - title: Human-friendly name for admin UI and reports
    - channel_id: System identifier for routing and session isolation
    - access_type: 'public' or 'private'
    - Platform config overrides: Set to NULL to reset to defaults
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Internal BI Team",
                    "channel_id": "Internal-BI-Updated",
                    "monthly_quota": 150000,
                    "daily_quota": 7000,
                    "is_active": True,
                },
                {"is_active": False},
                {
                    "title": "Marketing Platform",
                    "channel_id": "Marketing-Platform",
                    "rate_limit": 80,
                    "max_history": 25,
                },
                {
                    "default_model": "openai/gpt-5-chat",
                    "available_models": ["openai/gpt-5-chat", "anthropic/claude-4.1"],
                    "allow_model_switch": True,
                },
            ]
        }
    )

    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Update the human-friendly display name (supports Persian/Farsi). Leave null to keep existing value.",
        examples=["Internal BI Team", "Updated Marketing Platform"],
    )
    channel_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description=(
            "Update the system identifier for routing (ASCII only, no spaces). "
            "WARNING: Changing this will break existing sessions and API integrations. "
            "Leave null to keep existing value."
        ),
        examples=["Internal-BI-Updated", "New-Channel-ID"],
    )
    access_type: Optional[str] = Field(
        None,
        pattern=r"^(public|private)$",
        description=(
            "Update the platform access type ('public' or 'private'). "
            "Changing this affects default configurations but won't override explicitly set values. "
            "Leave null to keep existing value."
        ),
        examples=["private", "public"],
    )
    monthly_quota: Optional[int] = Field(
        None,
        ge=0,
        description="Update monthly request quota. Set to 0 or very high value for unlimited. Leave null to keep existing value.",
        examples=[150000, 200000, 0],
    )
    daily_quota: Optional[int] = Field(
        None,
        ge=0,
        description="Update daily request quota. Set to 0 or very high value for unlimited. Leave null to keep existing value.",
        examples=[7000, 10000, 0],
    )
    is_active: Optional[bool] = Field(
        None,
        description=(
            "Enable or disable the channel. "
            "Inactive channels (is_active=false) cannot process any requests and return 403 errors. "
            "Used for temporarily suspending access without deleting the channel. "
            "Leave null to keep existing value."
        ),
        examples=[True, False],
    )

    # Platform configuration overrides
    rate_limit: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
        description="Update rate limit (requests/min per user). Set to null to reset to access_type default. Leave unchanged if not provided.",
        examples=[60, 80, 100],
    )
    max_history: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description="Update max conversation history length. Set to null to reset to access_type default. Leave unchanged if not provided.",
        examples=[30, 25, 40],
    )
    default_model: Optional[str] = Field(
        None,
        description="Update default AI model. Set to null to reset to access_type default. Must be in available_models list.",
        examples=["openai/gpt-5-chat", "google/gemini-2.5-flash-001"],
    )
    available_models: Optional[List[str]] = Field(
        None,
        description="Update available models list. Set to null to reset to access_type default. Must include default_model.",
        examples=[["openai/gpt-5-chat", "anthropic/claude-4.1"], ["google/gemini-2.5-flash-001"]],
    )
    allow_model_switch: Optional[bool] = Field(
        None,
        description="Update model switching permission. Set to null to reset to access_type default.",
        examples=[True, False],
    )


class ChannelResponse(BaseModel):
    """
    Response model for channel with usage statistics.

    Includes API key prefix and usage data (one key per channel).

    Field Distinction:
    - title: Human-friendly name for display purposes
    - channel_id: System identifier for routing/operations
    - access_type: 'public' or 'private'
    - Platform config: Shows overrides if set, NULL means using defaults
    - usage: Recent usage statistics (last 30 days by default)
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "title": "Internal BI Team",
                    "channel_id": "Internal-BI",
                    "access_type": "private",
                    "monthly_quota": 100000,
                    "daily_quota": 5000,
                    "is_active": True,
                    "rate_limit": 80,
                    "max_history": 25,
                    "default_model": "openai/gpt-5-chat",
                    "available_models": ["openai/gpt-5-chat", "google/gemini-2.0-flash-001"],
                    "allow_model_switch": True,
                    "api_key_prefix": "ark_1234",
                    "api_key_last_used": "2025-01-15T14:30:00",
                    "created_at": "2025-01-01T10:00:00",
                    "updated_at": "2025-01-15T14:30:00",
                    "usage": {
                        "period": {
                            "start": "2025-01-01T00:00:00",
                            "end": "2025-01-31T23:59:59",
                            "days": 30,
                        },
                        "requests": {"total": 15000, "successful": 14850, "failed": 150},
                        "tokens": {"total": 1500000, "average_per_request": 100},
                        "cost": {"total": 15.50, "currency": "USD"},
                    },
                }
            ]
        },
    )

    id: int = Field(
        ...,
        description="Unique database identifier for the channel (auto-generated, immutable)",
        examples=[1, 2, 42],
        gt=0,
    )
    title: str = Field(
        ...,
        description="Human-friendly display name (supports Persian/Farsi). Used in admin UI and reports.",
        examples=["Internal BI Team", "تیم هوش مصنوعی", "Marketing Platform"],
    )
    channel_id: str = Field(
        ...,
        description="System identifier for routing and session isolation (ASCII, unique, immutable)",
        examples=["Internal-BI", "External-Marketing"],
    )
    access_type: str = Field(
        ...,
        description="Platform access type: 'public' (limited features) or 'private' (full features)",
        examples=["private", "public"],
    )
    monthly_quota: Optional[int] = Field(
        None,
        description="Monthly request limit. None = unlimited.",
        examples=[100000, None],
    )
    daily_quota: Optional[int] = Field(
        None,
        description="Daily request limit. None = unlimited.",
        examples=[5000, None],
    )
    is_active: bool = Field(
        ...,
        description="Whether the channel is active. Inactive channels cannot process requests.",
        examples=[True, False],
    )

    # Platform configuration (NULL = using defaults for access_type)
    rate_limit: Optional[int] = Field(
        None,
        description="Rate limit override (requests/min per user). None = using access_type default.",
        examples=[60, 80, None],
    )
    max_history: Optional[int] = Field(
        None,
        description="Max history override (number of messages). None = using access_type default.",
        examples=[30, 25, None],
    )
    default_model: Optional[str] = Field(
        None,
        description="Default AI model override. None = using access_type default.",
        examples=["openai/gpt-5-chat", None],
    )
    available_models: Optional[List[str]] = Field(
        None,
        description="Available models override. None = using access_type default.",
        examples=[["openai/gpt-5-chat", "google/gemini-2.0-flash-001"], None],
    )
    allow_model_switch: Optional[bool] = Field(
        None,
        description="Model switching permission override. None = using access_type default.",
        examples=[True, False, None],
    )

    api_key_prefix: Optional[str] = Field(
        None,
        description="First 8 characters of the channel's API key (for identification). Full key never shown after creation.",
        examples=["ark_1234", "ark_5678"],
    )
    api_key_last_used: Optional[datetime] = Field(
        None,
        description="ISO 8601 timestamp of when the API key was last used (UTC). None if never used.",
        examples=["2025-01-30T14:30:00Z", None],
    )
    created_at: datetime = Field(
        ...,
        description="ISO 8601 timestamp of when the channel was created (UTC)",
        examples=["2025-01-15T10:00:00Z"],
    )
    updated_at: datetime = Field(
        ...,
        description="ISO 8601 timestamp of when the channel was last updated (UTC)",
        examples=["2025-01-30T14:30:00Z"],
    )
    usage: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Usage statistics for the channel (last 30 days by default). "
            "Includes request counts, token usage, costs, and model breakdown. "
            "Only included when explicitly requested with include_usage=true parameter."
        ),
    )


class ChannelCreateResponse(BaseModel):
    """
    Response model when creating a channel (includes the generated API key).

    The API key is shown ONLY ONCE during creation.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "title": "تیم هوش مصنوعی داخلی",
                    "channel_id": "Internal-BI",
                    "access_type": "private",
                    "monthly_quota": 100000,
                    "daily_quota": 5000,
                    "is_active": True,
                    "rate_limit": 60,
                    "max_history": 30,
                    "default_model": None,
                    "available_models": None,
                    "allow_model_switch": None,
                    "created_at": "2025-01-15T10:00:00",
                    "api_key": "ark_1234567890abcdef1234567890abcdef12345678",
                    "warning": "Save this API key securely. It will not be shown again.",
                }
            ]
        }
    )

    id: int = Field(
        ...,
        description="Unique database ID of the newly created channel",
        examples=[1, 2, 42],
        gt=0,
    )
    title: str = Field(
        ...,
        description="Display name of the channel (as created or defaulted to channel_id)",
        examples=["تیم هوش مصنوعی داخلی", "Internal BI Team"],
    )
    channel_id: str = Field(
        ...,
        description="System identifier used for routing (as provided during creation)",
        examples=["Internal-BI", "External-Marketing"],
    )
    access_type: str = Field(
        ...,
        description="Access type: 'public' or 'private'",
        examples=["private", "public"],
    )
    monthly_quota: Optional[int] = Field(
        None,
        description="Monthly request quota (None = unlimited)",
        examples=[100000, None],
    )
    daily_quota: Optional[int] = Field(
        None,
        description="Daily request quota (None = unlimited)",
        examples=[5000, None],
    )
    is_active: bool = Field(
        ...,
        description="Channel activation status (always True for newly created channels)",
        examples=[True],
    )

    # Platform configuration
    rate_limit: Optional[int] = Field(
        None,
        description="Rate limit override (None = using access_type default)",
        examples=[60, None],
    )
    max_history: Optional[int] = Field(
        None,
        description="Max history override (None = using access_type default)",
        examples=[30, None],
    )
    default_model: Optional[str] = Field(
        None,
        description="Default model override (None = using access_type default)",
        examples=["openai/gpt-5-chat", None],
    )
    available_models: Optional[List[str]] = Field(
        None,
        description="Available models override (None = using access_type default)",
        examples=[["openai/gpt-5-chat"], None],
    )
    allow_model_switch: Optional[bool] = Field(
        None,
        description="Model switching override (None = using access_type default)",
        examples=[True, None],
    )

    created_at: datetime = Field(
        ...,
        description="ISO 8601 timestamp of when the channel was created",
        examples=["2025-01-30T10:00:00Z"],
    )
    api_key: str = Field(
        ...,
        min_length=48,
        max_length=48,
        description=(
            "FULL API KEY - Shown ONLY ONCE during creation! "
            "Format: 'ark_' prefix + 44 character hash (48 chars total). "
            "Save this immediately - it cannot be retrieved later. "
            "Use this key in Authorization: Bearer <api_key> header for API requests."
        ),
        examples=[
            "ark_1234567890abcdef1234567890abcdef12345678",
            "ark_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
        ],
    )
    warning: str = Field(
        default="Save this API key securely. It will not be shown again.",
        description="Critical warning about API key storage - this is the only time the full key is visible",
    )


class UsageStatsResponse(BaseModel):
    """Response model for usage statistics (channel-based only, no api_key_id)

    Note: channel_name contains the channel's title (supports Persian/Farsi)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "channel_id": 1,
                    "channel_name": "تیم هوش مصنوعی داخلی",
                    "period": {
                        "start": "2025-01-01T00:00:00",
                        "end": "2025-01-31T23:59:59",
                        "days": 30,
                    },
                    "requests": {"total": 15000, "successful": 14850, "failed": 150},
                    "tokens": {"total": 1500000, "average_per_request": 100},
                    "cost": {"total": 15.50, "currency": "USD"},
                    "performance": {"average_response_time_ms": 850, "p95_response_time_ms": 1200},
                    "models": [
                        {"model": "Gemini 2.0 Flash", "requests": 8000, "percentage": 53.3},
                        {"model": "GPT-5 Chat", "requests": 5000, "percentage": 33.3},
                        {"model": "DeepSeek v3", "requests": 2000, "percentage": 13.3},
                    ],
                }
            ]
        }
    )

    channel_id: Optional[int] = Field(
        None,
        description="Database ID of the channel (None for aggregated cross-channel stats)",
        examples=[1, 2, None],
        gt=0,
    )
    channel_name: Optional[str] = Field(
        None,
        description=(
            "Human-friendly channel name (supports Persian/Farsi). "
            "Taken from the channel's title field. "
            "None for aggregated cross-channel statistics."
        ),
        examples=["تیم هوش مصنوعی داخلی", "Internal BI Channel", None],
    )
    period: dict = Field(
        ...,
        description=(
            "Time period for these statistics. "
            "Contains: start (ISO 8601), end (ISO 8601), days (integer). "
            "Example: {'start': '2025-01-01T00:00:00Z', 'end': '2025-01-31T23:59:59Z', 'days': 30}"
        ),
    )
    requests: dict = Field(
        ...,
        description=(
            "Request statistics. "
            "Contains: total (int), successful (int), failed (int). "
            "Example: {'total': 15000, 'successful': 14850, 'failed': 150}"
        ),
    )
    tokens: dict = Field(
        ...,
        description=(
            "Token usage statistics. "
            "Contains: total (int), average_per_request (float). "
            "Tokens are the units consumed by AI models (input + output). "
            "Example: {'total': 1500000, 'average_per_request': 100}"
        ),
    )
    cost: dict = Field(
        ...,
        description=(
            "Estimated cost statistics. "
            "Contains: total (float), currency (str, typically 'USD'). "
            "Costs are estimates based on token usage and model pricing. "
            "Example: {'total': 15.50, 'currency': 'USD'}"
        ),
    )
    performance: dict = Field(
        ...,
        description=(
            "Performance metrics. "
            "Contains: average_response_time_ms (int), p95_response_time_ms (int). "
            "Measures API response times (excluding AI service latency). "
            "Example: {'average_response_time_ms': 850, 'p95_response_time_ms': 1200}"
        ),
    )
    models: List[dict] = Field(
        ...,
        description=(
            "Breakdown of usage by AI model. "
            "Each entry contains: model (str, friendly name), requests (int), percentage (float). "
            "Example: [{'model': 'Gemini 2.0 Flash', 'requests': 8000, 'percentage': 53.3}]"
        ),
    )


# ===========================
# Platform Information & Statistics (Admin Only)
# ===========================


class AdminDashboardResponse(BaseModel):
    """
    Unified admin dashboard response with platform info and statistics

    Combines health check, platform configurations, and statistics into a single endpoint
    """
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "service": "Arash External API Service",
                    "version": "1.0.0",
                    "status": "healthy",
                    "timestamp": "2025-01-15T14:30:00",
                    "platforms": {
                        "telegram": {
                            "type": "public",
                            "model": "Gemini 2.0 Flash",
                            "rate_limit": 20,
                            "commands": ["start", "help", "model", "clear"],
                            "max_history": 10,
                            "features": {
                                "model_switching": False,
                                "requires_auth": True
                            }
                        },
                        "internal": {
                            "type": "private",
                            "default_model": "Gemini 2.0 Flash",
                            "available_models": ["Gemini 2.0 Flash", "GPT-5 Chat", "DeepSeek v3"],
                            "rate_limit": 60,
                            "commands": ["start", "help", "model", "models", "clear", "status"],
                            "max_history": 30,
                            "features": {
                                "model_switching": True,
                                "requires_auth": True
                            }
                        }
                    },
                    "statistics": {
                        "total_sessions": 150,
                        "active_sessions": 25,
                        "telegram": {
                            "sessions": 10,
                            "messages": 500,
                            "active": 5,
                            "model": "Gemini 2.0 Flash"
                        },
                        "internal": {
                            "sessions": 140,
                            "messages": 5000,
                            "active": 20,
                            "models_used": {
                                "Gemini 2.0 Flash": 80,
                                "GPT-5 Chat": 40,
                                "DeepSeek v3": 20
                            },
                            "channel_breakdown": [
                                {
                                    "channel_id": 1,
                                    "channel_name": "Internal BI",
                                    "sessions": 100,
                                    "messages": 3000,
                                    "active": 15,
                                    "models_used": {"Gemini 2.0 Flash": 60}
                                }
                            ]
                        }
                    }
                }
            ]
        }
    )

    service: str = Field(
        ...,
        description="Service name identifier",
        examples=["Arash External API Service"],
    )
    version: str = Field(
        ...,
        description="Semantic version of the API service",
        examples=["1.0.0", "1.2.3"],
    )
    status: str = Field(
        ...,
        description=(
            "Overall service health status. "
            "'healthy': All systems operational (AI service responsive). "
            "'degraded': Service running but AI service unavailable. "
            "'down': Critical failure (database unavailable, etc.)."
        ),
        examples=["healthy", "degraded", "down"],
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp when this dashboard data was generated (UTC)",
        examples=["2025-01-30T14:30:00Z"],
    )
    platforms: Dict[str, Dict[str, Any]] = Field(
        ...,
        description=(
            "Platform configurations for 'telegram' (public) and 'internal' (private). "
            "Each platform contains: type, model(s), rate_limit, commands, max_history, features. "
            "Shows current configuration for all platforms managed by the service."
        ),
    )
    statistics: Dict[str, Any] = Field(
        ...,
        description=(
            "Real-time statistics for active sessions and usage. "
            "Contains: total_sessions, active_sessions, telegram (breakdown), internal (breakdown). "
            "Telegram breakdown: sessions, messages, active, model. "
            "Internal breakdown: sessions, messages, active, models_used, channel_breakdown."
        ),
    )


@router.get(
    "/",
    summary="Get admin dashboard with platform overview and statistics",
    description=(
        "Retrieve comprehensive admin dashboard data including service health, platform configurations, "
        "and real-time session statistics across all channels. "
        "Shows Telegram and internal platform settings, active sessions, model usage breakdown, "
        "and per-channel analytics. Super admin access required."
    ),
    response_description=(
        "Complete admin dashboard with service status, platform configurations (Telegram + Internal), "
        "and detailed statistics including session counts, message volumes, and model usage by channel."
    ),
    operation_id="get_admin_dashboard",
    response_model=AdminDashboardResponse,
    responses={
        200: {
            "description": "Admin dashboard data retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "service": "Arash External API Service",
                        "version": "1.0.0",
                        "status": "healthy",
                        "timestamp": "2025-01-15T14:30:00",
                        "platforms": {
                            "telegram": {
                                "type": "public",
                                "model": "Gemini 2.0 Flash",
                                "rate_limit": 20,
                                "commands": ["start", "help", "clear"]
                            },
                            "internal": {
                                "type": "private",
                                "default_model": "Gemini 2.0 Flash",
                                "available_models": ["Gemini 2.0 Flash", "GPT-5 Chat"],
                                "rate_limit": 60
                            }
                        },
                        "statistics": {
                            "total_sessions": 150,
                            "active_sessions": 25
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required - No super admin API key provided",
            "content": {
                "application/json": {
                    "examples": {
                        "no_auth_header": {
                            "summary": "Missing Authorization header",
                            "value": {
                                "detail": "Authentication required"
                            }
                        },
                        "admin_keys_not_configured": {
                            "summary": "Super admin keys not configured",
                            "value": {
                                "detail": "Super admin authentication not configured"
                            }
                        }
                    }
                }
            }
        },
        403: {
            "description": "Forbidden - Invalid super admin API key",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid super admin API key"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "examples": {
                        "database_error": {
                            "summary": "Database connection error",
                            "value": {
                                "detail": "Failed to retrieve dashboard data"
                            }
                        },
                        "general_error": {
                            "summary": "Unexpected server error",
                            "value": {
                                "detail": "An unexpected error occurred"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def admin_dashboard(
    api_key=Depends(require_admin_access),
):
    """
    Unified admin dashboard with platform info and statistics (ADMIN ONLY)

    Returns comprehensive information including:
    - Service health and version
    - Platform configurations (Telegram + Internal)
    - Session statistics (overall + per channel)

    SECURITY: Exposes Telegram platform details - Admin access required
    """
    db = get_db_session()

    # Get platform configurations
    telegram_config = channel_manager.get_config("telegram")
    internal_config = channel_manager.get_config("internal")

    # Get channel name mapping for statistics
    channels = APIKeyManager.list_all_channels(db)
    channel_name_map = {channel.id: channel.title for channel in channels}

    # Calculate statistics
    total_sessions = len(session_manager.sessions)
    active_sessions = session_manager.get_active_session_count(minutes=5)

    telegram_stats = {
        "sessions": 0,
        "messages": 0,
        "active": 0,
        "model": get_friendly_model_name(telegram_config.model),
    }

    internal_stats = {
        "sessions": 0,
        "messages": 0,
        "active": 0,
        "models_used": defaultdict(int),
    }

    channel_stats = defaultdict(
        lambda: {
            "channel_id": None,
            "channel_name": "Unknown",
            "sessions": 0,
            "messages": 0,
            "active": 0,
            "models_used": defaultdict(int),
        }
    )

    for session in session_manager.sessions.values():
        is_active = not session.is_expired(5)

        if session.channel_identifier == "telegram":
            telegram_stats["sessions"] += 1
            telegram_stats["messages"] += session.total_message_count
            if is_active:
                telegram_stats["active"] += 1
        elif session.channel_id is not None:
            internal_stats["sessions"] += 1
            internal_stats["messages"] += session.total_message_count
            friendly_model = get_friendly_model_name(session.current_model)
            internal_stats["models_used"][friendly_model] += 1
            if is_active:
                internal_stats["active"] += 1

            channel_id = session.channel_id
            if channel_id not in channel_stats:
                channel_stats[channel_id]["channel_id"] = channel_id
                channel_stats[channel_id]["channel_name"] = channel_name_map.get(channel_id, f"Channel {channel_id}")

            channel_stats[channel_id]["sessions"] += 1
            channel_stats[channel_id]["messages"] += session.total_message_count
            channel_stats[channel_id]["models_used"][friendly_model] += 1
            if is_active:
                channel_stats[channel_id]["active"] += 1

    channel_breakdown = [
        {
            "channel_id": stats["channel_id"],
            "channel_name": stats["channel_name"],
            "sessions": stats["sessions"],
            "messages": stats["messages"],
            "active": stats["active"],
            "models_used": dict(stats["models_used"]),
        }
        for stats in channel_stats.values()
    ]
    channel_breakdown.sort(key=lambda x: x["sessions"], reverse=True)

    return AdminDashboardResponse(
        service="Arash External API Service",
        version="1.0.0",
        status="healthy",
        timestamp=datetime.now(),
        platforms={
            "telegram": {
                "type": "public",
                "model": get_friendly_model_name(telegram_config.model),
                "rate_limit": telegram_config.rate_limit,
                "commands": telegram_config.commands,
                "max_history": telegram_config.max_history,
                "features": {
                    "model_switching": telegram_config.allow_model_switch,
                    "requires_auth": telegram_config.requires_auth,
                },
            },
            "internal": {
                "type": "private",
                "default_model": get_friendly_model_name(internal_config.model),
                "available_models": [
                    get_friendly_model_name(m) for m in internal_config.available_models
                ],
                "rate_limit": internal_config.rate_limit,
                "commands": internal_config.commands,
                "max_history": internal_config.max_history,
                "features": {
                    "model_switching": internal_config.allow_model_switch,
                    "requires_auth": internal_config.requires_auth,
                },
            },
        },
        statistics={
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "telegram": telegram_stats,
            "internal": {
                **internal_stats,
                "models_used": dict(internal_stats["models_used"]),
                "channel_breakdown": channel_breakdown,
            },
        },
    )


# ===========================
# Channel Management Endpoints
# ===========================


@router.post(
    "/channels",
    summary="Create new channel with auto-generated API key",
    description=(
        "Create a new channel for external integrations with an automatically generated API key. "
        "The full API key is returned ONLY ONCE in this response - save it securely. "
        "Channels can be configured with custom quotas, rate limits, AI models, and access controls. "
        "Super admin access required."
    ),
    response_description=(
        "Newly created channel details including the FULL API KEY (shown only once). "
        "Save the API key immediately - it cannot be retrieved later."
    ),
    operation_id="create_channel",
    response_model=ChannelCreateResponse,
    responses={
        200: {
            "description": "Channel created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "title": "تیم هوش مصنوعی داخلی",
                        "channel_id": "Internal-BI",
                        "monthly_quota": 100000,
                        "daily_quota": 5000,
                        "is_active": True,
                        "created_at": "2025-01-15T10:00:00",
                        "api_key": "ark_1234567890abcdef1234567890abcdef12345678",
                        "warning": "Save this API key securely. It will not be shown again.",
                    }
                }
            },
        },
        400: {
            "description": "Bad request - Invalid input or channel_id already exists",
            "content": {
                "application/json": {
                    "examples": {
                        "channel_exists": {
                            "summary": "Channel ID already exists",
                            "value": {
                                "detail": "Channel with ID 'Internal-BI' already exists"
                            }
                        },
                        "invalid_channel_id": {
                            "summary": "Invalid channel_id format",
                            "value": {
                                "detail": "channel_id must be ASCII characters without spaces"
                            }
                        },
                        "invalid_quota": {
                            "summary": "Invalid quota value",
                            "value": {
                                "detail": "Quota values must be positive integers"
                            }
                        }
                    }
                }
            },
        },
        401: {
            "description": "Authentication required - No super admin API key provided",
            "content": {
                "application/json": {
                    "examples": {
                        "no_auth_header": {
                            "summary": "Missing Authorization header",
                            "value": {
                                "detail": "Authentication required"
                            }
                        },
                        "admin_keys_not_configured": {
                            "summary": "Super admin keys not configured",
                            "value": {
                                "detail": "Super admin authentication not configured"
                            }
                        }
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - Invalid super admin API key",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid super admin API key"
                    }
                }
            },
        },
        422: {
            "description": "Validation error - Request body doesn't match schema",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "channel_id"],
                                "msg": "field required",
                                "type": "value_error.missing"
                            }
                        ]
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "examples": {
                        "database_error": {
                            "summary": "Database error during channel creation",
                            "value": {
                                "detail": "Failed to create channel due to database error"
                            }
                        },
                        "api_key_generation_error": {
                            "summary": "Error generating API key",
                            "value": {
                                "detail": "Channel created but API key generation failed"
                            }
                        },
                        "general_error": {
                            "summary": "Unexpected server error",
                            "value": {
                                "detail": "An unexpected error occurred"
                            }
                        }
                    }
                }
            },
        },
    },
)
async def create_channel(
    channel_data: ChannelCreate,
    api_key=Depends(require_admin_access),
):
    """
    Create a new channel with auto-generated API key (Admin only).

    ⚠️ **IMPORTANT**: The API key is shown ONLY ONCE in the response. Save it securely!

    ## Request Example
    ```json
    {
      "channel_id": "Internal-BI",
      "monthly_quota": 100000,
      "daily_quota": 5000
    }
    ```

    ## Response
    The response includes the full API key. This is the **only time** it will be visible.
    Store it immediately in a secure location.

    ## Authentication
    Requires super admin API key in Authorization header:
    ```http
    Authorization: Bearer <super-admin-key>
    ```
    """
    db = get_db_session()

    # Check if channel_id already exists
    existing_channel = APIKeyManager.get_channel_by_channel_id(db, channel_data.channel_id)
    if existing_channel:
        raise HTTPException(
            status_code=400,
            detail=f"Channel with channel_id '{channel_data.channel_id}' already exists",
        )

    # Create channel with auto-generated API key
    channel, api_key_string = APIKeyManager.create_channel_with_key(
        db=db,
        channel_id=channel_data.channel_id,
        title=channel_data.title,
        access_type=channel_data.access_type,
        monthly_quota=channel_data.monthly_quota,
        daily_quota=channel_data.daily_quota,
        rate_limit=channel_data.rate_limit,
        max_history=channel_data.max_history,
        default_model=channel_data.default_model,
        available_models=channel_data.available_models,
        allow_model_switch=channel_data.allow_model_switch,
    )

    return ChannelCreateResponse(
        id=channel.id,
        title=channel.title,
        channel_id=channel.channel_id,
        access_type=channel.access_type,
        monthly_quota=channel.monthly_quota,
        daily_quota=channel.daily_quota,
        is_active=channel.is_active,
        rate_limit=channel.rate_limit,
        max_history=channel.max_history,
        default_model=channel.default_model,
        available_models=channel.available_models.split(",") if channel.available_models else None,
        allow_model_switch=channel.allow_model_switch,
        created_at=channel.created_at,
        api_key=api_key_string,
    )


class ChannelsListResponse(BaseModel):
    """Response model for channels listing with optional total report"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "channels": [
                        {
                            "id": 1,
                            "title": "Internal BI Team",
                            "channel_id": "Internal-BI",
                            "monthly_quota": 100000,
                            "daily_quota": 5000,
                            "is_active": True,
                            "api_key_prefix": "ark_1234",
                            "usage": {
                                "requests": {"total": 15000, "successful": 14850}
                            }
                        }
                    ],
                    "total_report": {
                        "total_channels": 5,
                        "active_channels": 4,
                        "total_requests": 75000,
                        "total_successful": 74250,
                        "total_failed": 750,
                        "total_cost": 75.50
                    }
                }
            ]
        }
    )

    channels: List[ChannelResponse]
    total_report: Optional[Dict[str, Any]] = Field(
        None,
        description="Total aggregated report across all channels (included when totally=true)",
    )


@router.get(
    "/channels",
    summary="List all channels with usage statistics",
    description=(
        "Retrieve a list of all channels with their configuration and usage statistics. "
        "Optionally filter by active status, specify the time period for usage data, "
        "or include an aggregated total report across all channels. "
        "Super admin access required."
    ),
    response_description=(
        "List of channels with usage data for the specified period. "
        "Optionally includes aggregated total report when totally=true."
    ),
    operation_id="list_channels",
    response_model=ChannelsListResponse,
    responses={
        200: {
            "description": "Channels list retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "channels_list": {
                            "summary": "List of channels with usage statistics",
                            "value": {
                                "channels": [
                                    {
                                        "id": 1,
                                        "title": "Internal BI Team",
                                        "channel_id": "Internal-BI",
                                        "monthly_quota": 100000,
                                        "daily_quota": 5000,
                                        "is_active": True,
                                        "api_key_prefix": "ark_1234",
                                        "created_at": "2025-01-01T10:00:00",
                                        "updated_at": "2025-01-15T14:30:00",
                                        "usage": {
                                            "requests": {"total": 15000, "successful": 14850}
                                        }
                                    }
                                ],
                                "total_report": None
                            }
                        },
                        "channels_with_total": {
                            "summary": "Channels list with total aggregated report",
                            "value": {
                                "channels": [
                                    {
                                        "id": 1,
                                        "title": "Internal BI Team",
                                        "channel_id": "Internal-BI",
                                        "monthly_quota": 100000,
                                        "is_active": True
                                    }
                                ],
                                "total_report": {
                                    "total_channels": 5,
                                    "active_channels": 4,
                                    "total_requests": 75000,
                                    "total_cost": 75.50
                                }
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required - No super admin API key provided",
            "content": {
                "application/json": {
                    "examples": {
                        "no_auth_header": {
                            "summary": "Missing Authorization header",
                            "value": {
                                "detail": "Authentication required"
                            }
                        },
                        "admin_keys_not_configured": {
                            "summary": "Super admin keys not configured",
                            "value": {
                                "detail": "Super admin authentication not configured"
                            }
                        }
                    }
                }
            }
        },
        403: {
            "description": "Forbidden - Invalid super admin API key",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid super admin API key"
                    }
                }
            }
        },
        404: {
            "description": "Not found - Channel with specified ID does not exist",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Channel not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "examples": {
                        "database_error": {
                            "summary": "Database connection error",
                            "value": {
                                "detail": "Failed to retrieve channels from database"
                            }
                        },
                        "usage_stats_error": {
                            "summary": "Error calculating usage statistics",
                            "value": {
                                "detail": "Failed to calculate usage statistics"
                            }
                        },
                        "general_error": {
                            "summary": "Unexpected server error",
                            "value": {
                                "detail": "An unexpected error occurred"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def get_channels(
    channel_id: Optional[int] = None,
    active_only: bool = True,
    days: int = 30,
    totally: bool = False,
    api_key=Depends(require_admin_access),
):
    """
    Get channels with usage statistics (Admin only)

    Parameters:
    - channel_id: Optional channel ID to get specific channel (returns single item list)
    - active_only: Filter active channels only (default: True)
    - days: Number of days for usage statistics (default: 30)
    - totally: Include total aggregated report across all channels (default: False)

    Returns:
    - List of channels with usage data
    - Optional total report when totally=true

    Examples:
    - GET /admin/channels - List all active channels with usage
    - GET /admin/channels?channel_id=1 - Get specific channel with usage
    - GET /admin/channels?totally=true - List all channels with total report
    - GET /admin/channels?active_only=false&days=7 - All channels with 7-day usage
    """
    db = get_db_session()

    # Get channels based on filter
    if channel_id:
        channel = APIKeyManager.get_channel_by_id(db, channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        channels = [channel]
    else:
        channels = APIKeyManager.list_all_channels(db, active_only=active_only)

    # Calculate start date for usage statistics
    start_date = datetime.utcnow() - timedelta(days=days)

    # Build response with API key prefix and usage for each channel
    responses = []
    total_requests = 0
    total_successful = 0
    total_failed = 0
    total_cost = 0.0

    for channel in channels:
        # Get the channel's API key (one per channel)
        api_key_obj = db.query(APIKey).filter(APIKey.channel_id == channel.id).first()

        # Get usage statistics for the channel
        try:
            usage_stats = UsageTracker.get_channel_usage_stats(db, channel.id, start_date)
            # Remove channel_id and channel_name from usage stats (already in ChannelResponse)
            usage_stats.pop("channel_id", None)
            usage_stats.pop("channel_name", None)

            # Aggregate for total report
            if totally:
                total_requests += usage_stats.get("requests", {}).get("total", 0)
                total_successful += usage_stats.get("requests", {}).get("successful", 0)
                total_failed += usage_stats.get("requests", {}).get("failed", 0)
                total_cost += usage_stats.get("cost", {}).get("total", 0.0)
        except Exception as e:
            logger.warning(f"Failed to get usage stats for channel {channel.id}: {e}")
            usage_stats = None

        responses.append(
            ChannelResponse(
                id=channel.id,
                title=channel.title,
                channel_id=channel.channel_id,
                access_type=channel.access_type,
                monthly_quota=channel.monthly_quota,
                daily_quota=channel.daily_quota,
                is_active=channel.is_active,
                rate_limit=channel.rate_limit,
                max_history=channel.max_history,
                default_model=channel.default_model,
                available_models=channel.available_models.split(",") if channel.available_models else None,
                allow_model_switch=channel.allow_model_switch,
                api_key_prefix=api_key_obj.key_prefix if api_key_obj else None,
                api_key_last_used=api_key_obj.last_used_at if api_key_obj else None,
                created_at=channel.created_at,
                updated_at=channel.updated_at,
                usage=usage_stats,
            )
        )

    # Build total report if requested
    total_report = None
    if totally:
        total_report = {
            "total_channels": len(responses),
            "active_channels": sum(1 for r in responses if r.is_active),
            "total_requests": total_requests,
            "total_successful": total_successful,
            "total_failed": total_failed,
            "total_cost": round(total_cost, 2),
            "currency": "USD",
            "period": {
                "start": start_date.isoformat(),
                "end": datetime.utcnow().isoformat(),
                "days": days,
            },
        }

    return ChannelsListResponse(
        channels=responses,
        total_report=total_report,
    )


@router.patch(
    "/channels/{channel_id}",
    summary="Update channel configuration",
    description=(
        "Update one or more settings for an existing channel. "
        "All fields are optional - only provide the fields you want to update. "
        "Returns the updated channel with usage statistics for the specified period. "
        "WARNING: Changing channel_id will break existing sessions and integrations. "
        "Super admin access required."
    ),
    response_description=(
        "Updated channel configuration with usage statistics. "
        "Includes all current settings and recent usage data."
    ),
    operation_id="update_channel",
    response_model=ChannelResponse,
    responses={
        200: {
            "description": "Channel updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "title": "Internal BI Channel Updated",
                        "channel_id": "Internal-BI-v2",
                        "monthly_quota": 150000,
                        "daily_quota": 7000,
                        "is_active": True,
                        "api_key_prefix": "ark_1234",
                        "api_key_last_used": "2025-01-15T14:30:00",
                        "created_at": "2025-01-01T10:00:00",
                        "updated_at": "2025-01-16T10:00:00",
                        "usage": {
                            "requests": {"total": 15000, "successful": 14850}
                        }
                    }
                }
            }
        },
        400: {
            "description": "Bad request - Invalid update data",
            "content": {
                "application/json": {
                    "examples": {
                        "channel_exists": {
                            "summary": "Channel ID already exists (when changing channel_id)",
                            "value": {
                                "detail": "Channel ID 'Internal-BI-v2' is already in use by another channel"
                            }
                        },
                        "invalid_quota": {
                            "summary": "Invalid quota value",
                            "value": {
                                "detail": "Quota values must be positive integers or null"
                            }
                        },
                        "no_fields_provided": {
                            "summary": "No fields to update",
                            "value": {
                                "detail": "At least one field must be provided for update"
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required - No super admin API key provided",
            "content": {
                "application/json": {
                    "examples": {
                        "no_auth_header": {
                            "summary": "Missing Authorization header",
                            "value": {
                                "detail": "Authentication required"
                            }
                        },
                        "admin_keys_not_configured": {
                            "summary": "Super admin keys not configured",
                            "value": {
                                "detail": "Super admin authentication not configured"
                            }
                        }
                    }
                }
            }
        },
        403: {
            "description": "Forbidden - Invalid super admin API key",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid super admin API key"
                    }
                }
            }
        },
        404: {
            "description": "Not found - Channel with specified ID does not exist",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Channel not found"
                    }
                }
            }
        },
        422: {
            "description": "Validation error - Request body doesn't match schema",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "monthly_quota"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "examples": {
                        "database_error": {
                            "summary": "Database error during update",
                            "value": {
                                "detail": "Failed to update channel due to database error"
                            }
                        },
                        "usage_stats_error": {
                            "summary": "Error retrieving usage statistics",
                            "value": {
                                "detail": "Channel updated but failed to retrieve usage statistics"
                            }
                        },
                        "general_error": {
                            "summary": "Unexpected server error",
                            "value": {
                                "detail": "An unexpected error occurred"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def update_channel(
    channel_id: int,
    channel_data: ChannelUpdate,
    days: int = 30,
    api_key=Depends(require_admin_access),
):
    """
    Update channel settings (Admin only)

    Returns updated channel with usage statistics.

    Parameters:
    - channel_id: ID of the channel to update (path parameter)
    - days: Number of days for usage statistics (default: 30)
    - channel_data: Fields to update (all optional)
    """
    db = get_db_session()

    channel = APIKeyManager.update_channel(
        db=db,
        channel_id=channel_id,
        title=channel_data.title,
        channel_id_str=channel_data.channel_id,
        access_type=channel_data.access_type,
        monthly_quota=channel_data.monthly_quota,
        daily_quota=channel_data.daily_quota,
        is_active=channel_data.is_active,
        rate_limit=channel_data.rate_limit,
        max_history=channel_data.max_history,
        default_model=channel_data.default_model,
        available_models=channel_data.available_models,
        allow_model_switch=channel_data.allow_model_switch,
    )

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Get the channel's API key
    api_key_obj = db.query(APIKey).filter(APIKey.channel_id == channel.id).first()

    # Get usage statistics
    start_date = datetime.utcnow() - timedelta(days=days)
    try:
        usage_stats = UsageTracker.get_channel_usage_stats(db, channel.id, start_date)
        usage_stats.pop("channel_id", None)
        usage_stats.pop("channel_name", None)
    except Exception as e:
        logger.warning(f"Failed to get usage stats for channel {channel.id}: {e}")
        usage_stats = None

    return ChannelResponse(
        id=channel.id,
        title=channel.title,
        channel_id=channel.channel_id,
        access_type=channel.access_type,
        monthly_quota=channel.monthly_quota,
        daily_quota=channel.daily_quota,
        is_active=channel.is_active,
        rate_limit=channel.rate_limit,
        max_history=channel.max_history,
        default_model=channel.default_model,
        available_models=channel.available_models.split(",") if channel.available_models else None,
        allow_model_switch=channel.allow_model_switch,
        api_key_prefix=api_key_obj.key_prefix if api_key_obj else None,
        api_key_last_used=api_key_obj.last_used_at if api_key_obj else None,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        usage=usage_stats,
    )