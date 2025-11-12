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
from .spinner_manager import safe_spinner


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

            # Get AI analysis using the agent system with fallback logic
            # Use safe spinner for non-verbose modes (except reinit_failure which handles its own display)
            spinner_text = "Analyzing..." if analysis_type != "reinit_failure" else None
            show_spinner = not verbose and analysis_type != "reinit_failure"

            with safe_spinner(
                spinner_text or "Processing...", console, verbose=not show_spinner
            ):
                result = self._analyze_with_fallback(
                    prompt, resolved_agent, verbose=verbose, target=target
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

                # Get service name for container collection
                systemd_data = self.collectors["systemd"].collect(
                    target, manager=self.manager
                )
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
        agent_name: Optional[str] = None,
        verbose: bool = False,
        target: Optional[str] = None,
    ) -> Optional[str]:
        """Analyze with agent fallback logic and user feedback"""
        # Get the requested agent or default
        agent = ai_agent_manager.get_agent(agent_name)
        if not agent:
            console.print("[red]No AI agents available[/red]")
            return None

        # Show which agents we're trying
        console.print("[cyan]🤖 AI Agent Selection:[/cyan]")

        # Check if the agent is available before announcing it
        if not agent.is_available():
            # Show that the preferred agent is not available
            if agent_name:
                console.print(
                    f"  [red]❌[/red] {agent.config.display_name} - [yellow]Not available (requested)[/yellow]"
                )
            else:
                console.print(
                    f"  [red]❌[/red] {agent.config.display_name} - [yellow]Not available (default)[/yellow]"
                )

            # Try to find an available fallback agent with detailed logging
            fallback_agent = self._find_fallback_agent_with_logging(agent.config.name)
            if fallback_agent:
                console.print(
                    f"  [green]✅[/green] {fallback_agent.config.display_name} - [green]Selected for analysis[/green]"
                )
                console.print()
                agent = fallback_agent
            else:
                console.print("[red]No available AI agents found[/red]")
                return None
        else:
            # Show which agent we're using (only if it's available)
            console.print(
                f"  [green]✅[/green] {agent.config.display_name} - [green]Selected for analysis[/green]"
            )
            console.print()

        # Use the agent (either original or fallback)
        if verbose:
            verbose_print(
                f"  [cyan]exec: Using AI agent: {agent.config.display_name}[/cyan]"
            )

        try:
            result = agent.analyze_logs(prompt)
            return result
        except Exception as e:
            if verbose:
                verbose_print(f"  [cyan]exec: Agent analysis failed: {e}[/cyan]")
            console.print(f"[red]AI analysis failed: {e}[/red]")
            return None

    def _find_fallback_agent_with_logging(
        self, failed_agent_name: str
    ) -> Optional[Any]:
        """Find an available fallback agent with detailed logging"""
        # Get fallback order from agent manager config or use configured agents
        try:
            # Try to get fallback order from ai_agents_config.json
            import json
            from pathlib import Path

            config_file = Path("ai_agents_config.json")
            if config_file.exists():
                with open(config_file, "r") as f:
                    config_data = json.load(f)
                    fallback_order = config_data.get("agent_preferences", {}).get(
                        "fallback_order", []
                    )
            else:
                fallback_order = []

            # If no fallback order in config, use all configured agents
            if not fallback_order:
                fallback_order = list(ai_agent_manager.agents.keys())

        except Exception:
            # Fallback to hardcoded list if config reading fails
            fallback_order = [
                "vllm-qwen25",
                "claude-sonnet",
                "gpt-4",
                "claude-haiku",
                "gpt-3.5-turbo",
            ]

        # Remove the failed agent from fallback order
        if failed_agent_name in fallback_order:
            fallback_order.remove(failed_agent_name)

        # Try each agent in fallback order with logging
        for agent_name in fallback_order:
            agent = ai_agent_manager.get_agent(agent_name)
            if agent:
                if agent.is_available():
                    console.print(
                        f"  [green]✅[/green] {agent.config.display_name} - [green]Available (fallback)[/green]"
                    )
                    return agent
                else:
                    # Show more detailed reason for unavailability
                    reason = self._get_unavailability_reason(agent)
                    console.print(
                        f"  [red]❌[/red] {agent.config.display_name} - [yellow]{reason}[/yellow]"
                    )
            else:
                console.print(
                    f"  [red]❌[/red] {agent_name} - [yellow]Agent not configured[/yellow]"
                )

        # If no specific fallback found, try any available agent
        console.print("  [cyan]Checking all configured agents...[/cyan]")
        available_agents = ai_agent_manager.list_available_agents()
        if available_agents:
            # Filter out the failed agent
            available_agents = [
                name for name in available_agents if name != failed_agent_name
            ]
            if available_agents:
                agent = ai_agent_manager.get_agent(available_agents[0])
                if agent:
                    console.print(
                        f"  [green]✅[/green] {agent.config.display_name} - [green]Available (any available)[/green]"
                    )
                    return agent

        console.print("  [red]❌[/red] No available AI agents found")
        return None

    def _get_unavailability_reason(self, agent) -> str:
        """Get a detailed reason why an agent is unavailable"""
        try:
            if agent.config.agent_type == "local_vllm":
                if not agent.config.endpoint:
                    return "No endpoint configured"
                # Try to determine if it's a network issue or service down
                import requests

                try:
                    response = requests.get(
                        f"{agent.config.endpoint}/health", timeout=2
                    )
                    if response.status_code != 200:
                        return f"Service unhealthy (HTTP {response.status_code})"
                except requests.ConnectionError:
                    return "Connection refused (service not running)"
                except requests.Timeout:
                    return "Connection timeout"
                except Exception as e:
                    return f"Network error: {str(e)[:30]}..."
                return "Service check failed"
            elif agent.config.agent_type in ["claude", "openai"]:
                import os

                api_key_env = agent.config.api_key_env or (
                    "ANTHROPIC_API_KEY"
                    if agent.config.agent_type == "claude"
                    else "OPENAI_API_KEY"
                )
                if not os.getenv(api_key_env):
                    return f"Missing {api_key_env} environment variable"
                return "API key configured but service unavailable"
            else:
                return "Unknown agent type"
        except Exception:
            return "Not available"

    def _find_fallback_agent(self, failed_agent_name: str) -> Optional[Any]:
        """Find an available fallback agent (legacy method for compatibility)"""
        return self._find_fallback_agent_with_logging(failed_agent_name)
