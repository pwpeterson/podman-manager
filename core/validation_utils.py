"""Unified validation utilities for quadlet services and system prerequisites."""

from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from core.config import console, verbose_print
from utils.secure_subprocess import SecureSubprocessError, secure_run, systemctl_user


class ValidationUtils:
    """Centralized validation utilities for quadlet services."""

    def __init__(self):
        self.quadlets_dir = Path("/etc/containers/systemd")
        self.quadlet_generator = "/usr/lib/systemd/system-generators/podman-quadlet"

    def validate_prerequisites(self) -> bool:
        """Validate that required tools exist."""
        logger.debug("Starting prerequisites validation")

        # Check systemctl
        if not self._command_exists("systemctl"):
            logger.error("Required command 'systemctl' not found!")
            return False

        # Check if we can run sudo systemctl
        result = systemctl_user(["--help"])
        if result.returncode != 0:
            logger.error("'sudo systemctl' is not available!")
            console.print(
                "[dim]Make sure systemd is running and sudo access is available[/dim]"
            )
            return False

        logger.success("Prerequisites validation complete")
        return True

    def check_container_file_exists(
        self, target: str, fuzzy_matcher=None, command: str = "install"
    ) -> Tuple[bool, Optional[str]]:
        """Check if container file exists using fuzzy matching.

        Returns:
            tuple[bool, Optional[str]]: (exists, resolved_service_name)
        """
        if not fuzzy_matcher:
            # Basic check without fuzzy matching
            container_file = self.quadlets_dir / f"{target}.container"
            target_file = self.quadlets_dir / f"{target}.target"
            exists = container_file.exists() or target_file.exists()
            return exists, target if exists else None

        # Use fuzzy matching to resolve the target
        resolved_target = fuzzy_matcher.fuzzy_match_service_or_stack(target, command)

        if not resolved_target or resolved_target == "CANCELLED":
            return False, None

        # Handle stack targets
        if resolved_target.startswith("STACK:"):
            stack_name = resolved_target[6:]  # Remove "STACK:" prefix
            # For stacks, we need to check if at least one service exists
            from core.service_discovery import get_service_discovery

            discovery = get_service_discovery()

            if stack_name in discovery.stack_services:
                for service_name in discovery.stack_services[stack_name]:
                    container_file = self.quadlets_dir / f"{service_name}.container"
                    target_file = self.quadlets_dir / f"{service_name}.target"
                    if container_file.exists() or target_file.exists():
                        return True, resolved_target
                return False, None

        # Handle individual services
        service_name = resolved_target
        if service_name.endswith(".service"):
            service_name = service_name[:-8]  # Remove ".service" suffix
        elif service_name.endswith(".target"):
            service_name = service_name[:-7]  # Remove ".target" suffix

        container_file = self.quadlets_dir / f"{service_name}.container"
        target_file = self.quadlets_dir / f"{service_name}.target"
        exists = container_file.exists() or target_file.exists()
        return exists, resolved_target if exists else None

    def validate_quadlet_files(
        self, container_files: List[str], use_sudo: bool = False
    ) -> Tuple[bool, List[str]]:
        """Validate container files using podman-quadlet.

        Returns:
            tuple[bool, List[str]]: (success, error_messages)
        """
        if not container_files:
            return True, []

        if not Path(self.quadlet_generator).exists():
            console.print(
                "[yellow]Warning: podman-quadlet not found, skipping validation[/yellow]"
            )
            return True, []

        console.print("[green]Validating quadlet containers...[/green]")
        console.print()

        container_errors = []
        for container_file in container_files:
            errors = self._validate_single_container_file(container_file, use_sudo)
            container_errors.extend(errors)

        if container_errors:
            console.print()
            console.print("[red]Validation errors found:[/red]")
            for error in container_errors:
                console.print(f"  {error}")
            return False, container_errors

        return True, []

    def _validate_single_container_file(
        self, container_file: str, use_sudo: bool = False
    ) -> List[str]:
        """Validate a single container file."""
        quadlet_cmd = ["sudo", self.quadlet_generator, "--dryrun"]
        if use_sudo:
            quadlet_cmd = ["sudo", self.quadlet_generator, "--dryrun"]

        grep_cmd = ["grep", container_file]
        full_cmd = " | ".join([" ".join(quadlet_cmd), " ".join(grep_cmd)])

        verbose_print(f"  [cyan]exec: {full_cmd}[/cyan]")

        try:
            # Run podman-quadlet and pipe to grep using secure subprocess
            try:
                quadlet_result = secure_run(quadlet_cmd, timeout=30)
                if quadlet_result.returncode == 0 and quadlet_result.stdout:
                    # Filter output for the specific container file
                    lines = quadlet_result.stdout.split("\n")
                    filtered_lines = [line for line in lines if container_file in line]
                    if filtered_lines:
                        return self._format_quadlet_errors(
                            "\n".join(filtered_lines), container_file
                        )
            except SecureSubprocessError as e:
                logger.debug("Error validating {}: {}", container_file, e)
                return []

        except Exception as e:
            logger.debug("Error validating {}: {}", container_file, e)

        return []

    def _format_quadlet_errors(
        self, grep_output: str, container_file: str
    ) -> List[str]:
        """Format quadlet error messages for clean display."""
        formatted_errors = []
        import re

        # Handle multi-line error pattern
        full_output = grep_output.strip()
        multiline_pattern = r'quadlet-generator\[\d+\]:\s*Loading source unit file[^\n]*\n\s*quadlet-generator\[\d+\]:\s*error loading "([^"]+)", file contains line (\d+): "([^"]+)" which\s*is not a key-value pair, group, or comment'
        multiline_match = re.search(
            multiline_pattern, full_output, re.MULTILINE | re.DOTALL
        )

        if multiline_match:
            file_path = multiline_match.group(1)
            line_num = multiline_match.group(2)
            content = multiline_match.group(3)
            formatted_errors.append(
                f'[bright_yellow]error loading "{file_path}", file contains line {line_num}: "{content}" which is not a key-value pair, group, or comment[/bright_yellow]'
            )
            return formatted_errors

        # Process line by line for other error types
        lines = full_output.split("\n")
        for line in lines:
            line = line.strip()
            if not line or "Loading source unit file" in line:
                continue

            # Handle unsupported key errors
            if "unsupported key" in line.lower():
                match = re.search(
                    r"unsupported key '([^']+)' in group '([^']+)'", line, re.IGNORECASE
                )
                if match:
                    key = match.group(1)
                    group = match.group(2)
                    formatted_errors.append(
                        f"[bright_yellow]Unsupported key '{key}' in group '{group}' in {container_file}[/bright_yellow]"
                    )
                else:
                    clean_line = re.sub(r"quadlet-generator\[\d+\]:\s*", "", line)
                    if clean_line.strip():
                        formatted_errors.append(
                            f"[bright_yellow]{clean_line}[/bright_yellow]"
                        )
            elif any(
                keyword in line.lower()
                for keyword in ["error", "invalid", "failed", "cannot", "missing"]
            ):
                # Handle single-line error pattern
                single_line_pattern = r'quadlet-generator\[\d+\]:\s*error loading "([^"]+)", file contains line (\d+): "([^"]+)" which\s*is not a key-value pair, group, or comment'
                single_match = re.search(single_line_pattern, line, re.IGNORECASE)

                if single_match:
                    file_path = single_match.group(1)
                    line_num = single_match.group(2)
                    content = single_match.group(3)
                    formatted_errors.append(
                        f'[bright_yellow]error loading "{file_path}", file contains line {line_num}: "{content}" which is not a key-value pair, group, or comment[/bright_yellow]'
                    )
                else:
                    clean_line = re.sub(r"quadlet-generator\[\d+\]:\s*", "", line)
                    if clean_line.strip():
                        formatted_errors.append(
                            f"[bright_yellow]{clean_line}[/bright_yellow]"
                        )

        return formatted_errors

    def check_systemd_user_session(self) -> bool:
        """Check systemd health."""
        console.print("[green]Checking systemd health...[/green]")

        try:
            # Check if systemd is running
            verbose_print("  [cyan]exec: sudo systemctl status[/cyan]")
            result = systemctl_user(["status"], timeout=10)

            if result.returncode != 0:
                console.print("[yellow]Systemd appears to be unavailable[/yellow]")
                console.print("[blue]This may cause daemon-reload to fail[/blue]")
                console.print(
                    "[blue]Check that systemd is running and sudo access is available[/blue]"
                )
                return False

            # Check if we can communicate with systemd
            verbose_print(
                "  [cyan]exec: sudo systemctl list-units --type=service --state=loaded[/cyan]"
            )
            result = systemctl_user(
                ["list-units", "--type=service", "--state=loaded"], timeout=10
            )

            if result.returncode != 0:
                console.print("[yellow]Cannot communicate with systemd[/yellow]")
                console.print("[blue]Transport endpoint may be disconnected[/blue]")
                return False

            console.print()
            console.print("[green]Systemd is healthy[/green]")
            return True

        except Exception as e:
            if "timeout" in str(e).lower():
                console.print("[yellow]Systemd health check timed out[/yellow]")
            else:
                console.print(f"[yellow]Systemd health check failed: {e}[/yellow]")
            return False

    def show_install_suggestion(self, target: str) -> None:
        """Show suggestion to install missing container file."""
        console.print(
            f"[bright_yellow]Required container file is missing, run pm install {target}[/bright_yellow]"
        )

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH."""
        try:
            result = secure_run(["which", command])
            exists = result.returncode == 0
            logger.debug("Command '{}' exists: {}", command, exists)
            return exists
        except Exception as e:
            logger.debug("Error checking command '{}': {}", command, e)
            return False


# Global instance for shared use
_validation_utils = None


def get_validation_utils() -> ValidationUtils:
    """Get the global validation utils instance."""
    global _validation_utils
    if _validation_utils is None:
        _validation_utils = ValidationUtils()
    return _validation_utils
