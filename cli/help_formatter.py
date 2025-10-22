#!/usr/bin/env python3
"""
Rich-formatted help display for podman manager
"""

from rich.table import Table

from config import console


def show_rich_help():
    """Show beautiful Rich-formatted help for vLLM Quadlet Manager"""
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
                    "status [cyan]<stack|service>[/cyan] [-v]",
                    "Show service status tree with running status (-v: verbose with container details)",
                    "pm status vllm-qwen25 -v",
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
