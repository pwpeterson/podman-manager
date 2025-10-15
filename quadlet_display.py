"""Rich UI display components for quadlet services."""

import subprocess
from typing import Optional

from rich.table import Table
from rich.tree import Tree

from config import console


class QuadletDisplayManager:
    """Rich UI display components for quadlet services"""

    def __init__(self, manager):
        self.manager = manager

    def show_status(self, target=None):
        """Show projects and services in alphabetical tree format"""
        # Get all available projects and services
        all_items = self._get_all_projects_and_services()

        if not all_items:
            console.print("[red]No projects or services found![/red]")
            return

        # Filter by target if specified
        if target:
            # Use the quadlet manager's service resolution logic
            resolved_target = self.manager._find_service_name(
                target, allow_interactive=False
            )

            if resolved_target and resolved_target.startswith("STACK:"):
                # It's a stack - extract the stack name
                stack_name = resolved_target[6:]  # Remove "STACK:" prefix
                if stack_name in all_items:
                    filtered_items = {stack_name: all_items[stack_name]}
                else:
                    console.print(
                        f"[red]No project or service found matching '{target}'[/red]"
                    )
                    return
            else:
                # Original logic for direct matches
                filtered_items = {}
                for project_name, project_info in all_items.items():
                    if target == project_name:
                        # Show entire project
                        filtered_items[project_name] = project_info
                    elif target in project_info.get("services", {}):
                        # Show specific service within project
                        filtered_items[project_name] = {
                            "type": project_info["type"],
                            "services": {target: project_info["services"][target]},
                        }

                if not filtered_items:
                    console.print(
                        f"[red]No project or service found matching '{target}'[/red]"
                    )
                    return

            all_items = filtered_items

        tree = Tree("Projects & Services", style="cyan")

        # Sort projects alphabetically
        for project_name in sorted(all_items.keys()):
            project_info = all_items[project_name]

            # Use display_name if available, otherwise use project_name
            display_name = project_info.get("display_name", project_name)

            # For mixed projects, just show the project name without type suffix
            project_node = tree.add(f"[cyan]{display_name}[/cyan]")

            services = project_info.get("services", {})
            if services:
                # Sort services alphabetically
                for service_name in sorted(services.keys()):
                    project_node.add(f"[yellow]{service_name}[/yellow]")
            else:
                project_node.add("[dim](no services found)[/dim]")

        console.print(tree)

    def _get_all_projects_and_services(self):
        """Get all projects and services from both quadlets and compose"""
        all_items = {}

        # Get compose projects first
        compose_projects = self._get_compose_projects()

        # Add compose projects to all_items (excluding those that have quadlet equivalents)
        compose_stack_names = set()
        for project_name, project_info in compose_projects.items():
            # Convert compose project names to potential stack names for comparison
            potential_stack_name = f"{project_name}-stack"
            if potential_stack_name not in self.manager.stack_services:
                all_items[project_name] = {"type": "mixed", "services": {}}
                # Add compose services with (compose) suffix
                for service_name, service_info in project_info["services"].items():
                    display_name = f"{service_name} [dim white](compose)[/dim white]"
                    all_items[project_name]["services"][display_name] = service_info
            else:
                compose_stack_names.add(project_name)

        # Process all discovered quadlet stacks
        for stack_name, stack_service_list in self.manager.stack_services.items():
            if stack_name not in all_items:
                all_items[stack_name] = {"type": "mixed", "services": {}}

            # Add all quadlet services in this stack
            for short_name in stack_service_list:
                if short_name in self.manager.quadlet_services:
                    full_name = self.manager.quadlet_services[short_name]

                    # Get installation status for color coding
                    status = self.manager.service_status.get(
                        short_name, {"installed": False, "source": False}
                    )

                    if status["installed"] and status["source"]:
                        # Green: installed and available in source
                        color = "green"
                    elif status["installed"] and not status["source"]:
                        # Yellow: installed but only in systemd
                        color = "yellow"
                    elif not status["installed"] and status["source"]:
                        # Red: available in source but not installed
                        color = "red"
                    else:
                        # Default: unknown status
                        color = "yellow"

                    display_name = f"[{color}]{full_name}[/{color}] [dim white](quadlet)[/dim white]"
                    all_items[stack_name]["services"][display_name] = {
                        "full_name": full_name
                    }

            # Add compose services if they exist for this stack
            compose_project_name = stack_name.replace("-stack", "")
            if compose_project_name in compose_projects:
                for service_name, service_info in compose_projects[
                    compose_project_name
                ]["services"].items():
                    compose_display_name = (
                        f"{service_name} [dim white](compose)[/dim white]"
                    )
                    all_items[stack_name]["services"][
                        compose_display_name
                    ] = service_info

        # Add the vllm-stack.target if it exists and vllm-stack is present
        if "vllm-stack" in all_items and hasattr(self.manager, "stack_target"):
            stack_display_name = (
                f"{self.manager.stack_target} [dim white](quadlet)[/dim white]"
            )
            all_items["vllm-stack"]["services"][stack_display_name] = {
                "full_name": self.manager.stack_target
            }

        return all_items

    def _get_compose_projects(self):
        """Get compose projects from actual compose files or fallback to containers"""
        try:
            # Import here to avoid circular imports
            import os
            from pathlib import Path

            from manager import PodmanManager

            # Try to find compose directory
            compose_dir = os.environ.get("PODMAN_COMPOSE_DIR")
            if not compose_dir:
                # Try common locations
                possible_dirs = [
                    Path.home() / "srv" / "local-ai-packaged",
                    Path("/home/pwp/srv/local-ai-packaged"),
                    Path(".") / "compose",
                ]
                for dir_path in possible_dirs:
                    if dir_path.exists() and any(dir_path.glob("*compose*.yml")):
                        compose_dir = str(dir_path)
                        break

            if compose_dir and Path(compose_dir).exists():
                compose_manager = PodmanManager(compose_dir)
                projects = compose_manager._parse_compose_files()
                if projects:
                    return projects

            # Fallback to container-based detection
            return self._get_projects_from_containers()

        except Exception as e:
            console.print(
                f"[dim]Error getting compose projects, using container fallback: {e}[/dim]"
            )
            return self._get_projects_from_containers()

    def _get_projects_from_containers(self):
        """Fallback: Get projects by parsing container names and labels"""
        compose_containers = self._get_compose_containers()
        compose_projects = {}

        for container in compose_containers:
            # Try to extract project name from container name
            # Most compose containers are named like: project-service or project_service
            name = container["name"]

            # Common patterns for compose project extraction
            if "-" in name:
                parts = name.split("-")
                if len(parts) >= 2:
                    project = parts[0]
                    service = "-".join(parts[1:])
                else:
                    project = "containers"
                    service = name
            elif "_" in name:
                parts = name.split("_")
                if len(parts) >= 2:
                    project = parts[0]
                    service = "_".join(parts[1:])
                else:
                    project = "containers"
                    service = name
            else:
                project = "containers"
                service = name

            if project not in compose_projects:
                compose_projects[project] = {"services": {}}

            compose_projects[project]["services"][service] = {
                "image": container["image"],
                "status": container["status"],
                "ports": container["ports"],
            }

        return compose_projects

    def _get_compose_containers(self):
        """Get list of running compose containers"""
        try:
            cmd = [
                "podman",
                "ps",
                "-a",
                "--format",
                "{{.Names}};{{.Image}};{{.Status}};{{.Ports}}",
                "--filter",
                "label=com.docker.compose.project",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            containers = []
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        parts = line.split(";")
                        if len(parts) >= 4:
                            name, image, status, ports = parts[:4]
                            containers.append(
                                {
                                    "name": name,
                                    "image": image,
                                    "status": status,
                                    "ports": ports,
                                }
                            )

            return containers
        except Exception as e:
            console.print(f"[dim]Error getting compose containers: {e}[/dim]")
            return []

    def _show_stack_status(self, stack_status):
        """Show detailed stack status"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        active_state = stack_status.get("ActiveState", "unknown")
        if active_state == "active":
            colored_active = f"[green]{active_state}[/green]"
        elif active_state == "inactive":
            colored_active = f"[yellow]{active_state}[/yellow]"
        else:
            colored_active = f"[red]{active_state}[/red]"

        table.add_row("Service", "vllm-stack.target")
        table.add_row("Active State", colored_active)
        table.add_row("Sub State", stack_status.get("SubState", "unknown"))
        table.add_row("Load State", stack_status.get("LoadState", "unknown"))
        table.add_row("Unit File State", stack_status.get("UnitFileState", "unknown"))

        console.print(table)

    def show_available_targets(self, command_name: str = "command"):
        """Show available services when no target is specified"""
        console.print(
            f"[yellow]No target specified for '{command_name}' command.[/yellow]"
        )
        console.print("\n[bold cyan]Available targets:[/bold cyan]")

        tree = Tree("vLLM Services", style="cyan")

        # Add stack target
        stack_node = tree.add(f"[cyan]stack[/cyan] ({self.manager.stack_target})")
        stack_node.add("[dim]Manages all vLLM services together[/dim]")

        # Add individual services
        services_node = tree.add("[cyan]Individual Services[/cyan]")
        for short_name, full_name in sorted(self.manager.quadlet_services.items()):
            service_node = services_node.add(
                f"[yellow]{short_name}[/yellow] ({full_name})"
            )
            service_node.add(f"[dim]Short alias for {full_name}[/dim]")

        console.print(tree)

        console.print("\n[bold]Usage examples:[/bold]")
        console.print(
            f"  pm {command_name} vllm-stack      # Operate on entire vLLM stack"
        )
        console.print(
            f"  pm {command_name} vllm-qwen25     # Operate on Qwen2.5 Coder service"
        )
        console.print(f"  pm {command_name} vllm-proxy      # Operate on proxy service")
        console.print(
            f"  pm {command_name} vllm-delegator  # Operate on delegator service"
        )
        console.print("\n[dim]Use 'pm list' to see the full service status tree.[/dim]")
        return True

    def show_ps(self):
        """Show container status in a rich table"""
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

    def show_service_details(self, target: str):
        """Show detailed information about a specific service"""
        service_name = self.manager._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return

        console.print(f"[bold cyan]Service Details: {service_name}[/bold cyan]")

        # Show systemctl status
        cmd = ["systemctl", "--user", "status", service_name, "--no-pager"]
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[yellow]{result.stderr}[/yellow]")
