#!/usr/bin/env python3
"""
Demo script to show different LOG_TIMESTAMP modes
Run this to see how UTC, IR, and both modes work
"""
import os
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import after path setup
from app.utils.logger import setup_logging, get_structured_logger
from app.core import config

def demo_mode(mode: str):
    """Demonstrate a specific timestamp mode"""
    print(f"\n{'='*80}")
    print(f"MODE: LOG_TIMESTAMP={mode.upper()}")
    print('='*80)

    # Update settings temporarily
    config.settings.LOG_TIMESTAMP = mode

    # Re-setup logging with new mode
    setup_logging()

    # Get logger
    logger = logging.getLogger("app.demo")
    slog = get_structured_logger("app.api.demo")

    # Test different log levels
    logger.info("server_started port=8080")
    slog.info("auth_success", context="api.auth", user_id=1234, method="jwt")
    logger.warning("rate_limit_approaching threshold=80%")
    slog.error("connection_failed", context="db.postgres",
               error="timeout", duration_ms=5000)
    print()

def main():
    """Run demo for all timestamp modes"""
    print("\n" + "="*80)
    print("TIMESTAMP MODE DEMONSTRATION")
    print("="*80)
    print("\nThis demo shows how different LOG_TIMESTAMP modes work:")
    print("  - utc:  Show only UTC timestamp")
    print("  - ir:   Show only Iranian (Jalali) timestamp")
    print("  - both: Show both UTC and Iranian timestamps")
    print("\nYou can change the mode in your .env file:")
    print("  LOG_TIMESTAMP=utc   # or ir, or both")
    print("="*80)

    # Demo each mode
    demo_mode("utc")
    demo_mode("ir")
    demo_mode("both")

    print("="*80)
    print("DEMO COMPLETE")
    print("="*80)
    print("\nTo use a specific mode:")
    print("  1. Edit your .env file")
    print("  2. Set LOG_TIMESTAMP=utc (or ir, or both)")
    print("  3. Restart your application")
    print("\nCurrent setting in .env: LOG_TIMESTAMP=both")
    print()

if __name__ == "__main__":
    main()
