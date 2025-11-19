"""
Admin API routes for channel and API key management

TWO-PATH AUTHENTICATION:
These endpoints are ONLY accessible to SUPER ADMINS (internal team).
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
from app.services.platform_manager import platform_manager
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
    - Platform config overrides: If NULL, uses defaults for platform_type
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
        description="Human-friendly display name (supports Persian/Farsi). Defaults to platform_name if not provided.",
        examples=["تیم هوش مصنوعی داخلی", "Internal BI Team", "پلتفرم بازاریابی"],
    )
    channel_id: str = Field(
        ...,
        description="System identifier for routing (ASCII, no spaces, e.g., 'Internal-BI', 'External-Marketing')",
        examples=["Internal-BI", "External-Marketing", "Data-Analytics"],
    )
    access_type: str = Field(
        "private",
        description="Platform type: 'public' (Telegram, Discord) or 'private' (customer integrations)",
        examples=["private", "public"],
    )
    monthly_quota: Optional[int] = Field(
        None, description="Monthly request quota (None = unlimited)", examples=[100000, None]
    )
    daily_quota: Optional[int] = Field(
        None, description="Daily request quota (None = unlimited)", examples=[5000, None]
    )

    # Platform configuration overrides (NULL = use defaults for platform_type)
    rate_limit: Optional[int] = Field(
        None,
        description="Override default rate limit (requests/min). NULL = use platform_type default",
        examples=[20, 60, None],
    )
    max_history: Optional[int] = Field(
        None,
        description="Override default max conversation history. NULL = use platform_type default",
        examples=[10, 30, None],
    )
    default_model: Optional[str] = Field(
        None,
        description="Override default AI model. NULL = use platform_type default",
        examples=["openai/gpt-5-chat", "google/gemini-2.0-flash-001", None],
    )
    available_models: Optional[List[str]] = Field(
        None,
        description="Override available models list. NULL = use platform_type default",
        examples=[["openai/gpt-5-chat", "google/gemini-2.0-flash-001"], None],
    )
    allow_model_switch: Optional[bool] = Field(
        None,
        description="Override model switching permission. NULL = use platform_type default",
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

    title: Optional[str] = Field(None, examples=["Internal BI Team"])
    channel_id: Optional[str] = Field(None, examples=["Internal-BI-Updated"])
    access_type: Optional[str] = Field(None, examples=["private", "public"])
    monthly_quota: Optional[int] = Field(None, examples=[150000])
    daily_quota: Optional[int] = Field(None, examples=[7000])
    is_active: Optional[bool] = Field(None, examples=[True, False])

    # Platform configuration overrides
    rate_limit: Optional[int] = Field(None, examples=[60, 80, None])
    max_history: Optional[int] = Field(None, examples=[30, 25, None])
    default_model: Optional[str] = Field(None, examples=["openai/gpt-5-chat", None])
    available_models: Optional[List[str]] = Field(
        None, examples=[["openai/gpt-5-chat", "anthropic/claude-4.1"], None]
    )
    allow_model_switch: Optional[bool] = Field(None, examples=[True, False, None])


class ChannelResponse(BaseModel):
    """
    Response model for channel with usage statistics.

    Includes API key prefix and usage data (one key per team).

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

    id: int = Field(..., examples=[1])
    title: str = Field(..., examples=["Internal BI Team"])
    channel_id: str = Field(..., examples=["Internal-BI"])
    access_type: str = Field(..., examples=["private", "public"])
    monthly_quota: Optional[int] = Field(None, examples=[100000])
    daily_quota: Optional[int] = Field(None, examples=[5000])
    is_active: bool = Field(..., examples=[True])

    # Platform configuration (NULL = using defaults for platform_type)
    rate_limit: Optional[int] = Field(None, examples=[60, 80, None])
    max_history: Optional[int] = Field(None, examples=[30, 25, None])
    default_model: Optional[str] = Field(None, examples=["openai/gpt-5-chat", None])
    available_models: Optional[List[str]] = Field(
        None, examples=[["openai/gpt-5-chat", "google/gemini-2.0-flash-001"], None]
    )
    allow_model_switch: Optional[bool] = Field(None, examples=[True, False, None])

    api_key_prefix: Optional[str] = Field(None, examples=["ark_1234"])
    api_key_last_used: Optional[datetime] = Field(None, examples=["2025-01-15T14:30:00"])
    created_at: datetime
    updated_at: datetime
    usage: Optional[Dict[str, Any]] = Field(
        None,
        description="Usage statistics for the channel (last 30 days by default)",
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

    id: int = Field(..., examples=[1])
    title: str = Field(..., examples=["تیم هوش مصنوعی داخلی", "Internal BI Team"])
    channel_id: str = Field(..., examples=["Internal-BI"])
    access_type: str = Field(..., examples=["private", "public"])
    monthly_quota: Optional[int] = Field(None, examples=[100000])
    daily_quota: Optional[int] = Field(None, examples=[5000])
    is_active: bool = Field(..., examples=[True])

    # Platform configuration
    rate_limit: Optional[int] = Field(None, examples=[60, None])
    max_history: Optional[int] = Field(None, examples=[30, None])
    default_model: Optional[str] = Field(None, examples=["openai/gpt-5-chat", None])
    available_models: Optional[List[str]] = Field(None, examples=[None])
    allow_model_switch: Optional[bool] = Field(None, examples=[True, None])

    created_at: datetime
    api_key: str = Field(
        ...,
        description="Full API key - shown only once!",
        examples=["ark_1234567890abcdef1234567890abcdef12345678"],
    )
    warning: str = "Save this API key securely. It will not be shown again."


class UsageStatsResponse(BaseModel):
    """Response model for usage statistics (team-based only, no api_key_id)

    Note: team_name contains the channel's display_name (supports Persian/Farsi)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "team_id": 1,
                    "team_name": "تیم هوش مصنوعی داخلی",
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

    channel_id: Optional[int] = Field(None, examples=[1])
    team_name: Optional[str] = Field(
        None,
        description="Channel display name (supports Persian/Farsi)",
        examples=["تیم هوش مصنوعی داخلی", "Internal BI Team"],
    )
    period: dict
    requests: dict
    tokens: dict
    cost: dict
    performance: dict
    models: List[dict]


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
                            "team_breakdown": [
                                {
                                    "team_id": 1,
                                    "team_name": "Internal BI",
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

    service: str = Field(..., examples=["Arash External API Service"])
    version: str = Field(..., examples=["1.0.0"])
    status: str = Field(..., examples=["healthy"])
    timestamp: datetime
    platforms: Dict[str, Dict[str, Any]]
    statistics: Dict[str, Any]


@router.get(
    "/",
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
    - Session statistics (overall + per team)

    SECURITY: Exposes Telegram platform details - Admin access required
    """
    db = get_db_session()

    # Get platform configurations
    telegram_config = platform_manager.get_config("telegram")
    internal_config = platform_manager.get_config("internal")

    # Get channel name mapping for statistics
    channels = APIKeyManager.list_all_channels(db)
    team_name_map = {channel.id: channel.title for channel in teams}

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

    team_stats = defaultdict(
        lambda: {
            "team_id": None,
            "team_name": "Unknown",
            "sessions": 0,
            "messages": 0,
            "active": 0,
            "models_used": defaultdict(int),
        }
    )

    for session in session_manager.sessions.values():
        is_active = not session.is_expired(5)

        if session.platform == "telegram":
            telegram_stats["sessions"] += 1
            telegram_stats["messages"] += session.total_message_count
            if is_active:
                telegram_stats["active"] += 1
        elif session.team_id is not None:
            internal_stats["sessions"] += 1
            internal_stats["messages"] += session.total_message_count
            friendly_model = get_friendly_model_name(session.current_model)
            internal_stats["models_used"][friendly_model] += 1
            if is_active:
                internal_stats["active"] += 1

            team_id = session.team_id
            if team_id not in team_stats:
                team_stats[team_id]["team_id"] = team_id
                team_stats[team_id]["team_name"] = team_name_map.get(team_id, f"Channel {team_id}")

            team_stats[team_id]["sessions"] += 1
            team_stats[team_id]["messages"] += session.total_message_count
            team_stats[team_id]["models_used"][friendly_model] += 1
            if is_active:
                team_stats[team_id]["active"] += 1

    team_breakdown = [
        {
            "team_id": stats["team_id"],
            "team_name": stats["team_name"],
            "sessions": stats["sessions"],
            "messages": stats["messages"],
            "active": stats["active"],
            "models_used": dict(stats["models_used"]),
        }
        for stats in team_stats.values()
    ]
    team_breakdown.sort(key=lambda x: x["sessions"], reverse=True)

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
                "team_breakdown": team_breakdown,
            },
        },
    )


