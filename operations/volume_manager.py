"""Volume and Network Management Operations for Stack Copying."""

import json
import subprocess
from pathlib import Path
from typing import List

from rich.progress import Progress, SpinnerColumn, TextColumn

from core.config import console, verbose_print
from utils.secure_subprocess import podman_cmd, secure_run


class VolumeNetworkManager:
    """Handles volume copying operations with automatic share network copying."""

    def __init__(self, manager):
        self.manager = manager
        self.quadlet_base_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")

    def copy_stack_volumes(self, source_stack: str, target_stack: str) -> bool:
        """Copy all volumes from source stack to target stack, including share networks.

        Args:
            source_stack: Name of the source stack to copy volumes from
            target_stack: Name of the target stack to copy volumes to

        Returns:
            bool: True if copying was successful, False otherwise
        """
        console.print(
            f"[green]Copying volumes from {source_stack} to {target_stack}...[/green]"
        )
        console.print()

        # Get volume and network dependencies from both runtime and quadlet files
        volumes_to_copy = self._get_stack_volumes(source_stack)
        networks_to_copy = self._get_stack_networks(source_stack)

        # Also check quadlet files for additional network dependencies
        quadlet_networks = self._get_quadlet_network_dependencies(source_stack)
        networks_to_copy.extend(
            [net for net in quadlet_networks if net not in networks_to_copy]
        )

        if not volumes_to_copy and not networks_to_copy:
            console.print(
                f"[yellow]No volumes or networks found in {source_stack}[/yellow]"
            )
            return True

        # Show what will be copied
        self._show_copy_plan(
            volumes_to_copy, networks_to_copy, source_stack, target_stack
        )

        success = True

        # Copy networks first (volumes may depend on them)
        if networks_to_copy:
            console.print("[green]Copying share networks...[/green]")
            for network_name in networks_to_copy:
                if not self._copy_network(network_name, source_stack, target_stack):
                    success = False

        # Copy volumes
        if volumes_to_copy:
            console.print("[green]Copying volumes...[/green]")
            for volume_name in volumes_to_copy:
                if not self._copy_volume(volume_name, source_stack, target_stack):
                    success = False

        if success:
            console.print(
                f"[green]Successfully copied all volumes and networks from {source_stack} to {target_stack}[/green]"
            )
        else:
            console.print(
                f"[red]Some volumes or networks failed to copy from {source_stack} to {target_stack}[/red]"
            )

        return success

    def _get_stack_volumes(self, stack_name: str) -> List[str]:
        """Get list of volume names from a stack."""
        volumes = []

        try:
            # Get volumes from podman
            verbose_print("[cyan]exec: podman volume ls --format {{.Name}}[/cyan]")
            result = podman_cmd(["volume", "ls", "--format", "{{.Name}}"], timeout=10)

            if result.returncode == 0:
                all_volumes = (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )

                # Filter volumes that belong to this stack
                stack_prefix = stack_name.replace("-stack", "")
                for volume in all_volumes:
                    if volume.startswith(stack_prefix) or stack_prefix in volume:
                        volumes.append(volume)

        except Exception as e:
            verbose_print(f"[red]Error getting volumes for {stack_name}: {e}[/red]")

        return volumes

    def _get_stack_networks(self, stack_name: str) -> List[str]:
        """Get list of network names from a stack."""
        networks = []

        try:
            # Get networks from podman
            verbose_print("[cyan]exec: podman network ls --format {{.Name}}[/cyan]")
            result = podman_cmd(["network", "ls", "--format", "{{.Name}}"], timeout=10)

            if result.returncode == 0:
                all_networks = (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )

                # Filter networks that belong to this stack (exclude default networks)
                stack_prefix = stack_name.replace("-stack", "")
                default_networks = {"podman", "default", "bridge", "host", "none"}

                for network in all_networks:
                    if (
                        network.startswith(stack_prefix) or stack_prefix in network
                    ) and network not in default_networks:
                        networks.append(network)

        except Exception as e:
            verbose_print(f"[red]Error getting networks for {stack_name}: {e}[/red]")

        return networks

    def _get_quadlet_network_dependencies(self, stack_name: str) -> List[str]:
        """Get network dependencies from quadlet .container files."""
        networks = []

        try:
            stack_dir = self.quadlet_base_dir / stack_name
            if not stack_dir.exists():
                return networks

            # Look for .container files
            for container_file in stack_dir.glob("*.container"):
                if container_file.name.endswith(".disabled"):
                    continue

                # Parse container file for Network= entries
                try:
                    with open(container_file, "r") as f:
                        content = f.read()

                    # Look for Network= lines
                    for line in content.split("\n"):
                        line = line.strip()
                        if line.startswith("Network="):
                            network_name = line.split("=", 1)[1].strip()
                            if network_name and network_name not in networks:
                                networks.append(network_name)

                except Exception as e:
                    verbose_print(
                        f"[yellow]Warning: Could not parse {container_file}: {e}[/yellow]"
                    )

        except Exception as e:
            verbose_print(
                f"[red]Error getting quadlet network dependencies for {stack_name}: {e}[/red]"
            )

        return networks

    def _show_copy_plan(
        self, volumes: List[str], networks: List[str], source: str, target: str
    ) -> None:
        """Show what will be copied."""
        console.print(f"[cyan]Copy plan from {source} to {target}:[/cyan]")

        if networks:
            console.print(f"  [yellow]Networks ({len(networks)}):[/yellow]")
            for network in networks:
                console.print(f"    • {network}")

        if volumes:
            console.print(f"  [yellow]Volumes ({len(volumes)}):[/yellow]")
            for volume in volumes:
                console.print(f"    • {volume}")

        console.print()

    def _copy_network(
        self, network_name: str, source_stack: str, target_stack: str
    ) -> bool:
        """Copy a network from source to target stack."""
        try:
            # Get network details
            verbose_print(f"[cyan]exec: podman network inspect {network_name}[/cyan]")
            inspect_result = podman_cmd(
                ["network", "inspect", network_name], timeout=10
            )

            if inspect_result.returncode != 0:
                console.print(
                    f"[yellow]Network {network_name} not found in runtime, will create basic network[/yellow]"
                )
                network_config = None
            else:
                try:
                    network_config = (
                        json.loads(inspect_result.stdout)[0]
                        if inspect_result.stdout.strip()
                        else None
                    )
                except (json.JSONDecodeError, IndexError):
                    network_config = None

            # Generate target network name
            target_network_name = network_name.replace(
                source_stack.replace("-stack", ""), target_stack.replace("-stack", "")
            )

            # Check if target network already exists
            verbose_print(
                f"[cyan]exec: podman network exists {target_network_name}[/cyan]"
            )
            check_result = podman_cmd(
                ["network", "exists", target_network_name], timeout=5
            )

            if check_result.returncode == 0:
                console.print(
                    f"[yellow]Network {target_network_name} already exists, skipping[/yellow]"
                )
                return True

            # Create new network with similar configuration if available
            verbose_print(
                f"[cyan]exec: podman network create {target_network_name}[/cyan]"
            )

            # Build command with configuration options
            create_cmd = ["network", "create"]

            # Add subnet if available
            if (
                network_config
                and "subnets" in network_config
                and network_config["subnets"]
                and network_config["subnets"][0].get("subnet")
            ):
                subnet = network_config["subnets"][0]["subnet"]
                create_cmd.extend(["--subnet", subnet])

            # Add driver if available and not default
            if (
                network_config
                and "options" in network_config
                and network_config["options"].get("driver")
                and network_config["options"]["driver"] != "bridge"
            ):
                driver = network_config["options"]["driver"]
                create_cmd.extend(["--driver", driver])

            create_cmd.append(target_network_name)

            create_result = podman_cmd(create_cmd, timeout=10)

            if create_result.returncode == 0:
                console.print(f"[green]Created network: {target_network_name}[/green]")
                return True
            else:
                console.print(
                    f"[red]Failed to create network {target_network_name}: {create_result.stderr}[/red]"
                )
                return False

        except Exception as e:
            console.print(f"[red]Error copying network {network_name}: {e}[/red]")
            return False

    def _copy_volume(
        self, volume_name: str, source_stack: str, target_stack: str
    ) -> bool:
        """Copy a volume from source to target stack."""
        try:
            # Generate target volume name
            target_volume_name = volume_name.replace(
                source_stack.replace("-stack", ""), target_stack.replace("-stack", "")
            )

            # Check if target volume already exists
            verbose_print(
                f"[cyan]exec: podman volume exists {target_volume_name}[/cyan]"
            )
            check_result = podman_cmd(
                ["volume", "exists", target_volume_name], timeout=5
            )

            if check_result.returncode == 0:
                console.print(
                    f"[yellow]Volume {target_volume_name} already exists, skipping[/yellow]"
                )
                return True

            # Create new volume
            verbose_print(
                f"[cyan]exec: podman volume create {target_volume_name}[/cyan]"
            )
            create_result = podman_cmd(
                ["volume", "create", target_volume_name], timeout=10
            )

            if create_result.returncode != 0:
                console.print(
                    f"[red]Failed to create volume {target_volume_name}: {create_result.stderr}[/red]"
                )
                return False

            # Copy volume data using a temporary container
            copy_success = self._copy_volume_data(volume_name, target_volume_name)

            if copy_success:
                console.print(
                    f"[green]Copied volume: {volume_name} → {target_volume_name}[/green]"
                )
                return True
            else:
                # Clean up failed volume
                podman_cmd(["volume", "rm", target_volume_name])
                return False

        except Exception as e:
            console.print(f"[red]Error copying volume {volume_name}: {e}[/red]")
            return False

    def _copy_volume_data(self, source_volume: str, target_volume: str) -> bool:
        """Copy data from source volume to target volume using temporary containers."""
        temp_container_name = f"volume-copy-{source_volume}-to-{target_volume}"

        try:
            # Use a lightweight container to copy data
            verbose_print(
                f"[cyan]exec: podman run --rm -v {source_volume}:/source:ro -v {target_volume}:/target --name {temp_container_name} alpine:latest sh -c 'cp -a /source/. /target/'[/cyan]"
            )

            with Progress(
                SpinnerColumn(),
                TextColumn(
                    f"[yellow]Copying data from {source_volume} to {target_volume}...[/yellow]"
                ),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("copying", total=None)
                copy_result = secure_run(
                    [
                        "podman",
                        "run",
                        "--rm",
                        "-v",
                        f"{source_volume}:/source:ro",
                        "-v",
                        f"{target_volume}:/target",
                        "--name",
                        temp_container_name,
                        "alpine:latest",
                        "sh",
                        "-c",
                        "cp -a /source/. /target/",
                    ],
                    timeout=300,
                )
                progress.remove_task(task)

            if copy_result.returncode == 0:
                return True
            else:
                console.print(
                    f"[red]Failed to copy volume data: {copy_result.stderr}[/red]"
                )
                return False

        except subprocess.TimeoutExpired:
            console.print(f"[red]Volume copy timed out for {source_volume}[/red]")
            # Try to clean up the container
            podman_cmd(["rm", "-f", temp_container_name])
            return False
        except Exception as e:
            console.print(f"[red]Error copying volume data: {e}[/red]")
            return False

    def list_stack_volumes_and_networks(self, stack_name: str) -> None:
        """List all volumes and networks for a stack."""
        console.print(f"[cyan]Volumes and Networks for {stack_name}:[/cyan]")
        console.print()

        volumes = self._get_stack_volumes(stack_name)
        networks = self._get_stack_networks(stack_name)

        if networks:
            console.print(f"[yellow]Networks ({len(networks)}):[/yellow]")
            for network in networks:
                console.print(f"  • {network}")
            console.print()

        if volumes:
            console.print(f"[yellow]Volumes ({len(volumes)}):[/yellow]")
            for volume in volumes:
                # Get volume size info
                size_info = self._get_volume_size(volume)
                console.print(f"  • {volume} {size_info}")
            console.print()

        if not volumes and not networks:
            console.print("[dim]No volumes or networks found[/dim]")
            console.print()

    def _get_volume_size(self, volume_name: str) -> str:
        """Get volume size information."""
        try:
            # Get volume mount point
            result = podman_cmd(
                [
                    "volume",
                    "inspect",
                    volume_name,
                    "--format",
                    "{{.Mountpoint}}",
                ],
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                mount_point = result.stdout.strip()

                # Get size using du
                du_result = secure_run(["du", "-sh", mount_point], timeout=5)

                if du_result.returncode == 0:
                    size = du_result.stdout.split()[0]
                    return f"[dim]({size})[/dim]"

        except Exception:
            pass

        return "[dim](size unknown)[/dim]"

    def cleanup_orphaned_volumes(self, stack_name: str) -> bool:
        """Clean up volumes that are no longer used by any containers in the stack."""
        console.print(
            f"[green]Cleaning up orphaned volumes for {stack_name}...[/green]"
        )

        try:
            # Get all volumes for the stack
            volumes = self._get_stack_volumes(stack_name)

            if not volumes:
                console.print("[yellow]No volumes found to clean up[/yellow]")
                return True

            # Check which volumes are in use
            orphaned_volumes = []

            for volume in volumes:
                if not self._is_volume_in_use(volume):
                    orphaned_volumes.append(volume)

            if not orphaned_volumes:
                console.print("[green]No orphaned volumes found[/green]")
                return True

            # Remove orphaned volumes
            console.print(
                f"[yellow]Found {len(orphaned_volumes)} orphaned volumes:[/yellow]"
            )
            for volume in orphaned_volumes:
                console.print(f"  • {volume}")

            # Remove them
            for volume in orphaned_volumes:
                verbose_print(f"[cyan]exec: podman volume rm {volume}[/cyan]")
                result = podman_cmd(["volume", "rm", volume])

                if result.returncode == 0:
                    console.print(f"[green]Removed orphaned volume: {volume}[/green]")
                else:
                    console.print(
                        f"[red]Failed to remove volume {volume}: {result.stderr}[/red]"
                    )

            return True

        except Exception as e:
            console.print(f"[red]Error cleaning up orphaned volumes: {e}[/red]")
            return False

    def _is_volume_in_use(self, volume_name: str) -> bool:
        """Check if a volume is currently in use by any container."""
        try:
            # Check if any containers are using this volume
            result = podman_cmd(
                ["ps", "-a", "--format", "{{.Names}} {{.Mounts}}"], timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if volume_name in line:
                        return True

            return False

        except Exception:
            # If we can't determine, assume it's in use to be safe
            return True
