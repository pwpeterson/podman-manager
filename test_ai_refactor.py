#!/usr/bin/env python3
"""Test script to verify the AI analysis refactoring works correctly"""

import sys
import traceback


def test_imports():
    """Test that all refactored modules can be imported"""
    print("Testing imports...")

    try:

        print("✓ ai_analyzer imported successfully")
    except Exception as e:
        print(f"✗ Failed to import ai_analyzer: {e}")
        traceback.print_exc()
        return False

    try:

        print("✓ AIDiagnostics imported successfully")
    except Exception as e:
        print(f"✗ Failed to import AIDiagnostics: {e}")
        traceback.print_exc()
        return False

    try:

        print("✓ ReinitManager imported successfully")
    except Exception as e:
        print(f"✗ Failed to import ReinitManager: {e}")
        traceback.print_exc()
        return False

    return True


def test_ai_analyzer_structure():
    """Test that ai_analyzer has the expected structure"""
    print("\nTesting ai_analyzer structure...")

    try:
        from ai_analyzer import AIAnalyzer, ai_analyzer

        # Check that ai_analyzer is an instance of AIAnalyzer
        if isinstance(ai_analyzer, AIAnalyzer):
            print("✓ ai_analyzer is properly instantiated")
        else:
            print(f"✗ ai_analyzer is not an AIAnalyzer instance: {type(ai_analyzer)}")
            return False

        # Check that it has the ai_analyze method
        if hasattr(ai_analyzer, "ai_analyze"):
            print("✓ ai_analyzer has ai_analyze method")
        else:
            print("✗ ai_analyzer missing ai_analyze method")
            return False

        # Check method signature
        import inspect

        sig = inspect.signature(ai_analyzer.ai_analyze)
        expected_params = [
            "analysis_type",
            "target",
            "context_data",
            "ai_agent",
            "verbose",
        ]
        actual_params = list(sig.parameters.keys())

        if all(param in actual_params for param in expected_params):
            print("✓ ai_analyze method has correct signature")
        else:
            print(
                f"✗ ai_analyze method signature mismatch. Expected: {expected_params}, Got: {actual_params}"
            )
            return False

        return True

    except Exception as e:
        print(f"✗ Failed to test ai_analyzer structure: {e}")
        traceback.print_exc()
        return False


def test_analysis_types():
    """Test that all expected analysis types are supported"""
    print("\nTesting analysis types...")

    try:
        from ai_analyzer import ai_analyzer

        # Test that prompt generation works for different analysis types
        expected_types = [
            "logs",
            "reinit_failure",
            "status",
            "build_failure",
            "performance",
            "security",
        ]

        for analysis_type in expected_types:
            try:
                # Test prompt generation (this should not fail)
                prompt = ai_analyzer._generate_prompt(
                    analysis_type, "test-service", {"timestamp": "2023-01-01"}
                )
                if prompt and analysis_type in prompt:
                    print(f"✓ {analysis_type} analysis type supported")
                else:
                    print(
                        f"✗ {analysis_type} analysis type may not be properly implemented"
                    )
                    return False
            except Exception as e:
                print(f"✗ {analysis_type} analysis type failed: {e}")
                return False

        return True

    except Exception as e:
        print(f"✗ Failed to test analysis types: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=== AI Analysis Refactoring Test ===")

    tests = [test_imports, test_ai_analyzer_structure, test_analysis_types]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            print(f"\n❌ Test {test.__name__} failed")

    print(f"\n=== Results: {passed}/{total} tests passed ===")

    if passed == total:
        print("🎉 All tests passed! The refactoring appears to be successful.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
