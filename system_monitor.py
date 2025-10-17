"""System monitoring and health check operations."""

import subprocess
from typing import List

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from config import console


class SystemMonitor:
    """Handles system monitoring, health checks, and maintenance operations"""

    def __init__(self, manager):
        self.manager = manager

    def check_auto_update_status(self) -> None:
        """Check if podman auto-update timer is enabled"""
        console.print("[yellow]Checking auto-update status...[/yellow]")

        # Check if auto-update timer is enabled
        timer_cmd = ["systemctl", "--user", "is-enabled", "podman-auto-update.timer"]
        console.print(f"[cyan]exec: {' '.join(timer_cmd)}[/cyan]")

        result = subprocess.run(timer_cmd, capture_output=True, text=True)

        if result.returncode == 0 and "enabled" in result.stdout:
            console.print("[green]Podman auto-update timer is enabled[/green]")

            # Show next run time
            next_cmd = [
                "systemctl",
                "--user",
                "list-timers",
                "podman-auto-update.timer",
            ]
            next_result = subprocess.run(next_cmd, capture_output=True, text=True)
            if next_result.returncode == 0:
                console.print(next_result.stdout)
        else:
            console.print("[yellow]Podman auto-update timer is not enabled[/yellow]")
            console.print(
                "[dim]Enable with: systemctl --user enable --now podman-auto-update.timer[/dim]"
            )

    def enable_auto_update(self) -> bool:
        """Enable podman auto-update timer"""
        console.print("[yellow]Enabling podman auto-update timer...[/yellow]")

        cmd = ["systemctl", "--user", "enable", "--now", "podman-auto-update.timer"]
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print("[green]Podman auto-update timer enabled[/green]")
            return True
        else:
            console.print(
                f"[red]Failed to enable auto-update timer: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
            )
            return False

    def trigger_auto_update(self) -> bool:
        """Manually trigger podman auto-update"""
        console.print("[yellow]Triggering manual auto-update...[/yellow]")

        cmd = ["systemctl", "--user", "start", "podman-auto-update.service"]
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print("[green]Auto-update triggered successfully[/green]")
            return True
        else:
            console.print(
                f"[red]Failed to trigger auto-update: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
            )
            return False

    def show_container_status(self) -> None:
        """Show status of containers managed by quadlets"""
        console.print("[yellow]Checking container status...[/yellow]")

        # Get containers that might be managed by our quadlets
        cmd = [
            "podman",
            "ps",
            "-a",
            "--format",
            "{{.Names}};{{.Image}};{{.Status}};{{.Ports}}",
            "--filter",
            "label=io.containers.autoupdate=registry",
        ]

        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Image", style="dim", max_width=40)
            table.add_column("Status", no_wrap=True)
            table.add_column("Ports", style="blue", max_width=30)

            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split(";")
                    if len(parts) >= 4:
                        name, image, status, ports = parts[:4]

                        # Color code status
                        if "Up" in status or "running" in status.lower():
                            colored_status = f"[green]{status}[/green]"
                        elif "Exited" in status:
                            colored_status = f"[red]{status}[/red]"
                        else:
                            colored_status = f"[yellow]{status}[/yellow]"

                        table.add_row(name, image, colored_status, ports)

            console.print(table)
        else:
            console.print("[dim]No containers with auto-update labels found[/dim]")

    def exec_command(self, target: str, command: List[str]) -> None:
        """Execute command in container (find container by service name)"""
        # First, we need to find the container name from the service
        self.manager._clear_auto_match_cache()
        service_name = self.manager._find_service_name(target, allow_interactive=True)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return

        # Get the container name associated with this service
        # This is tricky with quadlets - we need to infer the container name
        # Usually it's based on the service name
        container_name = target
        if target in self.manager.vllm_services:
            # Use the short name as container name
            container_name = target

        cmd = ["podman", "exec", "-it", container_name] + command
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            subprocess.run(cmd)
        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")
            console.print(
                f"[dim]Container '{container_name}' may not be running or accessible[/dim]"
            )

    def prune_containers(self, enhanced: bool = True, quick: bool = False) -> None:
        """Remove unused containers and images with intelligent analysis

        Args:
            enhanced: Use enhanced prune with analysis (default: True)
            quick: Use quick prune mode (default: False)
        """
        if enhanced and not quick:
            # Use enhanced prune with full analysis
            from prune import EnhancedPruner

            pruner = EnhancedPruner(console)
            success = pruner.run_safe_prune_workflow()
            if not success:
                console.print(
                    "[yellow]Enhanced prune failed, falling back to basic prune[/yellow]"
                )
                self._basic_prune_containers()
        elif quick:
            # Use quick prune from enhanced pruner
            from prune import EnhancedPruner

            pruner = EnhancedPruner(console)
            pruner.run_quick_prune()
        else:
            # Use basic prune
            self._basic_prune_containers()

    def _basic_prune_containers(self) -> None:
        """Basic prune functionality (original implementation)"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold white]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                # Step 1: Prune containers
                task1 = progress.add_task("Pruning unused containers...", total=None)
                result1 = subprocess.run(
                    ["podman", "container", "prune", "-f"],
                    capture_output=True,
                    text=True,
                )
                progress.remove_task(task1)

                if result1.returncode != 0:
                    console.print(
                        f"[yellow]Container prune warning: {result1.stderr.strip()}[/yellow]"
                    )

                # Step 2: Prune images
                task2 = progress.add_task("Pruning unused images...", total=None)
                result2 = subprocess.run(
                    ["podman", "image", "prune", "-f"], capture_output=True, text=True
                )
                progress.remove_task(task2)

                if result2.returncode != 0:
                    console.print(
                        f"[yellow]Image prune warning: {result2.stderr.strip()}[/yellow]"
                    )

            console.print("[green]Prune completed[/green]")

            # Show what was cleaned up if there's output
            if result1.stdout.strip():
                console.print(f"[dim]Containers: {result1.stdout.strip()}[/dim]")
            if result2.stdout.strip():
                console.print(f"[dim]Images: {result2.stdout.strip()}[/dim]")

        except Exception as e:
            console.print(f"[red]Error pruning: {e}[/red]")

    def prune(self, enhanced: bool = True, quick: bool = False) -> None:
        """Alias for prune_containers for compatibility"""
        self.prune_containers(enhanced=enhanced, quick=quick)

    def show_system_df(self) -> None:
        """Show system disk usage"""
        df_cmd = ["podman", "system", "df"]
        console.print(f"[cyan]exec: {' '.join(df_cmd)}[/cyan]")

        result = subprocess.run(df_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(result.stdout)
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Failed to get system disk usage: {error_msg}[/red]")

    def health_check(self, target: str | None = None) -> None:
        """Perform comprehensive health check on services or entire system"""
        if target:
            self._health_check_service(target)
        else:
            self._health_check_system()

    def _health_check_service(self, target: str) -> None:
        """Health check for a specific service"""
        console.print(f"[yellow]🏥 Health check for {target}...[/yellow]")

        # Check service status
        service_name = self.manager._find_service_name(target, allow_interactive=True)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return

        # Get service status
        status_cmd = ["systemctl", "--user", "is-active", service_name]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)

        if status_result.returncode == 0:
            console.print(f"[green]✓ {target} is active[/green]")
        else:
            console.print(f"[red]✗ {target} is not active[/red]")

        # Check recent logs for errors
        logs_cmd = [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "--since",
            "5 minutes ago",
            "-n",
            "10",
            "--no-pager",
        ]

        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)
        if logs_result.returncode == 0 and logs_result.stdout:
            log_content = logs_result.stdout.lower()
            error_count = log_content.count("error") + log_content.count("failed")

            if error_count > 0:
                console.print(
                    f"[yellow]⚠ Found {error_count} error(s) in recent logs[/yellow]"
                )
            else:
                console.print("[green]✓ No recent errors in logs[/green]")

        # Service-specific health checks
        if target in ["vllm-proxy", "vllm-qwen25"]:
            self._check_vllm_health(target)
        elif target == "vllm-delegator":
            self._check_delegator_health(target)

    def _health_check_system(self) -> None:
        """Comprehensive system health check"""
        console.print("[yellow]🏥 System health check...[/yellow]")

        # Check systemd user session
        console.print("\n[cyan]Systemd User Session:[/cyan]")
        systemd_cmd = ["systemctl", "--user", "is-system-running"]
        systemd_result = subprocess.run(systemd_cmd, capture_output=True, text=True)

        if systemd_result.returncode == 0:
            console.print("[green]✓ Systemd user session is running[/green]")
        else:
            console.print(
                f"[red]✗ Systemd user session issues: {systemd_result.stdout.strip()}[/red]"
            )

        # Check podman
        console.print("\n[cyan]Podman Status:[/cyan]")
        podman_cmd = ["podman", "version", "--format", "{{.Client.Version}}"]
        podman_result = subprocess.run(podman_cmd, capture_output=True, text=True)

        if podman_result.returncode == 0:
            console.print(
                f"[green]✓ Podman version: {podman_result.stdout.strip()}[/green]"
            )
        else:
            console.print("[red]✗ Podman not available[/red]")

        # Check disk space
        console.print("\n[cyan]Disk Usage:[/cyan]")
        self.show_system_df()

        # Check running containers
        console.print("\n[cyan]Container Status:[/cyan]")
        self.show_container_status()

    def _check_vllm_health(self, target: str) -> None:
        """Health check for vLLM services"""
        # Try to import requests, handle gracefully if not available
        try:
            import requests
        except ImportError:
            console.print("[dim]requests not available for HTTP health check[/dim]")
            return

        if target == "vllm-proxy":
            # Check if proxy is responding
            try:
                response = requests.get("http://localhost:8002/health", timeout=5)
                if response.status_code == 200:
                    console.print("[green]✓ vLLM proxy is responding[/green]")
                else:
                    console.print(
                        f"[yellow]⚠ vLLM proxy returned status {response.status_code}[/yellow]"
                    )
            except Exception as e:
                console.print(f"[red]✗ vLLM proxy health check failed: {e}[/red]")

        elif target == "vllm-qwen25":
            # Check if model server is responding
            try:
                response = requests.get("http://localhost:8001/health", timeout=5)
                if response.status_code == 200:
                    console.print("[green]✓ vLLM model server is responding[/green]")
                else:
                    console.print(
                        f"[yellow]⚠ vLLM model server returned status {response.status_code}[/yellow]"
                    )
            except Exception as e:
                console.print(
                    f"[red]✗ vLLM model server health check failed: {e}[/red]"
                )

    def _check_delegator_health(self, target: str) -> None:
        """Health check for vLLM delegator service"""
        # Check if delegator is accessible (this is more complex due to MCP protocol)
        console.print(
            "[dim]vLLM delegator uses MCP protocol - basic service check only[/dim]"
        )

    def monitor_services(
        self, services: List[str] | None = None, interval: int = 5
    ) -> None:
        """Monitor services in real-time"""
        if services is None:
            services = ["vllm-qwen25", "vllm-proxy", "vllm-delegator"]

        console.print(f"[yellow]Monitoring services: {', '.join(services)}[/yellow]")
        console.print(
            f"[dim]Refresh interval: {interval}s (Press Ctrl+C to stop)[/dim]"
        )

        try:
            while True:
                console.clear()
                console.print(f"[bold cyan]Service Monitor - {services}[/bold cyan]")
                console.print("=" * 60)

                for service in services:
                    service_name = self.manager._find_service_name(
                        service, allow_interactive=True
                    )
                    if service_name:
                        status_cmd = ["systemctl", "--user", "is-active", service_name]
                        status_result = subprocess.run(
                            status_cmd, capture_output=True, text=True
                        )

                        if status_result.returncode == 0:
                            status = "[green]ACTIVE[/green]"
                        else:
                            status = "[red]INACTIVE[/red]"

                        console.print(f"{service:<20} {status}")
                    else:
                        console.print(f"{service:<20} [red]NOT FOUND[/red]")

                console.print("=" * 60)
                console.print(f"[dim]Next update in {interval}s...[/dim]")

                import time

                time.sleep(interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped[/yellow]")

    def system_info(self) -> None:
        """Display comprehensive system information"""
        console.print("[bold cyan]System Information[/bold cyan]")
        console.print("=" * 50)

        # OS Information
        try:
            with open("/etc/os-release", "r") as f:
                os_info = f.read()
                for line in os_info.split("\n"):
                    if line.startswith("PRETTY_NAME="):
                        os_name = line.split("=")[1].strip('"')
                        console.print(f"OS: {os_name}")
                        break
        except FileNotFoundError:
            console.print("OS: Unknown")

        # Podman version
        podman_cmd = ["podman", "version", "--format", "{{.Client.Version}}"]
        podman_result = subprocess.run(podman_cmd, capture_output=True, text=True)
        if podman_result.returncode == 0:
            console.print(f"Podman: {podman_result.stdout.strip()}")

        # Python version
        import sys

        console.print(f"Python: {sys.version.split()[0]}")

        # Systemd user session
        systemd_cmd = ["systemctl", "--user", "is-system-running"]
        systemd_result = subprocess.run(systemd_cmd, capture_output=True, text=True)
        console.print(f"Systemd: {systemd_result.stdout.strip()}")

        # Container count
        container_cmd = ["podman", "ps", "-a", "--format", "{{.Names}}"]
        container_result = subprocess.run(container_cmd, capture_output=True, text=True)
        if container_result.returncode == 0:
            container_count = len(
                [line for line in container_result.stdout.split("\n") if line.strip()]
            )
            console.print(f"Containers: {container_count}")

        # Image count
        image_cmd = ["podman", "images", "--format", "{{.Repository}}"]
        image_result = subprocess.run(image_cmd, capture_output=True, text=True)
        if image_result.returncode == 0:
            image_count = len(
                [line for line in image_result.stdout.split("\n") if line.strip()]
            )
            console.print(f"Images: {image_count}")

        console.print("=" * 50)
