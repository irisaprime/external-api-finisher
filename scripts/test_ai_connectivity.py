#!/usr/bin/env python3
"""
Manual AI Service Connectivity Test Script

Run this script to test connectivity to your AI service.
This is NOT a pytest test - it's meant for manual verification.

Usage:
    python scripts/test_ai_connectivity.py
"""

import asyncio
import sys
from pathlib import Path

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.ai_client import ai_client


def main():
    """Manual test function for direct execution"""
    print("=" * 70)
    print("AI Service Connectivity Test".center(70))
    print("=" * 70)
    print()

    print(f"Service URL: {settings.AI_SERVICE_URL}")
    print(f"Telegram Default Model: {settings.TELEGRAM_DEFAULT_MODEL}")
    print(f"Internal Models: {len(settings.internal_models_list)}")
    print()
    print("-" * 70)

    async def run_tests():
        client = httpx.AsyncClient(timeout=10.0)
        base_url = settings.AI_SERVICE_URL

        # Test 1: Base URL
        print("\n1. Testing Base URL Connectivity...")
        try:
            response = await client.get(base_url)
            print(f"   [OK] Status: {response.status_code}")
            print(f"   Response: {response.text[:150]}")
        except httpx.ConnectError as e:
            print(f"   [ERROR] Connection Error: {e}")
            print(f"   Hint: Check if {base_url} is correct and reachable")
        except Exception as e:
            print(f"   [ERROR] Error: {e}")

        # Test 2: Health endpoint
        print("\n2. Testing Health Endpoint...")
        try:
            response = await client.get(f"{base_url}/health", timeout=5.0)
            print(f"   [OK] Status: {response.status_code}")
            print(f"   Response: {response.text[:150]}")
        except httpx.TimeoutException:
            print("   [ERROR] Timeout: Service did not respond within 5 seconds")
        except Exception as e:
            print(f"   [ERROR] Error: {e}")

        # Test 3: Chat endpoint
        print("\n3. Testing Chat Endpoint...")
        payload = {
            "UserId": "test_user",
            "UserName": "TestBot",
            "SessionId": "test_session",
            "History": [],
            "Pipeline": settings.TELEGRAM_DEFAULT_MODEL,
            "Query": "Hello, this is a test",
            "AudioFile": None,
            "Files": [],
        }

        try:
            response = await client.post(f"{base_url}/v2/chat", json=payload, timeout=30.0)
            print(f"   [OK] Status: {response.status_code}")
            data = response.json()
            print(f"   Response: {str(data)[:200]}")
        except httpx.TimeoutException:
            print("   [ERROR] Timeout: Chat request took too long (>30s)")
            print("   Hint: Service might be overloaded or slow")
        except httpx.ConnectError:
            print("   [ERROR] Cannot connect to service")
        except Exception as e:
            print(f"   [ERROR] Error: {e}")

        # Test 4: Client health check
        print("\n4. Testing Client Health Check Method...")
        try:
            is_healthy = await ai_client.health_check()
            if is_healthy:
                print("   [OK] Service is healthy")
            else:
                print("   [WARNING] Service reported unhealthy")
        except Exception as e:
            print(f"   [ERROR] Error: {e}")

        await client.aclose()

        print()
        print("=" * 70)
        print("Test Complete".center(70))
        print("=" * 70)
        print()
        print("Next Steps:")
        print("  - If all tests pass: Your AI service is working!")
        print("  - If tests fail: Check the AI_SERVICE_URL in .env")
        print("  - For timeout errors: Consider increasing timeout or checking network")
        print()

    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    # Run manual test when executed directly
    main()
