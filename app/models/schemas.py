"""
Pydantic models for request/response schemas with OpenAPI examples
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import MessageType


class MessageAttachment(BaseModel):
    """Message attachment model"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "image",
                    "url": "https://example.com/image.jpg",
                    "file_id": "file_12345",
                    "mime_type": "image/jpeg",
                    "file_size": 102400,
                }
            ]
        }
    )

    type: MessageType
    url: Optional[str] = None
    file_id: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    data: Optional[str] = None  # Base64 encoded data

    @field_validator("data")
    @classmethod
    def validate_base64(cls, v):
        """Validate base64 data format"""
        if v and not v.replace("+", "").replace("/", "").replace("=", "").isalnum():
            raise ValueError("Invalid base64 data")
        return v


class IncomingMessage(BaseModel):
    """
    Simplified incoming message for chat endpoint.

    Architecture:
    - Each user has ONE conversation per platform/channel (no conversation_id needed)
    - Messages are persisted in database
    - /clear command excludes previous messages from AI context (but keeps in DB)
    - Platform auto-detected from API key's channel.channel_id
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "user_12345",
                    "text": "سلام، چطوری؟",
                },
                {
                    "user_id": "telegram_987654",
                    "text": "What is the weather like today?",
                },
                {
                    "user_id": "customer_001",
                    "text": "Help me with my order",
                },
            ]
        }
    )

    user_id: str = Field(
        ...,
        description="Unique user identifier (client-provided, e.g., telegram ID, customer ID, email)",
        examples=["user_12345", "telegram_987654", "customer@example.com"],
    )
    text: str = Field(
        ...,
        description="Message text content",
        examples=["سلام!", "Hello, how can I help?", "/clear"],
    )


class BotResponse(BaseModel):
    """
    Bot response model for chat endpoint.

    Architecture:
    - Each user has ONE conversation per platform/channel (no conversation_id)
    - total_message_count shows total messages in history (persists through /clear)
    - /clear removes messages from AI context but keeps in database
    - Commands (e.g., /model, /help, /clear) are NOT counted in total_message_count
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "response": "سلام! چطور می‌تونم کمکتون کنم؟",
                    "model": "Gemini 2.0 Flash",
                    "total_message_count": 2,
                },
                {
                    "success": True,
                    "response": "برای تغییر مدل، از دستور /model استفاده کنید.",
                    "model": "DeepSeek Chat V3",
                    "total_message_count": 10,
                },
                {
                    "success": False,
                    "error": "rate_limit_exceeded",
                    "response": "⚠️ محدودیت سرعت. لطفاً قبل از ارسال پیام بعدی کمی صبر کنید.\n\nمحدودیت: 60 پیام در دقیقه",
                },
                {
                    "success": False,
                    "error": "ai_service_unavailable",
                    "response": "متأسفم، سرویس هوش مصنوعی در حال حاضر در دسترس نیست.",
                },
            ]
        }
    )

    success: bool = Field(..., description="Request success status", examples=[True, False])
    response: Optional[str] = Field(
        None,
        description="Response text from AI or error message",
        examples=["سلام! چطور می‌تونم کمکتون کنم؟"],
    )
    model: Optional[str] = Field(
        None,
        description="User-friendly AI model name currently in use",
        examples=["Gemini 2.0 Flash", "DeepSeek Chat V3", "GPT-4o Mini"],
    )
    total_message_count: Optional[int] = Field(
        None,
        description="Total messages in conversation history (user + assistant). Persists through /clear. NOTE: Commands (e.g., /model, /help, /clear) are NOT included in this count - only actual chat messages and AI responses.",
        examples=[2, 10, 24],
    )
    error: Optional[str] = Field(
        None,
        description="Error code if success=false",
        examples=["rate_limit_exceeded", "ai_service_unavailable", "authentication_failed"],
    )


class PlatformConfigResponse(BaseModel):
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
    platform: str = Field(..., examples=["telegram", "Internal-BI"])
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
    """Error response model"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": False,
                    "error": "Authentication required",
                    "detail": "No valid API key provided",
                    "timestamp": "2025-01-15T14:30:00",
                },
                {
                    "success": False,
                    "error": "Invalid API key",
                    "detail": "The provided API key is invalid or has been revoked",
                    "timestamp": "2025-01-15T14:30:00",
                },
            ]
        }
    )

    success: bool = Field(False, examples=[False])
    error: str = Field(
        ..., examples=["Authentication required", "Invalid API key", "Channel not found"]
    )
    detail: Optional[str] = Field(None, examples=["No valid API key provided"])
    timestamp: datetime = Field(default_factory=datetime.utcnow)