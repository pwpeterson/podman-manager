"""Container building and image management operations."""

import os
import subprocess
from pathlib import Path
from typing import List

from rich.progress import Progress, SpinnerColumn, TextColumn

from config import console


class ContainerBuilder:
    """Handles container building and image management operations"""

    def __init__(self, manager):
        self.manager = manager

    def _render_ansi_output(self, output: str) -> None:
        """Render ANSI-colored output from subprocess"""
        # For now, just print the output directly
        # Rich console should handle ANSI codes properly
        console.print(output)

    def build_service(self, target: str) -> bool:
        """Build images for a single service using quadlet build process"""
        try:
            # Use the quadlet installation script for building
            return self._build_service_quadlet(target)

        except Exception as e:
            console.print(f"[red]Error building {target}: {e}[/red]")
            return False

    def _build_service_quadlet(self, target: str) -> bool:
        """Build service using quadlet installation script"""
        try:
            # Path to the quadlet installation script
            script_path = "/home/pwp/srv/apps/podman_manager/pm_install_containers.py"

            if not Path(script_path).exists():
                console.print(
                    f"[red]Quadlet installation script not found: {script_path}[/red]"
                )
                return False

            # Map service names to quadlet groups
            # Remove -mcp suffix if present to get the base service name
            service_name = target.replace("-mcp", "")

            # Map service names to quadlet group names
            service_to_group = {
                "vllm-delegator": "vllm",
                "vllm-proxy": "vllm",
                "vllm-qwen25": "vllm",
                "taskflow-backend": "taskflow",
                "taskflow-frontend": "taskflow",
            }

            # Determine the quadlet group
            if service_name in service_to_group:
                quadlet_group = service_to_group[service_name]
            else:
                # For other services, try to extract group from service name
                if "-" in service_name:
                    quadlet_group = service_name.split("-")[0]
                else:
                    quadlet_group = service_name

            console.print(
                f"[yellow]🔨 Building quadlet group '{quadlet_group}' for service '{target}'...[/yellow]"
            )

            # Run the quadlet installation script with timeout
            build_cmd = [script_path, quadlet_group, "user"]
            console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")

            try:
                result = subprocess.run(
                    build_cmd, capture_output=True, text=True, timeout=120
                )  # 2 minute timeout
            except subprocess.TimeoutExpired:
                console.print(
                    "[red]❌ Quadlet build script timed out after 2 minutes[/red]"
                )
                return False

            if result.returncode == 0:
                if result.stdout:
                    # Show the script output with ANSI colors rendered
                    self._render_ansi_output(result.stdout.strip())
                console.print(f"[green]✅ Quadlet build completed for {target}[/green]")
                return True
            else:
                console.print(f"[red]❌ Quadlet build failed for {target}[/red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr.strip()}[/red]")
                if result.stdout:
                    self._render_ansi_output(result.stdout.strip())
                return False

        except Exception as e:
            console.print(f"[red]Error in quadlet build for {target}: {e}[/red]")
            return False

    def build_service_podman(self, target: str) -> bool:
        """Build images using regular podman build (not specialized rebuild)"""
        try:
            # Common Dockerfile locations for different services
            dockerfile_locations = {
                "vllm-delegator": (
                    "/home/pwp/srv/coding_agent/mcp/mcp-vllm-delegator",
                    "Dockerfile-vllm-delegator",
                ),
                "vllm-delegator-mcp": (
                    "/home/pwp/srv/coding_agent/mcp/mcp-vllm-delegator",
                    "Dockerfile-vllm-delegator",
                ),
                "vllm-proxy": (
                    "/home/pwp/srv/local-ai-packaged/vllm-proxy",
                    "Dockerfile.vllm_proxy",
                ),
                "vllm-proxy-mcp": (
                    "/home/pwp/srv/local-ai-packaged/vllm-proxy",
                    "Dockerfile.vllm_proxy",
                ),
            }

            if target in dockerfile_locations:
                build_dir, dockerfile = dockerfile_locations[target]
                if not Path(build_dir).exists():
                    console.print(f"[red]Build directory not found: {build_dir}[/red]")
                    return False

                original_cwd = os.getcwd()
                try:
                    os.chdir(build_dir)

                    if not Path(dockerfile).exists():
                        console.print(f"[red]Dockerfile not found: {dockerfile}[/red]")
                        return False

                    # Determine image name
                    if target in ["vllm-delegator", "vllm-delegator-mcp"]:
                        image_name = "localhost/vllm-delegator-mcp:latest"
                    elif target in ["vllm-proxy", "vllm-proxy-mcp"]:
                        image_name = "localhost/vllm-proxy:latest"
                    else:
                        image_name = f"localhost/{target}:latest"

                    build_cmd = [
                        "podman",
                        "build",
                        "--no-cache",
                        "-f",
                        dockerfile,
                        "-t",
                        image_name,
                        ".",
                    ]
                    console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")

                    result = subprocess.run(build_cmd, capture_output=True, text=True)

                    if result.returncode == 0:
                        console.print(
                            f"[green]Podman build completed for {target}[/green]"
                        )
                        return True
                    else:
                        console.print(f"[red]Podman build failed for {target}[/red]")
                        if result.stderr:
                            console.print(f"[red]{result.stderr.strip()}[/red]")
                        return False

                finally:
                    os.chdir(original_cwd)
            else:
                console.print(
                    f"[yellow]No podman build configuration for {target}, skipping[/yellow]"
                )
                return True  # Not an error, just no build needed

        except Exception as e:
            console.print(f"[red]Error in podman build for {target}: {e}[/red]")
            return False

    def rebuild_service(self, target: str) -> bool:
        """Rebuild a single service"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold white]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            # Step 1: Stop the service
            task1 = progress.add_task("Step 1: Stopping service...", total=None)
            stop_success = self.manager.stop_service(target)
            progress.remove_task(task1)

            if not stop_success:
                console.print(
                    "[yellow]Service was not running or failed to stop[/yellow]"
                )

            # Step 2: Build the service (this will call our specialized rebuild methods)
            task2 = progress.add_task("Step 2: Rebuilding image...", total=None)
            build_success = self.build_service(target)
            progress.remove_task(task2)

            if not build_success:
                console.print("[red]Failed to rebuild image[/red]")
                return False

            # Step 3: Reload systemd daemon
            task3 = progress.add_task("Step 3: Reloading systemd daemon...", total=None)
            reload_success = self.manager.reload_daemon()
            progress.remove_task(task3)

            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False

            # Step 4: Start the service
            task4 = progress.add_task("Step 4: Starting service...", total=None)
            start_success = self.manager.start_service(target)
            progress.remove_task(task4)

            if start_success:
                console.print(f"[green]Successfully rebuilt {target}[/green]")
                return True
            else:
                console.print(f"[red]Failed to start {target} after rebuild[/red]")
                return False

    def rebuild_stack(self, project: str) -> bool:
        """Rebuild an entire project stack"""
        if project == "vllm":
            services = ["vllm-qwen25", "vllm-proxy", "vllm-delegator"]
            display_name = "vLLM stack"
        elif project == "taskflow":
            services = ["taskflow-frontend", "taskflow-backend"]
            display_name = "taskflow stack"
        else:
            # Generic project - find services that start with project name
            services = [
                short_name
                for short_name in self.manager.quadlet_services.keys()
                if short_name.startswith(f"{project}-")
            ]
            display_name = f"{project} stack"

        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold white]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            # Step 1: Stop all services
            task1 = progress.add_task(
                f"Step 1: Stopping all {project} services...", total=None
            )
            stop_success = True
            for service in services:
                if not self.manager.stop_service(service, quiet=False):
                    stop_success = False
            progress.remove_task(task1)

            if not stop_success:
                console.print(
                    "[yellow]Some services were not running or failed to stop[/yellow]"
                )

            # Step 2: Rebuild all services
            task2 = progress.add_task(
                f"Step 2: Rebuilding {project} images...", total=None
            )
            build_success = self._build_stack(project, services)
            progress.remove_task(task2)

            if not build_success:
                console.print(
                    f"[red]Failed to rebuild images for {project} stack[/red]"
                )
                return False

            # Step 3: Reload systemd daemon
            task3 = progress.add_task("Step 3: Reloading systemd daemon...", total=None)
            reload_success = self.manager.reload_daemon()
            progress.remove_task(task3)

            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False

            # Step 4: Start all services
            task4 = progress.add_task(
                f"Step 4: Starting all {project} services...", total=None
            )
            start_success = True
            for service in services:
                if not self.manager.start_service(service):
                    start_success = False
            progress.remove_task(task4)

            if start_success:
                console.print(f"[green]Successfully rebuilt {display_name}[/green]")
                return True
            else:
                console.print(
                    f"[red]Failed to start some services in {display_name}[/red]"
                )
                return False

    def _build_stack(self, project: str, services: List[str]) -> bool:
        """Build images for all services in a stack using quadlet build process"""
        success = True
        for service in services:
            if not self.build_service(service):
                success = False
        return success

    def build_stack_podman(self, project: str, services: List[str]) -> bool:
        """Build images for all services in a stack using podman build"""
        success = True
        for service in services:
            if not self.build_service_podman(service):
                success = False
        return success

    def rebuild_vllm_delegator_mcp(self) -> bool:
        """Rebuild vLLM Delegator MCP container image (for quadlet management)"""
        # Initialize original_cwd to prevent unbound variable error
        original_cwd = os.getcwd()

        # Configuration for vLLM Delegator MCP rebuild
        CONTAINER_NAME = "vllm-delegator-mcp"
        IMAGE_NAME = "localhost/vllm-delegator-mcp:latest"
        DOCKERFILE = "Dockerfile-vllm-delegator"
        MCP_SERVICE_DIR = "/home/pwp/srv/coding_agent/mcp/mcp-vllm-delegator"

        console.print("[yellow]🔨 Rebuilding vLLM Delegator MCP image...[/yellow]")

        try:
            # Change to the MCP service directory
            original_cwd = os.getcwd()
            if not Path(MCP_SERVICE_DIR).exists():
                console.print(
                    f"[red]MCP service directory not found: {MCP_SERVICE_DIR}[/red]"
                )
                return False

            os.chdir(MCP_SERVICE_DIR)

            # Function to check if container exists
            def container_exists():
                result = subprocess.run(
                    ["podman", "container", "exists", CONTAINER_NAME],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0

            # Function to check if container is running
            def container_running():
                result = subprocess.run(
                    [
                        "podman",
                        "container",
                        "inspect",
                        CONTAINER_NAME,
                        "--format",
                        "{{.State.Running}}",
                    ],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0 and result.stdout.strip() == "true"

            # Stop and remove existing container if it exists (quietly)
            if container_exists():
                if container_running():
                    subprocess.run(
                        ["podman", "stop", CONTAINER_NAME],
                        capture_output=True,
                        text=True,
                    )
                subprocess.run(
                    ["podman", "rm", CONTAINER_NAME], capture_output=True, text=True
                )

            # Remove old image to force rebuild (quietly)
            subprocess.run(
                ["podman", "rmi", IMAGE_NAME], capture_output=True, text=True
            )

            # Build new image
            console.print(f"[yellow]🔨 Building new image: {IMAGE_NAME}[/yellow]")
            if not Path(DOCKERFILE).exists():
                console.print(f"[red]Dockerfile not found: {DOCKERFILE}[/red]")
                return False

            build_cmd = [
                "podman",
                "build",
                "--no-cache",
                "-f",
                DOCKERFILE,
                "-t",
                IMAGE_NAME,
                ".",
            ]
            console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")
            build_result = subprocess.run(build_cmd, capture_output=True, text=True)

            if build_result.returncode != 0:
                console.print("[red]❌ Build failed![/red]")
                if build_result.stderr:
                    console.print(f"[red]{build_result.stderr.strip()}[/red]")
                return False

            console.print("[green]✅ Image rebuilt successfully[/green]")

            return True

        except Exception as e:
            console.print(f"[red]Error during vLLM Delegator MCP rebuild: {e}[/red]")
            return False
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    def rebuild_vllm_proxy(self) -> bool:
        """Rebuild vLLM Proxy container image (for quadlet management)"""
        # Initialize original_cwd to prevent unbound variable error
        original_cwd = os.getcwd()

        # Configuration for vLLM Proxy rebuild
        CONTAINER_NAME = "vllm-proxy"
        IMAGE_NAME = "localhost/vllm-proxy:latest"
        DOCKERFILE = "Dockerfile.vllm_proxy"
        PROXY_SERVICE_DIR = "/home/pwp/srv/local-ai-packaged/vllm-proxy"

        console.print("[yellow]🔨 Rebuilding vLLM Proxy image...[/yellow]")

        try:
            # Change to the proxy service directory
            original_cwd = os.getcwd()
            if not Path(PROXY_SERVICE_DIR).exists():
                console.print(
                    f"[red]Proxy service directory not found: {PROXY_SERVICE_DIR}[/red]"
                )
                return False

            os.chdir(PROXY_SERVICE_DIR)

            # Function to check if container exists
            def container_exists():
                result = subprocess.run(
                    ["podman", "container", "exists", CONTAINER_NAME],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0

            # Function to check if container is running
            def container_running():
                result = subprocess.run(
                    [
                        "podman",
                        "container",
                        "inspect",
                        CONTAINER_NAME,
                        "--format",
                        "{{.State.Running}}",
                    ],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0 and result.stdout.strip() == "true"

            # Stop and remove existing container if it exists (quietly)
            if container_exists():
                if container_running():
                    subprocess.run(
                        ["podman", "stop", CONTAINER_NAME],
                        capture_output=True,
                        text=True,
                    )
                subprocess.run(
                    ["podman", "rm", CONTAINER_NAME], capture_output=True, text=True
                )

            # Remove old image to force rebuild (quietly)
            subprocess.run(
                ["podman", "rmi", IMAGE_NAME], capture_output=True, text=True
            )

            # Build new image
            console.print(f"[yellow]🔨 Building new image: {IMAGE_NAME}[/yellow]")
            if not Path(DOCKERFILE).exists():
                console.print(f"[red]Dockerfile not found: {DOCKERFILE}[/red]")
                return False

            build_cmd = [
                "podman",
                "build",
                "--no-cache",
                "-f",
                DOCKERFILE,
                "-t",
                IMAGE_NAME,
                ".",
            ]
            console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")
            build_result = subprocess.run(build_cmd, capture_output=True, text=True)

            if build_result.returncode != 0:
                console.print("[red]❌ Build failed![/red]")
                if build_result.stderr:
                    console.print(f"[red]{build_result.stderr.strip()}[/red]")
                return False

            console.print("[green]✅ Image rebuilt successfully[/green]")

            return True

        except Exception as e:
            console.print(f"[red]Error during vLLM Proxy rebuild: {e}[/red]")
            return False
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    def update_images_and_restart(self, target: str) -> bool:
        """Update container images and restart service (for quadlets with auto-update)"""
        console.print(f"[yellow]Updating images for {target}...[/yellow]")

        # For quadlets, we can trigger podman auto-update
        update_cmd = ["podman", "auto-update"]
        console.print(f"[cyan]exec: {' '.join(update_cmd)}[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Updating container images", total=None)
            result = subprocess.run(update_cmd, capture_output=True, text=True)
            progress.remove_task(task)

        if result.returncode == 0:
            console.print("[green]Images updated successfully[/green]")
            if result.stdout:
                console.print(result.stdout)

            # Restart the service to use updated images
            from service_lifecycle import ServiceLifecycle

            lifecycle = ServiceLifecycle(self.manager)
            return lifecycle.restart(target)
        else:
            console.print(
                f"[red]Failed to update images: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
            )
            return False
