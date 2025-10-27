#!/usr/bin/env python3
"""Simple test for Claude agent configuration"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_claude_config():
    """Test Claude configuration without making API calls"""
    print("Testing Claude Agent Configuration...")
    print()

    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"✓ ANTHROPIC_API_KEY is set (length: {len(api_key)})")
    else:
        print("✗ ANTHROPIC_API_KEY is not set")
        print("Please set: export ANTHROPIC_API_KEY=your_api_key_here")
        return False

    # Test configuration loading
    try:
        from ai_system.ai_agents import ai_agent_manager

        print("✓ AI agent manager loaded successfully")

        # Get Claude agent
        claude_agent = ai_agent_manager.get_agent("claude-sonnet-4.5")
        if claude_agent:
            print(f"✓ Claude agent found: {claude_agent.config.display_name}")
            print(f"  Model: {claude_agent.config.model_name}")
            print(f"  Type: {claude_agent.config.agent_type}")
            print(f"  Timeout: {claude_agent.config.timeout}s")
            print(f"  Max tokens: {claude_agent.config.max_tokens}")

            # Check availability (without API call)
            print(f"  API key available: {claude_agent.config.api_key_env}")
            return True
        else:
            print("✗ Claude agent not found")
            return False

    except Exception as e:
        print(f"✗ Error loading configuration: {e}")
        return False


if __name__ == "__main__":
    success = test_claude_config()
    print()
    if success:
        print("✓ Configuration test passed!")
        print("\nTo test API connectivity, run:")
        print("python test_claude_agent.py")
    else:
        print("✗ Configuration test failed!")

    sys.exit(0 if success else 1)
