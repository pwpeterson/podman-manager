#!/usr/bin/env python3
"""
Podman Container Management Script with Rich Console Output
Refactored modular version of the original podman-manager.py
"""

import argparse
import os
import sys
from pathlib import Path
from typing import NoReturn

from config import console
from container_ops import ContainerOperations
from display import DisplayManager
from manager import PodmanManager
from project_detector import ProjectTypeDetector
from quadlet_display import QuadletDisplayManager
from quadlet_manager import QuadletManager
from quadlet_ops import QuadletOperations


def show_rich_help():
    """Show beautiful Rich-formatted help for vLLM Quadlet Manager"""
    from rich.table import Table

    from config import console

    console.print("[bold blue]Podman Manager[/bold blue]")

    console.print()
    console.print("[bold]USAGE:[/bold]")
    console.print(
        "  [cyan]python podman_manager.py[/cyan] [dim][OPTIONS][/dim] [green]COMMAND[/green] [dim][ARGS][/dim]"
    )
    console.print(
        "  [cyan]pm[/cyan] [green]COMMAND[/green] [dim][ARGS][/dim]                    [dim]# Short alias[/dim]"
    )
    console.print()
    console.print(
        "[bold yellow]Note:[/bold yellow] Manages both quadlet services and compose projects"
    )

    console.print()
    console.print("[bold]GLOBAL OPTIONS:[/bold]")
    options_table = Table(show_header=False, box=None, padding=(0, 2))
    options_table.add_column("Option", style="yellow", width=30)
    options_table.add_column("Description", style="white")
    options_table.add_row(
        "--mode [auto|quadlet|compose]", "Manager mode (default: auto-detect)"
    )
    options_table.add_row("--debug-detection", "Show project type detection details")
    options_table.add_row("-h, --help", "Show this help message")
    console.print(options_table)

    console.print()
    console.print("[bold]COMMANDS:[/bold]")

    # Create command categories
    categories = [
        (
            "Status & Information",
            [
                (
                    "list [[dim]<project|service>[/dim]]",
                    "List quadlet services and compose projects",
                    "pm list",
                ),
                (
                    "status [cyan]<project|service>[/cyan]",
                    "Detailed service status",
                    "pm status vllm-qwen25",
                ),
                ("ps", "Container status table", "pm ps"),
                ("targets", "Show available targets by type", "pm targets"),
                ("images [--all]", "Show container images", "pm images"),
                ("stats [--follow]", "Show container resource usage", "pm stats"),
                ("events [--since TIME]", "Show container events", "pm events"),
            ],
        ),
        (
            "Service Lifecycle",
            [
                (
                    "reinit [cyan]<project|service>[/cyan]",
                    "Stop, reload daemon, and restart service",
                    "pm reinit vllm-delegator",
                ),
                (
                    "start [cyan]<project|service>[/cyan]",
                    "Start service or stack",
                    "pm start vllm-stack",
                ),
                (
                    "stop [cyan]<project|service>[/cyan]",
                    "Stop service or stack",
                    "pm stop vllm-qwen25",
                ),
                (
                    "down [cyan]<project|stack>[/cyan]",
                    "Stop all services in project or stack",
                    "pm down vllm-stack",
                ),
                (
                    "restart [cyan]<project|service>[/cyan]",
                    "Restart service or stack",
                    "pm restart vllm-proxy",
                ),
                (
                    "enable [cyan]<project|service>[/cyan]",
                    "Enable service at boot",
                    "pm enable vllm-stack",
                ),
                (
                    "disable [cyan]<project|service>[/cyan]",
                    "Disable service at boot",
                    "pm disable vllm-delegator",
                ),
            ],
        ),
        (
            "Images & Updates",
            [
                (
                    "update [cyan]<project|service>[/cyan]",
                    "Update images and restart",
                    "pm update vllm-qwen25",
                ),
                ("auto-update", "Check/enable auto-update timer", "pm auto-update"),
                ("reload", "Reload systemd daemon", "pm reload"),
                ("prune", "Remove unused images and containers", "pm prune"),
                ("system-df", "Show disk usage", "pm system-df"),
            ],
        ),
        (
            "Resources & Logs",
            [
                ("volumes", "List volumes", "pm volumes"),
                ("networks", "List networks", "pm networks"),
                (
                    "logs [cyan]<project|service>[/cyan] [--follow] [--tail N]",
                    "Show service logs (default: 100 lines)",
                    "pm logs vllm-qwen25 --follow --tail 50",
                ),
                (
                    "log-anal [cyan]<service>[/cyan]",
                    "Analyze service logs for errors and warnings",
                    "pm log-anal vllm-qwen25",
                ),
                (
                    "exec [cyan]<service>[/cyan] COMMAND",
                    "Execute command in container",
                    "pm exec vllm-proxy bash",
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
    console.print("[bold]EXAMPLES:[/bold]")
    examples_table = Table(show_header=False, box=None, padding=(0, 2))
    examples_table.add_column("Command", style="cyan", width=35)
    examples_table.add_column("Description", style="white")
    examples_table.add_row("pm list", "Show all vLLM services and stack status")
    examples_table.add_row(
        "pm targets", "Show available targets by type (quadlet/compose)"
    )
    examples_table.add_row("pm list vllm-qwen25", "Show details for specific service")
    examples_table.add_row("pm start vllm-stack", "Start all vLLM services")
    examples_table.add_row("pm stop vllm-proxy", "Stop proxy service")
    examples_table.add_row("pm down vllm-stack", "Stop all services in vLLM stack")
    examples_table.add_row(
        "pm reinit vllm-delegator", "Reinitialize delegator (stop, reload, start)"
    )
    examples_table.add_row("pm restart vllm-delegator", "Restart delegator service")
    examples_table.add_row(
        "pm logs vllm-qwen25 --follow", "Follow logs for Qwen2.5 Coder"
    )
    examples_table.add_row(
        "pm logs vllm-proxy --tail 50", "Show last 50 lines of proxy logs"
    )
    examples_table.add_row(
        "pm log-anal vllm-qwen25", "Analyze Qwen2.5 Coder logs for issues"
    )
    examples_table.add_row("pm status vllm-stack", "Detailed status of stack target")
    examples_table.add_row("pm enable vllm-stack", "Enable stack to start at boot")
    examples_table.add_row("pm update vllm-qwen25", "Update images and restart service")
    examples_table.add_row("pm auto-update", "Check auto-update timer status")
    examples_table.add_row("pm reload", "Reload systemd daemon")
    examples_table.add_row("pm ps", "Show running containers status")
    examples_table.add_row("pm stats --follow", "Monitor resource usage in real-time")
    examples_table.add_row("pm images --all", "Show all images including intermediates")
    examples_table.add_row("pm system-df", "Show disk usage by containers/images")
    examples_table.add_row("pm prune", "Clean up unused containers and images")
    examples_table.add_row("pm volumes", "List all volumes")
    examples_table.add_row("pm networks", "List all networks")
    examples_table.add_row("pm events --since 1h", "Show events from last hour")
    examples_table.add_row("pm --debug-detection list", "Show mode detection details")
    examples_table.add_row(
        "pm --mode compose restart myservice", "Force compose mode for command"
    )
    console.print(examples_table)

    console.print()
    console.print("[bold]TIPS:[/bold]")
    console.print(
        "  • Use [cyan]vllm-stack[/cyan] to manage all vLLM services together"
    )
    console.print("  • Services are managed via systemd user units")
    console.print("  • Use [cyan]pm enable vllm-stack[/cyan] to start services at boot")
    console.print("  • Press [cyan]Ctrl+C[/cyan] to interrupt long-running operations")
    console.print(
        "  • Check [cyan]pm list[/cyan] or [cyan]pm targets[/cyan] to see available services"
    )
    console.print(
        "  • Use [cyan]pm auto-update[/cyan] to enable automatic image updates"
    )
    console.print("  • Mode auto-detects project type (quadlet vs compose)")
    console.print("  • Use [cyan]--debug-detection[/cyan] to see detection logic")
    console.print("  • Use [cyan]--mode compose[/cyan] to force compose mode")


class CustomArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser with better error messages"""

    def error(self, message) -> NoReturn:
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
            else:
                console.print(f"[red]Error: {message}[/red]")
                console.print(
                    "[dim]Run 'pm --help' to see all available commands[/dim]"
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
    """Main entry point for vLLM quadlet manager"""
    parser = CustomArgumentParser(
        description="vLLM Quadlet Manager with Rich UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )

    parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    parser.add_argument(
        "--mode",
        choices=["compose", "quadlet", "auto"],
        default="auto",
        help="Manager mode (default: auto-detect)",
    )
    parser.add_argument(
        "--debug-detection",
        action="store_true",
        help="Show project type detection details",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status and info commands
    list_parser = subparsers.add_parser(
        "list", help="List quadlet services and compose projects"
    )
    list_parser.add_argument(
        "target",
        nargs="?",
        help="Project or service name (vllm-stack, vllm-qwen25, vllm-proxy, vllm-delegator)",
    )

    # Keep 'status' as an alias for backward compatibility
    status_parser = subparsers.add_parser(
        "status", help="Show service status (detailed)"
    )
    status_parser.add_argument("target", help="Project or service name")
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
    logs_parser = subparsers.add_parser("logs", help="Show service logs")
    logs_parser.add_argument("target", help="Project or service name")
    logs_parser.add_argument("--follow", action="store_true", help="Follow log output")
    logs_parser.add_argument(
        "--tail",
        type=int,
        default=100,
        help="Number of lines to show from end of logs (default: 100)",
    )

    log_anal_parser = subparsers.add_parser(
        "log-anal", help="Analyze service logs for errors and warnings"
    )
    log_anal_parser.add_argument("target", help="Service name")
    log_anal_parser.add_argument(
        "--lines",
        type=int,
        default=1000,
        help="Number of lines to analyze from end of logs (default: 1000)",
    )

    exec_parser = subparsers.add_parser("exec", help="Execute command in container")
    exec_parser.add_argument("target", help="Service name")
    exec_parser.add_argument("cmd", nargs="+", help="Command to execute")

    subparsers.add_parser("volumes", help="List volumes")
    subparsers.add_parser("networks", help="List networks")

    # Keep some original commands for container management
    subparsers.add_parser("prune", help="Remove unused images and containers")
    subparsers.add_parser("system-df", help="Show disk usage")

    # Service lifecycle commands
    reinit_parser = subparsers.add_parser(
        "reinit", help="Stop, reload daemon, and restart service"
    )
    reinit_parser.add_argument(
        "target",
        help="Project or service name (vllm-stack, vllm-qwen25, vllm-proxy, vllm-delegator)",
    )

    start_parser = subparsers.add_parser("start", help="Start service or stack")
    start_parser.add_argument(
        "target",
        help="Project or service name (vllm-stack, vllm-qwen25, vllm-proxy, vllm-delegator)",
    )

    stop_parser = subparsers.add_parser("stop", help="Stop service or stack")
    stop_parser.add_argument("target", help="Project or service name")

    down_parser = subparsers.add_parser(
        "down", help="Stop all services in project or stack"
    )
    down_parser.add_argument(
        "target", help="Project or stack name (e.g., vllm-stack, local-ai-packaged)"
    )

    enable_parser = subparsers.add_parser("enable", help="Enable service at boot")
    enable_parser.add_argument("target", help="Project or service name")

    disable_parser = subparsers.add_parser("disable", help="Disable service at boot")
    disable_parser.add_argument("target", help="Project or service name")

    # Image and update commands
    update_parser = subparsers.add_parser("update", help="Update images and restart")
    update_parser.add_argument("target", help="Project or service name")

    subparsers.add_parser("auto-update", help="Check/enable auto-update timer")
    subparsers.add_parser("reload", help="Reload systemd daemon")

    # Keep restart for compatibility
    restart_parser = subparsers.add_parser("restart", help="Restart service or stack")
    restart_parser.add_argument("target", help="Project or service name")

    # Add targets command to show available targets by type
    subparsers.add_parser(
        "targets", help="Show available targets by type (quadlet/compose)"
    )

    args = parser.parse_args()

    # Handle help with Rich formatting
    if args.help or (not args.command and len(sys.argv) == 1):
        show_rich_help()
        return

    try:
        # Initialize project type detector
        compose_dir = os.environ.get("PODMAN_COMPOSE_DIR")
        detector = ProjectTypeDetector(Path(compose_dir) if compose_dir else None)

        # Determine the target for mode detection
        target = getattr(args, "target", None)

        # Get intelligent mode selection
        if args.mode == "auto":
            selected_mode, detection_reason = detector.get_intelligent_mode(target)
        else:
            selected_mode, detection_reason = detector.get_intelligent_mode(
                target, args.mode
            )

        # Show detection details if requested
        if args.debug_detection:
            console.print(
                f"[dim]Mode selection: {selected_mode} ({detection_reason})[/dim]"
            )

        # Initialize the appropriate manager based on detected/selected mode
        if selected_mode == "quadlet":
            # Use quadlet manager for vLLM services
            manager = QuadletManager()
            container_ops = QuadletOperations(manager)
            display = QuadletDisplayManager(manager)
        else:
            # Use compose manager
            manager = PodmanManager(compose_dir)
            container_ops = ContainerOperations(manager)
            display = DisplayManager(manager)

        # Helper function for intelligent fallback
        def try_with_fallback(operation_func, *operation_args, **operation_kwargs):
            """Try operation with current mode, fallback to alternative if it fails"""
            try:
                result = operation_func(*operation_args, **operation_kwargs)
                # If operation returns False (failure), try fallback
                if result is False:
                    alternative_mode = detector.suggest_alternative_mode(
                        target or "", selected_mode
                    )
                    if alternative_mode and not args.debug_detection:
                        console.print(
                            f"[yellow]Trying alternative mode: {alternative_mode}[/yellow]"
                        )
                        # This would require reinitializing managers - for now just show suggestion
                        console.print(
                            f"[dim]Try: pm --mode {alternative_mode} {args.command} {' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''}[/dim]"
                        )
                return result
            except Exception as e:
                console.print(f"[red]Operation failed: {e}[/red]")
                alternative_mode = detector.suggest_alternative_mode(
                    target or "", selected_mode
                )
                if alternative_mode:
                    console.print(
                        f"[dim]Try: pm --mode {alternative_mode} {args.command} {' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''}[/dim]"
                    )
                return False

        # Route commands to appropriate modules
        if args.command == "list":
            if args.target:
                display.show_status(args.target)
            else:
                display.show_status()
        elif args.command == "status":
            if selected_mode == "quadlet":
                container_ops.show_service_status(args.target)
            else:
                display.show_status(args.target)
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
            container_ops.show_logs(args.target, follow=args.follow, tail=args.tail)
        elif args.command == "log-anal":
            container_ops.analyze_logs(args.target, lines=args.lines)
        elif args.command == "exec":
            container_ops.exec_command(args.target, args.cmd)
        elif args.command == "volumes":
            display.show_volumes()
        elif args.command == "networks":
            display.show_networks()
        elif args.command == "prune":
            if args.mode == "quadlet":
                container_ops.prune_containers()
            else:
                container_ops.prune()
        elif args.command == "system-df":
            if args.mode == "quadlet":
                container_ops.show_system_df()
            else:
                display.show_system_df()
        elif args.command == "reinit":
            success = try_with_fallback(container_ops.reinit, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "start":
            success = try_with_fallback(container_ops.start, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "stop":
            success = try_with_fallback(container_ops.stop, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "down":
            success = try_with_fallback(container_ops.down, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "restart":
            success = try_with_fallback(container_ops.restart, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "enable":
            success = try_with_fallback(container_ops.enable, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "disable":
            success = try_with_fallback(container_ops.disable, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "update":
            if selected_mode == "quadlet":
                success = try_with_fallback(
                    container_ops.update_images_and_restart, args.target
                )
                sys.exit(0 if success else 1)
            else:
                console.print(
                    "[red]Update command only available in quadlet mode[/red]"
                )
                sys.exit(1)
        elif args.command == "auto-update":
            if selected_mode == "quadlet":
                container_ops.check_auto_update_status()
            else:
                console.print(
                    "[red]Auto-update command only available in quadlet mode[/red]"
                )
                sys.exit(1)
        elif args.command == "reload":
            if selected_mode == "quadlet":
                success = container_ops.reload_daemon()
                sys.exit(0 if success else 1)
            else:
                console.print(
                    "[red]Reload command only available in quadlet mode[/red]"
                )
                sys.exit(1)
        elif args.command == "targets":
            # Show available targets by type
            available_targets = detector.list_available_targets()

            from rich.table import Table

            table = Table(
                show_header=True, header_style="bold magenta", title="Available Targets"
            )
            table.add_column("Type", style="cyan", no_wrap=True)
            table.add_column("Targets", style="white")

            if available_targets["quadlet"]:
                table.add_row(
                    "Quadlet Services", ", ".join(available_targets["quadlet"])
                )

            if available_targets["compose"]:
                table.add_row(
                    "Compose Services", ", ".join(available_targets["compose"])
                )

            if not available_targets["quadlet"] and not available_targets["compose"]:
                table.add_row("None", "No targets found")

            console.print(table)

            # Show current mode
            console.print(
                f"\n[dim]Current mode: {selected_mode} ({detection_reason})[/dim]"
            )
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
