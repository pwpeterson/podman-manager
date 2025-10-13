"""Rich UI display components."""

import subprocess
from typing import Optional

from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from config import console


class DisplayManager:
    """Rich UI display components"""

    def __init__(self, manager):
        self.manager = manager

    def show_status(self):
        """Show status of all projects and services"""
        projects = self.manager._parse_compose_files()

        if not projects:
            console.print("[red]No compose files found![/red]")
            return

        tree = Tree("Projects & Services", style="cyan")

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
                    # Make service names yellow
                    project_node.add(f"[yellow]{service_name}{profile_str}[/yellow]")
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
            "\n[dim]Use 'pm status' to see the full project/service tree.[/dim]"
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
        console.print(f"  [white]exec: {' '.join(cmd)}[/white]")
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
        console.print(f"  [white]exec: {' '.join(df_cmd)}[/white]")

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

        console.print(f"  [white]exec: {' '.join(events_cmd)}[/white]")
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
