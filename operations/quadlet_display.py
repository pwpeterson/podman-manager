"""Rich UI display components for quadlet services."""

import json
import subprocess  # nosec B404 - Only used for TimeoutExpired exception handling
from pathlib import Path
from typing import Optional

from rich.table import Table
from rich.tree import Tree

from core.config import console
from utils.secure_subprocess import podman_cmd, secure_run


class QuadletDisplayManager:
    """Rich UI display components for quadlet services"""

    def __init__(self, manager):
        self.manager = manager
        self._supabase_order_cache = None
        self._build_contexts_cache = None

    def show_status(self, target=None, verbose=False):
        """Show projects and services in table format with systemd and podman status columns"""

        # Show status while retrieving
        if verbose:
            console.print("\n[green]Retrieving podman status (verbose mode)...[/green]")
        else:
            console.print("\n[green]Retrieving podman status...[/green]")
        # Get all available projects and services
        all_items = self._get_all_projects_and_services(verbose=verbose)
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

        # Create table with three columns
        table = Table(
            show_header=True, header_style="bold cyan", box=None, padding=(0, 2)
        )
        table.add_column("Stacks & Services", style="cyan", no_wrap=False)
        table.add_column("systemd", style="white", no_wrap=False)
        table.add_column("podman ps", style="white", no_wrap=False)

        # Sort projects alphabetically
        for project_name in sorted(all_items.keys()):
            project_info = all_items[project_name]

            # Use display_name if available, otherwise use project_name
            display_name = project_info.get("display_name", project_name)

            # Add stack header row
            table.add_row(f"[bold cyan]{display_name}[/bold cyan]", "", "")

            services = project_info.get("services", {})
            if services:
                # Sort services - for supabase-stack, sort by startup order first, then alphabetically
                if project_name == "supabase-stack":

                    def sort_key(item):
                        service_name = item[0]
                        clean_name = self._extract_clean_service_name(service_name)
                        order = self._get_supabase_startup_order(clean_name)
                        # Sort by order number (0 means no order, put at end), then alphabetically
                        return (order if order > 0 else 999, clean_name)

                    sorted_services = sorted(services.items(), key=sort_key)
                else:
                    # For other stacks, sort alphabetically
                    sorted_services = sorted(services.items())

                for service_name, service_info in sorted_services:
                    # Get the clean service name (remove color formatting)
                    clean_service_name = self._extract_clean_service_name(service_name)

                    # Get service status from cached data (returns tuple: systemd, podman)
                    systemd_status, podman_status = self._get_service_status_columns(
                        clean_service_name, all_container_statuses
                    )

                    # Check if service has a Dockerfile and add buildable indicator
                    has_dockerfile = self._has_dockerfile(service_name)
                    buildable_indicator = " 🔨" if has_dockerfile else ""

                    # Get startup order for supabase services
                    startup_order_prefix = ""
                    if project_name == "supabase-stack":
                        order_num = self._get_supabase_startup_order(clean_service_name)
                        if order_num:
                            startup_order_prefix = f"[cyan]({order_num})[/cyan] "

                    # Color code service name based on systemd status
                    # Check if this is a STDIO service first
                    if "stdio" in systemd_status:
                        service_color = "green"  # STDIO services in green
                    elif "active" in systemd_status:
                        service_color = "green"
                    elif "failed" in systemd_status:
                        service_color = "red"
                    elif "inactive" in systemd_status or "starting" in systemd_status:
                        service_color = "yellow"
                    else:
                        service_color = "white"

                    # Format service name with startup order prefix, color, and buildable indicator
                    service_display = f"  {startup_order_prefix}[{service_color}]{clean_service_name}[/{service_color}]{buildable_indicator}"

                    table.add_row(service_display, systemd_status, podman_status)
            else:
                table.add_row("  [dim](no services found)[/dim]", "", "")

        console.print(table)
        console.print()

    def _get_all_projects_and_services(self, verbose=False):
        """Get all projects and services from quadlets only"""
        all_items = {}

        # Process all discovered quadlet stacks
        for stack_name, stack_service_list in self.manager.stack_services.items():
            if stack_name not in all_items:
                all_items[stack_name] = {"type": "quadlet", "services": {}}

            # Add all quadlet services in this stack
            for short_name in stack_service_list:
                if short_name in self.manager.quadlet_services:
                    full_name = self.manager.quadlet_services[short_name]

                    # Get installation status for color coding
                    status = self.manager.service_status.get(
                        short_name, {"installed": False, "source": False}
                    )

                    # Check if this is a STDIO service
                    is_stdio = status.get("stdio", False)

                    # In verbose mode, show all services (installed and source-only)
                    # In normal mode, only show installed services (but always show STDIO services)
                    if not verbose and not status["installed"] and not is_stdio:
                        if verbose:
                            console.print(
                                f"  [dim]Debug: Skipping {short_name} (not installed)[/dim]"
                            )
                        continue

                    if is_stdio:
                        # Cyan: STDIO service (not managed by systemd)
                        color = "cyan"
                    elif status["installed"] and status["source"]:
                        # Green: installed and available in source
                        color = "green"
                    elif status["installed"] and not status["source"]:
                        # Yellow: installed but only in systemd
                        color = "yellow"
                    else:
                        # Default: installed status
                        color = "green"

                    # Remove .service suffix from display name
                    clean_name = full_name.replace(".service", "").replace(
                        ".target", ""
                    )
                    display_name = f"[{color}]{clean_name}[/{color}]"
                    all_items[stack_name]["services"][display_name] = {
                        "full_name": full_name
                    }

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

    def _has_dockerfile(self, service_name: str) -> bool:
        """Check if a service has a corresponding Dockerfile.<service_name>"""
        try:
            # Get the clean service name (remove color formatting)
            clean_service_name = self._extract_clean_service_name(service_name)

            # Check if this is a STDIO service with a dockerfile_path
            if (
                hasattr(self.manager, "stdio_services")
                and clean_service_name in self.manager.stdio_services
            ):
                stdio_config = self.manager.stdio_services[clean_service_name]
                dockerfile_path = stdio_config.get("dockerfile_path")
                if dockerfile_path:
                    return Path(dockerfile_path).exists()

            # Check build_contexts.json for services with build configurations
            if self._build_contexts_cache is None:
                self._load_build_contexts()

            if self._build_contexts_cache:
                build_contexts = self._build_contexts_cache.get("build_contexts", {})
                if clean_service_name in build_contexts:
                    config = build_contexts[clean_service_name]
                    dockerfile = config.get("dockerfile")
                    build_dir = config.get("build_dir")
                    if dockerfile and build_dir:
                        dockerfile_path = Path(build_dir) / dockerfile
                        if dockerfile_path.exists():
                            return True

            # Check in the quadlets source directory structure
            quadlets_source_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")

            if not quadlets_source_dir.exists():
                return False

            # Look through all stack directories for the Dockerfile
            for stack_dir in quadlets_source_dir.iterdir():
                if not stack_dir.is_dir() or not stack_dir.name.endswith("-stack"):
                    continue

                # Try exact match first
                dockerfile_path = stack_dir / f"Dockerfile.{clean_service_name}"
                if dockerfile_path.exists():
                    return True

                # Try with underscores instead of hyphens
                service_with_underscores = clean_service_name.replace("-", "_")
                dockerfile_path_underscore = (
                    stack_dir / f"Dockerfile.{service_with_underscores}"
                )
                if dockerfile_path_underscore.exists():
                    return True

                # Try with hyphens instead of underscores
                service_with_hyphens = clean_service_name.replace("_", "-")
                dockerfile_path_hyphen = (
                    stack_dir / f"Dockerfile.{service_with_hyphens}"
                )
                if dockerfile_path_hyphen.exists():
                    return True

            return False
        except Exception:
            return False

    def _load_build_contexts(self):
        """Load build configurations from build_contexts.json"""
        try:
            config_file = Path(__file__).parent.parent / "build_contexts.json"
            if config_file.exists():
                with open(config_file) as f:
                    self._build_contexts_cache = json.load(f)
            else:
                self._build_contexts_cache = {}
        except Exception:
            self._build_contexts_cache = {}

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
        result = podman_cmd(
            [
                "ps",
                "-a",
                "--format",
                "{{.Names}};{{.Image}};{{.Status}};{{.Ports}}",
            ]
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

        result = podman_cmd(["images"] + (["-a"] if show_all else []))
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
                secure_run(cmd)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stats monitoring stopped[/yellow]")
        else:
            result = secure_run(cmd)
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
        result = podman_cmd(["volume", "ls", "--format", "table"])
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
        result = podman_cmd(["network", "ls"])
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

        result = podman_cmd(["system", "df"])

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
            result = secure_run(events_cmd)
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

        result = secure_run(cmd)
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
                f"{service_name}-1",  # Common suffix
                f"{service_name}_1",  # Alternative suffix
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

            # Check if container exists and get its status
            result = podman_cmd(
                [
                    "ps",
                    "-a",
                    "--filter",
                    f"name=^{container_name}$",
                    "--format",
                    "{{.Status}}",
                ],
                timeout=5,
            )

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
            result = podman_cmd(
                [
                    "ps",
                    "-a",
                    "--filter",
                    f"name={container_name}",
                    "--format",
                    "{{.Names}} {{.Status}}",
                ],
                timeout=5,
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
        """Get all container statuses at once using a single podman ps command with timeout protection

        When podman is unresponsive, this will return an empty dict, triggering systemd fallback
        in _get_service_status_from_cache which now provides more accurate status reporting.
        """
        try:
            cmd = ["podman", "ps", "-a", "--format", "{{.Names}};{{.Status}}"]

            if verbose:
                console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

            # Use 30 second timeout for podman ps command
            result = podman_cmd(
                ["ps", "-a", "--format", "{{.Names}};{{.Status}}"], timeout=30
            )

            if verbose:
                console.print(
                    f"  [dim]Debug: podman returncode={result.returncode}, stdout length={len(result.stdout) if result.stdout else 0}[/dim]"
                )
                if result.stdout:
                    console.print(
                        f"  [dim]Debug: First 200 chars of stdout: {result.stdout[:200]}[/dim]"
                    )

            if result.returncode == 0 and result.stdout.strip():
                container_statuses = {}
                for line in result.stdout.strip().split("\n"):
                    if ";" in line:
                        name, status = line.split(";", 1)
                        container_statuses[name.strip()] = status.strip()

                if verbose:
                    console.print(
                        f"  [dim]Debug: Parsed {len(container_statuses)} containers[/dim]"
                    )

                return container_statuses

            return {}

        except subprocess.TimeoutExpired:
            if verbose:
                console.print(
                    "  [yellow]⚠️  Podman command timed out after 30s - using systemd fallback[/yellow]"
                )
            return {}
        except Exception as e:
            if verbose:
                console.print(
                    f"  [red]Debug: Exception in _get_all_container_statuses: {e}[/red]"
                )
            return {}

    def _parse_systemctl_status(
        self, status_output: str, service_name: str
    ) -> tuple[str, str]:
        """
        Parse systemctl status output to extract status information.

        Example input:
        "● vllm-glm4-9b-chat.service - Podman container-vllm-glm4-9b-chat.service
           Loaded: loaded (/home/user/.config/systemd/user/vllm-glm4-9b-chat.service; enabled; preset: enabled)
           Active: active (running) since Tue 2025-11-11 13:08:46 CST; 1h 2min ago
        "

        Returns tuple: (formatted status string with Rich markup, uptime string)
        """
        lines = status_output.strip().split("\n")

        # Look for the Active line
        for line in lines:
            line = line.strip()
            if line.startswith("Active:"):
                # Parse "Active: active (running) since Tue 2025-11-11 13:08:46 CST; 1h 2min ago"
                # Extract the status and time info
                try:
                    # Split on 'since' to separate status from timestamp
                    if " since " in line:
                        status_part = line.split(" since ")[0].replace("Active: ", "")
                        time_part = line.split("; ")[-1] if "; " in line else ""

                        # Clean up the status part
                        status_clean = status_part.strip()

                        # Format based on status
                        if "active (running)" in status_clean:
                            return ("[green]active[/green]", time_part)
                        elif "active" in status_clean and "start" in status_clean:
                            return ("[yellow]starting[/yellow]", "")
                        elif "failed" in status_clean:
                            return ("[red]failed[/red]", "")
                        elif "inactive" in status_clean:
                            return ("[yellow]inactive[/yellow]", "")
                        else:
                            return (f"[dim]{status_clean}[/dim]", "")
                    else:
                        # Handle cases without 'since'
                        status_part = line.replace("Active: ", "").strip()
                        if "active (running)" in status_part:
                            return ("[green]active[/green]", "")
                        elif "failed" in status_part:
                            return ("[red]failed[/red]", "")
                        elif "inactive" in status_part:
                            return ("[yellow]inactive[/yellow]", "")
                        else:
                            return (f"[dim]{status_part}[/dim]", "")
                except Exception:
                    # Fallback if parsing fails
                    return ("[dim]unknown[/dim]", "")

        # Look for Loaded line to check if service exists
        for line in lines:
            line = line.strip()
            if line.startswith("Loaded:"):
                if "not-found" in line or "not found" in line:
                    return ("[white]not found[/white]", "")
                elif "loaded" in line:
                    # Service exists but no Active line found - unusual case
                    return ("[dim]unknown[/dim]", "")

        # If we get here, service likely doesn't exist
        return ("[white]not found[/white]", "")

    def _get_service_status_from_cache(self, service_name, all_container_statuses):
        """Get service status combining systemd status with podman health info"""
        try:
            # ALWAYS get systemd status first for uptime info
            systemd_status = None
            try:
                status_result = secure_run(
                    [
                        "systemctl",
                        "--user",
                        "status",
                        f"{service_name}.service",
                        "--no-pager",
                        "--lines=0",
                    ],
                    timeout=3,
                )
                if status_result.stdout:
                    systemd_status = self._parse_systemctl_status(
                        status_result.stdout, service_name
                    )
            except Exception:
                pass

            # Get podman health status from cache or direct query
            podman_health = None

            # Try to find health status in cache first
            if all_container_statuses:
                # Check exact match first
                if service_name in all_container_statuses:
                    podman_health = self._extract_health_status(
                        all_container_statuses[service_name]
                    )
                else:
                    # Check for partial matches
                    for container_name, status in all_container_statuses.items():
                        if service_name in container_name:
                            podman_health = self._extract_health_status(status)
                            break

                    # Check for common service variations
                    if not podman_health:
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
                                podman_health = self._extract_health_status(
                                    all_container_statuses[variation]
                                )
                                break

                            # Check partial matches for variations
                            for (
                                container_name,
                                status,
                            ) in all_container_statuses.items():
                                if variation in container_name:
                                    podman_health = self._extract_health_status(status)
                                    break
                            if podman_health:
                                break

            # If no health status in cache, try direct podman query
            if not podman_health:
                name_variations = [
                    service_name,
                    service_name.replace("-", "_"),
                    service_name.replace("_", "-"),
                ]

                for name_variant in name_variations:
                    try:
                        result = podman_cmd(
                            [
                                "ps",
                                "-a",
                                "--filter",
                                f"name=^{name_variant}$",
                                "--format",
                                "{{.Status}}",
                            ],
                            timeout=3,
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            podman_health = self._extract_health_status(
                                result.stdout.strip()
                            )
                            break
                    except Exception:
                        continue

            # Format as two columns: systemd status | podman status
            if systemd_status and podman_health:
                # Both statuses available
                return f"{systemd_status} | {podman_health}"
            elif systemd_status:
                # Only systemd status available
                # Check inactive BEFORE active (since "active" is substring of "inactive")
                if "inactive (systemd)" in systemd_status:
                    return f"{systemd_status} | [dim](not running)[/dim]"
                elif "failed (systemd)" in systemd_status:
                    return f"{systemd_status} | [dim](not running)[/dim]"
                elif "active (systemd)" in systemd_status:
                    return f"{systemd_status} | [dim](no healthcheck)[/dim]"
                return systemd_status
            else:
                # No systemd status - service not found
                return "[white]not found[/white]"

        except Exception:
            return "[red]error[/red]"

    def _get_service_status_columns(self, service_name, all_container_statuses):
        """Get service status as separate systemd and podman columns (returns tuple)"""
        try:
            # Check if this is a STDIO service
            if (
                hasattr(self.manager, "stdio_services")
                and service_name in self.manager.stdio_services
            ):
                return self._get_stdio_service_status(
                    service_name, all_container_statuses
                )

            # Get systemd status (returns tuple: status, uptime)
            systemd_status = None
            uptime = ""
            try:
                status_result = secure_run(
                    [
                        "systemctl",
                        "--user",
                        "status",
                        f"{service_name}.service",
                        "--no-pager",
                        "--lines=0",
                    ],
                    timeout=3,
                )
                if status_result.stdout:
                    systemd_status, uptime = self._parse_systemctl_status(
                        status_result.stdout, service_name
                    )
            except Exception:
                pass

            # Get podman health status from cache or direct query
            podman_health = None

            # Try to find health status in cache first
            if all_container_statuses:
                # Check exact match first
                if service_name in all_container_statuses:
                    podman_health = self._extract_health_status(
                        all_container_statuses[service_name]
                    )
                else:
                    # Check for partial matches
                    for container_name, status in all_container_statuses.items():
                        if service_name in container_name:
                            podman_health = self._extract_health_status(status)
                            break

                    # Check for common service variations
                    if not podman_health:
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
                                podman_health = self._extract_health_status(
                                    all_container_statuses[variation]
                                )
                                break

                            # Check partial matches for variations
                            for (
                                container_name,
                                status,
                            ) in all_container_statuses.items():
                                if variation in container_name:
                                    podman_health = self._extract_health_status(status)
                                    break
                            if podman_health:
                                break

            # If no health status in cache, try direct podman query
            if not podman_health:
                name_variations = [
                    service_name,
                    service_name.replace("-", "_"),
                    service_name.replace("_", "-"),
                ]

                for name_variant in name_variations:
                    try:
                        result = podman_cmd(
                            [
                                "ps",
                                "-a",
                                "--filter",
                                f"name=^{name_variant}$",
                                "--format",
                                "{{.Status}}",
                            ],
                            timeout=3,
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            podman_health = self._extract_health_status(
                                result.stdout.strip()
                            )
                            break
                    except Exception:
                        continue

            # Build podman column: uptime + health status with color coding
            podman_column = ""

            # Color code uptime - green indicates running
            uptime_colored = ""
            if uptime:
                uptime_colored = f"[green]{uptime}[/green]"

            if podman_health:
                # Color code based on health status
                if "(healthy)" in podman_health:
                    health_colored = "[green](healthy)[/green]"
                elif "(unhealthy)" in podman_health:
                    health_colored = "[yellow](unhealthy)[/yellow]"
                elif "(starting)" in podman_health:
                    health_colored = "[yellow](starting)[/yellow]"
                elif "(running)" in podman_health:
                    health_colored = "[green](running)[/green]"
                elif "(no healthcheck)" in podman_health:
                    health_colored = "[dim](no healthcheck)[/dim]"
                else:
                    health_colored = podman_health

                if uptime_colored:
                    podman_column = f"{uptime_colored} {health_colored}"
                else:
                    podman_column = health_colored
            elif systemd_status:
                # No podman health - add appropriate indicator
                if "inactive" in systemd_status or "failed" in systemd_status:
                    if uptime_colored:
                        podman_column = f"{uptime_colored} [dim](not running)[/dim]"
                    else:
                        podman_column = "[dim](not running)[/dim]"
                elif "active" in systemd_status:
                    if uptime_colored:
                        podman_column = f"{uptime_colored} [dim](no healthcheck)[/dim]"
                    else:
                        podman_column = "[dim](no healthcheck)[/dim]"
            elif uptime_colored:
                # Just uptime, no status
                podman_column = uptime_colored

            # Return as tuple (systemd_column, podman_column)
            if systemd_status:
                return (systemd_status, podman_column)
            else:
                return ("[white]not found[/white]", "")

        except Exception:
            return ("[red]error[/red]", "")

    def _get_stdio_service_status(self, service_name, all_container_statuses):
        """Get status for STDIO services (not managed by systemd)"""
        try:
            # STDIO services don't use systemd
            systemd_status = "[green]stdio[/green]"

            # Check if container is running via podman
            podman_status = ""

            # Try to find the container in podman
            if all_container_statuses:
                # Check exact match first
                if service_name in all_container_statuses:
                    container_status = all_container_statuses[service_name]
                    health = self._extract_health_status(container_status)
                    if health:
                        podman_status = health
                    else:
                        # Container exists but no clear status
                        podman_status = "[dim](status unknown)[/dim]"
                else:
                    # Check for partial matches
                    for container_name, status in all_container_statuses.items():
                        if service_name in container_name:
                            health = self._extract_health_status(status)
                            if health:
                                podman_status = health
                            break

            # If no container found in cache, it's not running
            if not podman_status:
                podman_status = "[green]not applicable[/green]"

            return (systemd_status, podman_status)

        except Exception:
            return ("[green]stdio[/green]", "[green]not applicable[/green]")

    def _extract_health_status(self, podman_status):
        """Extract health status from podman status string"""
        if not podman_status:
            return None

        status_lower = podman_status.lower()
        if "(healthy)" in status_lower:
            return "(healthy)"
        elif "(unhealthy)" in status_lower:
            return "(unhealthy)"
        elif "(starting)" in status_lower:
            return "(starting)"
        elif "(running)" in status_lower:
            return "(running)"
        elif "up" in status_lower:
            # Container is running but has no health status indicator
            return "(no healthcheck)"
        return None

    def _format_status(self, status):
        """Format container status with appropriate colors, preserving health status"""
        status_lower = status.lower()

        if "unhealthy" in status_lower or "starting" in status_lower:
            return f"[yellow]{status}[/yellow]"
        elif "up" in status_lower or "running" in status_lower:
            # Preserve health status from podman (e.g., "(healthy)")
            # Only add (running) if there's no parenthesis at all
            if "(" not in status:
                return f"[green]{status} (running)[/green]"
            else:
                # Status already has health info like "(healthy)" - preserve it
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
                result = podman_cmd(
                    [
                        "ps",
                        "-a",
                        "--filter",
                        f"name=^{container_name}$",
                        "--format",
                        "{{.ID}} {{.Image}}",
                    ],
                    timeout=5,
                )

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

    def _get_supabase_startup_order(self, service_name: str) -> int:
        """Get startup order number for a Supabase service"""
        # Build order cache if not already built
        if self._supabase_order_cache is None:
            self._supabase_order_cache = {}

            # Import here to avoid circular dependency
            from managers.supabase_stack_manager import SupabaseStackManager

            # Create temporary instance just to access startup_order
            temp_manager = SupabaseStackManager(self.manager)

            # Build mapping of service name to startup order
            for order, layer in enumerate(temp_manager.startup_order, start=1):
                for service in layer["services"]:
                    self._supabase_order_cache[service] = order

        return self._supabase_order_cache.get(service_name, 0)
