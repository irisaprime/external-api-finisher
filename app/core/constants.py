"""
Application constants and messages
"""

from enum import Enum


class Platform(str, Enum):
    """Supported messaging platforms"""

    TELEGRAM = "telegram"
    INTERNAL = "internal"


class MessageType(str, Enum):
    """Types of messages"""

    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    VOICE = "voice"
    VIDEO = "video"
    STICKER = "sticker"
    LOCATION = "location"
    COMMAND = "command"


class PlatformType(str, Enum):
    """Platform access types"""

    PUBLIC = "public"
    PRIVATE = "private"


# Model Aliases for easier switching
# Maps short aliases to FRIENDLY NAMES (not technical IDs)
# The resolve_model_name() function will convert friendly names to technical IDs
MODEL_ALIASES = {
    # Claude models (Internal only)
    "claude": "Claude Sonnet 4",
    "claude-4": "Claude Sonnet 4",
    "sonnet": "Claude Sonnet 4",
    "opus": "Claude Opus 4.5",
    # GPT models
    "gpt": "GPT-5 Chat",
    "gpt5": "GPT-5 Chat",
    "gpt-5": "GPT-5 Chat",
    "gpt4": "GPT-4.1",
    "gpt-4": "GPT-4.1",
    "gpt4-mini": "GPT-4o Mini",
    "mini": "GPT-4o Mini",
    "web": "GPT-4o Search Preview",
    "search": "GPT-4o Search Preview",
    "o1": "O1",
    # Gemini models (Available on Telegram)
    "gemini": "Gemini 2.5 Flash",
    "gemini-2.5": "Gemini 2.5 Flash",
    "gemini-2": "Gemini 2.0 Flash",
    "flash": "Gemini 2.0 Flash",
    "flash-2": "Gemini 2.0 Flash",
    "flash-2.5": "Gemini 2.5 Flash",
    "gemma": "Gemma 3 1B",
    # Other models
    "grok": "Grok 4",
    "deepseek": "DeepSeek Chat V3",
    "deep": "DeepSeek Chat V3",
    "llama": "Llama 4 Maverick",
}

# Telegram-specific aliases (for public users)
# Maps short aliases to FRIENDLY NAMES
TELEGRAM_MODEL_ALIASES = {
    "gemini": "Gemini 2.5 Flash",
    "gemini-2.5": "Gemini 2.5 Flash",
    "gemini-2": "Gemini 2.0 Flash",
    "flash": "Gemini 2.0 Flash",
    "flash-2": "Gemini 2.0 Flash",
    "flash-2.5": "Gemini 2.5 Flash",
    "gemma": "Gemma 3 1B",
    "deepseek": "DeepSeek Chat V3",
    "deep": "DeepSeek Chat V3",
    "mini": "GPT-4o Mini",
    "gpt-mini": "GPT-4o Mini",
}


# Persian Messages
MESSAGES_FA = {
    # Welcome messages
    "welcome_internal": """🤖 **خوش آمدید به ربات چت‌بات سازمانی آرش!**

شما به امکانات پیشرفته زیر دسترسی دارید:
• استفاده از چندین مدل هوش مصنوعی (مثل Claude، GPT-4 و غیره)
• امکان تغییر مدل با دستور /model
• تاریخچه گفت‌وگوی گسترده‌تر
• و غیره.

**مدل فعلی:** {model}

برای دیدن همه‌ی دستورات موجود، دستور /help را تایپ کنید.""",
    "welcome_internal_admin": """

👑 شما دسترسی مدیریتی (ادمین) دارید.""",
    "welcome_telegram": """🤖 **خوش آمدید به ربات آرش!**

من یک دستیار هوش مصنوعی هستم و اینجا هستم تا به سوالات شما کمک کنم.

**مدل:** {model}
**محدودیت سرعت:** {rate_limit} پیام در دقیقه

برای دیدن دستورات موجود، دستور /help را تایپ کنید.""",
    # Error messages
    "error_rate_limit": "⚠️ محدودیت سرعت ({rate_limit} پیام/دقیقه). لطفاً کمی صبر کنید.",
    "error_auth_failed": "❌ احراز هویت ناموفق. لطفاً کلید API معتبر ارائه دهید.",
    "error_processing": "❌ متأسفم، خطایی در پردازش پیام شما رخ داد. لطفاً دوباره تلاش کنید.",
    "error_image_processing": "❌ نتوانستم تصویر را پردازش کنم. لطفاً دوباره تلاش کنید.",
    "error_image_too_large": "❌ تصویر خیلی بزرگ است. حداکثر حجم {max_size}MB است.\nحجم تصویر شما: {actual_size:.1f}MB",
    "error_no_photo": "❌ هیچ تصویری در پیام یافت نشد.",
    "error_timeout": "⏱️ درخواست به پایان زمان رسید. ممکن است تصویر خیلی بزرگ باشد یا سرویس کند باشد. لطفاً دوباره تلاش کنید.",
    "error_generic": "❌ متأسفم، خطایی رخ داد. لطفاً بعداً تلاش کنید.",
    # Command not available
    "command_not_available_telegram": "❌ دستور `/{command}` در تلگرام در دسترس نیست.",
    "command_not_available_platform": "❌ دستور `/{command}` در {platform} در دسترس نیست.\n\n**دستورات موجود:**\n{commands}",
    "command_unknown": "❓ دستور ناشناخته: /{command}\nبرای دیدن دستورات موجود /help را تایپ کنید.",
    # Model switching
    "model_switch_not_available": "❌ تغییر مدل امکان‌پذیر نیست.\nشما از **{model}** استفاده می‌کنید",
    "model_current": "**مدل فعلی:** {model}",
    "model_switched": "✅ به **{model}** تغییر یافت",
    "model_invalid": "❌ مدل نامعتبر: `{model}`",
    # Session
    "session_cleared": "✨ تاریخچه گفت‌وگو پاک شد! شروع تازه.",
    "session_no_history": "هنوز گفت‌وگویی برای خلاصه کردن وجود ندارد!",
    # Only internal
    "internal_only": "❌ این قابلیت فقط برای کاربران داخلی در دسترس است.",
}


