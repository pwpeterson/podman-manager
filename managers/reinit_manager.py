"""Refactored reinit operations with specialized components for better maintainability."""

import subprocess
from datetime import datetime

from core.config import console, verbose_print

from .reinit import (
    ContainerManager,
    HealthChecker,
    ModelReinitFlow,
    ReinitAIAnalyzer,
    ReinitMonitor,
    ServiceManager,
)


class ReinitManager:
    """Main orchestrator for reinit operations using specialized components."""

    def __init__(self, manager):
        self.manager = manager

        # Initialize specialized components
        self.health_checker = HealthChecker(manager)
        self.container_manager = ContainerManager(manager)
        self.service_manager = ServiceManager(manager)
        self.model_flow = ModelReinitFlow(
            manager, self.container_manager, self.service_manager
        )
        self.monitor = ReinitMonitor(manager, self.health_checker)
        self.ai_analyzer = ReinitAIAnalyzer(manager)

        # Enhanced features
        self.diagnostic_data = {}
        self.reinit_context = {}
        self.pre_reinit_state = {}

    def reinit(
        self,
        target: str,
        build: bool = False,
        build_type: str | None = None,
        model_model: str | None = None,
        dry_run: bool = False,
        enhanced: bool = False,
    ) -> bool:
        """Stop service, reload daemon, and restart service (useful for .container file changes)"""
        if enhanced:
            return self.enhanced_reinit(target, build, build_type, model_model)

        # Clear cache at the start
        self.manager._clear_auto_match_cache()

        # Handle backward compatibility - if build=True and no build_type, use legacy
        if build and build_type is None:
            build_type = "legacy"

        # Handle vLLM model switching if specified
        if model_model:
            console.print(
                f"[green]vLLM model switching requested: {model_model}[/green]"
            )
            if not self.container_manager.model_manger.switch_model_model(model_model):
                console.print("[red]vLLM model switch failed, aborting reinit[/red]")
                return False
            console.print()

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
            return self._reinit_service_direct(
                target, service_name, build_type=build_type, dry_run=dry_run
            )
        else:
            console.print(f"[red]Service '{target}' was not found[/red]")
            return False

    def enhanced_reinit(
        self,
        target: str,
        build: bool = False,
        build_type: str | None = None,
        model_model: str | None = None,
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
        if not self.health_checker.perform_pre_reinit_health_check(target):
            if enable_ai_guidance:
                self.ai_analyzer.run_pre_reinit_ai_analysis(
                    target, self.pre_reinit_state
                )
            return False

        # Step 2: Capture baseline state
        self.pre_reinit_state = self.service_manager.capture_pre_reinit_state(target)

        # Step 3: Execute reinit with enhanced monitoring
        success = self.monitor.execute_enhanced_reinit(
            target,
            build,
            build_type,
            model_model,
            enable_ai_guidance,
            lambda t, b, bt, vm: self.reinit(t, b, bt, vm),
        )

        # Step 4: Post-reinit verification and optimization suggestions
        if success:
            self.monitor.perform_post_reinit_verification(target, enable_ai_guidance)

        return success

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
        timestamp = datetime.now().strftime("%H:%M:%S")
        if dry_run:
            console.print(
                f"\n[yellow]DRY RUN: Would reinitialize {display_name}...[/yellow]\n"
            )
        else:
            console.print(
                f"\n[green]{timestamp} | Reinitializing {display_name}...[/green]\n"
            )

        # Determine if this is a model service using name-based heuristics (legacy config removed)
        is_model_service = self.service_manager.is_model_service(display_name)

        # Route to appropriate reinit method based on service type
        if is_model_service:
            return self.model_flow.reinit_model_service(target, service_name, dry_run)
        else:
            return self._reinit_standard_service(
                target, service_name, build_type, dry_run
            )

    def _reinit_standard_service(
        self,
        target: str,
        service_name: str,
        build_type: str | None,
        dry_run: bool = False,
    ) -> bool:
        """Handle standard service reinit following the specified standard flow"""
        display_name = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )

        if dry_run:
            console.print(
                f"[yellow]DRY RUN: Would reinitialize {display_name}[/yellow]"
            )
            return True

        # Step 1: Stop the service
        stop_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(f"[green]{stop_timestamp} | Stopping {display_name}...[/green]")
        verbose_print(f"[cyan]exec: sudo systemctl stop {service_name}[/cyan]")
        stop_result = self.service_manager.stop_service(
            service_name, target, quiet=True
        )

        stopped_timestamp = datetime.now().strftime("%H:%M:%S")
        if stop_result.returncode == 0:
            console.print(
                f"[green]{stopped_timestamp} |   Stopped {display_name}[/green]"
            )
        else:
            console.print(
                f"[yellow]{stopped_timestamp} |   {display_name} was not running or failed to stop[/yellow]"
            )
        console.print()

        # Step 2: Remove service file (method handles its own messaging)
        self.service_manager.remove_service_file(service_name, dry_run=False)
        console.print()

        # Step 3: Reload systemd daemon
        if not self.service_manager.reload_daemon():
            return False
        console.print()

        # Step 4: Restart the service
        start_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{start_timestamp} | Restarting {display_name}...[/green]"
        )

        start_cmd = ["sudo", "systemctl", "restart", service_name]
        verbose_print(f"[cyan]exec: {' '.join(start_cmd)}[/cyan]")

        try:
            start_result = subprocess.run(
                start_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            start_result = subprocess.CompletedProcess(
                start_cmd, 124, "", "Service start timed out after 30 seconds"
            )
        except Exception as e:
            start_result = subprocess.CompletedProcess(
                start_cmd, 1, "", f"Service start failed: {str(e)}"
            )

        started_timestamp = datetime.now().strftime("%H:%M:%S")
        if start_result.returncode == 0:
            console.print()
            console.print(
                f"[green]{started_timestamp} | Successfully reinitialized {display_name}[/green]"
            )
            return True
        else:
            console.print(
                f"[red]{started_timestamp} |   Failed to restart {display_name}[/red]"
            )
            self.model_flow._handle_start_failure(target, start_result)
            error_message = start_result.stderr.strip() if start_result.stderr else ""
            self.model_flow._run_reinit_failure_analysis(target, error_message)
            return False
