"""Unified service discovery utility for quadlet services and stacks."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger


class ServiceDiscovery:
    """Centralized service and stack discovery for quadlet containers."""

    def __init__(self):
        # Primary source directory
        self.quadlets_source_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")
        # Installed directory
        self.quadlets_dir = Path.home() / ".config" / "containers" / "systemd"

        # Discovered data
        self.quadlet_services: Dict[str, str] = {}  # service_name -> full_service_name
        self.stack_services: Dict[str, List[str]] = {}  # stack_name -> [service_names]
        self.service_status: Dict[str, Dict[str, bool]] = (
            {}
        )  # service_name -> {installed, source}

        # Perform discovery
        self._discover_all_services()

    def _discover_all_services(self) -> None:
        """Auto-discover all quadlet services from both source and installed directories."""
        # Clear existing data
        self.quadlet_services.clear()
        self.stack_services.clear()
        self.service_status.clear()

        # Scan source directory first
        if self.quadlets_source_dir.exists():
            logger.debug(
                "Discovering services from source: {}", self.quadlets_source_dir
            )
            self._scan_source_directory()
        else:
            logger.warning("Source directory not found: {}", self.quadlets_source_dir)

        # Then scan installed directory
        if self.quadlets_dir.exists():
            logger.debug("Checking installed services: {}", self.quadlets_dir)
            self._scan_installed_directory()
        else:
            logger.warning("Installed directory not found: {}", self.quadlets_dir)

        logger.info(
            "Discovered {} services across {} stacks",
            len(self.quadlet_services),
            len(self.stack_services),
        )

    def _scan_source_directory(self) -> None:
        """Scan source directory for available stacks and services."""
        for stack_dir in self.quadlets_source_dir.iterdir():
            if not stack_dir.is_dir() or not stack_dir.name.endswith("-stack"):
                continue

            stack_name = stack_dir.name
            stack_services = []

            logger.debug("Scanning source stack: {}", stack_dir)

            # Find .container and .target files
            for service_file in stack_dir.glob("*.container"):
                service_name = service_file.stem
                full_service_name = f"{service_name}.service"

                self.quadlet_services[service_name] = full_service_name
                stack_services.append(service_name)
                self.service_status[service_name] = {"installed": False, "source": True}

                logger.debug(
                    "Found source service: {} -> {}", service_name, full_service_name
                )

            for target_file in stack_dir.glob("*.target"):
                target_name = target_file.stem
                full_target_name = f"{target_name}.target"

                self.quadlet_services[target_name] = full_target_name
                stack_services.append(target_name)
                self.service_status[target_name] = {"installed": False, "source": True}

                logger.debug(
                    "Found source target: {} -> {}", target_name, full_target_name
                )

            if stack_services:
                self.stack_services[stack_name] = stack_services
                logger.debug("Source stack {} contains: {}", stack_name, stack_services)

    def _scan_installed_directory(self) -> None:
        """Scan installed directory and mark services as installed."""
        standalone_services = []

        # Scan for .container files
        for service_file in self.quadlets_dir.glob("*.container"):
            service_name = service_file.stem

            if service_name in self.service_status:
                self.service_status[service_name]["installed"] = True
                logger.debug("Marked as installed: {}", service_name)
            else:
                # Standalone service only in systemd
                full_service_name = f"{service_name}.service"
                self.quadlet_services[service_name] = full_service_name
                self.service_status[service_name] = {"installed": True, "source": False}
                standalone_services.append(service_name)
                logger.debug("Found standalone installed service: {}", service_name)

        # Scan for .target files
        for target_file in self.quadlets_dir.glob("*.target"):
            target_name = target_file.stem

            if target_name in self.service_status:
                self.service_status[target_name]["installed"] = True
                logger.debug("Marked target as installed: {}", target_name)
            else:
                # Standalone target only in systemd
                full_target_name = f"{target_name}.target"
                self.quadlet_services[target_name] = full_target_name
                self.service_status[target_name] = {"installed": True, "source": False}
                standalone_services.append(target_name)
                logger.debug("Found standalone installed target: {}", target_name)

        # Add standalone services to special group
        if standalone_services:
            self.stack_services["standalone"] = standalone_services
            logger.debug("Created standalone group: {}", standalone_services)

    def refresh_discovery(self) -> None:
        """Re-discover all services and stacks."""
        logger.debug("Refreshing service discovery")
        self._discover_all_services()

    def get_available_stacks(self) -> List[str]:
        """Get list of available stack names."""
        stacks = []

        # From source directory
        if self.quadlets_source_dir.exists():
            for item in self.quadlets_source_dir.iterdir():
                if (
                    item.is_dir()
                    and item.name not in ["scripts", "docs"]
                    and item.name.endswith("-stack")
                    and self._has_quadlet_files(item)
                ):
                    stacks.append(item.name)

        return sorted(list(set(stacks)))

    def _has_quadlet_files(self, directory: Path) -> bool:
        """Check if directory contains container files."""
        for file in directory.glob("*.container"):
            if not file.name.endswith(".disabled"):
                return True
        return False

    def get_stack_files(self, stack_name: str) -> List[str]:
        """Get quadlet files for a stack."""
        stack_dir = self.quadlets_source_dir / stack_name
        if not stack_dir.exists():
            return []

        files = []
        for file in stack_dir.glob("*.container"):
            if not file.name.endswith(".disabled"):
                files.append(file.name)
        return sorted(files)

    def get_service_names(self, stack_name: str) -> List[str]:
        """Get service names from quadlet files."""
        stack_dir = self.quadlets_source_dir / stack_name
        if not stack_dir.exists():
            return []

        services = []
        for file in stack_dir.glob("*.container"):
            if not file.name.endswith(".disabled"):
                services.append(file.stem)
        return sorted(services)

    def find_service_in_stacks(self, service_name: str) -> Optional[Tuple[str, str]]:
        """Find which stack contains a specific service."""
        available_stacks = self.get_available_stacks()
        for stack in available_stacks:
            stack_dir = self.quadlets_source_dir / stack
            container_file = f"{service_name}.container"
            container_path = stack_dir / container_file

            if container_path.exists() and not container_file.endswith(".disabled"):
                return (stack, container_file)
        return None

    def get_service_display_info(self, service_name: str) -> str:
        """Get display information for a service."""
        info_parts = []

        # Check installation status
        if service_name in self.service_status:
            status = self.service_status[service_name]
            if status.get("installed", False):
                info_parts.append("[green](installed)[/green]")
            elif status.get("source", False):
                info_parts.append("[bright_yellow](available)[/bright_yellow]")
        else:
            # Check if service file exists in systemd directory
            container_file = self.quadlets_dir / f"{service_name}.container"
            target_file = self.quadlets_dir / f"{service_name}.target"
            if container_file.exists() or target_file.exists():
                info_parts.append("[green](installed)[/green]")

        # Check if it's part of a stack
        for stack_name, stack_services in self.stack_services.items():
            if service_name in stack_services:
                info_parts.append(f"[dim](in {stack_name})[/dim]")
                break

        return " " + " ".join(info_parts) if info_parts else ""

    def search_systemd_directory(self, partial_name: str) -> List[str]:
        """Search systemd directory for matching files."""
        matches = []

        if not self.quadlets_dir.exists():
            return matches

        try:
            # Search for .container files
            for container_file in self.quadlets_dir.glob("*.container"):
                service_name = container_file.stem
                if partial_name.lower() in service_name.lower():
                    if service_name not in self.quadlet_services:
                        matches.append(service_name)
                        self.quadlet_services[service_name] = f"{service_name}.service"

            # Search for .target files
            for target_file in self.quadlets_dir.glob("*.target"):
                target_name = target_file.stem
                if partial_name.lower() in target_name.lower():
                    if target_name not in self.quadlet_services:
                        matches.append(target_name)
                        self.quadlet_services[target_name] = f"{target_name}.target"

        except Exception as e:
            logger.debug("Error searching systemd directory: {}", e)

        return matches

    def resolve_from_directory_structure(self, partial_name: str) -> Optional[str]:
        """Resolve service/stack names using directory structure."""
        if not self.quadlets_source_dir.exists():
            return None

        try:
            stack_dirs = [d for d in self.quadlets_source_dir.iterdir() if d.is_dir()]

            # Check for exact stack name match
            for stack_dir in stack_dirs:
                if partial_name == stack_dir.name:
                    return f"STACK:{stack_dir.name}"

            # Check if partial_name matches stack prefix
            for stack_dir in stack_dirs:
                stack_name = stack_dir.name
                if stack_name.startswith(f"{partial_name}-") or stack_name.startswith(
                    partial_name
                ):
                    return f"STACK:{stack_name}"

            # Look for service files in all stack directories
            all_services = {}
            for stack_dir in stack_dirs:
                try:
                    service_files = []
                    service_files.extend(stack_dir.glob("*.container"))
                    service_files.extend(stack_dir.glob("*.service"))
                    service_files.extend(stack_dir.glob("Dockerfile.*"))

                    for service_file in service_files:
                        if service_file.name.startswith("Dockerfile."):
                            service_name = service_file.name.replace("Dockerfile.", "")
                        else:
                            service_name = service_file.stem
                        all_services[service_name] = stack_dir.name
                except Exception:
                    continue

            # Check for exact service name match
            if partial_name in all_services:
                return partial_name

            # Check for partial service name matches
            matching_services = [
                name
                for name in all_services.keys()
                if partial_name.lower() in name.lower()
            ]

            if len(matching_services) == 1:
                return matching_services[0]

            # Check for prefix matches
            prefix_matches = [
                name
                for name in all_services.keys()
                if name.lower().startswith(partial_name.lower())
            ]

            if len(prefix_matches) == 1:
                return prefix_matches[0]

            return None

        except Exception as e:
            logger.debug("Error scanning directory structure: {}", e)
            return None


# Global instance for shared use
_service_discovery = None


def get_service_discovery() -> ServiceDiscovery:
    """Get the global service discovery instance."""
    global _service_discovery
    if _service_discovery is None:
        _service_discovery = ServiceDiscovery()
    return _service_discovery


def refresh_service_discovery() -> None:
    """Refresh the global service discovery."""
    global _service_discovery
    if _service_discovery is not None:
        _service_discovery.refresh_discovery()
    else:
        _service_discovery = ServiceDiscovery()
