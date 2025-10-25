#!/usr/bin/env python3
"""
Rich-formatted help display for podman manager
"""

from rich.table import Table

from core.config import console


def show_rich_help():
    """Show beautiful Rich-formatted help for Quadlet Manager"""
    console.print("[bold blue]Quadlet Manager[/bold blue]")

    console.print()
    console.print("[bold]USAGE:[/bold]")
    console.print(
        "  [cyan]python podman_manager.py[/cyan] [green]COMMAND[/green] [dim][<stack|service>][/dim] [dim][OPTIONS][/dim]"
    )
    console.print(
        "  [cyan]pm[/cyan] [green]COMMAND[/green] [dim][<stack|service>][/dim] [dim][OPTIONS][/dim]                    [dim]# Short alias[/dim]"
    )
    console.print()
    console.print("[bold]GLOBAL OPTIONS:[/bold]")
    options_table = Table(show_header=False, box=None, padding=(0, 2))
    options_table.add_column("Option", style="yellow", width=30)
    options_table.add_column("Description", style="white")
    options_table.add_row(
        "-v, --verbose", "Show detailed command execution (exec lines)"
    )
    options_table.add_row(
        "-ai, --ai-agent [qwen25|glm46|claude|gpt4]",
        "AI agent for analysis (default: qwen25)",
    )
    options_table.add_row("-b, --build", "Build images before starting/restarting")
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
                    "List quadlet services with running status",
                    "pm list",
                ),
                (
                    "status [cyan]<stack|service>[/cyan]",
                    "Show service status tree with running status",
                    "pm status vllm-qwen25",
                ),
                ("ps", "Container status table", "pm ps"),
                ("targets", "Show available quadlet targets", "pm targets"),
                ("images", "Show container images", "pm images"),
                ("stats", "Show container resource usage", "pm stats"),
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
                    "logs [cyan]<stack|service>[/cyan]",
                    "Show service logs with automatic AI analysis on errors",
                    "pm logs vllm-qwen25",
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
    console.print("[bold]AUTOMATIC AI ANALYSIS:[/bold]")
    console.print(
        "  🤖 [green]AI analysis runs automatically when Podman errors are detected[/green]"
    )
    console.print(
        "  📊 [cyan]Comprehensive diagnostics collected for all failures[/cyan]"
    )
    console.print(
        "  🔍 [yellow]Analyzes logs, systemd status, container state, and system resources[/yellow]"
    )
    console.print(
        "  💡 [light_blue]Provides root cause analysis and step-by-step solutions[/light_blue]"
    )
    console.print()
    console.print("[bold]Available AI Agents:[/bold]")
    ai_table = Table(show_header=False, box=None, padding=(0, 2))
    ai_table.add_column("Agent", style="green", width=15)
    ai_table.add_column("Description", style="white", width=35)
    ai_table.add_column("Trigger", style="dim", width=30)
    ai_table.add_row(
        "qwen25", "Local Qwen2.5-Coder-32B (default)", "Automatic on errors"
    )
    ai_table.add_row("glm46", "Local GLM-4-6B-Chat", "Automatic on errors")
    ai_table.add_row("claude", "Claude 3.5 Sonnet", "Automatic on errors")
    ai_table.add_row("gpt4", "GPT-4", "Automatic on errors")
    console.print(ai_table)

    console.print()
    console.print("[bold]AI AGENT SELECTION:[/bold]")
    console.print(
        "  Use [cyan]-ai[/cyan] or [cyan]--ai-agent[/cyan] to select AI agent:"
    )
    console.print("  [dim]pm reinit supabase-analytics -ai claude[/dim]")
    console.print("  [dim]pm logs vllm-qwen25 -ai glm46[/dim]")
    console.print("  [dim]pm build vllm-delegator -ai qwen25[/dim]")

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
    console.print("  • Uses quadlet mode for systemd-based container management")
    console.print(
        "  • Use [cyan]--verbose[/cyan] or [cyan]-v[/cyan] before commands for detailed output"
    )
    console.print(
        "  • 🤖 AI analysis runs automatically when errors occur - no flags needed!"
    )
    console.print(
        "  • Verbose mode shows all diagnostic commands executed during AI analysis"
    )
    console.print(
        "  • AI analysis covers logs, systemd status, container state, and system resources"
    )
