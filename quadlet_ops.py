"""Quadlet container operations for vLLM services."""

import subprocess
from typing import List

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from config import console


class QuadletOperations:
    """Quadlet container operations for vLLM services"""

    def __init__(self, manager):
        self.manager = manager

    def show_logs(self, target: str, follow: bool = False, tail: int = 100) -> None:
        """Show service logs using journalctl"""
        success = self.manager.show_logs(target, follow=follow, lines=tail)
        if not success:
            console.print("[dim]Try running: pm list to see available services[/dim]")

    def start(self, target: str) -> bool:
        """Start a service or stack"""
        # Handle stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._start_stack(project_name)

        return self.manager.start_service(target)

    def stop(self, target: str) -> bool:
        """Stop a service or stack"""
        # Handle stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._stop_stack(project_name)

        return self.manager.stop_service(target)

    def down(self, target: str = "vllm-stack") -> bool:
        """Stop all services in a stack or project"""
        console.print(f"[yellow]Stopping {target}...[/yellow]")

        # Handle stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._stop_stack(project_name)

        # For quadlet mode, we primarily work with the vllm-stack
        if target in ["vllm-stack", "stack", "vllm"]:
            # Try to stop the stack target first (suppress errors since it may not exist)
            service_name = self.manager._find_service_name("vllm-stack")
            if service_name:
                cmd = ["systemctl", "--user", "stop", service_name]
                result = self.manager._run_systemctl_command(
                    cmd, "stop_vllm-stack", suppress_errors=True, quiet=True
                )

                if result.returncode == 0:
                    console.print("[green]✓ All services stopped[/green]")
                    return True

            # Stack target doesn't exist or failed, stop individual services with force
            all_success = True

            # Only stop vLLM services for vllm-stack, not all quadlet services
            vllm_services = ["vllm-qwen25", "vllm-proxy", "vllm-delegator"]
            for service_name in vllm_services:
                if not self.manager.stop_service(service_name, force=True, quiet=False):
                    all_success = False

            if all_success:
                console.print("[green]✓ All services stopped[/green]")
                return True
            else:
                console.print("[yellow]⚠ Some services may still be running[/yellow]")
                return False
        else:
            # For other targets, try to stop as a single service/target with force
            success = self.manager.stop_service(target, force=True, quiet=False)
            return success

    def restart(self, target: str) -> bool:
        """Restart a service or stack"""
        # Handle stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._restart_stack(project_name)

        return self.manager.restart_service(target)

    def reinit(self, target: str) -> bool:
        """Stop service, reload daemon, and restart service (useful for .container file changes)"""
        console.print(f"[yellow]Reinitializing {target}...[/yellow]")

        # Handle stack targets
        if target in ["vllm", "vllm-stack", "stack"]:
            return self._reinit_stack("vllm")
        elif target == "taskflow-stack":
            return self._reinit_stack("taskflow")
        elif target.endswith("-stack"):
            # Generic stack target
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._reinit_stack(project_name)

        # Handle individual service
        return self._reinit_service(target)

    def _reinit_service(self, target: str) -> bool:
        """Reinit a single service"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold white]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            # Step 1: Stop the service
            task1 = progress.add_task("Step 1: Stopping service...", total=None)
            stop_success = self.manager.stop_service(target)
            progress.remove_task(task1)

            if not stop_success:
                console.print(
                    "[yellow]Service was not running or failed to stop[/yellow]"
                )

            # Step 2: Reload systemd daemon
            task2 = progress.add_task("Step 2: Reloading systemd daemon...", total=None)
            reload_success = self.manager.reload_daemon()
            progress.remove_task(task2)

            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False

            # Step 3: Start the service
            task3 = progress.add_task("Step 3: Starting service...", total=None)
            start_success = self.manager.start_service(target)
            progress.remove_task(task3)

            if start_success:
                console.print(f"[green]Successfully reinitialized {target}[/green]")
                return True
            else:
                console.print(f"[red]Failed to start {target} after reinit[/red]")
                return False

    def _reinit_stack(self, project: str) -> bool:
        """Reinit an entire project stack"""
        if project == "vllm":
            services = ["vllm-qwen25", "vllm-proxy", "vllm-delegator"]
            display_name = "vLLM stack"
        elif project == "taskflow":
            services = ["taskflow-frontend", "taskflow-backend"]
            display_name = "taskflow stack"
        else:
            # Generic project - find services that start with project name
            services = [
                short_name
                for short_name in self.manager.quadlet_services.keys()
                if short_name.startswith(f"{project}-")
            ]
            display_name = f"{project} stack"

        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold white]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            # Step 1: Stop all services
            task1 = progress.add_task(
                f"Step 1: Stopping all {project} services...", total=None
            )
            stop_success = True
            for service in services:
                if not self.manager.stop_service(service, quiet=True):
                    stop_success = False
            progress.remove_task(task1)

            if not stop_success:
                console.print(
                    "[yellow]Some services were not running or failed to stop[/yellow]"
                )

            # Step 2: Reload systemd daemon
            task2 = progress.add_task("Step 2: Reloading systemd daemon...", total=None)
            reload_success = self.manager.reload_daemon()
            progress.remove_task(task2)

            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False

            # Step 3: Start all services
            task3 = progress.add_task(
                f"Step 3: Starting all {project} services...", total=None
            )
            start_success = True
            for service in services:
                if not self.manager.start_service(service):
                    start_success = False
            progress.remove_task(task3)

            if start_success:
                console.print(
                    f"[green]Successfully reinitialized {display_name}[/green]"
                )
                return True
            else:
                console.print(
                    f"[red]Failed to start some services in {display_name}[/red]"
                )
                return False

    def enable(self, target: str) -> bool:
        """Enable a service or stack to start at boot"""
        # Handle stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._enable_stack(project_name)

        return self.manager.enable_service(target)

    def disable(self, target: str) -> bool:
        """Disable a service or stack from starting at boot"""
        # Handle stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._disable_stack(project_name)

        return self.manager.disable_service(target)

    def reload_daemon(self) -> bool:
        """Reload systemd user daemon"""
        return self.manager.reload_daemon()

    def show_service_status(self, target: str) -> None:
        """Show detailed status for a specific service"""
        # Handle stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            self._show_stack_status(project_name)
            return

        service_name = self.manager._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return

        # Use systemctl status for detailed output
        cmd = ["systemctl", "--user", "status", service_name]
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[yellow]{result.stderr}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error getting service status: {e}[/red]")

    def update_images_and_restart(self, target: str) -> bool:
        """Update container images and restart service (for quadlets with auto-update)"""
        console.print(f"[yellow]Updating images for {target}...[/yellow]")

        # For quadlets, we can trigger podman auto-update
        update_cmd = ["podman", "auto-update"]
        console.print(f"[cyan]exec: {' '.join(update_cmd)}[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Updating container images", total=None)
            result = subprocess.run(update_cmd, capture_output=True, text=True)
            progress.remove_task(task)

        if result.returncode == 0:
            console.print("[green]Images updated successfully[/green]")
            if result.stdout:
                console.print(result.stdout)

            # Restart the service to use updated images
            return self.restart(target)
        else:
            console.print(
                f"[red]Failed to update images: {result.stderr.strip()}[/red]"
            )
            return False

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
                f"[red]Failed to enable auto-update timer: {result.stderr.strip()}[/red]"
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
                f"[red]Failed to trigger auto-update: {result.stderr.strip()}[/red]"
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
            from rich.table import Table

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
        service_name = self.manager._find_service_name(target)
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

    def prune_containers(self) -> None:
        """Remove unused containers and images"""
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

    def prune(self) -> None:
        """Alias for prune_containers for compatibility"""
        self.prune_containers()

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

    def _get_stack_services(self, project: str) -> List[str]:
        """Get list of services for a project stack"""
        if project == "vllm":
            return ["vllm-qwen25", "vllm-proxy", "vllm-delegator"]
        elif project == "taskflow":
            return ["taskflow-frontend", "taskflow-backend"]
        else:
            # Generic project - find services that start with project name
            return [
                short_name
                for short_name in self.manager.quadlet_services.keys()
                if short_name.startswith(f"{project}-")
            ]

    def _start_stack(self, project: str) -> bool:
        """Start all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Starting {project} stack...[/yellow]")
        success = True
        for service in services:
            if not self.manager.start_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully started {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to start[/yellow]"
            )
        return success

    def _stop_stack(self, project: str) -> bool:
        """Stop all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Stopping {project} stack...[/yellow]")
        success = True
        stopped_services = []
        failed_services = []

        for service in services:
            console.print(f"[bold white]  Stopping {service}...[/bold white]")
            if self.manager.stop_service(service, quiet=True):
                stopped_services.append(service)
                console.print(f"[green]  ✓ {service}[/green]")
            else:
                failed_services.append(service)
                console.print(f"[yellow]  ✗ {service} (not running or failed)[/yellow]")
                success = False

        if success:
            console.print(
                f"[green]Successfully stopped {project} stack ({len(stopped_services)} services)[/green]"
            )
        else:
            if stopped_services:
                console.print(
                    f"[yellow]Partially stopped {project} stack: {len(stopped_services)} succeeded, {len(failed_services)} failed[/yellow]"
                )
                console.print(f"[dim]  Stopped: {', '.join(stopped_services)}[/dim]")
                console.print(f"[dim]  Failed: {', '.join(failed_services)}[/dim]")
            else:
                console.print(
                    f"[yellow]No services in {project} stack were running or could be stopped[/yellow]"
                )
        return success

    def _restart_stack(self, project: str) -> bool:
        """Restart all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Restarting {project} stack...[/yellow]")
        success = True
        for service in services:
            if not self.manager.restart_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully restarted {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to restart[/yellow]"
            )
        return success

    def _enable_stack(self, project: str) -> bool:
        """Enable all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Enabling {project} stack...[/yellow]")
        success = True
        for service in services:
            if not self.manager.enable_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully enabled {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to enable[/yellow]"
            )
        return success

    def _disable_stack(self, project: str) -> bool:
        """Disable all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Disabling {project} stack...[/yellow]")
        success = True
        for service in services:
            if not self.manager.disable_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully disabled {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to disable[/yellow]"
            )
        return success

    def _show_stack_logs(
        self, project: str, follow: bool = False, tail: int = 100
    ) -> None:
        """Show logs for all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return

        console.print(f"[yellow]Showing logs for {project} stack services...[/yellow]")

        if follow:
            console.print(
                "[dim]Note: Following logs for multiple services - press Ctrl+C to stop[/dim]"
            )
            # For follow mode, show logs for all services in parallel (simplified approach)
            for service in services:
                console.print(f"\n[bold cyan]=== {service} ===[/bold cyan]")
                self.manager.show_logs(
                    service, follow=False, lines=tail // len(services)
                )

            # Then follow the first service (most common use case)
            if services:
                console.print(
                    f"\n[bold cyan]=== Following {services[0]} ===[/bold cyan]"
                )
                self.manager.show_logs(services[0], follow=True, lines=tail)
        else:
            # For non-follow mode, show logs for each service
            for service in services:
                console.print(f"\n[bold cyan]=== {service} ===[/bold cyan]")
                self.manager.show_logs(
                    service, follow=False, lines=tail // len(services)
                )

    def _show_stack_status(self, project: str) -> None:
        """Show status for all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return

        console.print(f"[bold cyan]{project.title()} Stack Status[/bold cyan]")

        for service in services:
            console.print(f"\n[bold yellow]=== {service} ===[/bold yellow]")
            service_name = self.manager._find_service_name(service)
            if service_name:
                cmd = [
                    "systemctl",
                    "--user",
                    "status",
                    service_name,
                    "--no-pager",
                    "-l",
                ]
                console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.stdout:
                        console.print(result.stdout)
                    if result.stderr:
                        console.print(f"[yellow]{result.stderr}[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error getting status for {service}: {e}[/red]")
            else:
                console.print(f"[red]Service '{service}' not found[/red]")

    def _update_stack(self, project: str) -> bool:
        """Update images and restart all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Updating images for {project} stack...[/yellow]")

        # For quadlets, we can trigger podman auto-update
        update_cmd = ["podman", "auto-update"]
        console.print(f"[cyan]exec: {' '.join(update_cmd)}[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Updating {project} stack images", total=None)
            result = subprocess.run(update_cmd, capture_output=True, text=True)
            progress.remove_task(task)

        if result.returncode == 0:
            console.print("[green]Images updated successfully[/green]")
            if result.stdout:
                console.print(result.stdout)

            # Restart all services in the stack
            return self._restart_stack(project)
        else:
            console.print(
                f"[red]Failed to update images: {result.stderr.strip()}[/red]"
            )
            return False