# ===========================
# Channel Management Endpoints
# ===========================


@router.post(
    "/channels",
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
            "description": "Bad request - Invalid input or platform name already exists",
            "content": {
                "application/json": {
                    "examples": {
                        "platform_exists": {
                            "summary": "Platform name already exists",
                            "value": {
                                "detail": "Channel with platform name 'Internal-BI' already exists"
                            }
                        },
                        "invalid_platform_name": {
                            "summary": "Invalid platform name format",
                            "value": {
                                "detail": "Platform name must be ASCII characters without spaces"
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
                                "loc": ["body", "platform_name"],
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

    # Check if platform_name already exists
    existing_channel = APIKeyManager.get_channel_by_channel_id(db, channel_data.platform_name)
    if existing_channel:
        raise HTTPException(
            status_code=400,
            detail=f"Channel with platform name '{channel_data.platform_name}' already exists",
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
        display_name=channel.title,
        platform_name=channel.channel_id,
        platform_type=channel.access_type,
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
                    "teams": [
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
                        "total_teams": 5,
                        "active_teams": 4,
                        "total_requests": 75000,
                        "total_successful": 74250,
                        "total_failed": 750,
                        "total_cost": 75.50
                    }
                }
            ]
        }
    )

    teams: List[ChannelResponse]
    total_report: Optional[Dict[str, Any]] = Field(
        None,
        description="Total aggregated report across all teams (included when totally=true)",
    )


@router.get(
    "/channels",
    response_model=ChannelsListResponse,
    responses={
        200: {
            "description": "Teams list retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "teams_list": {
                            "summary": "List of teams with usage statistics",
                            "value": {
                                "teams": [
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
                        "teams_with_total": {
                            "summary": "Teams list with total aggregated report",
                            "value": {
                                "teams": [
                                    {
                                        "id": 1,
                                        "title": "Internal BI Team",
                                        "channel_id": "Internal-BI",
                                        "monthly_quota": 100000,
                                        "is_active": True
                                    }
                                ],
                                "total_report": {
                                    "total_teams": 5,
                                    "active_teams": 4,
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
                                "detail": "Failed to retrieve teams from database"
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
    Get teams with usage statistics (Admin only)

    Parameters:
    - channel_id: Optional channel ID to get specific channel (returns single item list)
    - active_only: Filter active teams only (default: True)
    - days: Number of days for usage statistics (default: 30)
    - totally: Include total aggregated report across all teams (default: False)

    Returns:
    - List of teams with usage data
    - Optional total report when totally=true

    Examples:
    - GET /admin/teams - List all active teams with usage
    - GET /admin/teams?team_id=1 - Get specific channel with usage
    - GET /admin/teams?totally=true - List all teams with total report
    - GET /admin/teams?active_only=false&days=7 - All teams with 7-day usage
    """
    db = get_db_session()

    # Get teams based on filter
    if channel_id:
        channel = APIKeyManager.get_channel_by_id(db, team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Channel not found")
        teams = [team]
    else:
        channels = APIKeyManager.list_all_channels(db, active_only=active_only)

    # Calculate start date for usage statistics
    start_date = datetime.utcnow() - timedelta(days=days)

    # Build response with API key prefix and usage for each team
    responses = []
    total_requests = 0
    total_successful = 0
    total_failed = 0
    total_cost = 0.0

    for channel in channels:
        # Get the channel's API key (one per team)
        api_key_obj = db.query(APIKey).filter(APIKey.channel_id == channel.id).first()

        # Get usage statistics for the channel
        try:
            usage_stats = UsageTracker.get_team_usage_stats(db, channel.id, start_date)
            # Remove team_id and team_name from usage stats (already in ChannelResponse)
            usage_stats.pop("team_id", None)
            usage_stats.pop("team_name", None)

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
                display_name=channel.title,
                platform_name=channel.channel_id,
                platform_type=channel.access_type,
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
            "total_teams": len(responses),
            "active_teams": sum(1 for r in responses if r.is_active),
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
        teams=responses,
        total_report=total_report,
    )


@router.patch(
    "/channels/{channel_id}",
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
                        "platform_exists": {
                            "summary": "Platform name already exists (when changing platform_name)",
                            "value": {
                                "detail": "Platform name 'Internal-BI-v2' is already in use by another team"
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
        team_id=team_id,
        title=channel_data.title,
        channel_id=channel_data.channel_id,
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

    if not team:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Get the channel's API key
    api_key_obj = db.query(APIKey).filter(APIKey.channel_id == channel.id).first()

    # Get usage statistics
    start_date = datetime.utcnow() - timedelta(days=days)
    try:
        usage_stats = UsageTracker.get_team_usage_stats(db, channel.id, start_date)
        usage_stats.pop("team_id", None)
        usage_stats.pop("team_name", None)
    except Exception as e:
        logger.warning(f"Failed to get usage stats for channel {channel.id}: {e}")
        usage_stats = None

    return ChannelResponse(
        id=channel.id,
        display_name=channel.title,
        platform_name=channel.channel_id,
        platform_type=channel.access_type,
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