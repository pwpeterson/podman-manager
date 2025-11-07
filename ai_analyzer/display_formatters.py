"""Display and formatting classes for AI analysis system"""

import re
import textwrap
from abc import ABC, abstractmethod

from core.config import console


class DisplayFormatter(ABC):
    """Abstract base class for display formatters"""

    @abstractmethod
    def display(
        self, analysis_type: str, target: str, result: str, verbose: bool = False
    ) -> None:
        """Display analysis results"""
        pass


class MarkdownDisplayFormatter(DisplayFormatter):
    """Formats and displays analysis results as markdown"""

    def __init__(self):
        self._collected_data = None

    def display(
        self, analysis_type: str, target: str, result: str, verbose: bool = False
    ) -> None:
        """Display AI analysis results with markdown formatting"""
        title = self._get_title(analysis_type)
        console.print(f"\n[bold green]{title} for {target}[/bold green]")
        console.print()

        self._render_markdown(result)
        self._show_analysis_menu(analysis_type, target, verbose)

    def set_collected_data(self, data: dict) -> None:
        """Set the collected data for use in display methods"""
        self._collected_data = data

    def _get_title(self, analysis_type: str) -> str:
        """Get display title for analysis type"""
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
        """Remove Rich markup tags from AI-generated content"""
        # Remove Rich markup tags like [/cyan], [cyan], [bold], [/bold], etc.
        import re

        # Pattern to match Rich markup tags: [tag] or [/tag]
        # Include all common Rich colors and styles, plus any custom colors
        pattern = r"\[/?(?:cyan|bold|white|green|red|yellow|blue|magenta|dim|italic|underline|strike|blink|reverse|conceal|bright_[a-z]+|color\([0-9]+\)|rgb\([0-9,]+\)|#[0-9a-fA-F]+|orange1|[a-z_]+)\]"
        cleaned_content = re.sub(pattern, "", content)
        return cleaned_content

    def _render_markdown(self, content: str) -> None:
        """Render markdown content using Rich formatting"""
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
            def replace_code(match):
                code_content = match.group(1)
                if len(code_content) < 100 and "\n" not in code_content:
                    return f"[cyan]{code_content}[/cyan]"
                else:
                    return code_content

            line = re.sub(r"`([^`]+)`", replace_code, line)

            # Handle code blocks (```)
            if line.startswith("```"):
                if line == "```text" or (line == "```" and not in_code_block):
                    continue
                elif line == "```" and in_code_block:
                    in_code_block = False
                    continue
                elif any(
                    lang in line
                    for lang in ["bash", "ini", "python", "json", "yaml", "sh"]
                ):
                    in_code_block = True
                    continue
                else:
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
        """Check if a line contains a long command that should be formatted"""
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

        if len(line) > 100:
            return any(indicator in line for indicator in command_indicators)
        return False

    def _format_long_command_line(self, line: str) -> list:
        """Format a long command line for better readability"""
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

        formatted_lines = []

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
        """Show recommended actions after AI analysis"""
        from operations.common_actions import CommonActionsFormatter

        # Get the resolved service name from collected data, fallback to target.service
        service_name = target
        if self._collected_data and self._collected_data.get("service_name"):
            service_name = self._collected_data["service_name"]
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


class BasicTroubleshootingFormatter(DisplayFormatter):
    """Formats and displays basic troubleshooting guide when AI analysis fails"""

    def __init__(self):
        self._collected_data = None

    def display(
        self, analysis_type: str, target: str, result: str, verbose: bool = False
    ) -> None:
        """Show basic troubleshooting guide"""
        console.print(
            f"\n[bold yellow]Basic Troubleshooting Guide for {target}[/bold yellow]"
        )
        console.print()

        if analysis_type == "build_failure":
            self._show_build_troubleshooting(target, result)
        else:
            # Use standard common actions formatter for service troubleshooting
            from operations.common_actions import CommonActionsFormatter

            # Get the resolved service name from collected data, fallback to target.service
            service_name = target
            if self._collected_data and self._collected_data.get("service_name"):
                service_name = self._collected_data["service_name"]
            elif not service_name.endswith(".service"):
                service_name = f"{target}.service"

            # Use standard common actions formatter
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

    def set_collected_data(self, data: dict) -> None:
        """Set the collected data for use in display methods"""
        self._collected_data = data

    def _show_build_troubleshooting(self, target: str, data: str) -> None:
        """Show build-specific troubleshooting"""
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


