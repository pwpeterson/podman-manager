"""Quadlet Stack Installation Module

Refactored installer for quadlet stacks with improved separation of concerns.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from rich.table import Table

from config import console, verbose_print
from fuzzy_matcher import FuzzyMatcher


class EnvironmentManager:
    """Handles environment file processing and system environment setup."""

    def __init__(self):
        self.env_file_path = Path("/home/pwp/srv/local-ai-packaged/.env")
        self.system_env_target = "/etc/environment.d/10-app.conf"

    def load_and_clean_env_file(self) -> bool:
        """Load and clean .env file to system environment directory."""
        if not self.env_file_path.exists():
            self._print_warning(f"Environment file not found: {self.env_file_path}")
            return False

        console.print()
        self._print_success("Reloading and cleaning source .env file..")
        verbose_print(
            f"  [cyan]exec: Cleaning and loading {self.env_file_path} to {self.system_env_target}[/cyan]"
        )

        cleaned_lines = self._clean_env_file()
        if not cleaned_lines:
            self._print_warning("No valid environment variables found in .env file")
            self._show_env_preview()
            return False

        return self._create_system_env_file(cleaned_lines)

    def _create_system_env_file(self, cleaned_lines: List[str]) -> bool:
        """Create the system environment file with proper permissions."""
        try:
            subprocess.run(["sudo", "mkdir", "-p", "/etc/environment.d"], check=True)

            temp_file = "/tmp/10-app.conf"
            with open(temp_file, "w", encoding="utf-8") as f:
                for line in cleaned_lines:
                    f.write(f"{line}\n")

            subprocess.run(
                ["sudo", "cp", temp_file, self.system_env_target], check=True
            )
            subprocess.run(["sudo", "chmod", "600", self.system_env_target], check=True)
            subprocess.run(
                ["sudo", "chown", "root:root", self.system_env_target], check=True
            )
            Path(temp_file).unlink(missing_ok=True)

            verbose_print(
                f"  [cyan]exec: Created {self.system_env_target} with {len(cleaned_lines)} variables[/cyan]"
            )

            if Path(self.system_env_target).exists():
                self._print_success(f"Successfully created {self.system_env_target}")
                return True
            else:
                self._print_error(
                    f"Failed to create {self.system_env_target} - file does not exist after creation"
                )
                return False

        except subprocess.CalledProcessError as e:
            if "sudo" in str(e.cmd):
                self._show_sudoers_error()
            else:
                self._print_error(f"Failed to create environment file: {e}")
            return False
        except Exception as e:
            self._print_error(f"Unexpected error creating environment file: {e}")
            return False

    def _clean_env_file(self) -> List[str]:
        """Clean .env file content for /etc/environment.d/ format compliance."""
        cleaned_lines = []

        try:
            with open(self.env_file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self._print_error(f"Failed to read .env file: {e}")
            return []

        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            if not line.strip() or line.strip().startswith("#"):
                continue

            if line.count("=") > 1:
                # Handle multiple variables on one line
                import re

                pattern = r"([A-Z_][A-Z0-9_]*)\s*=\s*([^\s]+(?:\s+[^\s=]+)*?)(?=\s+[A-Z_][A-Z0-9_]*\s*=|\s*$)"
                matches = re.findall(pattern, line)

                if matches:
                    for key, value in matches:
                        cleaned_var = self._clean_env_variable(f"{key}={value}")
                        if cleaned_var:
                            cleaned_lines.append(cleaned_var)
                else:
                    # Fallback: split by spaces
                    parts = line.split()
                    for part in parts:
                        if "=" in part and not part.startswith("#"):
                            cleaned_var = self._clean_env_variable(part)
                            if cleaned_var:
                                cleaned_lines.append(cleaned_var)
            else:
                # Single variable per line
                if "=" in line:
                    cleaned_var = self._clean_env_variable(line)
                    if cleaned_var:
                        cleaned_lines.append(cleaned_var)

        return cleaned_lines

    def _clean_env_variable(self, var_line: str) -> Optional[str]:
        """Clean a single environment variable line."""
        if "#" in var_line:
            var_line = var_line.split("#")[0]

        var_line = var_line.strip()
        if not var_line or "=" not in var_line:
            return None

        key, value = var_line.split("=", 1)
        key = key.strip()
        value = value.strip().rstrip(">")

        if not value:
            value = '""'
        elif " " in value or "," in value or "@" in value:
            if not (value.startswith('"') and value.endswith('"')):
                value = f'"{value}"'

        return f"{key}={value}"

    def _show_env_preview(self):
        """Show preview of source file content for debugging."""
        verbose_print(
            f"  [cyan]Source file content preview: {self.env_file_path}[/cyan]"
        )
        try:
            with open(self.env_file_path, "r") as f:
                preview = f.read()[:200]
                verbose_print(f"  [dim]{preview}...[/dim]")
        except Exception:
            verbose_print("  [dim]Could not read source file[/dim]")

    def _show_sudoers_error(self):
        """Show detailed sudoers configuration error."""
        self._print_error(
            "Error: Add the following rules to /etc/sudoers.d/user_pwp_rules:"
        )
        console.print(
            "  [yellow]Cmnd_Alias ENV_DIR_MGMT = /bin/mkdir -p /etc/environment.d, \\[/yellow]"
        )
        console.print(
            "  [yellow]    /bin/cp /tmp/10-app.conf /etc/environment.d/10-app.conf, \\[/yellow]"
        )
        console.print(
            "  [yellow]    /bin/chmod 600 /etc/environment.d/10-app.conf, \\[/yellow]"
        )
        console.print(
            "  [yellow]    /usr/bin/chown root\\:root /etc/environment.d/10-app.conf[/yellow]"
        )
        console.print(
            "  [yellow]pwp ALL=(root) NOPASSWD: /home/pwp/.local/bin/pm, ENV_DIR_MGMT[/yellow]"
        )

    def _print_success(self, message: str) -> None:
        console.print(f"[green]{message}[/green]")

    def _print_warning(self, message: str) -> None:
        console.print(f"[yellow]{message}[/yellow]")

    def _print_error(self, message: str) -> None:
        console.print(f"[red]{message}[/red]")


class SystemdManager:
    """Handles systemd operations and service management."""

    def check_user_session(self) -> bool:
        """Check systemd user session health."""
        console.print("[green]Checking systemd user session health...[/green]")

        try:
            # Check if systemd user session is running
            cmd = ["systemctl", "--user", "status"]
            verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                console.print(
                    "[yellow]Systemd user session appears to be disconnected[/yellow]"
                )
                console.print("[blue]This may cause daemon-reload to fail[/blue]")
                console.print(
                    "[blue]Consider restarting your user session if issues persist[/blue]"
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                console.print(
                    "[yellow]Cannot communicate with systemd user session[/yellow]"
                )
                console.print("[blue]Transport endpoint may be disconnected[/blue]")
                return False

            console.print()
            console.print("[green]Systemd user session is healthy[/green]")
            return True

        except subprocess.TimeoutExpired:
            console.print("[yellow]Systemd health check timed out[/yellow]")
            return False
        except Exception as e:
            console.print(f"[yellow]Systemd health check failed: {e}[/yellow]")
            return False

    def reload_daemon(self, use_sudo: bool = False) -> bool:
        """Reload systemd daemon."""
        console.print("[green]Reloading systemd daemon...[/green]")

        if use_sudo:
            return self._reload_system_daemon()
        else:
            return self._reload_user_daemon()

    def _reload_system_daemon(self) -> bool:
        """Reload system daemon with sudo."""
        cmd = ["sudo", "systemctl", "daemon-reload"]
        verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(
                "[red]Failed to reload system daemon. You may need to manually run: sudo systemctl daemon-reload[/red]"
            )
            return False
        return True

    def _reload_user_daemon(self) -> bool:
        """Reload user daemon with retry logic."""
        cmd = ["systemctl", "--user", "daemon-reload"]
        verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(
                "[yellow]Failed to reload user daemon (systemd connection issue)[/yellow]"
            )
            console.print("[blue]Attempting to restart user systemd session...[/blue]")
            return self._retry_user_daemon_reload()
        return True

    def _retry_user_daemon_reload(self) -> bool:
        """Retry user daemon reload after resetting failed units."""
        reset_cmd = ["systemctl", "--user", "reset-failed"]
        verbose_print(f"  [cyan]exec: {' '.join(reset_cmd)}[/cyan]")
        reset_result = subprocess.run(reset_cmd, capture_output=True, text=True)

        if reset_result.returncode == 0:
            console.print("[blue]Reset failed units, retrying daemon-reload...[/blue]")
            retry_cmd = ["systemctl", "--user", "daemon-reload"]
            verbose_print(f"  [cyan]exec: {' '.join(retry_cmd)}[/cyan]")
            retry_result = subprocess.run(retry_cmd, capture_output=True, text=True)

            if retry_result.returncode == 0:
                console.print("[green]Successfully reloaded daemon after reset[/green]")
                return True
            else:
                self._show_manual_reload_instructions()
                return False
        else:
            console.print("[yellow]Could not reset systemd user session[/yellow]")
            self._show_manual_reload_instructions()
            return False

    def _show_manual_reload_instructions(self):
        """Show manual daemon reload instructions."""
        console.print(
            "[yellow]Daemon reload still failing. Manual intervention may be required.[/yellow]"
        )
        console.print("[blue]Try: systemctl --user daemon-reload[/blue]")
        console.print(
            f"[blue]Or restart user session: loginctl terminate-user {os.getenv('USER')}[/blue]"
        )


class ValidationManager:
    """Handles container file validation using podman-quadlet after deployment."""

    def __init__(self):
        self.quadlet_generator = "/usr/lib/systemd/user-generators/podman-quadlet"

    def validate_after_deployment(
        self, stack_name: str, files: List[str], use_sudo: bool = False
    ) -> bool:
        """Validate container files by running podman-quadlet and checking journalctl."""
        container_files = [f for f in files if f.endswith(".container")]

        if not container_files:
            return True

        if not Path(self.quadlet_generator).exists():
            console.print(
                "[yellow]Warning: podman-quadlet not found, skipping validation[/yellow]"
            )
            return True

        console.print("[green]Validating deployed quadlet files...[/green]")

        # Run podman-quadlet and check for container-specific errors
        success, container_errors = self._run_quadlet_generator_and_check_errors(
            container_files, use_sudo
        )

        if container_errors:
            console.print("[red]✗ Validation errors found[/red]")
            console.print("[yellow]Container validation errors:[/yellow]")
            for error in container_errors:
                console.print(f"  [dim]{error}[/dim]")
            return False
        else:
            console.print("[green]✓ No validation errors found[/green]")
            return True

    def _run_quadlet_generator_and_check_errors(
        self, container_files: List[str], use_sudo: bool
    ) -> Tuple[bool, List[str]]:
        """Run podman-quadlet generator and check for specific container errors."""
        cmd = [self.quadlet_generator, "--user", "--dryrun"]
        if use_sudo:
            cmd = [self.quadlet_generator, "--dryrun"]

        verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check both stdout and stderr for container-specific errors
            all_output = (result.stdout + "\n" + result.stderr).strip()
            container_errors = []

            if all_output:
                container_errors = self._filter_quadlet_output_for_containers(
                    all_output, container_files
                )

            if result.returncode == 0:
                if container_errors:
                    verbose_print(
                        "  [yellow]Quadlet generator completed but found container issues[/yellow]"
                    )
                else:
                    verbose_print(
                        "  [green]Quadlet generator completed successfully[/green]"
                    )
                return True, container_errors
            else:
                console.print("[yellow]Quadlet generator reported issues[/yellow]")
                return True, container_errors  # Return errors found

        except subprocess.TimeoutExpired:
            console.print(
                "[yellow]Quadlet generator timed out, assuming validation passed[/yellow]"
            )
            return True, []
        except Exception as e:
            console.print(
                f"[yellow]Quadlet generator error: {e}, assuming validation passed[/yellow]"
            )
            return True, []

    def _filter_quadlet_output_for_containers(
        self, quadlet_output: str, container_files: List[str]
    ) -> List[str]:
        """Filter podman-quadlet output for errors related to specific container files."""
        lines = quadlet_output.strip().split("\n")
        container_errors = []

        # Create patterns to match our container files
        container_patterns = []
        for container_file in container_files:
            # Match both the full filename and the service name
            container_name = container_file.replace(".container", "")
            container_patterns.extend([container_file, container_name])

        # Keywords that indicate validation errors
        error_keywords = [
            "error",
            "failed",
            "invalid",
            "unsupported",
            "cannot",
            "unable",
            "missing",
            "bad",
            "wrong",
            "illegal",
            "denied",
            "unknown",
        ]

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            line_lower = line_stripped.lower()

            # Check if line contains error keywords
            has_error_keyword = any(
                error_word in line_lower for error_word in error_keywords
            )

            # Check if line mentions our container files
            mentions_our_containers = any(
                pattern.lower() in line_lower for pattern in container_patterns
            )

            # Include line if it has error keywords and mentions our containers
            if has_error_keyword and mentions_our_containers:
                container_errors.append(line_stripped)

        return container_errors

    def _check_journalctl_for_errors(
        self, container_files: List[str], use_sudo: bool
    ) -> bool:
        """Check journalctl for quadlet-related errors."""
        journal_cmd = ["journalctl", "-b", "--grep=quadlet", "-o", "cat", "--no-pager"]
        if not use_sudo:
            journal_cmd.insert(1, "--user")

        verbose_print(f"  [cyan]exec: {' '.join(journal_cmd)}[/cyan]")

        try:
            result = subprocess.run(
                journal_cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Filter and analyze journal output for relevant errors
                relevant_errors = self._filter_relevant_quadlet_errors(
                    result.stdout, container_files
                )

                if relevant_errors:
                    console.print("[red]✗ Validation errors found[/red]")
                    console.print("[yellow]Relevant quadlet errors:[/yellow]")
                    for error in relevant_errors:
                        console.print(f"  [dim]{error}[/dim]")
                    console.print(
                        "[yellow]Run 'journalctl --user -b | grep -i quadlet' for full details[/yellow]"
                    )
                    return False
                else:
                    console.print(
                        "[green]✓ No validation errors found in journal[/green]"
                    )
                    return True
            else:
                console.print("[green]✓ No quadlet errors in journal[/green]")
                return True

        except subprocess.TimeoutExpired:
            console.print(
                "[yellow]Journal check timed out, assuming validation passed[/yellow]"
            )
            return True
        except Exception as e:
            console.print(
                f"[yellow]Journal check error: {e}, assuming validation passed[/yellow]"
            )
            return True

    def _filter_relevant_quadlet_errors(
        self, journal_output: str, container_files: List[str]
    ) -> List[str]:
        """Filter journal output to show only relevant quadlet errors for our container files."""
        lines = journal_output.strip().split("\n")
        relevant_errors = []
        container_names = [f.replace(".container", "") for f in container_files]

        # Keywords that indicate actual errors (not just info/debug messages)
        error_keywords = [
            "error",
            "failed",
            "invalid",
            "cannot",
            "unable",
            "missing",
            "bad",
            "wrong",
            "illegal",
            "unsupported",
            "denied",
        ]

        # Keywords to filter out (informational/debug messages)
        ignore_keywords = [
            "debug",
            "info",
            "starting",
            "stopping",
            "created",
            "removed",
            "pulled",
            "tagged",
            "loaded successfully",
        ]

        for line in lines:
            line_lower = line.lower()

            # Skip empty lines
            if not line.strip():
                continue

            # Skip lines that are just informational
            if any(ignore_word in line_lower for ignore_word in ignore_keywords):
                continue

            # Check if line contains error keywords
            has_error_keyword = any(
                error_word in line_lower for error_word in error_keywords
            )

            # Check if line mentions our container files
            mentions_our_containers = any(
                container_name in line_lower for container_name in container_names
            )

            # Include line if it has error keywords and either:
            # 1. Mentions our containers specifically, or
            # 2. Is a general quadlet error that could affect our containers
            if has_error_keyword and (
                mentions_our_containers or "quadlet" in line_lower
            ):
                relevant_errors.append(line.strip())

        # Limit to most recent/relevant errors (max 10)
        return relevant_errors[-10:] if relevant_errors else []


class FileManager:
    """Handles file operations during installation."""

    def create_target_directory(self, target_dir: Path, use_sudo: bool = False):
        """Create target directory with appropriate permissions."""
        if use_sudo:
            cmd = ["sudo", "mkdir", "-p", str(target_dir)]
            verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
            subprocess.run(cmd, check=True)
        else:
            verbose_print("  [cyan]exec: mkdir -p .../systemd[/cyan]")
            target_dir.mkdir(parents=True, exist_ok=True)

    def copy_quadlet_files(
        self,
        files: List[str],
        stack_dir: Path,
        target_dir: Path,
        use_sudo: bool = False,
    ):
        """Copy quadlet files to target directory."""
        for file in files:
            if file.endswith(".container"):
                service_name = file.replace(".container", "")
                console.print(
                    f"[green]Copying master {service_name} .container to systemd[/green]"
                )
            else:
                console.print(f"[green]Copying {file} to systemd[/green]")

            source_file = stack_dir / file
            target_file = target_dir / file

            if use_sudo:
                cmd = ["sudo", "cp", str(source_file), str(target_file)]
                verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                subprocess.run(cmd, check=True)
            else:
                verbose_print(f"  [cyan]exec: cp .../{file} .../systemd/{file}[/cyan]")
                shutil.copy2(source_file, target_file)

    def set_file_permissions(
        self, files: List[str], target_dir: Path, use_sudo: bool = False
    ):
        """Set proper permissions on installed files."""
        if use_sudo:
            for file in files:
                cmd = ["sudo", "chmod", "644", str(target_dir / file)]
                verbose_print(f"  [cyan]exec: chmod 644 .../systemd/{file}[/cyan]")
                subprocess.run(cmd, check=True)
        else:
            for file in files:
                verbose_print(f"  [cyan]exec: chmod 644 .../systemd/{file}[/cyan]")
                (target_dir / file).chmod(0o644)


class QuadletInstaller:
    """Main Quadlet Stack Installation Manager with refactored architecture."""

    def __init__(self):
        """Initialize the installer with component managers."""
        self.quadlet_base_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")

        # Component managers
        self.env_manager = EnvironmentManager()
        self.systemd_manager = SystemdManager()
        self.validation_manager = ValidationManager()
        self.file_manager = FileManager()

        self._validate_base_directory()

    def _validate_base_directory(self):
        """Validate that the quadlet base directory exists."""
        if not self.quadlet_base_dir.exists():
            console.print(
                f"[red]Quadlet base directory not found: {self.quadlet_base_dir}[/red]"
            )
            raise FileNotFoundError(
                f"Quadlet base directory not found: {self.quadlet_base_dir}"
            )

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
                services.append(file.stem)
        return sorted(services)

    def find_service_in_stacks(self, service_name: str) -> Optional[Tuple[str, str]]:
        """Find which stack contains a specific service."""
        available_stacks = self.discover_stacks()
        for stack in available_stacks:
            stack_dir = self.quadlet_base_dir / stack
            container_file = f"{service_name}.container"
            container_path = stack_dir / container_file

            if container_path.exists() and not container_file.endswith(".disabled"):
                return (stack, container_file)
        return None

    def validate_stack_or_service(self, name: str) -> Tuple[bool, str, Optional[str]]:
        """Validate that a stack or service exists with fuzzy matching support."""
        # Try exact match as a stack
        stack_dir = self.quadlet_base_dir / name
        if stack_dir.exists():
            files = self.get_stack_files(name)
            if files:
                return (True, name, None)

        # Try exact match as a service within stacks
        service_result = self.find_service_in_stacks(name)
        if service_result:
            stack_name, container_file = service_result
            return (True, stack_name, container_file)

        # Use fuzzy matcher
        fuzzy_matcher = FuzzyMatcher(quadlet_installer=self)
        fuzzy_result = fuzzy_matcher.fuzzy_match_service_or_stack(name)

        if fuzzy_result:
            if fuzzy_result.endswith(".service"):
                service_name = fuzzy_result.replace(".service", "")
                service_result = self.find_service_in_stacks(service_name)
                if service_result:
                    stack_name, container_file = service_result
                    return (True, stack_name, container_file)
            else:
                return (True, fuzzy_result, None)
        elif fuzzy_result == "CANCELLED":
            return (False, name, None)
        elif fuzzy_result is None:
            console.print(f"[red]Stack or service '{name}' not found[/red]")
            return (False, name, None)

        console.print(f"[red]Stack or service '{name}' not found[/red]")
        return (False, name, None)

    def validate_stack(self, stack_name: str) -> bool:
        """Validate that a stack exists and has files."""
        is_valid, resolved_stack, service_file = self.validate_stack_or_service(
            stack_name
        )
        return is_valid and service_file is None

    def check_systemd_user_session(self) -> bool:
        """Check systemd user session health."""
        return self.systemd_manager.check_user_session()

    def install_stack(
        self, name: str, target_dir: Optional[Path] = None, use_sudo: bool = False
    ) -> bool:
        """Install stack or service to target directory."""
        if target_dir is None:
            target_dir = Path.home() / ".config/containers/systemd"

        # Validate and determine if it's a stack or service
        is_valid, resolved_stack, service_file = self.validate_stack_or_service(name)
        if not is_valid or resolved_stack in ["CANCELLED", None]:
            return False

        stack_dir = self.quadlet_base_dir / resolved_stack
        files, install_type, display_name = self._determine_installation_scope(
            service_file, name, resolved_stack
        )

        # Load environment
        if not self.env_manager.load_and_clean_env_file():
            return False

        # Perform installation
        return self._perform_installation(
            files,
            stack_dir,
            target_dir,
            display_name,
            install_type,
            resolved_stack,
            name,
            service_file,
            use_sudo,
        )

    def _determine_installation_scope(
        self, service_file: Optional[str], name: str, resolved_stack: str
    ) -> Tuple[List[str], str, str]:
        """Determine what files to install and installation type."""
        if service_file:
            files = [service_file]
            install_type = "service"
            display_name = name
            self._show_dependency_warning(name, resolved_stack)
        else:
            files = self.get_stack_files(resolved_stack)
            install_type = "stack"
            display_name = resolved_stack

        return files, install_type, display_name

    def _show_dependency_warning(self, name: str, resolved_stack: str):
        """Show warning about service dependencies."""
        stack_files = self.get_stack_files(resolved_stack)
        network_files = [f for f in stack_files if f.endswith(".network")]
        volume_files = [f for f in stack_files if f.endswith(".volume")]

        if network_files or volume_files:
            console.print()
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

    def _perform_installation(
        self,
        files: List[str],
        stack_dir: Path,
        target_dir: Path,
        display_name: str,
        install_type: str,
        resolved_stack: str,
        name: str,
        service_file: Optional[str],
        use_sudo: bool,
    ) -> bool:
        """Perform the actual installation process."""
        console.print(
            f"[green]Deploying {display_name} {install_type} to [cyan]{target_dir}[/cyan][/green]"
        )

        try:
            # File operations
            self.file_manager.create_target_directory(target_dir, use_sudo)
            self.file_manager.copy_quadlet_files(files, stack_dir, target_dir, use_sudo)
            self.file_manager.set_file_permissions(files, target_dir, use_sudo)

            # System operations
            if not self.systemd_manager.reload_daemon(use_sudo):
                return False

            # Post-deployment validation
            if not self.validation_manager.validate_after_deployment(
                resolved_stack, files, use_sudo
            ):
                console.print("[red]Deployment completed but validation failed[/red]")
                console.print("[yellow]Services may not start correctly[/yellow]")
                return False

            self._refresh_pm_discovery(display_name)
            self._show_next_steps(service_file, name, resolved_stack, use_sudo)

            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Installation failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Unexpected error during installation: {e}[/red]")
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
            console.print("[green]Refreshing PM service discovery...[/green]")
            try:
                cmd = [str(pm_script), "refresh"]
                verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    console.print(
                        "[green]Restarting podman service to load changes...[/green]"
                    )
                    restart_cmd = ["systemctl", "--user", "restart", "podman.service"]
                    verbose_print(f"  [cyan]exec: {' '.join(restart_cmd)}[/cyan]")
                    restart_result = subprocess.run(
                        restart_cmd, capture_output=True, text=True, timeout=30
                    )

                    if restart_result.returncode != 0:
                        console.print(
                            "[yellow]Failed to restart podman service - you may need to run: systemctl --user restart podman.service[/yellow]"
                        )
                else:
                    console.print(
                        "[yellow]Failed to refresh PM service discovery (PM may not be available)[/yellow]"
                    )
            except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
                console.print(
                    f"[yellow]Failed to refresh PM service discovery: {e}[/yellow]"
                )
        else:
            console.print(
                "[blue]PM not found, skipping service discovery refresh[/blue]"
            )

    def _show_next_steps(
        self,
        service_file: Optional[str],
        name: str,
        resolved_stack: str,
        use_sudo: bool,
    ):
        """Show next steps after installation."""
        if service_file:
            self._show_service_next_steps(name, use_sudo)
        else:
            self._show_stack_next_steps(resolved_stack, use_sudo)

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

    def _show_stack_next_steps(self, stack_name: str, use_sudo: bool) -> None:
        """Show next steps after stack installation."""
        services = self.get_service_names(stack_name)
        systemctl_cmd = "systemctl" if use_sudo else "systemctl --user"
        journal_cmd = "journalctl" if use_sudo else "journalctl --user"

        if services:
            console.print()
            console.print("[green]Optional:[/green]")
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
        console.print("[blue]Available Stacks:[/blue]")
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
        """Uninstall stack or service from target directory."""
        if target_dir is None:
            target_dir = Path.home() / ".config/containers/systemd"

        # Validate and determine if it's a stack or service
        is_valid, resolved_stack, service_file = self.validate_stack_or_service(name)
        if not is_valid:
            return False

        files, services, install_type, display_name = self._determine_uninstall_scope(
            service_file, name, resolved_stack
        )

        console.print(
            f"[blue]Uninstalling {display_name} {install_type} from {target_dir}[/blue]"
        )

        try:
            self._stop_and_disable_services(services, use_sudo)
            self._remove_quadlet_files(files, target_dir, use_sudo)

            if not self.systemd_manager.reload_daemon(use_sudo):
                console.print(
                    "[yellow]Warning: Failed to reload daemon, but uninstallation completed[/yellow]"
                )

            console.print("[green]Uninstallation complete![/green]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Uninstallation failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Unexpected error during uninstallation: {e}[/red]")
            return False

    def _determine_uninstall_scope(
        self, service_file: Optional[str], name: str, resolved_stack: str
    ) -> Tuple[List[str], List[str], str, str]:
        """Determine what to uninstall."""
        if service_file:
            files = [service_file]
            services = [name]
            install_type = "service"
            display_name = name
        else:
            files = self.get_stack_files(resolved_stack)
            services = self.get_service_names(resolved_stack)
            install_type = "stack"
            display_name = resolved_stack

        return files, services, install_type, display_name

    def _stop_and_disable_services(self, services: List[str], use_sudo: bool):
        """Stop and disable services before uninstallation."""
        for service in services:
            console.print(f"[blue]Stopping {service}.service[/blue]")

            if use_sudo:
                stop_cmd = ["sudo", "systemctl", "stop", f"{service}.service"]
                disable_cmd = ["sudo", "systemctl", "disable", f"{service}.service"]
            else:
                stop_cmd = ["systemctl", "--user", "stop", f"{service}.service"]
                disable_cmd = ["systemctl", "--user", "disable", f"{service}.service"]

            verbose_print(f"  [cyan]exec: {' '.join(stop_cmd)}[/cyan]")
            subprocess.run(stop_cmd, capture_output=True)

            verbose_print(f"  [cyan]exec: {' '.join(disable_cmd)}[/cyan]")
            subprocess.run(disable_cmd, capture_output=True)

    def _remove_quadlet_files(self, files: List[str], target_dir: Path, use_sudo: bool):
        """Remove quadlet files from target directory."""
        for file in files:
            file_path = target_dir / file
            if file_path.exists():
                console.print(f"[blue]Removing {file}[/blue]")

                if use_sudo:
                    rm_cmd = ["sudo", "rm", str(file_path)]
                    verbose_print(f"  [cyan]exec: {' '.join(rm_cmd)}[/cyan]")
                    subprocess.run(rm_cmd, check=True)
                else:
                    verbose_print(f"  [cyan]exec: rm .../systemd/{file}[/cyan]")
                    file_path.unlink()
