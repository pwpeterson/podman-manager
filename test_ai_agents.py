#!/usr/bin/env python3
"""Test script to demonstrate the AI agent selection system"""

from ai_agents import ai_agent_manager
from config import console


def main():
    """Test the AI agent system"""
    console.print("[bold cyan]Testing AI Agent Selection System[/bold cyan]\n")

    # Show all available agents
    ai_agent_manager.show_agents_status()

    # Test a simple prompt
    test_prompt = """Analyze this log entry:
Oct 23 10:30:15 server systemd[1234]: Failed to start my-service.service
Oct 23 10:30:15 server systemd[1234]: my-service.service: Main process exited, code=exited, status=1/FAILURE

What could be the cause and how to fix it?"""

    console.print("\n[bold green]Testing AI Analysis with Default Agent:[/bold green]")
    result = ai_agent_manager.analyze_with_agent(test_prompt, verbose=True)

    if result:
        console.print("\n[bold yellow]AI Analysis Result:[/bold yellow]")
        console.print(result[:200] + "..." if len(result) > 200 else result)
    else:
        console.print("\n[red]No AI analysis result (no agents available)[/red]")

    # List available agents
    available = ai_agent_manager.list_available_agents()
    console.print(
        f"\n[dim]Available agents: {', '.join(available) if available else 'None'}[/dim]"
    )


if __name__ == "__main__":
    main()
