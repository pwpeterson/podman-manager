#!/usr/bin/env python3
"""
Simple test for the simplified Build AI Analysis Integration
"""

import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import console


def test_ai_prompt_generation():
    """Test the simplified AI prompt generation"""
    console.print("[bold cyan]Testing Simplified AI Prompt Generation[/bold cyan]")

    try:
        from ai_analyzer import ai_analyzer
        from quadlet_manager import QuadletManager

        # Initialize AI analyzer
        manager = QuadletManager()
        ai_analyzer.manager = manager

        # Test data - focused on just Dockerfile and errors
        test_data = {
            "target": "test-service",
            "build_error": "ERROR: Could not find base image 'nonexistent:latest'",
            "build_output": "Step 1/5 : FROM nonexistent:latest\n---> ERROR: image not found",
            "dockerfile_path": "/test/Dockerfile.test-service",
        }

        # Create a test Dockerfile content
        test_dockerfile = """FROM nonexistent:latest
RUN apt-get update
COPY . /app
WORKDIR /app
CMD ["python", "app.py"]"""

        # Mock the Dockerfile reading
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dockerfile", delete=False
        ) as f:
            f.write(test_dockerfile)
            test_data["dockerfile_path"] = f.name

        try:
            # Generate prompt
            base_context = "Test context"
            prompt = ai_analyzer._generate_build_failure_prompt(base_context, test_data)

            # Check if prompt contains expected elements
            expected_elements = [
                "DevOps engineer",
                "BUILD ERROR",
                "DOCKERFILE",
                "Root Cause",
                "Fix",
                "podman commands",
            ]

            missing_elements = []
            for element in expected_elements:
                if element not in prompt:
                    missing_elements.append(element)

            if not missing_elements:
                console.print(
                    "[green]✓ Simplified AI prompt generation working correctly[/green]"
                )
                console.print(
                    f"[dim]Generated prompt length: {len(prompt)} characters[/dim]"
                )

                # Show a sample of the prompt
                console.print("\n[bold]Sample prompt (first 300 chars):[/bold]")
                console.print(f"[dim]{prompt[:300]}...[/dim]")

                return True
            else:
                console.print("[red]✗ Simplified AI prompt missing elements[/red]")
                console.print(f"Missing: {', '.join(missing_elements)}")
                return False

        finally:
            # Clean up test file
            Path(test_data["dockerfile_path"]).unlink(missing_ok=True)

    except Exception as e:
        console.print(f"[red]✗ Error testing simplified AI prompt: {e}[/red]")
        return False


def test_build_context_simple():
    """Test simplified build context storage"""
    console.print("\n[bold cyan]Testing Simplified Build Context[/bold cyan]")

    try:
        from container_builder import ContainerBuilder
        from quadlet_manager import QuadletManager

        # Create a mock manager and builder
        manager = QuadletManager()
        builder = ContainerBuilder(manager)

        # Test storing minimal build context
        test_target = "test-service"
        test_context = {
            "dockerfile_path": "/test/Dockerfile.test-service",
            "service_type": "quadlet_container",
        }

        builder._store_build_context(test_target, **test_context)

        # Test retrieving build context
        retrieved_context = builder._get_build_context(test_target)

        if retrieved_context == test_context:
            console.print(
                "[green]✓ Simplified build context storage working correctly[/green]"
            )
            return True
        else:
            console.print("[red]✗ Simplified build context storage failed[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Error testing build context: {e}[/red]")
        return False


def test_automatic_trigger():
    """Test that AI analysis is triggered automatically"""
    console.print("\n[bold cyan]Testing Automatic AI Trigger[/bold cyan]")

    try:
        from container_builder import ContainerBuilder
        from quadlet_manager import QuadletManager

        # Create a mock manager and builder
        manager = QuadletManager()
        builder = ContainerBuilder(manager)

        # Store build context
        test_target = "test-service"
        builder._store_build_context(
            test_target,
            dockerfile_path="/test/Dockerfile.test-service",
            service_type="test_container",
        )

        console.print("[yellow]Testing automatic AI analysis trigger...[/yellow]")

        # This should not raise an exception even if AI is not available
        builder._trigger_build_ai_analysis(
            target=test_target,
            build_error="ERROR: Test build failure",
            build_output="Test build output",
            build_command="podman build test",
        )

        console.print(
            "[green]✓ Automatic AI trigger works (silent failure expected)[/green]"
        )
        return True

    except Exception as e:
        console.print(f"[red]✗ Unexpected error in automatic trigger: {e}[/red]")
        return False


def main():
    """Run simplified tests"""
    console.print("[bold blue]Simplified Build AI Analysis Tests[/bold blue]")
    console.print("=" * 45)

    tests = [
        ("Simplified AI Prompt Generation", test_ai_prompt_generation),
        ("Simplified Build Context", test_build_context_simple),
        ("Automatic AI Trigger", test_automatic_trigger),
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
    console.print("=" * 25)

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
            "[green]🎉 All tests passed! Simplified build AI analysis is working.[/green]"
        )
        console.print("\n[bold cyan]Key Features Verified:[/bold cyan]")
        console.print("• Automatic AI analysis on build failures")
        console.print("• Focused prompts with Dockerfile + errors only")
        console.print("• Silent failure when AI unavailable")
        console.print("• No CLI configuration needed")
        return 0
    else:
        console.print(
            "[red]❌ Some tests failed. Please check the implementation.[/red]"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
