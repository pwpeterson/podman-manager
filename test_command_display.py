#!/usr/bin/env python3
"""
Test script to verify the new command display functionality
"""

import subprocess
import sys


def test_command_display():
    """Test the new command display functionality"""

    # Test commands that should show different displays
    test_cases = [
        # Stack-only commands
        ("down", "Should show only stacks"),
        ("install", "Should show only stacks"),
        ("uninstall", "Should show only stacks"),
        # Service-only commands
        ("logs", "Should show hierarchy with dimmed stacks"),
        ("exec", "Should show hierarchy with dimmed stacks"),
        ("diagnose", "Should show hierarchy with dimmed stacks"),
        # Mixed commands
        ("start", "Should show full hierarchy"),
        ("stop", "Should show full hierarchy"),
        ("restart", "Should show full hierarchy"),
    ]

    print("Testing command display functionality...")
    print("=" * 50)

    for command, description in test_cases:
        print(f"\nTesting: pm {command}")
        print(f"Expected: {description}")
        print("-" * 30)

        # Run the command without arguments to trigger the error display
        try:
            result = subprocess.run(
                [sys.executable, "podman_manager.py", command],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                print("STDOUT:")
                print(result.stdout)
                if result.stderr:
                    print("STDERR:")
                    print(result.stderr)
            else:
                print("Command succeeded unexpectedly")

        except subprocess.TimeoutExpired:
            print("Command timed out")
        except Exception as e:
            print(f"Error running command: {e}")


if __name__ == "__main__":
    test_command_display()
