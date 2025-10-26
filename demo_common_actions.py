#!/usr/bin/env python3
"""
Demonstration script for the new Common Actions system
Shows how the standardized "More available actions" work across all pm commands
"""

from core.config import console
from operations.common_actions import (
    CommonActionsFormatter,
    show_common_actions,
    show_compact_actions,
    show_essential_actions,
)


def demo_basic_usage():
    """Demonstrate basic usage of common actions"""
    console.print("[bold blue]Demo: Basic Common Actions Usage[/bold blue]")
    console.print("=" * 50)

    # Example 1: Essential actions for a service
    console.print(
        "\n[bold cyan]Example 1: Essential actions for vllm-qwen25[/bold cyan]"
    )
    show_essential_actions("vllm-qwen25")

    # Example 2: Compact format
    console.print(
        "\n[bold cyan]Example 2: Compact format for supabase-analytics[/bold cyan]"
    )
    show_compact_actions(target="supabase-analytics", port="3000")

    # Example 3: Full detailed format
    console.print(
        "\n[bold cyan]Example 3: Detailed format with all categories[/bold cyan]"
    )
    show_common_actions(
        target="vllm-delegator",
        service_name="vllm-delegator.service",
        container_name="vllm-delegator",
        port="8002",
        categories=None,  # Show all categories
        compact=False,
    )


def demo_category_specific():
    """Demonstrate category-specific actions"""
    console.print("\n[bold blue]Demo: Category-Specific Actions[/bold blue]")
    console.print("=" * 50)

    formatter = CommonActionsFormatter()

    # Show available categories
    console.print("\n[bold cyan]Available Categories:[/bold cyan]")
    formatter.show_all_categories()

    # Show specific categories
    console.print("\n[bold cyan]Network & Connectivity Actions:[/bold cyan]")
    formatter.show_category_actions(
        "network_connectivity", target="studio", port="3000"
    )

    console.print("\n[bold cyan]Container Operations:[/bold cyan]")
    formatter.show_category_actions(
        "container_ops", target="supabase-storage", container_name="supabase-storage"
    )


def demo_integration_examples():
    """Show how this integrates with existing pm commands"""
    console.print("\n[bold blue]Demo: Integration with PM Commands[/bold blue]")
    console.print("=" * 50)

    # Simulate different pm command completions
    scenarios = [
        {
            "command": "pm install supabase-analytics",
            "target": "supabase-analytics",
            "categories": ["service_management", "service_status", "logs_diagnostics"],
        },
        {
            "command": "pm reinit vllm-qwen25",
            "target": "vllm-qwen25",
            "categories": ["pm_shortcuts", "service_status", "logs_diagnostics"],
        },
        {
            "command": "pm diag studio",
            "target": "studio",
            "categories": ["troubleshooting", "logs_diagnostics", "system_resources"],
        },
    ]

    for scenario in scenarios:
        console.print(f"\n[bold cyan]After: {scenario['command']}[/bold cyan]")
        show_common_actions(
            target=scenario["target"], categories=scenario["categories"], compact=False
        )


def demo_customization():
    """Show customization capabilities"""
    console.print("\n[bold blue]Demo: Customization Examples[/bold blue]")
    console.print("=" * 50)

    formatter = CommonActionsFormatter()

    # Custom port and container name
    console.print(
        "\n[bold cyan]Custom Configuration (port 9000, custom container):[/bold cyan]"
    )
    formatter.show_common_actions(
        target="custom-service",
        service_name="custom-service.service",
        container_name="my-custom-container",
        port="9000",
        categories=["network_connectivity", "container_ops"],
        compact=False,
    )

    # Show how placeholders work
    console.print("\n[bold cyan]Placeholder Substitution Examples:[/bold cyan]")
    test_template = "systemctl --user status {service_name}"
    result = formatter._substitute_placeholders(
        test_template,
        target="test-service",
        service_name="test-service.service",
        container_name="test-container",
        port="8080",
    )
    console.print(f"Template: [dim]{test_template}[/dim]")
    console.print(f"Result:   [white]{result}[/white]")


def main():
    """Run all demonstrations"""
    console.print("[bold green]Common Actions System Demonstration[/bold green]")
    console.print("This shows the new standardized 'More available actions' system")
    console.print(
        "that provides consistent diagnostic and management commands across all pm commands.\n"
    )

    demo_basic_usage()
    demo_category_specific()
    demo_integration_examples()
    demo_customization()

    console.print("\n[bold green]Summary:[/bold green]")
    console.print("✓ Standardized actions across all pm commands")
    console.print("✓ Categorized commands for different use cases")
    console.print("✓ Compact and detailed display formats")
    console.print("✓ Dynamic placeholder substitution")
    console.print("✓ Easy integration with existing codebase")
    console.print(
        "\n[dim]The system replaces inconsistent 'Optional actions' with a comprehensive, standardized set of diagnostic and management commands.[/dim]"
    )


if __name__ == "__main__":
    main()
