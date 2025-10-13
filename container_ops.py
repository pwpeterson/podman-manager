"""Container lifecycle operations."""

import subprocess
import time

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
            console.print(f"  [white]exec: {' '.join(status_cmd)}[/white]")
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
                console.print(f"  [white]exec: {' '.join(stop_cmd)}[/white]")

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
            console.print(f"  [white]exec: {' '.join(rm_cmd)}[/white]")

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
                    console.print(f"  [white]exec: {' '.join(name_cmd)}[/white]")
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
                        console.print(f"  [white]exec: {' '.join(dep_rm_cmd)}[/white]")
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
                console.print(f"  [white]exec: {' '.join(rm_cmd)}[/white]")
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
