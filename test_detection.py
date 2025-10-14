#!/usr/bin/env python3
"""Test script for project type detection."""

from rich.table import Table

from config import console
from project_detector import ProjectTypeDetector


def test_detection():
    """Test the project type detection logic"""
    detector = ProjectTypeDetector()

    # Test cases
    test_cases = [
        "vllm-qwen25",
        "vllm-proxy",
        "vllm-delegator",
        "vllm-stack",
        "stack",
        "unknown-service",
        "test.service",
        "nonexistent",
    ]

    console.print("[bold blue]Project Type Detection Test[/bold blue]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Target", style="cyan", no_wrap=True)
    table.add_column("Detected Type", style="green", no_wrap=True)
    table.add_column("Reason", style="white")

    for target in test_cases:
        project_type, reason = detector.detect_project_type(target)
        table.add_row(target, project_type, reason)

    console.print(table)

    # Test intelligent mode selection
    console.print("\n[bold blue]Intelligent Mode Selection Test[/bold blue]\n")

    mode_table = Table(show_header=True, header_style="bold magenta")
    mode_table.add_column("Target", style="cyan", no_wrap=True)
    mode_table.add_column("User Mode", style="yellow", no_wrap=True)
    mode_table.add_column("Selected Mode", style="green", no_wrap=True)
    mode_table.add_column("Reason", style="white")

    mode_test_cases = [
        ("vllm-qwen25", None),
        ("vllm-qwen25", "compose"),
        ("unknown-service", None),
        (None, None),
        ("vllm-stack", "auto"),
    ]

    for target, user_mode in mode_test_cases:
        selected_mode, reason = detector.get_intelligent_mode(target, user_mode)
        mode_table.add_row(target or "None", user_mode or "None", selected_mode, reason)

    console.print(mode_table)

    # Test available targets
    console.print("\n[bold blue]Available Targets[/bold blue]\n")

    available_targets = detector.list_available_targets()

    targets_table = Table(show_header=True, header_style="bold magenta")
    targets_table.add_column("Type", style="cyan", no_wrap=True)
    targets_table.add_column("Count", style="yellow", no_wrap=True)
    targets_table.add_column("Targets", style="white")

    for target_type, targets in available_targets.items():
        if targets:
            targets_table.add_row(
                target_type.title(),
                str(len(targets)),
                ", ".join(targets[:5]) + ("..." if len(targets) > 5 else ""),
            )
        else:
            targets_table.add_row(target_type.title(), "0", "None found")

    console.print(targets_table)

    # Test fallback suggestions
    console.print("\n[bold blue]Fallback Suggestions Test[/bold blue]\n")

    fallback_table = Table(show_header=True, header_style="bold magenta")
    fallback_table.add_column("Target", style="cyan", no_wrap=True)
    fallback_table.add_column("Current Mode", style="yellow", no_wrap=True)
    fallback_table.add_column("Suggested Alternative", style="green", no_wrap=True)

    fallback_test_cases = [
        ("vllm-qwen25", "compose"),
        ("unknown-service", "quadlet"),
        ("vllm-proxy", "compose"),
        ("nonexistent", "quadlet"),
    ]

    for target, current_mode in fallback_test_cases:
        alternative = detector.suggest_alternative_mode(target, current_mode)
        fallback_table.add_row(target, current_mode, alternative or "None")

    console.print(fallback_table)


if __name__ == "__main__":
    test_detection()
