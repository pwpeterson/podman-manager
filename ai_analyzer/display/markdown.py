"""Markdown-oriented display formatter for AI analyzer output."""

from __future__ import annotations

import re
import textwrap
from typing import Any

from core.config import console

from .base import DisplayFormatter


class MarkdownDisplayFormatter(DisplayFormatter):
    """Formats and displays analysis results as markdown."""

    def __init__(self) -> None:
        self._collected_data: dict[str, Any] | None = None

    def display(
        self, analysis_type: str, target: str, result: str, verbose: bool = False
    ) -> None:
        """Display AI analysis results with markdown formatting."""
        title = self._get_title(analysis_type)
        console.print(f"\n[bold green]{title} for {target}[/bold green]")
        console.print()

        self._render_markdown(result)
        self._show_analysis_menu(analysis_type, target, verbose)

    def set_collected_data(self, data: dict[str, Any]) -> None:
        """Set the collected data for use in display methods."""
        self._collected_data = data

    def _get_title(self, analysis_type: str) -> str:
        """Get display title for analysis type."""
        titles = {
            "logs": "AI Log Analysis",
            "reinit_failure": "AI Reinit Failure Analysis",
            "status": "AI Status Analysis",
            "build_failure": "AI Build Failure Analysis",
            "performance": "AI Performance Analysis",
            "security": "AI Security Analysis",
        }
        return titles.get(analysis_type, "AI Analysis")

    def _clean_rich_markup(self, content: str) -> str:
        """Remove Rich markup tags from AI-generated content."""
        # Pattern to match Rich markup tags: [tag] or [/tag]
        pattern = r"\[/?(?:cyan|bold|white|green|red|yellow|blue|magenta|dim|italic|underline|strike|blink|reverse|conceal|bright_[a-z]+|color\([0-9]+\)|rgb\([0-9,]+\)|#[0-9a-fA-F]+|orange1|[a-z_]+)\]"
        return re.sub(pattern, "", content)

    def _render_markdown(self, content: str) -> None:
        """Render markdown content using Rich formatting."""
        # Clean any Rich markup tags that might be in the AI-generated content
        content = self._clean_rich_markup(content)
        lines = content.split("\n")
        previous_was_header = False
        in_code_block = False

        for i, line in enumerate(lines):
            line = line.strip()

            # Skip multiple consecutive empty lines
            if not line:
                if not previous_was_header and i > 0 and lines[i - 1].strip():
                    console.print()
                continue

            # Handle headers (### Header)
            if line.startswith("### "):
                header_text = line[4:].strip()
                console.print(f"[bold cyan]{header_text}[/bold cyan]")
                previous_was_header = True
                continue
            else:
                previous_was_header = False

            # Handle bold text (**text**)
            line = re.sub(r"\*\*([^*]+)\*\*", r"[bold]\1[/bold]", line)

            # Handle inline code (`code`)
            def replace_code(match: re.Match[str]) -> str:
                code_content = match.group(1)
                if len(code_content) < 100 and "\n" not in code_content:
                    return f"[cyan]{code_content}[/cyan]"
                return code_content

            line = re.sub(r"`([^`]+)`", replace_code, line)

            # Handle code blocks (```)
            if line.startswith("```"):
                if line == "```text" or (line == "```" and not in_code_block):
                    continue
                if line == "```" and in_code_block:
                    in_code_block = False
                    continue
                if any(
                    lang in line
                    for lang in ["bash", "ini", "python", "json", "yaml", "sh"]
                ):
                    in_code_block = True
                    continue
                continue

            # Handle content inside code blocks
            if in_code_block:
                console.print(f"    {line}", style="cyan")
                continue

            # Handle numbered lists (1. item)
            if re.match(r"^\d+\.\s", line):
                wrapped_lines = textwrap.fill(
                    line, width=116, initial_indent="    ", subsequent_indent="       "
                )
                console.print(f"[white]{wrapped_lines}[/white]")
                continue

            # Handle bullet points (- item)
            if line.startswith("- "):
                wrapped_lines = textwrap.fill(
                    line,
                    width=112,
                    initial_indent="        ",
                    subsequent_indent="          ",
                )
                console.print(f"[white]{wrapped_lines}[/white]")
                continue

            # Handle long command lines
            if self._is_long_command_line(line):
                formatted_command = self._format_long_command_line(line)
                for cmd_line in formatted_command:
                    console.print(f"    {cmd_line}", style="cyan")
                continue

            # Regular text - wrap at 120 characters with indentation
            if len(line) > 116:
                wrapped_lines = textwrap.fill(
                    line, width=116, initial_indent="    ", subsequent_indent="    "
                )
                console.print(wrapped_lines)
            else:
                console.print(f"    {line}")

    def _is_long_command_line(self, line: str) -> bool:
        """Check if a line contains a long command that should be formatted."""
        command_indicators = [
            "ExecStart=",
            "podman run",
            "/usr/local/bin/podman",
            "--name",
            "--cidfile",
            "--replace",
            "--rm",
            "--network",
            "--publish",
            "--env",
            "--label",
            "--health-cmd",
        ]

        return len(line) > 100 and any(
            indicator in line for indicator in command_indicators
        )

    def _format_long_command_line(self, line: str) -> list[str]:
        """Format a long command line for better readability."""
        import shlex

        # Handle ExecStart= prefix
        exec_start_prefix = ""
        command_part = line

        if "ExecStart=" in line:
            parts = line.split("ExecStart=", 1)
            if len(parts) == 2:
                exec_start_prefix = parts[0] + "ExecStart="
                command_part = parts[1]

        # Handle numbered list prefix
        list_prefix = ""
        if line.strip().startswith(
            ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")
        ):
            match = re.match(r"^(\d+\.\s+[^:]+:\s*)", line.strip())
            if match:
                list_prefix = match.group(1)
                command_part = line.strip()[len(list_prefix) :].strip()
                if "ExecStart=" in command_part:
                    parts = command_part.split("ExecStart=", 1)
                    if len(parts) == 2:
                        exec_start_prefix = list_prefix + parts[0] + "ExecStart="
                        command_part = parts[1]
                    else:
                        exec_start_prefix = list_prefix
                else:
                    exec_start_prefix = list_prefix

        try:
            parts = shlex.split(command_part.strip())
        except ValueError:
            parts = command_part.strip().split()

        if not parts:
            return [line]

        formatted_lines: list[str] = []

        if exec_start_prefix:
            formatted_lines.append(exec_start_prefix)

        base_indent = "        "
        current_line = "    "
        if exec_start_prefix:
            current_line = base_indent

        i = 0
        while i < len(parts):
            part = parts[i]

            if part.startswith("--") and i > 0:
                if current_line.strip():
                    formatted_lines.append(current_line.rstrip())
                current_line = base_indent + part

                if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                    current_line += " " + parts[i + 1]
                    i += 1

                current_line += " \\"
            else:
                current_line += part + " "

            i += 1

        if current_line.strip():
            final_line = current_line.rstrip()
            if final_line.endswith(" \\"):
                final_line = final_line[:-3].rstrip()
            formatted_lines.append(final_line)

        return formatted_lines if formatted_lines else [line]

    def _show_analysis_menu(
        self, analysis_type: str, target: str, verbose: bool = False
    ) -> None:
        """Show recommended actions after AI analysis."""
        from operations.common_actions import CommonActionsFormatter

        # Get the resolved service name from collected data, fallback to target.service
        service_name = target
        if self._collected_data and self._collected_data.get("service_name"):
            service_name = str(self._collected_data["service_name"])
        elif not service_name.endswith(".service"):
            service_name = f"{target}.service"

        # Only show recommended actions for non-diag analysis types
        # (diag command should not show any additional actions)
        if analysis_type != "logs":  # diag uses "logs" analysis type
            formatter = CommonActionsFormatter()

            # Show analysis-type specific actions first
            console.print("\n  [bold green]Recommended actions:[/bold green]")

            if analysis_type == "reinit_failure":
                console.print(
                    f"[green]         Retry reinit:[/green] [white]pm reinit {target} -v[/white]"
                )
                console.print(
                    f"[green]   Reset failed state:[/green] [white]pm reset-failed {target}[/white]"
                )
            elif analysis_type == "build_failure":
                console.print(
                    f"[green]        Retry build:[/green] [white]pm build {target}[/white]"
                )
                console.print(
                    f"[green]    Clean and rebuild:[/green] [white]pm reinit {target} -b[/white]"
                )
            elif analysis_type == "status":
                console.print(
                    f"[green]    Restart service:[/green] [white]pm restart {target}[/white]"
                )
                console.print(
                    f"[green]   Monitor live logs:[/green] [white]pm logs {target} --f[/white]"
                )

            # Show common actions
            formatter.show_common_actions(
                target=target,
                service_name=service_name,
                categories=["pm_shortcuts", "logs_diagnostics", "troubleshooting"],
            )

        console.print()
