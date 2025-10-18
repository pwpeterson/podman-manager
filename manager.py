"""Core PodmanManager class with main functionality."""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from loguru import logger

from config import console

# Progress imports removed - not used in this module


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
        cmd = ["podman", "compose", "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("'podman compose' is not available!")
            console.print(
                "[dim]Make sure you have podman compose plugin installed[/dim]"
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
        cmd = ["which", command]
        result = subprocess.run(cmd, capture_output=True)
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
        # Check if it's a numeric selection (e.g., "1", "2", etc.)
        if service_name.isdigit():
            return self._handle_numeric_selection(int(service_name))

        projects = self._parse_compose_files()

        # First try exact match
        for project_name, project_info in projects.items():
            if service_name in project_info["services"]:
                logger.debug(
                    "Found service '{}' in project '{}'", service_name, project_name
                )
                return project_info["file"].name

        # Try fuzzy matching
        fuzzy_result = self._fuzzy_match_service(service_name)
        if fuzzy_result:
            return fuzzy_result

        logger.debug("Service '{}' not found in any project", service_name)
        return None

    def _handle_numeric_selection(self, selection: int) -> Optional[str]:
        """Handle numeric service selection from previous fuzzy match results"""
        console.print(
            f"[red]Numeric selection not supported in compose mode. Use 'pm --mode quadlet log-anal {selection}' instead.[/red]"
        )
        return None

    def _fuzzy_match_service(self, partial_name: str) -> Optional[str]:
        """Find service using fuzzy matching for partial names"""
        from rich.table import Table

        projects = self._parse_compose_files()

        # Get all available service names from all projects
        all_services = []
        service_to_project = {}

        for project_name, project_info in projects.items():
            for service_name in project_info["services"].keys():
                all_services.append(service_name)
                service_to_project[service_name] = project_info["file"].name

        if not all_services:
            return None

        # Find exact matches first
        exact_matches = [svc for svc in all_services if svc == partial_name]
        if len(exact_matches) == 1:
            return service_to_project[exact_matches[0]]

        # Find partial matches (case-insensitive)
        partial_matches = [
            svc for svc in all_services if partial_name.lower() in svc.lower()
        ]

        # If no partial matches, try prefix matching
        if not partial_matches:
            partial_matches = [
                svc
                for svc in all_services
                if svc.lower().startswith(partial_name.lower())
            ]

        # If still no matches, try fuzzy matching with edit distance
        if not partial_matches:

            def levenshtein_distance(s1: str, s2: str) -> int:
                """Calculate Levenshtein distance between two strings"""
                if len(s1) < len(s2):
                    return levenshtein_distance(s2, s1)
                if len(s2) == 0:
                    return len(s1)

                previous_row = list(range(len(s2) + 1))
                for i, c1 in enumerate(s1):
                    current_row = [i + 1]
                    for j, c2 in enumerate(s2):
                        insertions = previous_row[j + 1] + 1
                        deletions = current_row[j] + 1
                        substitutions = previous_row[j] + (c1 != c2)
                        current_row.append(min(insertions, deletions, substitutions))
                    previous_row = current_row
                return previous_row[-1]

            # Find services with small edit distance (max 2 for reasonable matches)
            fuzzy_matches = []
            for svc in all_services:
                distance = levenshtein_distance(partial_name.lower(), svc.lower())
                if (
                    distance <= 2 and len(partial_name) >= 3
                ):  # Only for reasonable length inputs
                    fuzzy_matches.append((svc, distance))

            # Sort by distance and take best matches
            fuzzy_matches.sort(key=lambda x: x[1])
            partial_matches = [match[0] for match in fuzzy_matches[:5]]  # Top 5 matches

        if len(partial_matches) == 1:
            # Single match found
            matched_service = partial_matches[0]
            console.print(f"[dim]Matched '{partial_name}' to '{matched_service}'[/dim]")
            return service_to_project[matched_service]
        elif len(partial_matches) > 1:
            # Multiple matches - show selection menu
            console.print(f"[yellow]Multiple services match '{partial_name}':[/yellow]")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("#", style="cyan", width=3)
            table.add_column("Service", style="green")
            table.add_column("Project", style="dim")

            for i, service in enumerate(partial_matches, 1):
                project_file = service_to_project[service]
                # Extract project name from file name
                if project_file == "podman-compose.yml":
                    project_name = "default"
                else:
                    project_name = project_file.replace("podman-compose-", "").replace(
                        ".yml", ""
                    )
                table.add_row(str(i), service, project_name)

            console.print(table)
            console.print(
                "[cyan]Please specify the full service name or use the number prefix:[/cyan]"
            )

            # Show example commands
            for i, service in enumerate(partial_matches, 1):
                console.print(f"  [dim]{i}.[/dim] [cyan]pm logs {service}[/cyan]")

            return None  # Let user choose

        return None  # No matches found

    def get_matched_service_name(self, target: str) -> Optional[str]:
        """Get the actual service name that was matched (for use after fuzzy matching)"""
        projects = self._parse_compose_files()

        # First try exact match
        for project_name, project_info in projects.items():
            if target in project_info["services"]:
                return target

        # Try fuzzy matching to find the actual matched service
        all_services = []
        for project_name, project_info in projects.items():
            all_services.extend(project_info["services"].keys())

        # Find partial matches (case-insensitive)
        partial_matches = [svc for svc in all_services if target.lower() in svc.lower()]

        # If no partial matches, try prefix matching
        if not partial_matches:
            partial_matches = [
                svc for svc in all_services if svc.lower().startswith(target.lower())
            ]

        # Return the first match if there's exactly one
        if len(partial_matches) == 1:
            return partial_matches[0]

        # If multiple matches or no matches, return the original target
        return target

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
        console.print(f"  [cyan]exec: {cmd}[/cyan]")

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
            console.print(f"  [cyan]exec: {' '.join(dep_cmd)}[/cyan]")
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

    def refresh_service_discovery(self) -> None:
        """Refresh service discovery cache - only available in quadlet mode"""
        console.print(
            "[red]Refresh service discovery only available in quadlet mode[/red]"
        )
