"""
Common "More available actions" for all pm commands
Provides a standardized set of diagnostic and management commands
"""

from typing import List, Optional

from core.config import console


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
                        "systemctl --user status {service_name} --no-pager -l",
                    ),
                    ("View service file", "systemctl --user cat {service_name}"),
                    ("Check if enabled", "systemctl --user is-enabled {service_name}"),
                    ("Check if active", "systemctl --user is-active {service_name}"),
                ],
            },
            # Logs & Diagnostics
            "logs_diagnostics": {
                "label": "Logs & Diagnostics",
                "commands": [
                    (
                        "View service logs",
                        "journalctl --user -u {service_name} -n 100 --no-pager",
                    ),
                    ("Follow live logs", "journalctl --user -u {service_name} -f"),
                    (
                        "View recent logs",
                        "journalctl --user -u {service_name} --since '1 hour ago' --no-pager",
                    ),
                    (
                        "Search for errors",
                        "journalctl --user -u {service_name} -n 200 --no-pager | grep -i error",
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
                    ("Inspect volume", "podman volume inspect {volume_name}"),
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
                    ("Start service", "systemctl --user start {service_name}"),
                    ("Stop service", "systemctl --user stop {service_name}"),
                    ("Restart service", "systemctl --user restart {service_name}"),
                    ("Enable auto-start", "systemctl --user enable {service_name}"),
                    ("Disable auto-start", "systemctl --user disable {service_name}"),
                    (
                        "Reset failed state",
                        "systemctl --user reset-failed {service_name}",
                    ),
                ],
            },
            # PM Command Shortcuts
            "pm_shortcuts": {
                "label": "PM Command Shortcuts",
                "commands": [
                    ("View podman logs", "pm logs {target}"),
                    ("Diagnose issues", "pm diag {target}"),
                    ("Restart service", "pm restart {target}"),
                    ("Reinitialize", "pm reinit {target}"),
                    ("View all containers", "pm ps"),
                ],
            },
            # Troubleshooting
            "troubleshooting": {
                "label": "Troubleshooting",
                "commands": [
                    ("Check systemd user session", "systemctl --user status"),
                    ("Reload systemd daemon", "systemctl --user daemon-reload"),
                    ("Check failed services", "systemctl --user --failed"),
                    ("View system journal", "journalctl --user -n 50 --no-pager"),
                    ("Check podman service", "systemctl --user status podman.service"),
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
            target: The pm target name (e.g., 'vllm-qwen25')
            service_name: Full service name (e.g., 'vllm-qwen25.service')
            container_name: Container name for podman commands
            port: Port number for network tests
            categories: List of category keys to show (None = all)
        """
        # Set defaults
        if not service_name and target:
            # Extract the last part of the target name for simplified service names
            # e.g., 'local-ai-neo4j' -> 'neo4j'
            simplified_target = target.split("-")[-1] if "-" in target else target
            service_name = f"{simplified_target}.service"
        if not container_name and target:
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

        console.print("\n[bold green]More available actions:[/bold green]")

        # Always use detailed format
        self._show_detailed_format(
            target, service_name, container_name, port, categories
        )

    def _show_detailed_format(
        self, target, service_name, container_name, port, categories
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
                    command_template, target, service_name, container_name, port
                )
                console.print(
                    f"        [green]✓ {label:20}:[/green] [white]{command}[/white]"
                )

        # Add a newline after all categories are displayed
        console.print()

    def _substitute_placeholders(
        self, template, target, service_name, container_name, port
    ):
        """Substitute placeholders in command templates"""
        substitutions = {
            "{target}": target or "SERVICE",
            "{service_name}": service_name or "SERVICE.service",
            "{container_name}": container_name or "CONTAINER",
            "{port}": port or "PORT",
            "{volume_name}": f"{target}-volume" if target else "VOLUME",
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
