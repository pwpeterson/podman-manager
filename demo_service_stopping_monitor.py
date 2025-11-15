#!/usr/bin/env python3
"""Demo script showing enhanced service stopping monitoring"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def demo_service_stopping_monitor():
    """Demonstrate the enhanced service stopping monitoring output"""
    console.print("\n[bold cyan]🛑 Enhanced Service Stopping Monitor Demo[/bold cyan]")
    console.print(
        "This shows what users will see when monitoring services during stopping:\n"
    )

    # Scenario 1: Normal service stopping
    console.print(
        "[bold green]Scenario 1: Normal service stopping process[/bold green]"
    )
    console.print("[yellow]🛑 Monitoring service stopping: vllm-qwen25[/yellow]")

    # Show the live panel that would be displayed
    panel_content = """Service: [bold cyan]vllm-qwen25[/bold cyan]
Status: [yellow]Deactivating[/yellow]
Elapsed: [dim]2.3s[/dim]
Details: [dim]Service is deactivating[/dim]
[yellow]⏳ Stopping in progress...[/yellow]"""

    console.print(
        Panel(
            panel_content,
            title="[bold]Service Stopping Monitor[/bold]",
            border_style="yellow",
            padding=(1, 2),
        )
    )

    console.print("[green]✅ Service vllm-qwen25 stopped successfully in 4.1s[/green]")
    console.print()

    # Scenario 2: Service stuck during stopping
    console.print("[bold red]Scenario 2: Service stuck during stopping[/bold red]")
    console.print(
        "[yellow]🛑 Monitoring service stopping: problematic-service[/yellow]"
    )

    panel_content_stuck = """Service: [bold cyan]problematic-service[/bold cyan]
Status: [yellow]Sending SIGKILL[/yellow]
Elapsed: [dim]15.7s[/dim]
Details: [dim]Force killing service[/dim]
[red]⚠️  Service appears stuck[/red]"""

    console.print(
        Panel(
            panel_content_stuck,
            title="[bold]Service Stopping Monitor[/bold]",
            border_style="yellow",
            padding=(1, 2),
        )
    )

    console.print(
        "[red]⚠️  Service problematic-service appears stuck during stopping[/red]"
    )
    console.print()

    # Scenario 3: Container stopping monitoring
    console.print("[bold blue]Scenario 3: Container stopping monitoring[/bold blue]")
    console.print("[yellow]🐳 Monitoring container stopping: vllm-container[/yellow]")

    panel_content_container = """Container: [bold cyan]vllm-container[/bold cyan]
Status: [yellow]Stopping[/yellow]
Elapsed: [dim]1.8s[/dim]
[yellow]⏳ Stopping in progress...[/yellow]"""

    console.print(
        Panel(
            panel_content_container,
            title="[bold]Container Stopping Monitor[/bold]",
            border_style="blue",
            padding=(1, 2),
        )
    )

    console.print("[green]✅ Container vllm-container stopped in 3.2s[/green]")
    console.print()

    # Show the different status types
    console.print("[bold cyan]📊 Service Stopping Status Types[/bold cyan]")

    status_table = Table(show_header=True, header_style="bold cyan", box=None)
    status_table.add_column("Status", style="white", width=20)
    status_table.add_column("Meaning", style="dim", width=40)
    status_table.add_column("Action", width=20)

    status_types = [
        (
            "Still Running",
            "Service hasn't started stopping yet",
            "[yellow]Continue monitoring[/yellow]",
        ),
        (
            "Deactivating",
            "Service is gracefully shutting down",
            "[green]Normal process[/green]",
        ),
        (
            "Sending SIGTERM",
            "Graceful shutdown signal sent",
            "[green]Normal process[/green]",
        ),
        ("Sending SIGKILL", "Force kill signal sent", "[red]Service stuck[/red]"),
        ("Stopped", "Service successfully stopped", "[green]Complete[/green]"),
        ("Failed", "Service failed during stop", "[red]Investigate[/red]"),
    ]

    for status, meaning, action in status_types:
        status_table.add_row(status, meaning, action)

    console.print(status_table)
    console.print()

    console.print("[bold green]✨ Service Stopping Monitor Benefits:[/bold green]")
    console.print("• [green]Real-time visibility[/green] into service stopping process")
    console.print(
        "• [green]Detailed status tracking[/green] (deactivating, SIGTERM, SIGKILL, etc.)"
    )
    console.print("• [green]Stuck service detection[/green] with early warning")
    console.print("• [green]Timeout handling[/green] prevents indefinite waiting")
    console.print("• [green]Live updating display[/green] with elapsed time tracking")
    console.print(
        "• [green]Container monitoring[/green] support for containerized services"
    )
    console.print("• [green]Graceful vs forced[/green] shutdown distinction")
    console.print("• [green]Integration ready[/green] for reinit operations")


if __name__ == "__main__":
    demo_service_stopping_monitor()
