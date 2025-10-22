#!/usr/bin/env python3
"""
Podman Container Management Script with Rich Console Output
Refactored modular version of the original podman-manager.py
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from config import console, set_verbose
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
        "  [cyan]pm[/cyan] [dim][OPTIONS][/dim] [green]COMMAND[/green] [dim][ARGS][/dim]                    [dim]# Short alias[/dim]"
    )
    console.print()
    console.print(
        "[bold yellow]Note:[/bold yellow] Manages both quadlet services and compose stacks"
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
    options_table.add_row(
        "-v, --verbose", "Show detailed command execution (exec lines)"
    )
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
                    "list <[cyan]stack|service[/cyan]>",
                    "List quadlet services and compose stacks with running status",
                    "pm list",
                ),
                (
                    "status [cyan]<stack|service>[/cyan]",
                    "Show service status tree with running status",
                    "pm status vllm-qwen25",
                ),
                ("ps", "Container status table", "pm ps"),
                ("targets", "Show available targets by type", "pm targets"),
                ("images [-a]", "Show container images", "pm images -a"),
                ("stats [-f]", "Show container resource usage", "pm stats -f"),
                ("events [--since TIME]", "Show container events", "pm events"),
            ],
        ),
        (
            "Service Lifecycle",
            [
                (
                    "reinit [cyan]<stack|service>[/cyan] [-v] [-b]",
                    "Stop, reload daemon, and restart stack or service (-v: verbose, -b: specialized rebuild for vllm-delegator/vllm-proxy)",
                    "pm reinit vllm-delegator -v -b",
                ),
                (
                    "build [cyan]<service>[/cyan]",
                    "Build container image and restart service",
                    "pm build vllm-delegator",
                ),
                (
                    "start [cyan]<stack|service>[/cyan] [-b]",
                    "Start stack or service",
                    "pm start vllm-stack -b",
                ),
                (
                    "stop [cyan]<stack|service>[/cyan]",
                    "Stop stack or service",
                    "pm stop vllm-qwen25",
                ),
                (
                    "down [cyan]<stack>[/cyan]",
                    "Stop all services in stack",
                    "pm down vllm-stack",
                ),
                (
                    "restart [cyan]<stack|service>[/cyan] [-b]",
                    "Restart stack or service",
                    "pm restart vllm-proxy -b",
                ),
                (
                    "enable [cyan]<stack|service>[/cyan]",
                    "Enable stack or service at boot",
                    "pm enable vllm-stack",
                ),
                (
                    "disable [cyan]<stack|service>[/cyan]",
                    "Disable stack or service at boot",
                    "pm disable vllm-delegator",
                ),
                (
                    "reset-failed [cyan]<service>[/cyan]",
                    "Reset failed service state",
                    "pm reset-failed vllm-qwen25",
                ),
                (
                    "show-service-file [cyan]<service>[/cyan]",
                    "Show service file contents",
                    "pm show-service-file vllm-qwen25",
                ),
            ],
        ),
        (
            "Images & Updates",
            [
                (
                    "install [cyan]<stack|service>[/cyan]",
                    "Install/build quadlet stack or individual service",
                    "pm install vllm",
                ),
                (
                    "uninstall [cyan]<stack|service>[/cyan]",
                    "Uninstall quadlet stack or service from systemd directory",
                    "pm uninstall local-ai-neo4j",
                ),
                (
                    "update [cyan]<stack|service>[/cyan]",
                    "Update images and restart",
                    "pm update vllm-qwen25",
                ),
                ("auto-update", "Check/enable auto-update timer", "pm auto-update"),
                ("reload", "Reload systemd daemon", "pm reload"),
                (
                    "prune [--basic] [--quick]",
                    "Intelligent cleanup of unused images and containers",
                    "pm prune",
                ),
                ("system-df", "Show disk usage", "pm system-df"),
            ],
        ),
        (
            "Resources & Logs",
            [
                ("volumes", "List volumes", "pm volumes"),
                ("networks", "List networks", "pm networks"),
                (
                    "logs [cyan]<stack|service>[/cyan] [-f] [-n N] [-ai]",
                    "Show service logs with optional AI analysis",
                    "pm logs vllm-qwen25 -f -n 50 -ai",
                ),
                (
                    "diagnose [cyan]<service>[/cyan]",
                    "Diagnose container startup failures",
                    "pm diagnose vllm-delegator",
                ),
                (
                    "exec [cyan]<service>[/cyan] COMMAND",
                    "Execute command in container",
                    "pm exec vllm-proxy bash",
                ),
                (
                    "help-podman [-hpm|--help-podman]",
                    "Show podman --help documentation",
                    "pm help-podman -hpm",
                ),
            ],
        ),
    ]

    for category, commands in categories:
        console.print(f"\n[bold cyan]{category}:[/bold cyan]")
        cmd_table = Table(show_header=False, box=None, padding=(0, 2))
        cmd_table.add_column("Command", style="green", width=40)
        cmd_table.add_column("Description", style="white", width=35)
        cmd_table.add_column("Example", style="dim", width=25)

        for cmd, desc, example in commands:
            cmd_table.add_row(cmd, desc, example)
        console.print(cmd_table)

    console.print()
    console.print("[bold]TIPS:[/bold]")
    console.print(
        "  • Use stacks (e.g., 'vllm-stack', 'local-ai-packaged') to manage all services together"
    )
    console.print("  • Services are managed via systemd user units")
    console.print("  • Use 'pm enable <service>' to start service at boot")
    console.print(
        "  • Use [cyan]-b[/cyan] to rebuild images with --no-cache before starting/restarting"
    )
    console.print("  • Press [cyan]Ctrl+C[/cyan] to interrupt long-running operations")
    console.print("  • Use 'pm list' or 'pm targets' to see available services")
    console.print("  • Use 'pm auto-update' to enable automatic image updates")
    console.print("  • Mode auto-detects target type (quadlet vs compose)")
    console.print("  • Use [cyan]--debug-detection[/cyan] to see detection logic")
    console.print("  • Use [cyan]--mode compose[/cyan] to force compose mode")
    console.print(
        "  • Use [cyan]--verbose[/cyan] or [cyan]-v[/cyan] before commands for detailed output"
    )


class CustomArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser with better error messages"""

    def _show_required_target_list(self, message: str) -> None:
        """Show hierarchical list of available targets based on command requirements"""
        import sys

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
            from quadlet_manager import QuadletManager

            quadlet_manager = QuadletManager()
            stacks.update(quadlet_manager.stack_services.keys())
        except Exception:
            pass

        # Try compose manager
        try:
            import os

            from manager import PodmanManager

            compose_dir = os.environ.get("PODMAN_COMPOSE_DIR")
            if compose_dir and Path(compose_dir).exists():
                compose_manager = PodmanManager(compose_dir)
                projects = compose_manager._parse_compose_files()
                stacks.update(projects.keys())
        except Exception:
            pass

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
            from quadlet_display import QuadletDisplayManager
            from quadlet_manager import QuadletManager

            quadlet_manager = QuadletManager()
            display = QuadletDisplayManager(quadlet_manager)

            # Use the enhanced show_status method which includes running status
            display.show_status()
            return
        except Exception:
            pass

        # Fallback to compose display
        try:
            import os

            from display import DisplayManager
            from manager import PodmanManager

            compose_dir = os.environ.get("PODMAN_COMPOSE_DIR")
            if compose_dir and Path(compose_dir).exists():
                compose_manager = PodmanManager(compose_dir)
                display = DisplayManager(compose_manager)
                display.show_status()
                return
        except Exception:
            pass

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


