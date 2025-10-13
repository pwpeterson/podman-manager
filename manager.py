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
