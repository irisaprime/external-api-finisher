"""
Pydantic models for request/response schemas with OpenAPI examples
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import MessageType


class MessageAttachment(BaseModel):
    """
    Message attachment metadata for non-text content (images, documents, voice, video).

    Attachments can be provided via URL, file ID (platform-specific), or base64-encoded data.
    The service may process certain attachment types (e.g., images with vision models).

    **Supported Types:**
    - `image`: Photos, screenshots, diagrams (processed with vision-enabled AI models)
    - `document`: PDFs, Word docs, spreadsheets (metadata only, content not processed)
    - `voice`: Audio messages (may support transcription in future)
    - `video`: Video files (metadata only)
    - `sticker`: Platform stickers (metadata only)
    - `location`: Geographic coordinates (metadata only)

    **Note:** Currently, only image attachments are fully processed by AI models with vision capabilities.
    Other types are logged but not sent to the AI service.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "image",
                    "url": "https://cdn.example.com/uploads/photo_2025_01_15.jpg",
                    "mime_type": "image/jpeg",
                    "file_size": 245760,
                },
                {
                    "type": "image",
                    "file_id": "telegram_AgACAgQAAxkBAAIC",
                    "mime_type": "image/png",
                    "file_size": 512000,
                },
                {
                    "type": "document",
                    "url": "https://docs.example.com/report_q4_2024.pdf",
                    "mime_type": "application/pdf",
                    "file_size": 1048576,
                },
                {
                    "type": "voice",
                    "data": "SGVsbG8gV29ybGQh",  # Base64 encoded audio
                    "mime_type": "audio/ogg",
                    "file_size": 32768,
                },
            ]
        }
    )

    type: MessageType = Field(
        ...,
        description="Type of attachment (image, document, voice, video, sticker, location)",
        examples=["image", "document", "voice"],
    )
    url: Optional[str] = Field(
        None,
        description="Public URL to the attachment file (HTTP/HTTPS). Used for remote files.",
        examples=[
            "https://cdn.example.com/image.jpg",
            "https://storage.example.com/doc.pdf",
        ],
    )
    file_id: Optional[str] = Field(
        None,
        description="Platform-specific file identifier (e.g., Telegram file_id). Used for platform-native file references.",
        examples=["telegram_AgACAgQAAxkBAAIC", "discord_123456789"],
    )
    mime_type: Optional[str] = Field(
        None,
        description="MIME type of the attachment (e.g., 'image/jpeg', 'application/pdf')",
        examples=["image/jpeg", "image/png", "application/pdf", "audio/ogg"],
    )
    file_size: Optional[int] = Field(
        None,
        description="File size in bytes. Used for validation and logging.",
        examples=[102400, 245760, 1048576],
        ge=0,
    )
    data: Optional[str] = Field(
        None,
        description="Base64-encoded file data for inline attachments. Alternative to URL/file_id for small files.",
        examples=["SGVsbG8gV29ybGQh", "iVBORw0KGgoAAAANSUhEUgAAAAUA..."],
    )

    @field_validator("data")
    @classmethod
    def validate_base64(cls, v):
        """Validate base64 data format"""
        if v and not v.replace("+", "").replace("/", "").replace("=", "").isalnum():
            raise ValueError("Invalid base64 data")
        return v


