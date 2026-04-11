"""Intelligent target type detection for pm facade - Quadlet-only version."""

from pathlib import Path
from typing import Optional, Tuple

from loguru import logger

from utils.secure_subprocess import systemctl_user


class ProjectTypeDetector:
    """Automatically detect quadlet services and targets"""

    def __init__(self, compose_dir: Optional[Path] = None):
        # Keep compose_dir parameter for backward compatibility but ignore it
        _ = compose_dir  # Explicitly mark as unused for vulture

        # Known quadlet services
        self.quadlet_services = {
            # vLLM services
            "vllm-qwen25": "vllm-qwen25-coder-32b-instruct-awq.service",
            "abacus-proxy": "abacus-proxy.service",
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
        Detect project type for a given target (quadlet-only).

        Returns:
            Tuple[str, str]: (project_type, reason)
            project_type: 'quadlet' or 'unknown'
            reason: explanation of detection logic
        """
        logger.debug("Detecting target type for target: {}", target)

        # 0. Check if it's a numeric selection - always use quadlet mode for these
        if target.isdigit():
            return (
                "quadlet",
                f"Numeric selection '{target}' - using quadlet mode for fuzzy matching",
            )

        # 1. Check if it's a stack target
        if target.endswith("-stack"):
            stack_name = target[:-6]  # Remove "-stack" suffix
            # Check if the stack has quadlet services
            has_quadlet_services = any(
                service.startswith(f"{stack_name}-")
                for service in self.quadlet_services.keys()
            )
            if has_quadlet_services or stack_name in ["vllm", "taskflow"]:
                return (
                    "quadlet",
                    f"Stack target with quadlet services: {target}",
                )

        # 2. Check if it's a known quadlet service
        if target in self.quadlet_services or target in self.stack_aliases:
            return "quadlet", f"Known quadlet service: {target}"

        # 2.1. Check if it's a partial match for quadlet services (fuzzy matching)
        quadlet_matches = [
            svc for svc in self.quadlet_services.keys() if target.lower() in svc.lower()
        ]
        if quadlet_matches:
            return (
                "quadlet",
                f"Partial match for quadlet services: {target} matches {quadlet_matches}",
            )

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

        # 5. Default to quadlet mode
        return "quadlet", "Defaulting to quadlet mode"

    def _systemd_unit_exists(self, unit_name: str) -> bool:
        """Check if a systemd user unit exists and is loaded"""
        try:
            result = systemctl_user(
                ["show", unit_name, "--property=LoadState"], timeout=5
            )

            if result.returncode == 0:
                # Check if unit is loaded (exists)
                return "LoadState=loaded" in result.stdout
            return False
        except Exception as e:
            logger.debug("Error checking systemd unit {}: {}", unit_name, e)
            return False

    def get_intelligent_mode(
        self, target: Optional[str] = None, user_mode: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Get the intelligent mode selection (quadlet-only).

        Args:
            target: The target service/project name
            user_mode: User-specified mode (ignored, always returns quadlet)

        Returns:
            Tuple[str, str]: (mode, reason)
        """
        # Always return quadlet mode
        if user_mode and user_mode != "quadlet":
            logger.warning(
                "Ignoring user mode '{}' - only quadlet mode supported", user_mode
            )

        # If no target specified, use quadlet
        if not target:
            return "quadlet", "No target specified, using quadlet mode"

        # Detect based on target (will always be quadlet or unknown)
        detected_mode, reason = self.detect_project_type(target)
        if detected_mode == "unknown":
            # Force to quadlet even if unknown
            return "quadlet", f"Unknown target, defaulting to quadlet mode: {reason}"

        return detected_mode, f"Auto-detected: {reason}"

    def suggest_alternative_mode(self, target: str, current_mode: str) -> Optional[str]:
        """
        Suggest alternative mode if current mode fails (quadlet-only).

        Since we only support quadlet mode, this always returns None.
        """
        _ = target, current_mode  # Explicitly mark as unused for vulture
        return None

    def list_available_targets(self) -> dict:
        """
        List all available targets by type (quadlet-only).

        Returns:
            Dict with 'quadlet' key containing list of targets
        """
        targets = {"quadlet": []}

        # Add known quadlet services
        targets["quadlet"].extend(self.quadlet_services.keys())

        # Scan for additional systemd services
        try:
            result = systemctl_user(
                [
                    "list-units",
                    "--type=service",
                    "--state=loaded",
                    "--no-legend",
                    "--plain",
                ],
                timeout=10,
            )

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

        # Remove duplicates and sort
        targets["quadlet"] = sorted(set(targets["quadlet"]))

        return targets
