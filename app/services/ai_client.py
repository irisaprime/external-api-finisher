"""
AI Service API client with retry logic
"""

import asyncio
import logging
from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.core.name_mapping import get_friendly_model_name, mask_session_id

logger = logging.getLogger(__name__)


class AIServiceClient:
    """Client for communicating with AI service"""

    def __init__(self):
        self.base_url = settings.AI_SERVICE_URL
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
        self.max_retries = 3

    async def send_chat_request(
        self,
        session_id: str,
        query: str,
        history: List[Dict[str, str]],
        pipeline: str,
        files: List[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send chat request to AI service with retry logic"""

        # Format history for AI service
        formatted_history = []

        # Always add system prompt for Persian responses at the beginning
        formatted_history.append(
            {
                "Role": "system",
                "Message": "شما یک دستیار هوشمند هستید که همیشه به زبان فارسی پاسخ می‌دهید. تمام پاسخ‌های شما باید به زبان فارسی باشد. از استفاده از زبان انگلیسی یا سایر زبان‌ها خودداری کنید مگر اینکه کاربر به صراحت درخواست کند.",
                "Files": None,
            }
        )

        for msg in history:
            formatted_history.append(
                {"Role": msg.get("role", "user"), "Message": msg.get("content", ""), "Files": None}
            )

        payload = {
            "UserId": session_id,
            "UserName": "MessengerBot",
            "SessionId": session_id,
            "History": formatted_history,
            "Pipeline": pipeline,
            "Query": query,
            "AudioFile": None,
            "Files": files or [],
        }

        last_error = None
        masked_session = mask_session_id(session_id)

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Attempt {attempt + 1}/{self.max_retries} for session {masked_session}"
                )

                # Debug logging: Log payload structure (but not full content for privacy)
                logger.debug(
                    f"Request payload structure: UserId={bool(payload.get('UserId'))}, "
                    f"Pipeline={payload.get('Pipeline')}, History_count={len(payload.get('History', []))}, "
                    f"Query_length={len(payload.get('Query', ''))}, Files_count={len(payload.get('Files', []))}"
                )

                response = await self.client.post(f"{self.base_url}/v2/chat", json=payload)

                # Debug logging: Log response details before raising errors
                logger.debug(
                    f"Response status: {response.status_code}, "
                    f"headers: {dict(response.headers)}, "
                    f"body_length: {len(response.content)}"
                )

                # If error, log response body for debugging
                if response.status_code >= 400:
                    try:
                        error_body = response.text[:500]  # First 500 chars
                        logger.error(
                            f"AI service error response (status {response.status_code}): {error_body}"
                        )
                    except Exception:
                        pass

                response.raise_for_status()

                result = response.json()

                # Log with friendly model name
                friendly_model = get_friendly_model_name(pipeline)
                logger.info(
                    f"Successfully processed request for session {masked_session} "
                    f"using model {friendly_model}"
                )
                return result

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{self.max_retries} "
                    f"for session {masked_session}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error {e.response.status_code} for session {masked_session}: {e}"
                )
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)

            except Exception as e:
                last_error = e
                logger.error(
                    f"Error on attempt {attempt + 1}/{self.max_retries} "
                    f"for session {masked_session}: {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)

        # All retries failed
        error_msg = f"Failed after {self.max_retries} attempts: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)

    async def health_check(self) -> bool:
        """Check if AI service is healthy"""
        try:
            response = await self.client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"AI service health check failed: {e}")
            return False

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
        logger.info("AI service client closed")


# Global instance
ai_client = AIServiceClient()
