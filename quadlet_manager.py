"""Core QuadletManager class for managing vLLM containers as systemd quadlets."""

import subprocess
import time
from typing import Dict, List, Optional

from loguru import logger

from config import console


class QuadletManager:
    """Main class for managing vLLM containers as systemd quadlets with Rich UI"""

    def __init__(self, project_name="vllm"):
        # Services managed as quadlets
        self.quadlet_services = {
            # vLLM services
            "vllm-qwen25": "vllm-qwen25-coder-32b-instruct-awq.service",
            "vllm-proxy": "vllm-proxy.service",
            "vllm-delegator": "vllm-delegator-mcp.service",
            # Taskflow services
            "taskflow-frontend": "taskflow-frontend.service",
            "taskflow-backend": "taskflow-backend.service",
        }

        # Stack target for managing all services together
        self.stack_target = "vllm-stack.target"

        # Project name for display purposes
        self.project_name = project_name

        logger.debug("Initializing QuadletManager for vLLM services")
        self._validate_prerequisites()

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
        # Display command in a subtle way (unless quiet)
        if not quiet:
            console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

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
            else:
                if not suppress_errors:
                    logger.error(
                        "Command failed with code {} in {:.2f}s",
                        result.returncode,
                        execution_time,
                    )
                    if result.stderr:
                        logger.error("Error output: {}", result.stderr)
                        console.print(
                            f"[red]Command failed: {result.stderr.strip()}[/red]"
                        )
                else:
                    logger.debug(
                        "Command failed with code {} in {:.2f}s (suppressed)",
                        result.returncode,
                        execution_time,
                    )

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

    def _find_service_name(self, target: str) -> Optional[str]:
        """Find the full service name from a target (short name or full name)"""
        # Check if it's a numeric selection (e.g., "1", "2", etc.)
        if target.isdigit():
            return self._handle_numeric_selection(int(target))

        # Check if it's a short name in quadlet services
        if target in self.quadlet_services:
            return self.quadlet_services[target]

        # Check if it's already a full service name in quadlet services
        if target in self.quadlet_services.values():
            return target

        # Check if it's the stack target
        if target == "stack" or target == "vllm-stack" or target == self.stack_target:
            return self.stack_target

        # For any other service, try as-is first
        if target.endswith(".service") or target.endswith(".target"):
            return target

        # Try fuzzy matching for partial names
        fuzzy_result = self._fuzzy_match_service(target)
        if fuzzy_result:
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

    def _handle_numeric_selection(self, selection: int) -> Optional[str]:
        """Handle numeric service selection from previous fuzzy match results"""
        # This is a simplified approach - in a real implementation, you'd want to
        # store the last fuzzy match results in a class variable or cache
        console.print(
            f"[red]Numeric selection '{selection}' not supported in this context[/red]"
        )
        console.print("[dim]Please use the full service name from the list above[/dim]")
        return None

    def _fuzzy_match_service(self, partial_name: str) -> Optional[str]:
        """Find service using fuzzy matching for partial names"""
        from rich.table import Table

        # Get all available service names (short names)
        all_services = list(self.quadlet_services.keys())

        # Add stack aliases
        all_services.extend(["stack", "vllm-stack"])

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
            # Multiple matches - show selection menu
            console.print(f"[yellow]Multiple services match '{partial_name}':[/yellow]")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("#", style="cyan", width=3)
            table.add_column("Service", style="green")
            table.add_column("Full Name", style="dim")

            for i, service in enumerate(partial_matches, 1):
                if service in self.quadlet_services:
                    full_name = self.quadlet_services[service]
                elif service in ["stack", "vllm-stack"]:
                    full_name = self.stack_target
                else:
                    full_name = service
                table.add_row(str(i), service, full_name)

            console.print(table)
            console.print(
                "[cyan]Please specify the full service name or use the number prefix:[/cyan]"
            )

            # Show example commands
            for i, service in enumerate(partial_matches, 1):
                console.print(f"  [dim]{i}.[/dim] [cyan]pm logs {service}[/cyan]")

            return None  # Let user choose

        return None  # No matches found

    def start_service(self, target: str) -> bool:
        """Start a service or the stack target"""
        service_name = self._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
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
        service_name = self._find_service_name(target)
        if not service_name:
            if not quiet:
                console.print(f"[red]Service '{target}' not found[/red]")
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
                console.print(f"[green]✓ {display_name}[/green]")
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
                        console.print(f"[green]✓ {target}[/green]")
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
                        console.print(f"[green]✓ {target} (force killed)[/green]")
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
                            f"[green]✓ {target} (containers eliminated)[/green]"
                        )
                    return True
                elif containers_found and not quiet:
                    console.print(
                        f"[yellow]Killed {len(containers_found)} containers but service may still be active[/yellow]"
                    )

            if not quiet:
                console.print(f"[red]✗ Failed to stop {target}[/red]")
            return False

    def restart_service(self, target: str) -> bool:
        """Restart a service or the stack target"""
        service_name = self._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
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
        service_name = self._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
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
        service_name = self._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
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
            console.print("[green]Systemd user daemon reloaded[/green]")
            return True
        else:
            console.print("[red]Failed to reload systemd user daemon[/red]")
            return False

    def show_logs(self, target: str, follow: bool = False, lines: int = 100) -> bool:
        """Show logs for a service"""
        service_name = self._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False

        cmd = ["journalctl", "--user", "-u", service_name, "-n", str(lines)]
        if follow:
            cmd.append("-f")

        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

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
