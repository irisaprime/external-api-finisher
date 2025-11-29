"""
Public API routes for external channels (clients)

TWO-TIER ACCESS CONTROL:
These endpoints are accessible to ALL valid API keys (both CHANNEL and ADMIN levels).
However, they are designed for external channels (clients) using the chatbot service.

PUBLIC ENDPOINTS (ALL VALID API KEYS):
- /v1/chat - Process chat messages

SECURITY MODEL:
- External channels (CHANNEL level) think they're using a simple chatbot API
- NO exposure of: sessions, channels, access levels, or other channels
- Complete transparency: channels don't know about our internal architecture
- Channel isolation enforced via session tagging (transparent to clients)

WHAT EXTERNAL CHANNELS SEE:
- Simple chatbot API with message in, response out
- No complexity, no admin features, no multi-tenancy visibility

WHAT THEY DON'T SEE:
- Access levels (ADMIN vs CHANNEL)
- Other channels or their usage
- Session management internals
- Platform configuration
- Admin endpoints
"""

import logging
from typing import Union

from fastapi import APIRouter, Depends

from app.api.dependencies import require_chat_access
from app.core.constants import COMMAND_DESCRIPTIONS
from app.models.database import APIKey
from app.models.schemas import (
    BotResponse,
    IncomingMessage,
)
from app.services.message_processor import message_processor
from app.services.channel_manager import channel_manager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post(
    "/chat",
    response_model=BotResponse,
    responses={
        200: {
            "description": "Successful chat response",
            "content": {
                "application/json": {
                    "examples": {
                        "first_message": {
                            "summary": "First message in conversation",
                            "value": {
                                "success": True,
                                "response": "سلام! چطور می‌تونم کمکتون کنم؟",
                                "model": "Gemini 2.0 Flash",
                                "total_message_count": 2,
                            },
                        },
                        "continuing_conversation": {
                            "summary": "Continuing an existing conversation",
                            "value": {
                                "success": True,
                                "response": "البته! فرآیند خرید خیلی ساده است. ابتدا محصول مورد نظر را انتخاب کنید...",
                                "model": "DeepSeek Chat V3",
                                "total_message_count": 12,
                            },
                        },
                        "after_clear": {
                            "summary": "After using /clear command",
                            "value": {
                                "success": True,
                                "response": "تاریخچه گفتگو پاک شد. چطور می‌تونم کمکتون کنم؟",
                                "model": "GPT-4o Mini",
                                "total_message_count": 26,
                            },
                        },
                        "rate_limit_exceeded": {
                            "summary": "Rate limit exceeded",
                            "value": {
                                "success": False,
                                "error": "rate_limit_exceeded",
                                "response": "⚠️ محدودیت سرعت. لطفاً قبل از ارسال پیام بعدی کمی صبر کنید.\n\nمحدودیت: 60 پیام در دقیقه",
                            },
                        },
                        "ai_service_error": {
                            "summary": "AI service unavailable",
                            "value": {
                                "success": False,
                                "error": "ai_service_unavailable",
                                "response": "متأسفم، سرویس هوش مصنوعی در حال حاضر در دسترس نیست. لطفاً چند لحظه دیگر دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
                            },
                        },
                        "access_denied": {
                            "summary": "API key trying to access another key's user",
                            "value": {
                                "success": False,
                                "error": "access_denied",
                                "response": "❌ دسترسی رد شد. این مکالمه متعلق به API key دیگری است.",
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "Bad request - Invalid input data",
            "content": {
                "application/json": {
                    "examples": {
                        "empty_text": {
                            "summary": "Empty message text",
                            "value": {
                                "detail": "Message text cannot be empty"
                            }
                        },
                        "empty_user_id": {
                            "summary": "Empty user ID",
                            "value": {
                                "detail": "User ID cannot be empty"
                            }
                        }
                    }
                }
            },
        },
        401: {
            "description": "Authentication required - No API key provided",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authentication required. Please provide an API key in the Authorization header."
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - Invalid or inactive API key",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_key": {
                            "summary": "Invalid API key",
                            "value": {
                                "detail": "Invalid API key. Please check your credentials."
                            }
                        },
                        "inactive_key": {
                            "summary": "Inactive API key",
                            "value": {
                                "detail": "API key is inactive or revoked"
                            }
                        },
                        "expired_key": {
                            "summary": "Expired API key",
                            "value": {
                                "detail": "API key has expired"
                            }
                        }
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
                                "loc": ["body", "user_id"],
                                "msg": "field required",
                                "type": "value_error.missing"
                            },
                            {
                                "loc": ["body", "text"],
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
                        "api_key_validation_error": {
                            "summary": "Error validating API key",
                            "value": {
                                "detail": "Error validating API key"
                            }
                        },
                        "database_error": {
                            "summary": "Database connection error",
                            "value": {
                                "detail": "Database error occurred"
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
        503: {
            "description": "Service unavailable - AI service or database is down",
            "content": {
                "application/json": {
                    "examples": {
                        "ai_service_down": {
                            "summary": "AI service unavailable",
                            "value": {
                                "success": False,
                                "error": "service_unavailable",
                                "response": "سرویس هوش مصنوعی در حال حاضر در دسترس نیست."
                            }
                        },
                        "database_down": {
                            "summary": "Database unavailable",
                            "value": {
                                "detail": "Database service is currently unavailable"
                            }
                        }
                    }
                }
            },
        },
    },
)
async def chat(
    message: IncomingMessage,
    auth: Union[str, APIKey] = Depends(require_chat_access),
):
    """
    Process a chat message - **AUTHENTICATION REQUIRED**.

    ## Security Update (CRITICAL)
    **Authentication is now MANDATORY for all requests.**
    - Telegram bot: Must use TELEGRAM_SERVICE_KEY
    - External channels: Must use their channel API keys
    - Unauthenticated requests: REJECTED with 401

    ## Authentication Modes

    ### 1. TELEGRAM MODE (Telegram bot service):
    - Telegram bot uses TELEGRAM_SERVICE_KEY in Authorization header
    - Platform="telegram", no channel_id
    - Session keys: telegram:conversation_id

    ### 2. CHANNEL MODE (External authenticated channels):
    - External channels use their channel API keys
    - Platform auto-detected from channel.channel_id
    - Session keys: channel_id:channel_id:conversation_id (channel isolation enforced)

    ## Single Conversation Per User
    - Each user has ONE conversation per platform/channel
    - No conversation_id needed - sessions are based on user_id
    - /clear command excludes previous messages from AI context but keeps in database

    ## Examples

    ### TELEGRAM BOT REQUEST:
    ```http
    Authorization: Bearer <TELEGRAM_SERVICE_KEY>
    ```
    ```json
    {
      "user_id": "telegram_user_12345",
      "text": "سلام، چطوری؟"
    }
    ```

    ### EXTERNAL CHANNEL REQUEST:
    ```http
    Authorization: Bearer ark_1234567890abcdef
    ```
    ```json
    {
      "user_id": "user123",
      "text": "سلام، چطوری؟"
    }
    ```
    **Each user has one continuous conversation** - no conversation_id needed.

    ## Security
    - Telegram traffic: Authenticated and logged as [TELEGRAM]
    - Channel traffic: Authenticated and logged as [CHANNEL]
    - Unauthorized traffic: Blocked with 401/403
    - Super admins can now track ALL API usage
    """
    # Determine mode based on authentication type
    if auth == "telegram":
        # TELEGRAM MODE: Telegram bot service
        channel_identifier = "telegram"
        channel_id = None
        api_key_id = None
        api_key_prefix = None

        logger.info(f"[TELEGRAM] bot_request user_id={message.user_id}")
    else:
        # CHANNEL MODE: Authenticated external channel
        channel_identifier = auth.channel.channel_id
        channel_id = auth.channel_id
        api_key_id = auth.id
        api_key_prefix = auth.key_prefix

        logger.info(
            f"[CHANNEL] chat_request channel={channel_identifier} channel_id={channel_id} user_id={message.user_id}"
        )

    # Process message (handles both modes)
    return await message_processor.process_message_simple(
        channel_identifier=channel_identifier,
        channel_id=channel_id,
        api_key_id=api_key_id,
        api_key_prefix=api_key_prefix,
        user_id=message.user_id,
        text=message.text,
    )


@router.get(
    "/commands",
    responses={
        200: {
            "description": "List of available commands",
            "content": {
                "application/json": {
                    "examples": {
                        "telegram_commands": {
                            "summary": "Telegram (public) commands",
                            "value": {
                                "success": True,
                                "platform": "telegram",
                                "commands": [
                                    {
                                        "command": "start",
                                        "description": "شروع ربات و دریافت پیام خوش‌آمدگویی",
                                        "usage": "/start",
                                    },
                                    {
                                        "command": "help",
                                        "description": "نمایش راهنمای استفاده و دستورات موجود",
                                        "usage": "/help",
                                    },
                                    {
                                        "command": "clear",
                                        "description": "پاک کردن تاریخچه گفتگو و شروع مجدد",
                                        "usage": "/clear",
                                    },
                                ],
                            },
                        },
                        "internal_commands": {
                            "summary": "Internal (private) commands",
                            "value": {
                                "success": True,
                                "platform": "Internal-BI",
                                "commands": [
                                    {
                                        "command": "start",
                                        "description": "شروع ربات و دریافت پیام خوش‌آمدگویی",
                                        "usage": "/start",
                                    },
                                    {
                                        "command": "help",
                                        "description": "نمایش راهنمای استفاده و دستورات موجود",
                                        "usage": "/help",
                                    },
                                    {
                                        "command": "model",
                                        "description": "تغییر مدل هوش مصنوعی",
                                        "usage": "/model",
                                    },
                                    {
                                        "command": "models",
                                        "description": "نمایش لیست تمام مدل‌های موجود",
                                        "usage": "/models",
                                    },
                                    {
                                        "command": "clear",
                                        "description": "پاک کردن تاریخچه گفتگو و شروع مجدد",
                                        "usage": "/clear",
                                    },
                                    {
                                        "command": "status",
                                        "description": "نمایش وضعیت نشست و اطلاعات جاری",
                                        "usage": "/status",
                                    },
                                ],
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": "Authentication required - No API key provided",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authentication required. Please provide an API key in the Authorization header."
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - Invalid or inactive API key",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_key": {
                            "summary": "Invalid API key",
                            "value": {
                                "detail": "Invalid API key. Please check your credentials."
                            }
                        },
                        "inactive_key": {
                            "summary": "Inactive API key",
                            "value": {
                                "detail": "API key is inactive or revoked"
                            }
                        }
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "examples": {
                        "api_key_validation_error": {
                            "summary": "Error validating API key",
                            "value": {
                                "detail": "Error validating API key"
                            }
                        },
                        "platform_error": {
                            "summary": "Error retrieving platform configuration",
                            "value": {
                                "detail": "Failed to retrieve platform configuration"
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
async def get_commands(
    auth: Union[str, APIKey] = Depends(require_chat_access),
):
    """
    Get available commands with Persian descriptions - **AUTHENTICATION REQUIRED**.

    ## Security Update (CRITICAL)
    **Authentication is now MANDATORY for all requests.**
    - Telegram bot: Must use TELEGRAM_SERVICE_KEY
    - External channels: Must use their channel API keys
    - Unauthenticated requests: REJECTED with 401

    ## Authentication Modes

    ### 1. TELEGRAM MODE:
    - Telegram bot uses TELEGRAM_SERVICE_KEY
    - Returns Telegram platform commands

    ### 2. CHANNEL MODE:
    - External channels use their channel API keys
    - Returns commands for authenticated channel's platform

    ## Response Format
    ```json
    {
      "success": true,
      "platform": "telegram",
      "commands": [
        {
          "command": "start",
          "description": "شروع ربات و دریافت پیام خوش‌آمدگویی",
          "usage": "/start"
        }
      ]
    }
    ```

    ## Security
    - Telegram traffic: Logged as [TELEGRAM]
    - Channel traffic: Logged as [CHANNEL]
    - Unauthorized traffic: Blocked with 401/403
    """
    # Determine channel based on authentication type
    if auth == "telegram":
        # TELEGRAM MODE: Telegram bot service
        channel_identifier = "telegram"
        logger.info("[TELEGRAM] commands_request platform=telegram")
    else:
        # CHANNEL MODE: Authenticated external channel
        channel_identifier = auth.channel.channel_id
        logger.info(f"[CHANNEL] commands_request channel={channel_identifier} channel_id={auth.channel_id}")

    # Get allowed commands for this channel
    allowed_commands = channel_manager.get_allowed_commands(channel_identifier)

    # Build command list with descriptions
    commands_list = []
    for cmd in allowed_commands:
        if cmd in COMMAND_DESCRIPTIONS:
            commands_list.append(
                {"command": cmd, "description": COMMAND_DESCRIPTIONS[cmd], "usage": f"/{cmd}"}
            )

    return {"success": True, "platform": channel_identifier, "commands": commands_list}