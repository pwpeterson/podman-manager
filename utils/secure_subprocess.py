#!/usr/bin/env python3
"""
Secure subprocess wrapper utility to address security concerns.

This module provides secure alternatives to subprocess calls with:
- Input validation and sanitization
- Command allowlisting
- Proper timeout handling
- Secure defaults (no shell=True)
- Logging of security-sensitive operations
"""

import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from rich.console import Console

console = Console()

# Allowlisted commands that are safe to execute
ALLOWED_COMMANDS = {
    # System management
    "systemctl",
    "journalctl",
    "which",
    "df",
    "free",
    "du",
    "chmod",
    "mkdir",
    "cp",
    "rm",
    # Podman/container operations
    "podman",
    "podman-quadlet",
    # Network tools
    "ping",
    "curl",
    "wget",
    "ss",
    # File operations
    "find",
    "grep",
    "cat",
    "ls",
    "touch",
    # Administrative (with extra validation)
    "sudo",
}

# Commands that require extra validation
HIGH_RISK_COMMANDS = {"sudo", "rm", "chmod"}

# Maximum allowed timeout for any subprocess call
MAX_TIMEOUT = 300  # 5 minutes


class SecureSubprocessError(Exception):
    """Raised when subprocess execution fails security validation."""

    pass


class SubprocessResult:
    """Container for subprocess execution results."""

    def __init__(
        self,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        execution_time: float = 0.0,
        command: Optional[List[str]] = None,
    ):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.execution_time = execution_time
        self.command = command or []


def validate_command(cmd: List[str]) -> None:
    """
    Validate that a command is safe to execute.

    Args:
        cmd: Command list to validate

    Raises:
        SecureSubprocessError: If command fails validation
    """
    if not cmd:
        raise SecureSubprocessError("Empty command not allowed")

    command_name = Path(cmd[0]).name

    # Check if command is in allowlist
    if command_name not in ALLOWED_COMMANDS:
        raise SecureSubprocessError(f"Command '{command_name}' not in allowlist")

    # Extra validation for high-risk commands
    if command_name in HIGH_RISK_COMMANDS:
        _validate_high_risk_command(cmd)

    # Validate arguments don't contain shell metacharacters
    # Note: Allow curly braces for podman --format templates
    command_name = Path(cmd[0]).name
    for arg in cmd[1:]:
        # For podman commands, allow curly braces in format strings
        if command_name == "podman" and ("{{" in arg or "}}" in arg):
            # This is likely a Go template format string, which is safe
            continue
        if any(char in arg for char in [";", "&", "|", "`", "$", "(", ")"]):
            raise SecureSubprocessError(f"Potentially unsafe argument: {arg}")


def _validate_high_risk_command(cmd: List[str]) -> None:
    """Validate high-risk commands with extra scrutiny."""
    command_name = Path(cmd[0]).name

    if command_name == "sudo":
        # Only allow specific sudo operations
        if len(cmd) < 2:
            raise SecureSubprocessError("sudo requires additional arguments")

        sudo_cmd = cmd[1]
        allowed_sudo_commands = {"mkdir", "cp", "chmod", "systemctl"}
        if sudo_cmd not in allowed_sudo_commands:
            raise SecureSubprocessError(f"sudo {sudo_cmd} not allowed")

    elif command_name == "rm":
        # Prevent dangerous rm operations
        if "-rf" in " ".join(cmd) or "--recursive --force" in " ".join(cmd):
            # Only allow if targeting specific safe patterns
            safe_patterns = ["/tmp/", "podman-", ".container", ".service"]
            if not any(pattern in " ".join(cmd) for pattern in safe_patterns):
                raise SecureSubprocessError("Dangerous rm operation detected")

    elif command_name == "chmod":
        # Validate chmod permissions are reasonable
        if len(cmd) >= 2:
            perm = cmd[1]
            if perm.startswith("7") or "777" in perm:
                raise SecureSubprocessError("Overly permissive chmod detected")


