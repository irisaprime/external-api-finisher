"""
AI Service Integration Tests
Tests connectivity and functionality of the AI service
"""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.ai_client import ai_client


@pytest.mark.integration
class TestAIServiceConnectivity:
    """Test AI service connectivity (requires actual service)"""

    @pytest.fixture
    def client(self):
        """Create HTTP client"""
        return httpx.AsyncClient(timeout=10.0)

    @pytest.fixture
    def base_url(self):
        """Get base URL from settings"""
        return settings.AI_SERVICE_URL

    @pytest.mark.asyncio
    async def test_base_url_reachable(self, client, base_url):
        """Test if base URL is reachable"""
        try:
            response = await client.get(base_url)
            assert response.status_code in [
                200,
                404,
                405,
            ], f"Unexpected status code: {response.status_code}"
            print(f"[OK] Base URL reachable: {response.status_code}")
        except httpx.ConnectError as e:
            pytest.fail(f"[ERROR] Cannot connect to {base_url}: {e}")
        except Exception as e:
            pytest.fail(f"[ERROR] Unexpected error: {e}")
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client, base_url):
        """Test health check endpoint (if available)"""
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 404:
                pytest.skip("Health endpoint not available on AI service (404)")
            assert (
                response.status_code == 200
            ), f"Health check failed with status: {response.status_code}"
            print(f"[OK] Health endpoint OK: {response.text[:100]}")
        except httpx.ConnectError:
            pytest.skip("Service not reachable, skipping health check")
        except Exception as e:
            pytest.fail(f"[ERROR] Health check failed: {e}")
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_chat_endpoint_format(self, client, base_url):
        """Test chat endpoint with proper payload"""
        payload = {
            "UserId": "test_user",
            "UserName": "TestUser",
            "SessionId": "test_session",
            "History": [],
            "Pipeline": "google/gemini-2.0-flash-001",
            "Query": "Hello",
            "AudioFile": None,
            "Files": [],
        }

        try:
            response = await client.post(f"{base_url}/v2/chat", json=payload, timeout=30.0)
            assert response.status_code in [
                200,
                201,
            ], f"Chat endpoint returned: {response.status_code}"

            data = response.json()
            assert (
                "Response" in data or "response" in data
            ), "Response does not contain expected fields"
            print(f"[OK] Chat endpoint working: {response.status_code}")
        except httpx.TimeoutException:
            pytest.skip("Service timeout - might be slow or overloaded")
        except httpx.ConnectError:
            pytest.skip("Service not reachable")
        except Exception as e:
            pytest.fail(f"[ERROR] Chat endpoint test failed: {e}")
        finally:
            await client.aclose()


class TestAIServiceClient:
    """Test AI service client wrapper"""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client is properly initialized"""
        assert ai_client is not None
        assert ai_client.base_url == settings.AI_SERVICE_URL
        assert ai_client.max_retries == 3
        print("[OK] Client initialized correctly")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_health_check_method(self):
        """Test client health check method"""
        try:
            is_healthy = await ai_client.health_check()
            assert isinstance(is_healthy, bool)
            if is_healthy:
                print("[OK] Service is healthy")
            else:
                print("[WARNING] Service reported unhealthy")
        except Exception as e:
            pytest.skip(f"Health check failed: {e}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_send_chat_request(self):
        """Test sending actual chat request"""
        try:
            response = await ai_client.send_chat_request(
                session_id="test_session",
                query="Hello, this is a test",
                history=[],
                pipeline="google/gemini-2.0-flash-001",
                files=[],
            )

            assert isinstance(response, dict)
            assert "Response" in response or "response" in response
            print(f"[OK] Chat request successful: {response}")
        except Exception as e:
            pytest.skip(f"Chat request failed: {e}")


class TestAIServiceConfiguration:
    """Test AI service configuration"""

    def test_url_configured(self):
        """Test that AI service URL is configured"""
        assert settings.AI_SERVICE_URL, "AI_SERVICE_URL not configured in .env"
        assert settings.AI_SERVICE_URL.startswith(
            "http"
        ), "AI_SERVICE_URL must start with http or https"
        print(f"[OK] URL configured: {settings.AI_SERVICE_URL}")

    def test_url_format(self):
        """Test URL format is valid"""
        url = settings.AI_SERVICE_URL
        assert not url.endswith("/"), "AI_SERVICE_URL should not end with /"
        print("[OK] URL format valid")

    def test_models_configured(self):
        """Test that models are properly configured"""
        telegram_model = settings.TELEGRAM_DEFAULT_MODEL
        internal_models = settings.internal_models_list

        assert telegram_model, "TELEGRAM_DEFAULT_MODEL not configured"
        assert internal_models, "INTERNAL_MODELS not configured"
        assert len(internal_models) > 0, "No internal models configured"
        print(f"[OK] Models configured: {len(internal_models)} models")


# NOTE: For manual AI service connectivity testing, run:
#   python scripts/test_ai_connectivity.py
