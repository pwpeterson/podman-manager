"""Stack management operations for multi-service projects."""

import subprocess
import time
from typing import List

from rich.progress import Progress, SpinnerColumn, TextColumn

from config import console, verbose_print


class StackManager:
    """Handles multi-service stack operations and coordination"""

    def __init__(self, manager):
        self.manager = manager

    def _get_stack_services(self, project: str) -> List[str]:
        """Get list of services for a project stack"""
        # Normalize project name to stack name format
        if not project.endswith("-stack"):
            stack_name = f"{project}-stack"
        else:
            stack_name = project

        # Look up in discovered stack services
        if (
            hasattr(self.manager, "stack_services")
            and stack_name in self.manager.stack_services
        ):
            return self.manager.stack_services[stack_name]

        # If not found, return empty list
        return []

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
            console.print(f"  Stopping {service}...")
            if self.manager.stop_service(service, quiet=False):
                stopped_services.append(service)
            else:
                failed_services.append(service)
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

    def _start_stack(self, project: str) -> bool:
        """Start all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Starting {project} stack...[/yellow]")

        success = True
        for service in services:
            console.print(f"[dim]  Starting {service}...[/dim]")
            if not self.manager.start_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully started {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to start[/yellow]"
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
            console.print(f"[dim]  Restarting {service}...[/dim]")
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
            console.print(f"[dim]  Enabling {service}...[/dim]")
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
            console.print(f"[dim]  Disabling {service}...[/dim]")
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

    def uninstall_stack(self, stack: str) -> bool:
        """Uninstall quadlet stack from systemd directory"""
        from installer import QuadletInstaller

        console.print(f"[green]Uninstalling {stack} stack...[/green]")

        try:
            installer = QuadletInstaller()
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            return False

        # Validate the stack or service first to get the resolved name
        is_valid, resolved_stack, service_file = installer.validate_stack_or_service(
            stack
        )
        if not is_valid:
            return False

        # Use the resolved stack name from validation
        full_stack_name = resolved_stack

        # Check systemd health
        if not installer.check_systemd_user_session():
            console.print(
                "[yellow]Systemd health check failed. Uninstallation may encounter issues.[/yellow]"
            )

        # Uninstall the stack
        success = installer.uninstall_stack(full_stack_name)

        if success:
            # Final success message
            console.print(f"[green]Successfully uninstalled {stack} stack[/green]")

        return success

    def install_stack(self, stack: str) -> bool:
        """Install/build quadlet stack or service using integrated installer module"""
        from installer import QuadletInstaller

        try:
            installer = QuadletInstaller()
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            return False

        # Check if it's a stack or service first to show correct message
        is_valid, resolved_stack, service_file = installer.validate_stack_or_service(
            stack
        )
        if not is_valid:
            return False

        console.print()
        if service_file:
            console.print(f"[green]Installing {stack} service...[/green]")
        else:
            console.print(f"[green]Installing {stack} stack...[/green]")
        console.print()

        # Check systemd health
        if not installer.check_systemd_user_session():
            console.print(
                "[yellow]Systemd health check failed. Installation may encounter issues.[/yellow]"
            )

        # Install the stack or service - pass original user input, not resolved stack
        success = installer.install_stack(stack)

        if success:
            # Final success message - use appropriate term based on what was installed
            if service_file:
                console.print(f"[green]Successfully installed {stack} service[/green]")
            else:
                console.print(f"[green]Successfully installed {stack} stack[/green]")
            console.print()

        return success

    def reinit_stack(
        self, project: str, build: bool = False, build_type: str | None = None
    ) -> bool:
        """Reinit an entire project stack"""
        console.print(f"\n[green]Reinitializing {project} stack...[/green]\n")

        services = self._get_stack_services(project)

        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        verbose_print(f"[green]Stopping all {project} services...[/green]")
        stop_success = True
        for service in services:
            verbose_print(f"  Stopping {service}...")
            if not self.manager.stop_service(service, quiet=False):
                stop_success = False

        if not stop_success:
            console.print(
                "[yellow]Some services were not running or failed to stop[/yellow]"
            )

        # Step 2: Build if requested
        if build_type:
            # Handle backward compatibility
            if build and build_type is None:
                build_type = "legacy"

            if build_type == "podman":
                console.print(
                    f"[green]Building {project} images (podman build)...[/green]"
                )
                from container_builder import ContainerBuilder

                builder = ContainerBuilder(self.manager)
                build_success = builder.build_stack_podman(project, services)
            elif build_type in ["legacy", "quadlet"]:
                console.print(
                    f"[green]Building {project} images (quadlet build)...[/green]"
                )
                from container_builder import ContainerBuilder

                builder = ContainerBuilder(self.manager)
                build_success = builder._build_stack(project, services)
            else:
                build_success = True  # No build requested

            if not build_success:
                console.print(f"[red]Failed to build images for {project} stack[/red]")
                return False

        # Handle daemon reload and timing
        verbose_print("[green]Reloading systemd daemon...[/green]")

        if build_type not in ["legacy", "quadlet"]:
            # For podman build, we need to reload daemon manually
            reload_success = self.manager.reload_daemon()

            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False
        else:
            # Quadlet build script already reloaded daemon, add delay and force another reload
            time.sleep(3)  # Give systemd time to process new quadlet files

            # Force another daemon reload to ensure new services are recognized
            reload_success = self.manager.reload_daemon()

            if not reload_success:
                console.print(
                    "[yellow]Warning: Additional daemon reload failed[/yellow]"
                )
            else:
                time.sleep(1)  # Brief pause after reload

        # Restart all services
        verbose_print(f"[green]Starting all {project} services...[/green]")
        start_success = True
        for service in services:
            verbose_print(f"[dim]  Starting {service}...[/dim]")
            service_name = self.manager._find_service_name(
                service, allow_interactive=False
            )
            if service_name:
                restart_cmd = ["systemctl", "--user", "restart", service_name]
                verbose_print(f"  [cyan]exec: {' '.join(restart_cmd)}[/cyan]")
                restart_result = subprocess.run(
                    restart_cmd, capture_output=True, text=True
                )
                if restart_result.returncode == 0:
                    # Monitor service startup for this service
                    with Progress(
                        SpinnerColumn(),
                        TextColumn(f"[yellow]Monitoring {service} startup...[/yellow]"),
                        console=console,
                        transient=True,
                    ) as progress:
                        task = progress.add_task("monitoring", total=None)
                        service_success = self._monitor_service_startup(
                            service, service_name
                        )
                        progress.remove_task(task)

                    if service_success:
                        console.print(f"[green]Started {service}[/green]")
                    else:
                        start_success = False
                        # Show detailed error logs after spinner disappears
                        console.print(
                            f"[red]Failed to start {service} - service did not start properly[/red]\n"
                        )
                        self._show_startup_failure_logs(service, service_name)
                else:
                    start_success = False
                    self._handle_service_start_failure(service, restart_result)
            else:
                console.print(f"[red]Could not find service for {service}[/red]")
                start_success = False

        if start_success:
            console.print(
                f"\n[green]Successfully reinitialized {project} stack[/green]\n"
            )
            self._show_stack_next_steps(project)
            return True
        else:
            console.print(
                f"[red]Failed to start some services in {project} stack[/red]"
            )
            return False

    def _monitor_service_startup(
        self, target: str, service_name: str, timeout: int = 10
    ) -> bool:
        """Monitor service logs to verify successful startup"""
        # Wait a moment for service to start
        time.sleep(10)

        # Check service status first
        status_cmd = ["systemctl", "--user", "is-active", service_name]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)

        if status_result.returncode != 0:
            return False

        # Get recent logs to check for errors
        logs_cmd = [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "--since",
            "10 seconds ago",
            "-n",
            "20",
            "--no-pager",
        ]

        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)

        if logs_result.returncode == 0 and logs_result.stdout:
            log_content = logs_result.stdout.lower()

            # Check for common error patterns in logs
            error_patterns = [
                "error",
                "failed",
                "exception",
                "traceback",
                "fatal",
                "critical",
                "cannot",
                "unable to",
                "connection refused",
                "timeout",
                "permission denied",
            ]

            # Check for success patterns
            success_patterns = [
                "started",
                "listening",
                "ready",
                "running",
                "initialized",
                "server started",
            ]

            has_errors = any(pattern in log_content for pattern in error_patterns)
            has_success = any(pattern in log_content for pattern in success_patterns)

            if has_errors and not has_success:
                verbose_print(f"[red]Detected errors in {target} startup logs[/red]")
                return False
            elif has_success:
                verbose_print(f"[green]Service {target} started successfully[/green]")
                return True

        # If no clear success/failure indicators, assume success if service is active
        verbose_print(
            f"[yellow]Service {target} appears to be running (no clear startup indicators)[/yellow]"
        )
        return True

    def _show_startup_failure_logs(self, target: str, service_name: str) -> None:
        """Show recent logs when service fails to start properly"""
        from log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer(self.manager)
        analyzer.show_startup_failure_logs(target, service_name)

    def _handle_service_start_failure(self, service: str, restart_result) -> None:
        """Handle service start failure with detailed error reporting"""
        if restart_result.stderr:
            # Extract and summarize the error message
            error_msg = restart_result.stderr.strip()
            if "Job for" in error_msg and "failed because" in error_msg:
                # Extract service name from error
                import re

                service_match = re.search(r"Job for ([^\s]+) failed", error_msg)
                service_name_from_error = (
                    service_match.group(1) if service_match else service
                )

                console.print(
                    f"[red]❌ Service startup failed: {service} ({service_name_from_error})[/red]"
                )
                console.print(f"[yellow]💡 Recommended actions for {service}:[/yellow]")

                # Extract systemd-recommended commands from error message
                systemd_commands = []
                if 'See "' in error_msg:
                    # Find all commands between quotes after "See"
                    see_pattern = r'See "([^"]+)"'
                    matches = re.findall(see_pattern, error_msg)
                    systemd_commands = matches

                # Add systemd-recommended commands first
                for cmd in systemd_commands:
                    console.print(
                        f"[green] Run systemd command:[/green] [white]{cmd}[/white]"
                    )

                # Add our standard troubleshooting commands
                console.print(
                    f"[green] Check service status:[/green] [white]pm status {service}[/white]"
                )
                console.print(
                    f"[green]   View detailed logs:[/green] [white]pm logs {service}[/white]"
                )
                console.print(
                    f"[green]   Diagnose the issue:[/green] [white]pm diagnose {service}[/white]"
                )
                console.print(
                    f"[green]   Reset failed state:[/green] [white]pm reset-failed {service}[/white]"
                )
            else:
                console.print(f"[red]Restart failed for {service}: {error_msg}[/red]")

    def _show_stack_next_steps(self, project: str) -> None:
        """Show optional next steps for the stack"""
        console.print("[green]Optional:[/green]")
        console.print(
            f"[green] Check service status:[/green] [white]pm status {project}[/white]"
        )
        console.print(
            f"  [green] View detailed logs:[/green] [white]pm logs {project}[/white]"
        )
        console.print(
            f"  [green] Diagnose the issue:[/green] [white]pm diagnose {project}[/white]"
        )
        console.print(
            f"  [green] Reset failed state:[/green] [white]pm reset-failed {project}[/white]"
        )
        console.print()
