"""Container building and image management operations."""

import os
import subprocess
from pathlib import Path
from typing import List, Optional, Union

from rich.progress import Progress, SpinnerColumn, TextColumn

from core.config import console, verbose_print


class ContainerBuilder:
    """Handles container building and image management operations"""

    def __init__(self, manager):
        self.manager = manager
        self._build_context = {}  # Store build context for AI analysis

    def _find_stack_for_service(self, service_name: str) -> Optional[str]:
        """Find which stack directory contains the given service."""
        quadlets_base_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")

        if not quadlets_base_dir.exists():
            # Fallback logic if directory doesn't exist
            if service_name.startswith("local-ai-"):
                return "local-ai-stack"
            elif service_name.startswith("supabase-"):
                return "supabase-stack"
            elif service_name.startswith("vllm-"):
                return "vllm-stack"
            elif "-" in service_name:
                base_name = service_name.split("-")[0]
                return f"{base_name}-stack"
            else:
                return f"{service_name}-stack"

        try:
            # Search all stack directories for the service
            for stack_dir in quadlets_base_dir.iterdir():
                if not stack_dir.is_dir():
                    continue

                # Look for Dockerfile.service-name in this stack directory
                dockerfile_path = stack_dir / f"Dockerfile.{service_name}"
                if dockerfile_path.exists():
                    return stack_dir.name

                # Also check for .container and .service files
                container_file = stack_dir / f"{service_name}.container"
                service_file = stack_dir / f"{service_name}.service"
                if container_file.exists() or service_file.exists():
                    return stack_dir.name

            # If not found, use fallback logic based on service name patterns
            if service_name.startswith("local-ai-"):
                return "local-ai-stack"
            elif service_name.startswith("supabase-"):
                return "supabase-stack"
            elif service_name.startswith("vllm-"):
                return "vllm-stack"
            elif "-" in service_name:
                base_name = service_name.split("-")[0]
                return f"{base_name}-stack"
            else:
                # For single word services, try common stack patterns first
                common_stacks = ["local-ai-stack", "vllm-stack", "supabase-stack"]
                for stack in common_stacks:
                    stack_dir = quadlets_base_dir / stack
                    if stack_dir.exists():
                        # Check if any service file in this stack might match
                        dockerfile_path = stack_dir / f"Dockerfile.{service_name}"
                        if dockerfile_path.exists():
                            return stack
                # Final fallback
                return f"{service_name}-stack"

        except Exception as e:
            console.print(f"[dim]Error scanning for service stack: {e}[/dim]")
            # Fallback logic based on service name patterns
            if service_name.startswith("local-ai-"):
                return "local-ai-stack"
            elif service_name.startswith("supabase-"):
                return "supabase-stack"
            elif service_name.startswith("vllm-"):
                return "vllm-stack"
            elif "-" in service_name:
                base_name = service_name.split("-")[0]
                return f"{base_name}-stack"
            else:
                return f"{service_name}-stack"

    def _render_ansi_output(self, output: str) -> None:
        """Render ANSI-colored output from subprocess"""
        # For now, just print the output directly
        # Rich console should handle ANSI codes properly
        console.print(output)

    def _trigger_build_ai_analysis(
        self,
        target: str,
        build_error: str,
        build_output: str = "",
        build_command: str = "",
        verbose: bool = False,
    ) -> None:
        """Trigger automatic AI analysis for build failures"""
        try:
            from ai_analyzer import ai_analyzer

            # Initialize AI analyzer with manager if not already done
            if ai_analyzer.manager is None:
                ai_analyzer.manager = self.manager

            # Get build context for this target
            build_context = self._build_context.get(target, {})

            # Prepare focused build failure context - just Dockerfile and errors
            context_data = {
                "build_error": build_error,
                "build_output": build_output,
                "dockerfile_path": build_context.get("dockerfile_path", ""),
                "target": target,
            }

            # Run AI analysis with default agent
            result = ai_analyzer.ai_analyze(
                analysis_type="build_failure",
                target=target,
                context_data=context_data,
                ai_agent=None,  # Always use default agent
                verbose=verbose,
            )

            if result:
                pass  # Analysis completed, no message needed
            else:
                console.print("[yellow]⚠ Unable to analyze build failure[/yellow]")

        except Exception:
            # Silently fail - don't let AI analysis errors break the build process
            pass

    def _store_build_context(self, target: str, **context) -> None:
        """Store build context for AI analysis"""
        self._build_context[target] = context

    def _get_build_context(self, target: str) -> dict:
        """Get stored build context for AI analysis"""
        return self._build_context.get(target, {})

    def _get_container_image(self, container_name: str) -> Optional[str]:
        """Get the image name used by a container using podman ps command."""
        try:
            # Use the exact command format specified by the user
            cmd = f"podman ps --filter name={container_name} --format '{{{{.Image}}}}'"
            verbose_print(f"[cyan]exec: {cmd}[/cyan]")

            result = subprocess.run(
                [
                    "podman",
                    "ps",
                    "--filter",
                    f"name={container_name}",
                    "--format",
                    "{{.Image}}",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and result.stdout.strip():
                image_name = result.stdout.strip()
                verbose_print(
                    f"    [cyan]Found image for {container_name}: {image_name}[/cyan]"
                )
                return image_name
            else:
                verbose_print(
                    f"[dim]No running container found for {container_name}[/dim]"
                )
                return None

        except Exception as e:
            verbose_print(f"[dim]Error getting container image: {e}[/dim]")
            return None

    def _cleanup_existing_container(self, container_name: str) -> None:
        """Stop and remove existing container following the proper cleanup sequence."""
        try:
            # Check if container exists (silently)
            exists_result = subprocess.run(
                ["podman", "container", "exists", container_name],
                capture_output=True,
                text=True,
            )

            if exists_result.returncode == 0:
                # Container exists, check if it's running
                verbose_print(
                    f"[cyan]exec: podman container inspect {container_name} --format {{{{.State.Running}}}}[/cyan]"
                )
                inspect_result = subprocess.run(
                    [
                        "podman",
                        "container",
                        "inspect",
                        container_name,
                        "--format",
                        "{{.State.Running}}",
                    ],
                    capture_output=True,
                    text=True,
                )

                # Stop container if running
                if (
                    inspect_result.returncode == 0
                    and inspect_result.stdout.strip() == "true"
                ):
                    verbose_print(f"[cyan]exec: podman stop {container_name}[/cyan]")
                    subprocess.run(
                        ["podman", "stop", container_name],
                        capture_output=True,
                        text=True,
                    )
                    console.print(f"[green]Stopped container: {container_name}[/green]")

                # Remove container
                verbose_print(f"[cyan]exec: podman rm {container_name}[/cyan]")
                subprocess.run(
                    ["podman", "rm", container_name],
                    capture_output=True,
                    text=True,
                )
                console.print(f"[green]Removed container: {container_name}[/green]")

        except Exception as e:
            verbose_print(f"[dim]Error during container cleanup: {e}[/dim]")

    def build_service(self, target: str) -> bool:
        """Build images for a single service by looking for Dockerfile.<service_name>"""
        try:
            # Dynamically determine stack name from directory structure
            stack_name = self._find_stack_for_service(target)

            # Construct Dockerfile name using the full service name
            dockerfile_name = f"Dockerfile.{target}"

            # Search in quadlets directory with stack name subdirectory
            quadlets_dir = f"/home/pwp/srv/local-ai-packaged/quadlets/{stack_name}/"

            dockerfile_path: Union[Path, None] = None
            build_dir: Union[Path, None] = None

            # Search for the Dockerfile in quadlets directory
            console.print(f"[green]Checking for {dockerfile_name}[/green]")
            verbose_print(f"[cyan]exec: Checking directory {quadlets_dir}[/cyan]")

            source_path = Path(quadlets_dir)
            if source_path.exists():
                # Search recursively for the Dockerfile
                for dockerfile in source_path.rglob(dockerfile_name):
                    dockerfile_path = dockerfile
                    build_dir = dockerfile.parent
                    verbose_print(
                        f"[cyan]exec: Found {dockerfile_name} at {dockerfile_path}[/cyan]"
                    )
                    break
            else:
                verbose_print(
                    f"[cyan]exec: Directory {quadlets_dir} does not exist[/cyan]"
                )

            if not dockerfile_path or not dockerfile_path.exists():
                console.print()
                console.print(
                    f"[yellow]Build stopped: Missing Dockerfile.{target}[/yellow]"
                )
                console.print()
                return False

            # Ensure build_dir is not None before passing to _build_with_dockerfile
            if build_dir is None:
                console.print(f"[red]Build directory not found for {target}[/red]")
                return False

            # Build the container image
            return self._build_with_dockerfile(target, build_dir, dockerfile_name)  # type: ignore

        except Exception as e:
            console.print(f"[red]Error building {target}: {e}[/red]")
            return False

    def _build_with_dockerfile(
        self, target: str, build_dir: Path, dockerfile_name: str
    ) -> bool:
        """Build container image using the specified Dockerfile"""
        original_cwd = os.getcwd()
        # Initialize service_name for error handling
        service_name = target
        try:
            os.chdir(build_dir)

            # Store build context for AI analysis
            self._store_build_context(
                target,
                dockerfile_path=str(build_dir / dockerfile_name),
                build_dir=str(build_dir),
                service_type="quadlet_container",
            )

            # Determine service names
            service_name = target  # Full service name (e.g., "local-ai-ollama")
            stack_name = self._find_stack_for_service(
                service_name
            )  # e.g., "local-ai-stack"

            # Calculate short_service_name by removing stack prefix
            if stack_name and stack_name.endswith("-stack"):
                stack_prefix = stack_name[
                    :-6
                ]  # Remove "-stack" suffix (e.g., "local-ai")
                if service_name.startswith(f"{stack_prefix}-"):
                    short_service_name = service_name[
                        len(stack_prefix) + 1 :
                    ]  # Remove "local-ai-" prefix
                else:
                    short_service_name = (
                        service_name  # Fallback if pattern doesn't match
                    )
            else:
                short_service_name = service_name  # Fallback if no stack found

            # Get the actual image name from running container using short service name
            actual_image_name = self._get_container_image(short_service_name)
            if not actual_image_name:
                # Fallback: try with full service name
                actual_image_name = self._get_container_image(service_name)

            # Determine target image name for building (what we want to build)
            target_image_name = f"localhost/{service_name}:latest"

            # Update build context with image name
            self._build_context[target]["image_name"] = target_image_name

            # Service information (hidden in normal output)
            # verbose_print(f"[dim]Service name: {service_name}[/dim]")
            # verbose_print(f"[dim]Stack name: {stack_name}[/dim]")
            # verbose_print(f"[dim]Short service name: {short_service_name}[/dim]")
            # verbose_print(f"[dim]Image name: {actual_image_name or target_image_name}[/dim]")

            # Step 1: Stop and remove existing container (try both names)
            self._cleanup_existing_container(service_name)  # Try full name first
            self._cleanup_existing_container(
                short_service_name
            )  # Try short name as fallback

            # Step 2: Remove the current image if we found one
            if actual_image_name:
                verbose_print(f"[cyan]exec: podman rmi {actual_image_name}[/cyan]")
                subprocess.run(
                    ["podman", "rmi", actual_image_name], capture_output=True, text=True
                )
                console.print(f"[green]Removed image: {actual_image_name}[/green]")
            else:
                # Fallback: remove image by expected name
                verbose_print(f"[cyan]exec: podman rmi {target_image_name}[/cyan]")
                subprocess.run(
                    ["podman", "rmi", target_image_name], capture_output=True, text=True
                )
                verbose_print(
                    f"[dim]No running container found, tried to remove expected image: {target_image_name}[/dim]"
                )

            # Build new image using target image name
            build_cmd = [
                "podman",
                "build",
                "--no-cache",
                "-f",
                dockerfile_name,
                "-t",
                target_image_name,
                ".",
            ]
            verbose_print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")

            from core.config import _verbose_enabled

            if _verbose_enabled:
                # In verbose mode, show build output with indentation and capture for AI analysis
                console.print(f"[green]Building image: {target_image_name}[/green]")

                process = subprocess.Popen(
                    build_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                # Capture output while displaying it live
                captured_output = []
                if process.stdout:
                    for line in iter(process.stdout.readline, ""):  # type: ignore
                        if line.strip():
                            console.print(f"  {line.rstrip()}")
                            captured_output.append(line.rstrip())
                process.wait()

                # Create a mock result object with captured output for AI analysis
                class MockResult:
                    def __init__(self, returncode, stdout):
                        self.returncode = returncode
                        self.stdout = stdout
                        self.stderr = None  # stderr is merged with stdout

                build_result = MockResult(
                    process.returncode, "\n".join(captured_output)
                )
            else:
                # In non-verbose mode, use spinner and capture output
                with Progress(
                    SpinnerColumn(),
                    TextColumn(f"[yellow]Building image: {target_image_name}[/yellow]"),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task("building", total=None)
                    build_result = subprocess.run(
                        build_cmd, capture_output=True, text=True
                    )
                    progress.remove_task(task)

            if build_result.returncode != 0:
                console.print(f"[red]Failed to build {target} image.[/red]")

                # Collect error information for AI analysis
                build_error = ""
                build_output = ""
                build_command = " ".join(build_cmd)

                # Handle both Popen and CompletedProcess objects
                if hasattr(build_result, "stderr") and build_result.stderr:
                    if isinstance(build_result.stderr, str):
                        build_error = build_result.stderr.strip()
                        console.print(f"[red]{build_error}[/red]")

                if hasattr(build_result, "stdout") and build_result.stdout:
                    if isinstance(build_result.stdout, str):
                        build_output = build_result.stdout.strip()

                # Trigger AI analysis for build failure
                from core.config import _verbose_enabled

                self._trigger_build_ai_analysis(
                    target=service_name,
                    build_error=build_error,
                    build_output=build_output,
                    build_command=build_command,
                    verbose=_verbose_enabled,
                )

                return False

            # Show build output in non-verbose mode (only if captured and build failed)
            if (
                not _verbose_enabled
                and build_result.returncode != 0
                and hasattr(build_result, "stdout")
                and build_result.stdout
            ):
                if isinstance(build_result.stdout, str):
                    for line in build_result.stdout.strip().split("\n"):  # type: ignore
                        if line.strip():
                            console.print(line)

            console.print(
                f"[green]✅ Image {target_image_name} built successfully[/green]"
            )

            return True

        except Exception as e:
            console.print(
                f"[red]Error during container build for {service_name}: {e}[/red]"
            )
            return False
        finally:
            os.chdir(original_cwd)

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

            # Determine the quadlet group from stack name
            stack_name = self._find_stack_for_service(service_name)
            if stack_name:
                # Convert stack name to group name (remove -stack suffix)
                if stack_name.endswith("-stack"):
                    quadlet_group = stack_name[:-6]  # Remove "-stack"
                else:
                    quadlet_group = stack_name
            else:
                # Fallback: extract group from service name
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

                        # Collect error information for AI analysis
                        build_error = (
                            result.stderr.strip()
                            if result.stderr
                            else "Build failed with unknown error"
                        )
                        build_output = result.stdout.strip() if result.stdout else ""
                        build_command = " ".join(build_cmd)

                        if result.stderr:
                            console.print(f"[red]{build_error}[/red]")

                        # Store build context for AI analysis
                        self._store_build_context(
                            target,
                            dockerfile_path=str(Path(build_dir) / dockerfile),
                            build_dir=build_dir,
                            image_name=image_name,
                            service_type="podman_container",
                        )

                        # Trigger AI analysis for build failure
                        from core.config import _verbose_enabled

                        self._trigger_build_ai_analysis(
                            target=target,
                            build_error=build_error,
                            build_output=build_output,
                            build_command=build_command,
                            verbose=_verbose_enabled,
                        )

                        return False

                finally:
                    os.chdir(original_cwd)
            else:
                console.print(
                    f"[yellow]No podman build configuration for {target}[/yellow]"
                )
                return False  # Return False so caller can try alternative approach

        except Exception as e:
            console.print(f"[red]Error in podman build for {target}: {e}[/red]")
            return False

    def rebuild_service(self, target: str) -> bool:
        """Rebuild a single service"""
        # Step 1: Build the service (this now handles build-first-then-stop internally)
        build_success = self.build_service(target)

        if not build_success:
            console.print()
            return False

        # Step 2: Reload systemd daemon
        from core.config import _verbose_enabled

        if _verbose_enabled:
            console.print("[green]Reloading systemd user daemon[/green]")
            reload_success = self.manager.reload_daemon()
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold white]Reloading systemd daemon...[/bold white]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("reloading", total=None)
                reload_success = self.manager.reload_daemon()
                progress.remove_task(task)

        if not reload_success:
            console.print("[red]Failed to reload systemd daemon[/red]")
            return False

        # Step 3: Start the service
        if _verbose_enabled:
            console.print()
            console.print(f"[green]Starting {target}.service[/green]")
            start_success = self.manager.start_service(target)
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn(f"[green]Starting {target}[/green]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("starting", total=None)
                start_success = self.manager.start_service(target)
                progress.remove_task(task)

        if start_success:
            console.print(f"[green]Successfully built {target}[/green]")
            console.print()
            return True
        else:
            console.print(f"[red]Failed to start {target} after build[/red]")
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
                console.print(f"[red]Failed to build {CONTAINER_NAME} image.[/red]")
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
                console.print(f"[red]Failed to build {CONTAINER_NAME} image.[/red]")
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
            from managers.service_lifecycle import ServiceLifecycle

            lifecycle = ServiceLifecycle(self.manager)
            return lifecycle.restart(target)
        else:
            console.print(
                f"[red]Failed to update images: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
            )
            return False
