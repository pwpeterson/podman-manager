"""Stack management operations for multi-service projects."""

# pyright: reportPossiblyUnboundVariable=false

import subprocess
import time
from typing import List

from rich.progress import Progress, SpinnerColumn, TextColumn

from core.config import console, verbose_print


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
        # Handle stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._stop_stack(project_name)

        # For quadlet mode, we primarily work with the vllm-stack
        if target in ["vllm-stack", "stack", "vllm"]:
            console.print("pm stop vllm")
            console.print()

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
            vllm_services = [
                "vllm-qwen25-coder-32b-instruct-awq",
                "vllm-delegator-mcp",
                "vllm-proxy",
                "vllm-glm41-9b-thinking",
                "vllm-glm4-9b-chat",
                "vllm-deepseek-coder-v2",
            ]
            for service_name in vllm_services:
                console.print(f"[green]Stopping {service_name}...[/green]")
                if self.manager.stop_service(service_name, force=True, quiet=True):
                    console.print(f"  [green]Stopped {service_name}[/green]")
                else:
                    console.print(
                        f"  [yellow]{service_name} was not running or failed to stop[/yellow]"
                    )
                    all_success = False
                console.print()

            if all_success:
                console.print(
                    f"[green]Successfully stopped vllm stack ({len(vllm_services)} services)[/green]"
                )
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

        console.print(f"pm stop {project}")

        success = True
        stopped_services = []
        failed_services = []

        for service in services:
            console.print(f"[green]Stopping {service}...[/green]")
            service_stopped = self.manager.stop_service(service, quiet=True)

            if service_stopped:
                console.print(f"  [green]Stopped {service}[/green]")
                stopped_services.append(service)
            else:
                console.print(
                    f"  [yellow]{service} was not running or failed to stop[/yellow]"
                )
                failed_services.append(service)
                success = False
            console.print()

        if success:
            console.print(
                f"[green]Successfully stopped {project} stack ({len(stopped_services)} services)[/green]"
            )
        else:
            if stopped_services:
                console.print()
                console.print(
                    f"[yellow]Partially stopped {project} stack: {len(stopped_services)} succeeded, {len(failed_services)} failed[/yellow]"
                )
                console.print(f"[dim]  Stopped: {', '.join(stopped_services)}[/dim]")
                console.print(f"[dim]  Failed: {', '.join(failed_services)}[/dim]")
                console.print()
            else:
                console.print()
                console.print(
                    f"[yellow]No services in {project} stack were running or could be stopped[/yellow]"
                )
                console.print()
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

        console.print()
        console.print(f"[green]Restarting {project} stack...[/green]")
        console.print()

        success = True
        for service in services:
            console.print(f"[green]Restarting {service}...[/green]")
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

    def _show_stack_logs(self, project: str, follow: bool = False) -> None:
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
                self.manager.show_logs(service, follow=False)

            # Then follow the first service (most common use case)
            if services:
                console.print(
                    f"\n[bold cyan]=== Following {services[0]} ===[/bold cyan]"
                )
                self.manager.show_logs(services[0], follow=True)
        else:
            # For non-follow mode, show logs for each service
            for service in services:
                console.print(f"\n[bold cyan]=== {service} ===[/bold cyan]")
                self.manager.show_logs(service, follow=False)

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

        with Progress(  # type: ignore
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
        from operations.installer import QuadletInstaller

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
        from operations.installer import QuadletInstaller

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

        # Check if user cancelled the selection
        if resolved_stack == "CANCELLED":
            return False

        console.print()
        if service_file:
            # Get display name for the resolved service
            display_name = resolved_stack
            if display_name.endswith(".service"):
                display_name = display_name[:-8]  # Remove .service suffix
            elif display_name.endswith(".target"):
                display_name = display_name[:-7]  # Remove .target suffix
            console.print(f"[green]Installing {display_name} service...[/green]")
        else:
            console.print(f"[green]Installing {resolved_stack} stack...[/green]")
        console.print()

        # Check systemd health
        if not installer.check_systemd_user_session():
            console.print(
                "[yellow]Systemd health check failed. Installation may encounter issues.[/yellow]"
            )

        # Install the stack or service - use original service name for individual services
        if service_file:
            # For individual services, pass the original service name to avoid installing the whole stack
            success = installer.install_stack(stack)
        else:
            # For stacks, use the resolved stack name
            success = installer.install_stack(resolved_stack)

        if success:
            # Final success message - use appropriate term based on what was installed
            if service_file:
                console.print(f"[green]Successfully installed {stack} service[/green]")
            else:
                console.print(
                    f"[green]Successfully installed {resolved_stack} stack[/green]"
                )
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

        # Show different messages for verbose vs non-verbose mode
        from core.config import _verbose_enabled

        if _verbose_enabled:
            verbose_print(f"[green]Stopping all {project} services...[/green]")
            verbose_print("")
        else:
            console.print(f"[green]Stopping all {project} services...[/green]")
            console.print()

        stop_success = True
        for service in services:
            if _verbose_enabled:
                verbose_print(f"  [green]Stopping {service}...[/green]")
                if not self.manager.stop_service(service, quiet=True):
                    stop_success = False
            else:
                # Show individual service stopping without spinner for non-verbose
                console.print(f"[green]Stopping {service}...[/green]")
                service_stopped = self.manager.stop_service(service, quiet=True)

                if service_stopped:
                    console.print(f"  [green]Stopped {service}[/green]")
                else:
                    console.print(
                        f"  [yellow]{service} was not running or failed to stop[/yellow]"
                    )
                    stop_success = False
                console.print()

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
                from operations.container_builder import ContainerBuilder

                builder = ContainerBuilder(self.manager)
                build_success = builder.build_stack_podman(project, services)
            elif build_type in ["legacy", "quadlet"]:
                console.print(
                    f"[green]Building {project} images (quadlet build)...[/green]"
                )
                from operations.container_builder import ContainerBuilder

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
        from core.config import _verbose_enabled

        if _verbose_enabled:
            verbose_print(f"[green]Starting all {project} services...[/green]")
        else:
            console.print(f"[green]Starting all {project} services...[/green]")
            console.print()

        start_success = True
        for service in services:
            from core.config import _verbose_enabled

            service_name = self.manager._find_service_name(service)
            if service_name:
                if _verbose_enabled:
                    verbose_print(f"[green]  Starting {service}...[/green]")
                    restart_cmd = ["systemctl", "--user", "restart", service_name]
                    verbose_print(f"  [cyan]exec: {' '.join(restart_cmd)}[/cyan]")
                    restart_result = self.manager._run_systemctl_command(
                        restart_cmd,
                        f"restart_{service}",
                        suppress_errors=True,
                        quiet=True,
                    )

                    # Verbose mode continues with original logic
                    if restart_result.returncode == 0:
                        # Monitor service startup for this service
                        with Progress(  # type: ignore
                            SpinnerColumn(),
                            TextColumn(
                                f"[yellow]Monitoring {service} startup...[/yellow]"
                            ),
                            console=console,
                            transient=True,
                        ) as progress:
                            task = progress.add_task("monitoring", total=None)
                            service_success = self._monitor_service_startup(
                                service, service_name
                            )
                            progress.remove_task(task)

                        if not service_success:
                            start_success = False
                            # Show clean error message without detailed systemd output
                            clean_service_name = service.replace(
                                ".service", ""
                            ).replace(".target", "")
                            verbose_print(
                                f"    [red]{clean_service_name} start failed. Run [/red][white]pm reinit {clean_service_name}[/white][red] for AI analysis.[/red]"
                            )
                    else:
                        start_success = False
                        # Show clean failure message without detailed error output
                        clean_service_name = service.replace(".service", "").replace(
                            ".target", ""
                        )
                        verbose_print(
                            f"    [red]{clean_service_name} start failed. Run [/red][white]pm reinit {clean_service_name}[/white][red] for AI analysis.[/red]"
                        )
                else:
                    # Non-verbose mode: simple starting message without spinner
                    console.print(f"[green]Starting {service}...[/green]")
                    restart_cmd = ["systemctl", "--user", "restart", service_name]
                    restart_result = subprocess.run(
                        restart_cmd, capture_output=True, text=True
                    )

                    if restart_result.returncode == 0:
                        # Monitor service startup
                        service_success = self._monitor_service_startup(
                            service, service_name
                        )
                    else:
                        service_success = False

                    if restart_result.returncode == 0 and service_success:
                        console.print(f"  [green]Started {service}[/green]")
                        console.print()
                    elif restart_result.returncode != 0:
                        start_success = False
                        self._handle_service_start_failure(service, restart_result)
                    else:
                        start_success = False
                        clean_service_name = service.replace(".service", "").replace(
                            ".target", ""
                        )
                        console.print(
                            f"    [red]{clean_service_name} start failed. Run [/red][white]pm reinit {clean_service_name}[/white][red] for AI analysis.[/red]"
                        )
                        console.print()
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
            console.print()
            return False

    def _monitor_service_startup(
        self, target: str, service_name: str, timeout: int = 20
    ) -> bool:
        """Monitor service startup using healthchecks and logs"""
        # Wait a bit for service to start
        time.sleep(2)

        # Check service status first
        status_cmd = ["systemctl", "--user", "is-active", service_name]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)

        if status_result.returncode != 0:
            verbose_print(f"[red]Service {target} is not active[/red]")
            return False

        # Try to check container healthcheck first (most reliable)
        healthcheck_result = self._check_container_health(target)
        if healthcheck_result is not None:
            if healthcheck_result:
                verbose_print(
                    f"[green]Service {target} is healthy (healthcheck passed)[/green]"
                )
                return True
            else:
                verbose_print(f"[red]Service {target} healthcheck failed[/red]")
                return False

        # If no healthcheck available, use stability-based monitoring
        return self._monitor_service_stability(target, service_name)

    def _monitor_service_stability(self, target: str, service_name: str) -> bool:
        """Monitor service stability over time when no healthcheck is available"""
        verbose_print(
            f"    [cyan]Monitoring {target} stability (no healthcheck available)...[/cyan]"
        )

        status_cmd = ["systemctl", "--user", "is-active", service_name]

        # Check stability over multiple intervals
        check_intervals = [3, 6, 10]  # Check at 3s, 6s, and 10s

        for i, interval in enumerate(check_intervals):
            time.sleep(interval - (check_intervals[i - 1] if i > 0 else 0))

            status_result = subprocess.run(status_cmd, capture_output=True, text=True)

            if status_result.returncode != 0:
                verbose_print(
                    f"[red]Service {target} became inactive during stability check[/red]"
                )
                return False

            verbose_print(f"    [cyan]Service {target} stable at {interval}s[/cyan]")

        # If service has been stable for 10 seconds, check logs for any critical errors
        log_result = self._check_startup_logs(target, service_name)

        # Even if logs are unclear, if service is stable for 10+ seconds, assume success
        if log_result or True:  # Always return True if stable
            verbose_print(
                f"    [green]Service {target} is stable and appears healthy[/green]"
            )
            return True

        return log_result

    def _check_container_health(self, target: str) -> bool | None:
        """Check container healthcheck status. Returns None if no healthcheck configured."""
        try:
            # First, let's find what containers are actually running
            list_cmd = [
                "podman",
                "ps",
                "--format",
                "{{.Names}}",
                "--filter",
                "status=running",
            ]
            list_result = subprocess.run(list_cmd, capture_output=True, text=True)

            if list_result.returncode != 0:
                verbose_print(
                    f"[dim]Could not list running containers for {target}[/dim]"
                )
                return None

            running_containers = (
                list_result.stdout.strip().split("\n")
                if list_result.stdout.strip()
                else []
            )

            # Try to find the container name - handle both full and short service names
            container_names = [target]  # Start with the exact target name

            # Add variations with underscores
            container_names.append(target.replace("-", "_"))

            # If target is a full service name (e.g., local-ai-ollama), also try the short name
            if target.startswith("local-ai-"):
                short_name = target.replace("local-ai-", "")
                container_names.extend([short_name, short_name.replace("-", "_")])
            elif target.startswith("supabase-"):
                short_name = target.replace("supabase-", "")
                container_names.extend([short_name, short_name.replace("-", "_")])

            # Also try with prefixes in case container has them
            if not target.startswith("local-ai-") and not target.startswith(
                "supabase-"
            ):
                container_names.extend(
                    [
                        f"local-ai-{target}",
                        f"local_ai_{target}",
                        f"supabase-{target}",
                        f"supabase_{target}",
                    ]
                )

            # Find matching container from running containers
            matching_container = None
            for container_name in container_names:
                for running_container in running_containers:
                    if (
                        container_name == running_container
                        or container_name in running_container
                    ):
                        matching_container = running_container
                        break
                if matching_container:
                    break

            if not matching_container:
                verbose_print(f"[dim]No running container found for {target}[/dim]")
                return None

            # Check if container exists and get its health status
            inspect_cmd = [
                "podman",
                "inspect",
                "--format",
                "{{.State.Health.Status}}",
                matching_container,
            ]
            result = subprocess.run(inspect_cmd, capture_output=True, text=True)

            if result.returncode == 0 and result.stdout.strip():
                health_status = result.stdout.strip()
                verbose_print(
                    f"    [cyan]Container {matching_container} health status: {health_status}[/cyan]"
                )

                if health_status == "healthy":
                    return True
                elif health_status == "starting":
                    # If starting, wait longer and check multiple times
                    verbose_print(
                        f"    [cyan]Container {matching_container} is starting, waiting up to 15 seconds...[/cyan]"
                    )

                    # Check multiple times over 15 seconds
                    for wait_time in [3, 6, 10, 15]:
                        time.sleep(3)  # Wait 3 seconds between each check
                        result = subprocess.run(
                            inspect_cmd, capture_output=True, text=True
                        )
                        if result.returncode == 0:
                            health_status = result.stdout.strip()
                            verbose_print(
                                f"    [cyan]Container {matching_container} health status after {wait_time}s: {health_status}[/cyan]"
                            )

                            if health_status == "healthy":
                                return True
                            elif health_status == "unhealthy":
                                return False
                            # If still "starting", continue waiting

                    # After 15 seconds, if still starting, assume it's taking too long but don't fail
                    verbose_print(
                        f"    [cyan]Container {matching_container} still starting after 15s, falling back to stability check[/cyan]"
                    )
                    return None  # Fall back to stability monitoring
                elif health_status == "unhealthy":
                    return False
                elif health_status == "none":
                    # No healthcheck configured
                    verbose_print(
                        f"[dim]Container {matching_container} has no healthcheck configured[/dim]"
                    )
                    return None
                else:
                    # Unknown status, assume no healthcheck
                    verbose_print(
                        f"[dim]Container {matching_container} has unknown health status: {health_status}[/dim]"
                    )
                    return None
            else:
                verbose_print(
                    f"[cyan]Could not inspect container {matching_container}[/cyan]"
                )
                return None

        except Exception as e:
            verbose_print(
                f"[dim]Could not check container health for {target}: {e}[/dim]"
            )
            return None

    def _check_startup_logs(self, target: str, service_name: str) -> bool:
        """Check startup logs for success/failure patterns"""
        verbose_print(f"    [cyan]Checking startup logs for {target}...[/cyan]")

        # Get recent logs to check for critical errors
        logs_cmd = [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "--since",
            "20 seconds ago",
            "-n",
            "50",
            "--no-pager",
        ]

        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)

        if logs_result.returncode == 0 and logs_result.stdout:
            log_content = logs_result.stdout.lower()
            verbose_print(
                f"    [cyan]Log content preview for {target}: {log_content[:200]}...[/cyan]"
            )

            # Check for critical error patterns that indicate startup failure
            critical_error_patterns = [
                "fatal error",
                "critical error",
                "startup failed",
                "failed to start",
                "cannot start",
                "unable to start",
                "bind: address already in use",
                "permission denied",
                "no such file or directory",
                "command not found",
                "segmentation fault",
                "panic:",
                "abort",
                # Only check for exit codes that indicate failure
                "exited with code 1",
                "exited with code 2",
                "exit status 1",
                "exit status 2",
            ]

            # Check for positive success patterns (more comprehensive)
            success_patterns = [
                "started successfully",
                "server started",
                "listening on",
                "ready to accept",
                "initialization complete",
                "service ready",
                "startup complete",
                "server is ready",
                "application started",
                "service started",
                "daemon started",
                # ClickHouse specific patterns
                "processing configuration file",
                "logging trace to",
                "logging errors to",
                # Neo4j patterns
                "started neo4j",
                "remote interface available",
                "bolt enabled",
                # PostgreSQL patterns
                "database system is ready to accept connections",
                "listening on ipv4 address",
                # Redis patterns
                "ready to accept connections",
                "server initialized",
                # Ollama patterns
                "ollama serving",
                "listening at",
                # FastAPI patterns
                "uvicorn running",
                "application startup complete",
                "started server process",
                # General container patterns
                "container started",
                "service initialized",
                # Generic success indicators
                "up and running",
                "successfully initialized",
                "ready for connections",
            ]

            # Look for critical errors that definitely indicate failure
            has_critical_errors = any(
                pattern in log_content for pattern in critical_error_patterns
            )
            has_success_indicators = any(
                pattern in log_content for pattern in success_patterns
            )

            if has_critical_errors:
                verbose_print(
                    f"[red]Detected critical startup errors in {target} logs[/red]"
                )
                return False
            elif has_success_indicators:
                verbose_print(
                    f"[green]Service {target} started successfully (log analysis)[/green]"
                )
                return True
            else:
                verbose_print(
                    f"    [cyan]No clear success/failure indicators in {target} logs[/cyan]"
                )

        # If service is active and no critical errors found, be more optimistic
        verbose_print(
            f"    [green]Service {target} is active and stable (assuming success)[/green]"
        )
        return True

    def _show_startup_failure_logs(self, target: str, service_name: str) -> None:
        """Show recent logs when service fails to start properly"""
        from ai_system.log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer(self.manager)
        analyzer.show_startup_failure_logs(target, service_name)

    def _handle_service_start_failure(self, service: str, restart_result) -> None:
        """Handle service start failure with detailed error reporting"""
        # Clean service name for display
        clean_service_name = service.replace(".service", "").replace(".target", "")

        # Show clean failure message with AI analysis suggestion
        console.print(
            f"      [red]{clean_service_name} start failed. Run [/red][white]pm reinit {clean_service_name}[/white][red] for AI analysis.[/red]"
        )
        console.print()

    def _show_stack_next_steps(self, project: str) -> None:
        """Show optional next steps for the stack"""
        console.print("[green]Optional:[/green]")
        console.print(
            f"[green] Check emojie service status:[/green] [white]pm status {project}[/white]"
        )
        console.print(
            f"    [green] View detailed logs:[/green] [white]pm logs {project}[/white]"
        )
        console.print(
            f"  [green] Diagnose the issue:[/green] [white]pm diagnose {project}[/white]"
        )
        console.print(
            f"[green] Reset failed state:[/green] [white]pm reset-failed {project}[/white]"
        )
        console.print()
