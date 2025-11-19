#!/usr/bin/env python3
"""
Test script to demonstrate the new logging standard with colorized output
"""
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.utils.logger import get_structured_logger, setup_logging


def main():
    """Test all logging features"""
    # Setup logging
    setup_logging()

    # Get logger
    logger = logging.getLogger("app.test.demo")

    # Get structured logger
    slog = get_structured_logger("app.api.test")

    print("=" * 80)
    print("LOGGING STANDARD DEMONSTRATION")
    print("=" * 80)
    print(f"Timestamp Mode: {settings.LOG_TIMESTAMP}")
    print(f"Color Mode: {settings.LOG_COLOR}")
    print(f"Precision: {settings.LOG_TIMESTAMP_PRECISION} digits")
    print("=" * 80)
    print()

    # Test 1: Simple messages with different log levels
    print("1. Different Log Levels:")
    print("-" * 80)
    logger.debug("debug_message_example")
    logger.info("server_started port=8080")
    logger.warning("rate_limit_approaching")
    logger.error('payment_failed user_id=5678 error="card declined"')
    print()

    # Test 2: Messages with context
    print("2. Messages with Context:")
    print("-" * 80)
    slog.info("auth_success", context="api.auth", user_id=1234, method="jwt")
    slog.info("query_executed", context="db.postgres", query="SELECT * FROM users", duration_ms=45)
    slog.error(
        "connection_failed", context="redis.client", host="localhost", port=6379, error="timeout"
    )
    print()

    # Test 3: Structured logging with various data types
    print("3. Structured Key-Value Pairs:")
    print("-" * 80)
    slog.info(
        "api_request",
        request_id="req-123456",
        method="POST",
        path="/api/v1/message",
        status_code=200,
        duration_ms=125,
    )

    slog.info(
        "user_action", user_id=9999, action="login", ip="192.168.1.100", user_agent="Mozilla/5.0"
    )

    slog.debug("cache_hit", key="user:profile:1234", ttl_seconds=3600, hit_rate=0.95)
    print()

    # Test 4: Error with structured data
    print("4. Error Messages (Red):")
    print("-" * 80)
    slog.error(
        "database_error",
        context="db.postgres",
        query="INSERT INTO users",
        error="duplicate key violation",
        table="users",
        constraint="users_email_key",
    )

    slog.error(
        "api_timeout",
        context="external.ai_service",
        url="https://api.example.com/v1/chat",
        timeout_ms=5000,
        retry_count=3,
    )
    print()

    # Test 5: Complex scenarios
    print("5. Real-World Scenarios:")
    print("-" * 80)

    # Telegram message processing
    slog.info(
        "telegram_message_received",
        context="telegram.handler",
        conversation_id=123456789,
        user_id=987654321,
        message_type="text",
        length=250,
    )

    slog.info(
        "ai_request_sent",
        context="ai.client",
        model="google/gemini-2.0-flash-001",
        tokens=150,
        temperature=0.7,
        request_id="ai-req-789",
    )

    slog.info(
        "ai_response_received",
        context="ai.client",
        model="google/gemini-2.0-flash-001",
        tokens=420,
        duration_ms=1234,
        request_id="ai-req-789",
        cost_usd=0.0023,
    )

    # Rate limiting
    slog.warning(
        "rate_limit_warning",
        context="session.manager",
        platform="telegram",
        conversation_id=123456789,
        current_requests=18,
        limit=20,
        window="1m",
    )

    # Session management
    slog.debug(
        "session_created",
        context="session.manager",
        session_key="telegram:1:123456789",
        model="google/gemini-2.0-flash-001",
        max_history=10,
    )

    slog.debug(
        "session_cleanup",
        context="session.manager",
        expired_count=5,
        total_sessions=42,
        cleanup_duration_ms=12,
    )
    print()

    # Test 6: Messages with spaces in values (should be quoted)
    print("6. Quoted Values (spaces and special chars):")
    print("-" * 80)
    slog.info(
        "user_registration",
        email="user@example.com",
        name="John Doe",
        company="Tech Corp Inc.",
        role="Senior Developer",
    )

    slog.error(
        "validation_error",
        field="password",
        error="must contain at least 8 characters",
        provided_value="abc123",
    )
    print()

    # Test 7: Exception handling
    print("7. Exception with Stack Trace:")
    print("-" * 80)
    try:
        _ = 1 / 0
    except Exception:
        logger.error('calculation_failed error="division by zero"', exc_info=True)
    print()

    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    print()
    print("Logging Features Demonstrated:")
    print("  ✓ Dual timestamps (UTC + Iranian/Jalali)")
    print("  ✓ NO 'J' prefix in Iranian dates")
    print("  ✓ Color-coded log levels")
    print("  ✓ Color-coded context blocks")
    print("  ✓ Color-coded key=value pairs (keys in cyan)")
    print("  ✓ Automatic value quoting for spaces/special chars")
    print("  ✓ snake_case enforcement for keys")
    print("  ✓ Microsecond precision")
    print("  ✓ Error messages in red (bracket + message)")
    print("  ✓ Stack traces for exceptions")
    print()
    print(f"Log file location: {settings.LOG_FILE}")
    print()


if __name__ == "__main__":
    main()
