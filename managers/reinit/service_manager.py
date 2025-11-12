"""Service management functionality for reinit operations."""

import os
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
            verbose_print(f"[cyan]exec: rm -f {service_file_path}[/cyan]")
            try:
                if os.path.exists(service_file_path):
                    os.remove(service_file_path)
                    console.print(f"[green]  Removed {service_file_name}[/green]")
                else:
                    console.print(f"[green]  Removed {service_file_name}[/green]")
                    verbose_print(
                        f"[cyan]Service file {service_file_path} does not exist, skipping removal[/cyan]"
                    )
                return True
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not remove service file: {e}[/yellow]"
                )
                return False

    def is_vllm_model_service(self, service_name: str) -> bool:
        """Check if a service is a vLLM model by looking in ai_agents_config.json"""
        try:
            import json

            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "ai_agents_config.json",
            )

            if not os.path.exists(config_path):
                verbose_print(
                    f"[cyan]ai_agents_config.json not found at {config_path}[/cyan]"
                )
                return False

            with open(config_path, "r") as f:
                config = json.load(f)

            # Check if service_name matches any model_name in the agents list
            for agent in config.get("agents", []):
                if agent.get("agent_type") == "local_vllm":
                    model_name = agent.get("model_name", "")
                    if model_name == service_name:
                        verbose_print(
                            f"[cyan]Is {service_name} a vLLM model: true[/cyan]"
                        )
                        return True

            verbose_print(f"[cyan]Is {service_name} a vLLM model: false[/cyan]")
            return False

        except Exception as e:
            verbose_print(f"[cyan]Error checking ai_agents_config.json: {e}[/cyan]")
            return False

    def start_service(
        self, service_name: str, target: str, quiet: bool = False
    ) -> subprocess.CompletedProcess:
        """Start a systemd service"""
        start_cmd = ["systemctl", "--user", "restart", service_name]
        verbose_print(f"[cyan]exec: {' '.join(start_cmd)}[/cyan]")

        return self.manager._run_systemctl_command(
            start_cmd,
            f"start_{target}",
            quiet=quiet,
        )

    def stop_service(
        self, service_name: str, target: str, quiet: bool = True
    ) -> subprocess.CompletedProcess:
        """Stop a systemd service"""
        stop_cmd = ["systemctl", "--user", "stop", service_name]
        verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")

        return self.manager._run_systemctl_command(
            stop_cmd, f"stop_{target}", quiet=quiet
        )

    def reload_daemon(self) -> bool:
        """Reload systemd daemon"""
        console.print("[green]Reloading systemd daemon...[/green]")
        reload_success = self.manager.reload_daemon()
        if reload_success:
            console.print("[green]  Reloaded systemd daemon[/green]")
        else:
            console.print("[red]  Failed to reload systemd daemon[/red]")
        return reload_success

    def monitor_service_startup(
        self, target: str, service_name: str, timeout: int = 10
    ) -> bool:
        """Monitor service logs to verify successful startup"""
        # Wait a moment for service to start
        time.sleep(10)

        # Check service status first
        status_cmd = ["systemctl", "--user", "is-active", service_name]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)

        if status_result.returncode != 0:
            return False

        # Get recent logs to check for errors
        logs_cmd = [
            "journalctl",
            "--user",
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
            "journalctl",
            "--user",
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
                        "systemctl",
                        "--user",
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