class IncomingMessage(BaseModel):
    """
    Incoming chat message request for processing by the AI service.

    **Architecture & Session Management:**
    - Each user maintains ONE continuous conversation per platform/channel
    - No conversation_id required - sessions are automatically managed based on `user_id`
    - Messages are persisted in the database for audit and conversation history
    - `/clear` command excludes previous messages from AI context while preserving database records
    - Platform routing is auto-detected from the API key's channel configuration

    **Usage Pattern:**
    1. External channel sends message with user_id and text
    2. Service looks up or creates session for this user on this channel
    3. Message is added to conversation history
    4. AI processes message with full conversation context
    5. Response is returned and logged

    **Commands:**
    Messages starting with `/` are treated as commands (e.g., `/clear`, `/model`, `/help`).
    Regular text messages are processed by the AI model.

    **User ID Guidelines:**
    - Must be unique within your channel/platform
    - Can be any string format: numeric IDs, UUIDs, emails, usernames
    - Same user_id always returns to the same conversation
    - Different channels maintain separate conversations even with same user_id
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "user_12345",
                    "text": "سلام، چطور می‌تونم سفارشم رو پیگیری کنم؟",
                },
                {
                    "user_id": "telegram_987654321",
                    "text": "What are the main differences between GPT-4 and Claude?",
                },
                {
                    "user_id": "customer@example.com",
                    "text": "Help me understand my invoice",
                },
                {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "text": "/clear",
                },
                {
                    "user_id": "internal_user_42",
                    "text": "/model gpt5",
                },
            ]
        }
    )

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description=(
            "Unique identifier for the user within your channel. "
            "Used for session management and conversation isolation. "
            "Can be any format: numeric ID, UUID, email, username, or custom identifier. "
            "Same user_id always returns to the same conversation on this channel."
        ),
        examples=[
            "user_12345",
            "telegram_987654321",
            "customer@example.com",
            "550e8400-e29b-41d4-a716-446655440000",
        ],
    )
    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description=(
            "Message text content to process. "
            "Can be a regular chat message or a command (starting with '/'). "
            "Commands: /clear (reset history), /model (switch AI model), /help (show available commands), /status (session info). "
            "Regular messages are sent to the AI model for processing."
        ),
        examples=[
            "سلام! چطور می‌تونم کمکتون کنم؟",
            "What is the capital of France?",
            "Explain quantum computing in simple terms",
            "/clear",
            "/model gemini",
            "/help",
        ],
    )


class BotResponse(BaseModel):
    """
    Response returned after processing a chat message.

    **Response Structure:**
    - `success`: Indicates whether the request was processed successfully
    - `response`: The AI-generated text response or error message (user-facing)
    - `model`: The AI model used to generate the response
    - `total_message_count`: Total chat messages in conversation (excludes commands)
    - `error`: Machine-readable error code when success=false

    **Success Response (success=true):**
    Contains the AI's response in the `response` field, along with metadata about the
    current model and message count. The `error` field will be null.

    **Error Response (success=false):**
    Contains a user-friendly error message in the `response` field and a machine-readable
    error code in the `error` field. The `model` and `total_message_count` may be null.

    **Conversation Tracking:**
    - `total_message_count` persists through `/clear` commands (database count)
    - Only actual chat messages and AI responses are counted
    - Commands (`/clear`, `/model`, `/help`, etc.) are NOT counted
    - Count includes both user messages and assistant responses

    **Error Codes:**
    - `rate_limit_exceeded`: User has exceeded rate limit for this channel
    - `ai_service_unavailable`: AI service is down or unreachable
    - `authentication_failed`: Invalid or missing API key
    - `quota_exceeded`: Monthly or daily quota has been reached
    - `access_denied`: User attempting to access another user's conversation
    - `invalid_model`: Requested model is not available for this channel
    - `processing_error`: Unexpected error during message processing
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "response": "سلام! من دستیار هوش مصنوعی هستم. چطور می‌تونم کمکتون کنم؟",
                    "model": "Gemini 2.0 Flash",
                    "total_message_count": 2,
                },
                {
                    "success": True,
                    "response": "Paris is the capital of France. It's known for the Eiffel Tower, the Louvre Museum, and its rich cultural history.",
                    "model": "GPT-5 Chat",
                    "total_message_count": 8,
                },
                {
                    "success": True,
                    "response": "✅ مدل به Claude Sonnet 4 تغییر یافت. حالا می‌تونید از قابلیت‌های پیشرفته‌تر استفاده کنید.",
                    "model": "Claude Sonnet 4",
                    "total_message_count": 15,
                },
                {
                    "success": True,
                    "response": "✨ تاریخچه گفتگو پاک شد! آماده شروع گفتگوی جدید هستم.",
                    "model": "DeepSeek Chat V3",
                    "total_message_count": 24,
                },
                {
                    "success": False,
                    "error": "rate_limit_exceeded",
                    "response": "⚠️ محدودیت سرعت. شما بیش از حد مجاز پیام ارسال کرده‌اید.\n\nمحدودیت: 60 پیام در دقیقه\nلطفاً چند ثانیه صبر کنید و دوباره امتحان کنید.",
                },
                {
                    "success": False,
                    "error": "ai_service_unavailable",
                    "response": "متأسفم، سرویس هوش مصنوعی در حال حاضر در دسترس نیست. لطفاً چند لحظه دیگر دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
                },
                {
                    "success": False,
                    "error": "quota_exceeded",
                    "response": "⚠️ سهمیه ماهانه شما تمام شده است. برای افزایش سهمیه با مدیر سیستم تماس بگیرید.",
                },
                {
                    "success": False,
                    "error": "access_denied",
                    "response": "❌ دسترسی رد شد. این مکالمه متعلق به کاربر دیگری است.",
                },
            ]
        }
    )

    success: bool = Field(
        ...,
        description=(
            "Indicates whether the request was processed successfully. "
            "True for successful AI responses, False for errors (rate limits, service unavailable, etc.)"
        ),
        examples=[True, False],
    )
    response: Optional[str] = Field(
        None,
        description=(
            "The response text - either AI-generated content (when success=true) "
            "or a user-friendly error message (when success=false). "
            "May include Persian/English text depending on the user's message language."
        ),
        examples=[
            "سلام! چطور می‌تونم کمکتون کنم؟",
            "Paris is the capital of France.",
            "⚠️ Rate limit exceeded. Please wait.",
        ],
    )
    model: Optional[str] = Field(
        None,
        description=(
            "User-friendly name of the AI model used to generate the response. "
            "Examples: 'Gemini 2.0 Flash', 'GPT-5 Chat', 'Claude Sonnet 4', 'DeepSeek Chat V3'. "
            "May be null in error responses."
        ),
        examples=["Gemini 2.0 Flash", "GPT-5 Chat", "Claude Sonnet 4", "DeepSeek Chat V3"],
    )
    total_message_count: Optional[int] = Field(
        None,
        description=(
            "Total number of chat messages in conversation history (user messages + AI responses). "
            "Persists through /clear commands (database count, not AI context). "
            "Commands like /clear, /model, /help are NOT counted - only actual chat messages. "
            "May be null in error responses."
        ),
        examples=[2, 8, 15, 24, 50],
        ge=0,
    )
    error: Optional[str] = Field(
        None,
        description=(
            "Machine-readable error code when success=false. Null when success=true. "
            "Use this field for programmatic error handling. "
            "Common codes: rate_limit_exceeded, ai_service_unavailable, authentication_failed, "
            "quota_exceeded, access_denied, invalid_model, processing_error."
        ),
        examples=[
            "rate_limit_exceeded",
            "ai_service_unavailable",
            "authentication_failed",
            "quota_exceeded",
            "access_denied",
        ],
    )


