"""Quadlet Stack Installation Module

Integrated installer for quadlet stacks that follows the existing codebase patterns.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from rich.table import Table

from config import console, verbose_print
from fuzzy_matcher import FuzzyMatcher


class QuadletInstaller:
    """Quadlet Stack Installation Manager

    Integrates with the existing codebase architecture and console patterns.
    """

    def __init__(self):
        """Initialize the installer with quadlet base directory."""
        self.quadlet_base_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")

        # Validate base directory exists
        if not self.quadlet_base_dir.exists():
            console.print(
                f"[red]Quadlet base directory not found: {self.quadlet_base_dir}[/red]"
            )
            raise FileNotFoundError(
                f"Quadlet base directory not found: {self.quadlet_base_dir}"
            )

    def _print_status(self, message: str) -> None:
        """Print status message using consistent formatting."""
        console.print(f"[blue]{message}[/blue]")

    def _print_success(self, message: str) -> None:
        """Print success message using consistent formatting."""
        console.print(f"[green]{message}[/green]")

    def _print_warning(self, message: str) -> None:
        """Print warning message using consistent formatting."""
        console.print(f"[yellow]{message}[/yellow]")

    def _print_error(self, message: str) -> None:
        """Print error message using consistent formatting."""
        console.print(f"[red]{message}[/red]")

    def discover_stacks(self) -> List[str]:
        """Discover available stacks in the quadlet directory."""
        stacks = []

        for item in self.quadlet_base_dir.iterdir():
            if (
                item.is_dir()
                and item.name not in ["scripts", "docs"]
                and self._has_quadlet_files(item)
            ):
                stacks.append(item.name)

        return sorted(stacks)

    def _has_quadlet_files(self, directory: Path) -> bool:
        """Check if directory contains quadlet files (excluding .disabled files)."""
        quadlet_extensions = [".container", ".network", ".volume"]

        for ext in quadlet_extensions:
            for file in directory.glob(f"*{ext}"):
                if not file.name.endswith(".disabled"):
                    return True
        return False

    def get_stack_files(self, stack_name: str) -> List[str]:
        """Get quadlet files for a stack."""
        stack_dir = self.quadlet_base_dir / stack_name

        if not stack_dir.exists():
            return []

        files = []
        quadlet_extensions = [".container", ".network", ".volume"]

        for ext in quadlet_extensions:
            for file in stack_dir.glob(f"*{ext}"):
                if not file.name.endswith(".disabled"):
                    files.append(file.name)

        return sorted(files)

    def get_service_names(self, stack_name: str) -> List[str]:
        """Get service names from quadlet files."""
        stack_dir = self.quadlet_base_dir / stack_name

        if not stack_dir.exists():
            return []

        services = []
        for file in stack_dir.glob("*.container"):
            if not file.name.endswith(".disabled"):
                services.append(file.stem)  # Remove .container extension

        return sorted(services)

    def find_service_in_stacks(self, service_name: str) -> Optional[tuple[str, str]]:
        """Find which stack contains a specific service.

        Returns:
            Tuple of (stack_name, container_file) if found, None otherwise
        """
        available_stacks = self.discover_stacks()

        for stack in available_stacks:
            stack_dir = self.quadlet_base_dir / stack
            # Look for service.container file
            container_file = f"{service_name}.container"
            container_path = stack_dir / container_file

            if container_path.exists() and not container_file.endswith(".disabled"):
                return (stack, container_file)

        return None

    def validate_stack_or_service(self, name: str) -> tuple[bool, str, Optional[str]]:
        """Validate that a stack or service exists with fuzzy matching support.

        Returns:
            Tuple of (is_valid, resolved_stack_name, service_file_if_service)
        """
        # First try exact match as a stack
        stack_dir = self.quadlet_base_dir / name
        if stack_dir.exists():
            files = self.get_stack_files(name)
            if files:
                return (True, name, None)  # It's a valid stack

        # Try exact match as a service within stacks
        service_result = self.find_service_in_stacks(name)
        if service_result:
            stack_name, container_file = service_result
            return (True, stack_name, container_file)  # It's a valid service

        # Use unified fuzzy matcher
        fuzzy_matcher = FuzzyMatcher(quadlet_installer=self)
        fuzzy_result = fuzzy_matcher.fuzzy_match_service_or_stack(name)

        if fuzzy_result:
            # Check if it's a service (has .service extension) or stack
            if fuzzy_result.endswith(".service"):
                # It's a service - find which stack it belongs to
                service_name = fuzzy_result.replace(".service", "")
                service_result = self.find_service_in_stacks(service_name)
                if service_result:
                    stack_name, container_file = service_result
                    return (True, stack_name, container_file)
            else:
                # It's a stack
                return (True, fuzzy_result, None)
        elif fuzzy_result == "CANCELLED":
            # User cancelled selection - don't show error message
            return (False, name, None)
        elif fuzzy_result is None:
            # No matches found
            self._print_error(f"Stack or service '{name}' not found")
            return (False, name, None)

        # This shouldn't happen, but handle it just in case
        self._print_error(f"Stack or service '{name}' not found")

        return (False, name, None)

    def validate_stack(self, stack_name: str) -> bool:
        """Validate that a stack exists and has files."""
        is_valid, resolved_stack, service_file = self.validate_stack_or_service(
            stack_name
        )
        return (
            is_valid and service_file is None
        )  # Only valid if it's actually a stack, not a service

    def check_systemd_user_session(self) -> bool:
        """Check systemd user session health."""
        self._print_success("Checking systemd user session health...")

        try:
            # Check if systemd user session is running
            cmd = ["systemctl", "--user", "status"]
            verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                self._print_warning("Systemd user session appears to be disconnected")
                self._print_status("This may cause daemon-reload to fail")
                self._print_status(
                    "Consider restarting your user session if issues persist"
                )
                return False

            # Check if we can communicate with systemd
            cmd = [
                "systemctl",
                "--user",
                "list-units",
                "--type=service",
                "--state=loaded",
            ]
            verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                self._print_warning("Cannot communicate with systemd user session")
                self._print_status("Transport endpoint may be disconnected")
                return False

            self._print_success("Systemd user session is healthy")
            return True

        except subprocess.TimeoutExpired:
            self._print_warning("Systemd health check timed out")
            return False
        except Exception as e:
            self._print_warning(f"Systemd health check failed: {e}")
            return False

    def install_stack(
        self, name: str, target_dir: Optional[Path] = None, use_sudo: bool = False
    ) -> bool:
        """Install stack or service to target directory.

        Args:
            name: Name of the stack or service to install
            target_dir: Target directory (defaults to user systemd directory)
            use_sudo: Whether to use sudo for system installation

        Returns:
            True if installation succeeded, False otherwise
        """
        if target_dir is None:
            target_dir = Path.home() / ".config/containers/systemd"

        # Validate and determine if it's a stack or service
        is_valid, resolved_stack, service_file = self.validate_stack_or_service(name)
        if not is_valid:
            return False

        # Additional check to ensure we don't proceed with invalid stack names
        if resolved_stack == "CANCELLED" or resolved_stack is None:
            return False

        stack_dir = self.quadlet_base_dir / resolved_stack

        if service_file:
            # Installing a single service - only install the specific service file
            files = [service_file]
            install_type = "service"
            display_name = name

            # Check if service might need dependencies (networks/volumes)
            stack_files = self.get_stack_files(resolved_stack)
            network_files = [f for f in stack_files if f.endswith(".network")]
            volume_files = [f for f in stack_files if f.endswith(".volume")]

            if network_files or volume_files:
                console.print(
                    f"[yellow]Service {name} may require shared resources:[/yellow]"
                )
                if network_files:
                    console.print(f"  Networks: {', '.join(network_files)}")
                if volume_files:
                    console.print(f"  Volumes: {', '.join(volume_files)}")
                console.print(
                    "[yellow]Installing only the service file. Install the full stack if needed.[/yellow]"
                )
        else:
            # Installing entire stack
            files = self.get_stack_files(resolved_stack)
            install_type = "stack"
            display_name = resolved_stack

        # Print installation message with cyan path
        console.print(
            f"[green]Installing {display_name} {install_type} to [cyan]{target_dir}[/cyan][/green]"
        )

        try:
            # Create target directory
            if use_sudo:
                cmd = ["sudo", "mkdir", "-p", str(target_dir)]
                verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                subprocess.run(cmd, check=True)
                verbose_print(f"    Updated: [cyan]{target_dir}[/cyan]")
            else:
                verbose_print("  [cyan]exec: mkdir -p .../systemd[/cyan]")
                target_dir.mkdir(parents=True, exist_ok=True)
                verbose_print(f"    Updated: [cyan]{target_dir}[/cyan]")

            # Copy quadlet files
            for file in files:
                console.print(f"[green]Installing {file}[/green]")
                source_file = stack_dir / file
                target_file = target_dir / file

                if use_sudo:
                    cmd = ["sudo", "cp", str(source_file), str(target_file)]
                    verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                    subprocess.run(cmd, check=True)
                    verbose_print(f"    Copied: {file}")
                else:
                    verbose_print(
                        f"  [cyan]exec: cp .../{file} .../systemd/{file}[/cyan]"
                    )
                    shutil.copy2(source_file, target_file)
                    verbose_print(f"    Copied: {file}")

            # Set proper permissions
            if use_sudo:
                for file in files:
                    cmd = ["sudo", "chmod", "644", str(target_dir / file)]
                    verbose_print(f"  [cyan]exec: chmod 644 .../systemd/{file}[/cyan]")
                    subprocess.run(cmd, check=True)
            else:
                for file in files:
                    verbose_print(f"  [cyan]exec: chmod 644 .../systemd/{file}[/cyan]")
                    (target_dir / file).chmod(0o644)

            # Reload systemd
            self._print_success("Reloading systemd daemon...")
            if use_sudo:
                cmd = ["sudo", "systemctl", "daemon-reload"]
                verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self._print_error(
                        "Failed to reload system daemon. You may need to manually run: sudo systemctl daemon-reload"
                    )
                    return False
            else:
                cmd = ["systemctl", "--user", "daemon-reload"]
                verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self._print_warning(
                        "Failed to reload user daemon (systemd connection issue)"
                    )
                    self._print_status("Attempting to restart user systemd session...")

                    # Try to reset failed units
                    reset_cmd = ["systemctl", "--user", "reset-failed"]
                    verbose_print(f"  [cyan]exec: {' '.join(reset_cmd)}[/cyan]")
                    reset_result = subprocess.run(
                        reset_cmd,
                        capture_output=True,
                        text=True,
                    )
                    if reset_result.returncode == 0:
                        self._print_status(
                            "Reset failed units, retrying daemon-reload..."
                        )
                        retry_cmd = ["systemctl", "--user", "daemon-reload"]
                        verbose_print(f"  [cyan]exec: {' '.join(retry_cmd)}[/cyan]")
                        retry_result = subprocess.run(
                            retry_cmd,
                            capture_output=True,
                            text=True,
                        )
                        if retry_result.returncode == 0:
                            self._print_success(
                                "Successfully reloaded daemon after reset"
                            )
                        else:
                            self._print_warning(
                                "Daemon reload still failing. Manual intervention may be required."
                            )
                            self._print_status("Try: systemctl --user daemon-reload")
                            self._print_status(
                                f"Or restart user session: loginctl terminate-user {os.getenv('USER')}"
                            )
                    else:
                        self._print_warning("Could not reset systemd user session")
                        self._print_status(
                            "Manual daemon reload required: systemctl --user daemon-reload"
                        )
                        self._print_status(
                            f"Or restart user session: loginctl terminate-user {os.getenv('USER')}"
                        )

            # Refresh PM service discovery if available
            self._refresh_pm_discovery(display_name)

            # Show next steps
            if service_file:
                # For single service, show service-specific next steps
                self._show_service_next_steps(name, use_sudo)
            else:
                # For stack, show full stack next steps
                self._show_next_steps(resolved_stack, use_sudo)

            return True

        except subprocess.CalledProcessError as e:
            self._print_error(f"Installation failed: {e}")
            return False
        except Exception as e:
            self._print_error(f"Unexpected error during installation: {e}")
            return False

    def _refresh_pm_discovery(self, display_name: str) -> None:
        """Refresh PM service discovery."""
        pm_locations = [
            "/home/pwp/srv/apps/podman_manager/pm",
            shutil.which("pm"),
            Path.home() / "srv/apps/podman_manager/pm",
            "./pm",
        ]

        pm_script = None
        for location in pm_locations:
            if location and Path(location).is_file() and os.access(location, os.X_OK):
                pm_script = location
                break

        if pm_script:
            self._print_success("Refreshing PM service discovery...")
            try:
                cmd = [str(pm_script), "refresh"]
                verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    # Restart podman service to pick up new quadlet files
                    self._print_success("Restarting podman service...")
                    restart_cmd = ["systemctl", "--user", "restart", "podman.service"]
                    verbose_print(f"  [cyan]exec: {' '.join(restart_cmd)}[/cyan]")
                    restart_result = subprocess.run(
                        restart_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if restart_result.returncode != 0:
                        self._print_warning(
                            "Failed to restart podman service - you may need to run: systemctl --user restart podman.service"
                        )
                else:
                    self._print_warning(
                        "Failed to refresh PM service discovery (PM may not be available)"
                    )
            except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
                self._print_warning(f"Failed to refresh PM service discovery: {e}")
        else:
            self._print_status("PM not found, skipping service discovery refresh")

    def _show_service_next_steps(self, service_name: str, use_sudo: bool) -> None:
        """Show next steps after single service installation."""
        systemctl_cmd = "systemctl" if use_sudo else "systemctl --user"
        journal_cmd = "journalctl" if use_sudo else "journalctl --user"

        console.print()
        console.print("[green]Optional:[/green]")

        console.print(
            f"       [green]Check status:[/green]{systemctl_cmd} status {service_name}"
        )
        console.print(
            f"          [green]View logs:[/green]{journal_cmd} -u {service_name} -f"
        )
        console.print(
            f"  [green]Show service file:[/green]{systemctl_cmd} cat {service_name}"
        )
        console.print(
            f"  [green]Enable auto-start:[/green]{systemctl_cmd} enable {service_name}"
        )
        console.print(
            f" [green]Disable auto-start:[/green]{systemctl_cmd} disable {service_name}"
        )
        console.print()

    def _show_next_steps(self, stack_name: str, use_sudo: bool) -> None:
        """Show next steps after installation."""
        services = self.get_service_names(stack_name)
        systemctl_cmd = "systemctl" if use_sudo else "systemctl --user"
        journal_cmd = "journalctl" if use_sudo else "journalctl --user"

        if services:
            console.print()
            console.print("[green]Optional:[/green]")
            # Use first service as example, or show all if only one
            example_service = (
                services[0] if len(services) == 1 else f"{services[0]} (example)"
            )

            console.print(
                f"       [green]Check status:[/green]{systemctl_cmd} status {example_service}"
            )
            console.print(
                f"          [green]View logs:[/green]{journal_cmd} -u {example_service} -f"
            )
            console.print(
                f"   [green]Show service file:[/green]{systemctl_cmd} cat {example_service}"
            )
            console.print(
                f"  [green]Enable auto-start:[/green]{systemctl_cmd} enable {example_service}"
            )
            console.print(
                f" [green]Disable auto-start:[/green]{systemctl_cmd} disable {example_service}"
            )
            console.print()

        # Show stack-specific information if README exists
        readme_path = self.quadlet_base_dir / stack_name / "README.md"
        if readme_path.exists():
            console.print()
            console.print(
                f"[blue]For detailed information about this stack, see: [cyan]{readme_path}[/cyan][/blue]"
            )

    def list_stacks(self) -> None:
        """List all available stacks."""
        self._print_status("Available Stacks:")
        console.print()

        available_stacks = self.discover_stacks()

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Stack Name", style="green", no_wrap=True)
        table.add_column("Files", style="cyan")
        table.add_column("Services", style="yellow")

        for stack in available_stacks:
            files = self.get_stack_files(stack)
            services = self.get_service_names(stack)

            table.add_row(
                stack,
                ", ".join(files) if files else "None",
                ", ".join(services) if services else "None",
            )

        console.print(table)

    def uninstall_stack(
        self, name: str, target_dir: Optional[Path] = None, use_sudo: bool = False
    ) -> bool:
        """Uninstall stack or service from target directory.

        Args:
            name: Name of the stack or service to uninstall
            target_dir: Target directory (defaults to user systemd directory)
            use_sudo: Whether to use sudo for system uninstallation

        Returns:
            True if uninstallation succeeded, False otherwise
        """
        if target_dir is None:
            target_dir = Path.home() / ".config/containers/systemd"

        # Validate and determine if it's a stack or service
        is_valid, resolved_stack, service_file = self.validate_stack_or_service(name)
        if not is_valid:
            return False

        if service_file:
            # Uninstalling a single service
            files = [service_file]
            services = [name]
            install_type = "service"
            display_name = name
        else:
            # Uninstalling entire stack
            files = self.get_stack_files(resolved_stack)
            services = self.get_service_names(resolved_stack)
            install_type = "stack"
            display_name = resolved_stack

        self._print_status(
            f"Uninstalling {display_name} {install_type} from {target_dir}"
        )

        try:
            # Stop and disable services first
            for service in services:
                self._print_status(f"Stopping {service}.service")
                if use_sudo:
                    stop_cmd = ["sudo", "systemctl", "stop", f"{service}.service"]
                    verbose_print(f"  [cyan]exec: {' '.join(stop_cmd)}[/cyan]")
                    subprocess.run(stop_cmd, capture_output=True)

                    disable_cmd = ["sudo", "systemctl", "disable", f"{service}.service"]
                    verbose_print(f"  [cyan]exec: {' '.join(disable_cmd)}[/cyan]")
                    subprocess.run(disable_cmd, capture_output=True)
                else:
                    stop_cmd = ["systemctl", "--user", "stop", f"{service}.service"]
                    verbose_print(f"  [cyan]exec: {' '.join(stop_cmd)}[/cyan]")
                    subprocess.run(stop_cmd, capture_output=True)

                    disable_cmd = [
                        "systemctl",
                        "--user",
                        "disable",
                        f"{service}.service",
                    ]
                    verbose_print(f"  [cyan]exec: {' '.join(disable_cmd)}[/cyan]")
                    subprocess.run(disable_cmd, capture_output=True)

            # Remove quadlet files
            for file in files:
                file_path = target_dir / file
                if file_path.exists():
                    self._print_status(f"Removing {file}")
                    if use_sudo:
                        rm_cmd = ["sudo", "rm", str(file_path)]
                        verbose_print(f"  [cyan]exec: {' '.join(rm_cmd)}[/cyan]")
                        subprocess.run(rm_cmd, check=True)
                    else:
                        verbose_print(f"  [cyan]exec: rm .../systemd/{file}[/cyan]")
                        file_path.unlink()

            # Reload systemd
            self._print_status("Reloading systemd daemon...")
            if use_sudo:
                reload_cmd = ["sudo", "systemctl", "daemon-reload"]
                verbose_print(f"  [cyan]exec: {' '.join(reload_cmd)}[/cyan]")
                result = subprocess.run(
                    reload_cmd,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self._print_error(
                        "Failed to reload system daemon. You may need to manually run: sudo systemctl daemon-reload"
                    )
            else:
                reload_cmd = ["systemctl", "--user", "daemon-reload"]
                verbose_print(f"  [cyan]exec: {' '.join(reload_cmd)}[/cyan]")
                result = subprocess.run(
                    reload_cmd,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self._print_warning(
                        "Failed to reload user daemon (systemd connection issue)"
                    )
                    self._print_status(
                        "Manual daemon reload may be required: systemctl --user daemon-reload"
                    )

            self._print_success("Uninstallation complete!")
            return True

        except subprocess.CalledProcessError as e:
            self._print_error(f"Uninstallation failed: {e}")
            return False
        except Exception as e:
            self._print_error(f"Unexpected error during uninstallation: {e}")
            return False
