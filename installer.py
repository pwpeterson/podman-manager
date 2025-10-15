"""Quadlet Stack Installation Module

Integrated installer for quadlet stacks that follows the existing codebase patterns.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from rich.table import Table

from config import console


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
        console.print(f"[blue][INFO][/blue] {message}")

    def _print_success(self, message: str) -> None:
        """Print success message using consistent formatting."""
        console.print(f"[green][SUCCESS][/green] {message}")

    def _print_warning(self, message: str) -> None:
        """Print warning message using consistent formatting."""
        console.print(f"[yellow][WARNING][/yellow] {message}")

    def _print_error(self, message: str) -> None:
        """Print error message using consistent formatting."""
        console.print(f"[red][ERROR][/red] {message}")

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

    def validate_stack(self, stack_name: str) -> bool:
        """Validate that a stack exists and has files."""
        stack_dir = self.quadlet_base_dir / stack_name

        if not stack_dir.exists():
            self._print_error(f"Stack directory not found: [cyan]{stack_dir}[/cyan]")
            console.print()
            self._print_status("Available stacks:")
            available_stacks = self.discover_stacks()
            for stack in available_stacks:
                console.print(f"  {stack}")
            return False

        files = self.get_stack_files(stack_name)
        if not files:
            self._print_error(f"No quadlet files found in stack: {stack_name}")
            return False

        # Check if all files exist
        for file in files:
            file_path = stack_dir / file
            if not file_path.exists():
                self._print_error(f"Quadlet file {file} not found in {stack_dir}")
                return False

        return True

    def check_systemd_user_session(self) -> bool:
        """Check systemd user session health."""
        self._print_status("Checking systemd user session health...")

        try:
            # Check if systemd user session is running
            result = subprocess.run(
                ["systemctl", "--user", "status"],
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
            result = subprocess.run(
                [
                    "systemctl",
                    "--user",
                    "list-units",
                    "--type=service",
                    "--state=loaded",
                ],
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
        self, stack_name: str, target_dir: Optional[Path] = None, use_sudo: bool = False
    ) -> bool:
        """Install stack to target directory.

        Args:
            stack_name: Name of the stack to install
            target_dir: Target directory (defaults to user systemd directory)
            use_sudo: Whether to use sudo for system installation

        Returns:
            True if installation succeeded, False otherwise
        """
        if target_dir is None:
            target_dir = Path.home() / ".config/containers/systemd"

        stack_dir = self.quadlet_base_dir / stack_name
        files = self.get_stack_files(stack_name)

        # Print installation message with cyan path
        console.print(
            f"[blue][INFO][/blue] Installing {stack_name} stack to [cyan]{target_dir}[/cyan]"
        )

        try:
            # Create target directory
            if use_sudo:
                subprocess.run(["sudo", "mkdir", "-p", str(target_dir)], check=True)
            else:
                target_dir.mkdir(parents=True, exist_ok=True)

            # Copy quadlet files
            for file in files:
                self._print_status(f"Installing {file}")
                source_file = stack_dir / file
                target_file = target_dir / file

                if use_sudo:
                    subprocess.run(
                        ["sudo", "cp", str(source_file), str(target_file)], check=True
                    )
                else:
                    shutil.copy2(source_file, target_file)

            # Set proper permissions
            if use_sudo:
                subprocess.run(
                    ["sudo", "chmod", "644"] + [str(target_dir / f) for f in files],
                    check=True,
                )
            else:
                for file in files:
                    (target_dir / file).chmod(0o644)

            self._print_success(f"Successfully installed {stack_name} stack")

            # Reload systemd
            self._print_status("Reloading systemd daemon...")
            if use_sudo:
                result = subprocess.run(
                    ["sudo", "systemctl", "daemon-reload"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self._print_error(
                        "Failed to reload system daemon. You may need to manually run: sudo systemctl daemon-reload"
                    )
                    return False
            else:
                result = subprocess.run(
                    ["systemctl", "--user", "daemon-reload"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self._print_warning(
                        "Failed to reload user daemon (systemd connection issue)"
                    )
                    self._print_status("Attempting to restart user systemd session...")

                    # Try to reset failed units
                    reset_result = subprocess.run(
                        ["systemctl", "--user", "reset-failed"],
                        capture_output=True,
                        text=True,
                    )
                    if reset_result.returncode == 0:
                        self._print_status(
                            "Reset failed units, retrying daemon-reload..."
                        )
                        retry_result = subprocess.run(
                            ["systemctl", "--user", "daemon-reload"],
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
            self._refresh_pm_discovery()

            # Show next steps
            self._show_next_steps(stack_name, use_sudo)

            return True

        except subprocess.CalledProcessError as e:
            self._print_error(f"Installation failed: {e}")
            return False
        except Exception as e:
            self._print_error(f"Unexpected error during installation: {e}")
            return False

    def _refresh_pm_discovery(self) -> None:
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
            self._print_status("Refreshing PM service discovery...")
            try:
                result = subprocess.run(
                    [str(pm_script), "refresh"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    self._print_success("PM service discovery refreshed")
                else:
                    self._print_warning(
                        "Failed to refresh PM service discovery (PM may not be available)"
                    )
            except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
                self._print_warning(f"Failed to refresh PM service discovery: {e}")
        else:
            self._print_status("PM not found, skipping service discovery refresh")

    def _show_next_steps(self, stack_name: str, use_sudo: bool) -> None:
        """Show next steps after installation."""
        services = self.get_service_names(stack_name)
        systemctl_cmd = "systemctl" if use_sudo else "systemctl --user"
        sudo_prefix = "sudo " if use_sudo else ""

        if services:
            console.print()
            self._print_status("Next steps:")

            console.print("1. Start services:")
            for service in services:
                console.print(
                    f"   {sudo_prefix}{systemctl_cmd} start {service}.service"
                )

            console.print()
            console.print("2. Enable auto-start:")
            for service in services:
                console.print(
                    f"   {sudo_prefix}{systemctl_cmd} enable {service}.service"
                )

            console.print()
            console.print("3. Check status:")
            for service in services:
                console.print(f"   {systemctl_cmd} status {service}.service")

            console.print()
            console.print("4. View logs:")
            journal_cmd = "journalctl" if use_sudo else "journalctl --user"
            for service in services:
                console.print(f"   {journal_cmd} -u {service}.service -f")

        # Show stack-specific information if README exists
        readme_path = self.quadlet_base_dir / stack_name / "README.md"
        if readme_path.exists():
            console.print()
            console.print(
                f"[blue][INFO][/blue] For detailed information about this stack, see: [cyan]{readme_path}[/cyan]"
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
        self, stack_name: str, target_dir: Optional[Path] = None, use_sudo: bool = False
    ) -> bool:
        """Uninstall stack from target directory.

        Args:
            stack_name: Name of the stack to uninstall
            target_dir: Target directory (defaults to user systemd directory)
            use_sudo: Whether to use sudo for system uninstallation

        Returns:
            True if uninstallation succeeded, False otherwise
        """
        if target_dir is None:
            target_dir = Path.home() / ".config/containers/systemd"

        files = self.get_stack_files(stack_name)
        services = self.get_service_names(stack_name)

        self._print_status(f"Uninstalling {stack_name} stack from {target_dir}")

        try:
            # Stop and disable services first
            for service in services:
                self._print_status(f"Stopping {service}.service")
                if use_sudo:
                    subprocess.run(
                        ["sudo", "systemctl", "stop", f"{service}.service"],
                        capture_output=True,
                    )
                    subprocess.run(
                        ["sudo", "systemctl", "disable", f"{service}.service"],
                        capture_output=True,
                    )
                else:
                    subprocess.run(
                        ["systemctl", "--user", "stop", f"{service}.service"],
                        capture_output=True,
                    )
                    subprocess.run(
                        ["systemctl", "--user", "disable", f"{service}.service"],
                        capture_output=True,
                    )

            # Remove quadlet files
            for file in files:
                file_path = target_dir / file
                if file_path.exists():
                    self._print_status(f"Removing {file}")
                    if use_sudo:
                        subprocess.run(["sudo", "rm", str(file_path)], check=True)
                    else:
                        file_path.unlink()

            # Reload systemd
            self._print_status("Reloading systemd daemon...")
            if use_sudo:
                result = subprocess.run(
                    ["sudo", "systemctl", "daemon-reload"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self._print_error(
                        "Failed to reload system daemon. You may need to manually run: sudo systemctl daemon-reload"
                    )
            else:
                result = subprocess.run(
                    ["systemctl", "--user", "daemon-reload"],
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
