"""Reinit operations for services and stacks with advanced monitoring."""

import re
import subprocess
import time

from rich.progress import Progress, SpinnerColumn, TextColumn

from config import console, verbose_print


class ReinitManager:
    """Handles complex reinit operations with monitoring and error handling"""

    def __init__(self, manager):
        self.manager = manager

    def reinit(
        self, target: str, build: bool = False, build_type: str | None = None
    ) -> bool:
        """Stop service, reload daemon, and restart service (useful for .container file changes)"""
        # Clear cache at the start
        self.manager._clear_auto_match_cache()

        # Handle backward compatibility - if build=True and no build_type, use legacy
        if build and build_type is None:
            build_type = "legacy"

        # PRIORITY 1: Check for stack names first (before trying service name resolution)
        # Handle legacy stack targets
        if target in ["vllm", "vllm-stack", "stack"]:
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack("vllm", build_type=build_type)
        elif target == "taskflow-stack":
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack("taskflow", build_type=build_type)
        elif target.endswith("-stack"):
            # Generic stack target
            project_name = target[:-6]  # Remove "-stack" suffix
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack(project_name, build_type=build_type)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        # Try to find it in discovered stacks before trying service resolution
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack(target, build_type=build_type)

        # PRIORITY 3: Try service name resolution
        service_name = self.manager._find_service_name(target)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack(stack_name, build_type=build_type)

        # PRIORITY 4: Handle individual service (only if not a stack)
        if service_name:
            return self._reinit_service_direct(
                target, service_name, build_type=build_type
            )
        else:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False

    def _reinit_service_direct(
        self, target: str, service_name: str, build_type: str | None = None
    ) -> bool:
        """Reinit a single service using already-resolved service name"""
        console.print(f"\n[green]Reinitializing {target}...[/green]\n")

        # Use the provided service_name to avoid duplicate resolution
        # Stop the service
        verbose_print(f"[green]Stopping {target}...[/green]")
        stop_cmd = ["systemctl", "--user", "stop", service_name]
        verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
        stop_result = self.manager._run_systemctl_command(
            stop_cmd, f"stop_{target}", quiet=True
        )
        stop_success = stop_result.returncode == 0

        if stop_success:
            console.print(f"[green]Stopped {target}[/green]")
        else:
            console.print("[yellow]Service was not running or failed to stop[/yellow]")

        # Build if requested
        if build_type == "podman":
            console.print(f"[green]Building {target} (podman)...[/green]")
            from container_builder import ContainerBuilder

            builder = ContainerBuilder(self.manager)
            build_success = builder.build_service_podman(target)
            if not build_success:
                console.print("[red]Failed to build images[/red]")
                return False
        elif build_type in ["legacy", "quadlet"]:
            console.print(f"[green]Building {target} (quadlet)...[/green]")
            from container_builder import ContainerBuilder

            builder = ContainerBuilder(self.manager)
            build_success = builder.build_service(target)
            if not build_success:
                console.print("[red]Failed to build images[/red]")
                return False

        # Handle daemon reload
        verbose_print("[green]Reloading systemd daemon...[/green]")

        if build_type not in ["legacy", "quadlet"]:
            reload_success = self.manager.reload_daemon()
            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False
        else:
            # Quadlet build script already reloaded daemon, add delay and force another reload
            time.sleep(3)
            reload_success = self.manager.reload_daemon()
            if not reload_success:
                console.print(
                    "[yellow]Warning: Additional daemon reload failed[/yellow]"
                )
            else:
                time.sleep(1)

        # Start the service using the resolved service name
        verbose_print(f"[green]Starting {target}...[/green]")
        start_cmd = ["systemctl", "--user", "start", service_name]
        verbose_print(f"[cyan]exec: {' '.join(start_cmd)}[/cyan]")
        start_result = self.manager._run_systemctl_command(
            start_cmd, f"start_{target}", quiet=True
        )
        start_success = start_result.returncode == 0

        if not start_success and start_result.stderr:
            self._handle_start_failure(target, start_result)

        if start_success:
            # Monitor service logs to verify successful startup
            with Progress(
                SpinnerColumn(),
                TextColumn("[yellow]Monitoring service startup...[/yellow]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("monitoring", total=None)
                actual_success = self._monitor_service_startup(target, service_name)
                progress.remove_task(task)

            if actual_success:
                console.print(f"[green]Started {target}[/green]")
                console.print(f"\n[green]Successfully reinitialized {target}[/green]\n")

                # Show optional next steps
                self._show_next_steps(target)
                return True
            else:
                console.print(
                    f"[red]Failed to reinitialize {target} - service did not start properly[/red]\n"
                )
                # Show the detailed error logs and recommendations after the failure message
                self._show_startup_failure_logs(target, service_name)
                return False
        else:
            console.print(f"[red]Failed to start {target} after reinit[/red]")
            return False

    def _handle_start_failure(self, target: str, start_result) -> None:
        """Handle service start failure with detailed error reporting"""
        # Extract and summarize the error message
        error_msg = start_result.stderr.strip()
        if "Job for" in error_msg and "failed because" in error_msg:
            # Extract service name from error
            service_match = re.search(r"Job for ([^\s]+) failed", error_msg)
            service_name_from_error = (
                service_match.group(1) if service_match else target
            )

            console.print(
                f"[red]❌ Service startup failed: {service_name_from_error}[/red]"
            )
            console.print("[yellow]💡 Recommended actions:[/yellow]")

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
                f"[green] Check service status:[/green] [white]pm status {target}[/white]"
            )
            console.print(
                f"[green]   View detailed logs:[/green] [white]pm logs {target}[/white]"
            )
            console.print(
                f"[green]   Diagnose the issue:[/green] [white]pm diagnose {target}[/white]"
            )
            console.print(
                f"[green]   Reset failed state:[/green] [white]pm reset-failed {target}[/white]"
            )
        else:
            console.print(f"[red]Start failed: {error_msg}[/red]")

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

    def _show_next_steps(self, target: str) -> None:
        """Show optional next steps after successful reinit"""
        console.print("[green]Optional:[/green]")
        console.print(
            f"[green] Check service status:[/green] [white]pm status {target}[/white]"
        )
        console.print(
            f"  [green] View detailed logs:[/green] [white]pm logs {target}[/white]"
        )
        console.print(
            f"  [green] Diagnose the issue:[/green] [white]pm diagnose {target}[/white]"
        )
        console.print(
            f"  [green] Reset failed state:[/green] [white]pm reset-failed {target}[/white]"
        )
        console.print()