class InteractiveAnalysisHandler:
    """Handles interactive AI analysis sessions"""

    def __init__(self, ai_agent_manager):
        self.ai_agent_manager = ai_agent_manager
        self.original_prompt = None
        self.original_analysis_result = None

    def set_context(self, original_prompt: str, original_analysis_result: str) -> None:
        """Set context from original analysis"""
        self.original_prompt = original_prompt
        self.original_analysis_result = original_analysis_result

    def start_session(
        self, analysis_type: str, target: str, verbose: bool = False
    ) -> None:
        """Start interactive AI analysis session"""
        console.print("\n[bold green]Interactive AI Analysis[/bold green]")
        console.print(
            "[bright_yellow]Ask follow-up questions about the analysis.[/bright_yellow]"
        )
        console.print(
            "[dim]Type your question (can be multiple lines). Type 'END' on a new line to submit, or just 'END' to exit.[/dim]"
        )

        while True:
            try:
                console.print("\n[bold yellow]==>[/bold yellow] ", end="")
                user_input = self._read_multiline_input()

                if not user_input.strip():
                    break

                self._process_followup_question(
                    analysis_type, target, user_input, verbose
                )

            except KeyboardInterrupt:
                console.print("\n[dim]Interactive analysis interrupted.[/dim]")
                break
            except EOFError:
                console.print("\n[dim]Interactive analysis ended.[/dim]")
                break

        console.print(f"\n[green]AI analysis for {target} completed[/green]")

    def _read_multiline_input(self) -> str:
        """Read multi-line input until 'END' is entered on a new line"""
        lines = []

        while True:
            try:
                line = input()

                # Check if user wants to end input
                if line.strip().upper() == "END":
                    break

                # Add the line to our input
                lines.append(line)

            except (KeyboardInterrupt, EOFError):
                break

        # Join all lines and return the complete input
        result = "\n".join(lines).strip()
        return result

    def _process_followup_question(
        self, analysis_type: str, target: str, question: str, verbose: bool = False
    ) -> None:
        """Process a follow-up question and generate AI response"""
        console.print(f"\n[bold green]Follow-up Analysis for {target}[/bold green]")
        console.print()

        # Create followup prompt
        from .prompt_generators import FollowupPromptGenerator

        followup_data = {
            "analysis_type": analysis_type,
            "question": question,
            "original_prompt": self.original_prompt,
            "original_analysis": self.original_analysis_result,
        }

        generator = FollowupPromptGenerator()
        followup_prompt = generator.generate(target, followup_data)

        if verbose:
            console.print("\n[bold cyan]Follow-up AI Analysis Prompt:[/bold cyan]")
            console.print("[cyan]" + "─" * 80 + "[/cyan]")
            for line in followup_prompt.split("\n"):
                console.print(f"[cyan]{line}[/cyan]")
            console.print("[cyan]" + "─" * 80 + "[/cyan]")
            console.print()

        # Show analyzing spinner
        if not verbose:
            from rich.live import Live
            from rich.spinner import Spinner

            spinner = Spinner("dots", text="[green]Analyzing...[/green]")
            live = Live(spinner, console=console, refresh_per_second=10)
            live.start()

        # Get AI analysis
        result = self.ai_agent_manager.analyze_with_agent(followup_prompt)

        # Stop spinner
        if not verbose and result and "live" in locals():
            live.stop()
        elif not verbose and result:
            console.print("\r" + "" * 30 + "\r", end="")

        if result:
            formatter = MarkdownDisplayFormatter()
            formatter._render_markdown(result)
        else:
            console.print(
                "[yellow]Unable to generate follow-up analysis. Please try again.[/yellow]"
            )


class DisplayFormatterFactory:
    """Factory for creating appropriate display formatters"""

    @staticmethod
    def create_markdown_formatter() -> MarkdownDisplayFormatter:
        """Create markdown display formatter"""
        return MarkdownDisplayFormatter()

    @staticmethod
    def create_basic_troubleshooting_formatter() -> BasicTroubleshootingFormatter:
        """Create basic troubleshooting formatter"""
        return BasicTroubleshootingFormatter()

    @staticmethod
    def create_interactive_handler(ai_agent_manager) -> InteractiveAnalysisHandler:
        """Create interactive analysis handler"""
        return InteractiveAnalysisHandler(ai_agent_manager)
