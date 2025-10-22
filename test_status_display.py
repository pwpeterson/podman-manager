#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced status display functionality.
This script tests the new 'pm status' command that shows running status for each service.
"""

import subprocess
import sys


def test_status_display():
    """Test the enhanced status display functionality"""
    print("Testing enhanced 'pm status' command...")
    print("=" * 50)

    # Test the list command (should show all stacks and services with status)
    print("\n1. Testing 'pm list' command:")
    print("-" * 30)
    try:
        result = subprocess.run(
            [sys.executable, "podman_manager.py", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("✓ Command executed successfully")
            print("Output preview:")
            # Show first few lines of output
            lines = result.stdout.split("\n")[:10]
            for line in lines:
                if line.strip():
                    print(f"  {line}")
            if len(result.stdout.split("\n")) > 10:
                print("  ...")
        else:
            print("✗ Command failed")
            print(f"Error: {result.stderr}")

    except subprocess.TimeoutExpired:
        print("✗ Command timed out")
    except Exception as e:
        print(f"✗ Error running command: {e}")

    # Test with a specific target if available
    print("\n2. Testing 'pm status <target>' command:")
    print("-" * 40)

    # Try to find available targets first
    try:
        result = subprocess.run(
            [sys.executable, "podman_manager.py", "targets"],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0 and "vllm" in result.stdout.lower():
            # Try with vllm-stack if available
            print("Testing with 'vllm-stack' target...")
            result = subprocess.run(
                [sys.executable, "podman_manager.py", "status", "vllm-stack"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                print("✓ Status command with target executed successfully")
                print("Output preview:")
                lines = result.stdout.split("\n")[:8]
                for line in lines:
                    if line.strip():
                        print(f"  {line}")
            else:
                print("✗ Status command with target failed")
                print(f"Error: {result.stderr}")
        else:
            print("No specific targets available for testing")

    except Exception as e:
        print(f"✗ Error testing with target: {e}")

    print("\n" + "=" * 50)
    print("Test completed!")
    print("\nExpected enhancements:")
    print("• Tree view shows 'Stacks & Services' instead of 'Projects & Services'")
    print(
        "• Each service shows running status: > [green]running[/green], [red]failed[/red], [dim]not found[/dim], etc."
    )
    print(
        "• Status examples: 'local-ai-caddy > running', 'supabase-db > healthy', 'user-mgmt-api > not found'"
    )


if __name__ == "__main__":
    test_status_display()
