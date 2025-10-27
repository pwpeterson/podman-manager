#!/usr/bin/env python3
"""Test script to validate the Anthropic API key"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded .env file from {env_path}")
    else:
        print(f"✗ .env file not found at {env_path}")
except ImportError:
    print("✗ python-dotenv not installed")

try:
    import requests
except ImportError:
    print("✗ requests module not available")
    sys.exit(1)


def test_api_key():
    """Test the Anthropic API key"""
    print("\n=== Testing Anthropic API Key ===")

    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("✗ ANTHROPIC_API_KEY environment variable not set")
        return False

    # Show API key info
    key_length = len(api_key)
    key_preview = f"{api_key[:15]}...{api_key[-10:]}" if len(api_key) > 25 else api_key
    print(f"✓ API key found - Length: {key_length}, Preview: {key_preview}")

    # Validate API key format
    if not api_key.startswith("sk-ant-api03-"):
        print("⚠ Warning: API key doesn't start with expected prefix 'sk-ant-api03-'")
        print(f"  Current prefix: {api_key[:15]}")

    # Expected length for Anthropic API keys is typically around 108-120 characters
    if key_length < 100:
        print(
            f"⚠ Warning: API key seems short (length: {key_length}). Expected ~108-120 characters"
        )

    # Test API key with a simple request
    print("\n=== Testing API Connection ===")

    payload = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 10,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": "Hello"}],
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    try:
        print("Making test request to Anthropic API...")
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
            timeout=30,
        )

        print(f"Response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✓ API key is valid and working!")
            if "content" in result and len(result["content"]) > 0:
                content = result["content"][0]["text"]
                print(f"Response: {content}")
            return True
        elif response.status_code == 401:
            print("✗ API key is invalid (401 Unauthorized)")
            try:
                error_data = response.json()
                print(f"Error details: {error_data}")
            except Exception:
                print(f"Error response: {response.text[:200]}")
            return False
        elif response.status_code == 400:
            print(
                "⚠ Bad request (400) - API key might be valid but request format is wrong"
            )
            try:
                error_data = response.json()
                print(f"Error details: {error_data}")
            except Exception:
                print(f"Error response: {response.text[:200]}")
            return False
        else:
            print(f"✗ Unexpected response status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False

    except requests.RequestException as e:
        print(f"✗ Request failed: {e}")
        return False


def show_env_info():
    """Show environment information"""
    print("\n=== Environment Information ===")

    # Check all Anthropic-related env vars
    anthropic_vars = [key for key in os.environ.keys() if "ANTHROPIC" in key.upper()]
    if anthropic_vars:
        print("Anthropic environment variables found:")
        for var in anthropic_vars:
            value = os.getenv(var)
            if value:
                preview = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else value
                print(f"  {var}: {preview} (length: {len(value)})")
            else:
                print(f"  {var}: (empty)")
    else:
        print("No Anthropic environment variables found")

    # Check if .env file exists and show its location
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        print(f"\n.env file found at: {env_path.absolute()}")
        print(f".env file size: {env_path.stat().st_size} bytes")
    else:
        print(f"\n.env file not found at: {env_path.absolute()}")


if __name__ == "__main__":
    show_env_info()
    success = test_api_key()

    print("\n=== Summary ===")
    if success:
        print("✓ API key test passed - Claude agent should work correctly")
        sys.exit(0)
    else:
        print("✗ API key test failed - Please check your ANTHROPIC_API_KEY")
        print("\nTo fix:")
        print("1. Get a valid API key from https://console.anthropic.com/")
        print("2. Update the ANTHROPIC_API_KEY in your .env file")
        print(
            "3. Make sure the key starts with 'sk-ant-api03-' and is ~108-120 characters long"
        )
        sys.exit(1)
