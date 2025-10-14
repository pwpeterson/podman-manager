"""Container lifecycle operations."""

import subprocess
import time
from typing import List

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from config import console


class ContainerOperations:
    """Container lifecycle operations"""

    def __init__(self, manager):
        self.manager = manager

    def handle_container_dependencies(self, service: str) -> bool:
        """Handle container removal by checking status first, then stopping if needed"""
        try:
            # First, check if container exists and its status
            status_cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                f"name=^{service}$",
                "--format",
                "{{.Names}} {{.Status}}",
            ]
            console.print(f"  [cyan]exec: {' '.join(status_cmd)}[/cyan]")
            status_result = subprocess.run(status_cmd, capture_output=True, text=True)

            if status_result.returncode != 0:
                console.print("[yellow]Warning checking container status[/yellow]")
                # Continue with removal attempt anyway

            container_info = status_result.stdout.strip()
            if not container_info:
                console.print(f"[dim]Container {service} does not exist[/dim]")
                return True  # Already removed, success

            # Check if container is running and stop it first if needed
            if "Up" in container_info or "running" in container_info.lower():
                console.print("[green]Stopping container...[/green]")
                # Stop the container first
                stop_cmd = ["podman", "stop", service]
                console.print(f"  [cyan]exec: {' '.join(stop_cmd)}[/cyan]")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(
                        f"Stopping container: {service}", total=None
                    )
                    stop_result = subprocess.run(
                        stop_cmd, capture_output=True, text=True
                    )
                    progress.remove_task(task)

                if stop_result.returncode != 0:
                    stop_error = stop_result.stderr.strip()
                    if "did not die within timeout" in stop_error.lower():
                        console.print(
                            "[green]Container took longer than expected to stop (SIGKILL used)[/green]"
                        )
                    else:
                        console.print(
                            f"[yellow]Warning stopping container: {stop_error}[/yellow]"
                        )

                # Verify container has fully stopped before attempting removal
                max_wait = 5  # Maximum seconds to wait
                wait_time = 0.0
                while wait_time < max_wait:
                    time.sleep(0.5)
                    wait_time += 0.5

                    # Check if container is still stopping
                    status_check_cmd = [
                        "podman",
                        "ps",
                        "-a",
                        "--filter",
                        f"name=^{service}$",
                        "--format",
                        "{{.Status}}",
                    ]
                    status_check = subprocess.run(
                        status_check_cmd, capture_output=True, text=True
                    )

                    if status_check.returncode == 0:
                        status = status_check.stdout.strip()
                        if (
                            "stopping" not in status.lower()
                            and "up" not in status.lower()
                        ):
                            break
                        elif wait_time >= max_wait:
                            console.print(
                                f"[yellow]Container still stopping after {max_wait}s, proceeding anyway[/yellow]"
                            )
                    else:
                        break  # If status check fails, proceed with removal

            # Now remove the container (after ensuring it's stopped)
            console.print(f"[green]Removing: {service}[/green]")
            rm_cmd = ["podman", "rm", service]
            console.print(f"  [cyan]exec: {' '.join(rm_cmd)}[/cyan]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Removing container: {service}", total=None)
                rm_result = subprocess.run(rm_cmd, capture_output=True, text=True)
                progress.remove_task(task)

            if rm_result.returncode == 0:
                console.print(f"[green]Container removed: {service}[/green]")
                return True
            else:
                error_msg = rm_result.stderr.strip()
                if "dependent containers" in error_msg.lower():
                    console.print(
                        "[yellow]Container has dependencies, handling...[/yellow]"
                    )
                    return self._handle_dependent_containers(service, error_msg)
                elif "no such container" in error_msg.lower():
                    console.print(f"[dim]Container {service} already removed[/dim]")
                    return True
                else:
                    console.print(f"[red]Error removing container: {error_msg}[/red]")
                    return False

        except Exception as e:
            console.print(f"[red]Error handling container removal: {e}[/red]")
            return False

    def _handle_dependent_containers(self, service: str, error_msg: str) -> bool:
        """Handle containers with dependencies"""
        try:
            # Extract dependent container IDs from error message
            import re

            dep_pattern = r"dependent containers.*?before it: ([a-f0-9]+):"
            matches = re.findall(dep_pattern, error_msg)

            if matches:
                # Get names of dependent containers and remove them
                for dep_id in matches:
                    name_cmd = [
                        "podman",
                        "ps",
                        "-a",
                        "--filter",
                        f"id={dep_id}",
                        "--format",
                        "{{.Names}}",
                    ]
                    console.print(f"  [cyan]exec: {' '.join(name_cmd)}[/cyan]")
                    name_result = subprocess.run(
                        name_cmd, capture_output=True, text=True
                    )

                    if name_result.returncode == 0 and name_result.stdout.strip():
                        dep_name = name_result.stdout.strip()
                        console.print(
                            f"[green]Removing dependent container: {dep_name} ({dep_id[:12]})[/green]"
                        )

                        # Remove dependent container with force
                        dep_rm_cmd = ["podman", "rm", "-f", dep_name]
                        console.print(f"  [cyan]exec: {' '.join(dep_rm_cmd)}[/cyan]")
                        dep_result = subprocess.run(
                            dep_rm_cmd, capture_output=True, text=True
                        )

                        if dep_result.returncode == 0:
                            console.print(
                                f"[green]Removed dependent container: {dep_name}[/green]"
                            )
                        else:
                            console.print(
                                f"[yellow]Warning removing {dep_name}: {dep_result.stderr.strip()}[/yellow]"
                            )

                # Now try to remove the main container again
                console.print(f"[green]Retrying removal of {service}...[/green]")
                rm_cmd = ["podman", "rm", service]
                console.print(f"  [cyan]exec: {' '.join(rm_cmd)}[/cyan]")
                rm_result = subprocess.run(rm_cmd, capture_output=True, text=True)

                if rm_result.returncode == 0:
                    console.print(
                        f"[green]Successfully removed container: {service}[/green]"
                    )
                    return True
                else:
                    console.print(
                        f"[red]Still failed to remove {service}: {rm_result.stderr.strip()}[/red]"
                    )
                    return False
            else:
                console.print(
                    "[yellow]Could not parse dependency information from error[/yellow]"
                )
                return False

        except Exception as e:
            console.print(f"[red]Error handling dependencies: {e}[/red]")
            return False

    def show_logs(self, target: str, follow: bool = False, tail: int = 100) -> None:
        """Show container logs"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            # Check if container exists first
            check_cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                f"name={target}",
                "--format",
                "{{.Names}}",
            ]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True)

            if not check_result.stdout.strip():
                console.print(
                    f"[yellow]Container '{target}' not found or not running[/yellow]"
                )
                console.print(
                    "[dim]Try running: pm list to see available services[/dim]"
                )
                return

            cmd = ["podman", "compose", "-f", project, "logs", target, "--"]
            if tail > 0:
                cmd.extend(["-n", str(tail)])
            if follow:
                cmd.append("-f")

            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode != 0:
                console.print(
                    f"[yellow]No logs available for {target} or container not running[/yellow]"
                )

        except Exception as e:
            console.print(f"[red]Error showing logs: {e}[/red]")

    def exec_command(self, target: str, command: List[str]) -> None:
        """Execute command in container"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            cmd = ["podman", "compose", "-f", project, "exec", target] + command
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            subprocess.run(cmd, cwd=self.manager.compose_dir)

        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")

    def build(self, target: str, no_cache: bool = False) -> None:
        """Build container images"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            cmd = ["podman", "compose", "-f", project, "build"]
            if no_cache:
                cmd.append("--no-cache")
            cmd.append(target)

            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Build completed for {target}[/green]")
            else:
                console.print(f"[red]Build failed for {target}[/red]")

        except Exception as e:
            console.print(f"[red]Error building: {e}[/red]")

    def prune(self) -> None:
        """Remove unused images and containers"""
        try:
            console.print("[yellow]Pruning unused containers...[/yellow]")
            subprocess.run(["podman", "container", "prune", "-f"])

            console.print("[yellow]Pruning unused images...[/yellow]")
            subprocess.run(["podman", "image", "prune", "-f"])

            console.print("[green]Prune completed[/green]")

        except Exception as e:
            console.print(f"[red]Error pruning: {e}[/red]")

    def remove(self, target: str) -> None:
        """Remove containers"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            cmd = ["podman", "compose", "-f", project, "rm", "-f", target]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Removed {target}[/green]")
            else:
                console.print(f"[red]Failed to remove {target}[/red]")

        except Exception as e:
            console.print(f"[red]Error removing: {e}[/red]")

    def pull(self, target: str) -> None:
        """Pull latest images"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            cmd = ["podman", "compose", "-f", project, "pull", target]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Pulled latest images for {target}[/green]")
            else:
                console.print(f"[red]Failed to pull images for {target}[/red]")

        except Exception as e:
            console.print(f"[red]Error pulling: {e}[/red]")

    def reinit(
        self,
        target: str,
        build: bool = False,
        dry_run: bool = False,
        remove_orphans: bool = False,
    ) -> bool:
        """Reinitialize containers (remove and recreate)"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return False

            if dry_run:
                console.print(f"[yellow]DRY RUN: Would reinitialize {target}[/yellow]")
                console.print("[dim]Steps that would be performed:[/dim]")
                console.print("[dim]1. Stop containers[/dim]")
                console.print("[dim]2. Remove containers[/dim]")
                if build:
                    console.print("[dim]3. Build images[/dim]")
                console.print("[dim]3/4. Start containers[/dim]")
                return True

            console.print(f"[yellow]Reinitializing {target}...[/yellow]")

            # Stop
            stop_cmd = ["podman", "compose", "-f", project, "stop", target]
            console.print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
            subprocess.run(
                stop_cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            # Remove using direct podman command (compose rm not supported by podman-compose)
            rm_cmd = ["podman", "rm", "-f", target]
            console.print(f"[cyan]exec: {' '.join(rm_cmd)}[/cyan]")
            subprocess.run(rm_cmd, capture_output=True, text=True)

            # Build if requested
            if build:
                build_cmd = ["podman", "compose", "-f", project, "build", target]
                console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")
                result = subprocess.run(
                    build_cmd,
                    cwd=self.manager.compose_dir,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    console.print(f"[red]Build failed for {target}[/red]")
                    return False

            # Start
            up_cmd = ["podman", "compose", "-f", project, "up", "-d", target]
            if remove_orphans:
                up_cmd.append("--remove-orphans")

            console.print(f"[cyan]exec: {' '.join(up_cmd)}[/cyan]")
            result = subprocess.run(
                up_cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            if result.returncode == 0:
                console.print(f"[green]✓ {target} reinitialized[/green]")
                return True
            else:
                console.print(f"[red]✗ Failed to reinitialize {target}[/red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr.strip()}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error reinitializing: {e}[/red]")
            return False

    def restart(self, target: str, remove_orphans: bool = False) -> bool:
        """Restart services"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return False

            cmd = ["podman", "compose", "-f", project, "restart", target]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Restarted {target}[/green]")
                return True
            else:
                console.print(f"[red]Failed to restart {target}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error restarting: {e}[/red]")
            return False

    def stop(self, target: str, remove_orphans: bool = False) -> bool:
        """Stop services"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return False

            cmd = ["podman", "compose", "-f", project, "stop", target]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Stopped {target}[/green]")
                return True
            else:
                console.print(f"[red]Failed to stop {target}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error stopping: {e}[/red]")
            return False

    def down(self, target: str) -> bool:
        """Stop all services in a project"""
        try:
            # Find the compose file for the target project
            projects = self.manager._parse_compose_files()

            # Check if target is a project name
            compose_file = None
            for project_name, project_info in projects.items():
                if target == project_name:
                    compose_file = project_info["file"]
                    break

            if not compose_file:
                # Try to find by service name
                service_project = self.manager._find_service_project(target)
                if service_project:
                    compose_file = self.manager.compose_dir / service_project
                else:
                    console.print(f"[red]Project or service '{target}' not found[/red]")
                    return False

            cmd = ["podman", "compose", "-f", compose_file.name, "down"]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

            # Suppress verbose output from podman-compose
            result = subprocess.run(
                cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            if result.returncode == 0:
                # Parse output to show clean service list
                if result.stdout:
                    lines = result.stdout.split("\n")
                    stopped_services = []
                    for line in lines:
                        # Look for service names being stopped
                        if "podman stop" in line and "-t 10" in line:
                            service = line.split()[-1]
                            if service and service not in stopped_services:
                                stopped_services.append(service)

                    # Show clean output
                    for service in stopped_services:
                        console.print(f"[green]✓ {service}[/green]")

                console.print("[green]✓ All services stopped[/green]")
                return True
            else:
                console.print(f"[red]Failed to stop services in {target}[/red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr.strip()}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error stopping project: {e}[/red]")
            return False

    def show_service_status(self, target: str) -> None:
        """Show detailed service status (compatibility method)"""
        console.print(
            f"[yellow]Service status unavailable in compose mode for {target}[/yellow]"
        )
        console.print("[dim]Use 'pm list' to see available services[/dim]")

    def prune_containers(self) -> None:
        """Remove unused containers and images (compatibility method)"""
        self.prune()

    def show_system_df(self) -> None:
        """Show system disk usage (compatibility method)"""
        console.print("[yellow]System df not available in compose mode[/yellow]")
        console.print("[dim]Use 'pm system-df' command instead[/dim]")

    def start(self, target: str) -> bool:
        """Start services in a project"""
        try:
            # Find the compose file for the target project
            projects = self.manager._parse_compose_files()

            # Check if target is a project name
            compose_file = None
            for project_name, project_info in projects.items():
                if target == project_name:
                    compose_file = project_info["file"]
                    break

            if not compose_file:
                # Try to find by service name
                service_project = self.manager._find_service_project(target)
                if service_project:
                    compose_file = self.manager.compose_dir / service_project
                else:
                    console.print(f"[red]Project or service '{target}' not found[/red]")
                    return False

            cmd = ["podman", "compose", "-f", compose_file.name, "up", "-d"]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

            # Suppress verbose output from podman-compose
            result = subprocess.run(
                cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            if result.returncode == 0:
                # Parse output to show clean service list
                if result.stdout:
                    lines = result.stdout.split("\n")
                    started_services = []
                    for line in lines:
                        # Look for service names being started
                        if "podman run" in line or "Creating" in line:
                            # Extract service name from various output formats
                            words = line.split()
                            for word in words:
                                if (
                                    word
                                    and not word.startswith("-")
                                    and "/" not in word
                                    and "=" not in word
                                ):
                                    if word not in started_services and len(word) > 2:
                                        started_services.append(word)
                                        break

                    # Show clean output
                    for service in started_services:
                        console.print(f"[green]✓ {service}[/green]")

                console.print("[green]✓ All services started[/green]")
                return True
            else:
                console.print(f"[red]Failed to start services in {target}[/red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr.strip()}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error starting project: {e}[/red]")
            return False

    def enable(self, target: str) -> bool:
        """Enable service (compatibility method)"""
        console.print(
            f"[yellow]Enable command not available in compose mode for {target}[/yellow]"
        )
        console.print("[cyan]Compose services don't have enable/disable concept[/cyan]")
        return False

    def disable(self, target: str) -> bool:
        """Disable service (compatibility method)"""
        console.print(
            f"[yellow]Disable command not available in compose mode for {target}[/yellow]"
        )
        console.print("[cyan]Compose services don't have enable/disable concept[/cyan]")
        return False

    def update_images_and_restart(self, target: str) -> bool:
        """Update images and restart (compatibility method)"""
        console.print(
            f"[yellow]Update command not available in compose mode for {target}[/yellow]"
        )
        console.print("[cyan]Use 'pm pull' and 'pm restart' commands instead[/cyan]")
        return False

    def check_auto_update_status(self) -> None:
        """Check auto-update status (compatibility method)"""
        console.print("[yellow]Auto-update not available in compose mode[/yellow]")
        console.print("[cyan]Auto-update is a quadlet/systemd feature[/cyan]")

    def reload_daemon(self) -> bool:
        """Reload daemon (compatibility method)"""
        console.print("[yellow]Reload daemon not available in compose mode[/yellow]")
        console.print("[cyan]This is a systemd-specific command[/cyan]")
        return False
