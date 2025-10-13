#!/usr/bin/env python3
"""
Podman Container Management Script with Rich Console Output
Refactored modular version of the original podman-manager.py
"""

import argparse
import os
import sys

from config import console
from container_ops import ContainerOperations
from display import DisplayManager
from manager import PodmanManager


def show_rich_help():
    """Show beautiful Rich-formatted help"""
    from rich.panel import Panel
    from rich.table import Table

    console.print("[bold blue]Podman Container Manager[/bold blue]")

    console.print()
    console.print("[bold]USAGE:[/bold]")
    console.print(
        "  [cyan]python podman_manager.py[/cyan] [dim][OPTIONS][/dim] [green]COMMAND[/green] [dim][ARGS][/dim]"
    )
    console.print(
        "  [cyan]pm[/cyan] [green]COMMAND[/green] [dim][ARGS][/dim]                    [dim]# Short alias[/dim]"
    )

    console.print()
    console.print("[bold]GLOBAL OPTIONS:[/bold]")
    options_table = Table(show_header=False, box=None, padding=(0, 2))
    options_table.add_column("Option", style="yellow", width=25)
    options_table.add_column("Description", style="white")
    options_table.add_row("--compose-dir PATH", "Compose files directory")
    options_table.add_row("-h, --help", "Show this help message")
    console.print(options_table)

    console.print()
    console.print("[bold]COMMANDS:[/bold]")

    # Create command categories
    categories = [
        (
            "Status & Information",
            [
                ("status", "Show projects and services tree", "pm status"),
                ("ps", "Container status table", "pm ps"),
                ("images [--all]", "Show container images", "pm images"),
                ("stats [--follow]", "Show container resource usage", "pm stats"),
                ("events [--since TIME]", "Show container events", "pm events"),
            ],
        ),
        (
            "Container Lifecycle",
            [
                ("reinit TARGET", "Remove and recreate containers", "pm reinit ollama"),
                ("restart TARGET", "Quick restart containers", "pm restart app"),
                ("stop TARGET", "Gracefully stop containers", "pm stop vllm-models"),
                ("remove TARGET", "Remove containers", "pm remove old-service"),
                ("pull TARGET", "Pull latest images", "pm pull app"),
            ],
        ),
        (
            "Build & Images",
            [
                (
                    "build TARGET [--no-cache]",
                    "Build container images",
                    "pm build app --no-cache",
                ),
                ("prune", "Remove unused images and containers", "pm prune"),
                ("system-df", "Show disk usage", "pm system-df"),
            ],
        ),
        (
            "Resources",
            [
                ("volumes", "List volumes", "pm volumes"),
                ("networks", "List networks", "pm networks"),
                (
                    "logs TARGET [--follow]",
                    "Show container logs",
                    "pm logs app --follow",
                ),
                (
                    "exec TARGET COMMAND",
                    "Execute command in container",
                    "pm exec app bash",
                ),
            ],
        ),
    ]

    for category, commands in categories:
        console.print(f"\n[bold cyan]{category}:[/bold cyan]")
        cmd_table = Table(show_header=False, box=None, padding=(0, 2))
        cmd_table.add_column("Command", style="green", width=25)
        cmd_table.add_column("Description", style="white", width=35)
        cmd_table.add_column("Example", style="dim", width=25)

        for cmd, desc, example in commands:
            cmd_table.add_row(cmd, desc, example)
        console.print(cmd_table)

    console.print()
    console.print("[bold]ENVIRONMENT:[/bold]")
    console.print(
        "  [yellow]PODMAN_COMPOSE_DIR[/yellow]  Directory containing compose files"
    )
    console.print(
        "                        [dim](default: ~/srv/local-ai-packaged)[/dim]"
    )

    console.print()
    console.print("[bold]EXAMPLES:[/bold]")
    examples_table = Table(show_header=False, box=None, padding=(0, 2))
    examples_table.add_column("Command", style="cyan", width=35)
    examples_table.add_column("Description", style="white")
    examples_table.add_row("pm status", "Show all projects and their services")
    examples_table.add_row(
        "pm reinit ollama --build", "Rebuild and restart ollama service"
    )
    examples_table.add_row("pm logs app --follow", "Follow logs for app service")
    examples_table.add_row("pm stats --follow", "Monitor resource usage in real-time")
    examples_table.add_row("pm exec app bash", "Open bash shell in app container")
    console.print(examples_table)

    console.print()
    console.print("[bold]TIPS:[/bold]")
    console.print(
        "  • Use [cyan]--dry-run[/cyan] with reinit to see what would be done"
    )
    console.print("  • TARGET can be a project name or specific service name")
    console.print("  • Use [cyan]--remove-orphans[/cyan] to clean up unused containers")
    console.print("  • Press [cyan]Ctrl+C[/cyan] to interrupt long-running operations")
    console.print("  • Check [cyan]pm status[/cyan] first to see available targets")


