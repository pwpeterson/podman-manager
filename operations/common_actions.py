"""
Common "More available actions" for all pm commands
Provides a standardized set of diagnostic and management commands
"""

from typing import List, Optional

from core.config import console
from core.simple_fuzzy_matcher import find_container


class CommonActionsFormatter:
    """Formats and displays common actions available after pm command completion"""

    def __init__(self):
        self.actions = self._build_common_actions()

    def _build_common_actions(self) -> dict:
        """Build the comprehensive set of common actions"""
        return {
            # Service Status & Information
            "service_status": {
                "label": "Service Status",
                "commands": [
                    (
                        "Check service status",
                        "systemctl --user status {container_name} --no-pager -l",
                    ),
                    ("View service file", "systemctl --user cat {container_name}"),
                    (
                        "Check if enabled",
                        "systemctl --user is-enabled {container_name}",
                    ),
                    ("Check if active", "systemctl --user is-active {container_name}"),
                ],
            },
            # Logs & Diagnostics
            "logs_diagnostics": {
                "label": "Logs & Diagnostics",
                "commands": [
                    (
                        "View service logs",
                        "journalctl --user -u {container_name} -n 100 --no-pager",
                    ),
                    ("Follow live logs", "journalctl --user -u {container_name} -f"),
                    (
                        "View recent logs",
                        "journalctl --user -u {container_name} --since '1 hour ago' --no-pager",
                    ),
                    (
                        "Search for errors",
                        "journalctl --user -u {container_name} -n 200 --no-pager | grep -i error",
                    ),
                ],
            },
            # Container Operations
            "container_ops": {
                "label": "Container Operations",
                "commands": [
                    (
                        "List all containers",
                        "podman ps -a --format '{{.ID}} {{.Names}} {{.Status}} {{.Image}}'",
                    ),
                    (
                        "View container logs",
                        "podman logs {container_name} --since 2h --timestamps --tail 100",
                    ),
                    ("Inspect container", "podman inspect {container_name}"),
                    (
                        "Container resource usage",
                        "podman stats {container_name} --no-stream",
                    ),
                    (
                        "Execute into container",
                        "podman exec -it {container_name} /bin/bash",
                    ),
                ],
            },
            # System Resources
            "system_resources": {
                "label": "System Resources",
                "commands": [
                    ("Check disk space", "df -h /"),
                    ("Podman system info", "podman system info"),
                    ("Podman disk usage", "podman system df"),
                    ("Check memory usage", "free -h"),
                    ("Check running processes", "ps aux | grep {container_name}"),
                ],
            },
            # Network & Connectivity
            "network_connectivity": {
                "label": "Network & Connectivity",
                "commands": [
                    ("List networks", "podman network ls"),
                    ("Check port usage", "ss -tulpen -H"),
                    ("Check specific port", "ss -tulpen | grep :{port}"),
                    (
                        "Network connectivity test",
                        "curl -I http://localhost:{port} || echo 'Connection failed'",
                    ),
                    ("DNS resolution test", "nslookup {hostname} || echo 'DNS failed'"),
                ],
            },
            # Volume Management
            "volume_management": {
                "label": "Volume Management",
                "commands": [
                    ("List volumes", "podman volume ls"),
                    ("Inspect volume", "podman volume inspect {container_name}-volume"),
                    ("Volume usage", "podman system df -v"),
                    (
                        "Check volume mounts",
                        "podman inspect {container_name} | grep -A 10 'Mounts'",
                    ),
                ],
            },
            # Service Management
            "service_management": {
                "label": "Service Management",
                "commands": [
                    ("Start service", "systemctl --user start {container_name}"),
                    ("Stop service", "systemctl --user stop {container_name}"),
                    ("Restart service", "systemctl --user restart {container_name}"),
                    ("Enable auto-start", "systemctl --user enable {container_name}"),
                    ("Disable auto-start", "systemctl --user disable {container_name}"),
                    (
                        "Reset failed state",
                        "systemctl --user reset-failed {container_name}",
                    ),
                ],
            },
            # PM Command Shortcuts
            "pm_shortcuts": {
                "label": "PM Command Shortcuts",
                "commands": [
                    ("View podman logs", "pm logs {target_name}"),
                    ("Diagnose issues", "pm diag {target_name}"),
                    ("Restart service", "pm restart {target_name}"),
                    ("Reinitialize", "pm reinit {target_name}"),
                    ("View all containers", "pm ps"),
                ],
            },
            # Troubleshooting
            "troubleshooting": {
                "label": "Troubleshooting",
                "commands": [
                    ("Check systemd session", "systemctl --user status"),
                    ("Reload systemd daemon", "systemctl --user daemon-reload"),
                    ("Check failed services", "systemctl --user --failed"),
                    ("  View system journal", "journalctl --user -n 50 --no-pager"),
                    (" Check podman service", "systemctl --user status podman.service"),
                ],
            },
        }

    def show_common_actions(
        self,
        target: Optional[str] = None,
        service_name: Optional[str] = None,
        container_name: Optional[str] = None,
        port: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ):
        """
        Display common actions with dynamic substitution

        Args:
            target: The pm target name (e.g., 'vllm-qwen25') - used for fuzzy matching
            service_name: Full service name (e.g., 'vllm-qwen25.service') - derived if not provided
            container_name: Container name for podman commands - derived if not provided
            port: Port number for network tests - derived if not provided
            categories: List of category keys to show (None = all)
        """
        # If container_name is already provided, skip fuzzy matching to avoid duplicate prompts
        if container_name:
            # Use provided container_name, no fuzzy matching needed
            pass
        elif target:
            # Check if this is a stack target (ends with -stack or is a known stack name)
            is_stack_target = target.endswith("-stack") or target in [
                "local-ai",
                "supabase",
                "vllm",
                "stack",
            ]

            if not is_stack_target:
                # Only use fuzzy matching for individual container targets
                try:
                    container = find_container(target)
                    if container:
                        # Use container object to derive values
                        container_name = container["name"]
                        port = (
                            container["port"]
                            if container["port"] != "unknown"
                            else "8000"
                        )
                        # Derive service_name from container name
                        if not service_name:
                            # Use the full container name for service names
                            service_name = f"{container_name}.service"
                    else:
                        # Only show warning for non-stack targets
                        console.print(
                            f"[yellow]Warning: No container found for '{target}'. Using provided values.[/yellow]"
                        )
                except Exception:
                    # If fuzzy matching fails, continue with provided values
                    pass
            else:
                # For stack targets, use generic values without fuzzy matching
                if not container_name:
                    container_name = target
                if not service_name:
                    service_name = f"{target}.service"

        # Set defaults if not derived from container
        if not service_name and container_name:
            # Use the full container name for service names
            service_name = f"{container_name}.service"
        elif not service_name and target:
            # Fallback to target if container_name not available
            # For systemctl commands, we need the full service name with .service suffix
            service_name = f"{target}.service"
            if not container_name:
                container_name = target
        if not port:
            port = "8000"  # Default port for examples

        # Determine which categories to show
        if categories is None:
            categories = [
                "pm_shortcuts",
                "service_status",
                "logs_diagnostics",
                "troubleshooting",
            ]

        console.print("[bold green]More available actions:[/bold green]")

        # Always use detailed format - pass target for PM shortcuts
        self._show_detailed_format(
            container_name, service_name, port, categories, target
        )

    def _show_detailed_format(
        self, container_name, service_name, port, categories, target=None
    ):
        """Show detailed format with categorized commands"""
        for category_key in categories:
            if category_key not in self.actions:
                continue

            category = self.actions[category_key]
            console.print(f"\n[bold cyan]{category['label']}:[/bold cyan]")

            for label, command_template in category["commands"]:
                # Substitute placeholders
                command = self._substitute_placeholders(
                    command_template, container_name, service_name, port, target
                )
                console.print(
                    f"    [green]✓ {label:20}:[/green] [white]{command}[/white]"
                )

        # Add a newline after all categories are displayed
        console.print()

    def _substitute_placeholders(
        self, template, container_name, service_name, port, target=None
    ):
        """Substitute placeholders in command templates"""
        # For systemctl and journalctl commands, use service_name (includes .service suffix)
        # For podman commands, use container_name (without .service suffix)
        if "systemctl" in template or "journalctl" in template:
            name_for_template = (
                service_name or f"{container_name}.service"
                if container_name
                else "CONTAINER"
            )
        else:
            name_for_template = container_name or "CONTAINER"

        substitutions = {
            "{container_name}": name_for_template,
            "{target_name}": target or container_name or "TARGET",
            "{port}": port or "PORT",
            "{hostname}": "localhost",
        }

        result = template
        for placeholder, value in substitutions.items():
            result = result.replace(placeholder, value)
        return result

    def show_category_actions(self, category_key: str, **kwargs):
        """Show actions for a specific category"""
        if category_key not in self.actions:
            console.print(f"[red]Unknown category: {category_key}[/red]")
            return

        self.show_common_actions(categories=[category_key], **kwargs)

    def get_available_categories(self) -> List[str]:
        """Get list of available action categories"""
        return list(self.actions.keys())

    def show_all_categories(self):
        """Show all available categories"""
        console.print("[bold blue]Available Action Categories:[/bold blue]")
        for key, category in self.actions.items():
            console.print(f"  [cyan]{key:20}[/cyan] - {category['label']}")


# Convenience functions for easy import
def show_common_actions(**kwargs):
    """Convenience function to show common actions"""
    formatter = CommonActionsFormatter()
    formatter.show_common_actions(**kwargs)