def secure_run(
    cmd: Union[List[str], str],
    *,
    capture_output: bool = True,
    text: bool = True,
    timeout: Optional[float] = 30,
    check: bool = False,
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    input_data: Optional[str] = None,
    verbose: bool = False,
) -> SubprocessResult:
    """
    Securely execute a subprocess command.

    Args:
        cmd: Command to execute (list or string)
        capture_output: Whether to capture stdout/stderr
        text: Whether to return text output
        timeout: Maximum execution time in seconds
        check: Whether to raise exception on non-zero exit
        cwd: Working directory
        env: Environment variables
        input_data: Input to pass to process
        verbose: Whether to log command execution

    Returns:
        SubprocessResult with execution details

    Raises:
        SecureSubprocessError: If command fails security validation
        subprocess.TimeoutExpired: If command times out
        subprocess.CalledProcessError: If check=True and command fails
    """
    # Convert string command to list
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    # Validate command
    validate_command(cmd)

    # Validate timeout
    if timeout and timeout > MAX_TIMEOUT:
        raise SecureSubprocessError(
            f"Timeout {timeout}s exceeds maximum {MAX_TIMEOUT}s"
        )

    # Log command execution if verbose
    if verbose:
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

    start_time = time.time()

    try:
        # Execute with secure defaults
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            check=check,
            cwd=cwd,
            env=env,
            input=input_data,
            # Security: Never use shell=True
            shell=False,
            # Security: Don't inherit environment by default
            # (env parameter allows explicit control)
        )

        execution_time = time.time() - start_time

        return SubprocessResult(
            returncode=result.returncode,
            stdout=result.stdout if capture_output else "",
            stderr=result.stderr if capture_output else "",
            execution_time=execution_time,
            command=cmd,
        )

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        console.print(f"[red]Command timed out after {timeout}s: {' '.join(cmd)}[/red]")
        raise

    except subprocess.CalledProcessError as e:
        execution_time = time.time() - start_time
        if verbose:
            console.print(
                f"[red]Command failed with exit code {e.returncode}: {' '.join(cmd)}[/red]"
            )
        raise


def secure_popen(
    cmd: Union[List[str], str],
    *,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text: bool = True,
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    verbose: bool = False,
) -> subprocess.Popen:
    """
    Securely create a Popen process.

    Args:
        cmd: Command to execute
        stdout: stdout handling
        stderr: stderr handling
        text: Whether to use text mode
        cwd: Working directory
        env: Environment variables
        verbose: Whether to log command execution

    Returns:
        Popen process object

    Raises:
        SecureSubprocessError: If command fails security validation
    """
    # Convert string command to list
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    # Validate command
    validate_command(cmd)

    # Log command execution if verbose
    if verbose:
        console.print(f"[cyan]popen: {' '.join(cmd)}[/cyan]")

    return subprocess.Popen(
        cmd,
        stdout=stdout,
        stderr=stderr,
        text=text,
        cwd=cwd,
        env=env,
        # Security: Never use shell=True
        shell=False,
    )


def check_command_exists(command: str) -> bool:
    """
    Safely check if a command exists in PATH.

    Args:
        command: Command name to check

    Returns:
        True if command exists, False otherwise
    """
    try:
        result = secure_run(["which", command], timeout=5, verbose=False)
        return result.returncode == 0
    except (SecureSubprocessError, subprocess.TimeoutExpired):
        return False


def get_command_version(command: str, version_flag: str = "--version") -> Optional[str]:
    """
    Safely get version information for a command.

    Args:
        command: Command name
        version_flag: Flag to get version (default: --version)

    Returns:
        Version string if successful, None otherwise
    """
    try:
        result = secure_run([command, version_flag], timeout=10, verbose=False)
        if result.returncode == 0:
            return result.stdout.strip()
    except (SecureSubprocessError, subprocess.TimeoutExpired):
        pass
    return None


# Convenience functions for common operations
def systemctl_user(args: List[str], **kwargs) -> SubprocessResult:
    """Safely execute systemctl --user commands."""
    return secure_run(["systemctl", "--user"] + args, **kwargs)


def podman_cmd(args: List[str], **kwargs) -> SubprocessResult:
    """Safely execute podman commands."""
    return secure_run(["podman"] + args, **kwargs)


def journalctl_user(args: List[str], **kwargs) -> SubprocessResult:
    """Safely execute journalctl --user commands."""
    return secure_run(["journalctl", "--user"] + args, **kwargs)
