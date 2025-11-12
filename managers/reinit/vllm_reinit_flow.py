"""vLLM-specific reinit flow management."""

from core.config import console, verbose_print


class VLLMReinitFlow:
    """Handles vLLM model service reinit flows with proper routing and container management."""

    def __init__(self, manager, container_manager, service_manager):
        self.manager = manager
        self.container_manager = container_manager
        self.service_manager = service_manager
        self._vllm_manager = None

    @property
    def vllm_manager(self):
        """Lazy initialization of vLLM manager"""
        if self._vllm_manager is None:
            from managers.vllm_model_manager import VLLMModelManager

            self._vllm_manager = VLLMModelManager(self.manager)
        return self._vllm_manager

    def reinit_vllm_model_service(
        self, target: str, service_name: str, dry_run: bool = False
    ) -> bool:
        """Handle vLLM model service reinit - routes to appropriate flow based on active model detection"""
        display_name = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )

        if dry_run:
            console.print(
                f"[yellow]DRY RUN: Would reinitialize {display_name}[/yellow]"
            )
            return True

        # Detection step - find current active vLLM model
        verbose_print(
            f"[cyan]Starting vLLM container detection for {display_name}[/cyan]"
        )
        current_container = self.vllm_manager._find_current_vllm_container()
        verbose_print(
            f"[cyan]Detection result: current_container = {current_container}[/cyan]"
        )

        # Ensure we only follow one path to prevent duplicate service restarts
        if current_container:
            # Route to active vLLM model flow
            verbose_print(
                f"[cyan]Detected active vLLM container: {current_container}, using active flow[/cyan]"
            )
            result = self._reinit_active_vllm_model_service(
                target, service_name, current_container
            )
            verbose_print(f"[cyan]Active flow completed with result: {result}[/cyan]")
            return result
        else:
            # Route to non-active vLLM model flow
            verbose_print(
                "[cyan]No active vLLM container detected, using non-active flow[/cyan]"
            )
            result = self._reinit_non_active_vllm_model_service(target, service_name)
            verbose_print(
                f"[cyan]Non-active flow completed with result: {result}[/cyan]"
            )
            return result

    def _reinit_active_vllm_model_service(
        self, target: str, service_name: str, current_container: str
    ) -> bool:
        """Handle vLLM model reinit when there's an active vLLM model"""
        verbose_print(
            f"[cyan]_reinit_active_vllm_model_service started for {service_name} with current_container={current_container}[/cyan]"
        )
        display_name = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )

        # Show detection result
        console.print(f"[green]Current 8005: {current_container}[/green]")
        console.print()

        # Stop the current active vLLM model with polling-based monitoring
        if not self.container_manager.monitor_container_stop(current_container):
            console.print(
                f"[red]Failed to stop active vLLM model {current_container}[/red]"
            )
            return False
        console.print()

        # Remove the current active vLLM model
        console.print(f"[green]Removing {current_container}...[/green]")
        if self.container_manager.remove_container_with_message(current_container):
            console.print(f"[green]  Removed {current_container}[/green]")
        else:
            console.print(
                f"[yellow]  {current_container} was not found or failed to remove[/yellow]"
            )
        console.print()

        # Reload systemd daemon
        if not self.service_manager.reload_daemon():
            return False
        console.print()

        # Start the new vLLM model
        console.print(f"[green]Starting {display_name}...[/green]")
        start_result = self.service_manager.start_service(
            service_name, target, quiet=False
        )
        start_success = start_result.returncode == 0

        if not start_success:
            console.print(f"[red]  Failed to start {display_name}[/red]")
            self._handle_start_failure(target, start_result)
            error_message = start_result.stderr.strip() if start_result.stderr else ""
            self._run_reinit_failure_analysis(target, error_message)
            return False

        console.print(f"[green]  Started {display_name}[/green]")
        console.print()

        # Restart vllm-proxy and mcp-vllm-delegator
        success = self.container_manager.restart_vllm_support_services(display_name)
        verbose_print(
            f"[cyan]Active vLLM model service reinit completed with success={success}[/cyan]"
        )
        return success

    def _reinit_non_active_vllm_model_service(
        self, target: str, service_name: str
    ) -> bool:
        """Handle vLLM model reinit when there's no active vLLM model"""
        verbose_print(
            f"[cyan]_reinit_non_active_vllm_model_service started for {service_name}[/cyan]"
        )
        display_name = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )

        # Reload systemd daemon
        if not self.service_manager.reload_daemon():
            return False
        console.print()

        # Start the new vLLM model
        console.print(f"[green]Starting {display_name}...[/green]")
        start_result = self.service_manager.start_service(
            service_name, target, quiet=False
        )
        start_success = start_result.returncode == 0

        if not start_success:
            console.print(f"[red]  Failed to start {display_name}[/red]")
            self._handle_start_failure(target, start_result)
            error_message = start_result.stderr.strip() if start_result.stderr else ""
            self._run_reinit_failure_analysis(target, error_message)
            return False

        console.print(f"[green]  Started {display_name}[/green]")
        console.print()

        # Restart vllm-proxy and mcp-vllm-delegator
        success = self.container_manager.restart_vllm_support_services(display_name)
        verbose_print(
            f"[cyan]Non-active vLLM model service reinit completed with success={success}[/cyan]"
        )
        return success

    def _handle_start_failure(self, target: str, start_result) -> None:
        """Handle service start failure with detailed error reporting"""
        import re

        from core.config import _verbose_enabled

        # Extract and summarize the error message
        error_msg = start_result.stderr.strip()

        if "Job for" in error_msg and "failed because" in error_msg:
            # Extract service name from error
            service_match = re.search(r"Job for ([^\s]+) failed", error_msg)
            service_name_from_error = (
                service_match.group(1) if service_match else target
            )

            # Remove .service suffix from service name for display
            clean_service_name = service_name_from_error.replace(
                ".service", ""
            ).replace(".target", "")
            console.print(
                f"    [red]{clean_service_name} failed -[/red] [white]AI analysis will run automatically[/white]"
            )

        # Only show detailed error in verbose mode to avoid duplication
        if _verbose_enabled and error_msg:
            console.print("[red]❌ Complete systemd error message:[/red]")
            console.print("[dim]" + "─" * 60 + "[/dim]")
            # Split error message into lines and display with proper formatting
            for line in error_msg.split("\n"):
                if line.strip():
                    console.print(f"[red]{line}[/red]")
            console.print("[dim]" + "─" * 60 + "[/dim]")

            # In verbose mode, also show stdout if available
            if start_result.stdout and start_result.stdout.strip():
                console.print("[yellow]Additional output:[/yellow]")
                console.print("[dim]" + "─" * 60 + "[/dim]")
                for line in start_result.stdout.strip().split("\n"):
                    if line.strip():
                        console.print(f"[yellow]{line}[/yellow]")
                console.print("[dim]" + "─" * 60 + "[/dim]")

    def _run_reinit_failure_analysis(self, target: str, error_message: str) -> None:
        """Run AI analysis on reinit failure - consolidated method to avoid duplication."""
        import time

        from core.config import _verbose_enabled

        # Add a small delay to ensure any Rich displays are properly closed
        time.sleep(0.1)

        # Show error detection message and start AI analysis
        # Use the actual container name from fuzzy matching
        from core.simple_fuzzy_matcher import find_container

        container = find_container(target)
        container_name = container["name"] if container else target

        console.print(f"[red]{container_name} failed to start.[/red]")
        console.print("[dim]Starting AI failure analysis...[/dim]")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            # Create analyzer instance with manager
            analyzer = AIAnalyzer(self.manager)

            # Display which AI agent is being used
            ai_agent_info = self._get_ai_agent_info(analyzer)
            console.print(f"[cyan]Using AI agent: {ai_agent_info}[/cyan]\n")

            # Run unified AI analysis with error context and verbose mode
            result = analyzer.ai_analyze(
                analysis_type="reinit_failure",
                target=target,
                context_data={"start_error": error_message},
                ai_agent=None,
                verbose=_verbose_enabled,
            )

            if not result:
                console.print()
                console.print(
                    "[yellow]⚠️  AI analysis was unable to provide insights[/yellow]"
                )

        except ImportError as e:
            verbose_print(f"  [cyan]exec: AI analyzer import failed: {e}[/cyan]")
            console.print(
                "[red]❌ AI analyzer module not available: ai_analyzer module not found[/red]"
            )
            console.print(
                "[dim]Install ai_analyzer module to enable AI failure analysis[/dim]"
            )
        except Exception as e:
            verbose_print(f"  [cyan]exec: AI analysis failed with error: {e}[/cyan]")
            console.print(f"[yellow]⚠️  AI analysis failed: {e}[/yellow]")

    def _get_ai_agent_info(self, analyzer) -> str:
        """Get information about which AI agent is being used."""
        try:
            # Try to get the current AI agent from the analyzer
            if hasattr(analyzer, "current_agent") and analyzer.current_agent:
                agent_name = analyzer.current_agent.get("name", "Unknown")
                agent_type = analyzer.current_agent.get("agent_type", "Unknown")
                return f"{agent_name} ({agent_type})"
            elif hasattr(analyzer, "ai_agents") and analyzer.ai_agents:
                # Get the first available agent
                first_agent = next(iter(analyzer.ai_agents.values()), {})
                agent_name = first_agent.get("name", "Unknown")
                agent_type = first_agent.get("agent_type", "Unknown")
                return f"{agent_name} ({agent_type})"
            else:
                return "No AI agent configured"
        except Exception:
            return "AI agent detection failed"
