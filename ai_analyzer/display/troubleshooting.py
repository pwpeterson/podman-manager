"""Fallback troubleshooting formatter for when AI analysis is unavailable."""

from __future__ import annotations

from typing import Any

from core.config import console

from .base import DisplayFormatter


class BasicTroubleshootingFormatter(DisplayFormatter):
    """Formats and displays basic troubleshooting guide when AI analysis fails."""

    def __init__(self) -> None:
        self._collected_data: dict[str, Any] | None = None

    def display(
        self, analysis_type: str, target: str, result: str, verbose: bool = False
    ) -> None:
        """Show basic troubleshooting guide."""
        _ = verbose  # kept for DisplayFormatter signature consistency

        console.print(
            f"\n[bold yellow]Basic Troubleshooting Guide for {target}[/bold yellow]"
        )
        console.print()

        if analysis_type == "build_failure":
            self._show_build_troubleshooting(target, result)
            return

        # Use standard common actions formatter for service troubleshooting
        from operations.common_actions import CommonActionsFormatter

        # Get the resolved service name from collected data, fallback to target.service
        service_name = target
        if self._collected_data and self._collected_data.get("service_name"):
            service_name = str(self._collected_data["service_name"])
        elif not service_name.endswith(".service"):
            service_name = f"{target}.service"

        formatter = CommonActionsFormatter()
        formatter.show_common_actions(
            target=target,
            service_name=service_name,
            categories=[
                "pm_shortcuts",
                "service_status",
                "logs_diagnostics",
                "troubleshooting",
            ],
        )

    def set_collected_data(self, data: dict[str, Any]) -> None:
        """Set the collected data for use in display methods."""
        self._collected_data = data

    def _show_build_troubleshooting(self, target: str, data: str) -> None:
        """Show build-specific troubleshooting."""
        console.print("[bold cyan]Build Error Analysis:[/bold cyan]")

        # Parse data if it's a dict-like string
        if "build_error" in data:
            console.print("\n[bold red]Build Error:[/bold red]")
            # Extract and show error lines
            error_lines = data.split("\n")
            for line in error_lines[-10:]:
                if line.strip():
                    console.print(f"    [red]{line}[/red]")

        console.print("\n[bold cyan]Common Build Issues:[/bold cyan]")
        console.print("    1. [white]Missing dependencies in Dockerfile[/white]")
        console.print("    2. [white]Incorrect base image or version[/white]")
        console.print(
            "    3. [white]File not found errors (check COPY/ADD paths)[/white]"
        )
        console.print("    4. [white]Permission issues with files[/white]")
        console.print(
            "    5. [white]Network issues during package installation[/white]"
        )

        console.print("\n[bold green]Next Steps:[/bold green]")
        console.print(f"    [white]Retry build:[/white] [cyan]pm build {target}[/cyan]")
        console.print(
            f"    [white]Clean rebuild:[/white] [cyan]pm reinit {target} -b[/cyan]"
        )
        console.print(
            f"    [white]Check Dockerfile:[/white] [cyan]cat Dockerfile.{target}[/cyan]"
        )
        console.print()
