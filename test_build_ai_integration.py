#!/usr/bin/env python3
"""
Test script for Build AI Analysis Integration

This script tests the AI analysis integration for container build failures
without actually running builds that might fail.
"""

import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ai_analyzer import ai_analyzer
from config import console
from container_builder import ContainerBuilder
from quadlet_manager import QuadletManager


def test_build_context_storage():
    """Test build context storage functionality"""
    console.print("\n[bold cyan]Testing Build Context Storage[/bold cyan]")

    # Create a mock manager and builder
    manager = QuadletManager()
    builder = ContainerBuilder(manager)

    # Test storing build context
    test_target = "test-service"
    test_context = {
        "dockerfile_path": "/test/Dockerfile.test-service",
        "build_dir": "/test/build",
        "image_name": "localhost/test-service:latest",
        "service_type": "quadlet_container",
    }

    builder._store_build_context(test_target, **test_context)

    # Test retrieving build context
    retrieved_context = builder._get_build_context(test_target)

    if retrieved_context == test_context:
        console.print("[green]✓ Build context storage working correctly[/green]")
        return True
    else:
        console.print("[red]✗ Build context storage failed[/red]")
        console.print(f"Expected: {test_context}")
        console.print(f"Got: {retrieved_context}")
        return False


def test_ai_analysis_trigger():
    """Test AI analysis trigger functionality"""
    console.print("\n[bold cyan]Testing AI Analysis Trigger[/bold cyan]")

    # Create a mock manager and builder
    manager = QuadletManager()
    builder = ContainerBuilder(manager)

    # Initialize AI analyzer
    ai_analyzer.manager = manager

    # Test data for build failure
    test_target = "test-service"
    test_build_error = "ERROR: Could not find base image 'nonexistent:latest'"
    test_build_output = "Step 1/5 : FROM nonexistent:latest\n---> ERROR\n"
    test_build_command = "podman build --no-cache -f Dockerfile.test-service -t localhost/test-service:latest ."

    # Store some build context first
    builder._store_build_context(
        test_target,
        dockerfile_path="/test/Dockerfile.test-service",
        build_dir="/test/build",
        image_name="localhost/test-service:latest",
        service_type="test_container",
    )

    console.print("[yellow]Simulating build failure AI analysis...[/yellow]")

    try:
        # This would normally trigger AI analysis, but we'll catch any errors
        # since we don't have a real AI agent running in test mode
        builder._trigger_build_ai_analysis(
            target=test_target,
            build_error=test_build_error,
            build_output=test_build_output,
            build_command=test_build_command,
        )
        console.print("[green]✓ AI analysis trigger executed without errors[/green]")
        return True
    except Exception as e:
        # Expected if no AI agent is available
        if "AI analysis failed" in str(e) or "No AI agent available" in str(e):
            console.print(
                "[yellow]⚠ AI analysis trigger works but no agent available (expected in test)[/yellow]"
            )
            return True
        else:
            console.print(f"[red]✗ Unexpected error in AI analysis trigger: {e}[/red]")
            return False


def test_build_failure_prompt_generation():
    """Test build failure prompt generation"""
    console.print("\n[bold cyan]Testing Build Failure Prompt Generation[/bold cyan]")

    # Test data
    base_context = "You are an expert system administrator and DevOps engineer.\n\nTarget: test-service\nAnalysis Type: build_failure\nTimestamp: 2024-01-01T12:00:00"

    test_data = {
        "target": "test-service",
        "build_command": "podman build --no-cache -f Dockerfile.test-service -t localhost/test-service:latest .",
        "build_error": "ERROR: Could not find base image 'nonexistent:latest'",
        "build_output": "Step 1/5 : FROM nonexistent:latest\n---> ERROR: image not found",
        "dockerfile_path": "/test/Dockerfile.test-service",
        "build_dir": "/test/build",
        "image_name": "localhost/test-service:latest",
        "service_type": "quadlet_container",
    }

    try:
        # Initialize AI analyzer
        manager = QuadletManager()
        ai_analyzer.manager = manager

        # Generate prompt
        prompt = ai_analyzer._generate_build_failure_prompt(base_context, test_data)

        # Check if prompt contains expected elements
        expected_elements = [
            "build failure",
            "Podman container",
            "BUILD INFORMATION",
            "BUILD ERROR",
            "BUILD OUTPUT",
            "Root Cause Analysis",
            "Immediate Fix",
            "podman commands",
        ]

        missing_elements = []
        for element in expected_elements:
            if element not in prompt:
                missing_elements.append(element)

        if not missing_elements:
            console.print(
                "[green]✓ Build failure prompt generation working correctly[/green]"
            )
            console.print(
                f"[dim]Generated prompt length: {len(prompt)} characters[/dim]"
            )
            return True
        else:
            console.print("[red]✗ Build failure prompt missing elements[/red]")
            console.print(f"Missing: {', '.join(missing_elements)}")
            return False

    except Exception as e:
        console.print(f"[red]✗ Error generating build failure prompt: {e}[/red]")
        return False


def test_cli_integration():
    """Test CLI argument parsing for build AI analysis"""
    console.print("\n[bold cyan]Testing CLI Integration[/bold cyan]")

    try:
        from cli.parser import create_argument_parser

        parser = create_argument_parser()

        # Test build command with AI options
        test_args = ["build", "test-service", "--ai-agent", "claude", "--verbose"]

        args = parser.parse_args(test_args)

        # Check if arguments are parsed correctly
        if (
            args.command == "build"
            and args.target == "test-service"
            and args.ai_agent == "claude"
            and args.verbose
        ):
            console.print("[green]✓ CLI integration working correctly[/green]")
            return True
        else:
            console.print("[red]✗ CLI integration failed[/red]")
            console.print(f"Parsed args: {args}")
            return False

    except Exception as e:
        console.print(f"[red]✗ Error testing CLI integration: {e}[/red]")
        return False


def main():
    """Run all tests"""
    console.print("[bold blue]Build AI Analysis Integration Tests[/bold blue]")
    console.print("=" * 50)

    tests = [
        ("Build Context Storage", test_build_context_storage),
        ("AI Analysis Trigger", test_ai_analysis_trigger),
        ("Build Failure Prompt Generation", test_build_failure_prompt_generation),
        ("CLI Integration", test_cli_integration),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            console.print(f"[red]✗ {test_name} failed with exception: {e}[/red]")
            results.append((test_name, False))

    # Summary
    console.print("\n[bold blue]Test Results Summary[/bold blue]")
    console.print("=" * 30)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "[green]PASS[/green]" if result else "[red]FAIL[/red]"
        console.print(f"{status} {test_name}")
        if result:
            passed += 1

    console.print(f"\n[bold]Results: {passed}/{total} tests passed[/bold]")

    if passed == total:
        console.print(
            "[green]🎉 All tests passed! Build AI analysis integration is working correctly.[/green]"
        )
        return 0
    else:
        console.print(
            "[red]❌ Some tests failed. Please check the implementation.[/red]"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
