"""
Usage Tracking Service
Tracks API usage, enforces quotas, and provides usage analytics.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.name_mapping import get_friendly_model_name
from app.models.database import APIKey, UsageLog

logger = logging.getLogger(__name__)


class UsageTracker:
    """Tracks and manages API usage for channels and API keys"""

    @staticmethod
    def log_usage(
        db: Session,
        api_key_id: int,
        channel_id: int,
        session_id: str,
        platform: str,
        model_used: str,
        success: bool,
        response_time_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> UsageLog:
        """
        Log an API usage event.

        Args:
            db: Database session
            api_key_id: API key ID
            channel_id: Channel ID
            session_id: Session identifier (masked)
            platform: Platform name
            model_used: Model name (will be converted to friendly name)
            success: Whether the request was successful
            response_time_ms: Response time in milliseconds
            tokens_used: Number of tokens used
            estimated_cost: Estimated cost
            error_message: Error message if failed

        Returns:
            Created usage log entry
        """
        # Convert model name to friendly name
        friendly_model = get_friendly_model_name(model_used)

        usage_log = UsageLog(
            api_key_id=api_key_id,
            channel_id=channel_id,
            session_id=session_id,
            platform=platform,
            model_used=friendly_model,
            success=success,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            estimated_cost=estimated_cost,
            error_message=error_message,
        )

        db.add(usage_log)
        db.commit()

        logger.debug(
            f"Logged usage for API key ID {api_key_id}, channel ID {channel_id}, "
            f"model: {friendly_model}, success: {success}"
        )

        return usage_log

    @staticmethod
    def check_quota(db: Session, api_key: APIKey, period: str = "daily") -> Dict[str, any]:
        """
        Check if API key or channel has exceeded quota.

        Args:
            db: Database session
            api_key: API key object
            period: "daily" or "monthly"

        Returns:
            Dict with quota information:
            {
                "allowed": bool,
                "current_usage": int,
                "quota_limit": int or None,
                "quota_source": "api_key" or "channel" or "unlimited",
                "reset_time": datetime or None
            }
        """
        # Determine which quota to use
        if period == "daily":
            quota_limit = (
                api_key.daily_quota if api_key.daily_quota is not None else api_key.channel.daily_quota
            )
            period_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            reset_time = period_start + timedelta(days=1)
        elif period == "monthly":
            quota_limit = (
                api_key.monthly_quota
                if api_key.monthly_quota is not None
                else api_key.channel.monthly_quota
            )
            now = datetime.utcnow()
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Calculate first day of next month
            if now.month == 12:
                reset_time = period_start.replace(year=now.year + 1, month=1)
            else:
                reset_time = period_start.replace(month=now.month + 1)
        else:
            raise ValueError(f"Invalid period: {period}. Must be 'daily' or 'monthly'")

        # If no quota is set, allow unlimited
        if quota_limit is None:
            return {
                "allowed": True,
                "current_usage": 0,
                "quota_limit": None,
                "quota_source": "unlimited",
                "reset_time": None,
            }

        # Count usage in the period
        current_usage = (
            db.query(func.count(UsageLog.id))
            .filter(
                UsageLog.api_key_id == api_key.id,
                UsageLog.timestamp >= period_start,
                UsageLog.success,  # Only count successful requests
            )
            .scalar()
        )

        quota_source = (
            "api_key"
            if (
                (period == "daily" and api_key.daily_quota is not None)
                or (period == "monthly" and api_key.monthly_quota is not None)
            )
            else "channel"
        )

        allowed = current_usage < quota_limit

        if not allowed:
            logger.warning(
                f"Quota exceeded for API key {api_key.key_prefix} (channel: {api_key.channel.title}): "
                f"{current_usage}/{quota_limit} {period} requests"
            )

        return {
            "allowed": allowed,
            "current_usage": current_usage,
            "quota_limit": quota_limit,
            "quota_source": quota_source,
            "reset_time": reset_time,
        }

    @staticmethod
    def get_channel_usage_stats(
        db: Session,
        channel_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get usage statistics for a channel.

        Args:
            db: Database session
            channel_id: Channel ID
            start_date: Start date for stats (default: 30 days ago)
            end_date: End date for stats (default: now)

        Returns:
            Dict with usage statistics
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        # Total requests
        total_requests = (
            db.query(func.count(UsageLog.id))
            .filter(
                UsageLog.channel_id == channel_id,
                UsageLog.timestamp >= start_date,
                UsageLog.timestamp <= end_date,
            )
            .scalar()
        )

        # Successful requests
        successful_requests = (
            db.query(func.count(UsageLog.id))
            .filter(
                UsageLog.channel_id == channel_id,
                UsageLog.timestamp >= start_date,
                UsageLog.timestamp <= end_date,
                UsageLog.success,
            )
            .scalar()
        )

        # Failed requests
        failed_requests = total_requests - successful_requests

        # Total tokens (if tracked)
        total_tokens = (
            db.query(func.sum(UsageLog.tokens_used))
            .filter(
                UsageLog.channel_id == channel_id,
                UsageLog.timestamp >= start_date,
                UsageLog.timestamp <= end_date,
                UsageLog.tokens_used.isnot(None),
            )
            .scalar()
            or 0
        )

        # Total cost (if tracked)
        total_cost = (
            db.query(func.sum(UsageLog.estimated_cost))
            .filter(
                UsageLog.channel_id == channel_id,
                UsageLog.timestamp >= start_date,
                UsageLog.timestamp <= end_date,
                UsageLog.estimated_cost.isnot(None),
            )
            .scalar()
            or 0.0
        )

        # Average response time
        avg_response_time = (
            db.query(func.avg(UsageLog.response_time_ms))
            .filter(
                UsageLog.channel_id == channel_id,
                UsageLog.timestamp >= start_date,
                UsageLog.timestamp <= end_date,
                UsageLog.response_time_ms.isnot(None),
            )
            .scalar()
            or 0
        )

        # Most used models
        model_usage = (
            db.query(UsageLog.model_used, func.count(UsageLog.id).label("count"))
            .filter(
                UsageLog.channel_id == channel_id,
                UsageLog.timestamp >= start_date,
                UsageLog.timestamp <= end_date,
            )
            .group_by(UsageLog.model_used)
            .order_by(func.count(UsageLog.id).desc())
            .limit(10)
            .all()
        )

        return {
            "channel_id": channel_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "requests": {
                "total": total_requests,
                "successful": successful_requests,
                "failed": failed_requests,
                "success_rate": (
                    (successful_requests / total_requests * 100) if total_requests > 0 else 0
                ),
            },
            "tokens": {
                "total": total_tokens,
                "average_per_request": (
                    (total_tokens / successful_requests) if successful_requests > 0 else 0
                ),
            },
            "cost": {
                "total": round(total_cost, 4),
                "average_per_request": (
                    round(total_cost / successful_requests, 4) if successful_requests > 0 else 0
                ),
            },
            "performance": {
                "avg_response_time_ms": round(avg_response_time, 2) if avg_response_time else 0,
            },
            "models": [{"model": model, "requests": count} for model, count in model_usage],
        }

    @staticmethod
    def get_api_key_usage_stats(
        db: Session,
        api_key_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Get usage statistics for a specific API key.

        Args:
            db: Database session
            api_key_id: API key ID
            start_date: Start date for stats (default: 30 days ago)
            end_date: End date for stats (default: now)

        Returns:
            Dict with usage statistics
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        # Total requests
        total_requests = (
            db.query(func.count(UsageLog.id))
            .filter(
                UsageLog.api_key_id == api_key_id,
                UsageLog.timestamp >= start_date,
                UsageLog.timestamp <= end_date,
            )
            .scalar()
        )

        # Successful requests
        successful_requests = (
            db.query(func.count(UsageLog.id))
            .filter(
                UsageLog.api_key_id == api_key_id,
                UsageLog.timestamp >= start_date,
                UsageLog.timestamp <= end_date,
                UsageLog.success,
            )
            .scalar()
        )

        return {
            "api_key_id": api_key_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "requests": {
                "total": total_requests,
                "successful": successful_requests,
                "failed": total_requests - successful_requests,
            },
        }

    @staticmethod
    def get_recent_usage(
        db: Session,
        channel_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[UsageLog]:
        """
        Get recent usage logs (channel-based tracking only).

        Args:
            db: Database session
            channel_id: Filter by channel ID (optional)
            limit: Maximum number of logs to return

        Returns:
            List of usage logs
        """
        query = db.query(UsageLog)

        if channel_id is not None:
            query = query.filter(UsageLog.channel_id == channel_id)

        return query.order_by(UsageLog.timestamp.desc()).limit(limit).all()