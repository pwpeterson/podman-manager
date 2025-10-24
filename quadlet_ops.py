"""Quadlet container operations for vLLM services - Refactored with modular architecture."""

from typing import List

from ai_diagnostics import AIDiagnostics
from config import console
from container_builder import ContainerBuilder
from log_analyzer import LogAnalyzer
from reinit_manager import ReinitManager
from service_lifecycle import ServiceLifecycle
from stack_manager import StackManager
from system_monitor import SystemMonitor


class QuadletOperations:
    """
    Quadlet container operations coordinator - acts as a facade for modular components.

    This class has been refactored to delegate operations to specialized modules:
    - ServiceLifecycle: Basic service operations (start, stop, restart, enable, disable)
    - LogAnalyzer: Log analysis, pattern matching, and diagnostics
    - AIDiagnostics: AI-powered log analysis and troubleshooting
    - ContainerBuilder: Image building and rebuild operations
    - StackManager: Multi-service stack operations
    - SystemMonitor: Health checks, monitoring, and maintenance
    - ReinitManager: Complex reinit operations with monitoring
    """

    def __init__(self, manager):
        self.manager = manager

        # Initialize specialized modules
        self.service_lifecycle = ServiceLifecycle(manager)
        self.log_analyzer = LogAnalyzer(manager)
        self.ai_diagnostics = AIDiagnostics(manager)
        self.container_builder = ContainerBuilder(manager)
        self.stack_manager = StackManager(manager)
        self.system_monitor = SystemMonitor(manager)
        self.reinit_manager = ReinitManager(manager)

    def _resolve_service_name(
        self, target: str, strip_service_suffix: bool = False
    ) -> str:
        """Resolve service name using fuzzy matching and optionally strip .service suffix.

        Args:
            target: Original target name (e.g., 'ollama')
            strip_service_suffix: If True, remove .service suffix for Dockerfile naming

        Returns:
            Resolved service name, optionally without .service suffix
        """
        service_name = self.manager._find_service_name(target)
        resolved_target = (
            service_name
            if service_name and not service_name.startswith("STACK:")
            else target
        )

        if strip_service_suffix and resolved_target.endswith(".service"):
            resolved_target = resolved_target[:-8]

        return resolved_target

    # Service Lifecycle Operations
    def start(self, target: str, build: bool = False) -> bool:
        """Start a service or stack"""
        return self.service_lifecycle.start(target, build)

    def stop(self, target: str) -> bool:
        """Stop a service or stack"""
        return self.service_lifecycle.stop(target)

    def restart(self, target: str, build: bool = False) -> bool:
        """Restart a service or stack"""
        return self.service_lifecycle.restart(target, build)

    def enable(self, target: str) -> bool:
        """Enable a service or stack to start at boot"""
        return self.service_lifecycle.enable(target)

    def disable(self, target: str) -> bool:
        """Disable a service or stack from starting at boot"""
        return self.service_lifecycle.disable(target)

    def reset_failed(self, target: str) -> bool:
        """Reset failed service state"""
        return self.service_lifecycle.reset_failed(target)

    def show_service_file(self, target: str) -> bool:
        """Show service file contents"""
        return self.service_lifecycle.show_service_file(target)

    def show_service_status(self, target: str) -> None:
        """Show detailed status for a specific service"""
        self.service_lifecycle.show_service_status(target)

    def reload_daemon(self) -> bool:
        """Reload systemd user daemon"""
        return self.service_lifecycle.reload_daemon()

    # Log Analysis Operations
    def show_logs(self, target: str, follow: bool = False) -> None:
        """Show service logs using journalctl"""
        self.log_analyzer.show_logs(target, follow)

    def analyze_logs(self, target: str, lines: int = 50) -> None:
        """Analyze service logs for errors, warnings, and other issues"""
        self.log_analyzer.analyze_logs(target, lines)

    def diagnose_container_failure(self, target: str) -> None:
        """Diagnose why a container is failing to start"""
        self.log_analyzer.diagnose_container_failure(target)

    # AI-Powered Diagnostics
    def ai_analyze_logs(
        self,
        target: str,
        lines: int = 50,
        vllm_url: str = "http://localhost:8002",
        verbose: bool = False,
        ai_agent: str | None = None,
    ) -> None:
        """AI-powered analysis of service logs for root causes and solutions"""
        self.ai_diagnostics.ai_analyze_logs(target, lines, vllm_url, verbose, ai_agent)

    # Container Building Operations
    def rebuild(self, target: str) -> bool:
        """Rebuild container image and restart service"""
        console.print()
        console.print(f"[green]Building {target}...[/green]")
        console.print()

        service_name = self.manager._find_service_name(target)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self.container_builder.rebuild_stack(stack_name)

        # Handle legacy stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self.container_builder.rebuild_stack(project_name)

        # Handle individual service - use resolved service name without .service suffix
        resolved_target = self._resolve_service_name(target, strip_service_suffix=True)
        return self.container_builder.rebuild_service(resolved_target)

    def update_images_and_restart(self, target: str) -> bool:
        """Update container images and restart service (for quadlets with auto-update)"""
        resolved_target = self._resolve_service_name(target, strip_service_suffix=True)
        return self.container_builder.update_images_and_restart(resolved_target)

    # Stack Management Operations
    def down(self, target: str = "vllm-stack") -> bool:
        """Stop all services in a stack or project"""
        return self.stack_manager.down(target)

    def uninstall_stack(self, stack: str) -> bool:
        """Uninstall quadlet stack from systemd directory"""
        return self.stack_manager.uninstall_stack(stack)

    def install_stack(self, stack: str) -> bool:
        """Install/build quadlet stack or service using integrated installer module"""
        return self.stack_manager.install_stack(stack)

    # System Monitoring Operations
    def check_auto_update_status(self) -> None:
        """Check if podman auto-update timer is enabled"""
        self.system_monitor.check_auto_update_status()

    def enable_auto_update(self) -> bool:
        """Enable podman auto-update timer"""
        return self.system_monitor.enable_auto_update()

    def trigger_auto_update(self) -> bool:
        """Manually trigger podman auto-update"""
        return self.system_monitor.trigger_auto_update()

    def show_container_status(self) -> None:
        """Show status of containers managed by quadlets"""
        self.system_monitor.show_container_status()

    def exec_command(self, target: str, command: List[str]) -> None:
        """Execute command in container (find container by service name)"""
        self.system_monitor.exec_command(target, command)

    def prune_containers(self, enhanced: bool = True, quick: bool = False) -> None:
        """Remove unused containers and images with intelligent analysis"""
        self.system_monitor.prune_containers(enhanced, quick)

    def prune(self, enhanced: bool = True, quick: bool = False) -> None:
        """Alias for prune_containers for compatibility"""
        self.system_monitor.prune(enhanced, quick)

    def show_system_df(self) -> None:
        """Show system disk usage"""
        self.system_monitor.show_system_df()

    def health_check(self, target: str | None = None) -> None:
        """Perform comprehensive health check on services or entire system"""
        self.system_monitor.health_check(target)

    def monitor_services(
        self, services: List[str] | None = None, interval: int = 5
    ) -> None:
        """Monitor services in real-time"""
        self.system_monitor.monitor_services(services, interval)

    def system_info(self) -> None:
        """Display comprehensive system information"""
        self.system_monitor.system_info()

    # Complex Reinit Operations
    def reinit(
        self, target: str, build: bool = False, build_type: str | None = None
    ) -> bool:
        """Stop service, reload daemon, and restart service (useful for .container file changes)"""
        return self.reinit_manager.reinit(target, build, build_type)

    # Legacy compatibility methods - these delegate to the appropriate modules
    def _render_ansi_output(self, output: str) -> None:
        """Render ANSI-colored output from subprocess"""
        self.container_builder._render_ansi_output(output)

    def _extract_log_message(self, log_line: str, msg_type: str) -> str:
        """Extract the actual error/warning message from a log line with timestamp"""
        return self.log_analyzer._extract_log_message(log_line, msg_type)

    # Specialized rebuild methods for backward compatibility
    def _rebuild_vllm_delegator_mcp(self) -> bool:
        """Rebuild vLLM Delegator MCP container image"""
        return self.container_builder.rebuild_vllm_delegator_mcp()

    def _rebuild_vllm_proxy(self) -> bool:
        """Rebuild vLLM Proxy container image"""
        return self.container_builder.rebuild_vllm_proxy()

    def _build_service(self, target: str) -> bool:
        """Build images for a single service using quadlet build process"""
        resolved_target = self._resolve_service_name(target, strip_service_suffix=True)
        return self.container_builder.build_service(resolved_target)

    def _build_service_podman(self, target: str) -> bool:
        """Build images using regular podman build"""
        resolved_target = self._resolve_service_name(target, strip_service_suffix=True)
        return self.container_builder.build_service_podman(resolved_target)

    def _start_service_with_build(self, target: str, build: bool = False) -> bool:
        """Start a service with optional build"""
        # For service lifecycle operations, keep the full service name with .service suffix
        resolved_target = self._resolve_service_name(target, strip_service_suffix=False)
        return self.service_lifecycle._start_service_with_build(resolved_target, build)

    def _restart_service_with_build(self, target: str, build: bool = False) -> bool:
        """Restart a service with optional build"""
        # For service lifecycle operations, keep the full service name with .service suffix
        resolved_target = self._resolve_service_name(target, strip_service_suffix=False)

        if build:
            # Stop first (clear cache to prevent duplicate messages)
            self.manager._clear_auto_match_cache()
            self.manager.stop_service(resolved_target, quiet=True)
            # Build - use service name without .service suffix for Dockerfile naming
            build_target = self._resolve_service_name(target, strip_service_suffix=True)
            if not self.container_builder.build_service(build_target):
                return False
            # Reload daemon
            self.manager.reload_daemon()
            # Clear cache again before restart
            self.manager._clear_auto_match_cache()
        return self.manager.restart_service(resolved_target)