def main():
    """Main entry point for refactored podman manager"""
    parser = argparse.ArgumentParser(
        description="Podman Container Manager with Rich UI (Refactored)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )

    parser.add_argument("--compose-dir", help="Compose directory path")
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status and info commands
    subparsers.add_parser("status", help="Show project status")
    subparsers.add_parser("ps", help="Show container status")
    subparsers.add_parser("help", help="Show detailed help")

    # Container lifecycle commands
    reinit_parser = subparsers.add_parser("reinit", help="Reinitialize containers")
    reinit_parser.add_argument("target", nargs="?", help="Project or service name")
    reinit_parser.add_argument("--build", action="store_true", help="Rebuild images")
    reinit_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    reinit_parser.add_argument(
        "--remove-orphans", action="store_true", help="Remove orphaned containers"
    )

    restart_parser = subparsers.add_parser("restart", help="Restart services")
    restart_parser.add_argument("target", nargs="?", help="Project or service name")
    restart_parser.add_argument(
        "--remove-orphans", action="store_true", help="Remove orphaned containers"
    )

    stop_parser = subparsers.add_parser("stop", help="Stop services")
    stop_parser.add_argument("target", nargs="?", help="Project or service name")
    stop_parser.add_argument(
        "--remove-orphans", action="store_true", help="Remove orphaned containers"
    )

    args = parser.parse_args()

    # Handle help with Rich formatting
    if args.help or (not args.command and len(sys.argv) == 1):
        show_rich_help()
        return

    # Set compose directory from environment variable if not provided
    compose_dir = args.compose_dir or os.environ.get("PODMAN_COMPOSE_DIR")

    try:
        # Initialize the manager and components
        manager = PodmanManager(compose_dir)
        container_ops = ContainerOperations(manager)
        display = DisplayManager(manager)

        # Route commands to appropriate modules
        if args.command == "status":
            display.show_status()
        elif args.command == "ps":
            display.show_ps()
        elif args.command == "help":
            show_rich_help()
        elif args.command == "reinit":
            if not args.target:
                display.show_available_targets("reinit")
                sys.exit(1)
            success = container_ops.reinit(
                args.target,
                build=args.build,
                dry_run=args.dry_run,
                remove_orphans=args.remove_orphans,
            )
            sys.exit(0 if success else 1)
        elif args.command == "restart":
            if not args.target:
                display.show_available_targets("restart")
                sys.exit(1)
            success = container_ops.restart(
                args.target, remove_orphans=args.remove_orphans
            )
            sys.exit(0 if success else 1)
        elif args.command == "stop":
            if not args.target:
                display.show_available_targets("stop")
                sys.exit(1)
            success = container_ops.stop(
                args.target, remove_orphans=args.remove_orphans
            )
            sys.exit(0 if success else 1)
        else:
            console.print(f"[red]Unknown command: {args.command}[/red]")
            console.print("[dim]Use --help to see available commands[/dim]")
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception:
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
