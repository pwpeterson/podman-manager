"""Monitoring and display functionality for reinit operations."""

import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from core.config import console


class ReinitMonitor:
    """Handles monitoring, progress display, and verification for reinit operations."""

    def __init__(self, manager, health_checker):
        self.manager = manager
        self.health_checker = health_checker

    def perform_post_reinit_verification(
        self, target: str, enable_ai_guidance: bool
    ) -> None:
        """Perform post-reinit verification and provide optimization suggestions."""
        console.print("\n[cyan]🔍 Post-reinit Verification[/cyan]")

        verification_results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]Verifying reinit success...[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("verification", total=None)

            # Wait a moment for services to stabilize
            time.sleep(3)

            # Check service status
            progress.update(
                task, description="[yellow]Checking service status...[/yellow]"
            )
            service_status = self.health_checker.verify_service_status(target)
            verification_results.append(("Service Status", service_status))

            # Check container health
            progress.update(
                task, description="[yellow]Checking container health...[/yellow]"
            )
            container_health = self.health_checker.verify_container_health(target)
            verification_results.append(("Container Health", container_health))

            # Check performance metrics
            progress.update(
                task, description="[yellow]Checking performance...[/yellow]"
            )
            # Note: This would need pre_reinit_state passed in for full functionality
            performance_check = {
                "status": "info",
                "details": "Performance baseline unavailable",
            }
            verification_results.append(("Performance", performance_check))

            # Show completion message without spinner
            progress.update(task, description="[green]Verification completed[/green]")
            time.sleep(0.5)  # Brief pause to show completion
            progress.remove_task(task)

        # Display verification results
        self._display_verification_results(verification_results)

        # Provide optimization suggestions if AI guidance is enabled
        if enable_ai_guidance:
            self._provide_optimization_suggestions(target, verification_results)

    def _display_verification_results(
        self, results: List[Tuple[str, Dict[str, str]]]
    ) -> None:
        """Display verification results."""
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Verification", style="white", width=20)
        table.add_column("Status", width=12)
        table.add_column("Details", style="dim")

        status_styles = {
            "good": "[green]✅ Good[/green]",
            "info": "[blue]ℹ️  Info[/blue]",
            "warning": "[yellow]⚠️  Warning[/yellow]",
            "error": "[red]❌ Error[/red]",
        }

        for check_name, result in results:
            status = result["status"]
            details = result["details"]
            styled_status = status_styles.get(status, f"[dim]{status}[/dim]")
            table.add_row(check_name, styled_status, details)

        console.print(table)

    def _provide_optimization_suggestions(
        self, target: str, verification_results: List
    ) -> None:
        """Provide AI-powered optimization suggestions after successful reinit."""
        console.print("\n[cyan]💡 Optimization Suggestions[/cyan]")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Run optimization analysis
            analyzer.ai_analyze(
                analysis_type="post_reinit_optimization",
                target=target,
                context_data={
                    "verification_results": verification_results,
                },
                verbose=False,
            )

        except Exception as e:
            console.print(f"[dim]Optimization suggestions unavailable: {e}[/dim]")

    def show_next_steps(self, target: str) -> None:
        """Show optional next steps after successful reinit"""
        # Common actions are now handled by the command router's try_with_fallback method
        # This method is kept for potential future use but no longer displays actions
        pass

    def execute_enhanced_reinit(
        self,
        target: str,
        build: bool,
        build_type: str | None,
        vllm_model: str | None,
        enable_ai_guidance: bool,
        reinit_func,
    ) -> bool:
        """Execute reinit with enhanced monitoring and real-time diagnostic parsing."""
        console.print("[cyan]🔄 Enhanced Reinit Execution[/cyan]")

        # Store context for potential AI analysis
        reinit_context = {
            "target": target,
            "build": build,
            "build_type": build_type,
            "vllm_model": vllm_model,
            "start_time": time.time(),
        }

        # Execute the standard reinit process with enhanced monitoring
        try:
            # Use the provided reinit function
            success = reinit_func(target, build, build_type, vllm_model)

            if not success and enable_ai_guidance:
                # Enhanced failure analysis with context
                self._run_enhanced_failure_analysis(target, reinit_context)

            return success

        except Exception as e:
            console.print(f"[red]Reinit execution failed: {e}[/red]")
            if enable_ai_guidance:
                self._run_enhanced_failure_analysis(
                    target, reinit_context, exception=str(e)
                )
            return False

    def _run_enhanced_failure_analysis(
        self, target: str, reinit_context: Dict, exception: str | None = None
    ) -> None:
        """Run enhanced AI failure analysis with reinit context."""
        console.print("\n[red]🔍 Enhanced Failure Analysis[/red]")
        console.print("[dim]Analyzing reinit failure with full context...[/dim]\n")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Prepare enhanced context data
            context_data = {
                "reinit_context": reinit_context,
            }

            if exception:
                context_data["exception"] = {"error": exception}

            # Run enhanced AI analysis
            analyzer.ai_analyze(
                analysis_type="enhanced_reinit_failure",
                target=target,
                context_data=context_data,
                verbose=True,
            )

        except Exception as e:
            console.print(f"[yellow]Enhanced failure analysis failed: {e}[/yellow]")

    def run_pre_reinit_ai_analysis(self, target: str, pre_reinit_state: Dict) -> None:
        """Run AI analysis before reinit to identify potential issues."""
        console.print("\n[green]🤖 Pre-reinit AI Analysis[/green]")
        console.print("[dim]Analyzing potential issues before reinit...[/dim]\n")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Run AI analysis with pre-reinit context
            analyzer.ai_analyze(
                analysis_type="pre_reinit_check",
                target=target,
                context_data={
                    "health_check_failed": True,
                    "pre_reinit_state": pre_reinit_state,
                },
                verbose=True,
            )

        except Exception as e:
            console.print(f"[yellow]Pre-reinit AI analysis failed: {e}[/yellow]")

    def monitor_service_stopping(self, target: str, timeout: int = 30) -> bool:
        """Monitor a service during the stopping process with real-time feedback."""
        console.print(f"[yellow]🛑 Monitoring service stopping: {target}[/yellow]")

        service_name = self.manager._find_service_name(target)
        if not service_name or service_name.startswith("STACK:"):
            service_name = target

        start_time = time.time()

        # Create a live display for real-time monitoring
        with Live(
            self._create_stopping_status_panel(service_name, "Initiating stop...", 0),
            console=console,
            refresh_per_second=2,
        ) as live:

            while time.time() - start_time < timeout:
                try:
                    # Check service status
                    status_info = self._get_service_stopping_status(service_name)
                    elapsed = time.time() - start_time

                    # Update the live display
                    live.update(
                        self._create_stopping_status_panel(
                            service_name, status_info["status"], elapsed, status_info
                        )
                    )

                    # Check if service has stopped
                    if status_info["stopped"]:
                        console.print(
                            f"[green]✅ Service {service_name} stopped successfully in {elapsed:.1f}s[/green]"
                        )
                        return True

                    # Check if service is stuck
                    if status_info["stuck"]:
                        console.print(
                            f"[red]⚠️  Service {service_name} appears stuck during stopping[/red]"
                        )
                        return False

                    time.sleep(0.5)  # Check every 500ms

                except Exception as e:
                    console.print(f"[red]Error monitoring service stopping: {e}[/red]")
                    return False

        # Timeout reached
        console.print(
            f"[red]⏰ Timeout reached waiting for {service_name} to stop[/red]"
        )
        return False

    def _get_service_stopping_status(self, service_name: str) -> Dict[str, Any]:
        """Get detailed status of a service during stopping process."""
        try:
            # Check systemctl status
            result = subprocess.run(
                ["systemctl", "--user", "status", service_name],
                capture_output=True,
                text=True,
                timeout=5,
            )

            status_output = result.stdout.lower()

            # Determine current state
            if "inactive (dead)" in status_output:
                return {
                    "status": "Stopped",
                    "stopped": True,
                    "stuck": False,
                    "details": "Service successfully stopped",
                }
            elif "deactivating" in status_output:
                return {
                    "status": "Deactivating",
                    "stopped": False,
                    "stuck": False,
                    "details": "Service is deactivating",
                }
            elif "stop-sigterm" in status_output:
                return {
                    "status": "Sending SIGTERM",
                    "stopped": False,
                    "stuck": False,
                    "details": "Graceful shutdown in progress",
                }
            elif "stop-sigkill" in status_output:
                return {
                    "status": "Sending SIGKILL",
                    "stopped": False,
                    "stuck": True,
                    "details": "Force killing service",
                }
            elif "active (running)" in status_output:
                return {
                    "status": "Still Running",
                    "stopped": False,
                    "stuck": False,
                    "details": "Service still active",
                }
            elif "failed" in status_output:
                return {
                    "status": "Failed",
                    "stopped": True,
                    "stuck": False,
                    "details": "Service failed during stop",
                }
            else:
                return {
                    "status": "Unknown State",
                    "stopped": False,
                    "stuck": False,
                    "details": "Unable to determine state",
                }

        except subprocess.TimeoutExpired:
            return {
                "status": "Status Check Timeout",
                "stopped": False,
                "stuck": True,
                "details": "systemctl command timed out",
            }
        except Exception as e:
            return {
                "status": "Error",
                "stopped": False,
                "stuck": False,
                "details": f"Status check failed: {str(e)[:50]}...",
            }

    def _create_stopping_status_panel(
        self,
        service_name: str,
        status: str,
        elapsed: float,
        status_info: Optional[Dict] = None,
    ) -> Panel:
        """Create a rich panel showing service stopping status."""

        # Create status content
        content_lines = [
            f"Service: [bold cyan]{service_name}[/bold cyan]",
            f"Status: [yellow]{status}[/yellow]",
            f"Elapsed: [dim]{elapsed:.1f}s[/dim]",
        ]

        if status_info and "details" in status_info:
            content_lines.append(f"Details: [dim]{status_info['details']}[/dim]")

        # Add progress indicators based on status
        if status_info:
            if status_info["stopped"]:
                content_lines.append("[green]✅ Service stopped[/green]")
            elif status_info["stuck"]:
                content_lines.append("[red]⚠️  Service appears stuck[/red]")
            else:
                content_lines.append("[yellow]⏳ Stopping in progress...[/yellow]")

        content = "\n".join(content_lines)

        return Panel(
            content,
            title="[bold]Service Stopping Monitor[/bold]",
            border_style="yellow",
            padding=(1, 2),
        )

    def monitor_container_stopping(self, target: str, timeout: int = 30) -> bool:
        """Monitor container during stopping process."""
        console.print(f"[yellow]🐳 Monitoring container stopping: {target}[/yellow]")

        try:
            from core.simple_fuzzy_matcher import find_container

            container = find_container(target)

            if not container:
                console.print(f"[red]Container not found for {target}[/red]")
                return False

            container_name = container["name"]
            start_time = time.time()

            with Live(
                self._create_container_stopping_panel(
                    container_name, "Initiating stop...", 0
                ),
                console=console,
                refresh_per_second=2,
            ) as live:

                while time.time() - start_time < timeout:
                    try:
                        # Check container status
                        result = subprocess.run(
                            [
                                "podman",
                                "ps",
                                "-a",
                                "--format",
                                "{{.Names}} {{.Status}}",
                                "--filter",
                                f"name={container_name}",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )

                        elapsed = time.time() - start_time

                        if result.returncode == 0 and result.stdout.strip():
                            status_line = result.stdout.strip()

                            if "Exited" in status_line:
                                console.print(
                                    f"[green]✅ Container {container_name} stopped in {elapsed:.1f}s[/green]"
                                )
                                return True
                            elif "Up" in status_line:
                                live.update(
                                    self._create_container_stopping_panel(
                                        container_name, "Still running", elapsed
                                    )
                                )
                            else:
                                live.update(
                                    self._create_container_stopping_panel(
                                        container_name, "Stopping", elapsed
                                    )
                                )
                        else:
                            console.print(
                                f"[green]✅ Container {container_name} stopped (not found in ps)[/green]"
                            )
                            return True

                        time.sleep(0.5)

                    except Exception as e:
                        console.print(f"[red]Error monitoring container: {e}[/red]")
                        return False

            console.print(
                f"[red]⏰ Timeout waiting for container {container_name} to stop[/red]"
            )
            return False

        except Exception as e:
            console.print(f"[red]Error setting up container monitoring: {e}[/red]")
            return False

    def _create_container_stopping_panel(
        self, container_name: str, status: str, elapsed: float
    ) -> Panel:
        """Create a rich panel showing container stopping status."""

        content = "\n".join(
            [
                f"Container: [bold cyan]{container_name}[/bold cyan]",
                f"Status: [yellow]{status}[/yellow]",
                f"Elapsed: [dim]{elapsed:.1f}s[/dim]",
                "[yellow]⏳ Stopping in progress...[/yellow]",
            ]
        )

        return Panel(
            content,
            title="[bold]Container Stopping Monitor[/bold]",
            border_style="blue",
            padding=(1, 2),
        )
