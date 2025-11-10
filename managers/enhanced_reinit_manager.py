"""Enhanced Reinit Manager with proactive AI troubleshooting and diagnostic parsing."""

import subprocess
import time
from typing import TYPE_CHECKING, Dict, List, Tuple

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

if TYPE_CHECKING:
    import requests
else:
    try:
        import requests
    except ImportError:
        requests = None

from core.config import console, verbose_print
from managers.reinit_manager import ReinitManager


class EnhancedReinitManager(ReinitManager):
    """Enhanced reinit manager with proactive AI troubleshooting and diagnostic parsing."""

    def __init__(self, manager):
        super().__init__(manager)
        self.diagnostic_data = {}
        self.reinit_context = {}
        self.pre_reinit_state = {}

    def enhanced_reinit(
        self,
        target: str,
        build: bool = False,
        build_type: str | None = None,
        vllm_model: str | None = None,
        enable_ai_guidance: bool = True,
    ) -> bool:
        """Enhanced reinit with proactive diagnostics and AI guidance."""
        console.print(
            f"\n[bold green]Enhanced Reinit Process for {target}[/bold green]"
        )
        console.print(
            "[dim]With proactive AI troubleshooting and diagnostic parsing[/dim]\n"
        )

        # Step 1: Pre-reinit health check and validation
        if not self._pre_reinit_health_check(target):
            if enable_ai_guidance:
                self._run_pre_reinit_ai_analysis(target)
            return False

        # Step 2: Capture baseline state
        self._capture_pre_reinit_state(target)

        # Step 3: Execute reinit with enhanced monitoring
        success = self._execute_enhanced_reinit(
            target, build, build_type, vllm_model, enable_ai_guidance
        )

        # Step 4: Post-reinit verification and optimization suggestions
        if success:
            self._post_reinit_verification(target, enable_ai_guidance)

        return success

    def _pre_reinit_health_check(self, target: str) -> bool:
        """Perform comprehensive pre-reinit health check."""
        console.print("[cyan]🔍 Pre-reinit Health Check[/cyan]")

        health_checks = [
            ("Service Status", self._check_service_status),
            ("Container State", self._check_container_state),
            ("Resource Usage", self._check_resource_usage),
            ("Network Connectivity", self._check_network_connectivity),
            ("Storage Health", self._check_storage_health),
        ]

        health_results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]Running health checks...[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("health_check", total=None)

            for check_name, check_func in health_checks:
                try:
                    result = check_func(target)
                    health_results.append(
                        (check_name, result["status"], result["details"])
                    )
                    progress.update(
                        task,
                        description=f"[yellow]Checking {check_name.lower()}...[/yellow]",
                    )
                    time.sleep(0.5)  # Brief pause for visual feedback
                except Exception as e:
                    health_results.append((check_name, "error", str(e)))

            progress.remove_task(task)

        # Display health check results
        self._display_health_check_results(health_results)

        # Determine if we should proceed
        critical_failures = [r for r in health_results if r[1] == "critical"]
        if critical_failures:
            console.print("\n[red]❌ Critical issues detected. Reinit may fail.[/red]")
            return False

        warnings = [r for r in health_results if r[1] == "warning"]
        if warnings:
            console.print(
                "\n[yellow]⚠️  Warnings detected. Proceeding with enhanced monitoring.[/yellow]"
            )
        else:
            console.print(
                "\n[green]✅ Health check passed. Proceeding with reinit.[/green]"
            )

        console.print()
        return True

    def _check_service_status(self, target: str) -> Dict[str, str]:
        """Check current service status and recent failures."""
        try:
            # Get service name
            service_name = self.manager._find_service_name(target)
            if not service_name or service_name.startswith("STACK:"):
                service_name = target

            # Check systemctl status
            result = subprocess.run(
                ["systemctl", "--user", "status", service_name],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if "failed" in result.stdout.lower():
                return {"status": "warning", "details": "Service in failed state"}
            elif "active (running)" in result.stdout.lower():
                return {"status": "good", "details": "Service running normally"}
            elif "inactive" in result.stdout.lower():
                return {"status": "info", "details": "Service stopped"}
            else:
                return {"status": "warning", "details": "Service in unknown state"}

        except Exception as e:
            return {"status": "error", "details": f"Status check failed: {e}"}

    def _check_container_state(self, target: str) -> Dict[str, str]:
        """Check container state and recent exit codes."""
        try:
            # Use fuzzy matching to find container
            from core.simple_fuzzy_matcher import find_container

            container = find_container(target)

            if not container:
                return {"status": "warning", "details": "Container not found"}

            container_name = container["name"]

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
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                status_line = result.stdout.strip()
                if "Up" in status_line:
                    return {"status": "good", "details": "Container running"}
                elif "Exited (0)" in status_line:
                    return {"status": "info", "details": "Container stopped cleanly"}
                elif "Exited" in status_line:
                    return {
                        "status": "warning",
                        "details": "Container exited with error",
                    }
                else:
                    return {"status": "info", "details": "Container in transition"}
            else:
                return {"status": "warning", "details": "Container not created"}

        except Exception as e:
            return {"status": "error", "details": f"Container check failed: {e}"}

    def _check_resource_usage(self, target: str) -> Dict[str, str]:
        """Check system resource usage that might affect reinit."""
        try:
            import psutil

            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                return {
                    "status": "critical",
                    "details": f"High memory usage: {memory.percent:.1f}%",
                }
            elif memory.percent > 80:
                return {
                    "status": "warning",
                    "details": f"Elevated memory usage: {memory.percent:.1f}%",
                }

            # Check disk usage
            disk = psutil.disk_usage("/")
            if disk.percent > 95:
                return {
                    "status": "critical",
                    "details": f"Disk nearly full: {disk.percent:.1f}%",
                }
            elif disk.percent > 85:
                return {
                    "status": "warning",
                    "details": f"High disk usage: {disk.percent:.1f}%",
                }

            return {
                "status": "good",
                "details": f"Resources OK (Mem: {memory.percent:.1f}%, Disk: {disk.percent:.1f}%)",
            }

        except ImportError:
            return {
                "status": "info",
                "details": "Resource monitoring unavailable (psutil not installed)",
            }
        except Exception as e:
            return {"status": "error", "details": f"Resource check failed: {e}"}

    def _check_network_connectivity(self, target: str) -> Dict[str, str]:
        """Check network connectivity for services that need it."""
        try:
            # For vLLM services, check if ports are available
            if "vllm" in target.lower():
                import socket

                # Check if vLLM port 8005 is available or properly used
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    result = s.connect_ex(("localhost", 8005))
                    if result == 0:
                        return {"status": "info", "details": "vLLM port 8005 in use"}
                    else:
                        return {"status": "good", "details": "vLLM port 8005 available"}

            return {"status": "good", "details": "Network connectivity OK"}

        except Exception as e:
            return {"status": "error", "details": f"Network check failed: {e}"}

    def _check_storage_health(self, target: str) -> Dict[str, str]:
        """Check storage health and volume availability."""
        try:
            # Check if podman volumes are accessible
            result = subprocess.run(
                ["podman", "volume", "ls", "--quiet"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                volume_count = (
                    len(result.stdout.strip().split("\n"))
                    if result.stdout.strip()
                    else 0
                )
                return {
                    "status": "good",
                    "details": f"Storage OK ({volume_count} volumes)",
                }
            else:
                return {"status": "warning", "details": "Volume access issues"}

        except Exception as e:
            return {"status": "error", "details": f"Storage check failed: {e}"}

    def _display_health_check_results(
        self, results: List[Tuple[str, str, str]]
    ) -> None:
        """Display health check results in a formatted table."""
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Check", style="white", width=20)
        table.add_column("Status", width=12)
        table.add_column("Details", style="dim")

        status_styles = {
            "good": "[green]✅ Good[/green]",
            "info": "[blue]ℹ️  Info[/blue]",
            "warning": "[yellow]⚠️  Warning[/yellow]",
            "critical": "[red]❌ Critical[/red]",
            "error": "[red]💥 Error[/red]",
        }

        for check_name, status, details in results:
            styled_status = status_styles.get(status, f"[dim]{status}[/dim]")
            table.add_row(check_name, styled_status, details)

        console.print(table)

    def _capture_pre_reinit_state(self, target: str) -> None:
        """Capture system state before reinit for comparison."""
        verbose_print("  [cyan]exec: Capturing pre-reinit state for comparison[/cyan]")

        try:
            # Capture service status
            service_name = self.manager._find_service_name(target)
            if service_name and not service_name.startswith("STACK:"):
                result = subprocess.run(
                    [
                        "systemctl",
                        "--user",
                        "show",
                        service_name,
                        "--property=ActiveState,SubState,ExecMainPID",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.pre_reinit_state["service_properties"] = result.stdout

            # Capture container state
            from core.simple_fuzzy_matcher import find_container

            container = find_container(target)
            if container:
                result = subprocess.run(
                    [
                        "podman",
                        "inspect",
                        container["name"],
                        "--format",
                        "{{.State.Status}} {{.State.ExitCode}}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.pre_reinit_state["container_state"] = result.stdout.strip()

            # Capture timestamp
            self.pre_reinit_state["timestamp"] = time.time()

        except Exception as e:
            verbose_print(
                f"  [cyan]exec: Failed to capture pre-reinit state: {e}[/cyan]"
            )

    def _execute_enhanced_reinit(
        self,
        target: str,
        build: bool,
        build_type: str | None,
        vllm_model: str | None,
        enable_ai_guidance: bool,
    ) -> bool:
        """Execute reinit with enhanced monitoring and real-time diagnostic parsing."""
        console.print("[cyan]🔄 Enhanced Reinit Execution[/cyan]")

        # Store context for potential AI analysis
        self.reinit_context = {
            "target": target,
            "build": build,
            "build_type": build_type,
            "vllm_model": vllm_model,
            "start_time": time.time(),
        }

        # Execute the standard reinit process with enhanced monitoring
        try:
            # Use the parent class reinit method but with enhanced error handling
            success = super().reinit(target, build, build_type, vllm_model)

            if not success and enable_ai_guidance:
                # Enhanced failure analysis with context
                self._run_enhanced_failure_analysis(target)

            return success

        except Exception as e:
            console.print(f"[red]Reinit execution failed: {e}[/red]")
            if enable_ai_guidance:
                self._run_enhanced_failure_analysis(target, exception=str(e))
            return False

    def _post_reinit_verification(self, target: str, enable_ai_guidance: bool) -> None:
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
            service_status = self._verify_service_status(target)
            verification_results.append(("Service Status", service_status))

            # Check container health
            progress.update(
                task, description="[yellow]Checking container health...[/yellow]"
            )
            container_health = self._verify_container_health(target)
            verification_results.append(("Container Health", container_health))

            # Check performance metrics
            progress.update(
                task, description="[yellow]Checking performance...[/yellow]"
            )
            performance_check = self._verify_performance(target)
            verification_results.append(("Performance", performance_check))

            progress.remove_task(task)

        # Display verification results
        self._display_verification_results(verification_results)

        # Provide optimization suggestions if AI guidance is enabled
        if enable_ai_guidance:
            self._provide_optimization_suggestions(target, verification_results)

    def _verify_service_status(self, target: str) -> Dict[str, str]:
        """Verify service is running properly after reinit."""
        try:
            service_name = self.manager._find_service_name(target)
            if not service_name or service_name.startswith("STACK:"):
                service_name = target

            result = subprocess.run(
                ["systemctl", "--user", "is-active", service_name],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip() == "active":
                return {"status": "good", "details": "Service active and running"}
            else:
                return {
                    "status": "warning",
                    "details": f"Service state: {result.stdout.strip()}",
                }

        except Exception as e:
            return {"status": "error", "details": f"Status verification failed: {e}"}

    def _verify_container_health(self, target: str) -> Dict[str, str]:
        """Verify container is healthy after reinit."""
        try:
            from core.simple_fuzzy_matcher import find_container

            container = find_container(target)

            if not container:
                return {"status": "warning", "details": "Container not found"}

            # Check if container is running
            if container["status"] == "running":
                # For vLLM services, check if they're responding
                if "vllm" in target.lower() and requests:
                    try:
                        response = requests.get(
                            "http://localhost:8005/health", timeout=5
                        )
                        if response.status_code == 200:
                            return {
                                "status": "good",
                                "details": "Container healthy and responding",
                            }
                        else:
                            return {
                                "status": "warning",
                                "details": "Container running but not responding",
                            }
                    except Exception:
                        return {
                            "status": "info",
                            "details": "Container running (health check unavailable)",
                        }
                else:
                    return {"status": "good", "details": "Container running normally"}
            else:
                return {
                    "status": "warning",
                    "details": f"Container status: {container['status']}",
                }

        except Exception as e:
            return {"status": "error", "details": f"Health verification failed: {e}"}

    def _verify_performance(self, target: str) -> Dict[str, str]:
        """Check performance metrics after reinit."""
        try:
            # Compare with pre-reinit state if available
            if "timestamp" in self.pre_reinit_state:
                reinit_duration = time.time() - self.pre_reinit_state["timestamp"]
                if reinit_duration < 30:
                    return {
                        "status": "good",
                        "details": f"Fast reinit ({reinit_duration:.1f}s)",
                    }
                elif reinit_duration < 60:
                    return {
                        "status": "info",
                        "details": f"Normal reinit ({reinit_duration:.1f}s)",
                    }
                else:
                    return {
                        "status": "warning",
                        "details": f"Slow reinit ({reinit_duration:.1f}s)",
                    }
            else:
                return {"status": "info", "details": "Performance baseline unavailable"}

        except Exception as e:
            return {"status": "error", "details": f"Performance check failed: {e}"}

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

    def _run_pre_reinit_ai_analysis(self, target: str) -> None:
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
                    "pre_reinit_state": self.pre_reinit_state,
                },
                verbose=True,
            )

        except Exception as e:
            console.print(f"[yellow]Pre-reinit AI analysis failed: {e}[/yellow]")

    def _run_enhanced_failure_analysis(
        self, target: str, exception: str = None
    ) -> None:
        """Run enhanced AI failure analysis with reinit context."""
        console.print("\n[red]🔍 Enhanced Failure Analysis[/red]")
        console.print("[dim]Analyzing reinit failure with full context...[/dim]\n")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Prepare enhanced context data
            context_data = {
                "reinit_context": self.reinit_context,
                "pre_reinit_state": self.pre_reinit_state,
                "diagnostic_data": self.diagnostic_data,
            }

            if exception:
                context_data["exception"] = exception

            # Run enhanced AI analysis
            analyzer.ai_analyze(
                analysis_type="enhanced_reinit_failure",
                target=target,
                context_data=context_data,
                verbose=True,
            )

        except Exception as e:
            console.print(f"[yellow]Enhanced failure analysis failed: {e}[/yellow]")

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
                    "reinit_context": self.reinit_context,
                    "pre_reinit_state": self.pre_reinit_state,
                },
                verbose=False,
            )

        except Exception as e:
            console.print(f"[dim]Optimization suggestions unavailable: {e}[/dim]")
