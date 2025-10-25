"""Refactored AI Analyzer - main coordinator class"""

from datetime import datetime
from typing import Any, Dict, Optional

from ai_system.ai_agents import ai_agent_manager
from core.config import console, verbose_print

from .config import config
from .data_collectors import (
    ContainerDataCollector,
    LogsDataCollector,
    NetworkStorageCollector,
    PerformanceDataCollector,
    QuadletDataCollector,
    SystemdDataCollector,
    SystemResourceCollector,
)
from .display_formatters import (
    DisplayFormatterFactory,
)
from .prompt_generators import PromptGeneratorFactory


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
        self.interactive_handler = DisplayFormatterFactory.create_interactive_handler(
            ai_agent_manager
        )

    def ai_analyze(
        self,
        analysis_type: str,
        target: str,
        context_data: Optional[Dict[str, Any]] = None,
        ai_agent: Optional[str] = None,
        verbose: bool = False,
    ) -> Optional[str]:
        """
        Unified AI analysis method for all PM commands.

        Args:
            analysis_type: Type of analysis (e.g., 'logs', 'reinit_failure', 'status', 'build_failure')
            target: Target service/stack name
            context_data: Additional context data specific to the analysis type
            ai_agent: Specific AI agent to use (optional)
            verbose: Enable verbose output

        Returns:
            AI analysis result or None if failed
        """
        # Resolve short agent names to full names
        resolved_agent = config.resolve_agent_name(ai_agent)

        if verbose:
            verbose_print(
                f"  [cyan]exec: ai_analyze(type={analysis_type}, target={target}, agent={resolved_agent or 'default'})[/cyan]"
            )

        try:
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

            # Show analyzing spinner before AI agent call
            if not verbose:
                if analysis_type == "build_failure":
                    console.print("[green]⠴ Analyzing build failure...[/green]", end="")
                else:
                    console.print("[green]Analyzing error data...[/green]", end="")
                console.print(" ", end="")

            # Get AI analysis using the agent system
            result = ai_agent_manager.analyze_with_agent(
                prompt, resolved_agent, verbose=verbose
            )

            # Clear the analyzing message if not in verbose mode
            if not verbose and result:
                console.print("\r" + "" * 30 + "\r", end="")

            if result:
                # Store context for follow-up questions
                self._original_prompt = prompt
                self._original_analysis_result = result
                self.interactive_handler.set_context(prompt, result)

                # Display the results
                self.markdown_formatter.display(analysis_type, target, result, verbose)

                # Start interactive analysis session
                self.interactive_handler.start_session(analysis_type, target, verbose)

                return result
            else:
                if verbose:
                    verbose_print("  [cyan]exec: No AI analysis result returned[/cyan]")

                # Show basic troubleshooting guide when AI analysis fails
                self.basic_formatter.display(
                    analysis_type, target, str(collected_data), verbose
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
                container_data = self.collectors["container"].collect(target)
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

                container_data = self.collectors["container"].collect(target)
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