class ChannelConfigResponse(BaseModel):
    """Platform configuration response"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "private",
                    "available_models": ["Gemini 2.0 Flash", "GPT-5 Chat", "DeepSeek v3"],
                    "rate_limit": 60,
                    "commands": ["start", "help", "model", "models", "clear", "status"],
                    "max_history": 30,
                    "features": {"model_switching": True, "requires_auth": True},
                }
            ]
        }
    )

    type: str = Field(..., examples=["public", "private"])
    model: Optional[str] = Field(None, examples=["Gemini 2.0 Flash"])
    available_models: Optional[List[str]] = Field(
        None, examples=[["Gemini 2.0 Flash", "GPT-5 Chat", "DeepSeek v3"]]
    )
    rate_limit: int = Field(..., examples=[20, 60])
    commands: List[str] = Field(..., examples=[["start", "help", "model", "clear"]])
    max_history: int = Field(..., examples=[10, 30])
    features: Dict[str, bool] = Field(
        ..., examples=[{"model_switching": True, "requires_auth": True}]
    )


class SessionStatusResponse(BaseModel):
    """Session status response"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "user_12345",
                    "platform": "Internal-BI",
                    "access_type": "private",
                    "current_model": "Gemini 2.0 Flash",
                    "total_message_count": 24,
                    "history_length": 10,
                    "last_activity": "2025-01-15T14:30:00",
                    "uptime_seconds": 3600.5,
                    "rate_limit": 60,
                    "is_admin": False,
                }
            ]
        }
    )

    user_id: str = Field(..., examples=["user_12345", "telegram_987654"])
    channel_identifier: str = Field(..., examples=["telegram", "Internal-BI"])
    access_type: str = Field(..., examples=["public", "private"])
    current_model: str = Field(..., examples=["Gemini 2.0 Flash", "DeepSeek Chat V3"])
    total_message_count: int = Field(
        ..., examples=[24], description="Total messages ever (persists through /clear). Commands are NOT counted - only chat messages and AI responses."
    )
    history_length: int = Field(
        ..., examples=[10], description="Messages currently in AI context (resets after /clear)"
    )
    last_activity: datetime
    uptime_seconds: float = Field(..., examples=[3600.5])
    rate_limit: int = Field(..., examples=[60])
    is_admin: bool = Field(..., examples=[False])


class SessionListResponse(BaseModel):
    """Session list response"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total": 2,
                    "authenticated": True,
                    "sessions": [
                        {
                            "user_id": "user_12345",
                            "platform": "Internal-BI",
                            "total_message_count": 24,
                            "last_activity": "2025-01-15T14:30:00",
                        }
                    ],
                }
            ]
        }
    )

    total: int = Field(..., examples=[2])
    authenticated: bool = Field(..., examples=[True, False])
    sessions: List[Dict[str, Any]]


class StatsResponse(BaseModel):
    """Statistics response"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total_sessions": 150,
                    "active_sessions": 25,
                    "telegram": {"sessions": 10, "model": "Gemini 2.0 Flash"},
                    "internal": {"sessions": 15, "channels": 5},
                    "uptime_seconds": 86400.0,
                }
            ]
        }
    )

    total_sessions: int = Field(..., examples=[150])
    active_sessions: int = Field(..., examples=[25])
    telegram: Dict[str, Any]
    internal: Dict[str, Any]
    uptime_seconds: float = Field(..., examples=[86400.0])