def fix_supabase_environment_variables():
    """Fix Supabase environment variable issues in container files"""

    # Common Supabase environment variable defaults
    SUPABASE_ENV_DEFAULTS = {
        "POSTGRES_PASSWORD": "your-super-secret-and-long-postgres-password",
        "POSTGRES_DB": "postgres",
        "POSTGRES_USER": "postgres",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "JWT_SECRET": "your-super-secret-jwt-token-with-at-least-32-characters-long",
        "ANON_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0",
        "SERVICE_ROLE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU",
        "DASHBOARD_USERNAME": "supabase",
        "DASHBOARD_PASSWORD": "this_password_is_insecure_and_should_be_updated",
        "SECRET_KEY_BASE": "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890",
        "SITE_URL": "http://localhost:3000",
        "API_EXTERNAL_URL": "http://localhost:8000",
        "SUPABASE_PUBLIC_URL": "http://localhost:8000",
        "SUPABASE_URL": "http://localhost:8000",
        "SUPABASE_ANON_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0",
        "IMGPROXY_ENABLE_WEBP_DETECTION": "true",
        "IMGPROXY_USE_ETAG": "true",
        "IMGPROXY_KEY": "your-imgproxy-key-here",
        "IMGPROXY_SALT": "your-imgproxy-salt-here",
        "GOTRUE_EXTERNAL_EMAIL_ENABLED": "true",
        "GOTRUE_MAILER_AUTOCONFIRM": "false",
        "GOTRUE_SMTP_ADMIN_EMAIL": "admin@example.com",
        "GOTRUE_SMTP_HOST": "localhost",
        "GOTRUE_SMTP_PORT": "587",
        "GOTRUE_SMTP_USER": "your-smtp-user",
        "GOTRUE_SMTP_PASS": "your-smtp-password",
        "GOTRUE_SMTP_SENDER_NAME": "Supabase",
        "STUDIO_DEFAULT_ORGANIZATION": "Default Organization",
        "STUDIO_DEFAULT_PROJECT": "Default Project",
        "SUPABASE_AUTH_ADMIN_EMAIL": "admin@example.com",
        "SUPABASE_AUTH_ADMIN_PASSWORD": "password",
        "FUNCTIONS_VERIFY_JWT": "false",
        "LOGFLARE_API_KEY": "your-logflare-api-key",
        "LOGFLARE_SOURCE_TOKEN": "your-logflare-source-token",
        "VECTOR_API_KEY": "your-vector-api-key",
    }

    console.print("[bold green]Supabase Environment Variable Fix[/bold green]")
    console.print("=" * 50)

    # Find Supabase container files
    systemd_dir = Path.home() / ".config/containers/systemd"

    if not systemd_dir.exists():
        console.print(f"[red]Systemd directory not found: {systemd_dir}[/red]")
        return False

    supabase_files = list(systemd_dir.glob("supabase*.container"))
    console.print(f"[cyan]Found {len(supabase_files)} Supabase container files[/cyan]")

    if not supabase_files:
        console.print("[red]No Supabase container files found to fix[/red]")
        return False

    # Fix each file
    fixed_count = 0

    for file_path in supabase_files:
        console.print(f"[cyan]Processing {file_path.name}...[/cyan]")

        # Create backup
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        if not backup_path.exists():
            backup_path.write_text(file_path.read_text())
            console.print(f"[dim]Created backup: {backup_path}[/dim]")

        # Read file content
        content = file_path.read_text()
        lines = content.split("\n")

        modified = False
        fixed_lines = []

        for line in lines:
            # Process Environment= lines
            if line.strip().startswith("Environment="):
                # Find unset variables (${VAR} without default)
                var_refs = re.findall(r"\$\{([^}:]+)\}", line)

                for var_name in var_refs:
                    if var_name in SUPABASE_ENV_DEFAULTS:
                        # Replace ${VAR} with ${VAR:-default}
                        old_pattern = f"${{{var_name}}}"
                        new_pattern = (
                            f"${{{var_name}:-{SUPABASE_ENV_DEFAULTS[var_name]}}}"
                        )
                        line = line.replace(old_pattern, new_pattern)
                        modified = True
                        console.print(
                            f"[green]  Fixed: {var_name} -> default value[/green]"
                        )
                    else:
                        console.print(
                            f"[yellow]  Warning: No default for {var_name}[/yellow]"
                        )

            fixed_lines.append(line)

        if modified:
            # Write the fixed content
            file_path.write_text("\n".join(fixed_lines))
            console.print(f"[green]✓ Fixed {file_path.name}[/green]")
            fixed_count += 1
        else:
            console.print(f"[dim]  No changes needed for {file_path.name}[/dim]")

    console.print(
        f"\n[cyan]Fixed {fixed_count} out of {len(supabase_files)} files[/cyan]"
    )

    if fixed_count > 0:
        # Reload systemd daemon
        console.print("[yellow]Reloading systemd daemon...[/yellow]")
        try:
            result = subprocess.run(
                ["systemctl", "--user", "daemon-reload"], capture_output=True, text=True
            )

            if result.returncode == 0:
                console.print("[green]✓ Systemd daemon reloaded[/green]")

                # Reset failed services
                console.print("[yellow]Resetting failed services...[/yellow]")
                subprocess.run(
                    ["systemctl", "--user", "reset-failed", "supabase*"],
                    capture_output=True,
                    text=True,
                )
                console.print("[green]✓ Failed services reset[/green]")

                console.print("\n[bold green]Fix completed successfully![/bold green]")
                console.print("[cyan]Next steps:[/cyan]")
                console.print("1. [white]Run: pm reinit supabase[/white]")
                console.print("2. [white]Check status: pm status supabase[/white]")
                console.print(
                    "3. [white]View logs if needed: pm logs supabase-imgproxy[/white]"
                )
                return True
            else:
                console.print(f"[red]Failed to reload daemon: {result.stderr}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]Error reloading daemon: {e}[/red]")
            return False
    else:
        console.print("[yellow]No files needed fixing[/yellow]")
        return True


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
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status and info commands
    list_parser = subparsers.add_parser(
        "list", help="List quadlet services and compose stacks with running status"
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

    # Keep 'status' as an alias for backward compatibility
    status_parser = subparsers.add_parser(
        "status", help="Show service status tree with running status"
    )
    status_parser.add_argument(
        "target",
        nargs="?",
        help="Stack or service name (optional - shows all if not specified)",
    )
    status_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )
    ps_parser = subparsers.add_parser("ps", help="Show container status")
    ps_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

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

    # Additional status commands
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

    events_parser = subparsers.add_parser("events", help="Show container events")
    events_parser.add_argument("--since", help="Show events since timestamp")
    events_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Resource commands
    logs_parser = subparsers.add_parser("logs", help="Show service logs")
    logs_parser.add_argument("target", help="Stack or service name")
    logs_parser.add_argument(
        "-f", "--follow", action="store_true", help="Follow log output"
    )
    logs_parser.add_argument(
        "-n",
        "--tail",
        type=int,
        default=100,
        help="Number of lines to show from end of logs (default: 100)",
    )
    logs_parser.add_argument(
        "-ai",
        "--ai-diagnose",
        action="store_true",
        help="AI-powered log analysis for root causes and solutions",
    )
    logs_parser.add_argument(
        "--vllm-url",
        default="http://localhost:8002",
        help="vLLM proxy URL for AI analysis (default: http://localhost:8002)",
    )
    logs_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

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

    exec_parser = subparsers.add_parser("exec", help="Execute command in container")
    exec_parser.add_argument("target", help="Service name")
    exec_parser.add_argument("cmd", nargs="+", help="Command to execute")
    exec_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    volumes_parser = subparsers.add_parser("volumes", help="List volumes")
    volumes_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    networks_parser = subparsers.add_parser("networks", help="List networks")
    networks_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Keep some original commands for container management
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

    system_df_parser = subparsers.add_parser("system-df", help="Show disk usage")
    system_df_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Service lifecycle commands
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

    build_parser = subparsers.add_parser(
        "build", help="Build container image and restart service"
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

    stop_parser = subparsers.add_parser("stop", help="Stop stack or service")
    stop_parser.add_argument("target", help="Stack or service name")
    stop_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

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

    # Image and update commands
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

    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Uninstall quadlet stack or service from systemd directory"
    )
    uninstall_parser.add_argument(
        "target", help="Stack or service name (e.g., vllm, local-ai-neo4j, supabase)"
    )

    update_parser = subparsers.add_parser("update", help="Update images and restart")
    update_parser.add_argument("target", help="Stack or service name")
    update_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    auto_update_parser = subparsers.add_parser(
        "auto-update", help="Check/enable auto-update timer"
    )
    auto_update_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    reload_parser = subparsers.add_parser("reload", help="Reload systemd daemon")
    reload_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    # Hidden refresh command (used internally by universal script)
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

    # Keep restart for compatibility
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

    # Add targets command to show available targets by type
    targets_parser = subparsers.add_parser(
        "targets", help="Show available targets by type (quadlet/compose)"
    )
    targets_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed command execution (exec lines)",
    )

    args = parser.parse_args()

    # Handle help with Rich formatting
    if args.help or (not args.command and len(sys.argv) == 1):
        show_rich_help()
        return

    try:
        # Set verbose mode from global flag
        set_verbose(args.verbose)

        # Helper function to handle command-specific verbose flags
        def handle_command_verbose(args):
            if hasattr(args, "verbose") and args.verbose:
                set_verbose(True)

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
            if args.target:
                if selected_mode == "quadlet":
                    container_ops.show_service_status(args.target)
                else:
                    display.show_status(args.target)
            else:
                # Show full status tree when no target specified
                display.show_status()
        elif args.command == "ps":
            # Run podman ps with specific format and display in borderless table
            try:
                result = subprocess.run(
                    [
                        "podman",
                        "ps",
                        "-a",
                        "--format",
                        "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    from rich.table import Table

                    # Create table without borders
                    table = Table(show_header=True, box=None, padding=(0, 1))
                    table.add_column("ID", style="cyan", no_wrap=True)
                    table.add_column("Names", style="green")
                    table.add_column("Status", style="yellow")
                    table.add_column("Ports", style="blue")

                    # Parse the output and add rows
                    lines = result.stdout.strip().split("\n")
                    for line in lines:
                        if line.strip():  # Skip empty lines
                            parts = line.split("\t")
                            if len(parts) >= 4:
                                table.add_row(parts[0], parts[1], parts[2], parts[3])
                            elif len(parts) == 3:
                                table.add_row(parts[0], parts[1], parts[2], "")
                            elif len(parts) == 2:
                                table.add_row(parts[0], parts[1], "", "")
                            elif len(parts) == 1:
                                table.add_row(parts[0], "", "", "")

                    console.print(table)
                else:
                    console.print(
                        f"[red]Error running podman ps: {result.stderr}[/red]"
                    )
                    sys.exit(1)
            except subprocess.TimeoutExpired:
                console.print("[red]Timeout running podman ps[/red]")
                sys.exit(1)
            except FileNotFoundError:
                console.print(
                    "[red]Podman command not found. Please install podman.[/red]"
                )
                sys.exit(1)
            except Exception as e:
                console.print(f"[red]Error running podman ps: {e}[/red]")
                sys.exit(1)
        elif args.command == "help":
            show_rich_help()
        elif args.command == "help-podman":
            # Show podman --help documentation
            try:
                result = subprocess.run(
                    ["podman", "--help"], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    console.print("[bold blue]Podman Help Documentation[/bold blue]")
                    console.print("=" * 50)
                    # Print without markup parsing to avoid Rich markup conflicts
                    console.print(result.stdout, markup=False)
                else:
                    console.print(
                        f"[red]Error running podman --help: {result.stderr}[/red]"
                    )
                    sys.exit(1)
            except subprocess.TimeoutExpired:
                console.print("[red]Timeout running podman --help[/red]")
                sys.exit(1)
            except FileNotFoundError:
                console.print(
                    "[red]Podman command not found. Please install podman.[/red]"
                )
                sys.exit(1)
            except Exception as e:
                console.print(f"[red]Error running podman --help: {e}[/red]")
                sys.exit(1)
        elif args.command == "images":
            display.show_images(show_all=args.all)
        elif args.command == "stats":
            display.show_stats(follow=args.follow)
        elif args.command == "events":
            display.show_events(since=args.since)
        elif args.command == "logs":
            if getattr(args, "ai_diagnose", False):
                container_ops.ai_analyze_logs(
                    args.target,
                    lines=args.tail,
                    vllm_url=args.vllm_url,
                    verbose=args.verbose,
                )
            else:
                container_ops.show_logs(args.target, follow=args.follow, tail=args.tail)
        elif args.command == "diagnose":
            if selected_mode == "quadlet":
                container_ops.diagnose_container_failure(args.target)
            else:
                console.print(
                    "[red]Diagnose command only available in quadlet mode[/red]"
                )
        elif args.command == "exec":
            container_ops.exec_command(args.target, args.cmd)
        elif args.command == "volumes":
            display.show_volumes()
        elif args.command == "networks":
            display.show_networks()
        elif args.command == "prune":
            enhanced = not getattr(args, "basic", False)
            quick = getattr(args, "quick", False)
            container_ops.prune(enhanced=enhanced, quick=quick)
        elif args.command == "system-df":
            if args.mode == "quadlet":
                container_ops.show_system_df()
            else:
                display.show_system_df()
        elif args.command == "reinit":
            # Handle command-specific verbose flag
            handle_command_verbose(args)

            # Determine build type
            build_type = None
            if getattr(args, "build", False):
                build_type = "legacy"  # -b flag (backward compatibility)
            elif getattr(args, "podman_build", False):
                build_type = "podman"
            elif getattr(args, "quadlet_build", False):
                build_type = "quadlet"

            success = try_with_fallback(
                container_ops.reinit, args.target, build_type=build_type
            )
            sys.exit(0 if success else 1)
        elif args.command == "build":
            handle_command_verbose(args)
            success = try_with_fallback(container_ops.rebuild, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "start":
            handle_command_verbose(args)
            success = try_with_fallback(
                container_ops.start, args.target, build=getattr(args, "build", False)
            )
            sys.exit(0 if success else 1)
        elif args.command == "stop":
            handle_command_verbose(args)
            success = try_with_fallback(container_ops.stop, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "down":
            handle_command_verbose(args)
            success = try_with_fallback(container_ops.down, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "restart":
            handle_command_verbose(args)
            success = try_with_fallback(
                container_ops.restart, args.target, build=getattr(args, "build", False)
            )
            sys.exit(0 if success else 1)
        elif args.command == "enable":
            handle_command_verbose(args)
            success = try_with_fallback(container_ops.enable, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "disable":
            handle_command_verbose(args)
            success = try_with_fallback(container_ops.disable, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "reset-failed":
            handle_command_verbose(args)
            if selected_mode == "quadlet":
                success = try_with_fallback(container_ops.reset_failed, args.target)
                sys.exit(0 if success else 1)
            else:
                console.print(
                    "[red]Reset-failed command only available in quadlet mode[/red]"
                )
                sys.exit(1)
        elif args.command == "show-service-file":
            handle_command_verbose(args)
            if selected_mode == "quadlet":
                success = try_with_fallback(
                    container_ops.show_service_file, args.target
                )
                sys.exit(0 if success else 1)
            else:
                console.print(
                    "[red]Show-service-file command only available in quadlet mode[/red]"
                )
                sys.exit(1)
        elif args.command == "install":
            handle_command_verbose(args)
            if selected_mode == "quadlet":
                success = try_with_fallback(container_ops.install_stack, args.target)
                sys.exit(0 if success else 1)
            else:
                console.print(
                    "[red]Install command only available in quadlet mode[/red]"
                )
                sys.exit(1)
        elif args.command == "uninstall":
            if selected_mode == "quadlet":
                success = try_with_fallback(container_ops.uninstall_stack, args.target)
                sys.exit(0 if success else 1)
            else:
                console.print(
                    "[red]Uninstall command only available in quadlet mode[/red]"
                )
                sys.exit(1)
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
        elif args.command == "refresh":
            # Hidden refresh command used internally by universal script
            if selected_mode == "quadlet":
                if hasattr(manager, "refresh_service_discovery"):
                    manager.refresh_service_discovery()
                # Also clear any display caches
                if hasattr(display, "clear_cache"):
                    display.clear_cache()
                console.print("[green]Service discovery refreshed[/green]")
                sys.exit(0)
            else:
                sys.exit(1)
        elif args.command == "fix-supabase-env":
            # Fix Supabase environment variable issues
            if selected_mode == "quadlet":
                success = fix_supabase_environment_variables()
                sys.exit(0 if success else 1)
            else:
                console.print(
                    "[red]Fix Supabase environment command only available in quadlet mode[/red]"
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
