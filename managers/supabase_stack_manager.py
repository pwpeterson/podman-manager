"""Supabase-specific stack management with proper startup order."""

import subprocess
import time
from typing import Dict, List, Optional

from rich.progress import Progress, SpinnerColumn, TextColumn

from core.config import console, verbose_print


class SupabaseStackManager:
    """Handles Supabase stack operations with proper dependency order"""

    def __init__(self, manager):
        self.manager = manager

        # Define the Supabase startup order based on docs/supabase-stack-startup-order.md
        self.startup_order = [
            {
                "layer": "Vector Extension Layer",
                "services": ["supabase-vector"],
                "wait_time": 10,
                "description": "Vector extension service - required by database",
            },
            {
                "layer": "Database Layer (Core Data)",
                "services": ["supabase-db"],
                "wait_time": 15,
                "description": "PostgreSQL database - everything depends on this",
            },
            {
                "layer": "Core Services Layer (Authentication & API)",
                "services": ["supabase-auth", "supabase-rest", "supabase-meta"],
                "wait_time": 5,
                "description": "Authentication, REST API, and Meta services",
            },
            {
                "layer": "Supporting Services Layer",
                "services": [
                    "supabase-analytics",
                    "supabase-storage",
                    "supabase-realtime",
                    "supabase-edge-functions",
                ],
                "wait_time": 10,
                "description": "Analytics, Storage, Real-time, and Edge Functions",
            },
            {
                "layer": "Gateway Layer (Traffic Routing)",
                "services": ["supabase-kong"],
                "wait_time": 15,
                "description": "Kong API Gateway - routes all API traffic",
            },
            {
                "layer": "Frontend Layer (User Interface)",
                "services": ["supabase-studio"],
                "wait_time": 15,
                "description": "Studio Web Interface - depends on all backend services",
            },
            {
                "layer": "Additional Services Layer",
                "services": ["supabase-imgproxy", "supabase-pooler"],
                "wait_time": 8,
                "description": "Image processing and connection pooler services",
            },
        ]

    def start_supabase_stack(self, build: bool = False) -> bool:
        """Start Supabase stack in proper dependency order"""
        console.print()

        # Build if requested
        if build:
            console.print("[green]Building Supabase images...[/green]")
            from operations.container_builder import ContainerBuilder

            builder = ContainerBuilder(self.manager)
            if not builder.build_stack_supabase():
                console.print("[red]Failed to build Supabase images[/red]")
                return False
            console.print()

        success = True
        started_services = []
        failed_services = []

        for layer in self.startup_order:
            console.print(f"[bold cyan]{layer['layer']}[/bold cyan]")
            console.print(f"[dim]{layer['description']}[/dim]")

            # Start services in this layer
            layer_success = True
            for service in layer["services"]:
                # Check if service exists before trying to start it
                if not self._service_exists(service):
                    console.print(f"[yellow]  {service} not found, skipping[/yellow]")
                    continue

                if self._start_service_with_monitoring(service):
                    console.print(f"[green]    ✓ Started {service}[/green]")
                    started_services.append(service)
                else:
                    console.print(f"[red]    ✗ Failed to start {service}[/red]")
                    failed_services.append(service)
                    layer_success = False
                    success = False

            # Wait for this layer to stabilize before starting next layer
            if layer_success and layer["services"]:
                existing_services = [
                    s for s in layer["services"] if self._service_exists(s)
                ]
                if existing_services:
                    verbose_print(f"    [cyan]exec: sleep {layer['wait_time']}[/cyan]")
                    with Progress(
                        SpinnerColumn(),
                        TextColumn(
                            f"[yellow]Waiting {layer['wait_time']}s for layer to stabilize...[/yellow]"
                        ),
                        console=console,
                        transient=True,
                    ) as progress:
                        task = progress.add_task("waiting", total=None)
                        time.sleep(layer["wait_time"])
                        progress.remove_task(task)
            elif not layer_success:
                console.print(
                    "[red]  Layer failed, continuing with next layer...[/red]"
                )

        # Summary
        if success:
            console.print(
                f"[green]✓ Successfully started Supabase stack ({len(started_services)} services)[/green]"
            )
        else:
            console.print(
                f"[yellow]⚠ Partially started Supabase stack: {len(started_services)} succeeded, {len(failed_services)} failed[/yellow]"
            )
            if started_services:
                console.print(f"[dim]  Started: {', '.join(started_services)}[/dim]")
            if failed_services:
                console.print(f"[dim]  Failed: {', '.join(failed_services)}[/dim]")
                console.print(
                    "[dim]  Run 'pm reinit <service>' for individual service analysis[/dim]"
                )
        return success

    def stop_supabase_stack(self) -> bool:
        """Stop Supabase stack in reverse dependency order"""
        console.print(
            "[green]Stopping Supabase stack in reverse dependency order...[/green]"
        )
        console.print()

        success = True
        stopped_services = []
        failed_services = []

        # Stop in reverse order
        for layer in reversed(self.startup_order):
            console.print(f"[bold cyan]Stopping {layer['layer']}[/bold cyan]")

            for service in layer["services"]:
                if not self._service_exists(service):
                    continue

                console.print(f"[green]  Stopping {service}...[/green]")
                verbose_print(f"    [cyan]exec: systemctl --user stop {service}[/cyan]")
                if self.manager.stop_service(service, quiet=True):
                    console.print(f"[green]    ✓ Stopped {service}[/green]")
                    stopped_services.append(service)
                else:
                    console.print(
                        f"[yellow]    {service} was not running or failed to stop[/yellow]"
                    )
                    failed_services.append(service)
                    success = False
            console.print()

        if success:
            console.print(
                f"[green]✓ Successfully stopped Supabase stack ({len(stopped_services)} services)[/green]"
            )
        else:
            console.print(
                f"[yellow]⚠ Partially stopped Supabase stack: {len(stopped_services)} succeeded, {len(failed_services)} failed[/yellow]"
            )
            if failed_services:
                console.print(
                    f"[dim]  Failed to stop: {', '.join(failed_services)}[/dim]"
                )

        console.print()
        return success

    def reinit_supabase_stack(self, build_type: Optional[str] = None) -> bool:
        """Reinit Supabase stack with proper startup order"""
        console.print("\n[green]Reinitializing Supabase stack...[/green]\n")

        # Step 1: Stop all services in reverse order
        console.print("[green]Step 1: Stopping all Supabase services...[/green]\n")
        self.stop_supabase_stack()

        # Step 2: Build if requested
        if build_type:
            console.print("[green]Step 2: Building Supabase images...[/green]")
            from operations.container_builder import ContainerBuilder

            builder = ContainerBuilder(self.manager)

            if build_type == "podman":
                build_success = builder.build_stack_supabase_podman()
            else:
                build_success = builder.build_stack_supabase()

            if not build_success:
                console.print("[red]Failed to build Supabase images[/red]")
                return False

        # Step 3: Reload daemon
        console.print("[green]Step 3: Reloading systemd daemon...[/green]\n")
        if not self.manager.reload_daemon():
            console.print("[red]Failed to reload systemd daemon[/red]")
            return False

        # Add delay after daemon reload
        time.sleep(3)

        # Step 4: Start services in proper order
        console.print("[green]Step 4: Starting services in dependency order...[/green]")
        return self.start_supabase_stack()

    def _service_exists(self, service_name: str) -> bool:
        """Check if a service exists in systemd"""
        try:
            # Try to find the service using the manager's resolution
            resolved_service = self.manager._find_service_name(service_name, "status")
            return resolved_service is not None and not resolved_service.startswith(
                "STACK:"
            )
        except Exception:
            return False

    def _start_service_with_monitoring(self, service_name: str) -> bool:
        """Start a service and monitor its startup"""
        # Special handling for supabase-pooler - ensure database is fully ready
        if service_name == "supabase-pooler":
            if not self._ensure_database_ready_for_pooler():
                console.print(f"    [red]Database not ready for {service_name}[/red]")
                return False

        # Use the manager's start_service method to avoid duplication
        # This handles all the service name resolution and starting logic
        success = self.manager.start_service(service_name)

        if not success:
            return False

        # Get the resolved service name for monitoring
        resolved_service = self.manager._find_service_name(service_name, "start")
        if not resolved_service or resolved_service.startswith("STACK:"):
            return False

        # Monitor startup for a short time
        return self._monitor_service_startup(service_name, resolved_service)

    def _monitor_service_startup(
        self, service_name: str, resolved_service: str, timeout: int = 10
    ) -> bool:
        """Monitor service startup with basic health checking"""
        # Wait a moment for service to start
        time.sleep(2)

        # Check if service is active
        status_cmd = ["systemctl", "--user", "is-active", resolved_service]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)

        if status_result.returncode != 0:
            verbose_print(f"    [red]Service {service_name} is not active[/red]")
            return False

        # Check for critical errors in recent logs
        logs_cmd = [
            "journalctl",
            "--user",
            "-u",
            resolved_service,
            "--since",
            "10 seconds ago",
            "-n",
            "20",
            "--no-pager",
        ]

        try:
            logs_result = subprocess.run(
                logs_cmd, capture_output=True, text=True, timeout=5
            )
            if logs_result.returncode == 0 and logs_result.stdout:
                log_content = logs_result.stdout.lower()

                # Check for critical error patterns
                critical_errors = [
                    "fatal error",
                    "critical error",
                    "startup failed",
                    "failed to start",
                    "cannot start",
                    "unable to start",
                    "bind: address already in use",
                    "permission denied",
                    "segmentation fault",
                    "panic:",
                ]

                if any(error in log_content for error in critical_errors):
                    verbose_print(
                        f"    [red]Critical errors detected in {service_name} logs[/red]"
                    )
                    return False

        except subprocess.TimeoutExpired:
            pass  # Log check timeout is not critical
        except Exception:
            pass  # Log check errors are not critical

        verbose_print(f"    [green]Service {service_name} appears healthy[/green]")
        return True

    def _show_supabase_next_steps(self):
        """Show next steps after successful Supabase stack startup"""
        console.print("[green]Next steps:[/green]")
        console.print(
            "[green]  Check stack status:[/green] [white]pm status supabase[/white]"
        )
        console.print(
            "[green]  View Studio UI:[/green] [white]http://localhost:3000[/white]"
        )
        console.print(
            "[green]  View API docs:[/green] [white]http://localhost:8000[/white]"
        )
        console.print(
            "[green]  Check individual logs:[/green] [white]pm logs supabase-db[/white]"
        )
        console.print(
            "[green]  Diagnose issues:[/green] [white]pm diagnose supabase-kong[/white]"
        )

    def get_supabase_services(self) -> List[str]:
        """Get list of all Supabase services in startup order"""
        services = []
        for layer in self.startup_order:
            services.extend(layer["services"])
        return services

    def verify_supabase_health(self) -> Dict[str, bool]:
        """Verify health of all Supabase services"""
        health_status = {}

        for service in self.get_supabase_services():
            if not self._service_exists(service):
                health_status[service] = None  # Service doesn't exist
                continue

            resolved_service = self.manager._find_service_name(service, "status")
            if not resolved_service:
                health_status[service] = False
                continue

            # Check if service is active
            status_cmd = ["systemctl", "--user", "is-active", resolved_service]
            result = subprocess.run(status_cmd, capture_output=True, text=True)
            health_status[service] = result.returncode == 0

        return health_status

    def _ensure_database_ready_for_pooler(self) -> bool:
        """Ensure database is fully ready for supabase-pooler migrations"""
        max_attempts = 12  # 60 seconds total (12 * 5s)
        attempt = 0
        database_ready = False

        with console.status(
            "[yellow]Checking database readiness for pooler...[/yellow]", spinner="dots"
        ):
            while attempt < max_attempts:
                attempt += 1
                verbose_print(
                    f"    [cyan]Database readiness check attempt {attempt}/{max_attempts}[/cyan]"
                )

                try:
                    # Check 1: Basic pg_isready check
                    pg_ready_cmd = [
                        "podman",
                        "exec",
                        "supabase-db",
                        "pg_isready",
                        "-h",
                        "localhost",
                        "-p",
                        "5432",
                        "-U",
                        "supabase_admin",
                        "-d",
                        "_supabase",
                    ]
                    verbose_print(f"    [cyan]exec: {' '.join(pg_ready_cmd)}[/cyan]")

                    pg_ready_result = subprocess.run(
                        pg_ready_cmd, capture_output=True, text=True, timeout=10
                    )

                    if pg_ready_result.returncode != 0:
                        verbose_print(
                            f"    [cyan]pg_isready failed: {pg_ready_result.stderr.strip()}[/cyan]"
                        )
                        time.sleep(5)
                        continue

                    # Check 2: Test actual database connection and query
                    db_test_cmd = [
                        "podman",
                        "exec",
                        "supabase-db",
                        "psql",
                        "postgresql://supabase_admin:Sup4b453_1969@localhost:5432/_supabase",
                        "-c",
                        "SELECT 1",
                    ]
                    verbose_print(
                        "    [cyan]exec: podman exec supabase-db psql ... -c 'SELECT 1'[/cyan]"
                    )

                    db_test_result = subprocess.run(
                        db_test_cmd, capture_output=True, text=True, timeout=10
                    )

                    if db_test_result.returncode == 0:
                        database_ready = True
                        break
                    else:
                        verbose_print(
                            f"    [cyan]Database query failed: {db_test_result.stderr.strip()}[/cyan]"
                        )

                except subprocess.TimeoutExpired:
                    verbose_print("    [cyan]Database readiness check timed out[/cyan]")
                except Exception as e:
                    verbose_print(
                        f"    [cyan]Database readiness check error: {e}[/cyan]"
                    )

                if attempt < max_attempts:
                    verbose_print(
                        f"    [cyan]Database not ready yet, waiting... (attempt {attempt}/{max_attempts})[/cyan]"
                    )
                    time.sleep(5)

        # Print result after spinner ends
        if database_ready:
            console.print("    [green]✓ Database is ready for pooler[/green]")
            return True
        else:
            console.print(
                "    [red]✗ Database failed to become ready for pooler after 60 seconds[/red]"
            )
            return False
