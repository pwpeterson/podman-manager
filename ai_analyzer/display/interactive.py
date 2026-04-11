"""Interactive follow-up analysis session handler."""

from __future__ import annotations

from typing import Any, Optional

from core.config import console

from .markdown import MarkdownDisplayFormatter


class InteractiveAnalysisHandler:
    """Handles interactive AI analysis sessions."""

    def __init__(self) -> None:
        self.original_prompt: Optional[str] = None
        self.original_analysis_result: Optional[str] = None
        self._collected_data: dict[str, Any] | None = None

    def set_context(self, original_prompt: str, original_analysis_result: str) -> None:
        """Set context from original analysis."""
        self.original_prompt = original_prompt
        self.original_analysis_result = original_analysis_result

    def set_collected_data(self, data: dict[str, Any]) -> None:
        """Set the collected data for use in display methods."""
        self._collected_data = data

    def start_session(
        self, analysis_type: str, target: str, verbose: bool = False
    ) -> None:
        """Start interactive AI analysis session."""
        console.print("\n[bold green]Interactive AI Analysis[/bold green]")
        console.print(
            "[bright_yellow]Ask follow-up questions about the analysis.[/bright_yellow]"
        )
        console.print(
            "[dim]Type your question and press Enter to submit, or press Enter with no input to exit.[/dim]"
        )

        while True:
            try:
                console.print("\n[bold yellow]==>[/bold yellow] ", end="")
                user_input = self._read_single_line_input()

                if not user_input or not user_input.strip():
                    break

                self._process_followup_question(
                    analysis_type, target, user_input, verbose
                )

            except KeyboardInterrupt:
                # Clear any shell job control messages
                import sys

                sys.stdout.write("\r\033[K")  # Clear current line
                sys.stdout.flush()
                console.print("\n[dim]Interactive analysis interrupted.[/dim]")
                break
            except EOFError:
                # Clear any shell job control messages
                import sys

                sys.stdout.write("\r\033[K")  # Clear current line
                sys.stdout.flush()
                console.print("\n[dim]Interactive analysis ended.[/dim]")
                break

        # Get the resolved service name from collected data, fallback to target
        display_name = target
        if self._collected_data and self._collected_data.get("service_name"):
            service_name = str(self._collected_data["service_name"])
            # Remove .service suffix for display if present
            display_name = (
                service_name.replace(".service", "")
                if service_name.endswith(".service")
                else service_name
            )

        # Clear any shell job control messages by printing a newline and moving cursor
        import sys

        sys.stdout.write("\r\033[K")  # Clear current line
        sys.stdout.flush()

        console.print(f"[green]AI analysis for {display_name} completed[/green]")
        console.print()

    def _read_single_line_input(self) -> str:
        """Read single line input - Enter to submit, empty line to exit."""
        try:
            return input().strip()
        except (KeyboardInterrupt, EOFError):
            return ""

    def _process_followup_question(
        self, analysis_type: str, target: str, question: str, verbose: bool = False
    ) -> None:
        """Process a follow-up question and generate AI response."""
        # Get the resolved service name from collected data, fallback to target
        display_name = target
        if self._collected_data and self._collected_data.get("service_name"):
            service_name = str(self._collected_data["service_name"])
            # Remove .service suffix for display if present
            display_name = (
                service_name.replace(".service", "")
                if service_name.endswith(".service")
                else service_name
            )

        console.print(
            f"\n[bold green]Follow-up Analysis for {display_name}[/bold green]"
        )
        console.print()

        # Create followup prompt
        from ai_analyzer.prompts import FollowupPromptGenerator

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

        # Get AI analysis without spinner to avoid conflicts.
        # Model-proxy (assistant model) is the single backend for follow-ups.
        result: Optional[str] = None
        try:
            from ai_system.model_proxy_client import ModelProxyClient, ModelProxyError

            mp = ModelProxyClient()
            assistant_model = mp.get_assistant_model()
            if not assistant_model:
                console.print(
                    "[yellow]No assistant model is configured in abacus-proxy. Run the analysis again and select a model.[/yellow]"
                )
                return

            if verbose:
                console.print(
                    f"[dim]Using abacus-proxy assistant model for follow-up: {assistant_model}[/dim]"
                )

            result = mp.chat_completion_text(
                model=assistant_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert system administrator and DevOps engineer specializing in systemd service log analysis and troubleshooting.",
                    },
                    {"role": "user", "content": followup_prompt},
                ],
                max_tokens=1536,
                temperature=0.1,
            )
        except (ModelProxyError, Exception):
            result = None

        if result:
            formatter = MarkdownDisplayFormatter()
            formatter._render_markdown(result)
        else:
            console.print(
                "[yellow]Unable to generate follow-up analysis. Please try again.[/yellow]"
            )
