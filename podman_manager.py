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
                    "list [[dim]<stack|service>[/dim]]",
                    "List quadlet services and compose stacks",
                    "pm list",
                ),
                (
                    "status [cyan]<stack|service>[/cyan]",
                    "Detailed service status",
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
                    "reinit [cyan]<stack|service>[/cyan] [-b]",
                    "Stop, reload daemon, and restart stack or service (-b: specialized rebuild for vllm-delegator/vllm-proxy)",
                    "pm reinit vllm-delegator -b",
                ),
                (
                    "rebuild [cyan]<service>[/cyan]",
                    "Rebuild container image and restart service",
                    "pm rebuild vllm-delegator",
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
            ],
        ),
        (
            "Images & Updates",
            [
                (
                    "install [cyan]<stack>[/cyan]",
                    "Install/build quadlet stack using universal script",
                    "pm install vllm",
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
                    "logs [cyan]<stack|service>[/cyan] [-f] [-n N]",
                    "Show service logs (default: 100 lines)",
                    "pm logs vllm-qwen25 -f -n 50",
                ),
                (
                    "log-check [cyan]<service>[/cyan] [-n N]",
                    "Analyze service logs for errors and warnings",
                    "pm log-check vllm-qwen25 -n 100",
                ),
                (
                    "log-ai [cyan]<service>[/cyan] [-n N]",
                    "AI-powered log analysis for root causes and solutions",
                    "pm log-ai vllm-qwen25 -n 100",
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
    examples_table.add_row("pm list", "Show all services and stack status")
    examples_table.add_row(
        "pm targets", "Show available targets by type (quadlet/compose)"
    )
    examples_table.add_row("pm list vllm-qwen25", "Show details for specific service")
    examples_table.add_row(
        "pm install vllm", "Install/build vLLM stack using quadlet script"
    )
    examples_table.add_row("pm install local-ai", "Install/build local-ai stack")
    examples_table.add_row("pm start vllm-stack", "Start all services in vLLM stack")
    examples_table.add_row(
        "pm start vllm-stack -b", "Build and start all services in vLLM stack"
    )
    examples_table.add_row("pm stop vllm-proxy", "Stop proxy service")
    examples_table.add_row("pm down vllm-stack", "Stop all services in vLLM stack")
    examples_table.add_row(
        "pm reinit vllm-delegator",
        "Reinitialize delegator service (stop, reload, start)",
    )
    examples_table.add_row(
        "pm reinit vllm-delegator -b",
        "Specialized rebuild: stop quadlet, rebuild MCP container, reload, start",
    )
    examples_table.add_row(
        "pm reinit vllm-proxy -b",
        "Specialized rebuild: stop quadlet, rebuild proxy container, reload, start",
    )
    examples_table.add_row(
        "pm reinit local-ai-packaged", "Reinitialize entire stack (all services)"
    )
    examples_table.add_row(
        "pm rebuild vllm-delegator", "Rebuild delegator container and restart service"
    )
    examples_table.add_row("pm restart vllm-delegator", "Restart delegator service")
    examples_table.add_row(
        "pm restart vllm-delegator -b", "Build and restart delegator service"
    )
    examples_table.add_row("pm logs vllm-qwen25 -f", "Follow logs for Qwen2.5 Coder")
    examples_table.add_row(
        "pm logs vllm-proxy -n 50", "Show last 50 lines of proxy logs"
    )
    examples_table.add_row(
        "pm log-check vllm-qwen25", "Check Qwen2.5 Coder logs for issues (50 lines)"
    )
    examples_table.add_row(
        "pm log-check vllm-qwen25 -n 200", "Check n lines of logs for issues"
    )
    examples_table.add_row(
        "pm log-ai vllm-qwen25", "AI-powered analysis of Qwen2.5 Coder logs (50 lines)"
    )
    examples_table.add_row(
        "pm log-ai vllm-qwen25 -n 100", "AI analysis of n lines of logs"
    )
    examples_table.add_row("pm status vllm-stack", "Detailed status of stack")
    examples_table.add_row("pm enable vllm-stack", "Enable stack to start at boot")
    examples_table.add_row("pm update vllm-qwen25", "Update images and restart service")
    examples_table.add_row("pm auto-update", "Check auto-update timer status")
    examples_table.add_row("pm reload", "Reload systemd daemon")
    examples_table.add_row("pm ps", "Show running containers status")
    examples_table.add_row("pm stats -f", "Monitor resource usage in real-time")
    examples_table.add_row("pm images -a", "Show all images including intermediates")
    examples_table.add_row("pm system-df", "Show disk usage by containers/images")
    examples_table.add_row(
        "pm prune", "Intelligent cleanup with analysis and confirmation"
    )
    examples_table.add_row("pm prune --quick", "Quick cleanup of dangling images only")
    examples_table.add_row("pm prune --basic", "Basic cleanup without analysis")
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

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status and info commands
    list_parser = subparsers.add_parser(
        "list", help="List quadlet services and compose stacks"
    )
    list_parser.add_argument(
        "target",
        nargs="?",
        help="Stack or service name (vllm-stack, vllm-qwen25, vllm-proxy, vllm-delegator)",
    )

    # Keep 'status' as an alias for backward compatibility
    status_parser = subparsers.add_parser(
        "status", help="Show service status (detailed)"
    )
    status_parser.add_argument("target", help="Stack or service name")
    subparsers.add_parser("ps", help="Show container status")
    subparsers.add_parser("help", help="Show detailed help")

    # Additional status commands
    images_parser = subparsers.add_parser("images", help="Show container images")
    images_parser.add_argument(
        "-a", "--all", action="store_true", help="Show all images"
    )

    stats_parser = subparsers.add_parser("stats", help="Show container resource usage")
    stats_parser.add_argument(
        "-f", "--follow", action="store_true", help="Follow stats output"
    )

    events_parser = subparsers.add_parser("events", help="Show container events")
    events_parser.add_argument("--since", help="Show events since timestamp")

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

    log_check_parser = subparsers.add_parser(
        "log-check", help="Analyze service logs for errors and warnings"
    )
    log_check_parser.add_argument("target", help="Service name")
    log_check_parser.add_argument(
        "-n",
        "--lines",
        type=int,
        default=50,
        help="Number of lines to analyze from end of logs (default: 50)",
    )

    log_ai_parser = subparsers.add_parser(
        "log-ai",
        help="AI-powered analysis of service logs for root causes and solutions",
    )
    log_ai_parser.add_argument("target", help="Service name")
    log_ai_parser.add_argument(
        "-n",
        "--lines",
        type=int,
        default=50,
        help="Number of lines to analyze from end of logs (default: 50)",
    )
    log_ai_parser.add_argument(
        "--vllm-url",
        default="http://localhost:8002",
        help="vLLM proxy URL (default: http://localhost:8002)",
    )

    diagnose_parser = subparsers.add_parser(
        "diagnose", help="Diagnose container startup failures"
    )
    diagnose_parser.add_argument("target", help="Service name to diagnose")

    exec_parser = subparsers.add_parser("exec", help="Execute command in container")
    exec_parser.add_argument("target", help="Service name")
    exec_parser.add_argument("cmd", nargs="+", help="Command to execute")

    subparsers.add_parser("volumes", help="List volumes")
    subparsers.add_parser("networks", help="List networks")

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
    subparsers.add_parser("system-df", help="Show disk usage")

    # Service lifecycle commands
    reinit_parser = subparsers.add_parser(
        "reinit", help="Stop, reload daemon, and restart stack or service"
    )
    reinit_parser.add_argument(
        "target",
        help="Stack or service name (vllm-stack, local-ai-packaged, vllm-qwen25, vllm-proxy, vllm-delegator)",
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

    rebuild_parser = subparsers.add_parser(
        "rebuild", help="Rebuild container image and restart service"
    )
    rebuild_parser.add_argument(
        "target",
        help="Service name (vllm-delegator, etc.)",
    )

    start_parser = subparsers.add_parser("start", help="Start stack or service")
    start_parser.add_argument(
        "target",
        help="Stack or service name (vllm-stack, local-ai-packaged, vllm-qwen25, vllm-proxy, vllm-delegator)",
    )
    start_parser.add_argument(
        "-b",
        "--build",
        action="store_true",
        help="Build images before starting (with --no-cache)",
    )

    stop_parser = subparsers.add_parser("stop", help="Stop stack or service")
    stop_parser.add_argument("target", help="Stack or service name")

    down_parser = subparsers.add_parser("down", help="Stop all services in stack")
    down_parser.add_argument(
        "target", help="Stack name (e.g., vllm-stack, local-ai-packaged)"
    )

    enable_parser = subparsers.add_parser(
        "enable", help="Enable stack or service at boot"
    )
    enable_parser.add_argument("target", help="Stack or service name")

    disable_parser = subparsers.add_parser(
        "disable", help="Disable stack or service at boot"
    )
    disable_parser.add_argument("target", help="Stack or service name")

    # Image and update commands
    install_parser = subparsers.add_parser(
        "install", help="Install/build quadlet stack using universal script"
    )
    install_parser.add_argument(
        "stack", help="Stack name (e.g., vllm, local-ai, supabase)"
    )

    update_parser = subparsers.add_parser("update", help="Update images and restart")
    update_parser.add_argument("target", help="Stack or service name")

    subparsers.add_parser("auto-update", help="Check/enable auto-update timer")
    subparsers.add_parser("reload", help="Reload systemd daemon")

    # Hidden refresh command (used internally by universal script)
    subparsers.add_parser("refresh", help=argparse.SUPPRESS)

    # Fix Supabase environment variables
    subparsers.add_parser(
        "fix-supabase-env", help="Fix Supabase environment variable issues"
    )

    # Keep restart for compatibility
    restart_parser = subparsers.add_parser("restart", help="Restart stack or service")
    restart_parser.add_argument("target", help="Stack or service name")
    restart_parser.add_argument(
        "-b",
        "--build",
        action="store_true",
        help="Build images before restarting (with --no-cache)",
    )

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
        elif args.command == "log-check":
            container_ops.analyze_logs(args.target, lines=args.lines)
        elif args.command == "log-ai":
            container_ops.ai_analyze_logs(
                args.target, lines=args.lines, vllm_url=args.vllm_url
            )
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
            if selected_mode == "quadlet":
                container_ops.prune_containers(enhanced=enhanced, quick=quick)
            else:
                container_ops.prune(enhanced=enhanced, quick=quick)
        elif args.command == "system-df":
            if args.mode == "quadlet":
                container_ops.show_system_df()
            else:
                display.show_system_df()
        elif args.command == "reinit":
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
        elif args.command == "rebuild":
            success = try_with_fallback(container_ops.rebuild, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "start":
            success = try_with_fallback(
                container_ops.start, args.target, build=getattr(args, "build", False)
            )
            sys.exit(0 if success else 1)
        elif args.command == "stop":
            success = try_with_fallback(container_ops.stop, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "down":
            success = try_with_fallback(container_ops.down, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "restart":
            success = try_with_fallback(
                container_ops.restart, args.target, build=getattr(args, "build", False)
            )
            sys.exit(0 if success else 1)
        elif args.command == "enable":
            success = try_with_fallback(container_ops.enable, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "disable":
            success = try_with_fallback(container_ops.disable, args.target)
            sys.exit(0 if success else 1)
        elif args.command == "install":
            if selected_mode == "quadlet":
                success = try_with_fallback(container_ops.install_stack, args.stack)
                sys.exit(0 if success else 1)
            else:
                console.print(
                    "[red]Install command only available in quadlet mode[/red]"
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
