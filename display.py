"""Rich UI display components."""

import subprocess
from typing import Optional

from rich.table import Table
from rich.tree import Tree

from config import console


class DisplayManager:
    """Rich UI display components"""

    def __init__(self, manager):
        self.manager = manager

    def show_status(self, target=None, verbose=False):
        """Show status of all projects and services with running status"""

        # Show spinner while retrieving status
        with console.status("[green]Retrieving status...[/green]", spinner="dots"):
            projects = self.manager._parse_compose_files()
            # Get all container statuses at once
            all_container_statuses = self._get_all_container_statuses()
            import time

            time.sleep(0.5)  # Brief pause to show spinner

        if not projects:
            console.print("[red]No compose files found![/red]")
            return

        # Filter by target if specified
        if target:
            # Check if target is a project name
            if target in projects:
                projects = {target: projects[target]}
            else:
                # Check if target is a service name in any project
                filtered_projects = {}
                for project_name, project_info in projects.items():
                    if target in project_info["services"]:
                        filtered_projects[project_name] = project_info
                projects = filtered_projects

            if not projects:
                console.print(
                    f"[red]No project or service found matching '{target}'[/red]"
                )
                return

        tree = Tree("Stacks & Services", style="cyan")

        # Sort projects alphabetically
        for project_name in sorted(projects.keys()):
            project_info = projects[project_name]
            # Make project names green
            project_node = tree.add(f"[cyan]{project_name}[/cyan]")

            if project_info["services"]:
                # Sort services alphabetically
                for service_name in sorted(project_info["services"].keys()):
                    service_config = project_info["services"][service_name]
                    profiles = service_config.get("profiles", [])
                    profile_str = (
                        f" [dim]({', '.join(profiles)})[/dim]" if profiles else ""
                    )

                    # Get service running status from cached data
                    status_info = self._get_service_status_from_cache(
                        service_name, all_container_statuses
                    )

                    # Format service with status (30 character field for alignment)
                    # Calculate visual length without color codes for profile_str
                    import re

                    profile_visual_length = len(re.sub(r"\[.*?\]", "", profile_str))
                    service_with_profile_length = (
                        len(service_name) + profile_visual_length
                    )

                    # Ensure all service names are exactly 30 characters for alignment
                    if service_with_profile_length > 30:
                        # Truncate service name to fit within 30 characters including profile
                        available_for_name = 30 - profile_visual_length
                        truncated_name = service_name[:available_for_name]
                        service_display = (
                            f"[yellow]{truncated_name}[/yellow]{profile_str}"
                            + (" " * (30 - len(truncated_name) - profile_visual_length))
                        )
                    else:
                        # Pad to exactly 30 characters with spaces
                        service_display = (
                            f"[yellow]{service_name}[/yellow]{profile_str}"
                            + (" " * (30 - service_with_profile_length))
                        )

                    service_with_status = f"{service_display} {status_info}"

                    # Add verbose information if requested
                    if verbose:
                        verbose_info = self._get_verbose_service_info(
                            service_name, all_container_statuses
                        )
                        if verbose_info:
                            service_with_status += f" {verbose_info}"

                    project_node.add(service_with_status)
            else:
                project_node.add("[dim](no services found)[/dim]")

        console.print(tree)

    def show_available_targets(self, command_name: str = "command"):
        """Show available projects and services when no target is specified"""
        projects = self.manager._parse_compose_files()

        if not projects:
            console.print(
                f"[red]No compose files found in {self.manager.compose_dir}[/red]"
            )
            return False

        console.print(
            f"[yellow]No target specified for '{command_name}' command.[/yellow]"
        )
        console.print("\n[bold cyan]Available targets:[/bold cyan]")

        # Create a tree showing projects and their services
        tree = Tree("Projects & Services", style="cyan")

        # Sort projects alphabetically
        for project_name in sorted(projects.keys()):
            project_info = projects[project_name]
            # Make project names cyan
            project_node = tree.add(f"[cyan]{project_name}[/cyan]")

            if project_info["services"]:
                # Sort services alphabetically
                for service_name in sorted(project_info["services"].keys()):
                    service_config = project_info["services"][service_name]
                    profiles = service_config.get("profiles", [])
                    profile_str = (
                        f" [dim]({', '.join(profiles)})[/dim]" if profiles else ""
                    )
                    # Make service names yellow
                    project_node.add(f"[yellow]{service_name}{profile_str}[/yellow]")
            else:
                project_node.add("[dim](no services found)[/dim]")

        console.print(tree)

        console.print("\n[bold]Usage examples:[/bold]")
        console.print(f"  pm {command_name} <project_name> # Operate on entire project")
        console.print(
            f"  pm {command_name} <service_name> # Operate on specific service"
        )
        console.print(
            "\n[dim]Use 'pm list' to see the full project/service tree.[/dim]"
        )
        return True

    def show_ps(self):
        """Show container status in a rich table"""
        # Container status table

        # Get container information
        cmd = [
            "podman",
            "ps",
            "-a",
            "--format",
            "{{.Names}};{{.Image}};{{.Status}};{{.Ports}}",
        ]
        console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Error getting container status: {error_msg}[/red]")
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Image", style="dim", max_width=40)
        table.add_column("Status", no_wrap=True)
        table.add_column("Ports", style="blue", max_width=30)

        # Parse and collect container data
        containers = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue

            parts = line.split(";")
            if len(parts) >= 4:
                name, image, status, ports = parts[:4]

                # Color code status
                if "Up" in status or "running" in status.lower():
                    colored_status = f"[green]{status}[/green]"
                elif "Exited" in status:
                    colored_status = f"[red]{status}[/red]"
                else:
                    colored_status = f"[yellow]{status}[/yellow]"

                containers.append((name, image, colored_status, ports))

        # Sort containers alphabetically by name
        containers.sort(key=lambda x: x[0].lower())

        # Add sorted rows to table
        for name, image, status, ports in containers:
            table.add_row(name, image, status, ports)

        console.print(table)

    def show_images(self, show_all: bool = False):
        """Show container images in a formatted table"""
        # Container images table

        cmd = ["podman", "images"]
        if show_all:
            cmd.append("-a")

        console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Error listing images: {error_msg}[/red]")
            return False

        if not result.stdout.strip():
            console.print("[yellow]No images found[/yellow]")
            return True

        # Parse the output and create a rich table
        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:  # Header + at least one image
            console.print("[yellow]No images found[/yellow]")
            return True

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Repository", style="cyan")
        table.add_column("Tag", style="green")
        table.add_column("Image ID", style="yellow", no_wrap=True)
        table.add_column("Created", style="blue")
        table.add_column("Size", style="magenta")

        # Skip header line
        for line in lines[1:]:
            if line.strip():
                parts = line.split()
                if len(parts) >= 5:
                    repo = parts[0]
                    tag = parts[1]
                    image_id = parts[2][:12] + "..."  # Truncate ID
                    created = " ".join(parts[3:-1])  # Everything except size
                    size = parts[-1]
                    table.add_row(repo, tag, image_id, created, size)

        console.print(table)
        return True

    def show_stats(self, follow: bool = False):
        """Show resource usage statistics"""
        cmd = ["podman", "stats", "--no-stream"]
        if follow:
            cmd.remove("--no-stream")

        # Container resource usage
        console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

        if follow:
            console.print("[dim]Press Ctrl+C to stop following stats[/dim]")
            try:
                subprocess.run(cmd)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stats monitoring stopped[/yellow]")
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(result.stdout)
            else:
                error_msg = (
                    result.stderr.strip() if result.stderr.strip() else "Unknown error"
                )
                console.print(f"[red]Error getting stats: {error_msg}[/red]")
                return False
        return True

    def show_volumes(self):
        """List volumes with disk usage"""
        # Podman volumes

        cmd = ["podman", "volume", "ls", "--format", "table"]
        console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print(result.stdout)
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Error listing volumes: {error_msg}[/red]")
            return False
        return True

    def show_networks(self):
        """List networks"""
        # Podman networks

        cmd = ["podman", "network", "ls"]
        console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            console.print(result.stdout)
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Error listing networks: {error_msg}[/red]")
            return False
        return True

    def show_system_df(self):
        """Show system disk usage"""
        # Podman system disk usage

        df_cmd = ["podman", "system", "df"]
        console.print(f"  [cyan]exec: {' '.join(df_cmd)}[/cyan]")

        result = subprocess.run(df_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(result.stdout)
            return True
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Failed to get system disk usage: {error_msg}[/red]")
            return False

    def show_events(self, since: Optional[str] = None):
        """Stream real-time podman events"""
        # Podman events stream

        events_cmd = ["podman", "events"]
        if since:
            events_cmd.extend(["--since", since])

        console.print(f"  [cyan]exec: {' '.join(events_cmd)}[/cyan]")
        console.print("[dim]Press Ctrl+C to stop streaming events[/dim]")

        try:
            result = subprocess.run(events_cmd, text=True)
            return result.returncode == 0
        except KeyboardInterrupt:
            console.print("\n[yellow]Event streaming stopped[/yellow]")
            return True
        except Exception as e:
            console.print(f"[red]Error streaming events: {e}[/red]")
            return False

    def clear_cache(self) -> None:
        """Clear display cache - only available in quadlet mode"""
        console.print("[red]Clear cache only available in quadlet mode[/red]")

    def _get_service_running_status(self, service_name: str) -> str:
        """Get the running status of a compose service using only podman ps -a"""
        try:
            import subprocess

            # Check if container exists and get its status
            cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                f"name=^{service_name}$",
                "--format",
                "{{.Status}}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0 and result.stdout.strip():
                status = result.stdout.strip()
                status_lower = status.lower()

                if "unhealthy" in status_lower or "starting" in status_lower:
                    return f"[yellow]{status}[/yellow]"
                elif "up" in status_lower or "running" in status_lower:
                    # If status only has 'Up n <time period>' without health status, add (running)
                    if "up" in status_lower and "(" not in status:
                        return f"[green]{status} (running)[/green]"
                    else:
                        return f"[green]{status}[/green]"
                elif "exited" in status_lower:
                    # Check exit code
                    if "exited (0)" in status_lower:
                        return f"[orange1]{status}[/orange1]"
                    else:
                        return f"[red]{status}[/red]"
                elif "created" in status_lower:
                    return f"[dim]{status}[/dim]"
                elif "restarting" in status_lower:
                    return f"[yellow]{status}[/yellow]"
                else:
                    return f"[dim]{status}[/dim]"

            # Try partial name match if exact match fails
            cmd_partial = [
                "podman",
                "ps",
                "-a",
                "--filter",
                f"name={service_name}",
                "--format",
                "{{.Names}} {{.Status}}",
            ]

            result = subprocess.run(
                cmd_partial, capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if service_name in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            status = " ".join(parts[1:])
                            status_lower = status.lower()
                            if "up" in status_lower or "running" in status_lower:
                                return f"[green]{status}[/green]"
                            elif "exited" in status_lower:
                                if "exited (0)" in status_lower:
                                    return f"[orange1]{status}[/orange1]"
                                else:
                                    return f"[red]{status}[/red]"
                            elif "created" in status_lower:
                                return f"[dim]{status}[/dim]"
                            elif "restarting" in status_lower:
                                return f"[yellow]{status}[/yellow]"
                            else:
                                return f"[dim]{status}[/dim]"

            # Check for common service variations
            variations = [
                service_name.replace("-", "_"),
                service_name.replace("_", "-"),
                f"local-ai-{service_name}",
                f"supabase-{service_name}",
                service_name.replace("local-ai-", ""),
                service_name.replace("supabase-", ""),
            ]

            for variation in variations:
                cmd_var = [
                    "podman",
                    "ps",
                    "-a",
                    "--filter",
                    f"name={variation}",
                    "--format",
                    "{{.Names}} {{.Status}}",
                ]

                result = subprocess.run(
                    cmd_var, capture_output=True, text=True, timeout=5
                )

                if result.returncode == 0 and result.stdout.strip():
                    lines = result.stdout.strip().split("\n")
                    for line in lines:
                        if variation in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                status = " ".join(parts[1:])
                                status_lower = status.lower()
                                if "up" in status_lower or "running" in status_lower:
                                    return f"[green]{status}[/green]"
                                elif "exited" in status_lower:
                                    if "exited (0)" in status_lower:
                                        return f"[orange1]{status}[/orange1]"
                                    else:
                                        return f"[red]{status}[/red]"
                                elif "created" in status_lower:
                                    return f"[dim]{status}[/dim]"
                                elif "restarting" in status_lower:
                                    return f"[yellow]{status}[/yellow]"
                                else:
                                    return f"[dim]{status}[/dim]"

            # If not found in containers, return not found
            return "[white]not found[/white]"

        except Exception:
            return "[red]error[/red]"

    def _get_all_container_statuses(self):
        """Get all container statuses at once using a single podman ps command"""
        try:
            cmd = ["podman", "ps", "-a", "--format", "{{.Names}};{{.Status}}"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and result.stdout.strip():
                container_statuses = {}
                for line in result.stdout.strip().split("\n"):
                    if ";" in line:
                        name, status = line.split(";", 1)
                        container_statuses[name.strip()] = status.strip()
                return container_statuses

            return {}

        except Exception:
            return {}

    def _get_service_status_from_cache(self, service_name, all_container_statuses):
        """Get service status from cached container statuses"""
        try:
            # Check exact match first
            if service_name in all_container_statuses:
                return self._format_status(all_container_statuses[service_name])

            # Check for partial matches
            for container_name, status in all_container_statuses.items():
                if service_name in container_name:
                    return self._format_status(status)

            # Check for common service variations
            variations = [
                service_name.replace("-", "_"),
                service_name.replace("_", "-"),
                f"local-ai-{service_name}",
                f"supabase-{service_name}",
                service_name.replace("local-ai-", ""),
                service_name.replace("supabase-", ""),
            ]

            for variation in variations:
                if variation in all_container_statuses:
                    return self._format_status(all_container_statuses[variation])

                # Check partial matches for variations
                for container_name, status in all_container_statuses.items():
                    if variation in container_name:
                        return self._format_status(status)

            return "[white]not found[/white]"

        except Exception:
            return "[red]error[/red]"

    def _format_status(self, status):
        """Format container status with appropriate colors"""
        status_lower = status.lower()

        if "unhealthy" in status_lower or "starting" in status_lower:
            return f"[yellow]{status}[/yellow]"
        elif "up" in status_lower or "running" in status_lower:
            # If status only has 'Up n <time period>' without health status, add (running)
            if "up" in status_lower and "(" not in status:
                return f"[green]{status} (running)[/green]"
            else:
                return f"[green]{status}[/green]"
        elif "exited" in status_lower:
            # Check exit code
            if "exited (0)" in status_lower:
                return f"[orange1]{status}[/orange1]"
            else:
                return f"[red]{status}[/red]"
        elif "created" in status_lower:
            return f"[dim]{status}[/dim]"
        elif "restarting" in status_lower:
            return f"[yellow]{status}[/yellow]"
        else:
            return f"[dim]{status}[/dim]"

    def _get_verbose_service_info(self, service_name, all_container_statuses):
        """Get additional verbose information about a service"""
        try:
            # Find the container for this service
            container_name = None

            # Check exact match first
            if service_name in all_container_statuses:
                container_name = service_name
            else:
                # Check for partial matches and variations
                variations = [
                    service_name.replace("-", "_"),
                    service_name.replace("_", "-"),
                    f"local-ai-{service_name}",
                    f"supabase-{service_name}",
                    service_name.replace("local-ai-", ""),
                    service_name.replace("supabase-", ""),
                ]

                for variation in variations:
                    if variation in all_container_statuses:
                        container_name = variation
                        break

                # Check partial matches
                if not container_name:
                    for name, status in all_container_statuses.items():
                        if service_name in name:
                            container_name = name
                            break

            if not container_name:
                return "[dim](container not found)[/dim]"

            # Get additional container information
            verbose_parts = []

            # Add container name if different from service name
            if container_name != service_name:
                verbose_parts.append(f"[dim]container: {container_name}[/dim]")

            # Get container ID and image info
            try:
                cmd = [
                    "podman",
                    "ps",
                    "-a",
                    "--filter",
                    f"name=^{container_name}$",
                    "--format",
                    "{{.ID}} {{.Image}}",
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

                if result.returncode == 0 and result.stdout.strip():
                    parts = result.stdout.strip().split()
                    if len(parts) >= 2:
                        container_id = parts[0][:12]  # Short ID
                        image = parts[1]

                        verbose_parts.append(f"[dim]id: {container_id}[/dim]")

                        # Shorten image name for display
                        if len(image) > 40:
                            image = "..." + image[-37:]
                        verbose_parts.append(f"[dim]image: {image}[/dim]")

            except Exception:
                pass

            return " ".join(verbose_parts) if verbose_parts else ""

        except Exception:
            return "[dim](verbose info unavailable)[/dim]"
