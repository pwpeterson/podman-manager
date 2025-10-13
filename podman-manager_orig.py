#!/usr/bin/env python3
"""
Podman Container Management Script with Rich Console Output
A complete standalone Python implementation for managing Podman containers
"""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

try:
    from loguru import logger
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.prompt import Confirm
    from rich.table import Table
    from rich.tree import Tree
except ImportError:
    print("Error: Required libraries not found. Install with:")
    print("pip install rich pyyaml loguru")
    sys.exit(1)

# Configure Rich console
console = Console()

# Configure Loguru with Rich integration
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format=(
        "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    level="WARNING",
    colorize=True,
    enqueue=True,
)

# Add file logging for debugging
logger.add(
    Path.home() / ".local/share/podman-manager.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    format=(
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{name}:{function}:{line} | {message}"
    ),
    serialize=True,  # JSON format for structured logs
)


class PodmanManager:
    """Main class for managing Podman containers with Rich UI"""

    def __init__(self, compose_dir: Optional[str] = None):
        self.compose_dir = (
            Path(compose_dir)
            if compose_dir
            else Path.home() / "srv" / "local-ai-packaged"
        )
        self.projects_cache: Dict[str, Dict] = {}
        logger.debug(
            "Initializing PodmanManager with compose_dir: {}", self.compose_dir
        )
        self._validate_prerequisites()

    def _validate_prerequisites(self) -> bool:
        """Validate that required tools and directories exist"""
        logger.debug("Starting prerequisites validation")

        # Check podman
        if not self._command_exists("podman"):
            logger.error("Required command 'podman' not found!")
            return False

        # Check podman compose
        result = subprocess.run(
            ["podman", "compose", "--help"], capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error("'podman compose' is not available!")
            console.print(
                "[dim]Make sure you have podman-compose plugin installed[/dim]"
            )
            return False

        # Check compose directory
        if not self.compose_dir.exists():
            logger.error("Compose directory does not exist: {}", self.compose_dir)
            console.print(
                "[dim]Set PODMAN_COMPOSE_DIR environment variable to correct path[/dim]"
            )
            return False

        if not self.compose_dir.is_dir() or not os.access(self.compose_dir, os.R_OK):
            logger.error("Compose directory is not readable: {}", self.compose_dir)
            return False

        logger.success("Prerequisites validation complete")
        return True

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        result = subprocess.run(["which", command], capture_output=True)
        exists = result.returncode == 0
        logger.debug("Command '{}' exists: {}", command, exists)
        return exists

    def _validate_compose_file(self, compose_file: Path) -> bool:
        """Validate that compose file exists and has valid YAML"""
        if not compose_file.exists():
            logger.error("Compose file not found: {}", compose_file)
            return False

        if not os.access(compose_file, os.R_OK):
            logger.error("Compose file is not readable: {}", compose_file)
            return False

        try:
            with open(compose_file, "r") as f:
                yaml.safe_load(f)
            logger.debug("YAML validation passed for: {}", compose_file)
        except yaml.YAMLError as e:
            logger.error("Invalid YAML syntax in {}: {}", compose_file, e)
            console.print(f"[dim]Error: {e}[/dim]")
            return False

        return True

    def _parse_compose_files(self) -> Dict[str, Dict]:
        """Parse all compose files and extract project/service information"""
        projects = {}
        logger.debug("Parsing compose files in: {}", self.compose_dir)

        for compose_file in self.compose_dir.glob("podman-compose*.yml"):
            if not self._validate_compose_file(compose_file):
                continue

            try:
                with open(compose_file, "r") as f:
                    compose_data = yaml.safe_load(f)

                # Extract project name
                if compose_file.name == "podman-compose.yml":
                    project_name = "default"
                else:
                    project_name = compose_file.name.replace(
                        "podman-compose-", ""
                    ).replace(".yml", "")

                # Use name from compose file if available
                if compose_data and "name" in compose_data:
                    project_name = compose_data["name"]

                # Extract services
                services = {}
                if compose_data and "services" in compose_data:
                    for service_name, service_config in compose_data[
                        "services"
                    ].items():
                        services[service_name] = {
                            "profiles": service_config.get("profiles", []),
                            "depends_on": service_config.get("depends_on", []),
                            "links": service_config.get("links", []),
                            "build": service_config.get("build", {}),
                        }

                projects[project_name] = {
                    "file": compose_file,
                    "services": services,
                    "compose_data": compose_data,
                }

                logger.debug(
                    "Parsed project '{}' with {} services", project_name, len(services)
                )

            except Exception as e:
                logger.warning("Failed to parse {}: {}", compose_file, e)

        self.projects_cache = projects
        logger.info("Parsed {} projects with compose files", len(projects))
        return projects

    def _get_project_name(self, compose_file: Path) -> str:
        """Get project name from compose file"""
        filename = compose_file.name

        try:
            with open(compose_file, "r") as f:
                compose_data = yaml.safe_load(f)
                if compose_data and "name" in compose_data:
                    return compose_data["name"]
        except (OSError, yaml.YAMLError):
            pass

        if filename == "podman-compose.yml":
            return "default"
        else:
            return filename.replace("podman-compose-", "").replace(".yml", "")

    def _find_service_project(self, service_name: str) -> Optional[str]:
        """Find which project contains a given service"""
        projects = self._parse_compose_files()

        for project_name, project_info in projects.items():
            if service_name in project_info["services"]:
                logger.debug(
                    "Found service '{}' in project '{}'", service_name, project_name
                )
                return project_info["file"].name

        logger.debug("Service '{}' not found in any project", service_name)
        return None

    def _setup_compose_command(
        self,
        project: Optional[str],
        compose_file: Optional[Path],
        profile_args: str = "",
        remove_orphans: bool = False,
    ) -> Tuple[str, str]:
        """Setup the base compose command with proper arguments"""
        if compose_file is None:
            raise ValueError("compose_file cannot be None")

        actual_project_name = self._get_project_name(compose_file)

        base_cmd = f"podman compose -p {actual_project_name} -f {compose_file.name}"

        if profile_args:
            base_cmd += f" {profile_args}"

        orphan_args = "--remove-orphans" if remove_orphans else ""

        logger.debug(
            "Setup compose command: {} (orphan_args: {})", base_cmd, orphan_args
        )
        return base_cmd, orphan_args

    def _run_compose_command(
        self, cmd: str, action: str, cwd: Optional[Path] = None
    ) -> subprocess.CompletedProcess:
        """Execute a compose command and return the result"""
        if cwd is None:
            cwd = self.compose_dir

        # Display command in a subtle way
        console.print(f"  [white]exec: {cmd}[/white]")

        # Use loguru's context binding for structured logging
        with logger.contextualize(action=action, command=cmd, working_dir=str(cwd)):
            logger.info("Executing command: {}", cmd)

            start_time = time.time()
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, cwd=cwd
            )
            execution_time = time.time() - start_time

            # Filter out noise from output
            stdout_lines = [
                line
                for line in result.stdout.split("\n")
                if "Executing external compose provider" not in line and line.strip()
            ]
            result.stdout = "\n".join(stdout_lines)

            stderr_lines = [
                line
                for line in result.stderr.split("\n")
                if "Executing external compose provider" not in line and line.strip()
            ]
            result.stderr = "\n".join(stderr_lines)

            # Log the result with context
            if result.returncode == 0:
                logger.success(
                    "Command completed successfully in {:.2f}s", execution_time
                )
                if result.stdout:
                    logger.debug(
                        "Command output: {}",
                        (
                            result.stdout[:200] + "..."
                            if len(result.stdout) > 200
                            else result.stdout
                        ),
                    )
            else:
                logger.error(
                    "Command failed with code {} in {:.2f}s",
                    result.returncode,
                    execution_time,
                )
                if result.stderr:
                    logger.error("Error output: {}", result.stderr)
                    console.print(f"[red]Command failed: {result.stderr.strip()}[/red]")

            return result

    def _handle_container_dependencies(self, service: str) -> bool:
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
                import time

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

    def _simple_container_removal(self, service: str) -> bool:
        """Simple container stop and remove with error handling"""
        """Fallback simple container removal (legacy method)"""
        # This method is kept for backward compatibility but should rarely be used
        # The new _handle_container_dependencies method is more intelligent

        console.print(f"[yellow]Using fallback removal method for {service}[/yellow]")

        # Try direct removal
        rm_cmd = [
            "podman",
            "rm",
            "-f",
            service,
        ]  # Use force to handle running containers
        console.print(f"  [white]exec: {' '.join(rm_cmd)}[/white]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Force removing container: {service}", total=None)
            rm_result = subprocess.run(rm_cmd, capture_output=True, text=True)
            progress.remove_task(task)

        if rm_result.returncode == 0:
            console.print(f"[green]Successfully removed container: {service}[/green]")
            return True
        else:
            error_msg = rm_result.stderr.strip()
            if "no such container" in error_msg.lower():
                console.print(f"[dim]Container {service} does not exist[/dim]")
                return True
            else:
                console.print(f"[red]Failed to remove container: {error_msg}[/red]")
                return False

        return True

    def _check_dependencies(self, compose_file: Path, service: str) -> List[str]:
        """Check service dependencies and return list of missing ones"""
        projects = self._parse_compose_files()
        project_name = self._get_project_name(compose_file)

        if project_name not in projects:
            return []

        service_config = projects[project_name]["services"].get(service, {})
        dependencies = service_config.get("depends_on", [])

        missing_deps = []
        for dep in dependencies:
            # Check if dependency is running
            dep_cmd = [
                "podman",
                "ps",
                "--filter",
                f"name=^{dep}$",
                "--filter",
                "status=running",
                "--format",
                "{{.Names}}",
            ]
            result = subprocess.run(
                dep_cmd,
                capture_output=True,
                text=True,
            )

            if dep not in result.stdout:
                missing_deps.append(dep)

        if missing_deps:
            logger.warning("Missing dependencies for {}: {}", service, missing_deps)

        return missing_deps

    def _analyze_log_patterns(self, logs: str, service: str) -> Dict[str, int]:
        """Analyze log patterns and return health metrics"""
        error_patterns = r"error|fatal|exception|failed|crash"
        warning_patterns = r"warn|warning"
        startup_patterns = r"starting|started|listening|ready|serving|initialized"
        connection_patterns = (
            r"connection.*failed|connection.*refused|timeout|unreachable"
        )
        memory_patterns = r"out of memory|memory.*error|oom"
        permission_patterns = r"permission denied|access denied|unauthorized"

        metrics = {
            "errors": len(re.findall(error_patterns, logs, re.IGNORECASE)),
            "warnings": len(re.findall(warning_patterns, logs, re.IGNORECASE)),
            "startup_indicators": len(
                re.findall(startup_patterns, logs, re.IGNORECASE)
            ),
            "connection_errors": len(
                re.findall(connection_patterns, logs, re.IGNORECASE)
            ),
            "memory_issues": len(re.findall(memory_patterns, logs, re.IGNORECASE)),
            "permission_issues": len(
                re.findall(permission_patterns, logs, re.IGNORECASE)
            ),
        }

        # Recent logs (last 50 lines)
        recent_logs = "\n".join(logs.split("\n")[-50:])
        metrics["recent_errors"] = len(
            re.findall(error_patterns, recent_logs, re.IGNORECASE)
        )
        metrics["recent_warnings"] = len(
            re.findall(warning_patterns, recent_logs, re.IGNORECASE)
        )

        logger.debug("Log analysis for {}: {}", service, metrics)
        return metrics

    def _get_health_status(self, metrics: Dict[str, int]) -> Tuple[str, str]:
        """Determine health status from log metrics"""
        if (
            metrics["errors"] == 0
            and metrics["warnings"] <= 2
            and metrics["startup_indicators"] > 0
        ):
            return "HEALTHY", "green"
        elif (
            metrics["recent_errors"] == 0
            and metrics["recent_warnings"] <= 1
            and metrics["startup_indicators"] > 0
        ):
            return "MOSTLY_HEALTHY", "yellow"
        elif metrics["errors"] > 0 or metrics["recent_errors"] > 0:
            return "UNHEALTHY", "red"
        elif metrics["warnings"] > 5 or metrics["recent_warnings"] > 2:
            return "WARNING", "yellow"
        else:
            return "UNKNOWN", "dim"

    def show_help(self):
        """Display help information with Rich formatting - improved layout and visual hierarchy"""

        # Create header panel
        console.print()
        console.print(
            Panel.fit(
                "[bold blue]Podman Container Management Tool[/bold blue]\n"
                "[dim]Comprehensive container lifecycle management with Rich UI[/dim]",
                style="blue",
                padding=(1, 2),
            )
        )

        # Overview section
        console.print()
        console.print("[bold cyan]Overview[/bold cyan]")
        console.print(
            "[dim]Standalone Python application for managing Podman containers using compose files.[/dim]"
        )
        console.print(
            "[dim]Features enhanced logging, health monitoring, and beautiful terminal interface.[/dim]"
        )

        # Commands section with tables for better organization
        console.print()
        console.print("[bold cyan]Available Commands[/bold cyan]")

        # Status & Information Commands
        console.print()
        console.print("[bold yellow]Status & Information[/bold yellow]")
        info_table = Table(show_header=False, box=None, padding=(0, 2))
        info_table.add_column("Command", style="green", width=20)
        info_table.add_column("Description", style="white")
        info_table.add_row("status", "Show all projects and services in tree view")
        info_table.add_row("ps", "Show container status in formatted table")
        info_table.add_row(
            "inspect TARGET", "Show detailed container or image information"
        )
        info_table.add_row("config TARGET", "Show compose configuration for project")
        info_table.add_row("help", "Show this help message")
        console.print(info_table)

        # Container Lifecycle Commands
        console.print()
        console.print("[bold yellow]Container Lifecycle[/bold yellow]")
        lifecycle_table = Table(show_header=False, box=None, padding=(0, 2))
        lifecycle_table.add_column("Command", style="green", width=20)
        lifecycle_table.add_column("Description", style="white")
        lifecycle_table.add_row(
            "up TARGET", "Start services (create and start containers)"
        )
        lifecycle_table.add_row("down TARGET", "Stop and remove services/projects")
        lifecycle_table.add_row("start TARGET", "Start stopped containers")
        lifecycle_table.add_row(
            "reinit TARGET", "Remove and recreate containers (fresh start)"
        )
        lifecycle_table.add_row(
            "restart TARGET", "Quick restart of existing containers"
        )
        lifecycle_table.add_row("stop TARGET", "Gracefully stop containers")
        lifecycle_table.add_row(
            "remove TARGET", "Remove containers (preserves volumes)"
        )
        lifecycle_table.add_row("pause TARGET", "Pause running containers")
        lifecycle_table.add_row("unpause TARGET", "Unpause paused containers")
        lifecycle_table.add_row("kill TARGET", "Force kill containers with signal")
        console.print(lifecycle_table)

        # Build & Images Commands
        console.print()
        console.print("[bold yellow]Build & Images[/bold yellow]")
        build_table = Table(show_header=False, box=None, padding=(0, 2))
        build_table.add_column("Command", style="green", width=20)
        build_table.add_column("Description", style="white")
        build_table.add_row("build TARGET", "Build images for project or service")
        build_table.add_row("pull TARGET", "Pull latest images from registry")
        build_table.add_row("push TARGET", "Push images to registry")
        build_table.add_row("images", "List all images with details")
        build_table.add_row("prune", "Clean up unused resources")
        console.print(build_table)

        # Monitoring & Debugging Commands
        console.print()
        console.print("[bold yellow]Monitoring & Debugging[/bold yellow]")
        monitor_table = Table(show_header=False, box=None, padding=(0, 2))
        monitor_table.add_column("Command", style="green", width=22)
        monitor_table.add_column("Description", style="white")
        monitor_table.add_row(
            "logs SERVICE", "Analyze service logs with health metrics"
        )
        monitor_table.add_row(
            "exec SERVICE CMD", "Execute command in running container"
        )
        monitor_table.add_row("run SERVICE CMD", "Run one-off command in new container")
        monitor_table.add_row("stats", "Show resource usage statistics")
        monitor_table.add_row("top SERVICE", "Show running processes in container")
        monitor_table.add_row("port SERVICE", "Show port mappings")
        monitor_table.add_row("events", "Stream real-time podman events")
        monitor_table.add_row("wait TARGET", "Wait for containers to stop")
        console.print(monitor_table)

        # Resource Management Commands
        console.print()
        console.print("[bold yellow]Resource Management[/bold yellow]")
        resource_table = Table(show_header=False, box=None, padding=(0, 2))
        resource_table.add_column("Command", style="green", width=20)
        resource_table.add_column("Description", style="white")
        resource_table.add_row("volumes", "List volumes with disk usage")
        resource_table.add_row("networks", "List networks")
        resource_table.add_row("system-df", "Show system disk usage")
        resource_table.add_row(
            "remove-orphans", "Clean up project-specific orphaned resources"
        )
        resource_table.add_row("systemd ACTION", "Create systemd unit files")
        console.print(resource_table)

        # Usage Examples with better formatting
        console.print()
        console.print("[bold cyan]Usage Examples[/bold cyan]")

        examples = [
            (
                "Basic Operations",
                [
                    ("pm status", "Show all projects"),
                    ("pm ps", "Container status table"),
                    ("pm reinit ollama", "Recreate service"),
                    ("pm restart vllm-models", "Restart entire project"),
                ],
            ),
            (
                "Building & Images",
                [
                    ("pm build --no-cache service", "Build without cache"),
                    ("pm pull vllm-models", "Pull latest images"),
                    ("pm images --all", "Show all images"),
                ],
            ),
            (
                "Monitoring & Debug",
                [
                    ("pm logs open-webui", "Analyze logs with health check"),
                    ("pm exec ollama bash", "Interactive shell"),
                    ("pm stats --follow", "Live resource monitoring"),
                ],
            ),
            (
                "Resource Management",
                [
                    ("pm prune --all --volumes", "Deep cleanup"),
                    ("pm volumes", "List volumes with sizes"),
                    ("pm system-df", "Show disk usage"),
                ],
            ),
        ]

        for category, commands in examples:
            console.print()
            console.print(f"[bold magenta]{category}[/bold magenta]")
            example_table = Table(show_header=False, box=None, padding=(0, 2))
            example_table.add_column("Command", style="yellow", width=32)
            example_table.add_column("Description", style="white", width=40)
            for cmd, desc in commands:
                example_table.add_row(cmd, f"# {desc}")
            console.print(example_table)

        # Environment Variables
        console.print()
        console.print("[bold cyan]Environment Variables[/bold cyan]")
        env_table = Table(show_header=False, box=None, padding=(0, 2))
        env_table.add_column("Variable", style="blue", width=25)
        env_table.add_column("Description", style="white")
        env_table.add_row(
            "PODMAN_COMPOSE_DIR",
            "Directory containing compose files [dim](default: ~/srv/local-ai-packaged)[/dim]",
        )
        console.print(env_table)

        # Features with icons
        console.print()
        console.print("[bold cyan]Key Features[/bold cyan]")
        features = [
            "Rich Console Output with colors, panels, and tables",
            "Health Metrics for log analysis with recommendations",
            "Progress Tracking with spinners and time elapsed",
            "Smart Detection of projects vs services",
            "Safety Checks with confirmations for destructive operations",
            "YAML Validation with detailed error reporting",
            "Dependency Checking to prevent startup failures",
        ]

        for feature in features:
            console.print(f"  • {feature}")

        # Target Types
        console.print()
        console.print("[bold cyan]Target Types[/bold cyan]")
        target_table = Table(show_header=False, box=None, padding=(0, 2))
        target_table.add_column("Type", style="red bold", width=12)
        target_table.add_column("Description", style="white")
        target_table.add_column("Example", style="dim")
        target_table.add_row(
            "PROJECT", "Operates on all services in a compose file", "vllm-models"
        )
        target_table.add_row("SERVICE", "Operates on a specific service", "open-webui")
        console.print(target_table)

        console.print()
        console.print(
            "[dim]The tool automatically detects whether your target is a project or service.[/dim]"
        )

        # Footer with quick tips
        console.print()
        console.print(
            Panel(
                "[bold]Quick Tips:[/bold]\n"
                "• Use [yellow]pm[/yellow] as a short alias for [yellow]podman-manager[/yellow]\n"
                "• Add [yellow]--dry-run[/yellow] to see what commands would be executed\n"
                "• Use [yellow]--build[/yellow] flag to rebuild images during reinit\n"
                "• Check logs first with [yellow]pm logs SERVICE[/yellow] before troubleshooting",
                title="Pro Tips",
                style="blue",
                width=80,
                padding=(1, 2),
            )
        )

    def show_status(self):
        """Show status of all projects and services"""
        projects = self._parse_compose_files()

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
        projects = self._parse_compose_files()

        if not projects:
            console.print(f"[red]No compose files found in {self.compose_dir}[/red]")
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
        console.print(Panel.fit("Container Status", style="bold blue"))

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
            logger.error("Failed to get container status: {}", result.stderr)
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
        console.print(Panel.fit("Container Images", style="bold blue"))

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

    def build(self, target: str, no_cache: bool = False):
        """Build images for target"""
        projects = self._parse_compose_files()
        project = None
        service = None
        compose_file = None

        # Determine if target is project or service
        if target in projects:
            project = target
            compose_file = projects[target]["file"]
        else:
            found_file = self._find_service_project(target)
            if found_file:
                service = target
                for proj_name, proj_info in projects.items():
                    if proj_info["file"].name == found_file:
                        project = proj_name
                        compose_file = proj_info["file"]
                        break
            else:
                console.print(f"[red]Could not find project or service: {target}[/red]")
                return False

        # Setup build command
        base_cmd, _ = self._setup_compose_command(project, compose_file)
        build_cmd = f"{base_cmd} build"

        if no_cache:
            build_cmd += " --no-cache"

        if service:
            build_cmd += f" {service}"
            console.print(f"[green]Building service: {service}[/green]")
        else:
            console.print(f"[green]Building project: {project}[/green]")

        # Stream build output live
        console.print(f"  [white]exec: {build_cmd}[/white]")
        result = subprocess.run(
            build_cmd, shell=True, cwd=self.compose_dir, capture_output=True, text=True
        )

        if result.returncode == 0:
            console.print("[green]Build completed successfully[/green]")
            if result.stdout.strip():
                console.print(result.stdout)
            return True
        else:
            error_msg = (
                result.stderr.strip()
                if result.stderr.strip()
                else "Build failed with unknown error"
            )
            console.print(f"[red]Build failed: {error_msg}[/red]")
            return False

    def pull(self, target: str):
        """Pull latest images for target"""
        projects = self._parse_compose_files()
        project = None
        service = None
        compose_file = None

        # Determine if target is project or service
        if target in projects:
            project = target
            compose_file = projects[target]["file"]
        else:
            found_file = self._find_service_project(target)
            if found_file:
                service = target
                for proj_name, proj_info in projects.items():
                    if proj_info["file"].name == found_file:
                        project = proj_name
                        compose_file = proj_info["file"]
                        break
            else:
                console.print(f"[red]Could not find project or service: {target}[/red]")
                return False

        base_cmd, _ = self._setup_compose_command(project, compose_file)
        pull_cmd = f"{base_cmd} pull"

        if service:
            pull_cmd += f" {service}"
            console.print(f"[green]Pulling images for service: {service}[/green]")
        else:
            console.print(f"[green]Pulling images for project: {project}[/green]")

        result = self._run_compose_command(pull_cmd, f"pull images for {target}")

        if result.returncode == 0:
            console.print(f"[green]Successfully pulled images for {target}[/green]")
            return True
        else:
            console.print(Panel(result.stderr, title="Error", style="red"))
            return False

    def prune(self, all_images: bool = False, volumes: bool = False):
        """Clean up unused resources"""
        console.print("[green]Cleaning up unused resources...[/green]")

        commands = []
        if all_images:
            commands.append(("podman image prune -a -f", "unused images"))
        else:
            commands.append(("podman image prune -f", "dangling images"))

        if volumes:
            commands.append(("podman volume prune -f", "unused volumes"))

        commands.append(("podman container prune -f", "stopped containers"))
        commands.append(("podman network prune -f", "unused networks"))

        success_count = 0
        for cmd, description in commands:
            console.print(f"[dim]Removing {description}...[/dim]")
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            if result.returncode == 0:
                success_count += 1
                if result.stdout.strip():
                    console.print(f"[green]{result.stdout.strip()}[/green]")
            else:
                error_msg = (
                    result.stderr.strip() if result.stderr.strip() else "Unknown error"
                )
                console.print(f"[red]Failed to remove {description}: {error_msg}[/red]")

        console.print(
            f"[green]Cleanup completed ({success_count}/{len(commands)} operations successful)[/green]"
        )
        return success_count == len(commands)

    def exec_command(self, service: str, command: str, user: Optional[str] = None):
        """Execute command in running container"""
        # Find running container for service
        check_cmd = [
            "podman",
            "ps",
            "--filter",
            f"name={service}",
            "--filter",
            "status=running",
            "--format",
            "{{.Names}}",
        ]
        result = subprocess.run(
            check_cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            error_msg = (
                result.stderr.strip()
                if result.stderr.strip()
                else "Failed to check container status"
            )
            console.print(f"[red]Error checking service status: {error_msg}[/red]")
            return False

        if service not in result.stdout:
            console.print(f"[red]Service {service} is not running[/red]")
            return False

        exec_cmd = ["podman", "exec"]
        if user:
            exec_cmd.extend(["-u", user])
        exec_cmd.extend(["-it", service])
        exec_cmd.extend(command.split())

        console.print(f"[green]Executing in {service}: {command}[/green]")

        # Run interactively
        result = subprocess.run(exec_cmd, text=True)
        return result.returncode == 0

    def show_stats(self, follow: bool = False):
        """Show resource usage statistics"""
        cmd = ["podman", "stats", "--no-stream"]
        if follow:
            cmd.remove("--no-stream")

        console.print(Panel.fit("Container Resource Usage", style="bold blue"))

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
        console.print(Panel.fit("Podman Volumes", style="bold blue"))

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
        console.print(Panel.fit("Podman Networks", style="bold blue"))

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

    def reinit(
        self,
        target: str,
        build: bool = False,
        dry_run: bool = False,
        remove_orphans: bool = False,
    ):
        """Reinitialize containers"""

        with logger.contextualize(
            target=target, build=build, dry_run=dry_run, remove_orphans=remove_orphans
        ):
            logger.debug("Starting reinit operation for target: {}", target)

            # Parse arguments to determine project/service
            projects = self._parse_compose_files()
            project = None
            service = None
            compose_file = None

            # Check if target is a project
            if target in projects:
                project = target
                compose_file = projects[target]["file"]

                # Special case for vllm-models
                if project == "vllm-models":
                    logger.error(
                        "Project 'vllm-models' requires a specific service to be specified."
                    )
                    console.print("\n[dim]Available services in vllm-models:[/dim]")
                    for service_name in projects[project]["services"].keys():
                        console.print(f"  - {service_name}")
                    return False
            else:
                # Check if target is a service
                found_file = self._find_service_project(target)
                if found_file:
                    service = target
                    for proj_name, proj_info in projects.items():
                        if proj_info["file"].name == found_file:
                            project = proj_name
                            compose_file = proj_info["file"]
                            break

                    # Service found in project - no need to display this
                else:
                    logger.error("Could not find project or service: {}", target)
                    console.print("\n[dim]Available projects:[/dim]")
                    for project_name in projects.keys():
                        console.print(f"  - {project_name}")
                    return False

            if not compose_file:
                logger.error("Could not determine compose file for: {}", target)
                return False

            # Setup compose command
            profile_args = ""
            if service and project:
                service_config = projects[project]["services"].get(service, {})
                profiles = service_config.get("profiles", [])
                if profiles:
                    profile_args = f"--profile {','.join(profiles)}"
                    console.print(
                        f"[dim]Auto-detected profiles [{','.join(profiles)}] for service [{service}][/dim]"
                    )
                    logger.debug("Auto-detected profiles for {}: {}", service, profiles)

            base_cmd, orphan_args = self._setup_compose_command(
                project, compose_file, profile_args, remove_orphans
            )

            if dry_run:
                console.print(
                    Panel.fit(
                        "Dry-run mode - Commands that would be executed:", style="blue"
                    )
                )
                if service:
                    console.print(f"  podman stop {service}")
                    console.print(f"  podman rm {service}")
                    build_flag = " --build" if build else ""
                    console.print(
                        f"  {base_cmd} up -d --force-recreate --no-deps {service}{build_flag}"
                    )
                else:
                    console.print(
                        f"  {base_cmd} down {orphan_args if remove_orphans else ''}"
                    )
                    if build:
                        console.print(f"  {base_cmd} --progress=plain build --no-cache")
                    console.print(f"  {base_cmd} up -d")
                return True

            # Execute the reinit process
            if service:
                # Service-specific reinit
                console.print(f"[green]Reinitializing: {service}[/green]")

                # Check dependencies
                missing_deps = self._check_dependencies(compose_file, service)
                if missing_deps:
                    logger.error(
                        "Cannot start {} due to missing dependencies: {}",
                        service,
                        missing_deps,
                    )
                    console.print(
                        f"[green]Start them with: pm reinit {' '.join(missing_deps)}[/green]"
                    )
                    return False

                # Remove existing container
                check_cmd = [
                    "podman",
                    "ps",
                    "-a",
                    "--filter",
                    f"name={service}",
                    "--format",
                    "{{.Names}}",
                ]
                console.print(f"  [white]exec: {' '.join(check_cmd)}[/white]")
                result = subprocess.run(
                    check_cmd,
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    error_msg = (
                        result.stderr.strip()
                        if result.stderr.strip()
                        else "Failed to check container status"
                    )
                    console.print(
                        f"[red]Warning checking container status: {error_msg}[/red]"
                    )
                    console.print("[green]Continuing with reinit...[/green]")

                if service in result.stdout:
                    # First, try to identify and handle dependent containers
                    removal_result = self._handle_container_dependencies(service)
                    if not removal_result:
                        console.print(
                            "[green]Container removal had issues, but continuing with compose recreation[/green]"
                        )
                        console.print(
                            "[dim]Compose will handle any remaining container conflicts[/dim]"
                        )
                    # Remove the duplicate success message - already handled above

                # Build if requested - WITH LIVE OUTPUT
                if build:
                    console.print(
                        f"[green]Building images for service: {service}[/green]"
                    )
                    build_cmd = f"{base_cmd} build --no-cache {service}"
                    console.print(f"  [white]exec: {build_cmd}[/white]")

                    # Stream build output live
                    result = subprocess.run(
                        build_cmd, shell=True, cwd=self.compose_dir, text=True
                    )

                    if result.returncode != 0:
                        console.print(f"[red]Build failed for service: {service}[/red]")
                        return False

                    console.print(
                        f"[green]Build completed successfully for: {service}[/green]"
                    )

                # Start service with progress spinner
                console.print(f"[green]Starting: {service}[/green]")
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(f"Starting service: {service}", total=None)
                    up_cmd = f"{base_cmd} up -d --force-recreate --no-deps {service}"
                    if remove_orphans:
                        up_cmd += f" {orphan_args}"

                    result = self._run_compose_command(
                        up_cmd, f"start service: {service}"
                    )
                    progress.remove_task(task)

                    if result.returncode == 0:
                        console.print(
                            f"[green]Successfully reinitialized {service}[/green]"
                        )
                        return True
                    else:
                        console.print(Panel(result.stderr, title="Error", style="red"))
                        return False

            else:
                # Project-wide reinit
                console.print(f"[green]Reinitializing project: {project}[/green]")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    # Stop all services
                    task = progress.add_task(
                        f"Stopping all services in {project}", total=None
                    )
                    down_cmd = f"{base_cmd} down"
                    if remove_orphans:
                        down_cmd += f" {orphan_args}"

                    result = self._run_compose_command(down_cmd, "stop services")
                    if result.returncode != 0:
                        progress.remove_task(task)
                        console.print(Panel(result.stderr, title="Error", style="red"))
                        return False
                    progress.remove_task(task)

                    # Build if requested - WITH LIVE OUTPUT
                    if build:
                        console.print(
                            f"[green]Building images for project: {project}[/green]"
                        )
                        build_cmd = f"{base_cmd} build --no-cache"
                        console.print(f"  [white]exec: {build_cmd}[/white]")

                        # Stream build output live
                        result = subprocess.run(
                            build_cmd, shell=True, cwd=self.compose_dir, text=True
                        )

                        if result.returncode != 0:
                            console.print(
                                f"[red]Build failed for project: {project}[/red]"
                            )
                            return False

                        console.print(
                            f"[green]Build completed successfully for: {project}[/green]"
                        )

                    # Start all services
                    task = progress.add_task(
                        f"Starting all services in {project}", total=None
                    )
                    up_cmd = f"{base_cmd} up -d"
                    result = self._run_compose_command(up_cmd, "start services")
                    progress.remove_task(task)

                    if result.returncode == 0:
                        console.print(
                            f"[green]Successfully reinitialized {project}[/green]"
                        )
                        return True
                    else:
                        console.print(Panel(result.stderr, title="Error", style="red"))
                        return False

    def logs(self, service: str):
        """Analyze service logs"""
        with logger.contextualize(service=service):
            logger.info("Analyzing logs for service: {}", service)
            projects = self._parse_compose_files()

            # Find the service
            found_file = self._find_service_project(service)
            if not found_file:
                logger.error("Service not found: {}", service)
                return False

            project = None
            compose_file = None
            for proj_name, proj_info in projects.items():
                if proj_info["file"].name == found_file:
                    project = proj_name
                    compose_file = proj_info["file"]
                    break

            if not compose_file:
                logger.error("Could not find compose file for service: {}", service)
                return False

            console.print(
                Panel.fit(f"Analyzing logs for: {service}", style="bold blue")
            )

            # Setup compose command
            base_cmd, _ = self._setup_compose_command(project, compose_file)

            # Get logs
            logs_cmd = f"{base_cmd} logs --tail=200 {service}"
            result = self._run_compose_command(logs_cmd, f"get logs for {service}")

            if result.returncode != 0:
                logger.error("Failed to retrieve logs for service: {}", service)
                console.print(Panel(result.stderr, title="Error", style="red"))
                return False

            if not result.stdout.strip():
                console.print("[yellow]No logs found for service[/yellow]")
                console.print("This could mean:")
                console.print("  - Service hasn't started yet")
                console.print("  - Service container doesn't exist")
                console.print("  - Service produces no output")
                return False

            # Analyze logs
            metrics = self._analyze_log_patterns(result.stdout, service)
            health_status, health_color = self._get_health_status(metrics)

            logger.info(
                "Health analysis for {}: {} ({})", service, health_status, metrics
            )

            # Display analysis
            console.print()
            console.print(
                f"[{health_color}]Service Health: {health_status}[/{health_color}]"
            )

            # Create metrics table
            table = Table(title="Log Analysis Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Count", justify="right", style="magenta")

            table.add_row("Total Errors", str(metrics["errors"]))
            table.add_row("Total Warnings", str(metrics["warnings"]))
            table.add_row("Startup Indicators", str(metrics["startup_indicators"]))
            table.add_row(
                "Recent Errors (last 50 lines)", str(metrics["recent_errors"])
            )
            table.add_row(
                "Recent Warnings (last 50 lines)", str(metrics["recent_warnings"])
            )

            console.print(table)

            # Show specific issues
            if metrics["connection_errors"] > 0:
                console.print(
                    f"\n[yellow]Connection Issues Detected ({metrics['connection_errors']})[/yellow]"
                )

            if metrics["memory_issues"] > 0:
                console.print(
                    f"\n[yellow]Memory Issues Detected ({metrics['memory_issues']})[/yellow]"
                )

            if metrics["permission_issues"] > 0:
                console.print(
                    f"\n[yellow]Permission Issues Detected ({metrics['permission_issues']})[/yellow]"
                )

            # Recommendations
            console.print("\n[bold]Recommendations:[/bold]")
            if health_status == "HEALTHY":
                console.print("[green]Service appears to be running normally.[/green]")
            elif health_status == "MOSTLY_HEALTHY":
                console.print(
                    "[yellow]Service is running but monitor for recurring warnings.[/yellow]"
                )
            elif health_status == "WARNING":
                console.print(
                    "[yellow]Check configuration and dependencies. Consider restart if warnings persist.[/yellow]"
                )
            elif health_status == "UNHEALTHY":
                console.print(
                    "[red]Service has errors. Check configuration, dependencies, and consider restart.[/red]"
                )
                console.print(f"   Use: pm reinit {service}")
            else:
                console.print(
                    "[dim]Unable to determine service health. Check logs manually.[/dim]"
                )

            # Ask if user wants to view live logs
            if Confirm.ask("\nDo you want to view the active log?"):
                console.print(
                    f"[dim]Showing live logs for {service}. Press Ctrl+C to exit.[/dim]"
                )
                live_logs_cmd = f"cd {self.compose_dir} && {base_cmd} logs {service} -f"
                try:
                    subprocess.run(
                        [
                            "bash",
                            "-c",
                            live_logs_cmd,
                        ]
                    )
                except KeyboardInterrupt:
                    console.print("\n[yellow]Log viewing stopped[/yellow]")

            return True

    def restart(self, target: str, remove_orphans: bool = False):
        """Restart services or projects"""
        with logger.contextualize(target=target, remove_orphans=remove_orphans):
            logger.debug("Starting restart operation for target: {}", target)

            # Parse arguments to determine project/service
            projects = self._parse_compose_files()
            project = None
            service = None
            compose_file = None

            # Check if target is a project
            if target in projects:
                project = target
                compose_file = projects[target]["file"]
            else:
                # Check if target is a service
                found_file = self._find_service_project(target)
                if found_file:
                    service = target
                    for proj_name, proj_info in projects.items():
                        if proj_info["file"].name == found_file:
                            project = proj_name
                            compose_file = proj_info["file"]
                            break
                else:
                    logger.error("Could not find project or service: {}", target)
                    console.print(
                        f"[red]Could not find project or service: {target}[/red]"
                    )
                    console.print("\n[dim]Available projects:[/dim]")
                    for project_name in projects.keys():
                        console.print(f"  - {project_name}")
                    return False

            if not compose_file:
                logger.error("Could not determine compose file for: {}", target)
                return False

            # Setup compose command
            profile_args = ""
            if service and project:
                service_config = projects[project]["services"].get(service, {})
                profiles = service_config.get("profiles", [])
                if profiles:
                    profile_args = f"--profile {','.join(profiles)}"
                    console.print(
                        f"[dim]Auto-detected profiles [{','.join(profiles)}] for service [{service}][/dim]"
                    )
                    logger.debug("Auto-detected profiles for {}: {}", service, profiles)

            base_cmd, orphan_args = self._setup_compose_command(
                project, compose_file, profile_args, remove_orphans
            )

            # Execute the restart process
            if service:
                # Service-specific restart
                console.print(f"[green]Restarting service: {service}[/green]")

                # Check dependencies
                missing_deps = self._check_dependencies(compose_file, service)
                if missing_deps:
                    logger.warning(
                        "Service {} has missing dependencies: {}",
                        service,
                        missing_deps,
                    )
                    console.print(
                        f"[yellow]Warning: Missing dependencies: {', '.join(missing_deps)}[/yellow]"
                    )
                    console.print(
                        f"[green]Start them with: pm reinit {' '.join(missing_deps)}[/green]"
                    )

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        f"Restarting service: {service}", total=None
                    )
                    restart_cmd = f"{base_cmd} restart {service}"
                    if remove_orphans:
                        restart_cmd += f" {orphan_args}"

                    result = self._run_compose_command(
                        restart_cmd, f"restart service: {service}"
                    )
                    progress.remove_task(task)

                    if result.returncode == 0:
                        console.print(
                            f"[green]Successfully restarted {service}[/green]"
                        )
                        return True
                    else:
                        console.print(Panel(result.stderr, title="Error", style="red"))
                        return False

            else:
                # Project-wide restart
                console.print(f"[green]Restarting project: {project}[/green]")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        f"Restarting all services in {project}", total=None
                    )
                    restart_cmd = f"{base_cmd} restart"
                    if remove_orphans:
                        restart_cmd += f" {orphan_args}"

                    result = self._run_compose_command(restart_cmd, "restart services")
                    progress.remove_task(task)

                    if result.returncode == 0:
                        console.print(
                            f"[green]Successfully restarted {project}[/green]"
                        )
                        return True
                    else:
                        console.print(Panel(result.stderr, title="Error", style="red"))
                        return False

    def stop(self, target: str, remove_orphans: bool = False):
        """Stop services or projects"""
        with logger.contextualize(target=target, remove_orphans=remove_orphans):
            logger.debug("Starting stop operation for target: {}", target)

            # Parse arguments to determine project/service
            projects = self._parse_compose_files()
            project = None
            service = None
            compose_file = None

            # Check if target is a project
            if target in projects:
                project = target
                compose_file = projects[target]["file"]
            else:
                # Check if target is a service
                found_file = self._find_service_project(target)
                if found_file:
                    service = target
                    for proj_name, proj_info in projects.items():
                        if proj_info["file"].name == found_file:
                            project = proj_name
                            compose_file = proj_info["file"]
                            break
                else:
                    logger.error("Could not find project or service: {}", target)
                    console.print(
                        f"[red]Could not find project or service: {target}[/red]"
                    )
                    console.print("\n[dim]Available projects:[/dim]")
                    for project_name in projects.keys():
                        console.print(f"  - {project_name}")
                    return False

            if not compose_file:
                logger.error("Could not determine compose file for: {}", target)
                return False

            # Setup compose command
            profile_args = ""
            if service and project:
                service_config = projects[project]["services"].get(service, {})
                profiles = service_config.get("profiles", [])
                if profiles:
                    profile_args = f"--profile {','.join(profiles)}"
                    console.print(
                        f"[dim]Auto-detected profiles [{','.join(profiles)}] for service [{service}][/dim]"
                    )
                    logger.debug("Auto-detected profiles for {}: {}", service, profiles)

            base_cmd, orphan_args = self._setup_compose_command(
                project, compose_file, profile_args, remove_orphans
            )

            # Execute the stop process
            if service:
                # Service-specific stop
                console.print(f"[green]Stopping service: {service}[/green]")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(f"Stopping service: {service}", total=None)
                    stop_cmd = f"{base_cmd} stop {service}"
                    if remove_orphans:
                        stop_cmd += f" {orphan_args}"

                    result = self._run_compose_command(
                        stop_cmd, f"stop service: {service}"
                    )
                    progress.remove_task(task)

                    if result.returncode == 0:
                        console.print(f"[green]Successfully stopped {service}[/green]")
                        return True
                    else:
                        console.print(Panel(result.stderr, title="Error", style="red"))
                        return False

            else:
                # Project-wide stop
                console.print(f"[green]Stopping project: {project}[/green]")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        f"Stopping all services in {project}", total=None
                    )
                    stop_cmd = f"{base_cmd} stop"
                    if remove_orphans:
                        stop_cmd += f" {orphan_args}"

                    result = self._run_compose_command(stop_cmd, "stop services")
                    progress.remove_task(task)

                    if result.returncode == 0:
                        console.print(f"[green]Successfully stopped {project}[/green]")
                        return True
                    else:
                        console.print(Panel(result.stderr, title="Error", style="red"))
                        return False

    def remove(self, target: str, remove_orphans: bool = False):
        """Remove services or projects"""
        with logger.contextualize(target=target, remove_orphans=remove_orphans):
            logger.debug("Starting remove operation for target: {}", target)

            # Parse arguments to determine project/service
            projects = self._parse_compose_files()
            project = None
            service = None
            compose_file = None

            # Check if target is a project
            if target in projects:
                project = target
                compose_file = projects[target]["file"]
            else:
                # Check if target is a service
                found_file = self._find_service_project(target)
                if found_file:
                    service = target
                    for proj_name, proj_info in projects.items():
                        if proj_info["file"].name == found_file:
                            project = proj_name
                            compose_file = proj_info["file"]
                            break
                else:
                    logger.error("Could not find project or service: {}", target)
                    console.print(
                        f"[red]Could not find project or service: {target}[/red]"
                    )
                    console.print("\n[dim]Available projects:[/dim]")
                    for project_name in projects.keys():
                        console.print(f"  - {project_name}")
                    return False

            if not compose_file:
                logger.error("Could not determine compose file for: {}", target)
                return False

            # Setup compose command
            profile_args = ""
            if service and project:
                service_config = projects[project]["services"].get(service, {})
                profiles = service_config.get("profiles", [])
                if profiles:
                    profile_args = f"--profile {','.join(profiles)}"
                    console.print(
                        f"[dim]Auto-detected profiles [{','.join(profiles)}] for service [{service}][/dim]"
                    )
                    logger.debug("Auto-detected profiles for {}: {}", service, profiles)

            base_cmd, orphan_args = self._setup_compose_command(
                project, compose_file, profile_args, remove_orphans
            )

            # Execute the remove process
            if service:
                # Service-specific remove
                console.print(f"[green]Removing service: {service}[/green]")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(f"Removing service: {service}", total=None)
                    remove_cmd = f"{base_cmd} rm -s -f {service}"
                    if remove_orphans:
                        remove_cmd += f" {orphan_args}"

                    result = self._run_compose_command(
                        remove_cmd, f"remove service: {service}"
                    )
                    progress.remove_task(task)

                    if result.returncode == 0:
                        console.print(f"[green]Successfully removed {service}[/green]")
                        return True
                    else:
                        console.print(Panel(result.stderr, title="Error", style="red"))
                        return False

            else:
                # Project-wide remove
                console.print(f"[green]Removing project: {project}[/green]")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        f"Removing all services in {project}", total=None
                    )
                    remove_cmd = f"{base_cmd} rm -s -f"
                    if remove_orphans:
                        remove_cmd += f" {orphan_args}"

                    result = self._run_compose_command(remove_cmd, "remove services")
                    progress.remove_task(task)

                    if result.returncode == 0:
                        console.print(f"[green]Successfully removed {project}[/green]")
                        return True
                    else:
                        console.print(Panel(result.stderr, title="Error", style="red"))
                        return False

    def show_top(self, service: str):
        """Show running processes in container"""
        # Check if container is running
        check_cmd = [
            "podman",
            "ps",
            "--filter",
            f"name={service}",
            "--filter",
            "status=running",
            "--format",
            "{{.Names}}",
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(
                f"[red]Error checking container status: {result.stderr.strip()}[/red]"
            )
            return False

        if service not in result.stdout:
            console.print(f"[red]Container {service} is not running[/red]")
            return False

        console.print(Panel.fit(f"Processes in: {service}", style="bold blue"))

        top_cmd = ["podman", "top", service]
        console.print(f"  [white]exec: {' '.join(top_cmd)}[/white]")

        result = subprocess.run(top_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(result.stdout)
            return True
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(
                f"[red]Failed to show processes for {service}: {error_msg}[/red]"
            )
            return False

    def show_ports(self, service: str):
        """Show port mappings for container"""
        # Check if container exists
        check_cmd = [
            "podman",
            "ps",
            "-a",
            "--filter",
            f"name={service}",
            "--format",
            "{{.Names}} {{.Status}}",
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(
                f"[red]Error checking container status: {result.stderr.strip()}[/red]"
            )
            return False

        if not result.stdout.strip():
            console.print(f"[red]Container {service} not found[/red]")
            return False

        console.print(Panel.fit(f"Port mappings for: {service}", style="bold blue"))

        port_cmd = ["podman", "port", service]
        console.print(f"  [white]exec: {' '.join(port_cmd)}[/white]")

        result = subprocess.run(port_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            if result.stdout.strip():
                console.print(result.stdout)
            else:
                console.print(f"[dim]No port mappings found for {service}[/dim]")
            return True
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Failed to show ports for {service}: {error_msg}[/red]")
            return False

    def show_events(self, since: Optional[str] = None):
        """Stream real-time podman events"""
        console.print(Panel.fit("Podman Events Stream", style="bold blue"))

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

    def show_system_df(self):
        """Show system disk usage"""
        console.print(Panel.fit("Podman System Disk Usage", style="bold blue"))

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

    def remove_orphans(self, project: str):
        """Remove orphaned containers for a project"""
        projects = self._parse_compose_files()

        if project not in projects:
            console.print(f"[red]Project not found: {project}[/red]")
            console.print("\n[dim]Available projects:[/dim]")
            for project_name in projects.keys():
                console.print(f"  - {project_name}")
            return False

        compose_file = projects[project]["file"]
        base_cmd, orphan_args = self._setup_compose_command(
            project, compose_file, "", True
        )

        console.print(
            f"[green]Removing orphaned containers for project: {project}[/green]"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Removing orphans for {project}", total=None)
            remove_cmd = f"{base_cmd} down {orphan_args}"

            result = self._run_compose_command(
                remove_cmd, f"remove orphans for {project}"
            )
            progress.remove_task(task)

            if result.returncode == 0:
                console.print(
                    f"[green]Successfully removed orphans for {project}[/green]"
                )
                return True
            else:
                console.print(Panel(result.stderr, title="Error", style="red"))
                return False

    def pause(self, target: str):
        """Pause containers"""
        # Check if container exists and is running
        check_cmd = [
            "podman",
            "ps",
            "--filter",
            f"name={target}",
            "--filter",
            "status=running",
            "--format",
            "{{.Names}}",
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(
                f"[red]Error checking container status: {result.stderr.strip()}[/red]"
            )
            return False

        if target not in result.stdout:
            console.print(f"[red]Container {target} is not running[/red]")
            return False

        console.print(f"[green]Pausing container: {target}[/green]")
        pause_cmd = ["podman", "pause", target]
        console.print(f"  [white]exec: {' '.join(pause_cmd)}[/white]")

        result = subprocess.run(pause_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(f"[green]Successfully paused {target}[/green]")
            return True
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Failed to pause {target}: {error_msg}[/red]")
            return False

    def unpause(self, target: str):
        """Unpause containers"""
        # Check if container exists and is paused
        check_cmd = [
            "podman",
            "ps",
            "-a",
            "--filter",
            f"name={target}",
            "--format",
            "{{.Names}} {{.Status}}",
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(
                f"[red]Error checking container status: {result.stderr.strip()}[/red]"
            )
            return False

        container_info = result.stdout.strip()
        if not container_info:
            console.print(f"[red]Container {target} not found[/red]")
            return False

        if "paused" not in container_info.lower():
            console.print(f"[yellow]Container {target} is not paused[/yellow]")
            return True

        console.print(f"[green]Unpausing container: {target}[/green]")
        unpause_cmd = ["podman", "unpause", target]
        console.print(f"  [white]exec: {' '.join(unpause_cmd)}[/white]")

        result = subprocess.run(unpause_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(f"[green]Successfully unpaused {target}[/green]")
            return True
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Failed to unpause {target}: {error_msg}[/red]")
            return False

    def inspect(self, target: str, inspect_type: Optional[str] = None):
        """Inspect container or image"""
        console.print(Panel.fit(f"Inspecting: {target}", style="bold blue"))

        # If type is specified, use it directly
        if inspect_type:
            if inspect_type == "container":
                cmd = ["podman", "container", "inspect", target]
            elif inspect_type == "image":
                cmd = ["podman", "image", "inspect", target]
            else:
                console.print(f"[red]Invalid inspect type: {inspect_type}[/red]")
                return False
        else:
            # Try container first, then image
            container_cmd = ["podman", "container", "inspect", target]
            console.print(f"  [white]exec: {' '.join(container_cmd)}[/white]")
            result = subprocess.run(container_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                console.print(f"[green]Container inspection for: {target}[/green]")
                console.print(result.stdout)
                return True
            else:
                # Try as image
                console.print("[dim]Container not found, trying as image...[/dim]")
                cmd = ["podman", "image", "inspect", target]

        console.print(f"  [white]exec: {' '.join(cmd)}[/white]")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            if inspect_type == "image" or (not inspect_type and "image" in cmd):
                console.print(f"[green]Image inspection for: {target}[/green]")
            else:
                console.print(f"[green]Container inspection for: {target}[/green]")
            console.print(result.stdout)
            return True
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Failed to inspect {target}: {error_msg}[/red]")
            return False

    def up(self, target: str, detach: bool = True, build: bool = False):
        """Start services (create and start containers)"""
        with logger.contextualize(target=target, detach=detach, build=build):
            logger.debug("Starting up operation for target: {}", target)

            # Parse arguments to determine project/service
            projects = self._parse_compose_files()
            project = None
            service = None
            compose_file = None

            # Check if target is a project
            if target in projects:
                project = target
                compose_file = projects[target]["file"]
            else:
                # Check if target is a service
                found_file = self._find_service_project(target)
                if found_file:
                    service = target
                    for proj_name, proj_info in projects.items():
                        if proj_info["file"].name == found_file:
                            project = proj_name
                            compose_file = proj_info["file"]
                            break
                else:
                    logger.error("Could not find project or service: {}", target)
                    console.print(
                        f"[red]Could not find project or service: {target}[/red]"
                    )
                    console.print("\n[dim]Available projects:[/dim]")
                    for project_name in projects.keys():
                        console.print(f"  - {project_name}")
                    return False

            if not compose_file:
                logger.error("Could not determine compose file for: {}", target)
                return False

            # Setup compose command
            profile_args = ""
            if service and project:
                service_config = projects[project]["services"].get(service, {})
                profiles = service_config.get("profiles", [])
                if profiles:
                    profile_args = f"--profile {','.join(profiles)}"
                    console.print(
                        f"[dim]Auto-detected profiles [{','.join(profiles)}] for service [{service}][/dim]"
                    )
                    logger.debug("Auto-detected profiles for {}: {}", service, profiles)

            base_cmd, _ = self._setup_compose_command(
                project, compose_file, profile_args, False
            )

            # Execute the up process
            if service:
                console.print(f"[green]Starting service: {service}[/green]")
                up_cmd = f"{base_cmd} up"
                if detach:
                    up_cmd += " -d"
                if build:
                    up_cmd += " --build"
                up_cmd += f" {service}"
            else:
                console.print(f"[green]Starting project: {project}[/green]")
                up_cmd = f"{base_cmd} up"
                if detach:
                    up_cmd += " -d"
                if build:
                    up_cmd += " --build"

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task_desc = f"Starting {service if service else project}"
                task = progress.add_task(task_desc, total=None)
                result = self._run_compose_command(up_cmd, f"up {target}")
                progress.remove_task(task)

                if result.returncode == 0:
                    console.print(f"[green]Successfully started {target}[/green]")
                    return True
                else:
                    console.print(Panel(result.stderr, title="Error", style="red"))
                    return False

    def down(self, target: str, volumes: bool = False, remove_orphans: bool = True):
        """Stop and remove services"""
        with logger.contextualize(
            target=target, volumes=volumes, remove_orphans=remove_orphans
        ):
            logger.debug("Starting down operation for target: {}", target)

            # Parse arguments to determine project/service
            projects = self._parse_compose_files()
            project = None
            compose_file = None

            # Check if target is a project
            if target in projects:
                project = target
                compose_file = projects[target]["file"]
            else:
                console.print(f"[red]Could not find project: {target}[/red]")
                console.print("\n[dim]Available projects:[/dim]")
                for project_name in projects.keys():
                    console.print(f"  - {project_name}")
                return False

            if not compose_file:
                logger.error("Could not determine compose file for: {}", target)
                return False

            base_cmd, orphan_args = self._setup_compose_command(
                project, compose_file, "", remove_orphans
            )

            # Execute the down process
            console.print(f"[green]Stopping and removing project: {target}[/green]")
            down_cmd = f"{base_cmd} down"
            if volumes:
                down_cmd += " --volumes"
            if remove_orphans:
                down_cmd += f" {orphan_args}"

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task_desc = f"Stopping and removing {project}"
                task = progress.add_task(task_desc, total=None)
                result = self._run_compose_command(down_cmd, f"down {target}")
                progress.remove_task(task)

                if result.returncode == 0:
                    console.print(
                        f"[green]Successfully stopped and removed {target}[/green]"
                    )
                    return True
                else:
                    console.print(Panel(result.stderr, title="Error", style="red"))
                    return False

    def kill_container(self, target: str, signal: str = "SIGKILL"):
        """Kill containers with specific signal"""
        # Check if container exists
        check_cmd = [
            "podman",
            "ps",
            "--filter",
            f"name={target}",
            "--format",
            "{{.Names}} {{.Status}}",
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(
                f"[red]Error checking container status: {result.stderr.strip()}[/red]"
            )
            return False

        if not result.stdout.strip():
            console.print(f"[red]Container {target} not found[/red]")
            return False

        console.print(f"[green]Killing container {target} with signal {signal}[/green]")
        kill_cmd = ["podman", "kill", "-s", signal, target]
        console.print(f"  [white]exec: {' '.join(kill_cmd)}[/white]")

        result = subprocess.run(kill_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(f"[green]Successfully killed {target}[/green]")
            return True
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Failed to kill {target}: {error_msg}[/red]")
            return False

    def show_config(self, target: str):
        """Display compose configuration"""
        projects = self._parse_compose_files()
        project = None
        compose_file = None

        # Check if target is a project
        if target in projects:
            project = target
            compose_file = projects[target]["file"]
        else:
            console.print(f"[red]Could not find project: {target}[/red]")
            console.print("\n[dim]Available projects:[/dim]")
            for project_name in projects.keys():
                console.print(f"  - {project_name}")
            return False

        if not compose_file:
            console.print(f"[red]Could not determine compose file for: {target}[/red]")
            return False

        console.print(Panel.fit(f"Configuration for: {project}", style="bold blue"))

        base_cmd, _ = self._setup_compose_command(project, compose_file)
        config_cmd = f"{base_cmd} config"

        result = self._run_compose_command(config_cmd, f"show config for {target}")

        if result.returncode == 0:
            console.print(result.stdout)
            return True
        else:
            console.print(Panel(result.stderr, title="Error", style="red"))
            return False

    def start(self, target: str):
        """Start stopped containers"""
        with logger.contextualize(target=target):
            logger.debug("Starting start operation for target: {}", target)

            # Parse arguments to determine project/service
            projects = self._parse_compose_files()
            project = None
            service = None
            compose_file = None

            # Check if target is a project
            if target in projects:
                project = target
                compose_file = projects[target]["file"]
            else:
                # Check if target is a service
                found_file = self._find_service_project(target)
                if found_file:
                    service = target
                    for proj_name, proj_info in projects.items():
                        if proj_info["file"].name == found_file:
                            project = proj_name
                            compose_file = proj_info["file"]
                            break
                else:
                    logger.error("Could not find project or service: {}", target)
                    console.print(
                        f"[red]Could not find project or service: {target}[/red]"
                    )
                    console.print("\n[dim]Available projects:[/dim]")
                    for project_name in projects.keys():
                        console.print(f"  - {project_name}")
                    return False

            if not compose_file:
                logger.error("Could not determine compose file for: {}", target)
                return False

            # Setup compose command
            profile_args = ""
            if service and project:
                service_config = projects[project]["services"].get(service, {})
                profiles = service_config.get("profiles", [])
                if profiles:
                    profile_args = f"--profile {','.join(profiles)}"
                    console.print(
                        f"[dim]Auto-detected profiles [{','.join(profiles)}] for service [{service}][/dim]"
                    )
                    logger.debug("Auto-detected profiles for {}: {}", service, profiles)

            base_cmd, _ = self._setup_compose_command(
                project, compose_file, profile_args, False
            )

            # Execute the start process
            if service:
                console.print(f"[green]Starting service: {service}[/green]")
                start_cmd = f"{base_cmd} start {service}"
            else:
                console.print(f"[green]Starting project: {project}[/green]")
                start_cmd = f"{base_cmd} start"

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task_desc = f"Starting {service if service else project}"
                task = progress.add_task(task_desc, total=None)
                result = self._run_compose_command(start_cmd, f"start {target}")
                progress.remove_task(task)

                if result.returncode == 0:
                    console.print(f"[green]Successfully started {target}[/green]")
                    return True
                else:
                    console.print(Panel(result.stderr, title="Error", style="red"))
                    return False

    def push_images(self, target: str):
        """Push images to registry"""
        projects = self._parse_compose_files()
        project = None
        service = None
        compose_file = None

        # Check if target is a project
        if target in projects:
            project = target
            compose_file = projects[target]["file"]
        else:
            # Check if target is a service
            found_file = self._find_service_project(target)
            if found_file:
                service = target
                for proj_name, proj_info in projects.items():
                    if proj_info["file"].name == found_file:
                        project = proj_name
                        compose_file = proj_info["file"]
                        break
            else:
                console.print(f"[red]Could not find project or service: {target}[/red]")
                return False

        if not compose_file:
            console.print(f"[red]Could not determine compose file for: {target}[/red]")
            return False

        base_cmd, _ = self._setup_compose_command(project, compose_file)
        push_cmd = f"{base_cmd} push"

        if service:
            push_cmd += f" {service}"
            console.print(f"[green]Pushing images for service: {service}[/green]")
        else:
            console.print(f"[green]Pushing images for project: {project}[/green]")

        result = self._run_compose_command(push_cmd, f"push images for {target}")

        if result.returncode == 0:
            console.print(f"[green]Successfully pushed images for {target}[/green]")
            return True
        else:
            console.print(Panel(result.stderr, title="Error", style="red"))
            return False

    def run_command(
        self, service: str, command: str, user: Optional[str] = None, rm: bool = True
    ):
        """Run one-off command in new container"""
        # Find the service
        projects = self._parse_compose_files()
        found_file = self._find_service_project(service)
        if not found_file:
            console.print(f"[red]Service not found: {service}[/red]")
            return False

        project = None
        compose_file = None
        for proj_name, proj_info in projects.items():
            if proj_info["file"].name == found_file:
                project = proj_name
                compose_file = proj_info["file"]
                break

        if not compose_file:
            console.print(
                f"[red]Could not find compose file for service: {service}[/red]"
            )
            return False

        base_cmd, _ = self._setup_compose_command(project, compose_file)
        run_cmd = f"{base_cmd} run"

        if rm:
            run_cmd += " --rm"
        if user:
            run_cmd += f" --user {user}"

        run_cmd += f" {service} {command}"

        console.print(f"[green]Running command in {service}: {command}[/green]")
        console.print(f"  [white]exec: {run_cmd}[/white]")

        # Run interactively
        result = subprocess.run(run_cmd, shell=True, cwd=self.compose_dir, text=True)
        return result.returncode == 0

    def wait_containers(self, target: str):
        """Wait for containers to stop"""
        # Check if target is a container name or project
        projects = self._parse_compose_files()

        if target in projects:
            # Get all containers for the project
            project = target
            compose_file = projects[project]["file"]
            project_name = self._get_project_name(compose_file)

            # Get containers for this project
            check_cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                f"label=com.docker.compose.project={project_name}",
                "--format",
                "{{.Names}}",
            ]
            result = subprocess.run(check_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                console.print(
                    f"[red]Error getting containers for project: {result.stderr.strip()}[/red]"
                )
                return False

            containers = (
                result.stdout.strip().split("\n") if result.stdout.strip() else []
            )
        else:
            # Assume it's a container name
            containers = [target]

        if not containers or (len(containers) == 1 and not containers[0]):
            console.print(f"[yellow]No containers found for {target}[/yellow]")
            return True

        console.print(
            f"[green]Waiting for containers to stop: {', '.join(containers)}[/green]"
        )

        for container in containers:
            if not container:
                continue

            wait_cmd = ["podman", "wait", container]
            console.print(f"  [white]exec: {' '.join(wait_cmd)}[/white]")

            result = subprocess.run(wait_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                console.print(f"[green]Container {container} has stopped[/green]")
            else:
                error_msg = (
                    result.stderr.strip() if result.stderr.strip() else "Unknown error"
                )
                console.print(
                    f"[yellow]Warning waiting for {container}: {error_msg}[/yellow]"
                )

        console.print(f"[green]Finished waiting for {target}[/green]")
        return True

    def create_systemd_unit(self, action: str = "help"):
        """Create systemd unit files for compose stacks"""
        console.print(Panel.fit("Systemd Integration", style="bold blue"))

        if action == "help":
            console.print("[bold]Available systemd actions:[/bold]")
            console.print("  create-unit    Create systemd unit files")
            console.print("  register       Register current compose stack")
            console.print("")
            console.print("[bold]Usage:[/bold]")
            console.print("  pm systemd create-unit    # Create unit files")
            console.print("  pm systemd register       # Register stack")
            console.print("")
            console.print("[bold]After setup:[/bold]")
            console.print("  systemctl --user start podman-compose@<PROJECT>")
            console.print("  systemctl --user stop podman-compose@<PROJECT>")
            return True
        elif action == "create-unit":
            console.print("[green]Creating systemd unit files...[/green]")
            systemd_cmd = ["podman-compose", "systemd", "-a", "create-unit"]
        elif action == "register":
            console.print("[green]Registering compose stack...[/green]")
            systemd_cmd = ["podman-compose", "systemd", "-a", "register"]
        else:
            console.print(f"[red]Unknown systemd action: {action}[/red]")
            return False

        console.print(f"  [white]exec: {' '.join(systemd_cmd)}[/white]")

        result = subprocess.run(
            systemd_cmd, capture_output=True, text=True, cwd=self.compose_dir
        )

        if result.returncode == 0:
            console.print(f"[green]Systemd {action} completed successfully[/green]")
            if result.stdout.strip():
                console.print(result.stdout)
            return True
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Systemd {action} failed: {error_msg}[/red]")
            return False


def show_rich_help():
    """Show beautiful Rich-formatted help"""
    console.print()
    console.print(
        Panel.fit("Podman Container Manager", style="bold blue", padding=(1, 2))
    )

    console.print()
    console.print("[bold]USAGE:[/bold]")
    console.print(
        "  [cyan]podman-manager[/cyan] [dim][OPTIONS][/dim] [green]COMMAND[/green] [dim][ARGS][/dim]"
    )
    console.print(
        "  [cyan]pm[/cyan] [green]COMMAND[/green] [dim][ARGS][/dim]                    [dim]# Short alias[/dim]"
    )
    console.print(
        "  [cyan]pm-COMMAND[/cyan] [dim][ARGS][/dim]                [dim]# Direct command aliases[/dim]"
    )

    console.print()
    console.print("[bold]GLOBAL OPTIONS:[/bold]")
    options_table = Table(show_header=False, box=None, padding=(0, 2))
    options_table.add_column("Option", style="yellow", width=25)
    options_table.add_column("Description", style="white")
    options_table.add_row("--compose-dir PATH", "Compose files directory")
    options_table.add_row("-h, --help", "Show this help message")
    console.print(options_table)

    console.print()
    console.print("[bold]COMMANDS:[/bold]")

    # Create command categories
    categories = [
        (
            "Status & Information",
            [
                ("status", "Show projects and services tree", "pm status"),
                ("ps", "Container status table", "pm ps"),
                ("inspect TARGET", "Detailed container/image info", "pm inspect nginx"),
            ],
        ),
        (
            "Container Lifecycle",
            [
                ("reinit TARGET", "Remove and recreate containers", "pm-reinit ollama"),
                ("restart TARGET", "Quick restart containers", "pm-restart app"),
                ("stop TARGET", "Gracefully stop containers", "pm-stop vllm-models"),
                ("remove TARGET", "Remove containers", "pm-remove service"),
                ("pause TARGET", "Pause running containers", "pm pause app"),
                ("unpause TARGET", "Resume paused containers", "pm unpause app"),
            ],
        ),
        (
            "Build & Images",
            [
                ("build TARGET", "Build images", "pm-build --no-cache app"),
                ("pull TARGET", "Pull latest images", "pm-pull vllm-models"),
                ("images", "List all images", "pm images --all"),
            ],
        ),
        (
            "Monitoring & Debug",
            [
                ("logs SERVICE", "Analyze service logs", "pm-logs open-webui"),
                ("exec SERVICE CMD", "Execute in container", "pm-exec app bash"),
                ("stats", "Resource usage stats", "pm-stats --follow"),
                ("top SERVICE", "Show processes", "pm top nginx"),
                ("port SERVICE", "Show port mappings", "pm port web"),
                ("events", "Stream real-time events", "pm events --since 1h"),
            ],
        ),
        (
            "Resource Management",
            [
                ("volumes", "List volumes with usage", "pm volumes"),
                ("networks", "List networks", "pm networks"),
                ("prune", "Clean unused resources", "pm prune --all --volumes"),
                ("system-df", "Show disk usage", "pm system-df"),
                (
                    "remove-orphans PROJECT",
                    "Clean project orphans",
                    "pm remove-orphans app",
                ),
            ],
        ),
    ]

    for category, commands in categories:
        console.print(f"\n[bold cyan]{category}:[/bold cyan]")
        cmd_table = Table(show_header=False, box=None, padding=(0, 2))
        cmd_table.add_column("Command", style="green", width=25)
        cmd_table.add_column("Description", style="white", width=35)
        cmd_table.add_column("Example", style="dim", width=25)

        for cmd, desc, example in commands:
            cmd_table.add_row(cmd, desc, example)
        console.print(cmd_table)

    console.print()
    console.print("[bold]EXAMPLES:[/bold]")
    examples_table = Table(show_header=False, box=None, padding=(0, 1))
    examples_table.add_column("Command", style="green", width=35)
    examples_table.add_column("Description", style="white")

    examples = [
        ("pm status", "Show all projects and services"),
        ("pm-reinit --build app", "Rebuild and restart service"),
        ("pm-logs nginx", "Analyze nginx logs with health check"),
        ("pm-exec app 'ls -la'", "List files in container"),
        ("pm stats", "Show resource usage table"),
        ("pm prune --all --volumes", "Deep system cleanup"),
    ]

    for cmd, desc in examples:
        examples_table.add_row(cmd, desc)
    console.print(examples_table)

    console.print()
    console.print("[bold]ENVIRONMENT:[/bold]")
    console.print(
        "  [yellow]PODMAN_COMPOSE_DIR[/yellow]  Directory containing compose files"
    )
    console.print(
        "                        [dim](default: ~/srv/local-ai-packaged)[/dim]"
    )

    console.print()
    console.print("[dim]For detailed command help: [cyan]pm COMMAND --help[/cyan]")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Podman Container Manager with Rich UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )

    parser.add_argument("--compose-dir", help="Compose directory path")
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status and info commands
    subparsers.add_parser("status", help="Show project status")
    subparsers.add_parser("ps", help="Show container status")
    subparsers.add_parser("help", help="Show detailed help")

    # Container lifecycle commands
    reinit_parser = subparsers.add_parser("reinit", help="Reinitialize containers")
    reinit_parser.add_argument("target", nargs="?", help="Project or service name")
    reinit_parser.add_argument("--build", action="store_true", help="Rebuild images")
    reinit_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    reinit_parser.add_argument(
        "--remove-orphans", action="store_true", help="Remove orphaned containers"
    )

    restart_parser = subparsers.add_parser("restart", help="Restart services")
    restart_parser.add_argument("target", nargs="?", help="Project or service name")
    restart_parser.add_argument(
        "--remove-orphans", action="store_true", help="Remove orphaned containers"
    )

    stop_parser = subparsers.add_parser("stop", help="Stop services")
    stop_parser.add_argument("target", nargs="?", help="Project or service name")
    stop_parser.add_argument(
        "--remove-orphans", action="store_true", help="Remove orphaned containers"
    )

    remove_parser = subparsers.add_parser("remove", help="Remove services")
    remove_parser.add_argument("target", nargs="?", help="Project or service name")
    remove_parser.add_argument(
        "--remove-orphans", action="store_true", help="Remove orphaned containers"
    )

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Analyze service logs")
    logs_parser.add_argument("service", help="Service name")

    # Build & Images commands
    build_parser = subparsers.add_parser("build", help="Build images")
    build_parser.add_argument("target", nargs="?", help="Project or service name")
    build_parser.add_argument(
        "--no-cache", action="store_true", help="Build without cache"
    )

    pull_parser = subparsers.add_parser("pull", help="Pull latest images")
    pull_parser.add_argument("target", nargs="?", help="Project or service name")

    images_parser = subparsers.add_parser("images", help="List all images")
    images_parser.add_argument(
        "--all", action="store_true", help="Show all images including intermediates"
    )

    prune_parser = subparsers.add_parser("prune", help="Clean up unused resources")
    prune_parser.add_argument(
        "--all", action="store_true", help="Remove all unused images"
    )
    prune_parser.add_argument(
        "--volumes", action="store_true", help="Remove unused volumes"
    )

    # Monitoring & Debugging commands
    exec_parser = subparsers.add_parser("exec", help="Execute command in container")
    exec_parser.add_argument("service", help="Service name")
    exec_parser.add_argument("command", help="Command to execute")
    exec_parser.add_argument("--user", help="User to run as")

    stats_parser = subparsers.add_parser("stats", help="Show resource usage statistics")
    stats_parser.add_argument(
        "--follow", action="store_true", help="Follow stats output"
    )

    top_parser = subparsers.add_parser("top", help="Show running processes")
    top_parser.add_argument("service", help="Service name")

    port_parser = subparsers.add_parser("port", help="Show port mappings")
    port_parser.add_argument("service", help="Service name")

    events_parser = subparsers.add_parser("events", help="Stream real-time events")
    events_parser.add_argument("--since", help="Show events since timestamp")

    # Resource Management commands
    subparsers.add_parser("volumes", help="List volumes")
    subparsers.add_parser("networks", help="List networks")
    subparsers.add_parser("system-df", help="Show system disk usage")
    remove_orphans_parser = subparsers.add_parser(
        "remove-orphans", help="Remove orphaned containers"
    )
    remove_orphans_parser.add_argument("project", help="Project name")

    # Container lifecycle commands (pause/unpause)
    pause_parser = subparsers.add_parser("pause", help="Pause containers")
    pause_parser.add_argument("target", nargs="?", help="Project or service name")

    unpause_parser = subparsers.add_parser("unpause", help="Unpause containers")
    unpause_parser.add_argument("target", nargs="?", help="Project or service name")

    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect container or image")
    inspect_parser.add_argument("target", nargs="?", help="Container or image name")
    inspect_parser.add_argument(
        "--type", choices=["container", "image"], help="Type to inspect"
    )

    # New commands
    up_parser = subparsers.add_parser("up", help="Start services")
    up_parser.add_argument("target", nargs="?", help="Project or service name")
    up_parser.add_argument("--no-detach", action="store_true", help="Run in foreground")
    up_parser.add_argument(
        "--build", action="store_true", help="Build images before starting"
    )

    down_parser = subparsers.add_parser("down", help="Stop and remove services")
    down_parser.add_argument("target", nargs="?", help="Project name")
    down_parser.add_argument("--volumes", action="store_true", help="Remove volumes")
    down_parser.add_argument(
        "--no-remove-orphans",
        action="store_true",
        help="Don't remove orphaned containers",
    )

    kill_parser = subparsers.add_parser("kill", help="Kill containers with signal")
    kill_parser.add_argument("target", nargs="?", help="Container name")
    kill_parser.add_argument(
        "--signal", default="SIGKILL", help="Signal to send (default: SIGKILL)"
    )

    config_parser = subparsers.add_parser("config", help="Show compose configuration")
    config_parser.add_argument("target", nargs="?", help="Project name")

    # Additional commands
    start_parser = subparsers.add_parser("start", help="Start stopped containers")
    start_parser.add_argument("target", nargs="?", help="Project or service name")

    push_parser = subparsers.add_parser("push", help="Push images to registry")
    push_parser.add_argument("target", nargs="?", help="Project or service name")

    run_parser = subparsers.add_parser(
        "run", help="Run one-off command in new container"
    )
    run_parser.add_argument("service", nargs="?", help="Service name")
    run_parser.add_argument("cmd", nargs="?", help="Command to run")
    run_parser.add_argument("--user", help="User to run as")
    run_parser.add_argument(
        "--no-rm", action="store_true", help="Don't remove container after run"
    )

    wait_parser = subparsers.add_parser("wait", help="Wait for containers to stop")
    wait_parser.add_argument("target", nargs="?", help="Container name or project")

    systemd_parser = subparsers.add_parser("systemd", help="Create systemd unit files")
    systemd_parser.add_argument(
        "action",
        nargs="?",
        default="help",
        choices=["help", "create-unit", "register"],
        help="Systemd action to perform",
    )

    args = parser.parse_args()

    # Handle help with Rich formatting
    if args.help or (not args.command and len(sys.argv) == 1):
        show_rich_help()
        return

    # Set compose directory from environment variable if not provided
    compose_dir = args.compose_dir or os.environ.get("PODMAN_COMPOSE_DIR")

    try:
        manager = PodmanManager(compose_dir)

        # Status and info commands
        if args.command == "status":
            manager.show_status()
        elif args.command == "ps":
            manager.show_ps()
        elif args.command == "help":
            manager.show_help()
        elif args.command == "reinit":
            if not args.target:
                manager.show_available_targets("reinit")
                sys.exit(1)
            success = manager.reinit(
                args.target,
                build=args.build,
                dry_run=args.dry_run,
                remove_orphans=args.remove_orphans,
            )
            sys.exit(0 if success else 1)
        elif args.command == "logs":
            success = manager.logs(args.service)
            sys.exit(0 if success else 1)
        elif args.command == "restart":
            if not args.target:
                manager.show_available_targets("restart")
                sys.exit(1)
            success = manager.restart(args.target, remove_orphans=args.remove_orphans)
            sys.exit(0 if success else 1)
        elif args.command == "stop":
            if not args.target:
                manager.show_available_targets("stop")
                sys.exit(1)
            success = manager.stop(args.target, remove_orphans=args.remove_orphans)
            sys.exit(0 if success else 1)
        elif args.command == "remove":
            if not args.target:
                manager.show_available_targets("remove")
                sys.exit(1)
            success = manager.remove(args.target, remove_orphans=args.remove_orphans)
            sys.exit(0 if success else 1)
        elif args.command == "images":
            success = manager.show_images(show_all=args.all)
            sys.exit(0 if success else 1)
        elif args.command == "build":
            if not args.target:
                manager.show_available_targets("build")
                sys.exit(1)
            success = manager.build(args.target, no_cache=args.no_cache)
            sys.exit(0 if success else 1)
        elif args.command == "pull":
            if not args.target:
                manager.show_available_targets("pull")
                sys.exit(1)
            success = manager.pull(args.target)
            sys.exit(0 if success else 1)
        elif args.command == "prune":
            success = manager.prune(all_images=args.all, volumes=args.volumes)
            sys.exit(0 if success else 1)
        elif args.command == "exec":
            success = manager.exec_command(args.service, args.command, user=args.user)
            sys.exit(0 if success else 1)
        elif args.command == "stats":
            success = manager.show_stats(follow=args.follow)
            sys.exit(0 if success else 1)
        elif args.command == "top":
            success = manager.show_top(args.service)
            sys.exit(0 if success else 1)
        elif args.command == "port":
            success = manager.show_ports(args.service)
            sys.exit(0 if success else 1)
        elif args.command == "events":
            success = manager.show_events(since=args.since)
            sys.exit(0 if success else 1)
        elif args.command == "volumes":
            success = manager.show_volumes()
            sys.exit(0 if success else 1)
        elif args.command == "networks":
            success = manager.show_networks()
            sys.exit(0 if success else 1)
        elif args.command == "system-df":
            success = manager.show_system_df()
            sys.exit(0 if success else 1)
        elif args.command == "remove-orphans":
            success = manager.remove_orphans(args.project)
            sys.exit(0 if success else 1)
        elif args.command == "pause":
            if not args.target:
                manager.show_available_targets("pause")
                sys.exit(1)
            success = manager.pause(args.target)
            sys.exit(0 if success else 1)
        elif args.command == "unpause":
            if not args.target:
                manager.show_available_targets("unpause")
                sys.exit(1)
            success = manager.unpause(args.target)
            sys.exit(0 if success else 1)
        elif args.command == "inspect":
            if not args.target:
                manager.show_available_targets("inspect")
                sys.exit(1)
            success = manager.inspect(args.target, inspect_type=args.type)
            sys.exit(0 if success else 1)
        elif args.command == "up":
            if not args.target:
                manager.show_available_targets("up")
                sys.exit(1)
            success = manager.up(
                args.target, detach=not args.no_detach, build=args.build
            )
            sys.exit(0 if success else 1)
        elif args.command == "down":
            if not args.target:
                manager.show_available_targets("down")
                sys.exit(1)
            success = manager.down(
                args.target,
                volumes=args.volumes,
                remove_orphans=not args.no_remove_orphans,
            )
            sys.exit(0 if success else 1)
        elif args.command == "kill":
            if not args.target:
                manager.show_available_targets("kill")
                sys.exit(1)
            success = manager.kill_container(args.target, signal=args.signal)
            sys.exit(0 if success else 1)
        elif args.command == "config":
            if not args.target:
                manager.show_available_targets("config")
                sys.exit(1)
            success = manager.show_config(args.target)
            sys.exit(0 if success else 1)
        elif args.command == "start":
            if not args.target:
                manager.show_available_targets("start")
                sys.exit(1)
            success = manager.start(args.target)
            sys.exit(0 if success else 1)
        elif args.command == "push":
            if not args.target:
                manager.show_available_targets("push")
                sys.exit(1)
            success = manager.push_images(args.target)
            sys.exit(0 if success else 1)
        elif args.command == "run":
            if not args.service or not args.cmd:
                if not args.service:
                    manager.show_available_targets("run")
                    console.print(
                        "\n[yellow]Usage: pm run <service> <command>[/yellow]"
                    )
                else:
                    console.print("[yellow]No command specified for 'run'.[/yellow]")
                    console.print("[bold]Usage:[/bold] pm run <service> <command>")
                    console.print("[bold]Example:[/bold] pm run web-service bash")
                sys.exit(1)
            success = manager.run_command(
                args.service, args.cmd, user=args.user, rm=not args.no_rm
            )
            sys.exit(0 if success else 1)
        elif args.command == "wait":
            if not args.target:
                manager.show_available_targets("wait")
                sys.exit(1)
            success = manager.wait_containers(args.target)
            sys.exit(0 if success else 1)
        elif args.command == "systemd":
            success = manager.create_systemd_unit(args.action)
            sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception:
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
