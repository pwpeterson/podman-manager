"""Container management functionality for reinit operations."""

import subprocess
import threading
import time

from rich.progress import Progress, SpinnerColumn, TextColumn

from core.config import console, verbose_print


class ContainerManager:
    """Handles container operations during reinit processes."""

    def __init__(self, manager):
        self.manager = manager
        self._vllm_manager = None

    @property
    def vllm_manager(self):
        """Lazy initialization of vLLM manager"""
        if self._vllm_manager is None:
            from managers.vllm_model_manager import VLLMModelManager

            self._vllm_manager = VLLMModelManager(self.manager)
        return self._vllm_manager

    def monitor_container_stop(self, container_name: str) -> bool:
        """Monitor container stop using journalctl to watch for service exit"""
        service_name = f"{container_name}.service"
        exit_detected = threading.Event()

        # Start journalctl monitoring in background
        verbose_print(f"[cyan]exec: journalctl --user -u {service_name} -f[/cyan]")

        def monitor_journal():
            try:
                journal_process = subprocess.Popen(
                    ["journalctl", "--user", f"-u{service_name}", "-f"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                if journal_process.stdout:
                    for line in journal_process.stdout:
                        if f"{service_name}: Main process exited" in line:
                            exit_detected.set()
                            break

                journal_process.terminate()
            except Exception:
                pass

        # Start journal monitoring thread
        monitor_thread = threading.Thread(target=monitor_journal, daemon=True)
        monitor_thread.start()

        # Start the stop command without timeout
        verbose_print(f"[cyan]exec: podman stop {container_name}[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn(f"[green]Stopping {container_name}...[/green]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("stopping", total=None)

            # Start stop command without timeout
            stop_process = subprocess.Popen(
                ["podman", "stop", container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            start_time = time.time()
            last_message_time = start_time

            while stop_process.poll() is None:
                elapsed = int(time.time() - start_time)
                current_time = time.time()

                if exit_detected.is_set():
                    progress.update(
                        task,
                        description=f"[green]{container_name} main process exited[/green]",
                    )
                    break

                # Show "Waiting for service to stop" message every 10 seconds
                if current_time - last_message_time >= 10:
                    progress.update(
                        task,
                        description=f"[yellow]Waiting for {container_name} to stop ({elapsed}s)[/yellow]",
                    )
                    last_message_time = current_time
                else:
                    progress.update(
                        task,
                        description=f"[yellow]Stopping {container_name}... ({elapsed}s)[/yellow]",
                    )

                time.sleep(1)  # Check every second

            # Wait for stop command to complete
            try:
                stdout, stderr = stop_process.communicate(timeout=10)
                success = stop_process.returncode == 0
            except subprocess.TimeoutExpired:
                stop_process.kill()
                success = False

            # Show completion message without spinner
            if success:
                progress.update(
                    task,
                    description=f"[green]Stopped {container_name}[/green]",
                )
                time.sleep(0.5)  # Brief pause to show completion
                progress.remove_task(task)
                console.print(f"[green]  Stopped {container_name}[/green]")
                return True
            else:
                progress.update(
                    task,
                    description=f"[yellow]Failed to stop {container_name}[/yellow]",
                )
                time.sleep(0.5)  # Brief pause to show completion
                progress.remove_task(task)
                console.print(f"[yellow]  Failed to stop {container_name}[/yellow]")
                return False

    def run_command_with_spinner(
        self, cmd: list, message: str, success_msg: str, fail_msg: str
    ) -> bool:
        """Run a command with spinner and status messages"""
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[green]{message}[/green]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("operation", total=None)
            verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

            command_success = self.vllm_manager._run_command(cmd)

            # Show completion message without spinner
            if command_success:
                progress.update(
                    task,
                    description=f"[green]{success_msg}[/green]",
                )
                time.sleep(0.5)  # Brief pause to show completion
                progress.remove_task(task)
                console.print(f"[green]  {success_msg}[/green]")
                return True
            else:
                progress.update(
                    task,
                    description=f"[yellow]{fail_msg}[/yellow]",
                )
                time.sleep(0.5)  # Brief pause to show completion
                progress.remove_task(task)
                console.print(f"[yellow]  {fail_msg}[/yellow]")
                return False

    def show_dry_run_command(self, description: str, command: list) -> None:
        """Display dry-run command in consistent format"""
        console.print(f"[yellow]{description}[/yellow]")
        console.print(f"[yellow]  Would execute: {' '.join(command)}[/yellow]")

    def stop_active_vllm_container(
        self, current_container: str, dry_run: bool = False
    ) -> bool:
        """Stop the currently active vLLM container with spinner and wait for port release"""
        if dry_run:
            self.show_dry_run_command(
                f"Would stop {current_container}",
                ["podman", "stop", "-t", "120", current_container],
            )
            return True
        else:
            # Stop the container
            success = self.run_command_with_spinner(
                ["podman", "stop", "-t", "120", current_container],
                f"Stopping {current_container}...",
                f"Stopped {current_container}",
                f"Failed to stop {current_container}.",
            )

            if success:
                # Wait for port to be released to prevent systemd from restarting immediately
                max_wait_time = 30
                wait_interval = 1
                elapsed_time = 0

                while (
                    elapsed_time < max_wait_time
                    and self.vllm_manager._is_port_in_use(self.vllm_manager.vllm_port)
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval

                if self.vllm_manager._is_port_in_use(self.vllm_manager.vllm_port):
                    verbose_print(
                        f"[cyan]Warning: Port {self.vllm_manager.vllm_port} still in use after stopping {current_container}[/cyan]"
                    )
                    # Try force cleanup as fallback
                    return self.vllm_manager._cleanup_vllm_port()

            return success

    def remove_vllm_container(self, container_name: str, dry_run: bool = False) -> bool:
        """Remove a vLLM container with spinner, handling systemd restart race condition"""
        if dry_run:
            self.show_dry_run_command(
                f"Would remove {container_name}", ["podman", "rm", container_name]
            )
            return True
        else:
            # First try to remove the container
            success = self.run_command_with_spinner(
                ["podman", "rm", container_name],
                f"Removing {container_name}...",
                f"Removed {container_name}",
                f"Failed to remove {container_name}.",
            )

            # If removal failed, it might be because systemd restarted the container
            # In that case, stop it again and then remove
            if not success:
                verbose_print(
                    f"[cyan]Container {container_name} may have been restarted by systemd, trying to stop and remove again[/cyan]"
                )

                # Stop the container again
                stop_cmd = ["podman", "stop", "-t", "10", container_name]
                verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
                stop_result = self.vllm_manager._run_command(
                    stop_cmd, suppress_errors=True
                )

                if stop_result:
                    # Try to remove again
                    rm_cmd = ["podman", "rm", container_name]
                    verbose_print(f"[cyan]exec: {' '.join(rm_cmd)}[/cyan]")
                    remove_result = self.vllm_manager._run_command(
                        rm_cmd, suppress_errors=True
                    )

                    if remove_result:
                        console.print(f"[green]  Removed {container_name}[/green]")
                        return True
                    else:
                        console.print(
                            f"[yellow]  Failed to remove {container_name} after retry[/yellow]"
                        )
                        return False
                else:
                    console.print(
                        f"[yellow]  Failed to stop {container_name} for removal[/yellow]"
                    )
                    return False

            return success

    def stop_container_with_message(self, container_name: str) -> bool:
        """Stop a container with proper error handling"""
        try:
            stop_cmd = ["podman", "stop", container_name]
            verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
            result = subprocess.run(
                stop_cmd, capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0
        except Exception:
            return False

    def remove_container_with_message(self, container_name: str) -> bool:
        """Remove a container with proper error handling"""
        try:
            rm_cmd = ["podman", "rm", container_name]
            verbose_print(f"[cyan]exec: {' '.join(rm_cmd)}[/cyan]")
            result = subprocess.run(rm_cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except Exception:
            return False

    def start_vllm_proxy(self, backend_container: str) -> bool:
        """Start vllm-proxy with the correct backend URL"""
        try:
            # Use the vLLM manager's method to restart the proxy
            return self.vllm_manager._restart_vllm_proxy(backend_container)
        except Exception:
            return False

    def start_mcp_vllm_delegator(self) -> bool:
        """Start mcp-vllm-delegator container"""
        try:
            # Use the vLLM manager's method to restart the delegator
            return self.vllm_manager._restart_mcp_vllm_delegator()
        except Exception:
            return False

    def restart_vllm_support_services(self, display_name: str) -> bool:
        """Restart vllm-proxy and mcp-vllm-delegator services"""
        verbose_print(
            f"[cyan]restart_vllm_support_services called for {display_name}[/cyan]"
        )
        # Restart vllm-proxy with polling-based monitoring
        if not self.monitor_container_stop("vllm-proxy"):
            console.print(
                "[yellow]  vllm-proxy was not running or failed to stop[/yellow]"
            )
        console.print()

        console.print("[green]Removing vllm-proxy...[/green]")
        if self.remove_container_with_message("vllm-proxy"):
            console.print("[green]  Removed vllm-proxy[/green]")
        else:
            console.print(
                "[yellow]  vllm-proxy was not found or failed to remove[/yellow]"
            )
        console.print()

        console.print("[green]Starting vllm-proxy...[/green]")
        if self.start_vllm_proxy(display_name):
            console.print("[green]  Started vllm-proxy[/green]")
            # Note: start_vllm_proxy() calls vllm_manager._restart_vllm_proxy() which also restarts mcp-vllm-delegator
            # So we don't need to restart mcp-vllm-delegator separately to avoid duplicate operations
            verbose_print(
                "[cyan]mcp-vllm-delegator was restarted automatically by vllm-proxy restart[/cyan]"
            )
        else:
            console.print("[red]  Failed to start vllm-proxy[/red]")
            return False
        console.print()

        console.print(f"[green]Successfully reinitialized {display_name}[/green]")
        return True
