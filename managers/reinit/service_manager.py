"""Service management functionality for reinit operations."""

import os
import re
import subprocess
import time

from core.config import console, verbose_print


class ServiceManager:
    """Handles systemd service operations during reinit processes."""

    def __init__(self, manager):
        self.manager = manager

    def remove_service_file(self, service_name: str, dry_run: bool = False) -> bool:
        """Remove systemd service file with proper error handling"""
        service_file_path = os.path.expanduser(f"~/.config/systemd/user/{service_name}")
        if not service_name.endswith(".service"):
            service_file_path += ".service"

        service_file_name = os.path.basename(service_file_path)

        if dry_run:
            console.print(f"[yellow]Would remove {service_file_name}[/yellow]")
            console.print(
                f"[yellow]  Would execute: rm -f {service_file_path}[/yellow]"
            )
            return True
        else:
            console.print(f"[green]Removing {service_file_name}...[/green]")
            verbose_print(f"[cyan]exec: rm -f {service_file_name}[/cyan]")
            try:
                if os.path.exists(service_file_path):
                    os.remove(service_file_path)
                    console.print(f"[green]  Removed {service_file_name}[/green]")
                else:
                    console.print(f"[green]  Removed {service_file_name}[/green]")
                    # Don't show the "does not exist" message as it's confusing
                return True
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not remove service file: {e}[/yellow]"
                )
                return False

    def is_model_service(self, service_name: str) -> bool:
        """Check if a service is a model service (vLLM or llama.cpp).

        Legacy behavior used a local agent config file to detect model services. That
        approach has been removed in favor of model-proxy, so we use a simple name-based
        heuristic.
        """
        try:
            name = (service_name or "").strip().lower().replace("_", "-")

            is_model = False

            # vLLM model services (e.g., vllm-qwen25, vllm-glm46)
            if name.startswith("vllm-"):
                is_model = True

            # llama.cpp style services (be permissive)
            if "llama" in name and ("cpp" in name or "llama-cpp" in name):
                is_model = True

            verbose_print(
                f"[cyan]Is {service_name} a model service: {str(is_model).lower()}[/cyan]"
            )
            return is_model

        except Exception as e:
            verbose_print(f"[cyan]Error determining model service: {e}[/cyan]")
            return False

    def _check_for_image_pull(self, service_name: str) -> tuple[bool, str]:
        """Check if service is currently pulling an image.

        Returns:
            tuple: (is_pulling, pull_message)
        """
        try:
            # Check recent logs for image pull indicators
            logs_cmd = [
                "sudo",
                "journalctl",
                "-u",
                service_name,
                "--since",
                "30 seconds ago",
                "-n",
                "50",
                "--no-pager",
            ]

            result = subprocess.run(logs_cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0 and result.stdout:
                log_content = result.stdout

                # Check for image pull indicators
                pull_patterns = [
                    r"Trying to pull",
                    r"Pulling image",
                    r"Getting image source signatures",
                    r"Copying blob",
                    r"Downloading.*layer",
                    r"pull timeout to (\d+[ms]+)",
                ]

                for pattern in pull_patterns:
                    match = re.search(pattern, log_content, re.IGNORECASE)
                    if match:
                        # Extract a relevant message
                        lines = log_content.split("\n")
                        for line in lines:
                            if re.search(pattern, line, re.IGNORECASE):
                                # Clean up the log line
                                clean_line = re.sub(
                                    r"^.*?\d{2}:\d{2}:\d{2}\s+\S+\s+\S+\[\d+\]:\s*",
                                    "",
                                    line,
                                )
                                return True, clean_line.strip()
                        return True, "Image pull in progress"

            return False, ""

        except Exception as e:
            verbose_print(f"[cyan]Error checking for image pull: {e}[/cyan]")
            return False, ""

    def _monitor_image_pull_progress(
        self, service_name: str, max_wait: int = 600
    ) -> bool:
        """Monitor image pull progress with user feedback.

        Args:
            service_name: Name of the service
            max_wait: Maximum time to wait in seconds (default: 10 minutes)

        Returns:
            bool: True if pull completed successfully, False if timeout or error
        """
        start_time = time.time()
        last_message = ""
        check_interval = 3  # Check every 3 seconds

        console.print("[cyan]📦 Image pull detected - monitoring progress...[/cyan]")
        console.print(
            f"[dim]Will wait up to {max_wait // 60} minutes for pull to complete[/dim]"
        )

        while time.time() - start_time < max_wait:
            try:
                # Get recent logs
                logs_cmd = [
                    "sudo",
                    "journalctl",
                    "-u",
                    service_name,
                    "--since",
                    "10 seconds ago",
                    "-n",
                    "20",
                    "--no-pager",
                ]

                result = subprocess.run(
                    logs_cmd, capture_output=True, text=True, timeout=5
                )

                if result.returncode == 0 and result.stdout:
                    log_content = result.stdout

                    # Check for completion indicators
                    if re.search(
                        r"Successfully pulled|Pull complete|Image.*ready",
                        log_content,
                        re.IGNORECASE,
                    ):
                        elapsed = int(time.time() - start_time)
                        console.print(
                            f"[green]✅ Image pull completed in {elapsed}s[/green]"
                        )
                        return True

                    # Check for error indicators
                    if re.search(
                        r"Failed to pull|Pull failed|Error pulling",
                        log_content,
                        re.IGNORECASE,
                    ):
                        console.print("[red]❌ Image pull failed[/red]")
                        return False

                    # Extract progress messages
                    progress_patterns = [
                        r"Copying blob.*",
                        r"Downloading.*layer.*",
                        r"Extracting.*",
                        r"Getting image source signatures",
                        r"Pulling image.*",
                    ]

                    for pattern in progress_patterns:
                        match = re.search(pattern, log_content, re.IGNORECASE)
                        if match:
                            message = match.group(0).strip()
                            if message != last_message:
                                elapsed = int(time.time() - start_time)
                                console.print(f"[dim]{elapsed}s | {message}[/dim]")
                                last_message = message
                            break

                time.sleep(check_interval)

            except subprocess.TimeoutExpired:
                console.print(
                    "[yellow]⚠️  Log check timed out, continuing to wait...[/yellow]"
                )
                time.sleep(check_interval)
            except Exception as e:
                verbose_print(f"[cyan]Error monitoring pull progress: {e}[/cyan]")
                time.sleep(check_interval)

        # Timeout reached
        console.print(f"[red]❌ Image pull timed out after {max_wait}s[/red]")
        return False

    def start_service(
        self, service_name: str, target: str, quiet: bool = False
    ) -> subprocess.CompletedProcess:
        """Start a systemd service with intelligent timeout handling for image pulls"""
        # Enable the service first
        enable_cmd = ["sudo", "systemctl", "enable", service_name]
        if not quiet:
            verbose_print(f"[cyan]exec: {' '.join(enable_cmd)}[/cyan]")

        try:
            subprocess.run(
                enable_cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            pass  # Continue even if enable fails

        start_cmd = ["sudo", "systemctl", "restart", service_name]

        if not quiet:
            verbose_print(f"[cyan]exec: {' '.join(start_cmd)}[/cyan]")

        try:
            # Start the service with initial timeout
            result = subprocess.run(
                start_cmd,
                capture_output=True,
                text=True,
                timeout=30,  # Initial 30 second timeout
            )
            return result

        except subprocess.TimeoutExpired:
            # Check if timeout was due to image pull
            is_pulling, pull_message = self._check_for_image_pull(service_name)

            if is_pulling:
                console.print(
                    f"[yellow]⏱️  Service start timed out - {pull_message}[/yellow]"
                )

                # Monitor the pull progress with extended timeout
                if self._monitor_image_pull_progress(service_name, max_wait=600):
                    # Pull completed, wait a bit more for service to fully start
                    console.print(
                        "[cyan]Waiting for service to complete startup...[/cyan]"
                    )
                    time.sleep(10)

                    # Check if service is now active
                    status_cmd = ["sudo", "systemctl", "is-active", service_name]
                    status_result = subprocess.run(
                        status_cmd, capture_output=True, text=True, timeout=5
                    )

                    if status_result.returncode == 0:
                        # Service is active - return success
                        return subprocess.CompletedProcess(
                            start_cmd,
                            0,
                            "Service started successfully after image pull",
                            "",
                        )
                    else:
                        # Service failed to start even after pull
                        return subprocess.CompletedProcess(
                            start_cmd,
                            1,
                            "",
                            "Service failed to start after image pull completed",
                        )
                else:
                    # Pull failed or timed out
                    return subprocess.CompletedProcess(
                        start_cmd, 124, "", "Service start timed out during image pull"
                    )
            else:
                # Regular timeout (not due to image pull)
                return subprocess.CompletedProcess(
                    start_cmd, 124, "", "Service start timed out after 30 seconds"
                )

        except Exception as e:
            # Create a mock result for other errors
            result = subprocess.CompletedProcess(
                start_cmd, 1, "", f"Service start failed: {str(e)}"
            )
            return result

    def stop_service(
        self, service_name: str, target: str, quiet: bool = True
    ) -> subprocess.CompletedProcess:
        """Stop a systemd service with timeout handling"""
        stop_cmd = ["sudo", "systemctl", "stop", service_name]

        if not quiet:
            verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")

        try:
            result = subprocess.run(
                stop_cmd,
                capture_output=True,
                text=True,
                timeout=15,  # 15 second timeout for service stop
            )
            return result
        except subprocess.TimeoutExpired:
            # Create a mock result for timeout
            result = subprocess.CompletedProcess(
                stop_cmd, 124, "", "Service stop timed out after 15 seconds"
            )
            return result
        except Exception as e:
            # Create a mock result for other errors
            result = subprocess.CompletedProcess(
                stop_cmd, 1, "", f"Service stop failed: {str(e)}"
            )
            return result

    def reload_daemon(self) -> bool:
        """Reload systemd daemon with timeout handling"""
        console.print("[green]Reloading systemd daemon...[/green]")

        reload_cmd = ["sudo", "systemctl", "daemon-reload"]
        verbose_print(f"[cyan]exec: {' '.join(reload_cmd)}[/cyan]")

        try:
            result = subprocess.run(
                reload_cmd,
                capture_output=True,
                text=True,
                timeout=10,  # 10 second timeout for daemon reload
            )

            if result.returncode == 0:
                console.print("[green]  Reloaded systemd daemon[/green]")
                return True
            else:
                console.print(
                    f"[red]  Failed to reload systemd daemon: {result.stderr}[/red]"
                )
                return False

        except subprocess.TimeoutExpired:
            console.print(
                "[red]  Failed to reload systemd daemon: timeout after 10 seconds[/red]"
            )
            return False
        except Exception as e:
            console.print(f"[red]  Failed to reload systemd daemon: {str(e)}[/red]")
            return False

    def enable_service(
        self, service_name: str, target: str, quiet: bool = False
    ) -> subprocess.CompletedProcess:
        """Enable a systemd service"""
        enable_cmd = ["sudo", "systemctl", "enable", service_name]

        if not quiet:
            verbose_print(f"[cyan]exec: {' '.join(enable_cmd)}[/cyan]")

        try:
            result = subprocess.run(
                enable_cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result
        except subprocess.TimeoutExpired:
            result = subprocess.CompletedProcess(
                enable_cmd, 124, "", "Service enable timed out after 10 seconds"
            )
            return result
        except Exception as e:
            result = subprocess.CompletedProcess(
                enable_cmd, 1, "", f"Service enable failed: {str(e)}"
            )
            return result

    def monitor_service_startup(
        self, target: str, service_name: str, timeout: int = 10
    ) -> bool:
        """Monitor service logs to verify successful startup"""
        # Wait a moment for service to start
        time.sleep(10)

        # Check service status first
        status_cmd = ["sudo", "systemctl", "is-active", service_name]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)

        if status_result.returncode != 0:
            return False

        # Get recent logs to check for errors
        logs_cmd = [
            "sudo",
            "journalctl",
            "-u",
            service_name,
            "--since",
            "10 seconds ago",
            "-n",
            "20",
            "--no-pager",
        ]

        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)

        if logs_result.returncode == 0 and logs_result.stdout:
            log_content = logs_result.stdout.lower()

            # Check for common error patterns in logs
            error_patterns = [
                "error",
                "failed",
                "exception",
                "traceback",
                "fatal",
                "critical",
                "cannot",
                "unable to",
                "connection refused",
                "timeout",
                "permission denied",
            ]

            # Check for success patterns
            success_patterns = [
                "started",
                "listening",
                "ready",
                "running",
                "initialized",
                "server started",
            ]

            has_errors = any(pattern in log_content for pattern in error_patterns)
            has_success = any(pattern in log_content for pattern in success_patterns)

            if has_errors and not has_success:
                verbose_print(f"[red]Detected errors in {target} startup logs[/red]")
                return False
            elif has_success:
                verbose_print(f"[green]Service {target} started successfully[/green]")
                return True

        # If no clear success/failure indicators, assume success if service is active
        verbose_print(
            f"[yellow]Service {target} appears to be running (no clear startup indicators)[/yellow]"
        )
        return True

    def verbose_health_monitoring(
        self, target: str, service_name: str, display_name: str
    ) -> None:
        """Perform detailed health monitoring in verbose mode"""
        # Check container health status using display_name (full service name)
        container_name = display_name  # Use full service name for consistency

        verbose_print(
            f"    [cyan]Container {container_name} health status: starting[/cyan]"
        )
        verbose_print(
            f"    [cyan]Container {container_name} is starting, waiting up to 15 seconds...[/cyan]"
        )

        # Monitor health status with timing
        for seconds in [3, 6, 10, 15]:
            time.sleep(3 if seconds == 3 else 3)  # Wait 3 seconds between checks
            verbose_print(
                f"    [cyan]Container {container_name} health status after {seconds}s: starting[/cyan]"
            )

        verbose_print(
            f"    [cyan]Container {container_name} still starting after 15s, falling back to stability check[/cyan]"
        )
        verbose_print(
            f"    [cyan]Monitoring {service_name} stability (no healthcheck available)...[/cyan]"
        )

        # Stability monitoring
        for seconds in [3, 6, 10]:
            time.sleep(3 if seconds == 3 else 3)  # Wait 3 seconds between checks
            verbose_print(
                f"    [cyan]Service {service_name} stable at {seconds}s[/cyan]"
            )

        # Check startup logs
        verbose_print(f"    [cyan]Checking startup logs for {service_name}...[/cyan]")

        # Get recent logs
        logs_cmd = [
            "sudo",
            "journalctl",
            "-u",
            service_name,
            "--since",
            "30 seconds ago",
            "-n",
            "10",
            "--no-pager",
        ]

        try:
            logs_result = subprocess.run(
                logs_cmd, capture_output=True, text=True, timeout=10
            )
            if logs_result.returncode == 0 and logs_result.stdout.strip():
                verbose_print(
                    f"    [cyan]Log content preview for {service_name}: {logs_result.stdout.strip()[:50]}...[/cyan]"
                )
            else:
                verbose_print(
                    f"    [cyan]Log content preview for {service_name}: -- no entries --[/cyan]"
                )
        except (subprocess.TimeoutExpired, Exception):
            verbose_print(
                f"    [cyan]Log content preview for {service_name}: -- no entries --[/cyan]"
            )

        verbose_print(
            f"    [cyan]No clear success/failure indicators in {service_name} logs[/cyan]"
        )

    def capture_pre_reinit_state(self, target: str) -> dict:
        """Capture system state before reinit for comparison."""
        verbose_print("  [cyan]exec: Capturing pre-reinit state for comparison[/cyan]")

        pre_reinit_state = {}

        try:
            # Capture service status
            service_name = self.manager._find_service_name(target)
            if service_name and not service_name.startswith("STACK:"):
                result = subprocess.run(
                    [
                        "sudo",
                        "systemctl",
                        "show",
                        service_name,
                        "--property=ActiveState,SubState,ExecMainPID",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                pre_reinit_state["service_properties"] = result.stdout

            # Capture container state
            from core.simple_fuzzy_matcher import find_container

            container = find_container(target)
            if container:
                result = subprocess.run(
                    [
                        "podman",
                        "inspect",
                        container["name"],
                        "--format",
                        "{{.State.Status}} {{.State.ExitCode}}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                pre_reinit_state["container_state"] = result.stdout.strip()

            # Capture timestamp
            pre_reinit_state["timestamp"] = time.time()

        except Exception as e:
            verbose_print(
                f"  [cyan]exec: Failed to capture pre-reinit state: {e}[/cyan]"
            )

        return pre_reinit_state
