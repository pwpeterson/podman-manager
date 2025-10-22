"""Core QuadletManager class for managing vLLM containers as systemd quadlets."""

import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from config import console, verbose_print  # pyright: ignore[reportAttributeAccessIssue]
from fuzzy_matcher import FuzzyMatcher


class QuadletManager:
    """Main class for managing vLLM containers as systemd quadlets with Rich UI"""

    def __init__(self, project_name="vllm"):
        # Project name for display purposes
        self.project_name = project_name

        # Quadlets directory path (standard systemd location only)
        self.quadlets_dir = Path.home() / ".config" / "containers" / "systemd"

        # Services managed as quadlets (will be auto-discovered)
        self.quadlet_services = {}
        self.stack_services = {}  # Maps stack names to their services

        # Stack target for managing all services together
        self.stack_target = "vllm-stack.target"

        # Auto-discover all quadlet services and stacks
        self._discover_quadlet_services()

        # Store last fuzzy match results for numeric selection
        self.last_fuzzy_matches = []
        self.cache_file = Path.home() / ".pm_fuzzy_cache"

        logger.debug("Initializing QuadletManager for quadlet services")
        self._validate_prerequisites()
        self._load_fuzzy_cache()

    def _validate_prerequisites(self) -> bool:
        """Validate that required tools exist"""
        logger.debug("Starting prerequisites validation")

        # Check systemctl
        if not self._command_exists("systemctl"):
            logger.error("Required command 'systemctl' not found!")
            return False

        # Check if we can run systemctl --user
        result = subprocess.run(
            ["systemctl", "--user", "--help"], capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error("'systemctl --user' is not available!")
            console.print("[dim]Make sure systemd user services are enabled[/dim]")
            return False

        logger.success("Prerequisites validation complete")
        return True

    def _discover_quadlet_services(self) -> None:
        """Auto-discover all quadlet services from both source and installed directories"""
        # Primary source directory
        self.quadlets_source_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")

        # Track installation status for each service
        self.service_status = {}  # service_name -> {'installed': bool, 'source': bool}

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
                info_parts.append("[yellow](available)[/yellow]")
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
            f"[yellow]Required container file is missing, run pm install {target}[/yellow]"
        )

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        result = subprocess.run(["which", command], capture_output=True)
        exists = result.returncode == 0
        logger.debug("Command '{}' exists: {}", command, exists)
        return exists

    def _run_systemctl_command(
        self,
        cmd: List[str],
        action: str,
        suppress_errors: bool = False,
        quiet: bool = False,
    ) -> subprocess.CompletedProcess:
        """Execute a systemctl command and return the result"""
        from config import _verbose_enabled

        # Display command in a subtle way (unless quiet)
        if not quiet:
            verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        # Use loguru's context binding for structured logging
        with logger.contextualize(action=action, command=" ".join(cmd)):
            logger.info("Executing systemctl command: {}", " ".join(cmd))

            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True)
            execution_time = time.time() - start_time

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
                        console.print("[dim]Try: systemctl --user daemon-reload[/dim]")
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

                            # Show detailed error in verbose mode
                            if _verbose_enabled:
                                console.print("[red]❌ Complete command error:[/red]")
                                console.print("[dim]" + "─" * 60 + "[/dim]")
                                for line in result.stderr.strip().split("\n"):
                                    if line.strip():
                                        console.print(f"[red]{line}[/red]")
                                console.print("[dim]" + "─" * 60 + "[/dim]")
                            else:
                                # Show brief error in non-verbose mode
                                console.print(
                                    f"[red]Command failed: {result.stderr.strip()}[/red]"
                                )
                else:
                    logger.debug(
                        "Command failed with code {} in {:.2f}s (suppressed)",
                        result.returncode,
                        execution_time,
                    )
                    # Even in suppressed mode, show detailed error if verbose
                    if _verbose_enabled and result.stderr:
                        console.print("[yellow]Suppressed error details:[/yellow]")
                        console.print("[dim]" + "─" * 60 + "[/dim]")
                        for line in result.stderr.strip().split("\n"):
                            if line.strip():
                                console.print(f"[yellow]{line}[/yellow]")
                        console.print("[dim]" + "─" * 60 + "[/dim]")

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
            "systemctl",
            "--user",
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

        # PRIORITY: Check for stack names first (before individual services)
        # Check if it's any discovered stack name (exact match)
        if target in self.stack_services:
            return f"STACK:{target}"

        # Check if target ends with -stack and exists in our discovered stacks
        if target.endswith("-stack") and target in self.stack_services:
            return f"STACK:{target}"

        # Handle stack name mapping (shortened names) - ENHANCED
        if not target.endswith("-stack"):
            stack_variant = f"{target}-stack"
            if stack_variant in self.stack_services:
                return f"STACK:{stack_variant}"

            # Also check if any stack starts with the target name
            for stack_name in self.stack_services.keys():
                if stack_name.startswith(f"{target}-"):
                    return f"STACK:{stack_name}"

        # Check if it's a short name in quadlet services
        if target in self.quadlet_services:
            return self.quadlet_services[target]

        # Check if it's already a full service name in quadlet services
        if target in self.quadlet_services.values():
            return target

        # Check if it's any stack target
        if target == "stack" or target == "vllm-stack" or target == self.stack_target:
            return self.stack_target

        # For any other service, try as-is first
        if target.endswith(".service") or target.endswith(".target"):
            return target

        # Try fuzzy matching for partial names using unified matcher
        fuzzy_matcher = FuzzyMatcher(quadlet_manager=self)
        fuzzy_result = fuzzy_matcher.fuzzy_match_service_or_stack(target, command)
        if fuzzy_result == "CANCELLED":
            return None
        elif fuzzy_result:
            return fuzzy_result

        # Try adding .service extension for generic services
        potential_service = f"{target}.service"

        # Check if the service exists by trying to get its status
        cmd = ["systemctl", "--user", "show", potential_service, "--property=LoadState"]
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

    def _fuzzy_match_service(self, partial_name: str) -> Optional[str]:
        """Find service using fuzzy matching for partial names"""

        # Get all available service names (short names)
        all_services = list(self.quadlet_services.keys())

        # Add stack aliases
        all_services.extend(["stack", "vllm-stack"])

        # Also search the systemd directory for .container files that match
        systemd_matches = self._search_systemd_directory(partial_name)
        all_services.extend(systemd_matches)

        # Remove duplicates while preserving order
        seen = set()
        unique_services = []
        for svc in all_services:
            if svc not in seen:
                seen.add(svc)
                unique_services.append(svc)
        all_services = unique_services

        # Find exact matches first
        exact_matches = [svc for svc in all_services if svc == partial_name]
        if len(exact_matches) == 1:
            if exact_matches[0] in self.quadlet_services:
                return self.quadlet_services[exact_matches[0]]
            elif exact_matches[0] in ["stack", "vllm-stack"]:
                return self.stack_target

        # Find partial matches (case-insensitive)
        partial_matches = [
            svc for svc in all_services if partial_name.lower() in svc.lower()
        ]

        # If no partial matches, try prefix matching
        if not partial_matches:
            partial_matches = [
                svc
                for svc in all_services
                if svc.lower().startswith(partial_name.lower())
            ]

        # If still no matches, try fuzzy matching with edit distance
        if not partial_matches:

            def levenshtein_distance(s1: str, s2: str) -> int:
                """Calculate Levenshtein distance between two strings"""
                if len(s1) < len(s2):
                    return levenshtein_distance(s2, s1)
                if len(s2) == 0:
                    return len(s1)

                previous_row = list(range(len(s2) + 1))
                for i, c1 in enumerate(s1):
                    current_row = [i + 1]
                    for j, c2 in enumerate(s2):
                        insertions = previous_row[j + 1] + 1
                        deletions = current_row[j] + 1
                        substitutions = previous_row[j] + (c1 != c2)
                        current_row.append(min(insertions, deletions, substitutions))
                    previous_row = current_row
                return previous_row[-1]

            # Find services with small edit distance (max 2 for reasonable matches)
            fuzzy_matches = []
            for svc in all_services:
                distance = levenshtein_distance(partial_name.lower(), svc.lower())
                if (
                    distance <= 2 and len(partial_name) >= 3
                ):  # Only for reasonable length inputs
                    fuzzy_matches.append((svc, distance))

            # Sort by distance and take best matches
            fuzzy_matches.sort(key=lambda x: x[1])
            partial_matches = [match[0] for match in fuzzy_matches[:5]]  # Top 5 matches

        if len(partial_matches) == 1:
            # Single match found
            matched_service = partial_matches[0]
            if matched_service in self.quadlet_services:
                console.print(
                    f"[dim]Matched '{partial_name}' to '{matched_service}'[/dim]"
                )
                return self.quadlet_services[matched_service]
            elif matched_service in ["stack", "vllm-stack"]:
                console.print(
                    f"[dim]Matched '{partial_name}' to '{matched_service}'[/dim]"
                )
                return self.stack_target
        elif len(partial_matches) > 1:
            # Multiple matches - store them and show clean selection menu
            self.last_fuzzy_matches = partial_matches
            self._save_fuzzy_cache()

            # Show clean numbered list starting from 1
            console.print(f"[yellow]Multiple services match '{partial_name}':[/yellow]")

            for i, service in enumerate(partial_matches, 1):
                # Show additional info about the service
                service_info = self._get_service_display_info(service)
                console.print(f"[cyan]{i}.[/cyan] {service}{service_info}")

            # Interactive selection
            try:
                choice = input(
                    "\nSelect service (1-{}) or press Enter to cancel: ".format(
                        len(partial_matches)
                    )
                ).strip()

                if not choice:
                    return None

                choice_num = int(choice)

                if 1 <= choice_num <= len(partial_matches):
                    selected_service = partial_matches[choice_num - 1]

                    # Return the full service name
                    if selected_service in self.quadlet_services:
                        return self.quadlet_services[selected_service]
                    elif selected_service in ["stack", "vllm-stack"]:
                        return self.stack_target
                    else:
                        return f"{selected_service}.service"
                else:
                    return None
            except (ValueError, KeyboardInterrupt):
                return None

        return None  # No matches found

    def start_service(self, target: str) -> bool:
        """Start a service or the stack target"""
        self._clear_auto_match_cache()

        # Check if container file exists first
        exists, resolved_service = self._check_container_file_exists(target, "start")
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

        cmd = ["systemctl", "--user", "start", service_name]
        result = self._run_systemctl_command(cmd, f"start_{target}")

        if result.returncode == 0:
            console.print(f"[green]Started {service_name}[/green]")
            return True
        else:
            console.print(f"[red]Failed to start {service_name}[/red]")
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

        # First try normal stop
        cmd = ["systemctl", "--user", "stop", service_name]
        result = self._run_systemctl_command(cmd, f"stop_{target}", quiet=quiet)

        # Check if service and container are actually stopped
        def is_service_stopped():
            # Check systemd service status
            status_cmd = ["systemctl", "--user", "is-active", service_name]
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
            full_name = service_name.replace(".service", "")
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
                console.print(f"[green]{display_name} stopped[/green]")
            return True
        else:
            # If normal stop fails or service is still running, try aggressive stopping
            if force and service_name.endswith(".service"):
                if not quiet:
                    console.print(f"[yellow]Force stopping {target}...[/yellow]")

                # Try kill with SIGTERM first
                kill_cmd = ["systemctl", "--user", "kill", "-s", "TERM", service_name]
                self._run_systemctl_command(kill_cmd, f"kill_term_{target}", quiet=True)

                # Wait a moment and check
                import time

                time.sleep(1)

                if is_service_stopped():
                    if not quiet:
                        console.print(f"[green]{target} stopped[/green]")
                    return True

                # If still running, try SIGKILL
                if not quiet:
                    console.print("[yellow]Service stubborn, using SIGKILL...[/yellow]")
                kill_cmd = ["systemctl", "--user", "kill", "-s", "KILL", service_name]
                self._run_systemctl_command(kill_cmd, f"kill_kill_{target}", quiet=True)

                # Wait and final check
                time.sleep(2)

                if is_service_stopped():
                    if not quiet:
                        console.print(f"[green]{target} stopped (force killed)[/green]")
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

                # Kill all found containers
                for actual_container_name in containers_found:
                    if not quiet:
                        console.print(
                            f"[yellow]Killing container: {actual_container_name}[/yellow]"
                        )

                    # Try kill first
                    container_kill_cmd = ["podman", "kill", actual_container_name]
                    subprocess.run(container_kill_cmd, capture_output=True, text=True)

                    # Try stop with force
                    container_stop_cmd = [
                        "podman",
                        "stop",
                        "-t",
                        "1",
                        actual_container_name,
                    ]
                    subprocess.run(container_stop_cmd, capture_output=True, text=True)

                    # Force remove
                    rm_cmd = ["podman", "rm", "-f", actual_container_name]
                    subprocess.run(rm_cmd, capture_output=True, text=True)

                # Wait and check if everything is stopped
                time.sleep(2)

                if is_service_stopped():
                    if not quiet:
                        console.print(
                            f"[green]{target} stopped (containers eliminated)[/green]"
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

        cmd = ["systemctl", "--user", "restart", service_name]
        result = self._run_systemctl_command(cmd, f"restart_{target}")

        if result.returncode == 0:
            console.print(f"[green]Restarted {service_name}[/green]")
            return True
        else:
            console.print(f"[red]Failed to restart {service_name}[/red]")
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

        cmd = ["systemctl", "--user", "enable", service_name]
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

        cmd = ["systemctl", "--user", "disable", service_name]
        result = self._run_systemctl_command(cmd, f"disable_{target}")

        if result.returncode == 0:
            console.print(f"[green]Disabled {service_name}[/green]")
            return True
        else:
            console.print(f"[red]Failed to disable {service_name}[/red]")
            return False

    def reload_daemon(self) -> bool:
        """Reload systemd user daemon (after changing unit files)"""
        cmd = ["systemctl", "--user", "daemon-reload"]
        result = self._run_systemctl_command(cmd, "daemon_reload")

        if result.returncode == 0:
            return True
        else:
            console.print("[red]Failed to reload systemd user daemon[/red]")
            return False

    def show_logs(self, target: str, follow: bool = False, lines: int = 100) -> bool:
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

        cmd = ["journalctl", "--user", "-u", service_name, "-n", str(lines)]
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
