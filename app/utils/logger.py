"""
Custom logging configuration with colorized output and dual timestamps (UTC/IR)
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import jdatetime
import pytz

from app.core.config import settings


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors, dual timestamps (UTC/IR), and structured logging"""

    # ANSI color codes
    COLORS = {
        "utc_timestamp": "\033[96m",  # Cyan
        "ir_timestamp": "\033[94m",  # Blue
        "debug": "\033[90m",  # Gray
        "info": "\033[92m",  # Green
        "warning": "\033[93m",  # Yellow
        "error": "\033[91m",  # Red
        "context": "\033[95m",  # Magenta
        "key": "\033[36m",  # Cyan
        "reset": "\033[0m",  # Reset
    }

    # Level name mapping
    LEVEL_NAMES = {
        "DEBUG": "debug",
        "INFO": "info",
        "WARNING": "warn",
        "ERROR": "error",
        "CRITICAL": "error",
    }

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and self._should_use_colors()
        self.timestamp_mode = settings.LOG_TIMESTAMP.lower()
        self.precision = settings.LOG_TIMESTAMP_PRECISION

    def _should_use_colors(self) -> bool:
        """Determine if colors should be used"""
        # Check NO_COLOR environment variable
        if os.environ.get("NO_COLOR", settings.NO_COLOR) == "1":
            return False

        # Check LOG_COLOR setting
        log_color = settings.LOG_COLOR.lower()
        if log_color == "false":
            return False
        if log_color == "true":
            return True

        # Auto mode: check if output is a TTY
        # Check if we're in Docker/K8s (usually no TTY)
        if os.path.exists("/.dockerenv") or os.environ.get("KUBERNETES_SERVICE_HOST"):
            return False

        # Check if stdout is a TTY
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def _colorize(self, text: str, color_key: str) -> str:
        """Apply color to text if colors are enabled"""
        if not self.use_colors:
            return text
        return f"{self.COLORS.get(color_key, '')}{text}{self.COLORS['reset']}"

    def _format_timestamp_utc(self, record: logging.LogRecord) -> str:
        """Format UTC timestamp"""
        dt = datetime.utcfromtimestamp(record.created)
        if self.precision == 3:
            microseconds = f"{int(record.msecs):03d}"
        else:  # 6 digits (microseconds)
            microseconds = f"{int(record.msecs * 1000):06d}"

        timestamp = f"{dt.strftime('%Y-%m-%d %H:%M:%S')}.{microseconds} UTC"
        return self._colorize(f"[{timestamp}]", "utc_timestamp")

    def _format_timestamp_ir(self, record: logging.LogRecord) -> str:
        """Format Iranian (Jalali) timestamp in Tehran timezone - Server agnostic"""
        # Convert UTC timestamp to Tehran timezone (Asia/Tehran)
        tehran_tz = pytz.timezone("Asia/Tehran")
        utc_dt = datetime.utcfromtimestamp(record.created).replace(tzinfo=pytz.utc)
        tehran_dt = utc_dt.astimezone(tehran_tz)

        # Convert to Jalali calendar
        jdt = jdatetime.datetime.fromgregorian(datetime=tehran_dt)

        if self.precision == 3:
            microseconds = f"{int(record.msecs):03d}"
        else:  # 6 digits (microseconds)
            microseconds = f"{int(record.msecs * 1000):06d}"

        # Format: YYYY-MM-DD HH:MM:SS.μs IR (NO 'J' prefix)
        timestamp = f"{jdt.strftime('%Y-%m-%d %H:%M:%S')}.{microseconds} IR"
        return self._colorize(f"[{timestamp}]", "ir_timestamp")

    def _format_level(self, levelname: str) -> str:
        """Format log level with color"""
        level = self.LEVEL_NAMES.get(levelname, levelname.lower())
        return self._colorize(f"[{level}]", level)

    def _format_context(self, record: logging.LogRecord) -> str:
        """Format context (module.component) if available"""
        # Extract context from logger name (e.g., "app.api.routes" -> "api.routes")
        if hasattr(record, "context"):
            context = record.context
        else:
            # Auto-generate context from logger name
            name_parts = record.name.split(".")
            if len(name_parts) > 1 and name_parts[0] == "app":
                context = ".".join(name_parts[1:])
            elif record.name != "root":
                context = record.name
            else:
                return ""

        if context:
            return " " + self._colorize(f"[{context}]", "context")
        return ""

    def _colorize_message(self, message: str, levelname: str) -> str:
        """Colorize message text (only for error level)"""
        if levelname in ("ERROR", "CRITICAL") and self.use_colors:
            return self._colorize(message, "error")
        return message

    def _parse_and_colorize_kvs(self, message: str) -> str:
        """Parse and colorize key=value pairs in the message"""
        if not self.use_colors or "=" not in message:
            return message

        # Split message into parts
        parts = []
        current_part = []
        i = 0

        while i < len(message):
            # Look for key=value pattern
            if message[i:].find("=") != -1:
                eq_pos = message[i:].find("=")
                # Find the start of the key (backtrack to find word boundary)
                key_start = i
                for j in range(i + eq_pos - 1, -1, -1):
                    if message[j] in (" ", "\t", "\n"):
                        key_start = j + 1
                        break
                    if j == 0:
                        key_start = 0

                # Add text before key
                if key_start > i:
                    parts.append("".join(current_part) + message[i:key_start])
                    current_part = []
                else:
                    parts.append("".join(current_part))
                    current_part = []

                # Extract key
                key_end = i + eq_pos
                key = message[key_start:key_end]

                # Extract value (handle quoted values)
                value_start = key_end + 1
                value_end = value_start

                # Check if value is quoted
                if value_start < len(message) and message[value_start] in ('"', "'"):
                    quote = message[value_start]
                    value_end = message.find(quote, value_start + 1)
                    if value_end == -1:
                        value_end = len(message)
                    else:
                        value_end += 1
                else:
                    # Find end of unquoted value
                    for j in range(value_start, len(message)):
                        if message[j] in (" ", "\t", "\n"):
                            value_end = j
                            break
                    else:
                        value_end = len(message)

                value = message[value_start:value_end]

                # Colorize and add key=value
                colored_kv = self._colorize(key, "key") + "=" + value
                parts.append(colored_kv)

                i = value_end
            else:
                current_part.append(message[i])
                i += 1

        # Add remaining text
        if current_part:
            parts.append("".join(current_part))

        return "".join(parts)

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record"""
        # Build timestamp part
        timestamp_parts = []
        if self.timestamp_mode in ("utc", "both"):
            timestamp_parts.append(self._format_timestamp_utc(record))
        if self.timestamp_mode in ("ir", "both"):
            timestamp_parts.append(self._format_timestamp_ir(record))

        timestamp_str = "".join(timestamp_parts)

        # Build level part
        level_str = self._format_level(record.levelname)

        # Build message part
        message = record.getMessage()

        # Colorize key=value pairs in message
        message = self._parse_and_colorize_kvs(message)

        # Colorize message if error level
        message = self._colorize_message(message, record.levelname)

        # Build context part (comes after message)
        context_str = self._format_context(record)

        # Combine all parts: [timestamp(s)][level] message [context] key=value...
        log_line = f"{timestamp_str}{level_str} {message}{context_str}"

        # Add exception info if present
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            log_line += f"\n{exc_text}"

        return log_line


class StructuredLogger:
    """Helper class for structured logging with key-value pairs"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _format_kvs(self, **kwargs) -> str:
        """Format key-value pairs"""
        parts = []
        for key, value in kwargs.items():
            # Convert to snake_case if needed
            key = key.replace("-", "_").replace(" ", "_").lower()

            # Quote values with spaces or special characters
            if isinstance(value, str) and (" " in value or '"' in value or "=" in value):
                value = f'"{value}"'

            parts.append(f"{key}={value}")

        return " ".join(parts)

    def debug(self, message: str, context: Optional[str] = None, **kwargs):
        """Log debug message with structured data"""
        extra = {"context": context} if context else {}
        kv_str = self._format_kvs(**kwargs) if kwargs else ""
        full_message = f"{message} {kv_str}".strip()
        self.logger.debug(full_message, extra=extra)

    def info(self, message: str, context: Optional[str] = None, **kwargs):
        """Log info message with structured data"""
        extra = {"context": context} if context else {}
        kv_str = self._format_kvs(**kwargs) if kwargs else ""
        full_message = f"{message} {kv_str}".strip()
        self.logger.info(full_message, extra=extra)

    def warning(self, message: str, context: Optional[str] = None, **kwargs):
        """Log warning message with structured data"""
        extra = {"context": context} if context else {}
        kv_str = self._format_kvs(**kwargs) if kwargs else ""
        full_message = f"{message} {kv_str}".strip()
        self.logger.warning(full_message, extra=extra)

    def error(self, message: str, context: Optional[str] = None, **kwargs):
        """Log error message with structured data"""
        extra = {"context": context} if context else {}
        kv_str = self._format_kvs(**kwargs) if kwargs else ""
        full_message = f"{message} {kv_str}".strip()
        self.logger.error(full_message, extra=extra)


def setup_logging():
    """Setup application logging with custom formatter"""

    # Create logs directory if it doesn't exist
    log_file = Path(settings.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create console formatter (with colors)
    console_formatter = ColoredFormatter(use_colors=True)

    # Create file formatter (no colors)
    file_formatter = ColoredFormatter(use_colors=False)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    console_handler.setFormatter(console_formatter)

    # File handler
    file_handler = logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers to prevent duplicates (important for uvicorn reload)
    root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

    logging.info("logging_configured")


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger for a module"""
    return StructuredLogger(logging.getLogger(name))
