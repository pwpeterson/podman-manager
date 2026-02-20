"""Core QuadletManager class for managing vLLM containers as systemd quadlets."""

import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from ai_analyzer.spinner_manager import safe_spinner
from core.config import (  # pyright: ignore[reportAttributeAccessIssue]
    console,
    verbose_print,
)
from core.fuzzy_matcher import FuzzyMatcher
from core.service_discovery import get_service_discovery
from core.validation_utils import get_validation_utils


class QuadletManager:
    """Main class for managing vLLM containers as systemd quadlets with Rich UI"""

    def __init__(self, project_name="vllm"):
        # Project name for display purposes
        self.project_name = project_name

        # Get shared service discovery and validation utilities
        self.discovery = get_service_discovery()
        self.validation = get_validation_utils()

        # Quadlets directory path (standard systemd location only)
        self.quadlets_dir = Path("/etc/containers/systemd")

        # Stack target for managing all services together
        self.stack_target = "vllm-stack.target"

        # Store last fuzzy match results for numeric selection
        self.last_fuzzy_matches = []
        self.cache_file = Path.home() / ".pm_fuzzy_cache"

        logger.debug("Initializing QuadletManager for quadlet services")
        self.validation.validate_prerequisites()
        self._load_fuzzy_cache()

    @property
    def quadlet_services(self) -> Dict[str, str]:
        """Access to discovered quadlet services."""
        return self.discovery.quadlet_services

    @property
    def stack_services(self) -> Dict[str, List[str]]:
        """Access to discovered stack services."""
        return self.discovery.stack_services

    @property
    def service_status(self) -> Dict[str, Dict[str, bool]]:
        """Access to service status information."""
        return self.discovery.service_status

    @property
    def stdio_services(self) -> Dict[str, Dict]:
        """Access to STDIO services information."""
        return self.discovery.stdio_services

    def _validate_prerequisites(self) -> bool:
        """Validate that required tools exist"""
        logger.debug("Starting prerequisites validation")

        # Check systemctl
        if not self._command_exists("systemctl"):
            logger.error("Required command 'systemctl' not found!")
            return False

        # Check if we can run sudo systemctl
        result = subprocess.run(
            ["sudo", "systemctl", "--help"], capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error("'sudo systemctl' is not available!")
            console.print(
                "[dim]Make sure systemd is available and sudo is configured[/dim]"
            )
            return False

        logger.success("Prerequisites validation complete")
        return True

    def _discover_quadlet_services(self) -> None:
        """Auto-discover all quadlet services from both source and installed directories"""
        # Primary source directory
        self.quadlets_source_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")

        # Track installation status for each service (moved to ServiceDiscovery)

        # First scan primary source directory
        if self.quadlets_source_dir.exists():
            logger.debug(
                "Discovering quadlet services from source: {}", self.quadlets_source_dir
            )
            self._scan_source_directory(self.quadlets_source_dir)
        else:
            logger.warning(
                "Primary quadlets source directory not found: {}",
                self.quadlets_source_dir,
            )

        # Then scan installed directory to mark installation status
        if self.quadlets_dir.exists():
            logger.debug("Checking installed quadlet services: {}", self.quadlets_dir)
            self._scan_installed_directory(self.quadlets_dir)
        else:
            logger.warning(
                "Systemd quadlets directory not found: {}", self.quadlets_dir
            )

        logger.info(
            "Discovered {} quadlet services across {} stacks",
            len(self.quadlet_services),
            len(self.stack_services),
        )

    def _scan_source_directory(self, source_dir: Path) -> None:
        """Scan the primary source directory for all available stacks and services"""
        # Scan for stack directories
        for stack_dir in source_dir.iterdir():
            if not stack_dir.is_dir() or not stack_dir.name.endswith("-stack"):
                continue

            stack_name = stack_dir.name
            stack_services = []

            logger.debug("Scanning source stack directory: {}", stack_dir)

            # Find all .container and .target files in this stack
            for service_file in stack_dir.glob("*.container"):
                service_name = service_file.stem
                full_service_name = f"{service_name}.service"

                # Add to services mapping
                self.quadlet_services[service_name] = full_service_name
                stack_services.append(service_name)

                # Mark as available in source
                self.service_status[service_name] = {"installed": False, "source": True}

                logger.debug(
                    "Found source service: {} -> {}", service_name, full_service_name
                )

            # Add .target files too
            for target_file in stack_dir.glob("*.target"):
                target_name = target_file.stem
                full_target_name = f"{target_name}.target"

                self.quadlet_services[target_name] = full_target_name
                stack_services.append(target_name)
                self.service_status[target_name] = {"installed": False, "source": True}

                logger.debug(
                    "Found source target: {} -> {}", target_name, full_target_name
                )

            # Store stack services mapping
            if stack_services:
                self.stack_services[stack_name] = stack_services
                logger.debug(
                    "Source stack {} contains services: {}", stack_name, stack_services
                )

    def _scan_installed_directory(self, installed_dir: Path) -> None:
        """Scan installed directory and mark services as installed"""
        standalone_services = []

        # Scan for .container files
        for service_file in installed_dir.glob("*.container"):
            service_name = service_file.stem

            if service_name in self.service_status:
                # Mark existing service as installed
                self.service_status[service_name]["installed"] = True
                logger.debug("Marked service as installed: {}", service_name)
            else:
                # This is a standalone service only in systemd
                full_service_name = f"{service_name}.service"
                self.quadlet_services[service_name] = full_service_name
                self.service_status[service_name] = {"installed": True, "source": False}
                standalone_services.append(service_name)
                logger.debug("Found standalone installed service: {}", service_name)

        # Scan for .target files
        for target_file in installed_dir.glob("*.target"):
            target_name = target_file.stem

            if target_name in self.service_status:
                # Mark existing target as installed
                self.service_status[target_name]["installed"] = True
                logger.debug("Marked target as installed: {}", target_name)
            else:
                # This is a standalone target only in systemd
                full_target_name = f"{target_name}.target"
                self.quadlet_services[target_name] = full_target_name
                self.service_status[target_name] = {"installed": True, "source": False}
                standalone_services.append(target_name)
                logger.debug("Found standalone installed target: {}", target_name)

        # Add standalone services to a special group
        if standalone_services:
            self.stack_services["standalone"] = standalone_services
            logger.debug(
                "Created standalone group with services: {}", standalone_services
            )

    def _scan_quadlets_directory(self, quadlets_dir: Path) -> None:
        """Scan a specific quadlets directory for stack directories and services"""
        # First, scan for stack directories (subdirectories ending with -stack)
        for stack_dir in quadlets_dir.iterdir():
            if not stack_dir.is_dir() or not stack_dir.name.endswith("-stack"):
                continue

            stack_name = stack_dir.name  # e.g., "vllm-stack", "local-ai-stack"
            stack_services = []

            logger.debug("Scanning stack directory: {}", stack_dir)

            # Find all .container files in this stack
            for container_file in stack_dir.glob("*.container"):
                service_name = container_file.stem  # Remove .container extension
                full_service_name = f"{service_name}.service"

                # Create short name by removing common prefixes
                short_name = service_name
                stack_prefix = stack_name.replace("-stack", "-")  # e.g., "supabase-"

                if service_name.startswith(stack_prefix):
                    # Remove stack prefix: "supabase-auth" -> "auth"
                    short_name = service_name[len(stack_prefix) :]
                    # But keep the full service name for better identification
                    # Use the full service name as the short name for stack services
                    short_name = service_name
                else:
                    # For services that don't follow the pattern, keep full name
                    short_name = service_name

                # Add to services mapping
                self.quadlet_services[short_name] = full_service_name
                stack_services.append(short_name)

                logger.debug("Found service: {} -> {}", short_name, full_service_name)

            # Store stack services mapping
            if stack_services:
                self.stack_services[stack_name] = stack_services
                logger.debug(
                    "Stack {} contains services: {}", stack_name, stack_services
                )

        # Also scan for .container files directly in the quadlets directory
        # (for services not organized in stack subdirectories)
        # Group services by common prefixes to create logical stacks
        direct_services = {}
        stack_groups = {}

        for container_file in quadlets_dir.glob("*.container"):
            service_name = container_file.stem  # Remove .container extension
            full_service_name = f"{service_name}.service"

            # Use service name as short name for direct services
            short_name = service_name

            # Add to services mapping (only if not already added from a stack)
            if short_name not in self.quadlet_services:
                self.quadlet_services[short_name] = full_service_name
                direct_services[short_name] = full_service_name
                logger.debug(
                    "Found direct service: {} -> {}", short_name, full_service_name
                )

                # Group services by common prefixes to create logical stacks
                if "-" in service_name:
                    prefix = service_name.split("-")[0]
                    if prefix not in stack_groups:
                        stack_groups[prefix] = []
                    stack_groups[prefix].append(short_name)

        # Create logical stacks from grouped services
        for prefix, services in stack_groups.items():
            if len(services) > 1:  # Only create stacks with multiple services
                stack_name = f"{prefix}-stack"
                # Only create the stack if it doesn't already exist
                if stack_name not in self.stack_services:
                    self.stack_services[stack_name] = services
                    logger.debug(
                        "Created logical stack {} with services: {}",
                        stack_name,
                        services,
                    )

        # Handle standalone services that don't fit into any stack
        standalone_services = []
        for service_name in self.quadlet_services.keys():
            # Check if this service is already in a stack
            found_in_stack = False
            for stack_services in self.stack_services.values():
                if service_name in stack_services:
                    found_in_stack = True
                    break

            # If not in any stack, it's standalone
            if not found_in_stack:
                standalone_services.append(service_name)

        # Create standalone group if we have any
        if standalone_services:
            self.stack_services["standalone"] = standalone_services
            logger.debug(
                "Created standalone group with services: {}", standalone_services
            )

        # Handle standalone services that don't fit into any stack
        standalone_services = []
        for service_name in self.quadlet_services.keys():
            # Check if this service is already in a stack
            found_in_stack = False
            for stack_services in self.stack_services.values():
                if service_name in stack_services:
                    found_in_stack = True
                    break

            # If not in any stack, it's standalone
            if not found_in_stack:
                standalone_services.append(service_name)

        # Create standalone group if we have any
        if standalone_services:
            self.stack_services["standalone"] = standalone_services
            logger.debug(
                "Created standalone group with services: {}", standalone_services
            )

    def refresh_service_discovery(self) -> None:
        """Re-discover all quadlet services and stacks (useful after installing new stacks)"""
        logger.debug("Refreshing quadlet service discovery")

        # Clear existing mappings
        self.quadlet_services.clear()
        self.stack_services.clear()

        # Clear service status tracking
        if hasattr(self, "service_status"):
            self.service_status.clear()

        # Re-discover services
        self._discover_quadlet_services()

        logger.info(
            "Refreshed discovery: {} quadlet services across {} stacks",
            len(self.quadlet_services),
            len(self.stack_services),
        )

    def _load_fuzzy_cache(self) -> None:
        """Load fuzzy match results from cache file"""
        try:
            if self.cache_file.exists():
                import json

                with open(self.cache_file, "r") as f:
                    self.last_fuzzy_matches = json.load(f)
        except Exception:
            self.last_fuzzy_matches = []

    def _save_fuzzy_cache(self) -> None:
        """Save fuzzy match results to cache file"""
        try:
            import json

            with open(self.cache_file, "w") as f:
                json.dump(self.last_fuzzy_matches, f)
        except Exception:
            pass  # Ignore cache save errors

    def _search_systemd_directory(self, partial_name: str) -> List[str]:
        """Search systemd directory for .container files that match partial name"""
        matches = []

        if not self.quadlets_dir.exists():
            return matches

        try:
            # Search for .container files that contain the partial name
            for container_file in self.quadlets_dir.glob("*.container"):
                service_name = container_file.stem  # Remove .container extension

                # Check if partial name matches (case-insensitive)
                if partial_name.lower() in service_name.lower():
                    # Only add if not already in our discovered services
                    if service_name not in self.quadlet_services:
                        matches.append(service_name)
                        # Also add it to our services mapping for future use
                        self.quadlet_services[service_name] = f"{service_name}.service"

            # Also search for .target files
            for target_file in self.quadlets_dir.glob("*.target"):
                target_name = target_file.stem  # Remove .target extension

                # Check if partial name matches (case-insensitive)
                if partial_name.lower() in target_name.lower():
                    # Only add if not already in our discovered services
                    if target_name not in self.quadlet_services:
                        matches.append(target_name)
                        # Also add it to our services mapping for future use
                        self.quadlet_services[target_name] = f"{target_name}.target"

        except Exception as e:
            logger.debug("Error searching systemd directory: {}", e)

        return matches

    def _get_service_display_info(self, service_name: str) -> str:
        """Get additional display information for a service"""
        info_parts = []

        # Check if it's installed
        if hasattr(self, "service_status") and service_name in self.service_status:
            status = self.service_status[service_name]
            if status.get("installed", False):
                info_parts.append("[green](installed)[/green]")
            elif status.get("source", False):
                info_parts.append("[bright_yellow](available)[/bright_yellow]")
        else:
            # Check if service file exists in systemd directory
            container_file = self.quadlets_dir / f"{service_name}.container"
            target_file = self.quadlets_dir / f"{service_name}.target"
            if container_file.exists() or target_file.exists():
                info_parts.append("[green](installed)[/green]")

        # Check if it's part of a stack
        for stack_name, stack_services in self.stack_services.items():
            if service_name in stack_services:
                info_parts.append(f"[dim](in {stack_name})[/dim]")
                break

        # Check current status
        try:
            status = self.get_service_status(service_name)
            active_state = status.get("ActiveState", "unknown")
            if active_state == "active":
                info_parts.append("[green](running)[/green]")
            elif active_state == "inactive":
                info_parts.append("[dim](stopped)[/dim]")
            elif active_state == "failed":
                info_parts.append("[red](failed)[/red]")
        except Exception:
            pass  # Ignore status check errors

        return " " + " ".join(info_parts) if info_parts else ""

    def _clear_auto_match_cache(self) -> None:
        """Clear the auto-match cache for a new command"""
        # Auto-match cache is no longer used since fuzzy matching is always enabled
        pass

    def _check_container_file_exists(
        self, target: str, command: str = "install"
    ) -> tuple[bool, Optional[str]]:
        """Check if the container file exists in systemd directory for a given target using fuzzy matching

        Returns:
            tuple[bool, Optional[str]]: (exists, resolved_service_name)
        """
        # Use fuzzy matching to resolve the target
        fuzzy_matcher = FuzzyMatcher(quadlet_manager=self)
        resolved_target = fuzzy_matcher.fuzzy_match_service_or_stack(target, command)

        if not resolved_target or resolved_target == "CANCELLED":
            return False, None

        # Handle stack targets
        if resolved_target.startswith("STACK:"):
            stack_name = resolved_target[6:]  # Remove "STACK:" prefix
            if stack_name in self.stack_services:
                # Check if at least one service in the stack has a container file
                for service_name in self.stack_services[stack_name]:
                    container_file = self.quadlets_dir / f"{service_name}.container"
                    target_file = self.quadlets_dir / f"{service_name}.target"
                    if container_file.exists() or target_file.exists():
                        return True, resolved_target
                return False, None

        # Handle individual services
        # Extract service name from full service name (remove .service suffix)
        service_name = resolved_target
        if service_name.endswith(".service"):
            service_name = service_name[:-8]  # Remove ".service" suffix
        elif service_name.endswith(".target"):
            service_name = service_name[:-7]  # Remove ".target" suffix

        container_file = self.quadlets_dir / f"{service_name}.container"
        target_file = self.quadlets_dir / f"{service_name}.target"
        exists = container_file.exists() or target_file.exists()
        return exists, resolved_target if exists else None

    def _show_install_suggestion(self, target: str) -> None:
        """Show suggestion to install the missing container file"""
        console.print(
            f"[bright_yellow]Required container file is missing, run pm install {target}[/bright_yellow]"
        )

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        result = subprocess.run(["which", command], capture_output=True)
        exists = result.returncode == 0
        logger.debug("Command '{}' exists: {}", command, exists)
        return exists

    def _trigger_service_start_ai_analysis(
        self,
        target: str,
        service_name: str,
        start_command: str,
        error_code: int,
        systemd_error: Optional[str] = None,
    ) -> None:
        """Trigger automatic AI analysis for service start failures"""
        try:
            from ai_analyzer import get_ai_analyzer
            from core.config import _verbose_enabled

            analyzer = get_ai_analyzer(self)

            # Collect additional diagnostic information
            context_data = {
                "service_name": service_name,
                "target": target,
                "start_command": start_command,
                "error_code": error_code,
            }

            # Add systemd error if available
            if systemd_error:
                context_data["systemd_error"] = systemd_error

            # Get service status for additional context
            try:
                status = self.get_service_status(target)
                status_info = []
                for key, value in status.items():
                    status_info.append(f"{key}={value}")
                context_data["service_status"] = "\n".join(status_info)
            except Exception:
                pass  # Ignore status collection errors

            # Try to get recent logs for context
            try:
                log_cmd = [
                    "sudo",
                    "journalctl",
                    "-u",
                    service_name,
                    "--lines=20",
                    "--no-pager",
                ]
                log_result = subprocess.run(
                    log_cmd, capture_output=True, text=True, timeout=10
                )
                if log_result.returncode == 0 and log_result.stdout.strip():
                    context_data["recent_logs"] = log_result.stdout.strip()
            except Exception:
                pass  # Ignore log collection errors

            # Try to get container information if it's a container service
            try:
                container_name = target  # Use target as container name
                container_cmd = [
                    "podman",
                    "ps",
                    "-a",
                    "--filter",
                    f"name={container_name}",
                    "--format",
                    "table",
                ]
                container_result = subprocess.run(
                    container_cmd, capture_output=True, text=True, timeout=10
                )
                if container_result.returncode == 0 and container_result.stdout.strip():
                    context_data["container_info"] = container_result.stdout.strip()
            except Exception:
                pass  # Ignore container info collection errors

            # Get basic system resource information
            try:
                df_result = subprocess.run(
                    ["df", "-h", "/"], capture_output=True, text=True, timeout=5
                )
                free_result = subprocess.run(
                    ["free", "-h"], capture_output=True, text=True, timeout=5
                )
                resource_info = []
                if df_result.returncode == 0:
                    resource_info.append("DISK SPACE:")
                    resource_info.append(df_result.stdout.strip())
                if free_result.returncode == 0:
                    resource_info.append("\nMEMORY:")
                    resource_info.append(free_result.stdout.strip())
                if resource_info:
                    context_data["system_resources"] = "\n".join(resource_info)
            except Exception:
                pass  # Ignore resource collection errors

            # Run AI analysis with service start failure type (model-proxy)
            result = analyzer.ai_analyze(
                analysis_type="service_start_failure",
                target=target,
                context_data=context_data,
                ai_model=None,  # Use configured assistant model
                verbose=_verbose_enabled,
            )

            if not result:
                console.print(
                    "[bright_yellow]⚠ Unable to analyze service start failure[/bright_yellow]"
                )

        except Exception:
            # Silently fail - don't let AI analysis errors break the service management
            pass

    def _run_systemctl_command(
        self,
        cmd: List[str],
        action: str,
        suppress_errors: bool = False,
        quiet: bool = False,
    ) -> subprocess.CompletedProcess:
        """Execute a systemctl command and return the result"""
        from core.config import _verbose_enabled

        # Display command in a subtle way (unless quiet)
        if not quiet:
            verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        # Use loguru's context binding for structured logging
        with logger.contextualize(action=action, command=" ".join(cmd)):
            logger.info("Executing systemctl command: {}", " ".join(cmd))

            start_time = time.time()
            # Add timeout for systemctl commands, especially for vLLM model services
            timeout = 120  # 2 minutes timeout for systemctl commands
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=timeout
                )
                execution_time = time.time() - start_time
            except subprocess.TimeoutExpired:
                execution_time = time.time() - start_time
                logger.warning(
                    "Command timed out after {:.2f}s: {}", execution_time, " ".join(cmd)
                )
                # Create a mock result for timeout
                result = subprocess.CompletedProcess(
                    cmd,
                    returncode=124,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                )

            # Log the result with context
            if result.returncode == 0:
                logger.success(
                    "Command completed successfully in {:.2f}s", execution_time
                )
                if result.stdout:
                    logger.debug(
                        "Command output: {}",
                        (
                            result.stdout[:200] + "..."
                            if len(result.stdout) > 200
                            else result.stdout
                        ),
                    )
                    # Show stdout in verbose mode
                    if _verbose_enabled and result.stdout.strip():
                        console.print("[green]Command output:[/green]")
                        console.print("[dim]" + "─" * 60 + "[/dim]")
                        for line in result.stdout.strip().split("\n"):
                            if line.strip():
                                console.print(f"[green]{line}[/green]")
                        console.print("[dim]" + "─" * 60 + "[/dim]")
            else:
                if not suppress_errors:
                    # Handle specific error cases with user-friendly messages
                    if (
                        result.returncode == 1
                        and result.stderr
                        and "Failed to connect to bus" in result.stderr
                    ):
                        # Bus connection issue - show friendly message
                        console.print(
                            "[yellow]Cannot connect to systemd user session[/yellow]"
                        )
                        console.print("[dim]Try: sudo systemctl daemon-reload[/dim]")
                        logger.debug(
                            "Bus connection failed (code {}) in {:.2f}s: {}",
                            result.returncode,
                            execution_time,
                            result.stderr.strip(),
                        )
                    else:
                        logger.error(
                            "Command failed with code {} in {:.2f}s",
                            result.returncode,
                            execution_time,
                        )
                        if result.stderr:
                            logger.error("Error output: {}", result.stderr)

                            # Don't show error details to avoid cluttering output
                            # The calling method will handle user-facing error messages if needed
                else:
                    # Suppressed errors - only log, don't show to user
                    logger.debug(
                        "Command failed with code {} in {:.2f}s (suppressed)",
                        result.returncode,
                        execution_time,
                    )
                    if result.stderr:
                        logger.debug("Suppressed error output: {}", result.stderr)
                    # Don't show any console output when errors are suppressed

            return result

    def get_service_status(self, service_name: str) -> Dict[str, str]:
        """Get detailed status information for a service"""
        if service_name in self.quadlet_services:
            full_service_name = self.quadlet_services[service_name]
        elif service_name == self.stack_target:
            full_service_name = service_name  # Don't add .service to .target
        elif service_name.endswith(".service") or service_name.endswith(".target"):
            full_service_name = service_name
        else:
            full_service_name = f"{service_name}.service"

        cmd = [
            "sudo",
            "systemctl",
            "show",
            full_service_name,
            "--property=ActiveState,SubState,LoadState,UnitFileState",
        ]

        result = self._run_systemctl_command(cmd, f"status_{service_name}")

        status = {}
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    status[key] = value
        else:
            status = {
                "ActiveState": "unknown",
                "SubState": "unknown",
                "LoadState": "not-found",
                "UnitFileState": "unknown",
            }

        return status

    def list_quadlet_services(self) -> Dict[str, Dict]:
        """List all quadlet services with their status"""
        services = {}

        for short_name, full_name in self.quadlet_services.items():
            status = self.get_service_status(full_name)
            services[short_name] = {"full_name": full_name, "status": status}

        return services

    def get_stack_status(self) -> Dict[str, str]:
        """Get status of the vllm-stack.target"""
        return self.get_service_status(self.stack_target)

    def _find_service_name(
        self, target: str, command: str = "install"
    ) -> Optional[str]:
        """Find the full service name from a target (short name or full name)"""
        # Check if it's a numeric selection (e.g., "1", "2", etc.)
        if target.isdigit():
            return self._handle_numeric_selection(int(target))

        # Handle common service name aliases first
        service_aliases = {
            "vllm-qwen": "vllm-qwen25",
            "qwen": "vllm-qwen25",
            "qwen25": "vllm-qwen25",
            "delegator": "vllm-delegator",
            "proxy": "vllm-proxy",
        }

        if target in service_aliases:
            original_target = target
            target = service_aliases[target]
            console.print(
                f"[dim]Resolved alias '{original_target}' -> '{target}'[/dim]"
            )

        # Use the unified fuzzy matcher for all matching logic
        fuzzy_matcher = FuzzyMatcher(quadlet_manager=self)
        fuzzy_result = fuzzy_matcher.fuzzy_match_service_or_stack(target, command)

        if fuzzy_result == "CANCELLED":
            return None
        elif fuzzy_result:
            return fuzzy_result

        # Try adding .service extension for generic services as fallback
        potential_service = f"{target}.service"

        # Check if the service exists by trying to get its status
        cmd = ["sudo", "systemctl", "show", potential_service, "--property=LoadState"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and "LoadState=loaded" in result.stdout:
            return potential_service

        # If not found, return None
        return None

    def _suggest_similar_services(self, target: str) -> None:
        """Suggest similar service names when a service is not found"""
        all_services = list(self.quadlet_services.keys())

        # Also search systemd directory for additional matches
        systemd_matches = self._search_systemd_directory(target)
        all_services.extend(systemd_matches)

        # Remove duplicates
        all_services = list(set(all_services))

        # Find services that contain the target as a substring
        similar = [svc for svc in all_services if target.lower() in svc.lower()]

        if not similar:
            # Find services that start with the same prefix
            if "-" in target:
                prefix = target.split("-")[0]
                similar = [svc for svc in all_services if svc.startswith(prefix)]

        if similar:
            console.print(
                f"[yellow]Service '{target}' not found. Did you mean:[/yellow]"
            )
            for svc in similar[:5]:  # Show max 5 suggestions
                service_info = self._get_service_display_info(svc)
                console.print(f"  [cyan]{svc}[/cyan]{service_info}")
        else:
            console.print(
                f"[yellow]Service '{target}' not found. Available services:[/yellow]"
            )
            for svc in sorted(all_services)[:10]:  # Show first 10 services
                service_info = self._get_service_display_info(svc)
                console.print(f"  [cyan]{svc}[/cyan]{service_info}")
            if len(all_services) > 10:
                console.print(f"  [dim]... and {len(all_services) - 10} more[/dim]")

    def _handle_numeric_selection(self, selection: int) -> Optional[str]:
        """Handle numeric service selection from previous fuzzy match results"""
        if not self.last_fuzzy_matches:
            console.print(
                "[red]No previous service list to select from. Use 'pm log-anal <partial-name>' first.[/red]"
            )
            return None

        if selection < 1 or selection > len(self.last_fuzzy_matches):
            console.print(
                f"[red]Invalid selection '{selection}'. Choose 1-{len(self.last_fuzzy_matches)}[/red]"
            )
            return None

        # Get the selected service (1-based indexing)
        selected_service = self.last_fuzzy_matches[selection - 1]
        console.print(f"[dim]Selected: {selected_service}[/dim]")

        # Return the full service name
        if selected_service in self.quadlet_services:
            return self.quadlet_services[selected_service]
        elif selected_service in ["stack", "vllm-stack"]:
            return self.stack_target
        else:
            return f"{selected_service}.service"

    def start_service(self, target: str) -> bool:
        """Start a service or the stack target"""
        self._clear_auto_match_cache()

        # Check if target is already a resolved service name (skip fuzzy matching)
        if target in self.quadlet_services:
            service_name = self.quadlet_services[target]
        else:
            # Check if container file exists first
            exists, resolved_service = self._check_container_file_exists(
                target, "start"
            )
            if not exists:
                self._show_install_suggestion(target)
                return False

            # Use resolved service if available, otherwise try to find it
            service_name = resolved_service or self._find_service_name(target, "start")
            if not service_name:
                console.print(f"[red]Service '{target}' not found[/red]")
                return False
            elif service_name == "CANCELLED":
                return False

        # Handle stack targets by delegating to stack manager
        if service_name.startswith("STACK:"):
            from managers.stack_manager import StackManager

            stack_manager = StackManager(self)
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return stack_manager._start_stack(stack_name.replace("-stack", ""))

        # Get display name for the resolved service
        display_name = service_name
        if service_name.endswith(".service"):
            display_name = service_name[:-8]  # Remove .service suffix
        elif service_name.endswith(".target"):
            display_name = service_name[:-7]  # Remove .target suffix

        console.print(f"\n[green]Starting {display_name}...[/green]")

        cmd = ["sudo", "systemctl", "start", service_name]
        result = self._run_systemctl_command(cmd, f"start_{target}")

        if result.returncode == 0:
            console.print(f"  [green]Started {display_name}[/green]")
            return True
        else:
            console.print(f"[red]Failed to start {service_name}[/red]")

            # Trigger AI analysis for service start failure
            self._trigger_service_start_ai_analysis(
                target=target,
                service_name=service_name,
                start_command=" ".join(cmd),
                error_code=result.returncode,
                systemd_error=result.stderr.strip() if result.stderr else None,
            )

            return False

    def stop_service(
        self, target: str, force: bool = False, quiet: bool = False
    ) -> bool:
        """Stop a service or the stack target"""
        self._clear_auto_match_cache()

        # Check if container file exists first
        exists, resolved_service = self._check_container_file_exists(target, "stop")
        if not exists:
            if not quiet:
                self._show_install_suggestion(target)
            return False

        # Use resolved service if available, otherwise try to find it
        service_name = resolved_service or self._find_service_name(target, "stop")
        if not service_name:
            if not quiet:
                console.print(f"[red]Service '{target}' not found[/red]")
            return False
        elif service_name == "CANCELLED":
            return False

        # Handle stack targets by delegating to stack manager
        if service_name.startswith("STACK:"):
            from managers.stack_manager import StackManager

            stack_manager = StackManager(self)
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return stack_manager.down(stack_name)

        # Check if this is the 9b-thinking service to add spinner
        is_9b_thinking = (
            "9b-thinking" in target.lower()
            or "vllm-glm41-9b-thinking" in service_name.lower()
        )

        # First try normal stop
        cmd = ["sudo", "systemctl", "stop", service_name]

        if is_9b_thinking and not quiet:
            # Use spinner for 9b-thinking service
            from core.config import _verbose_enabled

            if _verbose_enabled:
                # In verbose mode, show the message without spinner
                console.print("\n[green]Stopping vllm-glm41-9b-thinking...[/green]")
                result = self._run_systemctl_command(cmd, f"stop_{target}", quiet=False)
            else:
                # In non-verbose mode, use spinner
                with safe_spinner("Stopping vllm-glm41-9b-thinking", verbose=False):
                    result = self._run_systemctl_command(
                        cmd, f"stop_{target}", quiet=True
                    )
        else:
            result = self._run_systemctl_command(cmd, f"stop_{target}", quiet=quiet)

        # Check if service and container are actually stopped
        def is_service_stopped():
            # Check systemd service status
            status_cmd = ["sudo", "systemctl", "is-active", service_name]
            status_result = subprocess.run(status_cmd, capture_output=True, text=True)
            service_inactive = status_result.returncode != 0

            # Also check if container is running (more reliable)
            container_name = target  # Use short name as container name

            # Check for exact name match
            container_cmd = [
                "podman",
                "ps",
                "-q",
                "--filter",
                f"name=^{container_name}$",
            ]
            container_result = subprocess.run(
                container_cmd, capture_output=True, text=True
            )
            exact_match_stopped = not container_result.stdout.strip()

            # Also check for partial name matches (in case of naming variations)
            partial_cmd = ["podman", "ps", "-q", "--filter", f"name={container_name}"]
            partial_result = subprocess.run(partial_cmd, capture_output=True, text=True)
            partial_match_stopped = not partial_result.stdout.strip()

            # Check for the full service name as container name too
            full_name = service_name.replace(".service", "") if service_name else target
            full_cmd = ["podman", "ps", "-q", "--filter", f"name={full_name}"]
            full_result = subprocess.run(full_cmd, capture_output=True, text=True)
            full_match_stopped = not full_result.stdout.strip()

            container_stopped = (
                exact_match_stopped and partial_match_stopped and full_match_stopped
            )

            return service_inactive and container_stopped

        if result.returncode == 0 and is_service_stopped():
            if not quiet:
                # Show short service name instead of full name
                display_name = (
                    target if target in self.quadlet_services else service_name
                )

                if is_9b_thinking:
                    # Special message for 9b-thinking service
                    console.print("\n[green]Stopping  vllm-glm41-9b-thinking[/green]")
                    console.print("  [green]stopped vllm-glm41-9b-thinking[/green]")
                else:
                    console.print(f"\n[green]Stopping  {display_name}[/green]")
                    console.print(f"  [green]Stopped {display_name}[/green]")
            return True
        else:
            # If normal stop fails or service is still running, try aggressive stopping
            if force and service_name.endswith(".service"):
                if not quiet:
                    console.print(f"[yellow]Force stopping {target}...[/yellow]")

                # Try kill with SIGTERM first
                kill_cmd = ["sudo", "systemctl", "kill", "-s", "TERM", service_name]
                self._run_systemctl_command(kill_cmd, f"kill_term_{target}", quiet=True)

                # Wait a moment and check
                import time

                time.sleep(1)

                if is_service_stopped():
                    if not quiet:
                        if is_9b_thinking:
                            console.print(
                                "\n[green]Stopping  vllm-glm41-9b-thinking[/green]"
                            )
                            console.print(
                                "  [green]stopped vllm-glm41-9b-thinking[/green]"
                            )
                        else:
                            console.print(f"\n[green]Stopping  {target}[/green]")
                            console.print(f"  [green]Stopped {target}[/green]")
                    return True

                # If still running, try SIGKILL
                if not quiet:
                    console.print("[yellow]Service stubborn, using SIGKILL...[/yellow]")
                kill_cmd = ["sudo", "systemctl", "kill", "-s", "KILL", service_name]
                self._run_systemctl_command(kill_cmd, f"kill_kill_{target}", quiet=True)

                # Wait and final check
                time.sleep(2)

                if is_service_stopped():
                    if not quiet:
                        if is_9b_thinking:
                            console.print(
                                "\n[green]Stopping  vllm-glm41-9b-thinking[/green]"
                            )
                            console.print(
                                "  [green]stopped vllm-glm41-9b-thinking (force killed)[/green]"
                            )
                        else:
                            console.print(f"\n[green]Stopping  {target}[/green]")
                            console.print(
                                f"  [green]Stopped {target} (force killed)[/green]"
                            )
                    return True

                # Last resort: try to kill the container directly
                if not quiet:
                    console.print("[yellow]Trying direct container kill...[/yellow]")

                # Find ALL containers that might be related
                container_names_to_try = [
                    target,
                    service_name.replace(".service", ""),
                ]

                containers_found = []
                for name in container_names_to_try:
                    find_cmd = [
                        "podman",
                        "ps",
                        "-a",
                        "--format",
                        "{{.Names}}",
                        "--filter",
                        f"name={name}",
                    ]
                    find_result = subprocess.run(
                        find_cmd, capture_output=True, text=True
                    )
                    if find_result.stdout.strip():
                        for container in find_result.stdout.strip().split("\n"):
                            if container and container not in containers_found:
                                containers_found.append(container)

                if not quiet and containers_found:
                    console.print(
                        f"[cyan]Found containers: {', '.join(containers_found)}[/cyan]"
                    )

                # Stop all found containers using systemctl --user (safer for Quadlet services)
                for actual_container_name in containers_found:
                    if not quiet:
                        console.print(
                            f"[yellow]Force stopping service: {actual_container_name}[/yellow]"
                        )

                    # Use sudo systemctl stop for safer Quadlet service management
                    service_name = f"{actual_container_name}.service"
                    stop_cmd = ["sudo", "systemctl", "stop", service_name]
                    verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
                    subprocess.run(stop_cmd, capture_output=True, text=True)

                    # Container removal is handled automatically by systemctl service lifecycle
                    if not quiet:
                        console.print(
                            f"[green]Service {service_name} stopped (container cleanup handled by systemctl)[/green]"
                        )

                # Wait and check if everything is stopped
                time.sleep(2)

                if is_service_stopped():
                    if not quiet:
                        if is_9b_thinking:
                            console.print(
                                "\n[green]Stopping  vllm-glm41-9b-thinking[/green]"
                            )
                            console.print(
                                "  [green]stopped vllm-glm41-9b-thinking (containers eliminated)[/green]"
                            )
                        else:
                            console.print(f"\n[green]Stopping  {target}[/green]")
                            console.print(
                                f"  [green]Stopped {target} (containers eliminated)[/green]"
                            )
                    return True
                elif containers_found and not quiet:
                    console.print(
                        f"[yellow]Killed {len(containers_found)} containers but service may still be active[/yellow]"
                    )

            if not quiet:
                console.print(f"[red]✗ Failed to stop {target}[/red]")
                console.print()  # Add newline
            return False

    def restart_service(self, target: str) -> bool:
        """Restart a service or the stack target"""
        self._clear_auto_match_cache()

        # Check if container file exists first
        exists, resolved_service = self._check_container_file_exists(target, "restart")
        if not exists:
            self._show_install_suggestion(target)
            return False

        # Use resolved service if available, otherwise try to find it
        service_name = resolved_service or self._find_service_name(target, "restart")
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False
        elif service_name == "CANCELLED":
            return False

        # Handle stack targets by delegating to stack manager
        if service_name.startswith("STACK:"):
            from managers.stack_manager import StackManager

            stack_manager = StackManager(self)
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return stack_manager._restart_stack(stack_name.replace("-stack", ""))

        cmd = ["sudo", "systemctl", "restart", service_name]
        result = self._run_systemctl_command(
            cmd, f"restart_{target}", suppress_errors=True
        )

        if result.returncode == 0:
            console.print(f"[green]Restarted {service_name}[/green]")
            return True
        else:
            return False

    def enable_service(self, target: str) -> bool:
        """Enable a service or the stack target to start at boot"""
        self._clear_auto_match_cache()

        # Check if container file exists first
        exists, resolved_service = self._check_container_file_exists(target, "enable")
        if not exists:
            self._show_install_suggestion(target)
            return False

        # Use resolved service if available, otherwise try to find it
        service_name = resolved_service or self._find_service_name(target, "enable")
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False
        elif service_name == "CANCELLED":
            return False

        # Handle stack targets by delegating to stack manager
        if service_name.startswith("STACK:"):
            from managers.stack_manager import StackManager

            stack_manager = StackManager(self)
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return stack_manager._enable_stack(stack_name.replace("-stack", ""))

        cmd = ["sudo", "systemctl", "enable", service_name]
        result = self._run_systemctl_command(cmd, f"enable_{target}")

        if result.returncode == 0:
            console.print(f"[green]Enabled {service_name}[/green]")
            return True
        else:
            console.print(f"[red]Failed to enable {service_name}[/red]")
            return False

    def disable_service(self, target: str) -> bool:
        """Disable a service or the stack target from starting at boot"""
        self._clear_auto_match_cache()

        # Check if container file exists first
        exists, resolved_service = self._check_container_file_exists(target, "disable")
        if not exists:
            self._show_install_suggestion(target)
            return False

        # Use resolved service if available, otherwise try to find it
        service_name = resolved_service or self._find_service_name(target, "disable")
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False
        elif service_name == "CANCELLED":
            return False

        # Handle stack targets by delegating to stack manager
        if service_name.startswith("STACK:"):
            from managers.stack_manager import StackManager

            stack_manager = StackManager(self)
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return stack_manager._disable_stack(stack_name.replace("-stack", ""))

        cmd = ["sudo", "systemctl", "disable", service_name]
        result = self._run_systemctl_command(cmd, f"disable_{target}")

        if result.returncode == 0:
            console.print(f"[green]Disabled {service_name}[/green]")
            return True
        else:
            console.print(f"[red]Failed to disable {service_name}[/red]")
            return False

    def reload_daemon(self) -> bool:
        """Reload systemd user daemon (after changing unit files)"""
        cmd = ["sudo", "systemctl", "daemon-reload"]
        result = self._run_systemctl_command(cmd, "daemon_reload")

        if result.returncode == 0:
            return True
        else:
            console.print("[red]Failed to reload systemd user daemon[/red]")
            return False

    def show_logs(self, target: str, follow: bool = False) -> bool:
        """Show logs for a service"""
        self._clear_auto_match_cache()

        # Check if container file exists first
        exists, resolved_service = self._check_container_file_exists(target, "logs")
        if not exists:
            self._show_install_suggestion(target)
            return False

        # Use resolved service if available, otherwise try to find it
        service_name = resolved_service or self._find_service_name(target, "logs")
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False
        elif service_name == "CANCELLED":
            return False

        # Handle stack targets by delegating to stack manager
        if service_name.startswith("STACK:"):
            from managers.stack_manager import StackManager

            stack_manager = StackManager(self)
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            stack_manager._show_stack_logs(stack_name.replace("-stack", ""), follow)
            return True

        # Get container name for podman logs (use target as container name)
        container_name = target

        # First show podman logs
        console.print("\n[bold cyan]=== Podman Container Logs ===[/bold cyan]")
        podman_cmd = ["sudo", "podman", "logs", container_name]
        verbose_print(f"[cyan]exec: {' '.join(podman_cmd)}[/cyan]")

        try:
            podman_result = subprocess.run(
                podman_cmd, capture_output=True, text=True, timeout=30
            )
            if podman_result.returncode == 0:
                if podman_result.stdout.strip():
                    console.print(podman_result.stdout)
                else:
                    console.print("[dim]No podman logs available[/dim]")
            else:
                console.print(
                    f"[yellow]Podman logs not available: {podman_result.stderr.strip()}[/yellow]"
                )
        except subprocess.TimeoutExpired:
            console.print("[yellow]Podman logs command timed out[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Could not get podman logs: {e}[/yellow]")

        # Then show systemd/journalctl logs
        console.print("\n[bold cyan]=== Systemd Service Logs ===[/bold cyan]")
        cmd = ["sudo", "journalctl", "-u", service_name]
        if follow:
            cmd.append("-f")

        verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            if follow:
                console.print("[dim]Press Ctrl+C to stop following logs[/dim]")
                subprocess.run(cmd)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    console.print(result.stdout)
                else:
                    console.print(
                        f"[red]Failed to get logs: {result.stderr.strip()}[/red]"
                    )
                    return False
            return True
        except KeyboardInterrupt:
            console.print("\n[yellow]Log following stopped[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]Error showing logs: {e}[/red]")
            return False