# English Messages (fallback)
MESSAGES_EN = {
    "welcome_internal": """🤖 **Welcome to Arash Organizational Chatbot!**

You have access to advanced features:
• Multiple AI models (Claude, GPT-4, etc.)
• Model switching with /model command
• Extended conversation history
• And more.

**Current model:** {model}

Type /help to see all available commands.""",
    "welcome_internal_admin": """

👑 You have admin access.""",
    "welcome_telegram": """🤖 **Welcome to Arash Bot!**

I'm an AI assistant here to help answer your questions.

**Model:** {model}
**Rate limit:** {rate_limit} messages/minute

Type /help to see available commands.""",
    "error_rate_limit": "⚠️ Rate limit exceeded ({rate_limit} msg/min). Please wait.",
    "error_auth_failed": "❌ Authentication failed. Please provide valid API key.",
    "error_processing": "❌ Sorry, an error occurred processing your message. Please try again.",
    "error_image_processing": "❌ Couldn't process the image. Please try again.",
    "error_image_too_large": "❌ Image too large. Maximum size is {max_size}MB.\nYour image: {actual_size:.1f}MB",
    "error_no_photo": "❌ No photo found in message.",
    "error_timeout": "⏱️ Request timed out. Image might be too large or service is slow. Please try again.",
    "error_generic": "❌ Sorry, an error occurred. Please try again later.",
    "command_not_available_telegram": "❌ Command `/{command}` is not available on Telegram.",
    "command_not_available_platform": "❌ Command `/{command}` is not available on {platform}.\n\n**Available commands:**\n{commands}",
    "command_unknown": "❓ Unknown command: /{command}\nType /help to see available commands.",
    "model_switch_not_available": "❌ Model switching not available.\nYou're using: **{model}**",
    "model_current": "**Current model:** {model}",
    "model_switched": "✅ Switched to **{model}**",
    "model_invalid": "❌ Invalid model: `{model}`",
    "session_cleared": "✨ Conversation history cleared! Starting fresh.",
    "session_no_history": "No conversation to summarize yet!",
    "internal_only": "❌ This feature is only available for internal users.",
}


# Command Descriptions
COMMAND_DESCRIPTIONS = {
    "start": "شروع ربات و دریافت پیام خوش‌آمدگویی",
    "help": "نمایش دستورات موجود",
    "status": "نمایش وضعیت نشست",
    "clear": "پاک کردن تاریخچه گفت‌وگو",
    "model": "تغییر مدل هوش مصنوعی",
    "models": "لیست مدل‌های موجود",
    "settings": "تنظیمات کاربر",
}


# HTTP Status Messages
HTTP_STATUS_MESSAGES = {
    401: "Unauthorized - Invalid or missing authentication",
    403: "Forbidden - Access denied",
    404: "Not Found - Resource does not exist",
    429: "Too Many Requests - Rate limit exceeded",
    500: "Internal Server Error - Something went wrong",
    503: "Service Unavailable - Service temporarily unavailable",
}
