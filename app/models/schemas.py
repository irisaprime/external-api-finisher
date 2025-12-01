"""
Pydantic models for request/response schemas with OpenAPI examples
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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