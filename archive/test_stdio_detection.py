#!/usr/bin/env python3
"""Test script for STDIO service detection."""

from rich.console import Console
from rich.table import Table

from core.service_discovery import get_service_discovery

console = Console()


def test_stdio_detection():
    """Test STDIO service detection."""
    console.print("\n[bold cyan]Testing STDIO Service Detection[/bold cyan]\n")

    # Get service discovery instance
    discovery = get_service_discovery()

    # Check if STDIO services were discovered
    console.print(
        f"[green]STDIO services found:[/green] {len(discovery.stdio_services)}"
    )

    if discovery.stdio_services:
        table = Table(
            title="STDIO Services", show_header=True, header_style="bold magenta"
        )
        table.add_column("Service Name", style="cyan")
        table.add_column("Stack", style="green")
        table.add_column("Description", style="white")
        table.add_column("Managed By", style="yellow")

        for service_name, config in discovery.stdio_services.items():
            table.add_row(
                service_name,
                config.get("stack", "N/A"),
                config.get("description", "N/A"),
                config.get("managed_by", "N/A"),
            )

        console.print(table)
        console.print()

        # Test service status
        for service_name in discovery.stdio_services.keys():
            status = discovery.service_status.get(service_name, {})
            console.print(f"[cyan]{service_name}[/cyan] status:")
            console.print(f"  - Installed: {status.get('installed', False)}")
            console.print(f"  - Source: {status.get('source', False)}")
            console.print(f"  - STDIO: {status.get('stdio', False)}")
            console.print(
                f"  - Is STDIO Service: {discovery.is_stdio_service(service_name)}"
            )
            console.print()
    else:
        console.print("[yellow]No STDIO services found[/yellow]")
        console.print(f"[dim]Config path: {discovery.stdio_config_path}[/dim]")
        console.print(
            f"[dim]Config exists: {discovery.stdio_config_path.exists()}[/dim]"
        )

    # Check stack services
    console.print("\n[bold cyan]Stack Services (including STDIO):[/bold cyan]\n")
    for stack_name, services in discovery.stack_services.items():
        console.print(f"[green]{stack_name}:[/green]")
        for service in services:
            is_stdio = discovery.is_stdio_service(service)
            marker = "[cyan](STDIO)[/cyan]" if is_stdio else ""
            console.print(f"  - {service} {marker}")
        console.print()


if __name__ == "__main__":
    test_stdio_detection()
