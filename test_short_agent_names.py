#!/usr/bin/env python3
"""Test script to verify short AI agent name resolution works correctly"""

import sys
import traceback


def test_agent_name_resolution():
    """Test that short agent names are correctly resolved to full names"""
    print("Testing AI agent name resolution...")

    try:
        from cli.command_router import CommandRouter

        # Create a mock router to test the method
        router = CommandRouter(None, None, None, None, None)

        # Test cases: short_name -> expected_full_name
        test_cases = {
            "qwen25": "vllm-qwen25",
            "glm46": "vllm-glm46",
            "claude": "claude-sonnet",
            "gpt4": "gpt-4",
            "gpt-4": "gpt-4",  # Should work with both formats
            "claude-sonnet": "claude-sonnet",  # Full names should pass through
            "vllm-qwen25": "vllm-qwen25",
            "QWEN25": "vllm-qwen25",  # Test case insensitive
            "Claude": "claude-sonnet",
            None: None,  # None should return None
            True: None,  # True should return None
            "": None,  # Empty string should return None
            "unknown": "unknown",  # Unknown names should pass through unchanged
        }

        passed = 0
        total = len(test_cases)

        for short_name, expected in test_cases.items():
            result = router._resolve_ai_agent_name(short_name)
            if result == expected:
                print(f"✓ '{short_name}' -> '{result}' (correct)")
                passed += 1
            else:
                print(f"✗ '{short_name}' -> '{result}' (expected '{expected}')")

        print(f"\nAgent name resolution: {passed}/{total} tests passed")
        return passed == total

    except Exception as e:
        print(f"✗ Failed to test agent name resolution: {e}")
        traceback.print_exc()
        return False


def test_ai_analyzer_resolution():
    """Test that ai_analyzer also resolves agent names correctly"""
    print("\nTesting AI analyzer agent name resolution...")

    try:
        from ai_analyzer import ai_analyzer

        # Test cases
        test_cases = {
            "qwen25": "vllm-qwen25",
            "claude": "claude-sonnet",
            "glm46": "vllm-glm46",
            "gpt4": "gpt-4",
        }

        passed = 0
        total = len(test_cases)

        for short_name, expected in test_cases.items():
            result = ai_analyzer._resolve_ai_agent_name(short_name)
            if result == expected:
                print(f"✓ ai_analyzer: '{short_name}' -> '{result}' (correct)")
                passed += 1
            else:
                print(
                    f"✗ ai_analyzer: '{short_name}' -> '{result}' (expected '{expected}')"
                )

        print(f"\nAI analyzer resolution: {passed}/{total} tests passed")
        return passed == total

    except Exception as e:
        print(f"✗ Failed to test AI analyzer resolution: {e}")
        traceback.print_exc()
        return False


def test_argument_parsing():
    """Test that the argument parser accepts the new -ai syntax"""
    print("\nTesting argument parsing...")

    try:
        from cli.parser import create_argument_parser

        parser = create_argument_parser()

        # Test cases for different -ai argument formats
        test_cases = [
            ["logs", "service", "-ai"],  # Just -ai flag
            ["logs", "service", "-ai", "qwen25"],  # -ai with agent name
            ["logs", "service", "-ai", "claude"],  # -ai with different agent
            ["logs", "service", "--ai-diagnose"],  # Long form flag
            ["logs", "service", "--ai-diagnose", "glm46"],  # Long form with agent
        ]

        passed = 0
        total = len(test_cases)

        for i, args in enumerate(test_cases):
            try:
                parsed = parser.parse_args(args)
                ai_diagnose = getattr(parsed, "ai_diagnose", False)

                if ai_diagnose:
                    print(f"✓ Test {i+1}: {args} -> ai_diagnose='{ai_diagnose}'")
                    passed += 1
                else:
                    print(f"✗ Test {i+1}: {args} -> ai_diagnose not set")
            except Exception as e:
                print(f"✗ Test {i+1}: {args} -> parsing failed: {e}")

        print(f"\nArgument parsing: {passed}/{total} tests passed")
        return passed == total

    except Exception as e:
        print(f"✗ Failed to test argument parsing: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=== Short AI Agent Names Test ===")

    tests = [
        test_agent_name_resolution,
        test_ai_analyzer_resolution,
        test_argument_parsing,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            print(f"\n❌ Test {test.__name__} failed")

    print(f"\n=== Results: {passed}/{total} tests passed ===")

    if passed == total:
        print("🎉 All tests passed! Short agent names are working correctly.")
        print("\n📝 You can now use:")
        print("   pm logs vllm-glm46 -ai qwen25")
        print("   pm logs vllm-glm46 -ai claude")
        print("   pm logs vllm-glm46 -ai glm46")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
