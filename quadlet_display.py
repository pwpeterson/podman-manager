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

    def show_status(self, target=None, verbose=False):
        """Show projects and services in alphabetical tree format with running status"""

        # Show status while retrieving
        console.print("\n[green]Retrieving podman status...[/green]")
        # Get all available projects and services
        all_items = self._get_all_projects_and_services()
        # Get all container statuses at once
        all_container_statuses = self._get_all_container_statuses(verbose=verbose)

        if not all_items:
            console.print("[red]No projects or services found![/red]")
            return

        # Filter by target if specified
        if target:
            # For list command, only accept stack names
            # Check if target matches any stack directly
            if target in all_items:
                filtered_items = {target: all_items[target]}
            else:
                # Check if it's a stack alias or partial match
                stack_matches = []
                for stack_name in all_items.keys():
                    if (
                        target.lower() in stack_name.lower()
                        or stack_name.lower().startswith(target.lower())
                    ):
                        stack_matches.append(stack_name)

                if len(stack_matches) == 1:
                    # Single stack match found
                    filtered_items = {stack_matches[0]: all_items[stack_matches[0]]}
                elif len(stack_matches) > 1:
                    # Multiple stack matches - show selection
                    console.print()
                    console.print(f"[green]Multiple stacks match '{target}':[/green]")
                    console.print()
                    console.print("[green]Please specify the full stack name:[/green]")
                    for i, stack_name in enumerate(stack_matches, 1):
                        console.print(
                            f"  [dim]{i}.[/dim] [cyan]pm list {stack_name}[/cyan]"
                        )
                    return
                else:
                    # No stack found - show error with suggestions
                    console.print()
                    console.print(f"[red]No stack was found matching '{target}'[/red]")
                    console.print()
                    console.print("[green]Available stacks:[/green]")
                    console.print("  [cyan]pm list[/cyan] [dim](show all stacks)[/dim]")
                    for stack_name in sorted(all_items.keys()):
                        console.print(f"  [cyan]pm list {stack_name}[/cyan]")
                    return

            all_items = filtered_items

        console.print()
        tree = Tree("Stacks & Services", style="cyan")

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
                    # Get the clean service name (remove color formatting)
                    clean_service_name = self._extract_clean_service_name(service_name)

                    # Get service status from cached data
                    status_info = self._get_service_status_from_cache(
                        clean_service_name, all_container_statuses
                    )

                    # Format service with status (30 character field for alignment)
                    clean_service_display = self._extract_clean_service_name(
                        service_name
                    )
                    # Ensure all service names are exactly 30 characters for alignment
                    if len(clean_service_display) > 30:
                        # Truncate and pad to exactly 30 characters
                        # Find truncation point that doesn't break color codes
                        truncated_service = service_name
                        while (
                            len(self._extract_clean_service_name(truncated_service))
                            > 30
                        ):
                            truncated_service = truncated_service[:-1]
                        clean_truncated = self._extract_clean_service_name(
                            truncated_service
                        )
                        padding_needed = 30 - len(clean_truncated)
                        service_display = truncated_service + (" " * padding_needed)
                    else:
                        # Pad original formatted name to exactly 30 characters with spaces
                        padding_needed = 30 - len(clean_service_display)
                        service_display = service_name + (" " * padding_needed)

                    service_with_status = f"{service_display} {status_info}"

                    # Add verbose information if requested
                    if verbose:
                        verbose_info = self._get_verbose_service_info(
                            clean_service_name, all_container_statuses
                        )
                        if verbose_info:
                            service_with_status += f" {verbose_info}"

                    project_node.add(service_with_status)
            else:
                project_node.add("[dim](no services found)[/dim]")

        console.print(tree)
        console.print()

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
                # Add compose services
                for service_name, service_info in project_info["services"].items():
                    display_name = service_name
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

                    # Remove .service suffix from display name
                    clean_name = full_name.replace(".service", "").replace(
                        ".target", ""
                    )
                    display_name = f"[{color}]{clean_name}[/{color}]"
                    all_items[stack_name]["services"][display_name] = {
                        "full_name": full_name
                    }

            # Add compose services if they exist for this stack
            compose_project_name = stack_name.replace("-stack", "")
            if compose_project_name in compose_projects:
                for service_name, service_info in compose_projects[
                    compose_project_name
                ]["services"].items():
                    compose_display_name = service_name
                    all_items[stack_name]["services"][
                        compose_display_name
                    ] = service_info

        # Add the vllm-stack.target if it exists and vllm-stack is present
        if "vllm-stack" in all_items and hasattr(self.manager, "stack_target"):
            # Check if the stack target file actually exists
            stack_target_path = (
                self.manager.quadlets_dir / f"{self.manager.stack_target}"
            )
            if stack_target_path.exists():
                # Remove .target suffix from stack display name
                clean_stack_name = self.manager.stack_target.replace(".target", "")
                stack_display_name = f"{clean_stack_name}"
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
            # Remove .service suffix from display name
            clean_full_name = full_name.replace(".service", "").replace(".target", "")
            service_node = services_node.add(
                f"[yellow]{short_name}[/yellow] ({clean_full_name})"
            )
            service_node.add(f"[dim]Short alias for {clean_full_name}[/dim]")

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

    def clear_cache(self) -> None:
        """Clear display cache"""
        # Clear any cached data if we have any
        console.print("[green]Display cache cleared[/green]")

    def _extract_clean_service_name(self, service_name: str) -> str:
        """Extract clean service name by removing Rich color formatting"""
        import re

        # Remove rich color tags like [green], [/green], [yellow], etc.
        clean_name = re.sub(r"\[/?[^\]]*\]", "", service_name)
        return clean_name.strip()

    def _get_service_running_status(self, service_name: str) -> str:
        """Get the running status of a service using only podman ps -a"""
        try:
            # Only use podman ps -a command
            container_status = self._get_container_status(service_name)
            if container_status:
                return container_status

            # Check for common service variations
            variations = [
                service_name.replace("-", "_"),
                service_name.replace("_", "-"),
                f"local-ai-{service_name}",
                f"supabase-{service_name}",
                service_name.replace("local-ai-", ""),
                service_name.replace("supabase-", ""),
                f"{service_name}-1",  # Common compose suffix
                f"{service_name}_1",  # Alternative compose suffix
            ]

            for variation in variations:
                container_status = self._get_container_status(variation)
                if container_status:
                    return container_status

            # If not found in containers, return not found
            return "[white]not found[/white]"

        except Exception:
            return "[red]error[/red]"

    def _get_container_status(self, container_name: str) -> str | None:
        """Get container status using podman ps"""
        try:
            import subprocess

            # Check if container exists and get its status
            cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                f"name=^{container_name}$",
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
                f"name={container_name}",
                "--format",
                "{{.Names}} {{.Status}}",
            ]

            result = subprocess.run(
                cmd_partial, capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if container_name in line:
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

            return None

        except Exception:
            return None

    def _get_all_container_statuses(self, verbose=False):
        """Get all container statuses at once using a single podman ps command"""
        try:
            cmd = ["podman", "ps", "-a", "--format", "{{.Names}};{{.Status}}"]

            if verbose:
                console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

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
