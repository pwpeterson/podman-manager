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

    def display(
        self, analysis_type: str, target: str, result: str, verbose: bool = False
    ) -> None:
        """Display AI analysis results with markdown formatting"""
        title = self._get_title(analysis_type)
        console.print(f"\n[bold green]{title} for {target}[/bold green]")
        console.print()

        self._render_markdown(result)
        self._show_analysis_menu(analysis_type, target, verbose)

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

    def _render_markdown(self, content: str) -> None:
        """Render markdown content using Rich formatting"""
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
                console.print(f"    [cyan]{line}[/cyan]")
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
                    console.print(f"    [cyan]{cmd_line}[/cyan]")
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
        console.print("\n  [bold green]Recommended actions:[/bold green]")

        # Common actions
        console.print(
            f"[green]   View detailed logs:[/green] [white]pm logs {target}[/white]"
        )

        if analysis_type == "reinit_failure":
            console.print(
                f"[green]         Retry reinit:[/green] [white]pm reinit {target} -v[/white]"
            )
            console.print(
                f"[green]    Reset failed state:[/green] [white]pm reset-failed {target}[/white]"
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

        # Universal actions
        console.print(
            f"[green]   Diagnose the issue:[/green] [white]pm diagnose {target}[/white]"
        )
        console.print(
            f"[green]   Re-run AI analysis:[/green] [white]pm logs {target}[/white]"
        )
        console.print()


class BasicTroubleshootingFormatter(DisplayFormatter):
    """Formats and displays basic troubleshooting guide when AI analysis fails"""

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
            self._show_service_troubleshooting(target, result, analysis_type)

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

    def _show_service_troubleshooting(
        self, target: str, data: str, analysis_type: str
    ) -> None:
        """Show service-specific troubleshooting"""
        console.print("[bold cyan]Common Issues to Check:[/bold cyan]")
        console.print(
            f"    1. [white]Check service status:[/white] [cyan]systemctl --user status {target}.service[/cyan]"
        )
        console.print(
            f"    2. [white]View recent logs:[/white] [cyan]journalctl --user -u {target}.service -n 20[/cyan]"
        )
        console.print("    3. [white]Check disk space:[/white] [cyan]df -h[/cyan]")
        console.print(
            "    4. [white]Check for port conflicts:[/white] [cyan]ss -tulpen | grep :8000[/cyan]"
        )
        console.print(
            f"    5. [white]Restart the service:[/white] [cyan]pm restart {target}[/cyan]"
        )

        # Check for specific issues in the data
        if isinstance(data, str):
            logs = data.lower()
            if "port already in use" in logs or "bind" in logs:
                console.print("\n[bold red]⚠ Port Conflict Detected[/bold red]")
                console.print(
                    f"    [white]Try:[/white] [cyan]pm stop {target} && pm start {target}[/cyan]"
                )
            elif "no space left" in logs or "disk" in logs:
                console.print("\n[bold red]⚠ Disk Space Issue Detected[/bold red]")
                console.print(
                    "    [white]Try:[/white] [cyan]podman system prune -f[/cyan]"
                )
            elif "permission denied" in logs:
                console.print("\n[bold red]⚠ Permission Issue Detected[/bold red]")
                console.print(
                    f"    [white]Try:[/white] [cyan]pm reset-failed {target}[/cyan]"
                )

        console.print("\n[bold green]Next Steps:[/bold green]")
        console.print(
            f"    [white]For detailed analysis:[/white] [cyan]pm logs {target} -ai claude[/cyan]"
        )
        console.print(
            f"    [white]For manual diagnosis:[/white] [cyan]pm diagnose {target}[/cyan]"
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
            "[yellow]Ask follow-up questions about the analysis. Press Enter with empty input to exit.[/yellow]"
        )

        while True:
            try:
                console.print("\n[bold yellow]==>[/bold yellow] ", end="")
                user_input = input().strip()

                if not user_input:
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
        console.print(
            f"    [green]For further analysis try:[/green] [white]pm logs {target} -ai[/white]"
        )
        console.print()

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
            console.print("[green]Analyzing...[/green]", end="")
            console.print(" ", end="")

        # Get AI analysis
        result = self.ai_agent_manager.analyze_with_agent(followup_prompt)

        # Clear spinner
        if not verbose and result:
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
