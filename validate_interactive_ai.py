#!/usr/bin/env python3
"""Validation script for interactive AI analysis - syntax check only"""

import ast
import sys


def validate_syntax(filename):
    """Validate Python syntax without executing the code"""
    try:
        with open(filename, "r") as f:
            source = f.read()

        # Parse the AST to check for syntax errors
        ast.parse(source)
        print(f"✅ {filename}: Syntax is valid")
        return True

    except SyntaxError as e:
        print(f"❌ {filename}: Syntax error at line {e.lineno}: {e.msg}")
        return False
    except Exception as e:
        print(f"❌ {filename}: Error reading file: {e}")
        return False


def check_interactive_methods():
    """Check if the interactive methods are properly defined"""
    try:
        with open("ai_analyzer.py", "r") as f:
            content = f.read()

        required_methods = [
            "_start_interactive_analysis",
            "_process_followup_question",
            "_generate_followup_prompt",
        ]

        for method in required_methods:
            if f"def {method}(" in content:
                print(f"✅ Method {method} is defined")
            else:
                print(f"❌ Method {method} is missing")
                return False

        # Check if the interactive call is added to _show_analysis_menu
        if "_start_interactive_analysis(analysis_type, target)" in content:
            print("✅ Interactive analysis is integrated into _show_analysis_menu")
        else:
            print("❌ Interactive analysis call is missing from _show_analysis_menu")
            return False

        return True

    except Exception as e:
        print(f"❌ Error checking methods: {e}")
        return False


if __name__ == "__main__":
    print("Validating Interactive AI Analysis Implementation...\n")

    # Check syntax
    syntax_ok = validate_syntax("ai_analyzer.py")

    # Check method definitions
    methods_ok = check_interactive_methods()

    print("\nValidation Summary:")
    print(f"Syntax: {'✅ Valid' if syntax_ok else '❌ Invalid'}")
    print(f"Methods: {'✅ Complete' if methods_ok else '❌ Incomplete'}")

    if syntax_ok and methods_ok:
        print("\n🎉 Interactive AI Analysis implementation is ready!")
        print("\nTo test the functionality:")
        print("1. Run: pm logs <service-name> -ai")
        print("2. After the initial analysis, you'll see the interactive prompt")
        print("3. Ask follow-up questions or press Enter to exit")
    else:
        print("\n⚠️  Implementation needs fixes before testing")
        sys.exit(1)
