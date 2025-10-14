"""Intelligent project type detection for pm facade."""

import subprocess
from pathlib import Path
from typing import Optional, Tuple

from loguru import logger


class ProjectTypeDetector:
    """Automatically detect if a target is a podman compose project or quadlet service"""

    def __init__(self, compose_dir: Optional[Path] = None):
        self.compose_dir = (
            Path(compose_dir)
            if compose_dir
            else Path.home() / "srv" / "local-ai-packaged"
        )

        # Known quadlet services
        self.quadlet_services = {
            # vLLM services
            "vllm-qwen25": "vllm-qwen25-coder-32b-instruct-awq.service",
            "vllm-proxy": "vllm-proxy.service",
            "vllm-delegator": "vllm-delegator-mcp.service",
            "vllm-stack": "vllm-stack.target",
            # Taskflow services
            "taskflow-frontend": "taskflow-frontend.service",
            "taskflow-backend": "taskflow-backend.service",
        }

        # Stack aliases
        self.stack_aliases = {"stack", "vllm-stack"}

    def detect_project_type(self, target: str) -> Tuple[str, str]:
        """
        Detect project type for a given target.

        Returns:
            Tuple[str, str]: (project_type, reason)
            project_type: 'quadlet', 'compose', or 'unknown'
            reason: explanation of detection logic
        """
        logger.debug("Detecting project type for target: {}", target)

        # 1. Check if it's a stack target
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            # Check if the project has quadlet services
            has_quadlet_services = any(
                service.startswith(f"{project_name}-")
                for service in self.quadlet_services.keys()
            )
            if has_quadlet_services or project_name in ["vllm", "taskflow"]:
                return (
                    "quadlet",
                    f"Stack target for project with quadlet services: {target}",
                )

        # 2. Check if it's a known quadlet service
        if target in self.quadlet_services or target in self.stack_aliases:
            return "quadlet", f"Known quadlet service: {target}"

        # 3. Check if it's a systemd service/target by name pattern
        if target.endswith(".service") or target.endswith(".target"):
            if self._systemd_unit_exists(target):
                return "quadlet", f"Systemd unit exists: {target}"
            else:
                return "unknown", f"Systemd unit not found: {target}"

        # 4. Check if systemd service exists for target
        potential_service = f"{target}.service"
        if self._systemd_unit_exists(potential_service):
            return "quadlet", f"Found systemd service: {potential_service}"

        # 5. Check if it's in any compose file
        compose_project = self._find_in_compose_files(target)
        if compose_project:
            return "compose", f"Found in compose file: {compose_project}"

        # 6. Default fallback logic
        # If compose directory exists and has files, assume compose
        if self.compose_dir.exists() and list(
            self.compose_dir.glob("podman-compose*.yml")
        ):
            return "compose", "Defaulting to compose mode (compose files available)"

        # 7. Final fallback to quadlet (current default)
        return "quadlet", "Defaulting to quadlet mode"

    def _systemd_unit_exists(self, unit_name: str) -> bool:
        """Check if a systemd user unit exists and is loaded"""
        try:
            cmd = ["systemctl", "--user", "show", unit_name, "--property=LoadState"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                # Check if unit is loaded (exists)
                return "LoadState=loaded" in result.stdout
            return False
        except (subprocess.TimeoutExpired, Exception) as e:
            logger.debug("Error checking systemd unit {}: {}", unit_name, e)
            return False

    def _find_in_compose_files(self, service_name: str) -> Optional[str]:
        """Find if service exists in any compose file"""
        if not self.compose_dir.exists():
            return None

        try:
            import yaml

            for compose_file in self.compose_dir.glob("podman-compose*.yml"):
                try:
                    with open(compose_file, "r") as f:
                        compose_data = yaml.safe_load(f)

                    if compose_data and "services" in compose_data:
                        if service_name in compose_data["services"]:
                            return compose_file.name
                except (OSError, yaml.YAMLError) as e:
                    logger.debug("Error reading compose file {}: {}", compose_file, e)
                    continue

            return None
        except ImportError:
            logger.warning("PyYAML not available, cannot check compose files")
            return None

    def get_intelligent_mode(
        self, target: Optional[str] = None, user_mode: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Get the intelligent mode selection.

        Args:
            target: The target service/project name
            user_mode: User-specified mode (overrides detection)

        Returns:
            Tuple[str, str]: (mode, reason)
        """
        # User override takes precedence
        if user_mode:
            return user_mode, f"User specified mode: {user_mode}"

        # If no target specified, use default
        if not target:
            return "quadlet", "No target specified, using default mode"

        # Detect based on target
        detected_mode, reason = self.detect_project_type(target)
        return detected_mode, f"Auto-detected: {reason}"

    def suggest_alternative_mode(self, target: str, current_mode: str) -> Optional[str]:
        """
        Suggest alternative mode if current mode fails.

        Args:
            target: The target that failed
            current_mode: The mode that was tried

        Returns:
            Alternative mode to try, or None
        """
        if current_mode == "quadlet":
            # Try compose if quadlet fails
            if self._find_in_compose_files(target):
                return "compose"
        elif current_mode == "compose":
            # Try quadlet if compose fails
            if target in self.quadlet_services or self._systemd_unit_exists(
                f"{target}.service"
            ):
                return "quadlet"

        return None

    def list_available_targets(self) -> dict:
        """
        List all available targets by type.

        Returns:
            Dict with 'quadlet' and 'compose' keys containing lists of targets
        """
        targets = {"quadlet": [], "compose": []}

        # Add known quadlet services
        targets["quadlet"].extend(self.quadlet_services.keys())

        # Scan for additional systemd services
        try:
            cmd = [
                "systemctl",
                "--user",
                "list-units",
                "--type=service",
                "--state=loaded",
                "--no-legend",
                "--plain",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        service_name = line.split()[0]
                        if service_name not in [
                            v for v in self.quadlet_services.values()
                        ]:
                            # Add service without .service suffix
                            clean_name = service_name.replace(".service", "")
                            if clean_name not in targets["quadlet"]:
                                targets["quadlet"].append(clean_name)
        except Exception as e:
            logger.debug("Error listing systemd services: {}", e)

        # Scan compose files
        if self.compose_dir.exists():
            try:
                import yaml

                for compose_file in self.compose_dir.glob("podman-compose*.yml"):
                    try:
                        with open(compose_file, "r") as f:
                            compose_data = yaml.safe_load(f)

                        if compose_data and "services" in compose_data:
                            targets["compose"].extend(compose_data["services"].keys())
                    except Exception as e:
                        logger.debug(
                            "Error reading compose file {}: {}", compose_file, e
                        )
            except ImportError:
                logger.debug("PyYAML not available for compose file scanning")

        # Remove duplicates and sort
        targets["quadlet"] = sorted(set(targets["quadlet"]))
        targets["compose"] = sorted(set(targets["compose"]))

        return targets
