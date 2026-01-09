"""Refactored AI Analyzer - main coordinator class"""

from datetime import datetime
from typing import Any, Dict, Optional

from core.config import console, verbose_print

from .data_collectors import (
    ContainerDataCollector,
    LogsDataCollector,
    NetworkStorageCollector,
    PerformanceDataCollector,
    QuadletDataCollector,
    SystemdDataCollector,
    SystemResourceCollector,
)
from .display import DisplayFormatterFactory
from .prompts import PromptGeneratorFactory
from .spinner_manager import SpinnerManager, safe_spinner

# Legacy multi-agent config system removed; model selection uses model-proxy


class AIAnalyzer:
    """Refactored AI analyzer with separated concerns"""

    def __init__(self, manager: Optional[Any]):
        self.manager: Optional[Any] = manager
        self._setup_collectors()
        self._setup_formatters()
        self._original_prompt = None
        self._original_analysis_result = None

    def _setup_collectors(self) -> None:
        """Initialize data collectors"""
        self.collectors = {
            "systemd": SystemdDataCollector(),
            "container": ContainerDataCollector(),
            "system_resources": SystemResourceCollector(),
            "network_storage": NetworkStorageCollector(),
            "quadlet": QuadletDataCollector(),
            "logs": LogsDataCollector(),
            "performance": PerformanceDataCollector(),
        }

    def _setup_formatters(self) -> None:
        """Initialize display formatters"""
        self.markdown_formatter = DisplayFormatterFactory.create_markdown_formatter()
        self.basic_formatter = (
            DisplayFormatterFactory.create_basic_troubleshooting_formatter()
        )
        self.interactive_handler = DisplayFormatterFactory.create_interactive_handler()

    def ai_analyze(
        self,
        analysis_type: str,
        target: str,
        context_data: Optional[Dict[str, Any]] = None,
        ai_model: Optional[str] = None,
        ai_agent: Optional[str] = None,
        verbose: bool = False,
    ) -> Optional[str]:
        """
        Unified AI analysis method for all PM commands.

        Args:
            analysis_type: Type of analysis (e.g., 'logs', 'reinit_failure', 'status', 'build_failure')
            target: Target service/stack name
            context_data: Additional context data specific to the analysis type
            ai_model: Model-proxy model id override (optional)
            ai_agent: Backward-compatible alias for ai_model (optional)
            verbose: Enable verbose output

        Returns:
            AI analysis result or None if failed
        """
        # Backward compatibility: accept legacy ai_agent kwarg (alias for ai_model).
        if ai_model is None and ai_agent is not None:
            ai_model = ai_agent

        # Model-proxy selection (assistant model)
        if verbose:
            verbose_print(
                f"  [cyan]exec: ai_analyze(type={analysis_type}, target={target}, model={ai_model or 'assistant'})[/cyan]"
            )

        try:
            # Show data collection message before starting collection (skip for reinit_failure)
            if analysis_type != "reinit_failure":
                console.print(
                    "[green]Collecting data for AI analysis and diagnostic...[/green]"
                )
                console.print()

            # Collect context data for the analysis
            collected_data = self._collect_context_data(
                analysis_type, target, context_data or {}, verbose
            )

            if not collected_data:
                if verbose:
                    verbose_print(
                        "  [cyan]exec: No context data collected for analysis[/cyan]"
                    )
                return None

            # Generate the appropriate prompt for this analysis type
            prompt = self._generate_prompt(analysis_type, target, collected_data)

            if verbose:
                console.print("\n[bold cyan]AI Analysis Prompt:[/bold cyan]")
                console.print("[cyan]" + "─" * 80 + "[/cyan]")
                for line in prompt.split("\n"):
                    console.print(f"[cyan]{line}[/cyan]")
                console.print("[cyan]" + "─" * 80 + "[/cyan]")
                console.print()

            # Show AI analysis message for both verbose and non-verbose modes
            if analysis_type == "build_failure":
                if verbose:
                    console.print(
                        "[green]Starting AI analysis for build failure...[/green]"
                    )
                    console.print()
                else:
                    console.print("[green]Analyzing build failure...[/green]", end="")
                    console.print(" ", end="")
            elif analysis_type == "reinit_failure":
                # For reinit failures, don't show any startup message to avoid duplication
                # The reinit manager already shows "Error found in reinit command"
                if verbose:
                    verbose_print(
                        "  [cyan]exec: Skipping startup message for reinit_failure[/cyan]"
                    )
                pass
            else:
                # For other analysis types, show analyzing message only in verbose mode (skip for reinit_failure)
                if verbose and analysis_type != "reinit_failure":
                    console.print(
                        "[green]Starting AI analysis and diagnostics...[/green]"
                    )
                    console.print()

            # AI agent event: choose assistant model for troubleshooting via model-proxy
            selected_model: Optional[str] = None

            if ai_model:
                # If user provided a model id, set it as assistant without prompting.
                try:
                    from ai_system.model_proxy_client import ModelProxyClient

                    ModelProxyClient().set_assistant_model(ai_model)
                    selected_model = ai_model
                except Exception as e:
                    if verbose:
                        verbose_print(
                            f"  [cyan]exec: Failed to set assistant model to {ai_model}: {e}[/cyan]"
                        )
            else:
                from ai_system.model_selection_event import run_model_selection_event

                selection = run_model_selection_event(
                    title=f"AI agent event: {analysis_type} ({target})",
                    prompt_text="Select a model to use for troubleshooting",
                )
                selected_model = selection.selected_model

            # Get AI analysis using model-proxy
            # Use safe spinner for non-verbose modes (except reinit_failure which handles its own display)
            spinner_text = "Analyzing..." if analysis_type != "reinit_failure" else None
            show_spinner = not verbose and analysis_type != "reinit_failure"

            with safe_spinner(
                spinner_text or "Processing...", console, verbose=not show_spinner
            ):
                result = self._analyze_with_fallback(
                    prompt,
                    verbose=verbose,
                    target=target,
                    selected_model=selected_model,
                )

            # Pass collected data to formatters so they can use resolved service names
            self.markdown_formatter.set_collected_data(collected_data)
            self.interactive_handler.set_collected_data(collected_data)
            self.basic_formatter.set_collected_data(collected_data)

            if result:
                # Store context for follow-up questions
                self._original_prompt = prompt
                self._original_analysis_result = result
                self.interactive_handler.set_context(prompt, result)

                # Display the results (do not show actions menu yet)
                self.markdown_formatter.display(analysis_type, target, result, verbose)

                # Start interactive analysis session (user exits to continue)
                self.interactive_handler.start_session(analysis_type, target, verbose)

                # Show recommended actions after interactive follow-ups end
                if hasattr(self.markdown_formatter, "show_recommended_actions"):
                    self.markdown_formatter.show_recommended_actions(
                        analysis_type, target, verbose
                    )

                return result
            else:
                if verbose:
                    verbose_print("  [cyan]exec: No AI analysis result returned[/cyan]")

                # Show basic troubleshooting guide when AI analysis fails
                self.basic_formatter.display(
                    analysis_type, target, str(collected_data), verbose
                )

                # For diag command, don't start interactive session to avoid hanging
                # The diag command should complete after showing troubleshooting guide
                if analysis_type != "logs" or verbose:
                    # Only start interactive session for non-diag commands or when verbose
                    console.print(
                        "\n[yellow]AI analysis was unavailable, but you can still ask questions about troubleshooting.[/yellow]"
                    )
                    self.interactive_handler.start_session(
                        analysis_type, target, verbose
                    )

                return "basic_troubleshooting_shown"

        except Exception as e:
            if verbose:
                verbose_print(
                    f"  [cyan]exec: AI analysis failed with exception: {e}[/cyan]"
                )
            console.print(f"[yellow]AI analysis failed: {e}[/yellow]")
            return None

    def _collect_context_data(
        self,
        analysis_type: str,
        target: str,
        context_data: Dict[str, Any],
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Collect context data based on analysis type using specialized collectors"""
        if verbose:
            verbose_print(
                f"  [cyan]exec: Starting comprehensive diagnostic data collection for {analysis_type} analysis[/cyan]"
            )

        data = {
            "target": target,
            "timestamp": datetime.now().isoformat(),
            "analysis_type": analysis_type,
        }

        # Add any provided context data
        data.update(context_data)

        # Set verbose mode for all collectors
        for collector in self.collectors.values():
            collector.verbose = verbose

        try:
            if analysis_type in ["logs", "reinit_failure"]:
                # Collect comprehensive service diagnostics
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Collecting comprehensive service diagnostics for {target}[/cyan]"
                    )

                # Get service name first
                systemd_data = self.collectors["systemd"].collect(
                    target, manager=self.manager
                )
                data.update(systemd_data)

                service_name = systemd_data.get("service_name", target)

                # Collect logs
                logs_data = self.collectors["logs"].collect(
                    target,
                    service_name=service_name,
                    lines=context_data.get("lines", 50),
                )
                data.update(logs_data)

                # Collect container details
                container_data = self.collectors["container"].collect(
                    target, service_name=service_name
                )
                data.update(container_data)

                # Collect Quadlet configuration
                quadlet_data = self.collectors["quadlet"].collect(
                    target, service_name=service_name
                )
                data.update(quadlet_data)

                # Collect system resources
                system_data = self.collectors["system_resources"].collect(target)
                data.update(system_data)

                # Collect network and storage info
                network_data = self.collectors["network_storage"].collect(target)
                data.update(network_data)

            elif analysis_type == "status":
                # Collect service status information
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Collecting service status information for {target}[/cyan]"
                    )

                systemd_data = self.collectors["systemd"].collect(
                    target, manager=self.manager
                )
                data.update(systemd_data)

            elif analysis_type == "build_failure":
                # Build logs are already provided in context_data
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Using provided build failure information for {target}[/cyan]"
                    )
                # No additional collection needed for build failures

            elif analysis_type == "service_start_failure":
                # Service start failure context is already provided in context_data
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Using provided service start failure information for {target}[/cyan]"
                    )
                # No additional collection needed for service start failures

            elif analysis_type == "performance":
                # Collect performance metrics
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Collecting performance metrics for {target}[/cyan]"
                    )

                performance_data = self.collectors["performance"].collect(target)
                data.update(performance_data)

            elif analysis_type == "security":
                # Collect security-related information
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Collecting security information for {target}[/cyan]"
                    )

                # For security analysis, collect systemd and container data
                systemd_data = self.collectors["systemd"].collect(
                    target, manager=self.manager
                )
                data.update(systemd_data)

                # Get service name for container collection (reuse systemd_data)
                service_name = systemd_data.get("service_name", target)

                container_data = self.collectors["container"].collect(
                    target, service_name=service_name
                )
                data.update(container_data)

            if verbose:
                verbose_print(
                    "  [cyan]exec: Diagnostic data collection completed[/cyan]"
                )

        except Exception as e:
            if verbose:
                verbose_print(f"  [cyan]exec: Data collection failed: {e}[/cyan]")
            data["collection_error"] = str(e)

        return data

    def _generate_prompt(
        self, analysis_type: str, target: str, data: Dict[str, Any]
    ) -> str:
        """Generate appropriate prompt based on analysis type"""
        generator = PromptGeneratorFactory.create(analysis_type)
        return generator.generate(target, data)

    def _analyze_with_fallback(
        self,
        prompt: str,
        verbose: bool = False,
        target: Optional[str] = None,
        selected_model: Optional[str] = None,
    ) -> Optional[str]:
        """Analyze using model-proxy (OpenAI-compatible).

        We rely on model-proxy for provider routing and credentials. The model to
        use is either:
        - the explicitly selected model (preferred), or
        - the current assistant model configured in model-proxy.
        """
        _ = target  # reserved for future prompt tailoring

        try:
            from ai_system.model_proxy_client import ModelProxyClient, ModelProxyError

            mp = ModelProxyClient()
            model_id = selected_model or mp.get_assistant_model()
            if not model_id:
                console.print(
                    "[yellow]No assistant model is configured in model-proxy. Select a model when prompted.[/yellow]"
                )
                return None

            if verbose:
                verbose_print(
                    f"  [cyan]exec: Using model-proxy model: {model_id}[/cyan]"
                )

            # If no spinner is active (e.g., verbose mode disables the outer spinner,
            # or reinit_failure suppresses it), show a spinner here so the user sees
            # immediate feedback after model selection.
            show_local_spinner = SpinnerManager._active_spinner is None

            with safe_spinner(
                "Processing request...", console, verbose=not show_local_spinner
            ):
                return mp.chat_completion_text(
                    model=model_id,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert system administrator and DevOps engineer specializing in systemd service log analysis and troubleshooting.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=2048,
                    temperature=0.1,
                )
        except (ModelProxyError, Exception) as e:
            if verbose:
                verbose_print(f"  [cyan]exec: model-proxy analysis failed: {e}[/cyan]")
            console.print(f"[red]AI analysis failed (model-proxy): {e}[/red]")
            return None
