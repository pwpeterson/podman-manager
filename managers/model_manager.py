"""Model Management for switching between different model backend containers (VLLM and llama.cpp).

Supports the models-stack architecture where both VLLM and llama.cpp models use port 8005
and only one model runs at a time."""

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
from utils.port_container_detector import PortContainerDetector
from utils.secure_subprocess import SecureSubprocessError, secure_run


class ModelManger:
    """Manages model switching operations for both VLLM and llama.cpp models.

    Supports the models-stack architecture:
    - llama-kimi-k2-thinking_q1 (llama.cpp)
    - llama-kimi-k2-thinking_q2 (llama.cpp)
    - vllm-deepseek-coder-v2 (VLLM)
    - vllm-glm4-9b-chat (VLLM)
    - vllm-glm41-9b-thinking (VLLM)
    - vllm-qwen25-coder-32b (VLLM)

    All models use port 8005 and only one runs at a time.
    """

    def __init__(self, manager):
        self.manager = manager
        self.model_port = 8005  # Both VLLM and llama.cpp use port 8005
        self.proxy_container = "sys-services-model-proxy"
        self.proxy_port = 8002
        self.network_name = "local-ai-network"
        self.proxy_image = (
            "sys-services-model-proxy:latest"  # Default, can be configured
        )
        self._startup_monitor = None
        self._port_detector = PortContainerDetector(
            excluded_containers=["sys-services-model-proxy", "mcp-model-delegator"]
        )

    def switch_model_model(
        self, new_model_container: str, proxy_image: Optional[str] = None
    ) -> bool:
        """Switch model backend to a different model container (VLLM or llama.cpp) with improved detection and cleanup.

        Supports switching between any model in the models-stack:
        - llama-kimi-k2-thinking_q1/q2 (llama.cpp models)
        - vllm-deepseek-coder-v2, vllm-glm4-9b-chat, vllm-glm41-9b-thinking, vllm-qwen25-coder-32b (VLLM models)
        """
        model_type = self._detect_model_type(new_model_container)
        console.print(
            f"[green]Switching {model_type} backend to: {new_model_container}[/green]"
        )
        console.print()

        # Step 1: Detect and stop current active model
        if not self._detect_and_stop_current_model():
            return False

        # Step 2: Start the new model backend container
        if not self._start_model_backend(new_model_container):
            return False

        # Step 3: Restart the proxy container with updated MODEL_VLLM
        if not self._restart_vllm_proxy(new_model_container, proxy_image):
            return False

        console.print(
            f"[green]Successfully switched {model_type} backend to {new_model_container}[/green]"
        )
        return True

    def _detect_model_type(self, container_name: str) -> str:
        """Detect if container is VLLM or llama.cpp model"""
        if container_name.startswith("vllm-"):
            return "VLLM"
        elif container_name.startswith("llama-"):
            return "llama.cpp"
        else:
            return "model"

    def _detect_and_stop_current_model(self) -> bool:
        """Detect current active model (VLLM or llama.cpp) and stop it properly"""
        return self._detect_and_stop_current_model_model()

    def _start_model_backend(self, container_name: str) -> bool:
        """Start the new model backend container (VLLM or llama.cpp) and wait for it to be ready"""
        return self._start_vllm_backend(container_name)

    def _detect_and_stop_current_model_model(self) -> bool:
        """Detect current active model (VLLM or llama.cpp) and stop it properly"""
        console.print("[yellow]Detecting current active model...[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn(
                "[yellow]Scanning for active model (VLLM/llama.cpp)...[/yellow]"
            ),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("detecting", total=None)

            # Find the current model container using port 8005
            current_container = self._find_current_vllm_container()

            # Show completion message without spinner
            if current_container:
                model_type = self._detect_model_type(current_container)
                progress.update(
                    task,
                    description=f"[green]Found active {model_type} model: {current_container}[/green]",
                )
            else:
                progress.update(
                    task, description="[yellow]No active model found[/yellow]"
                )
            time.sleep(0.5)  # Brief pause to show completion
            progress.remove_task(task)

        if current_container:
            model_type = self._detect_model_type(current_container)
            console.print(
                f"[green]Found {model_type} model using port {self.model_port}: {current_container}[/green]"
            )
            console.print()

            # Stop the current container gracefully
            console.print(f"[green]Stopping {current_container}...[/green]")
            service_name = f"{current_container}.service"
            stop_cmd = ["systemctl", "--user", "stop", service_name]
            verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")

            if self._run_command(stop_cmd):
                console.print(f"[green]  Stopped {current_container}.[/green]")
                console.print()

                # Wait for port to be released
                max_wait_time = 30
                wait_interval = 1
                elapsed_time = 0

                while elapsed_time < max_wait_time and self._is_port_in_use(
                    self.model_port
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval

                if self._is_port_in_use(self.model_port):
                    console.print(
                        f"[yellow]Warning: Port {self.model_port} still in use after stopping {current_container}[/yellow]"
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
                f"[yellow]No active model detected on port {self.model_port}[/yellow]"
            )
            # Still check if port is in use by other processes
            if self._is_port_in_use(self.model_port):
                console.print(
                    f"[yellow]Port {self.model_port} is in use by unknown process, cleaning up...[/yellow]"
                )
                return self._cleanup_vllm_port()
            return True

    def _stop_known_model_model_silent(self, container_name: str) -> bool:
        """Stop a known model container silently (no console output, no detection)"""
        if container_name:
            model_type = self._detect_model_type(container_name)
            verbose_print(
                f"[cyan]Found {model_type} model using port {self.model_port}: {container_name}[/cyan]"
            )

            # Stop the current container gracefully
            service_name = f"{container_name}.service"
            stop_cmd = ["systemctl", "--user", "stop", service_name]
            verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")

            if self._run_command(stop_cmd):
                verbose_print(f"[cyan]Stopped {container_name}[/cyan]")

                # Wait for port to be released
                max_wait_time = 30
                wait_interval = 1
                elapsed_time = 0

                while elapsed_time < max_wait_time and self._is_port_in_use(
                    self.model_port
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval

                if self._is_port_in_use(self.model_port):
                    verbose_print(
                        f"[cyan]Warning: Port {self.model_port} still in use after stopping {container_name}[/cyan]"
                    )
                    # Try force cleanup as fallback
                    return self._cleanup_vllm_port()

                return True
            else:
                verbose_print(
                    f"[cyan]Failed to stop {container_name}, trying force cleanup...[/cyan]"
                )
                return self._cleanup_vllm_port()
        else:
            verbose_print("[cyan]No container name provided for stopping[/cyan]")
            return True

    def _detect_and_stop_current_model_model_silent(self) -> bool:
        """Detect current active model (VLLM or llama.cpp) and stop it silently (no console output)"""
        # Find the current model container using port 8005
        current_container = self._find_current_vllm_container()

        if current_container:
            model_type = self._detect_model_type(current_container)
            verbose_print(
                f"[cyan]Found {model_type} model using port {self.model_port}: {current_container}[/cyan]"
            )

            # Stop the current container gracefully
            service_name = f"{current_container}.service"
            stop_cmd = ["systemctl", "--user", "stop", service_name]
            verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")

            if self._run_command(stop_cmd):
                verbose_print(f"[cyan]Stopped {current_container}[/cyan]")

                # Wait for port to be released
                max_wait_time = 30
                wait_interval = 1
                elapsed_time = 0

                while elapsed_time < max_wait_time and self._is_port_in_use(
                    self.model_port
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval

                if self._is_port_in_use(self.model_port):
                    verbose_print(
                        f"[cyan]Warning: Port {self.model_port} still in use after stopping {current_container}[/cyan]"
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
                f"[cyan]No active model detected on port {self.model_port}[/cyan]"
            )
            # Still check if port is in use by other processes
            if self._is_port_in_use(self.model_port):
                verbose_print(
                    f"[cyan]Port {self.model_port} is in use by unknown process, cleaning up...[/cyan]"
                )
                return self._cleanup_vllm_port()
            return True

    def _cleanup_vllm_port(self) -> bool:
        """Kill any process using the model port (8005) and wait for it to fully stop"""
        if not self._is_port_in_use(self.model_port):
            verbose_print(f"[cyan]Port {self.model_port} is not in use[/cyan]")
            return True

        # First, try to find and stop the model container gracefully
        current_model_container = self._find_current_vllm_container()
        if current_model_container:
            model_type = self._detect_model_type(current_model_container)
            with Progress(
                SpinnerColumn(),
                TextColumn(f"[yellow]Stopping current {model_type} model...[/yellow]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("stopping", total=None)

                # Stop the container gracefully
                service_name = f"{current_model_container}.service"
                stop_cmd = ["systemctl", "--user", "stop", service_name]
                verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
                self._run_command(stop_cmd, suppress_errors=True)

                # Wait for the port to be released
                max_wait_time = 60  # 1 minute
                wait_interval = 2
                elapsed_time = 0

                while elapsed_time < max_wait_time and self._is_port_in_use(
                    self.model_port
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval
                    progress.update(
                        task,
                        description=f"[yellow]Waiting for {current_model_container} to stop... ({elapsed_time}s)[/yellow]",
                    )

                # Show completion message without spinner
                progress.update(
                    task,
                    description=f"[green]Stopped {current_model_container}[/green]",
                )
                time.sleep(0.5)  # Brief pause to show completion
                progress.remove_task(task)

        # If port is still in use, force kill processes
        if self._is_port_in_use(self.model_port):
            console.print(
                f"[yellow]Force killing processes on port {self.model_port}...[/yellow]"
            )

            with Progress(
                SpinnerColumn(),
                TextColumn(
                    f"[yellow]Force stopping processes on port {self.model_port}...[/yellow]"
                ),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("force_stopping", total=None)

                killed = self._kill_process_on_port(self.model_port)
                if not killed:
                    progress.update(
                        task,
                        description=f"[red]Failed to kill process on port {self.model_port}[/red]",
                    )
                    time.sleep(0.5)  # Brief pause to show completion
                    progress.remove_task(task)
                    console.print(
                        f"[red]Failed to kill existing process on port {self.model_port}[/red]"
                    )
                    return False

                # Wait for port to be fully released
                max_wait_time = 30
                wait_interval = 1
                elapsed_time = 0

                while elapsed_time < max_wait_time and self._is_port_in_use(
                    self.model_port
                ):
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval
                    progress.update(
                        task,
                        description=f"[yellow]Waiting for port {self.model_port} to be released... ({elapsed_time}s)[/yellow]",
                    )

                # Show completion message without spinner
                progress.update(
                    task, description=f"[green]Port {self.model_port} released[/green]"
                )
                time.sleep(0.5)  # Brief pause to show completion
                progress.remove_task(task)

        if self._is_port_in_use(self.model_port):
            console.print(
                f"[red]Port {self.model_port} is still in use after cleanup attempts[/red]"
            )
            return False

        console.print("[green]  Successfully stopped current model[/green]")
        return True

    def _start_vllm_backend(self, container_name: str) -> bool:
        """Start the new model backend container (VLLM or llama.cpp) and wait for it to be ready"""
        console.print(f"[green]Starting {container_name}...[/green]")

        service_name = f"{container_name}.service"
        start_cmd = ["systemctl", "--user", "start", service_name]
        verbose_print(f"[cyan]exec: {' '.join(start_cmd)}[/cyan]")

        if not self._run_command(start_cmd):
            console.print(f"[red]  Failed to start {container_name}[/red]")
            return False

        console.print(f"[green]  Started {container_name}.[/green]")
        console.print()

        # Wait for the model to be fully ready before proceeding
        model_type = self._detect_model_type(container_name)
        console.print(
            f"[cyan]Waiting for {container_name} ({model_type}) to be fully ready...[/cyan]"
        )
        if not self._get_startup_monitor().monitor_model_startup(container_name):
            console.print(f"[red]❌ {container_name} failed to become ready[/red]")
            return False
        console.print()

        return True

    def _wait_for_vllm_ready(self, container_name: str) -> bool:
        """Wait for the model (VLLM or llama.cpp) to be fully ready (optional method)"""
        model_type = self._detect_model_type(container_name)
        with Progress(
            SpinnerColumn(),
            TextColumn(
                f"[yellow]Waiting for {container_name} ({model_type}) to be ready...[/yellow]"
            ),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("starting", total=None)

            # Wait for the container to be fully ready (both VLLM and llama.cpp models take time to load)
            max_wait_time = 300  # 5 minutes
            wait_interval = 5
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                time.sleep(wait_interval)
                elapsed_time += wait_interval

                # Check if the model service is responding on port 8005
                if self._is_vllm_service_ready(container_name):
                    # Show completion message without spinner
                    progress.update(
                        task, description=f"[green]{container_name} is ready[/green]"
                    )
                    time.sleep(0.5)  # Brief pause to show completion
                    progress.remove_task(task)
                    return True

                # Update progress message with elapsed time
                progress.update(
                    task,
                    description=f"[yellow]Waiting for {container_name} ({model_type}) to be ready... ({elapsed_time}s)[/yellow]",
                )

            # Show timeout completion message without spinner
            progress.update(
                task, description=f"[yellow]{container_name} startup timeout[/yellow]"
            )
            time.sleep(0.5)  # Brief pause to show completion
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

        # Start new proxy with updated MODEL_VLLM
        console.print(f"[green]Starting {self.proxy_container}...[/green]")
        vllm_url = f"http://{backend_container}:{self.model_port}"

        run_proxy_cmd = [
            "podman",
            "run",
            "-d",
            "--name",
            self.proxy_container,
            "--network",
            self.network_name,
            "-e",
            f"MODEL_VLLM={vllm_url}",
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

        # Restart mcp-model-delegator after proxy is started
        if not self._restart_mcp_model_delegator():
            console.print(
                "[yellow]Warning: Failed to restart mcp-model-delegator[/yellow]"
            )
            # Don't fail the entire operation if mcp-model-delegator fails

        return True

    def _restart_mcp_model_delegator(self) -> bool:
        """Restart the mcp-model-delegator container"""
        mcp_container = "mcp-model-delegator"

        # Stop existing mcp-model-delegator
        console.print(f"[green]Stopping {mcp_container}...[/green]")
        if self._stop_container(mcp_container):
            console.print(f"[green]  Stopped {mcp_container}.[/green]")
        else:
            console.print(
                f"[yellow]  {mcp_container} was not running or failed to stop.[/yellow]"
            )
        console.print()

        # Remove existing mcp-model-delegator
        console.print(f"[green]Removing {mcp_container}...[/green]")
        if self._remove_container(mcp_container):
            console.print(f"[green]  Removed {mcp_container}.[/green]")
        else:
            console.print(
                f"[yellow]  {mcp_container} was not found or failed to remove.[/yellow]"
            )
        console.print()

        # Start new mcp-model-delegator
        console.print(f"[green]Starting {mcp_container}...[/green]")

        # Use the standard container start command for mcp-model-delegator
        # This assumes the container is already configured and just needs to be started
        service_name = f"{mcp_container}.service"
        start_cmd = ["systemctl", "--user", "start", service_name]
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

            # Try to run the mcp-model-delegator container with basic configuration
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
                "mcp-model-delegator:latest",  # Default image name
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
        service_name = f"{container_name}.service"
        stop_cmd = ["systemctl", "--user", "stop", service_name]
        verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
        return self._run_command(stop_cmd, suppress_errors=True)

    def _remove_container(self, container_name: str) -> bool:
        """Remove a container"""
        # Container removal is handled automatically by systemctl service lifecycle
        verbose_print(
            f"[cyan]Container {container_name} removal handled by systemctl[/cyan]"
        )
        # Always return True for remove operations to show "Removed" message
        # Even if container doesn't exist, we consider it "removed"
        return True

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use"""
        # Delegate to port detector
        return self._port_detector.is_port_in_use(port)

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
            result = secure_run(cmd, timeout=30)
            if result.stdout.strip():
                verbose_print(f"[cyan]Command output: {result.stdout.strip()}[/cyan]")
            return result.returncode == 0
        except SecureSubprocessError as e:
            if not suppress_errors:
                verbose_print(f"[cyan]Command failed: {e}[/cyan]")
            return False

    def get_available_model_models(self) -> list:
        """Get list of available model containers (VLLM and llama.cpp, excluding sys-services-model-proxy)"""
        try:
            # Get containers with vllm in the name
            vllm_cmd = [
                "podman",
                "ps",
                "-a",
                "--format",
                "{{.Names}}",
                "--filter",
                "name=vllm",
            ]
            vllm_result = secure_run(vllm_cmd, timeout=15)

            # Get containers with llama in the name
            llama_cmd = [
                "podman",
                "ps",
                "-a",
                "--format",
                "{{.Names}}",
                "--filter",
                "name=llama",
            ]
            llama_result = secure_run(llama_cmd, timeout=15)
            containers = []

            # Process VLLM containers
            if vllm_result.returncode == 0:
                for line in vllm_result.stdout.strip().split("\n"):
                    container_name = line.strip()
                    # Exclude sys-services-model-proxy and mcp-model-delegator as they are not model containers
                    if container_name and container_name not in [
                        "sys-services-model-proxy",
                        "mcp-model-delegator",
                    ]:
                        containers.append(container_name)

            # Process llama.cpp containers
            if llama_result.returncode == 0:
                for line in llama_result.stdout.strip().split("\n"):
                    container_name = line.strip()
                    if container_name and container_name not in [
                        "sys-services-model-proxy",
                        "mcp-model-delegator",
                    ]:
                        containers.append(container_name)

            return containers
        except SecureSubprocessError:
            return []

    def get_current_vllm_backend(self) -> Optional[str]:
        """Get the currently active vLLM backend container"""
        try:
            # Inspect the proxy container to get the MODEL_VLLM environment variable
            cmd = [
                "podman",
                "inspect",
                self.proxy_container,
                "--format",
                "{{.Config.Env}}",
            ]
            result = secure_run(cmd, timeout=10)

            if result.returncode != 0:
                return None

            # Parse environment variables to find MODEL_VLLM
            env_vars = result.stdout.strip()
            for env_var in env_vars.split():
                if env_var.startswith("MODEL_VLLM="):
                    vllm_url = env_var.split("=", 1)[1]
                    # Extract container name from URL (http://container:port)
                    if "://" in vllm_url:
                        url_part = vllm_url.split("://")[1]
                        if ":" in url_part:
                            return url_part.split(":")[0]

            return None
        except SecureSubprocessError:
            return None

    def show_vllm_status(self) -> None:
        """Show current model configuration and available models (VLLM and llama.cpp)"""
        console.print("[bold cyan]Model Configuration Status[/bold cyan]")
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
        port_status = "In Use" if self._is_port_in_use(self.model_port) else "Available"
        console.print(f"[green]Model Port ({self.model_port}):[/green] {port_status}")

        # Available models
        available_models = self.get_available_model_models()
        console.print("\n[bold green]Available Models (models-stack):[/bold green]")
        if available_models:
            for model in available_models:
                status = self._get_container_status(model)
                model_type = self._detect_model_type(model)
                marker = "→" if model == current_backend else " "
                console.print(
                    f"  {marker} [cyan]{model}[/cyan] ({model_type}) - {status}"
                )
        else:
            console.print("  [yellow]No model containers found[/yellow]")

        console.print()

    def show_current_model_model(self) -> None:
        """Show which model (VLLM or llama.cpp) is currently using port 8005"""
        console.print("[bold cyan]Current Model Detection[/bold cyan]")
        console.print()

        # Check if port 8005 is in use
        if not self._is_port_in_use(self.model_port):
            console.print(
                f"[yellow]Port {self.model_port} is not in use - no model is currently running[/yellow]"
            )
            return

        console.print(f"[green]Port {self.model_port} is in use[/green]")

        # Try to find the current model container
        current_container = self._find_current_vllm_container()

        if current_container:
            model_type = self._detect_model_type(current_container)
            console.print(
                f"[green]Current {model_type} Model:[/green] [cyan]{current_container}[/cyan]"
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
                f"[yellow]Could not identify the specific model container using port {self.model_port}[/yellow]"
            )
            console.print(
                "[dim]This might be a process running outside of a container[/dim]"
            )

            # Try to get process information
            process_info = self._get_process_using_port()
            if process_info:
                console.print(
                    f"[yellow]Process using port {self.model_port}:[/yellow] {process_info}"
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
        # Delegate to port detector
        process_info = self._port_detector.get_process_using_port(self.model_port)
        if process_info:
            cmdline = (
                " ".join(process_info["cmdline"])
                if process_info["cmdline"]
                else process_info["name"]
            )
            return f"PID {process_info['pid']}: {cmdline[:100]}{'...' if len(cmdline) > 100 else ''}"
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
        """Find the currently running model container (VLLM or llama.cpp) using port 8005"""
        verbose_print(f"[cyan]Finding container using port {self.model_port}[/cyan]")

        # Use the port detector with container pattern filtering
        result = self._port_detector.find_container_by_port(
            self.model_port, container_patterns=["vllm", "llama"]
        )

        if result.success:
            verbose_print(
                f"[cyan]Found container using port {self.model_port}: {result.container_name} "
                f"(method: {result.detection_method})[/cyan]"
            )
            return result.container_name
        else:
            verbose_print(
                f"[cyan]Port detector failed: {result.error}, trying fallback[/cyan]"
            )
            return self._find_container_fallback()

    def _find_container_fallback(self) -> Optional[str]:
        """Fallback method to find vLLM container using simpler commands"""
        try:
            # Method 1: Check if port 8005 is in use first
            if not self._is_port_in_use(self.model_port):
                verbose_print(f"[cyan]Port {self.model_port} is not in use[/cyan]")
                return None

            verbose_print(
                f"[cyan]Port {self.model_port} is in use, finding container...[/cyan]"
            )

            # Method 2: Use simpler podman ps command
            cmd = ["podman", "ps", "--format", "{{.Names}}"]
            verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=10
            )

            # Check each container to see if it's using port 8005
            for line in result.stdout.strip().split("\n"):
                container_name = line.strip()
                if (
                    container_name
                    and (
                        "vllm" in container_name.lower()
                        or "llama" in container_name.lower()
                    )
                    and container_name not in self._port_detector.excluded_containers
                ):
                    # Check if this container is using port 8005
                    if self._container_uses_port(container_name, self.model_port):
                        model_type = self._detect_model_type(container_name)
                        verbose_print(
                            f"[cyan]Fallback found {model_type} container using port {self.model_port}: {container_name}[/cyan]"
                        )
                        return container_name

            verbose_print(
                f"[cyan]Fallback: No model container found using port {self.model_port}[/cyan]"
            )
            return None

        except Exception as e:
            verbose_print(f"[cyan]Fallback method also failed: {e}[/cyan]")
            return None

    def _find_container_by_port_process(self) -> Optional[str]:
        """Find container by checking which process is using port 8005"""
        # This method is now redundant with the port detector
        # Kept for backward compatibility but delegates to port detector
        result = self._port_detector.find_container_by_port(self.model_port)
        if result.success:
            return result.container_name
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

                        # Check if this container contains our process (exclude sys-services-model-proxy)
                        if (
                            "vllm" in container_name.lower()
                            and container_name != "sys-services-model-proxy"
                        ):
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
        """Find model container by inspecting all model containers (VLLM and llama.cpp, excluding sys-services-model-proxy)"""
        try:
            # Get all containers (running and stopped) with vllm or llama in the name
            vllm_cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                "name=vllm",
                "--format",
                "{{.Names}}\t{{.Status}}",
            ]
            llama_cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                "name=llama",
                "--format",
                "{{.Names}}\t{{.Status}}",
            ]
            vllm_result = subprocess.run(
                vllm_cmd, capture_output=True, text=True, check=True, timeout=10
            )
            llama_result = subprocess.run(
                llama_cmd, capture_output=True, text=True, check=True, timeout=10
            )

            running_vllm_containers = []

            # Process VLLM containers
            for line in vllm_result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        container_name = parts[0].strip()
                        status = parts[1].strip()

                        # Exclude sys-services-model-proxy as it's not a model container (uses port 8002, not 8005)
                        if (
                            "Up" in status or "running" in status.lower()
                        ) and container_name != "sys-services-model-proxy":
                            running_vllm_containers.append(container_name)

            # Process llama.cpp containers
            for line in llama_result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        container_name = parts[0].strip()
                        status = parts[1].strip()

                        # Exclude sys-services-model-proxy as it's not a model container (uses port 8002, not 8005)
                        if (
                            "Up" in status or "running" in status.lower()
                        ) and container_name != "sys-services-model-proxy":
                            running_vllm_containers.append(container_name)

            # Check each container to see which one is actually using port 8005
            for container_name in running_vllm_containers:
                if self._container_uses_port(container_name, self.model_port):
                    model_type = self._detect_model_type(container_name)
                    verbose_print(
                        f"[cyan]Found {model_type} container using port 8005: {container_name}[/cyan]"
                    )
                    return container_name

            # If no container is using port 8005, return None
            return None
        except subprocess.CalledProcessError:
            return None

    def _container_uses_port(self, container_name: str, port: int) -> bool:
        """Check if a specific container is using a specific port"""
        # Delegate to port detector
        return self._port_detector.container_uses_port(container_name, port)

    def _is_vllm_service_ready(self, container_name: str) -> bool:
        """Check if the model service (VLLM or llama.cpp) is ready by testing the health endpoint"""
        if requests:
            try:
                # Try to connect to the vLLM health endpoint
                response = requests.get(
                    f"http://localhost:{self.model_port}/health", timeout=5
                )
                if response.status_code == 200:
                    model_type = self._detect_model_type(container_name)
                    verbose_print(
                        f"[cyan]{model_type} service {container_name} is ready[/cyan]"
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
                self.model_port
            ):
                # Container is running and port is in use, assume it's starting up
                return False
        except subprocess.CalledProcessError:
            pass

        return False

    def reinit_with_vllm_switch(
        self, target: str, new_model_model: str, build_type: Optional[str] = None
    ) -> bool:
        """Reinit a service and switch model if it's a model-related service (VLLM or llama.cpp)"""
        # First perform the model switch if this is a model service (exclude sys-services-model-proxy)
        if ("vllm" in target.lower() or "llama" in target.lower()) and target not in [
            "sys-services-model-proxy",
            "vllm-stack",
            "models-stack",
        ]:
            model_type = self._detect_model_type(new_model_model)
            console.print(
                f"[green]Performing {model_type} model switch as part of reinit...[/green]"
            )
            if not self.switch_model_model(new_model_model):
                return False
            console.print()

        # Then perform the regular reinit
        from managers.reinit_manager import ReinitManager

        reinit_mgr = ReinitManager(self.manager)
        return reinit_mgr.reinit(
            target, build=(build_type is not None), build_type=build_type
        )

    def _get_startup_monitor(self):
        """Get or create the startup monitor instance."""
        if self._startup_monitor is None:
            from docs.model_startup_monitor import ModelStartupMonitor

            self._startup_monitor = ModelStartupMonitor(self.manager)
        return self._startup_monitor