class HealthCheckResponse(BaseModel):
    """Health check response"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "service": "Arash External API Service",
                    "version": "1.0.0",
                    "status": "healthy",
                    "platforms": {
                        "telegram": {
                            "type": "public",
                            "model": "Gemini 2.0 Flash",
                            "rate_limit": 20,
                        },
                        "internal": {
                            "type": "private",
                            "models": ["Gemini 2.0 Flash", "GPT-5 Chat", "DeepSeek v3"],
                            "rate_limit": 60,
                        },
                    },
                    "active_sessions": 25,
                    "timestamp": "2025-01-15T14:30:00",
                }
            ]
        }
    )

    service: str = Field(..., examples=["Arash External API Service"])
    version: str = Field(..., examples=["1.0.0"])
    status: str = Field(..., examples=["healthy", "degraded"])
    platforms: Dict[str, Dict[str, Any]]
    active_sessions: int = Field(..., examples=[25])
    timestamp: datetime


class ErrorResponse(BaseModel):
    """
    Standardized error response model for HTTP errors (4xx, 5xx status codes).

    This model is used for HTTP-level errors like authentication failures, validation errors,
    and server errors. It's distinct from the BotResponse error format (which uses success=false).

    **When This Model Is Used:**
    - 401 Unauthorized: Missing or invalid authentication
    - 403 Forbidden: Insufficient permissions or inactive API key
    - 404 Not Found: Resource doesn't exist (channel, user, etc.)
    - 422 Unprocessable Entity: Request validation failed
    - 429 Too Many Requests: Rate limit exceeded at HTTP level
    - 500 Internal Server Error: Unexpected server errors
    - 503 Service Unavailable: Database or AI service down

    **BotResponse vs ErrorResponse:**
    - `BotResponse` (success=false): Business logic errors within successful HTTP requests (e.g., user rate limit)
    - `ErrorResponse`: HTTP protocol errors (e.g., authentication failure, server error)

    **Fields:**
    - `success`: Always false for error responses
    - `error`: Short, machine-readable error type/category
    - `detail`: Human-readable detailed explanation
    - `timestamp`: When the error occurred (UTC)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": False,
                    "error": "authentication_required",
                    "detail": "Authentication required. Please provide an API key in the Authorization header.",
                    "timestamp": "2025-01-30T14:30:00Z",
                },
                {
                    "success": False,
                    "error": "invalid_api_key",
                    "detail": "The provided API key is invalid or has been revoked. Please check your credentials.",
                    "timestamp": "2025-01-30T14:30:00Z",
                },
                {
                    "success": False,
                    "error": "channel_not_found",
                    "detail": "Channel with ID 123 does not exist or has been deleted.",
                    "timestamp": "2025-01-30T14:30:00Z",
                },
                {
                    "success": False,
                    "error": "validation_error",
                    "detail": "Request validation failed. Please check the request body schema.",
                    "timestamp": "2025-01-30T14:30:00Z",
                },
                {
                    "success": False,
                    "error": "internal_server_error",
                    "detail": "An unexpected error occurred. Please try again later or contact support.",
                    "timestamp": "2025-01-30T14:30:00Z",
                },
                {
                    "success": False,
                    "error": "service_unavailable",
                    "detail": "The AI service is temporarily unavailable. Please try again in a few moments.",
                    "timestamp": "2025-01-30T14:30:00Z",
                },
                {
                    "success": False,
                    "error": "insufficient_permissions",
                    "detail": "You do not have permission to access this resource. Super admin access required.",
                    "timestamp": "2025-01-30T14:30:00Z",
                },
            ]
        }
    )

    success: bool = Field(
        False,
        description="Always false for error responses. Indicates the request failed at HTTP level.",
        examples=[False],
    )
    error: str = Field(
        ...,
        description=(
            "Machine-readable error type/category for programmatic error handling. "
            "Examples: authentication_required, invalid_api_key, channel_not_found, validation_error, "
            "internal_server_error, service_unavailable, insufficient_permissions."
        ),
        examples=[
            "authentication_required",
            "invalid_api_key",
            "channel_not_found",
            "validation_error",
            "insufficient_permissions",
        ],
    )
    detail: Optional[str] = Field(
        None,
        description=(
            "Human-readable detailed explanation of the error. "
            "Provides context and guidance for resolving the issue. "
            "May be displayed to end users or logged for debugging."
        ),
        examples=[
            "Authentication required. Please provide an API key in the Authorization header.",
            "The provided API key is invalid or has been revoked.",
            "Channel with ID 123 does not exist.",
        ],
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="ISO 8601 timestamp (UTC) when the error occurred. Used for logging and debugging.",
        examples=["2025-01-30T14:30:00Z", "2025-01-30T15:45:30.123456Z"],
    )