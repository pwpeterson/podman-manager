#!/usr/bin/env python3
"""Demo script showing enhanced AI agent selection output"""

from rich.console import Console

console = Console()


def demo_ai_agent_selection():
    """Demonstrate the enhanced AI agent selection output"""
    console.print("\n[bold cyan]🔍 Enhanced AI Diagnostic Analysis Demo[/bold cyan]")
    console.print("This shows what users will see when AI agents are being selected:\n")

    # Scenario 1: Default agent available
    console.print("[bold green]Scenario 1: Default agent is available[/bold green]")
    console.print("[cyan]🤖 AI Agent Selection:[/cyan]")
    console.print(
        "  [green]✅[/green] GLM-4.1-9B-Thinking - [green]Selected for analysis[/green]"
    )
    console.print()

    # Scenario 2: Default agent not available, fallback successful
    console.print(
        "[bold yellow]Scenario 2: Default agent unavailable, fallback successful[/bold yellow]"
    )
    console.print("[cyan]🤖 AI Agent Selection:[/cyan]")
    console.print(
        "  [red]❌[/red] GLM-4.1-9B-Thinking - [yellow]Connection refused (service not running) (default)[/yellow]"
    )
    console.print(
        "  [green]✅[/green] GLM-4-9B-Chat - [green]Available (fallback)[/green]"
    )
    console.print(
        "  [green]✅[/green] GLM-4-9B-Chat - [green]Selected for analysis[/green]"
    )
    console.print()

    # Scenario 3: Multiple agents unavailable
    console.print("[bold red]Scenario 3: Multiple agents unavailable[/bold red]")
    console.print("[cyan]🤖 AI Agent Selection:[/cyan]")
    console.print(
        "  [red]❌[/red] GLM-4.1-9B-Thinking - [yellow]Connection refused (service not running) (requested)[/yellow]"
    )
    console.print("  [red]❌[/red] GLM-4-9B-Chat - [yellow]Connection timeout[/yellow]")
    console.print(
        "  [red]❌[/red] claude-sonnet-4-5 - [yellow]Missing ANTHROPIC_API_KEY environment variable[/yellow]"
    )
    console.print(
        "  [red]❌[/red] GPT-4 - [yellow]Missing OPENAI_API_KEY environment variable[/yellow]"
    )
    console.print("  [cyan]Checking all configured agents...[/cyan]")
    console.print("  [red]❌[/red] No available AI agents found")
    console.print("[red]No available AI agents found[/red]")
    console.print()

    # Scenario 4: Fixed configuration shows proper fallback order
    console.print(
        "[bold green]Scenario 4: Fixed configuration with proper fallback order[/bold green]"
    )
    console.print("[cyan]🤖 AI Agent Selection:[/cyan]")
    console.print(
        "  [red]❌[/red] GLM-4.1-9B-Thinking - [yellow]Connection refused (service not running) (default)[/yellow]"
    )
    console.print(
        "  [green]✅[/green] GLM-4-9B-Chat - [green]Available (fallback)[/green]"
    )
    console.print(
        "  [green]✅[/green] GLM-4-9B-Chat - [green]Selected for analysis[/green]"
    )
    console.print(
        "\n[cyan]Note: With fixed endpoints (http://localhost:8002 instead of http://localhost:8002:8002),[/cyan]"
    )
    console.print(
        "[cyan]local vLLM agents will now be properly checked and prioritized over cloud agents.[/cyan]"
    )
    console.print()

    console.print("[bold green]✨ Enhancement Benefits:[/bold green]")
    console.print(
        "• [green]Clear visibility[/green] into which AI agents are being tried"
    )
    console.print(
        "• [green]Detailed feedback[/green] on why agents are unavailable (connection issues, missing API keys, etc.)"
    )
    console.print(
        "• [green]Transparent fallback[/green] process with step-by-step logging"
    )
    console.print(
        "• [green]Uses configured[/green] fallback order from ai_agents_config.json"
    )
    console.print(
        "• [green]Helpful status icons[/green] (✅ available, ❌ unavailable)"
    )
    console.print(
        "• [green]Fixed configuration[/green] ensures local vLLM agents are properly prioritized"
    )
    console.print(
        "• [green]Troubleshooting friendly[/green] with specific error messages for each failure type"
    )


if __name__ == "__main__":
    demo_ai_agent_selection()
