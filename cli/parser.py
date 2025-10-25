#!/usr/bin/env python3
"""
Custom argument parser with enhanced error handling
"""

import argparse
import sys
from typing import NoReturn

from core.config import console


class CustomArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser with better error messages"""

    def _show_required_target_list(self, message: str) -> None:
        """Show hierarchical list of available targets based on command requirements"""
        # Try to determine the command from sys.argv
        command = None
        if len(sys.argv) > 1:
            # Find the command in argv (skip global options)
            for arg in sys.argv[1:]:
                if not arg.startswith("-"):
                    command = arg
                    break

        # Determine if this is a stack-only or service command
        stack_only_commands = ["down", "uninstall"]
        service_commands = [
            "logs",
            "exec",
            "diagnose",
            "reset-failed",
            "show-service-file",
            "build",
        ]

        console.print()

        if command in stack_only_commands:
            # Show only stacks for stack-only commands
            self._show_stack_list()
        elif command in service_commands:
            # Show full hierarchy but dim stacks for service-only commands
            self._show_service_hierarchy(dim_stacks=True)
        else:
            # Show full hierarchy for commands that accept both
            self._show_service_hierarchy(dim_stacks=False)

        console.print()

    def _show_stack_list(self) -> None:
        """Show list of available stacks only"""
        from rich.tree import Tree

        # Try to get stacks from both quadlet and compose managers
        stacks = set()

        # Try quadlet manager first
        try:
            from managers.quadlet_manager import QuadletManager

            quadlet_manager = QuadletManager()
            stacks.update(quadlet_manager.stack_services.keys())
        except Exception:
            pass

        # Compose manager removed - quadlet-only mode

        if stacks:
            tree = Tree("Stacks available:", style="cyan")
            for stack_name in sorted(stacks):
                tree.add(f"[green]{stack_name}[/green]")
            console.print(tree)
        else:
            console.print("[red]No stacks found[/red]")

    def _show_service_hierarchy(self, dim_stacks: bool = False) -> None:
        """Show full service hierarchy with status indicators, optionally dimming stacks"""
        # Try to get the full hierarchy from display managers with status
        try:
            # Try quadlet display first - use the enhanced show_status method
            from managers.quadlet_manager import QuadletManager
            from operations.quadlet_display import QuadletDisplayManager

            quadlet_manager = QuadletManager()
            display = QuadletDisplayManager(quadlet_manager)

            # Use the enhanced show_status method which includes running status
            display.show_status()
            return
        except Exception:
            pass

        # Compose display removed - quadlet-only mode

        # Final fallback
        console.print("[red]No services or stacks found[/red]")

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
        elif "the following arguments are required:" in message and "target" in message:
            # Determine what type of target is required based on the command
            self._show_required_target_list(message)
            sys.exit(1)
        else:
            console.print(f"[red]Error: {message}[/red]")
            console.print("[dim]Run 'pm --help' for help[/dim]")
            sys.exit(1)


def create_argument_parser():
    """Create and configure the main argument parser"""
    parser = CustomArgumentParser(
        description="Quadlet Manager with Rich UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )

    parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )
    parser.add_argument(
        "--ai-agent",
        "-ai",
        choices=["qwen25", "glm46", "claude", "gpt4"],
        default="qwen25",
        help="AI agent for analysis (default: qwen25)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status and info commands
    _add_status_commands(subparsers)

    # Service lifecycle commands
    _add_lifecycle_commands(subparsers)

    # Image and update commands
    _add_image_commands(subparsers)

    # Resource commands
    _add_resource_commands(subparsers)

    return parser


def _add_status_commands(subparsers):
    """Add status and information commands"""
    # List command
    list_parser = subparsers.add_parser(
        "list", help="List quadlet services with running status"
    )
    list_parser.add_argument(
        "target",
        nargs="?",
        help="Stack or service name (vllm-stack, vllm-qwen25, vllm-proxy, vllm-delegator)",
    )
    list_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # PS command
    ps_parser = subparsers.add_parser("ps", help="Show container status")
    ps_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Help commands
    help_parser = subparsers.add_parser("help", help="Show detailed help")
    help_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    help_podman_parser = subparsers.add_parser(
        "help-podman", help="Show podman --help documentation"
    )
    help_podman_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )
    help_podman_parser.add_argument(
        "-hpm",
        "--help-podman",
        action="store_true",
        help="Show podman --help documentation (alias)",
    )

    # Images command
    images_parser = subparsers.add_parser("images", help="Show container images")
    images_parser.add_argument(
        "-a", "--all", action="store_true", help="Show all images"
    )
    images_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show container resource usage")
    stats_parser.add_argument(
        "-f", "--follow", action="store_true", help="Follow stats output"
    )
    stats_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Targets command
    targets_parser = subparsers.add_parser(
        "targets", help="Show available quadlet targets"
    )
    targets_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # AI Agents command
    ai_agents_parser = subparsers.add_parser(
        "ai-agents", help="Show available AI agents for log analysis"
    )
    ai_agents_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Set Default AI Agent command
    set_default_ai_parser = subparsers.add_parser(
        "set-default-ai", help="Set the default AI agent for analysis"
    )
    set_default_ai_parser.add_argument(
        "agent_name",
        choices=[
            "qwen25",
            "glm46",
            "claude",
            "gpt4",
            "vllm-qwen25",
            "vllm-glm46",
            "claude-sonnet",
            "gpt-4",
        ],
        help="AI agent name to set as default",
    )
    set_default_ai_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )


def _add_lifecycle_commands(subparsers):
    """Add service lifecycle commands"""
    # Reinit command
    reinit_parser = subparsers.add_parser(
        "reinit", help="Stop, reload daemon, and restart stack or service"
    )
    reinit_parser.add_argument(
        "target",
        help="Stack or service name (vllm-stack, local-ai-packaged, vllm-qwen25, vllm-proxy, vllm-delegator)",
    )
    reinit_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )
    build_group = reinit_parser.add_mutually_exclusive_group()
    build_group.add_argument(
        "-b",
        "--build",
        action="store_true",
        help="Build images before restarting (with --no-cache) - legacy option",
    )
    build_group.add_argument(
        "-pb",
        "--podman-build",
        action="store_true",
        help="Use podman build (with --no-cache)",
    )
    build_group.add_argument(
        "-qb",
        "--quadlet-build",
        action="store_true",
        help="Use quadlet rebuild process",
    )

    # Build command
    build_parser = subparsers.add_parser(
        "build",
        help="Build container image and restart service with automatic AI analysis on failures",
    )
    build_parser.add_argument(
        "target",
        help="Service name (vllm-delegator, etc.)",
    )
    build_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Start command
    start_parser = subparsers.add_parser("start", help="Start stack or service")
    start_parser.add_argument(
        "target",
        help="Stack or service name (vllm-stack, local-ai-packaged, vllm-qwen25, vllm-proxy, vllm-delegator)",
    )
    start_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )
    start_parser.add_argument(
        "-b",
        "--build",
        action="store_true",
        help="Build images before starting (with --no-cache)",
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop stack or service")
    stop_parser.add_argument("target", help="Stack or service name")
    stop_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Down command
    down_parser = subparsers.add_parser("down", help="Stop all services in stack")
    down_parser.add_argument(
        "target", help="Stack name (e.g., vllm-stack, local-ai-packaged)"
    )
    down_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart stack or service")
    restart_parser.add_argument("target", help="Stack or service name")
    restart_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )
    restart_parser.add_argument(
        "-b",
        "--build",
        action="store_true",
        help="Build images before restarting (with --no-cache)",
    )

    # Enable command
    enable_parser = subparsers.add_parser(
        "enable", help="Enable stack or service at boot"
    )
    enable_parser.add_argument("target", help="Stack or service name")
    enable_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Disable command
    disable_parser = subparsers.add_parser(
        "disable", help="Disable stack or service at boot"
    )
    disable_parser.add_argument("target", help="Stack or service name")
    disable_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Reset-failed command
    reset_failed_parser = subparsers.add_parser(
        "reset-failed", help="Reset failed service state"
    )
    reset_failed_parser.add_argument("target", help="Service name")
    reset_failed_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Show-service-file command
    show_service_file_parser = subparsers.add_parser(
        "show-service-file", help="Show service file contents"
    )
    show_service_file_parser.add_argument("target", help="Service name")
    show_service_file_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )


def _add_image_commands(subparsers):
    """Add image and update commands"""
    # Install command
    install_parser = subparsers.add_parser(
        "install", help="Install/build quadlet stack using universal script"
    )
    install_parser.add_argument(
        "target",
        help="Stack or service name (e.g., vllm, local-ai, local-ai-neo4j, supabase)",
    )
    install_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Uninstall command
    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Uninstall quadlet stack or service from systemd directory"
    )
    uninstall_parser.add_argument(
        "target", help="Stack or service name (e.g., vllm, local-ai-neo4j, supabase)"
    )

    # Update command
    update_parser = subparsers.add_parser("update", help="Update images and restart")
    update_parser.add_argument("target", help="Stack or service name")
    update_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Auto-update command
    auto_update_parser = subparsers.add_parser(
        "auto-update", help="Check/enable auto-update timer"
    )
    auto_update_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Reload command
    reload_parser = subparsers.add_parser("reload", help="Reload systemd daemon")
    reload_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Prune command
    prune_parser = subparsers.add_parser(
        "prune", help="Remove unused images and containers"
    )
    prune_parser.add_argument(
        "--basic",
        action="store_true",
        help="Use basic prune (skip intelligent analysis)",
    )
    prune_parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick prune (dangling images and containers only)",
    )
    prune_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # System-df command
    system_df_parser = subparsers.add_parser("system-df", help="Show disk usage")
    system_df_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Hidden refresh command
    refresh_parser = subparsers.add_parser("refresh", help=argparse.SUPPRESS)
    refresh_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Fix Supabase environment variables
    fix_supabase_parser = subparsers.add_parser(
        "fix-supabase-env", help="Fix Supabase environment variable issues"
    )
    fix_supabase_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )


def _add_resource_commands(subparsers):
    """Add resource and log commands"""
    # Logs command
    logs_parser = subparsers.add_parser(
        "logs", help="Show service logs with automatic AI analysis on errors"
    )
    logs_parser.add_argument("target", help="Stack or service name")
    logs_parser.add_argument(
        "-f", "--follow", action="store_true", help="Follow log output"
    )
    logs_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution and comprehensive diagnostic data collection",
    )
    logs_parser.add_argument(
        "--ai-agent",
        "-ai",
        choices=["qwen25", "glm46", "claude", "gpt4"],
        default="qwen25",
        help="AI agent for analysis (default: qwen25)",
    )

    # Diagnose command
    diagnose_parser = subparsers.add_parser(
        "diagnose", help="Diagnose container startup failures"
    )
    diagnose_parser.add_argument("target", help="Service name to diagnose")
    diagnose_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Exec command
    exec_parser = subparsers.add_parser("exec", help="Execute command in container")
    exec_parser.add_argument("target", help="Service name")
    exec_parser.add_argument("cmd", nargs="+", help="Command to execute")
    exec_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Volumes command
    volumes_parser = subparsers.add_parser("volumes", help="List volumes")
    volumes_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Networks command
    networks_parser = subparsers.add_parser("networks", help="List networks")
    networks_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )
