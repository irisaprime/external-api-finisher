"""
Database initialization with Alembic migration support.
This module ensures database schema is up-to-date using Alembic migrations.
"""

import logging
import subprocess
import time
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app.core.config import settings

logger = logging.getLogger(__name__)


def check_alembic_history() -> bool:
    """
    Check if Alembic migration history table exists.

    Returns:
        True if alembic_version table exists, False otherwise
    """
    from app.models.database import get_database

    try:
        db = get_database()
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        return "alembic_version" in tables
    except Exception as e:
        logger.error(f"Error checking Alembic history: {e}")
        return False


def get_current_revision() -> str:
    """
    Get current Alembic revision from database.

    Returns:
        Current revision ID or empty string if no revision
    """
    from app.models.database import get_database

    try:
        db = get_database()
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            return row[0] if row else ""
    except Exception as e:
        logger.error(f"Error getting current revision: {e}")
        return ""


def run_migrations() -> bool:
    """
    Run Alembic migrations to bring database up-to-date.

    Returns:
        True if migrations successful, False otherwise
    """
    try:
        # Get project root directory
        project_root = Path(__file__).parent.parent.parent

        logger.info("Running Alembic migrations")

        # Run alembic upgrade head (use python -m for container compatibility)
        result = subprocess.run(
            ["python", "-m", "alembic", "upgrade", "head"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            logger.info("Migrations completed successfully")
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        logger.info(f"Migration: {line}")
            return True
        else:
            logger.error(f"Migration failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Migration timeout after 60 seconds")
        return False
    except FileNotFoundError:
        logger.error("Python/Alembic command not found")
        return False
    except Exception as e:
        logger.error(f"Migration error: {e}")
        return False


def initialize_database() -> bool:
    """
    Initialize database with Alembic migrations.
    Automatically runs latest migrations on startup.

    Returns:
        True if database initialized successfully, False otherwise
    """
    try:
        logger.info("=" * 60)
        logger.info("Database Initialization")
        logger.info("=" * 60)

        # Wait for database
        from app.models.database import get_database

        for attempt in range(30):
            try:
                db = get_database()
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info(f"Database ready (attempt {attempt + 1})")
                break
            except OperationalError:
                if attempt < 29:
                    time.sleep(2)
                else:
                    logger.error("Database not ready after 30 attempts")
                    return False

        # Run migrations (alembic upgrade head handles both initial and updates)
        logger.info("Running migrations...")
        if not run_migrations():
            logger.error("Migrations failed")
            return False

        logger.info("Database initialized successfully")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.info("=" * 60)
        return False


def create_logs_directory():
    """
    Create logs directory if it doesn't exist.
    This is separate from database initialization.
    """
    try:
        log_file = Path(settings.LOG_FILE)
        log_dir = log_file.parent

        if not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created logs directory: {log_dir}")

        return True
    except Exception as e:
        logger.warning(f"Could not create logs directory: {e}")
        return False