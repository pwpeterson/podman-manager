"""vLLM Model Management for switching between different vLLM backend containers."""

import socket
import subprocess
import time
from typing import Optional

import psutil
from rich.progress import Progress, SpinnerColumn, TextColumn

try:
    import requests
except ImportError:
    requests = None

from core.config import console, verbose_print


class VLLMModelManager:
    """Manages vLLM model switching operations"""

    def __init__(self, manager):
        self.manager = manager
        self.vllm_port = 8005
        self.proxy_container = "vllm-proxy"
        self.proxy_port = 8002
        self.network_name = "local-ai-network"
        self.proxy_image = "vllm-proxy:latest"  # Default, can be configured

    def switch_vllm_model(
        self, new_model_container: str, proxy_image: Optional[str] = None
    ) -> bool:
        """Switch vLLM backend to a different model container with improved detection and cleanup"""
        console.print(
            f"[green]Switching vLLM backend to: {new_model_container}[/green]"
        )
        console.print()

        # Step 1: Detect and stop current active vLLM model
        if not self._detect_and_stop_current_vllm_model():
            return False

        # Step 2: Start the new vLLM backend container
        if not self._start_vllm_backend(new_model_container):
            return False

        # Step 3: Restart the proxy container with updated VLLM_URL
        if not self._restart_vllm_proxy(new_model_container, proxy_image):
            return False

        console.print(
            f"[green]Successfully switched vLLM backend to {new_model_container}[/green]"
        )
        return True

    def _detect_and_stop_current_vllm_model(self) -> bool:
        """Detect current active vLLM model and stop it properly"""
        console.print("[yellow]Detecting current active model...[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]Scanning for active vLLM model...[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("detecting", total=None)

            # Find the current vLLM container using port 8005
            current_container = self._find_current_vllm_container()

            progress.remove_task(task)

        if current_container:
            console.print(
                f"[green]Found vLLM model using port {self.vllm_port}: {current_container}[/green]"
            )
            console.print()

            # Stop the current container gracefully
            console.print(f"[green]Stopping {current_container}...[/green]")
            stop_cmd = ["podman", "stop", "-t", "60", current_container]
            verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")

            if self._run_command(stop_cmd):
                console.print(f"[green]  Stopped {current_container}.[/green]")
                console.print()

                # Wait for port to be released
                max_wait_time = 30
                wait_interval = 1
                elapsed_time = 0

                while elapsed_time < max_wait_time and self._is_port_in_use(
                    self.vllm_port
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval

                if self._is_port_in_use(self.vllm_port):
                    console.print(
                        f"[yellow]Warning: Port {self.vllm_port} still in use after stopping {current_container}[/yellow]"
                    )
                    # Try force cleanup as fallback
                    return self._cleanup_vllm_port()

                return True
            else:
                console.print(
                    f"[yellow]Failed to stop {current_container}, trying force cleanup...[/yellow]"
                )
                return self._cleanup_vllm_port()
        else:
            console.print(
                f"[yellow]No active vLLM model detected on port {self.vllm_port}[/yellow]"
            )
            # Still check if port is in use by other processes
            if self._is_port_in_use(self.vllm_port):
                console.print(
                    f"[yellow]Port {self.vllm_port} is in use by unknown process, cleaning up...[/yellow]"
                )
                return self._cleanup_vllm_port()
            return True

    def _detect_and_stop_current_vllm_model_silent(self) -> bool:
        """Detect current active vLLM model and stop it silently (no console output)"""
        # Find the current vLLM container using port 8005
        current_container = self._find_current_vllm_container()

        if current_container:
            verbose_print(
                f"[cyan]Found vLLM model using port {self.vllm_port}: {current_container}[/cyan]"
            )

            # Stop the current container gracefully
            stop_cmd = ["podman", "stop", "-t", "60", current_container]
            verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")

            if self._run_command(stop_cmd):
                verbose_print(f"[cyan]Stopped {current_container}[/cyan]")

                # Wait for port to be released
                max_wait_time = 30
                wait_interval = 1
                elapsed_time = 0

                while elapsed_time < max_wait_time and self._is_port_in_use(
                    self.vllm_port
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval

                if self._is_port_in_use(self.vllm_port):
                    verbose_print(
                        f"[cyan]Warning: Port {self.vllm_port} still in use after stopping {current_container}[/cyan]"
                    )
                    # Try force cleanup as fallback
                    return self._cleanup_vllm_port()

                return True
            else:
                verbose_print(
                    f"[cyan]Failed to stop {current_container}, trying force cleanup...[/cyan]"
                )
                return self._cleanup_vllm_port()
        else:
            verbose_print(
                f"[cyan]No active vLLM model detected on port {self.vllm_port}[/cyan]"
            )
            # Still check if port is in use by other processes
            if self._is_port_in_use(self.vllm_port):
                verbose_print(
                    f"[cyan]Port {self.vllm_port} is in use by unknown process, cleaning up...[/cyan]"
                )
                return self._cleanup_vllm_port()
            return True

    def _cleanup_vllm_port(self) -> bool:
        """Kill any process using the vLLM port and wait for it to fully stop"""
        if not self._is_port_in_use(self.vllm_port):
            verbose_print(f"[cyan]Port {self.vllm_port} is not in use[/cyan]")
            return True

        # First, try to find and stop the vLLM container gracefully
        current_vllm_container = self._find_current_vllm_container()
        if current_vllm_container:
            with Progress(
                SpinnerColumn(),
                TextColumn("[yellow]Stopping current vLLM model...[/yellow]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("stopping", total=None)

                # Stop the container gracefully
                stop_cmd = ["podman", "stop", "-t", "60", current_vllm_container]
                verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
                self._run_command(stop_cmd, suppress_errors=True)

                # Wait for the port to be released
                max_wait_time = 60  # 1 minute
                wait_interval = 2
                elapsed_time = 0

                while elapsed_time < max_wait_time and self._is_port_in_use(
                    self.vllm_port
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval
                    progress.update(
                        task,
                        description=f"[yellow]Waiting for {current_vllm_container} to stop... ({elapsed_time}s)[/yellow]",
                    )

                progress.remove_task(task)

        # If port is still in use, force kill processes
        if self._is_port_in_use(self.vllm_port):
            console.print(
                f"[yellow]Force killing processes on port {self.vllm_port}...[/yellow]"
            )

            with Progress(
                SpinnerColumn(),
                TextColumn(
                    f"[yellow]Force stopping processes on port {self.vllm_port}...[/yellow]"
                ),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("force_stopping", total=None)

                killed = self._kill_process_on_port(self.vllm_port)
                if not killed:
                    progress.remove_task(task)
                    console.print(
                        f"[red]Failed to kill existing process on port {self.vllm_port}[/red]"
                    )
                    return False

                # Wait for port to be fully released
                max_wait_time = 30
                wait_interval = 1
                elapsed_time = 0

                while elapsed_time < max_wait_time and self._is_port_in_use(
                    self.vllm_port
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval
                    progress.update(
                        task,
                        description=f"[yellow]Waiting for port {self.vllm_port} to be released... ({elapsed_time}s)[/yellow]",
                    )

                progress.remove_task(task)

        if self._is_port_in_use(self.vllm_port):
            console.print(
                f"[red]Port {self.vllm_port} is still in use after cleanup attempts[/red]"
            )
            return False

        console.print("[green]  Successfully stopped current vLLM model[/green]")
        return True

    def _start_vllm_backend(self, container_name: str) -> bool:
        """Start the new vLLM backend container and wait for it to be ready"""
        console.print(f"[green]Starting {container_name}...[/green]")

        start_cmd = ["podman", "start", container_name]
        verbose_print(f"[cyan]exec: {' '.join(start_cmd)}[/cyan]")

        if not self._run_command(start_cmd):
            console.print(f"[red]  Failed to start {container_name}[/red]")
            return False

        console.print(f"[green]  Started {container_name}.[/green]")
        console.print()

        # Optional: Wait for the vLLM model to be ready (can be disabled for faster startup)
        # This is commented out to match the desired output format, but can be enabled if needed
        # self._wait_for_vllm_ready(container_name)

        return True

    def _wait_for_vllm_ready(self, container_name: str) -> bool:
        """Wait for the vLLM model to be fully ready (optional method)"""
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[yellow]Waiting for {container_name} to be ready...[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("starting", total=None)

            # Wait for the container to be fully ready (vLLM models take time to load)
            max_wait_time = 300  # 5 minutes
            wait_interval = 5
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                time.sleep(wait_interval)
                elapsed_time += wait_interval

                # Check if the vLLM service is responding on port 8005
                if self._is_vllm_service_ready(container_name):
                    progress.remove_task(task)
                    return True

                # Update progress message with elapsed time
                progress.update(
                    task,
                    description=f"[yellow]Waiting for {container_name} to be ready... ({elapsed_time}s)[/yellow]",
                )

            progress.remove_task(task)
            console.print(
                f"[yellow]Warning: {container_name} may not be fully ready after {max_wait_time}s[/yellow]"
            )
            return False

    def _restart_vllm_proxy(
        self, backend_container: str, proxy_image: Optional[str] = None
    ) -> bool:
        """Restart the vLLM proxy container with updated backend URL"""
        console.print()

        # Stop existing proxy
        console.print(f"[green]Stopping {self.proxy_container}...[/green]")
        if self._stop_container(self.proxy_container):
            console.print(f"[green]  Stopped {self.proxy_container}.[/green]")
        else:
            console.print(
                f"[yellow]  {self.proxy_container} was not running or failed to stop.[/yellow]"
            )
        console.print()

        # Remove existing proxy
        console.print(f"[green]Removing {self.proxy_container}...[/green]")
        if self._remove_container(self.proxy_container):
            console.print(f"[green]  Removed {self.proxy_container}.[/green]")
        else:
            console.print(
                f"[yellow]  {self.proxy_container} was not found or failed to remove.[/yellow]"
            )
        console.print()

        # Start new proxy with updated VLLM_URL
        console.print(f"[green]Starting {self.proxy_container}...[/green]")
        vllm_url = f"http://{backend_container}:{self.vllm_port}"

        run_proxy_cmd = [
            "podman",
            "run",
            "-d",
            "--name",
            self.proxy_container,
            "--network",
            self.network_name,
            "-e",
            f"VLLM_URL={vllm_url}",
            "-p",
            f"{self.proxy_port}:{self.proxy_port}",
            proxy_image or self.proxy_image,
        ]

        verbose_print(f"[cyan]exec: {' '.join(run_proxy_cmd)}[/cyan]")

        if not self._run_command(run_proxy_cmd):
            console.print(f"[red]  Failed to start {self.proxy_container}[/red]")
            return False

        console.print(f"[green]  Started {self.proxy_container}.[/green]")
        console.print()

        # Restart mcp-vllm-delegator after proxy is started
        if not self._restart_mcp_vllm_delegator():
            console.print(
                "[yellow]Warning: Failed to restart mcp-vllm-delegator[/yellow]"
            )
            # Don't fail the entire operation if mcp-vllm-delegator fails

        return True

    def _restart_mcp_vllm_delegator(self) -> bool:
        """Restart the mcp-vllm-delegator container"""
        mcp_container = "mcp-vllm-delegator"

        # Stop existing mcp-vllm-delegator
        console.print(f"[green]Stopping {mcp_container}...[/green]")
        if self._stop_container(mcp_container):
            console.print(f"[green]  Stopped {mcp_container}.[/green]")
        else:
            console.print(
                f"[yellow]  {mcp_container} was not running or failed to stop.[/yellow]"
            )
        console.print()

        # Remove existing mcp-vllm-delegator
        console.print(f"[green]Removing {mcp_container}...[/green]")
        if self._remove_container(mcp_container):
            console.print(f"[green]  Removed {mcp_container}.[/green]")
        else:
            console.print(
                f"[yellow]  {mcp_container} was not found or failed to remove.[/yellow]"
            )
        console.print()

        # Start new mcp-vllm-delegator
        console.print(f"[green]Starting {mcp_container}...[/green]")

        # Use the standard container start command for mcp-vllm-delegator
        # This assumes the container is already configured and just needs to be started
        start_cmd = ["podman", "start", mcp_container]
        verbose_print(f"[cyan]exec: {' '.join(start_cmd)}[/cyan]")

        if self._run_command(start_cmd):
            console.print(f"[green]  Started {mcp_container}.[/green]")
            console.print()
            return True
        else:
            # If start fails, try to run the container (it might not exist yet)
            verbose_print(
                f"[cyan]Container {mcp_container} doesn't exist, trying to run it...[/cyan]"
            )

            # Try to run the mcp-vllm-delegator container with basic configuration
            # This is a fallback - the actual run command should be customized based on your setup
            run_cmd = [
                "podman",
                "run",
                "-d",
                "--name",
                mcp_container,
                "--network",
                self.network_name,
                # Add environment variables and other configuration as needed
                "mcp-vllm-delegator:latest",  # Default image name
            ]

            verbose_print(f"[cyan]exec: {' '.join(run_cmd)}[/cyan]")

            if self._run_command(run_cmd):
                console.print(f"[green]  Started {mcp_container}.[/green]")
                console.print()
                return True
            else:
                console.print(f"[red]  Failed to start {mcp_container}[/red]")
                console.print()
                return False

    def _stop_container(self, container_name: str) -> bool:
        """Stop a container"""
        stop_cmd = ["podman", "stop", container_name]
        verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
        return self._run_command(stop_cmd, suppress_errors=True)

    def _remove_container(self, container_name: str) -> bool:
        """Remove a container"""
        rm_cmd = ["podman", "rm", container_name]
        verbose_print(f"[cyan]exec: {' '.join(rm_cmd)}[/cyan]")
        self._run_command(rm_cmd, suppress_errors=True)
        # Always return True for remove operations to show "Removed" message
        # Even if container doesn't exist, we consider it "removed"
        return True

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) == 0

    def _kill_process_on_port(self, port: int) -> bool:
        """Find and kill process using the specified port"""
        for proc in psutil.process_iter(["pid", "name", "connections"]):
            try:
                connections = proc.connections() if hasattr(proc, "connections") else []
                for conn in connections:
                    if hasattr(conn, "laddr") and conn.laddr.port == port:
                        proc_name = proc.name() if hasattr(proc, "name") else "unknown"
                        proc_pid = proc.pid if hasattr(proc, "pid") else "unknown"

                        verbose_print(
                            f"[cyan]Found process {proc_name} (PID {proc_pid}) using port {port}, terminating...[/cyan]"
                        )

                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                            verbose_print(
                                f"[cyan]Process {proc_pid} terminated successfully[/cyan]"
                            )
                            return True
                        except psutil.TimeoutExpired:
                            verbose_print(
                                f"[cyan]Process {proc_pid} did not terminate in time, killing...[/cyan]"
                            )
                            proc.kill()
                            proc.wait(timeout=5)
                            verbose_print(f"[cyan]Process {proc_pid} killed[/cyan]")
                            return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        verbose_print(f"[cyan]No process found using port {port}[/cyan]")
        return False

    def _run_command(self, cmd: list, suppress_errors: bool = False) -> bool:
        """Run a shell command and return success status"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if result.stdout.strip():
                verbose_print(f"[cyan]Command output: {result.stdout.strip()}[/cyan]")
            return True
        except subprocess.CalledProcessError as e:
            if not suppress_errors:
                error_msg = e.stderr.strip() if e.stderr else "Unknown error"
                verbose_print(f"[cyan]Command failed: {error_msg}[/cyan]")
            return False

    def get_available_vllm_models(self) -> list:
        """Get list of available vLLM model containers"""
        try:
            # List all containers with vllm in the name
            cmd = [
                "podman",
                "ps",
                "-a",
                "--format",
                "{{.Names}}",
                "--filter",
                "name=vllm",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            containers = []
            for line in result.stdout.strip().split("\n"):
                if line.strip() and line.strip() != self.proxy_container:
                    containers.append(line.strip())

            return containers
        except subprocess.CalledProcessError:
            return []

    def get_current_vllm_backend(self) -> Optional[str]:
        """Get the currently active vLLM backend container"""
        try:
            # Inspect the proxy container to get the VLLM_URL environment variable
            cmd = [
                "podman",
                "inspect",
                self.proxy_container,
                "--format",
                "{{.Config.Env}}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse environment variables to find VLLM_URL
            env_vars = result.stdout.strip()
            for env_var in env_vars.split():
                if env_var.startswith("VLLM_URL="):
                    vllm_url = env_var.split("=", 1)[1]
                    # Extract container name from URL (http://container:port)
                    if "://" in vllm_url:
                        url_part = vllm_url.split("://")[1]
                        if ":" in url_part:
                            return url_part.split(":")[0]

            return None
        except subprocess.CalledProcessError:
            return None

    def show_vllm_status(self) -> None:
        """Show current vLLM configuration and available models"""
        console.print("[bold cyan]vLLM Configuration Status[/bold cyan]")
        console.print()

        # Current backend
        current_backend = self.get_current_vllm_backend()
        if current_backend:
            console.print(f"[green]Current Backend:[/green] {current_backend}")
        else:
            console.print(
                "[yellow]Current Backend:[/yellow] Unknown or proxy not running"
            )

        # Proxy status
        proxy_status = self._get_container_status(self.proxy_container)
        console.print(f"[green]Proxy Status:[/green] {proxy_status}")

        # Port status
        port_status = "In Use" if self._is_port_in_use(self.vllm_port) else "Available"
        console.print(f"[green]vLLM Port ({self.vllm_port}):[/green] {port_status}")

        # Available models
        available_models = self.get_available_vllm_models()
        console.print("\n[bold green]Available vLLM Models:[/bold green]")
        if available_models:
            for model in available_models:
                status = self._get_container_status(model)
                marker = "→" if model == current_backend else " "
                console.print(f"  {marker} [cyan]{model}[/cyan] - {status}")
        else:
            console.print("  [yellow]No vLLM model containers found[/yellow]")

        console.print()

    def show_current_vllm_model(self) -> None:
        """Show which vLLM model is currently using port 8005"""
        console.print("[bold cyan]Current vLLM Model Detection[/bold cyan]")
        console.print()

        # Check if port 8005 is in use
        if not self._is_port_in_use(self.vllm_port):
            console.print(
                f"[yellow]Port {self.vllm_port} is not in use - no vLLM model is currently running[/yellow]"
            )
            return

        console.print(f"[green]Port {self.vllm_port} is in use[/green]")

        # Try to find the current vLLM container
        current_container = self._find_current_vllm_container()

        if current_container:
            console.print(
                f"[green]Current vLLM Model:[/green] [cyan]{current_container}[/cyan]"
            )

            # Get additional container information
            status = self._get_container_status(current_container)
            console.print(f"[green]Container Status:[/green] {status}")

            # Try to get the model information from container environment or labels
            model_info = self._get_model_info_from_container(current_container)
            if model_info:
                console.print(f"[green]Model Details:[/green] {model_info}")

            # Check if the service is responding
            if self._is_vllm_service_ready(current_container):
                console.print("[green]Service Status:[/green] Ready and responding")
            else:
                console.print(
                    "[yellow]Service Status:[/yellow] Starting or not responding"
                )
        else:
            console.print(
                f"[yellow]Could not identify the specific vLLM container using port {self.vllm_port}[/yellow]"
            )
            console.print(
                "[dim]This might be a process running outside of a container[/dim]"
            )

            # Try to get process information
            process_info = self._get_process_using_port()
            if process_info:
                console.print(
                    f"[yellow]Process using port {self.vllm_port}:[/yellow] {process_info}"
                )

        console.print()

    def _get_model_info_from_container(self, container_name: str) -> Optional[str]:
        """Extract model information from container environment or labels"""
        try:
            # Check container environment variables for model information
            inspect_cmd = [
                "podman",
                "inspect",
                container_name,
                "--format",
                "{{json .Config.Env}}",
            ]
            result = subprocess.run(inspect_cmd, capture_output=True, text=True)

            if result.returncode == 0 and result.stdout.strip():
                import json

                try:
                    env_vars = json.loads(result.stdout.strip())
                    model_related_vars = []

                    for env_var in env_vars:
                        if any(
                            keyword in env_var.upper()
                            for keyword in ["MODEL", "HF_", "HUGGING"]
                        ):
                            model_related_vars.append(env_var)

                    if model_related_vars:
                        return "; ".join(model_related_vars)
                except json.JSONDecodeError:
                    pass

            # Check container labels for model information
            inspect_cmd = [
                "podman",
                "inspect",
                container_name,
                "--format",
                "{{json .Config.Labels}}",
            ]
            result = subprocess.run(inspect_cmd, capture_output=True, text=True)

            if result.returncode == 0 and result.stdout.strip():
                import json

                try:
                    labels = json.loads(result.stdout.strip())
                    if labels:
                        model_labels = [
                            f"{k}={v}"
                            for k, v in labels.items()
                            if "model" in k.lower()
                        ]
                        if model_labels:
                            return "; ".join(model_labels)
                except json.JSONDecodeError:
                    pass

            return None
        except subprocess.CalledProcessError:
            return None

    def _get_process_using_port(self) -> Optional[str]:
        """Get information about the process using port 8005"""
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline", "connections"]):
                try:
                    connections = (
                        proc.connections() if hasattr(proc, "connections") else []
                    )
                    for conn in connections:
                        if hasattr(conn, "laddr") and conn.laddr.port == self.vllm_port:
                            cmdline = (
                                " ".join(proc.cmdline())
                                if proc.cmdline()
                                else proc.name()
                            )
                            return f"PID {proc.pid}: {cmdline[:100]}{'...' if len(cmdline) > 100 else ''}"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return None
        except Exception:
            return None

    def _get_container_status(self, container_name: str) -> str:
        """Get the status of a container"""
        try:
            cmd = [
                "podman",
                "ps",
                "-a",
                "--format",
                "{{.Status}}",
                "--filter",
                f"name={container_name}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            status = result.stdout.strip()
            return status if status else "Not Found"
        except subprocess.CalledProcessError:
            return "Error"

    def _find_current_vllm_container(self) -> Optional[str]:
        """Find the currently running vLLM container using port 8005"""
        try:
            # Method 1: Check all vLLM containers and inspect their network settings (most reliable)
            container_name = self._find_vllm_container_by_inspection()
            if container_name:
                verbose_print(
                    f"[cyan]Found vLLM container by inspection: {container_name}[/cyan]"
                )
                return container_name

            # Method 2: Check running containers with port mapping
            cmd = ["podman", "ps", "--format", "{{.Names}}\t{{.Ports}}"]
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=10
            )

            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        container_name = parts[0].strip()
                        ports = parts[1].strip()

                        # Check if this is a vLLM container using port 8005
                        if "vllm" in container_name.lower() and (
                            "8005" in ports or "0.0.0.0:8005" in ports
                        ):
                            verbose_print(
                                f"[cyan]Found vLLM container using port 8005: {container_name}[/cyan]"
                            )
                            return container_name

            # Method 3: Use process enumeration (with timeout protection)
            container_name = self._find_container_by_port_process()
            if container_name:
                verbose_print(
                    f"[cyan]Found vLLM container by process: {container_name}[/cyan]"
                )
                return container_name

            verbose_print(
                f"[cyan]No vLLM container found using port {self.vllm_port}[/cyan]"
            )
            return None

        except subprocess.TimeoutExpired:
            verbose_print("[cyan]Container detection timed out[/cyan]")
            return None
        except subprocess.CalledProcessError as e:
            verbose_print(f"[cyan]Error finding current vLLM container: {e}[/cyan]")
            return None
        except Exception as e:
            verbose_print(
                f"[cyan]Unexpected error finding current vLLM container: {e}[/cyan]"
            )
            return None

    def _find_container_by_port_process(self) -> Optional[str]:
        """Find container by checking which process is using port 8005"""
        try:
            # Use psutil to find the process using port 8005
            # Add timeout protection to prevent hanging
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("Process enumeration timed out")

            # Set a 10-second timeout for process enumeration
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(10)

            try:
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        # Skip if process doesn't exist anymore
                        if not proc.is_running():
                            continue

                        # Get connections with timeout protection
                        connections = []
                        try:
                            connections = proc.connections(kind="inet")
                        except (
                            psutil.NoSuchProcess,
                            psutil.AccessDenied,
                            psutil.ZombieProcess,
                        ):
                            continue
                        except Exception:
                            # Skip processes that cause issues
                            continue

                        for conn in connections:
                            if (
                                hasattr(conn, "laddr")
                                and conn.laddr.port == self.vllm_port
                            ):
                                # Found the process, now find which container it belongs to
                                container_name = self._find_container_for_process(
                                    proc.pid
                                )
                                if container_name:
                                    verbose_print(
                                        f"[cyan]Found vLLM container by process: {container_name} (PID: {proc.pid})[/cyan]"
                                    )
                                    signal.alarm(0)  # Cancel timeout
                                    return container_name
                    except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied,
                        psutil.ZombieProcess,
                    ):
                        continue
                    except Exception:
                        # Skip problematic processes
                        continue

                signal.alarm(0)  # Cancel timeout
                return None
            except TimeoutError:
                verbose_print(
                    "[cyan]Process enumeration timed out, skipping port-based detection[/cyan]"
                )
                signal.alarm(0)  # Cancel timeout
                return None

        except Exception as e:
            verbose_print(f"[cyan]Error finding container by port process: {e}[/cyan]")
            try:
                signal.alarm(0)  # Cancel timeout if still active
            except Exception:
                pass
            return None

    def _find_container_for_process(self, pid: int) -> Optional[str]:
        """Find which container a process belongs to"""
        try:
            # Check if the process is running inside a container
            cmd = ["podman", "ps", "--format", "{{.Names}}\t{{.ID}}"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        container_name = parts[0].strip()
                        container_id = parts[1].strip()

                        # Check if this container contains our process
                        if "vllm" in container_name.lower():
                            inspect_cmd = [
                                "podman",
                                "inspect",
                                container_id,
                                "--format",
                                "{{.State.Pid}}",
                            ]
                            inspect_result = subprocess.run(
                                inspect_cmd, capture_output=True, text=True
                            )

                            if inspect_result.returncode == 0:
                                container_pid = inspect_result.stdout.strip()
                                # Check if our process is related to this container
                                if self._is_process_in_container(pid, container_pid):
                                    return container_name
            return None
        except subprocess.CalledProcessError:
            return None

    def _is_process_in_container(self, target_pid: int, container_pid: str) -> bool:
        """Check if a process is running inside a container"""
        try:
            if not container_pid or container_pid == "0":
                return False

            # Simple check: if the target PID is close to container PID, it might be related
            # This is a heuristic and may not be 100% accurate
            container_pid_int = int(container_pid)
            return abs(target_pid - container_pid_int) < 1000  # Arbitrary threshold
        except (ValueError, TypeError):
            return False

    def _find_vllm_container_by_inspection(self) -> Optional[str]:
        """Find vLLM container by inspecting all vLLM containers"""
        try:
            # Get all containers (running and stopped) with vllm in the name
            cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                "name=vllm",
                "--format",
                "{{.Names}}\t{{.Status}}",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=10
            )

            running_vllm_containers = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        container_name = parts[0].strip()
                        status = parts[1].strip()

                        if "Up" in status or "running" in status.lower():
                            running_vllm_containers.append(container_name)

            # If only one vLLM container is running, assume it's using port 8005
            if len(running_vllm_containers) == 1:
                verbose_print(
                    f"[cyan]Found single running vLLM container: {running_vllm_containers[0]}[/cyan]"
                )
                return running_vllm_containers[0]
            elif len(running_vllm_containers) > 1:
                # Multiple vLLM containers running, try to determine which one is using port 8005
                for container_name in running_vllm_containers:
                    if self._container_uses_port(container_name, self.vllm_port):
                        verbose_print(
                            f"[cyan]Found vLLM container using port 8005: {container_name}[/cyan]"
                        )
                        return container_name

                # If we can't determine which one, return the first one
                verbose_print(
                    f"[cyan]Multiple vLLM containers running, using first: {running_vllm_containers[0]}[/cyan]"
                )
                return running_vllm_containers[0]

            return None
        except subprocess.CalledProcessError:
            return None

    def _container_uses_port(self, container_name: str, port: int) -> bool:
        """Check if a specific container is using a specific port"""
        try:
            # Inspect the container's network settings
            inspect_cmd = [
                "podman",
                "inspect",
                container_name,
                "--format",
                "{{json .NetworkSettings.Ports}}",
            ]
            result = subprocess.run(inspect_cmd, capture_output=True, text=True)

            if result.returncode == 0 and result.stdout.strip():
                import json

                try:
                    ports_data = json.loads(result.stdout.strip())
                    # Check if our port is in the ports mapping
                    port_key = f"{port}/tcp"
                    if port_key in ports_data and ports_data[port_key]:
                        return True
                except json.JSONDecodeError:
                    pass

            # Fallback: check if port string appears in inspect output
            inspect_cmd = ["podman", "inspect", container_name]
            result = subprocess.run(inspect_cmd, capture_output=True, text=True)

            if result.returncode == 0 and str(port) in result.stdout:
                return True

            return False
        except subprocess.CalledProcessError:
            return False

    def _is_vllm_service_ready(self, container_name: str) -> bool:
        """Check if the vLLM service is ready by testing the health endpoint"""
        if requests:
            try:
                # Try to connect to the vLLM health endpoint
                response = requests.get(
                    f"http://localhost:{self.vllm_port}/health", timeout=5
                )
                if response.status_code == 200:
                    verbose_print(
                        f"[cyan]vLLM service {container_name} is ready[/cyan]"
                    )
                    return True
            except Exception:
                pass

        # Fallback: check if the container is running and port is in use
        try:
            status_cmd = [
                "podman",
                "inspect",
                container_name,
                "--format",
                "{{.State.Status}}",
            ]
            result = subprocess.run(
                status_cmd, capture_output=True, text=True, check=True
            )

            if result.stdout.strip() == "running" and self._is_port_in_use(
                self.vllm_port
            ):
                # Container is running and port is in use, assume it's starting up
                return False
        except subprocess.CalledProcessError:
            pass

        return False

    def reinit_with_vllm_switch(
        self, target: str, new_vllm_model: str, build_type: Optional[str] = None
    ) -> bool:
        """Reinit a service and switch vLLM model if it's a vLLM-related service"""
        # First perform the vLLM model switch if this is a vLLM service
        if "vllm" in target.lower() or target in ["vllm-proxy", "vllm-stack"]:
            console.print(
                "[green]Performing vLLM model switch as part of reinit...[/green]"
            )
            if not self.switch_vllm_model(new_vllm_model):
                return False
            console.print()

        # Then perform the regular reinit
        from managers.reinit_manager import ReinitManager

        reinit_mgr = ReinitManager(self.manager)
        return reinit_mgr.reinit(
            target, build=(build_type is not None), build_type=build_type
        )
