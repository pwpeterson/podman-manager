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
                ("list [<project/service>]", "List projects and services", "pm list"),
                ("ps", "Container status table", "pm ps"),
                ("images [--all]", "Show container images", "pm images"),
                ("stats [--follow]", "Show container resource usage", "pm stats"),
                ("events [--since TIME]", "Show container events", "pm events"),
            ],
        ),
        (
            "Container Lifecycle",
            [
                ("reinit <project/service>", "Remove and recreate containers", "pm reinit <project/service>"),
                ("restart <project/service>", "Quick restart containers", "pm restart <project/service>"),
                ("stop <project/service>", "Gracefully stop containers", "pm stop <project/service>"),
                ("remove <project/service>", "Remove containers", "pm remove <project/service>"),
                ("pull <project/service>", "Pull latest images", "pm pull <project/service>"),
            ],
        ),
        (
            "Build & Images",
            [
                (
                    "build <project/service> [--no-cache]",
                    "Build container images",
                    "pm build <project/service> --no-cache",
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
                    "logs <project/service> [--follow]",
                    "Show container logs",
                    "pm logs <project/service> --follow",
                ),
                (
                    "exec <project/service> COMMAND",
                    "Execute command in container",
                    "pm exec <project/service> bash",
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
    examples_table.add_row("pm list", "Show all projects and their services")
    examples_table.add_row("pm list <project/service>", "Show details for specific project/service")
    examples_table.add_row("pm ps", "Show running containers status")
    examples_table.add_row("pm logs <project/service> --follow", "Follow logs for specific service")
    examples_table.add_row("pm stats --follow", "Monitor resource usage in real-time")
    examples_table.add_row("pm exec <project/service> bash", "Open bash shell in container")
    examples_table.add_row("pm reinit <project/service> --build", "Rebuild and restart service")
    examples_table.add_row("pm build <project/service> --no-cache", "Build without using cache")
    examples_table.add_row("pm remove <project/service>", "Remove specific containers")
    examples_table.add_row("pm pull <project/service>", "Pull latest images for service")
    examples_table.add_row("pm restart <project/service>", "Restart specific service")
    examples_table.add_row("pm stop <project/service>", "Stop specific service")
    examples_table.add_row("pm images --all", "Show all images including intermediates")
    examples_table.add_row("pm system-df", "Show disk usage by containers/images")
    examples_table.add_row("pm prune", "Clean up unused containers and images")
    examples_table.add_row("pm volumes", "List all volumes")
    examples_table.add_row("pm networks", "List all networks")
    examples_table.add_row("pm events --since 1h", "Show events from last hour")
    console.print(examples_table)

    console.print()
    console.print("[bold]TIPS:[/bold]")
    console.print(
        "  • Use [cyan]--dry-run[/cyan] with reinit to see what would be done"
    )
    console.print("  • TARGET can be a project name or specific service name")
    console.print("  • Use [cyan]--remove-orphans[/cyan] to clean up unused containers")
    console.print("  • Press [cyan]Ctrl+C[/cyan] to interrupt long-running operations")
    console.print("  • Check [cyan]pm list[/cyan] first to see available targets")


class CustomArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser with better error messages"""

    def error(self, message):
        """Override error method to show helpful messages"""
        if "invalid choice" in message:
            # Extract the invalid command from the message
            import re

            match = re.search(r"invalid choice: '([^']+)'", message)
            if match:
                invalid_cmd = match.group(1)
                console.print(f"[red]Error: Unknown command '{invalid_cmd}'[/red]")
                console.print(
                    "[dim]Run 'pm --help' to see all available commands[/dim]"
                )
                console.print(
                    "[dim]Did you mean one of: list, ps, logs, images, stats?[/dim]"
                )
                sys.exit(1)
        elif "unrecognized arguments" in message:
            console.print(f"[red]Error: {message}[/red]")
            console.print("[dim]Run 'pm --help' to see command usage[/dim]")
            sys.exit(1)
        else:
            console.print(f"[red]Error: {message}[/red]")
            console.print("[dim]Run 'pm --help' for help[/dim]")
            sys.exit(1)


def main():
    """Main entry point for refactored podman manager"""
    parser = CustomArgumentParser(
        description="Podman Container Manager with Rich UI (Refactored)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )

    parser.add_argument("--compose-dir", help="Compose directory path")
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status and info commands
    list_parser = subparsers.add_parser("list", help="List projects and services")
    list_parser.add_argument("target", nargs="?", help="Project or service name")
    
    # Keep 'status' as an alias for backward compatibility
    status_parser = subparsers.add_parser("status", help="Show project status (alias for list)")
    status_parser.add_argument("target", nargs="?", help="Project or service name")
    subparsers.add_parser("ps", help="Show container status")
    subparsers.add_parser("help", help="Show detailed help")

    # Additional status commands
    images_parser = subparsers.add_parser("images", help="Show container images")
    images_parser.add_argument("--all", action="store_true", help="Show all images")

    stats_parser = subparsers.add_parser("stats", help="Show container resource usage")
    stats_parser.add_argument(
        "--follow", action="store_true", help="Follow stats output"
    )

    events_parser = subparsers.add_parser("events", help="Show container events")
    events_parser.add_argument("--since", help="Show events since timestamp")

    # Resource commands
    logs_parser = subparsers.add_parser("logs", help="Show container logs")
    logs_parser.add_argument("target", help="Project or service name")
    logs_parser.add_argument("--follow", action="store_true", help="Follow log output")

    exec_parser = subparsers.add_parser("exec", help="Execute command in container")
    exec_parser.add_argument("target", help="Project or service name")
    exec_parser.add_argument("command", nargs="+", help="Command to execute")

    subparsers.add_parser("volumes", help="List volumes")
    subparsers.add_parser("networks", help="List networks")

    # Build and image commands
    build_parser = subparsers.add_parser("build", help="Build container images")
    build_parser.add_argument("target", help="Project or service name")
    build_parser.add_argument(
        "--no-cache", action="store_true", help="Build without cache"
    )

    subparsers.add_parser("prune", help="Remove unused images and containers")
    subparsers.add_parser("system-df", help="Show disk usage")

    # Additional lifecycle commands
    remove_parser = subparsers.add_parser("remove", help="Remove containers")
    remove_parser.add_argument("target", help="Project or service name")

    pull_parser = subparsers.add_parser("pull", help="Pull latest images")
    pull_parser.add_argument("target", help="Project or service name")

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
        if args.command == "list" or args.command == "status":
            if args.target:
                display.show_status(args.target)
            else:
                display.show_status()
        elif args.command == "ps":
            display.show_ps()
        elif args.command == "help":
            show_rich_help()
        elif args.command == "images":
            display.show_images(show_all=args.all)
        elif args.command == "stats":
            display.show_stats(follow=args.follow)
        elif args.command == "events":
            display.show_events(since=args.since)
        elif args.command == "logs":
            container_ops.show_logs(args.target, follow=args.follow)
        elif args.command == "exec":
            container_ops.exec_command(args.target, args.command)
        elif args.command == "volumes":
            display.show_volumes()
        elif args.command == "networks":
            display.show_networks()
        elif args.command == "build":
            container_ops.build(args.target, no_cache=args.no_cache)
        elif args.command == "prune":
            container_ops.prune()
        elif args.command == "system-df":
            display.show_system_df()
        elif args.command == "remove":
            container_ops.remove(args.target)
        elif args.command == "pull":
            container_ops.pull(args.target)
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
