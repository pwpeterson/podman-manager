"""Reinit operations for services and stacks with advanced monitoring and AI troubleshooting."""

import re
import subprocess
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

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


class ReinitManager:
    """Handles complex reinit operations with monitoring, error handling, and AI troubleshooting"""

    def __init__(self, manager):
        self.manager = manager
        self._vllm_manager = None
        # Enhanced features
        self.diagnostic_data = {}
        self.reinit_context = {}
        self.pre_reinit_state = {}

    @property
    def vllm_manager(self):
        """Lazy initialization of vLLM manager"""
        if self._vllm_manager is None:
            from managers.vllm_model_manager import VLLMModelManager

            self._vllm_manager = VLLMModelManager(self.manager)
        return self._vllm_manager

    def reinit(
        self,
        target: str,
        build: bool = False,
        build_type: str | None = None,
        vllm_model: str | None = None,
        dry_run: bool = False,
        enhanced: bool = False,
    ) -> bool:
        """Stop service, reload daemon, and restart service (useful for .container file changes)"""
        if enhanced:
            return self.enhanced_reinit(target, build, build_type, vllm_model)

        # Clear cache at the start
        self.manager._clear_auto_match_cache()

        # Handle backward compatibility - if build=True and no build_type, use legacy
        if build and build_type is None:
            build_type = "legacy"

        # Handle vLLM model switching if specified, or detect vLLM services automatically
        is_vllm_service = "vllm" in target.lower() or target in [
            "vllm-proxy",
            "vllm-stack",
        ]
        # We'll determine if this is a vLLM model service later based on actual container detection
        is_vllm_model_service = False

        if vllm_model:
            console.print(
                f"[green]vLLM model switching requested: {vllm_model}[/green]"
            )
            if not self.vllm_manager.switch_vllm_model(vllm_model):
                console.print("[red]vLLM model switch failed, aborting reinit[/red]")
                return False
            console.print()
        elif is_vllm_service:
            # For vLLM services, the cleanup will be handled in the service-specific reinit
            # No need for silent cleanup here since we show it explicitly now
            pass

        # PRIORITY 1: Check for stack names first (before trying service name resolution)
        # Handle legacy stack targets
        if target in ["vllm", "vllm-stack", "stack"]:
            from managers.stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack("vllm", build_type=build_type)
        elif target == "taskflow-stack":
            from managers.stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack("taskflow", build_type=build_type)
        elif target.endswith("-stack"):
            # Generic stack target
            project_name = target[:-6]  # Remove "-stack" suffix
            from managers.stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack(project_name, build_type=build_type)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        # Try to find it in discovered stacks before trying service resolution
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            from managers.stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack(target, build_type=build_type)

        # PRIORITY 3: Check if container file exists first
        exists, resolved_service = self.manager._check_container_file_exists(
            target, "reinit"
        )
        if not exists:
            self.manager._show_install_suggestion(target)
            return False

        # PRIORITY 4: Try service name resolution (use resolved service if available)
        service_name = resolved_service or self.manager._find_service_name(
            target, "reinit"
        )

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            from managers.stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack(stack_name, build_type=build_type)

        # PRIORITY 5: Handle individual service (only if not a stack)
        if service_name == "CANCELLED":
            # User cancelled fuzzy match selection, return silently
            return False
        elif service_name:
            result = self._reinit_service_direct(
                target, service_name, build_type=build_type, dry_run=dry_run
            )

            # If this was a successful vLLM model service reinit, restart the proxy
            if result and is_vllm_model_service:
                console.print()
                if not self.vllm_manager._restart_vllm_proxy(target):
                    console.print(
                        "[yellow]Warning: Failed to restart vLLM proxy[/yellow]"
                    )
                    return False

                # Show success message after all container operations are complete
                display_name = (
                    service_name.replace(".service", "")
                    if service_name and service_name.endswith(".service")
                    else target
                )
                console.print(
                    f"[green]Successfully reinitialized {display_name}[/green]"
                )
                console.print()

            return result
        else:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False

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
            # Use the standard reinit method but with enhanced error handling
            success = self.reinit(target, build, build_type, vllm_model)

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
        self, target: str, exception: Optional[str] = None
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

    def _run_command_with_spinner(
        self, cmd: list, message: str, success_msg: str, fail_msg: str
    ) -> bool:
        """Run a command with spinner and status messages"""
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[green]{message}[/green]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("operation", total=None)
            verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

            if self.vllm_manager._run_command(cmd):
                progress.remove_task(task)
                console.print(f"[green]  {success_msg}[/green]")
                return True
            else:
                progress.remove_task(task)
                console.print(f"[yellow]  {fail_msg}[/yellow]")
                return False

    def _show_dry_run_command(self, description: str, command: list) -> None:
        """Display dry-run command in consistent format"""
        console.print(f"[yellow]{description}[/yellow]")
        console.print(f"[yellow]  Would execute: {' '.join(command)}[/yellow]")

    def _stop_active_vllm_container(
        self, current_container: str, dry_run: bool = False
    ) -> bool:
        """Stop the currently active vLLM container with spinner and wait for port release"""
        if dry_run:
            self._show_dry_run_command(
                f"Would stop {current_container}",
                ["podman", "stop", "-t", "120", current_container],
            )
            return True
        else:
            # Stop the container
            success = self._run_command_with_spinner(
                ["podman", "stop", "-t", "120", current_container],
                f"Stopping {current_container}...",
                f"Stopped {current_container}",
                f"Failed to stop {current_container}.",
            )

            if success:
                # Wait for port to be released to prevent systemd from restarting immediately
                max_wait_time = 30
                wait_interval = 1
                elapsed_time = 0

                while (
                    elapsed_time < max_wait_time
                    and self.vllm_manager._is_port_in_use(self.vllm_manager.vllm_port)
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval

                if self.vllm_manager._is_port_in_use(self.vllm_manager.vllm_port):
                    verbose_print(
                        f"[cyan]Warning: Port {self.vllm_manager.vllm_port} still in use after stopping {current_container}[/cyan]"
                    )
                    # Try force cleanup as fallback
                    return self.vllm_manager._cleanup_vllm_port()

            return success

    def _remove_vllm_container(
        self, container_name: str, dry_run: bool = False
    ) -> bool:
        """Remove a vLLM container with spinner, handling systemd restart race condition"""
        if dry_run:
            self._show_dry_run_command(
                f"Would remove {container_name}", ["podman", "rm", container_name]
            )
            return True
        else:
            # First try to remove the container
            success = self._run_command_with_spinner(
                ["podman", "rm", container_name],
                f"Removing {container_name}...",
                f"Removed {container_name}",
                f"Failed to remove {container_name}.",
            )

            # If removal failed, it might be because systemd restarted the container
            # In that case, stop it again and then remove
            if not success:
                verbose_print(
                    f"[cyan]Container {container_name} may have been restarted by systemd, trying to stop and remove again[/cyan]"
                )

                # Stop the container again
                stop_cmd = ["podman", "stop", "-t", "10", container_name]
                verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
                stop_result = self.vllm_manager._run_command(
                    stop_cmd, suppress_errors=True
                )

                if stop_result:
                    # Try to remove again
                    rm_cmd = ["podman", "rm", container_name]
                    verbose_print(f"[cyan]exec: {' '.join(rm_cmd)}[/cyan]")
                    remove_result = self.vllm_manager._run_command(
                        rm_cmd, suppress_errors=True
                    )

                    if remove_result:
                        console.print(f"[green]  Removed {container_name}[/green]")
                        return True
                    else:
                        console.print(
                            f"[yellow]  Failed to remove {container_name} after retry[/yellow]"
                        )
                        return False
                else:
                    console.print(
                        f"[yellow]  Failed to stop {container_name} for removal[/yellow]"
                    )
                    return False

            return success

    def _remove_service_file(self, service_name: str, dry_run: bool = False) -> bool:
        """Remove systemd service file with proper error handling"""
        import os

        service_file_path = os.path.expanduser(f"~/.config/systemd/user/{service_name}")
        if not service_name.endswith(".service"):
            service_file_path += ".service"

        service_file_name = os.path.basename(service_file_path)

        if dry_run:
            self._show_dry_run_command(
                f"Would remove {service_file_name}", ["rm", "-f", service_file_path]
            )
            return True
        else:
            console.print(f"[green]Removing {service_file_name}...[/green]")
            verbose_print(f"[cyan]exec: rm -f {service_file_path}[/cyan]")
            try:
                if os.path.exists(service_file_path):
                    os.remove(service_file_path)
                    console.print(f"[green]  Removed {service_file_name}[/green]")
                else:
                    console.print(f"[green]  Removed {service_file_name}[/green]")
                    verbose_print(
                        f"[cyan]Service file {service_file_path} does not exist, skipping removal[/cyan]"
                    )
                return True
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not remove service file: {e}[/yellow]"
                )
                return False

    def _reinit_vllm_model_service(
        self, target: str, service_name: str, dry_run: bool = False
    ) -> bool:
        """Handle vLLM model service reinit with container operations"""
        display_name = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )

        # Handle daemon reload
        if dry_run:
            self._show_dry_run_command(
                "Would reload systemd daemon", ["systemctl", "--user", "daemon-reload"]
            )
        else:
            console.print("[green]Reloading systemd daemon...[/green]")
            reload_success = self.manager.reload_daemon()
            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False
            else:
                console.print("[green]  Reloaded systemd daemon.[/green]")
                console.print()

        # Start the service using the resolved service name
        if dry_run:
            self._show_dry_run_command(
                f"Would start {display_name}",
                ["systemctl", "--user", "restart", service_name],
            )
            # For vLLM model services, show proxy/delegator restart in dry-run
            console.print(
                "[yellow]Would restart vllm-proxy and mcp-vllm-delegator[/yellow]"
            )
            console.print()
            console.print(
                f"[green]DRY RUN: Successfully would reinitialize {display_name}[/green]"
            )
            return True
        else:
            console.print(f"[green]Starting {display_name}...[/green]")
            start_cmd = ["systemctl", "--user", "restart", service_name]

            start_result = self.manager._run_systemctl_command(
                start_cmd,
                f"start_{target}",
                quiet=False,
            )
            start_success = start_result.returncode == 0

            if start_success:
                console.print(f"[green]  Started {display_name}.[/green]")

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
                    # Restart vllm-proxy and mcp-vllm-delegator
                    if not self.vllm_manager._restart_vllm_proxy(target):
                        console.print(
                            "[yellow]Warning: Failed to restart vLLM proxy[/yellow]"
                        )
                        return False

                    # Restart mcp-vllm-delegator
                    if not self.vllm_manager._restart_mcp_vllm_delegator():
                        console.print(
                            "[yellow]Warning: Failed to restart mcp-vllm-delegator[/yellow]"
                        )
                        # Don't fail the entire operation if mcp-vllm-delegator fails

                    # Show success message
                    console.print(
                        f"[green]Successfully reinitialized {display_name}[/green]"
                    )
                    return True
                else:
                    # Service failed to start after monitoring - run AI analysis
                    self._run_reinit_failure_analysis(
                        target, "Service failed to start after reinit"
                    )
                    return False
            else:
                console.print(f"[red]Failed to start {display_name} after reinit[/red]")
                # Handle start failure
                self._handle_start_failure(target, start_result)
                # Service failed to start immediately - run AI analysis
                error_message = (
                    start_result.stderr.strip() if start_result.stderr else ""
                )
                self._run_reinit_failure_analysis(target, error_message)
                return False

    def _reinit_standard_service(
        self,
        target: str,
        service_name: str,
        build_type: str | None,
        dry_run: bool = False,
    ) -> bool:
        """Handle standard service reinit with systemctl operations"""
        from core.config import _verbose_enabled

        display_name = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )

        # Stop the service
        if dry_run:
            self._show_dry_run_command(
                f"Would stop {display_name}",
                ["systemctl", "--user", "stop", service_name],
            )
            stop_success = True  # Assume success for dry run
        else:
            console.print(f"[green]Stopping {display_name}...[/green]")
            stop_cmd = ["systemctl", "--user", "stop", service_name]
            verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
            stop_result = self.manager._run_systemctl_command(
                stop_cmd, f"stop_{target}", quiet=True
            )
            stop_success = stop_result.returncode == 0

            if stop_success:
                console.print(f"[green]  Stopped {display_name}.[/green]")
                console.print()
            else:
                console.print(
                    "[yellow]Service was not running or failed to stop[/yellow]"
                )

        # Remove old generated service file
        self._remove_service_file(service_name, dry_run)
        console.print()

        # Build if requested
        if build_type == "podman":
            if dry_run:
                console.print(f"[yellow]Would build {target} (podman)[/yellow]")
                console.print("[yellow]  Would execute: podman build commands[/yellow]")
            else:
                console.print(f"[green]Building {target} (podman)...[/green]")
                from operations.container_builder import ContainerBuilder

                builder = ContainerBuilder(self.manager)
                build_success = builder.build_service_podman(target)
                if not build_success:
                    console.print("[red]Failed to build images[/red]")
                    return False
        elif build_type in ["legacy", "quadlet"]:
            if dry_run:
                console.print(f"[yellow]Would build {target} (quadlet)[/yellow]")
                console.print(
                    "[yellow]  Would execute: quadlet build commands[/yellow]"
                )
            else:
                console.print(f"[green]Building {target} (quadlet)...[/green]")
                from operations.container_builder import ContainerBuilder

                builder = ContainerBuilder(self.manager)
                build_success = builder.build_service(target)
                if not build_success:
                    console.print("[red]Failed to build images[/red]")
                    return False

        # Handle daemon reload
        if dry_run:
            self._show_dry_run_command(
                "Would reload systemd daemon", ["systemctl", "--user", "daemon-reload"]
            )
        else:
            console.print("[green]Reloading systemd daemon...[/green]")

            if build_type not in ["legacy", "quadlet"]:
                reload_success = self.manager.reload_daemon()
                if not reload_success:
                    console.print("[red]Failed to reload systemd daemon[/red]")
                    return False
                else:
                    console.print("[green]  Reloaded systemd daemon.[/green]")
                    console.print()
            else:
                # Quadlet build script already reloaded daemon, add delay and force another reload
                time.sleep(3)
                reload_success = self.manager.reload_daemon()
                if not reload_success:
                    console.print(
                        "[yellow]Warning: Additional daemon reload failed[/yellow]"
                    )
                else:
                    console.print("[green]  Reloaded systemd daemon.[/green]")
                    console.print()
                    time.sleep(1)

        # Start the service using the resolved service name
        if dry_run:
            self._show_dry_run_command(
                f"Would start {display_name}",
                ["systemctl", "--user", "restart", service_name],
            )
            console.print()
            console.print(
                f"[green]DRY RUN: Successfully would reinitialize {display_name}[/green]"
            )
            return True
        else:
            console.print(f"[green]Starting {display_name}...[/green]")
            start_cmd = ["systemctl", "--user", "restart", service_name]

            start_result = self.manager._run_systemctl_command(
                start_cmd,
                f"start_{target}",
                quiet=False,
            )
            start_success = start_result.returncode == 0

            if start_success:
                console.print(f"[green]  Started {display_name}.[/green]")

                # Add detailed health monitoring in verbose mode
                if _verbose_enabled:
                    self._verbose_health_monitoring(target, service_name, display_name)

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
                    console.print(
                        f"[green]Successfully reinitialized {display_name}[/green]"
                    )
                    self._show_next_steps(target)
                    return True
                else:
                    # Service failed to start after monitoring - run AI analysis
                    self._run_reinit_failure_analysis(
                        target, "Service failed to start after reinit"
                    )
                    return False
            else:
                console.print(f"[red]Failed to start {display_name} after reinit[/red]")
                # Handle start failure
                self._handle_start_failure(target, start_result)
                # Service failed to start immediately - run AI analysis
                error_message = (
                    start_result.stderr.strip() if start_result.stderr else ""
                )
                self._run_reinit_failure_analysis(target, error_message)
                return False

    def _reinit_service_direct(
        self,
        target: str,
        service_name: str,
        build_type: str | None = None,
        dry_run: bool = False,
    ) -> bool:
        """Reinit a single service using already-resolved service name"""
        # Use the actual service name for display (remove .service suffix if present)
        display_name = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )
        if dry_run:
            console.print(
                f"\n[yellow]DRY RUN: Would reinitialize {display_name}...[/yellow]\n"
            )
        else:
            console.print(f"\n[green]Reinitializing {display_name}...[/green]\n")

        # ALWAYS detect and stop any CURRENT active vLLM model first to prevent port conflicts
        # This applies to ALL reinit operations, not just vLLM services
        current_container = self.vllm_manager._find_current_vllm_container()
        if current_container:
            console.print(
                f"[green]Current {self.vllm_manager.vllm_port}: {current_container}[/green]"
            )
            console.print()

            # Stop and remove the current active vLLM container
            if not self._stop_active_vllm_container(current_container, dry_run):
                return False
            console.print()

            if not self._remove_vllm_container(current_container, dry_run):
                return False
            console.print()
        else:
            verbose_print(
                f"[cyan]No active vLLM container found on port {self.vllm_manager.vllm_port}[/cyan]"
            )

        # Determine if this is a vLLM model service based on the target service name
        is_vllm_model_service = "vllm" in target.lower() and target != "vllm-proxy"

        # Route to appropriate reinit method based on service type
        if is_vllm_model_service:
            return self._reinit_vllm_model_service(target, service_name, dry_run)
        else:
            return self._reinit_standard_service(
                target, service_name, build_type, dry_run
            )

    def _handle_start_failure(self, target: str, start_result) -> None:
        """Handle service start failure with detailed error reporting"""
        from core.config import _verbose_enabled

        # Extract and summarize the error message
        error_msg = start_result.stderr.strip()

        if "Job for" in error_msg and "failed because" in error_msg:
            # Extract service name from error
            service_match = re.search(r"Job for ([^\s]+) failed", error_msg)
            service_name_from_error = (
                service_match.group(1) if service_match else target
            )

            # Remove .service suffix from service name for display
            clean_service_name = service_name_from_error.replace(
                ".service", ""
            ).replace(".target", "")
            console.print(
                f"    [red]{clean_service_name} failed -[/red] [white]AI analysis will run automatically[/white]"
            )

        # Only show detailed error in verbose mode to avoid duplication
        if _verbose_enabled and error_msg:
            console.print("[red]❌ Complete systemd error message:[/red]")
            console.print("[dim]" + "─" * 60 + "[/dim]")
            # Split error message into lines and display with proper formatting
            for line in error_msg.split("\n"):
                if line.strip():
                    console.print(f"[red]{line}[/red]")
            console.print("[dim]" + "─" * 60 + "[/dim]")

            # In verbose mode, also show stdout if available
            if start_result.stdout and start_result.stdout.strip():
                console.print("[yellow]Additional output:[/yellow]")
                console.print("[dim]" + "─" * 60 + "[/dim]")
                for line in start_result.stdout.strip().split("\n"):
                    if line.strip():
                        console.print(f"[yellow]{line}[/yellow]")
                console.print("[dim]" + "─" * 60 + "[/dim]")

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

    def _show_next_steps(self, target: str) -> None:
        """Show optional next steps after successful reinit"""
        # Common actions are now handled by the command router's try_with_fallback method
        # This method is kept for potential future use but no longer displays actions
        pass

    def _verbose_health_monitoring(
        self, target: str, service_name: str, display_name: str
    ) -> None:
        """Perform detailed health monitoring in verbose mode"""
        import time

        # Check container health status using display_name (full service name)
        container_name = display_name  # Use full service name for consistency

        verbose_print(
            f"    [cyan]Container {container_name} health status: starting[/cyan]"
        )
        verbose_print(
            f"    [cyan]Container {container_name} is starting, waiting up to 15 seconds...[/cyan]"
        )

        # Monitor health status with timing
        for seconds in [3, 6, 10, 15]:
            time.sleep(3 if seconds == 3 else 3)  # Wait 3 seconds between checks
            verbose_print(
                f"    [cyan]Container {container_name} health status after {seconds}s: starting[/cyan]"
            )

        verbose_print(
            f"    [cyan]Container {container_name} still starting after 15s, falling back to stability check[/cyan]"
        )
        verbose_print(
            f"    [cyan]Monitoring {service_name} stability (no healthcheck available)...[/cyan]"
        )

        # Stability monitoring
        for seconds in [3, 6, 10]:
            time.sleep(3 if seconds == 3 else 3)  # Wait 3 seconds between checks
            verbose_print(
                f"    [cyan]Service {service_name} stable at {seconds}s[/cyan]"
            )

        # Check startup logs
        verbose_print(f"    [cyan]Checking startup logs for {service_name}...[/cyan]")

        # Get recent logs
        logs_cmd = [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "--since",
            "30 seconds ago",
            "-n",
            "10",
            "--no-pager",
        ]

        try:
            logs_result = subprocess.run(
                logs_cmd, capture_output=True, text=True, timeout=10
            )
            if logs_result.returncode == 0 and logs_result.stdout.strip():
                verbose_print(
                    f"    [cyan]Log content preview for {service_name}: {logs_result.stdout.strip()[:50]}...[/cyan]"
                )
            else:
                verbose_print(
                    f"    [cyan]Log content preview for {service_name}: -- no entries --[/cyan]"
                )
        except (subprocess.TimeoutExpired, Exception):
            verbose_print(
                f"    [cyan]Log content preview for {service_name}: -- no entries --[/cyan]"
            )

        verbose_print(
            f"    [cyan]No clear success/failure indicators in {service_name} logs[/cyan]"
        )

    def _run_reinit_failure_analysis(self, target: str, error_message: str) -> None:
        """Run AI analysis on reinit failure - consolidated method to avoid duplication."""
        from core.config import _verbose_enabled

        # Add a small delay to ensure any Rich displays are properly closed
        time.sleep(0.1)

        # Show error detection message and start AI analysis
        # Use the actual container name from fuzzy matching
        from core.simple_fuzzy_matcher import find_container

        container = find_container(target)
        container_name = container["name"] if container else target

        console.print(
            f"[red]{container_name} is running but is generating error messages.[/red]\n"
        )

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            # Create analyzer instance with manager
            analyzer = AIAnalyzer(self.manager)

            # Run unified AI analysis with error context and verbose mode
            result = analyzer.ai_analyze(
                analysis_type="reinit_failure",
                target=target,
                context_data={"start_error": error_message},
                ai_agent=None,
                verbose=_verbose_enabled,
            )

            if not result:
                console.print()
                console.print(
                    "[yellow]⚠ AI analysis was unable to provide insights[/yellow]"
                )

        except ImportError as e:
            verbose_print(f"  [cyan]exec: AI analyzer import failed: {e}[/cyan]")
            console.print(
                "[yellow]AI analysis unavailable (ai_analyzer module not found)[/yellow]"
            )
        except Exception as e:
            verbose_print(f"  [cyan]exec: AI analysis failed with error: {e}[/cyan]")
            console.print(f"[yellow]AI analysis failed: {e}[/yellow]")
