#!/usr/bin/env python3
"""Test script to verify Claude agent configuration"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from ai_system.ai_agents import ai_agent_manager
from core.config import console


def test_claude_agent():
    """Test the Claude agent configuration"""
    console.print("[bold cyan]Testing Claude Agent Configuration[/bold cyan]")
    console.print()

    # Check if ANTHROPIC_API_KEY is set
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        console.print(
            f"[green]✓ ANTHROPIC_API_KEY is set (length: {len(api_key)})[/green]"
        )
    else:
        console.print("[red]✗ ANTHROPIC_API_KEY is not set[/red]")
        console.print("[yellow]Please set your Anthropic API key:[/yellow]")
        console.print("[dim]export ANTHROPIC_API_KEY=your_api_key_here[/dim]")
        return False

    # Get the Claude agent
    claude_agent = ai_agent_manager.get_agent("claude-sonnet-4.5")
    if not claude_agent:
        console.print("[red]✗ Claude agent not found[/red]")
        return False

    console.print(
        f"[green]✓ Claude agent found: {claude_agent.config.display_name}[/green]"
    )
    console.print(f"[dim]Model: {claude_agent.config.model_name}[/dim]")
    console.print()

    # Check if agent is available
    console.print("[cyan]Checking agent availability...[/cyan]")
    is_available = claude_agent.is_available()

    if is_available:
        console.print("[green]✓ Claude agent is available[/green]")
    else:
        console.print("[red]✗ Claude agent is not available[/red]")
        return False

    # Test with a simple prompt
    console.print()
    console.print("[cyan]Testing with a simple prompt...[/cyan]")
    test_prompt = "Hello! Please respond with 'Claude agent is working correctly' to confirm the connection."

    try:
        response = claude_agent.analyze_logs(test_prompt)
        if response:
            console.print("[green]✓ Claude agent responded successfully![/green]")
            console.print(
                f"[dim]Response: {response[:100]}{'...' if len(response) > 100 else ''}[/dim]"
            )
            return True
        else:
            console.print("[red]✗ Claude agent returned no response[/red]")
            return False
    except Exception as e:
        console.print(f"[red]✗ Error testing Claude agent: {e}[/red]")
        return False


def show_all_agents():
    """Show status of all agents"""
    console.print()
    console.print("[bold cyan]All AI Agents Status:[/bold cyan]")
    ai_agent_manager.show_agents_status()


if __name__ == "__main__":
    success = test_claude_agent()
    show_all_agents()

    if success:
        console.print()
        console.print(
            "[bold green]✓ Claude agent test completed successfully![/bold green]"
        )
        sys.exit(0)
    else:
        console.print()
        console.print("[bold red]✗ Claude agent test failed[/bold red]")
        sys.exit(1)
