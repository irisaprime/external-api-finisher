"""
Message processor with platform-aware logic
"""

import logging
import time
from typing import Optional

from app.core.constants import MESSAGES_FA, MessageType
from app.models.database import get_db_session
from app.models.schemas import BotResponse, IncomingMessage
from app.models.session import ChatSession
from app.services.ai_client import ai_client
from app.services.command_processor import command_processor
from app.services.platform_manager import platform_manager
from app.services.session_manager import session_manager
from app.services.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Processes messages with platform-aware logic"""

    async def process_message(self, message: IncomingMessage) -> BotResponse:
        """Process incoming message with team isolation"""

        try:
            # Extract team info from metadata (set by API endpoint)
            team_id = message.metadata.get("team_id")
            api_key_id = message.metadata.get("api_key_id")
            api_key_prefix = message.metadata.get("api_key_prefix")

            # Get or create session with team isolation
            session = session_manager.get_or_create_session(
                platform=message.platform,
                user_id=message.user_id,
                conversation_id=message.conversation_id,
                team_id=team_id,
                api_key_id=api_key_id,
                api_key_prefix=api_key_prefix,
            )

            # Check authentication if required
            if platform_manager.requires_auth(message.platform):
                if not message.auth_token or not platform_manager.validate_auth(
                    message.platform, message.auth_token
                ):
                    return BotResponse(
                        success=False,
                        error="authentication_failed",
                        response=MESSAGES_FA["error_auth_failed"],
                    )

            # Check rate limit
            if not session_manager.check_rate_limit(message.platform, message.user_id):
                rate_limit = platform_manager.get_rate_limit(message.platform)
                return BotResponse(
                    success=False,
                    error="rate_limit",
                    response=MESSAGES_FA["error_rate_limit"].format(rate_limit=rate_limit),
                )

            # Process command or message
            if message.text and command_processor.is_command(message.text):
                response_text = await self._handle_command(session, message.text)
            else:
                response_text = await self._handle_chat(session, message)

            # Update session activity (total_message_count is already incremented by add_message)
            session.update_activity()

            # Prepare response (only expose user-facing fields, no internal session_id)
            return BotResponse(
                success=True,
                response=response_text,
                model=session.current_model_friendly,
                total_message_count=session.total_message_count,
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return BotResponse(
                success=False, error="processing_error", response=MESSAGES_FA["error_processing"]
            )

    async def process_message_simple(
        self,
        platform_name: str,
        team_id: Optional[int],
        api_key_id: Optional[int],
        api_key_prefix: Optional[str],
        user_id: str,
        text: str,
    ) -> BotResponse:
        """
        Process message with simplified interface (text-only, no webhooks).

        Args:
            platform_name: Platform name (e.g., "telegram", "Internal-BI")
            team_id: Team ID (None for Telegram, required for authenticated platforms)
            api_key_id: API key ID (None for Telegram)
            api_key_prefix: API key prefix (None for Telegram)
            user_id: User ID (client-provided)
            text: Message text

        Returns:
            BotResponse with total_message_count showing total messages
        """
        start_time = time.time()
        db = get_db_session()

        try:
            # Get or create session (loads message history from DB)
            try:
                session = session_manager.get_or_create_session(
                    platform=platform_name,
                    user_id=user_id,
                    team_id=team_id,
                    api_key_id=api_key_id,
                    api_key_prefix=api_key_prefix,
                )
            except PermissionError:
                # API key doesn't own this user's conversation
                return BotResponse(
                    success=False,
                    error="access_denied",
                    response="❌ دسترسی رد شد. این مکالمه متعلق به API key دیگری است.\n\nAccess denied. This conversation belongs to a different API key.",
                )

            # Check rate limit
            if not session_manager.check_rate_limit(platform_name, user_id):
                rate_limit = session.platform_config.get("rate_limit", 60)

                # Log rate limit failure (only for authenticated teams)
                if team_id and api_key_id:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    UsageTracker.log_usage(
                        db=db,
                        api_key_id=api_key_id,
                        team_id=team_id,
                        session_id=session.session_id,
                        platform=platform_name,
                        model_used=session.current_model,
                        success=False,
                        response_time_ms=response_time_ms,
                        error_message="rate_limit_exceeded",
                    )

                return BotResponse(
                    success=False,
                    error="rate_limit_exceeded",
                    response=f"⚠️ محدودیت سرعت. لطفاً قبل از ارسال پیام بعدی کمی صبر کنید.\n\nمحدودیت: {rate_limit} پیام در دقیقه",
                )

            # Process command or message
            if text and command_processor.is_command(text):
                response_text = await self._handle_command(session, text)
            else:
                response_text = await self._handle_chat_simple(session, text, db)

            # Update session activity
            session.update_activity()

            # Reload total_message_count from DB (after messages were saved)
            # NOTE: total_message_count only counts actual chat messages (user + assistant)
            # Commands (e.g., /model, /help, /clear) are NOT counted since they're
            # not saved to the messages table. This count persists through /clear.
            from sqlalchemy import func

            from app.models.database import Message

            session.total_message_count = (
                db.query(func.count(Message.id))
                .filter(
                    Message.platform == platform_name,
                    Message.user_id == user_id,
                    Message.team_id == team_id if team_id else Message.team_id.is_(None),
                )
                .scalar()
                or 0
            )

            # Log successful usage (only for authenticated teams)
            if team_id and api_key_id:
                response_time_ms = int((time.time() - start_time) * 1000)
                UsageTracker.log_usage(
                    db=db,
                    api_key_id=api_key_id,
                    team_id=team_id,
                    session_id=session.session_id,
                    platform=platform_name,
                    model_used=session.current_model,
                    success=True,
                    response_time_ms=response_time_ms,
                )

            # Return response
            return BotResponse(
                success=True,
                response=response_text,
                model=session.current_model_friendly,
                total_message_count=session.total_message_count,
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

            # Log error (only for authenticated teams)
            if team_id and api_key_id:
                response_time_ms = int((time.time() - start_time) * 1000)
                try:
                    # Get session for model info
                    session = session_manager.get_session(platform_name, user_id, team_id)
                    model_used = session.current_model if session else "unknown"
                    session_id = session.session_id if session else "unknown"

                    UsageTracker.log_usage(
                        db=db,
                        api_key_id=api_key_id,
                        team_id=team_id,
                        session_id=session_id,
                        platform=platform_name,
                        model_used=model_used,
                        success=False,
                        response_time_ms=response_time_ms,
                        error_message=str(e),
                    )
                except Exception:
                    pass  # Don't fail on logging errors

            return BotResponse(
                success=False,
                error="processing_error",
                response="❌ متأسفم، خطایی در پردازش پیام شما رخ داد. لطفاً دوباره تلاش کنید.",
            )

    async def _handle_chat_simple(self, session: ChatSession, text: str, db) -> str:
        """
        Handle chat message (simplified, text-only) and persist to database.

        Args:
            session: Chat session with in-memory history
            text: User message text
            db: Database session for persisting messages

        Returns:
            AI response text
        """
        from app.models.database import Message

        try:
            # Get max history for platform
            max_history = platform_manager.get_max_history(session.platform)

            # Send to AI service with session's current model
            try:
                response = await ai_client.send_chat_request(
                    session_id=session.session_id,
                    query=text,
                    history=session.get_recent_history(max_history),
                    pipeline=session.current_model,
                    files=[],  # No files in simplified version
                )

                ai_response = response["Response"]

                # Add to in-memory history
                session.add_message("user", text)
                session.add_message("assistant", ai_response)

                # Persist to database
                try:
                    user_msg = Message(
                        team_id=session.team_id,
                        api_key_id=session.api_key_id,
                        platform=session.platform,
                        user_id=session.user_id,
                        role="user",
                        content=text,
                    )
                    assistant_msg = Message(
                        team_id=session.team_id,
                        api_key_id=session.api_key_id,
                        platform=session.platform,
                        user_id=session.user_id,
                        role="assistant",
                        content=ai_response,
                    )
                    db.add(user_msg)
                    db.add(assistant_msg)
                    db.commit()
                except Exception as db_error:
                    logger.error(f"Error persisting messages to DB: {db_error}")
                    db.rollback()
                    # Continue anyway - in-memory history is intact

                # Trim in-memory history if exceeds platform limit
                if len(session.history) > max_history * 2:
                    session.history = session.history[-max_history * 2 :]

                return ai_response

            except Exception as ai_service_error:
                logger.error(f"AI service error: {ai_service_error}")
                return (
                    "متأسفم، سرویس هوش مصنوعی در حال حاضر در دسترس نیست. "
                    "لطفاً چند لحظه دیگر دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
                )

        except Exception as e:
            logger.error(f"Error processing chat: {e}", exc_info=True)
            return "خطایی در پردازش پیام شما رخ داد. لطفاً دوباره تلاش کنید."

    async def _handle_command(self, session: ChatSession, text: str) -> str:
        """Handle command"""
        return await command_processor.process_command(session, text)

    async def _handle_chat(self, session: ChatSession, message: IncomingMessage) -> str:
        """Handle chat message"""
        try:
            # Prepare files if any
            files = []
            if message.attachments:
                for att in message.attachments:
                    if att.type == MessageType.IMAGE and att.data:
                        files.append({"Data": att.data, "MIMEType": att.mime_type or "image/jpeg"})

            # Get max history for platform
            max_history = platform_manager.get_max_history(session.platform)

            # Send to AI service with session's current model
            try:
                response = await ai_client.send_chat_request(
                    session_id=session.session_id,
                    query=message.text or "این تصویر را توضیح بده؟",
                    history=session.get_recent_history(max_history),
                    pipeline=session.current_model,
                    files=files,
                )

                # Update history
                session.add_message("user", message.text or "[تصویر/پیوست]")
                session.add_message("assistant", response["Response"])

                # Trim history if exceeds platform limit
                if len(session.history) > max_history * 2:
                    session.history = session.history[-max_history * 2 :]

                return response["Response"]

            except Exception as ai_service_error:
                logger.error(f"AI service error: {ai_service_error}")

                # Return fallback message when AI service is unavailable
                return (
                    "⚠️ متأسفم، سرویس هوش مصنوعی در حال حاضر در دسترس نیست.\n\n"
                    f"پیام شما: {message.text}\n\n"
                    "لطفاً چند لحظه دیگر دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.\n\n"
                    f"جزئیات خطا: سرویس هوش مصنوعی پاسخ نمی‌دهد."
                )

        except Exception as e:
            logger.error(f"Error processing chat: {e}", exc_info=True)
            return MESSAGES_FA["error_processing"]


# Global instance
message_processor = MessageProcessor()
