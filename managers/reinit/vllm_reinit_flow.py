"""vLLM-specific reinit flow management."""

from datetime import datetime

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
        verbose_print("[cyan]Detecting active vLLM model using port 8005[/cyan]")
        current_container = self.vllm_manager._find_current_vllm_container()
        verbose_print(
            f"[cyan]Detection result: current_container = {current_container}[/cyan]"
        )

        # Always show detection result first
        if current_container:
            console.print(f"[green]Current 8005: {current_container}[/green]")
            console.print()
        else:
            console.print("[yellow]No active vLLM model detected on port 8005[/yellow]")
            console.print()

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

        # Stop the current active vLLM model using systemctl
        stop_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{stop_timestamp} | Stopping {current_container}...[/green]"
        )
        stop_result = self.service_manager.stop_service(
            f"{current_container}.service", current_container, quiet=True
        )
        stopped_timestamp = datetime.now().strftime("%H:%M:%S")
        if stop_result.returncode == 0:
            console.print(
                f"[green]{stopped_timestamp} |   Stopped {current_container}[/green]"
            )
        else:
            console.print(
                f"[yellow]{stopped_timestamp} |   {current_container} was not running or failed to stop[/yellow]"
            )
        console.print()

        # Reload systemd daemon
        if not self.service_manager.reload_daemon():
            return False
        console.print()

        # Start the new vLLM model
        start_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{start_timestamp} | Restarting {display_name}...[/green]"
        )
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

        started_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{started_timestamp} |   Restarted {display_name}[/green]"
        )
        console.print()

        # Restart sys-services-vllm-proxy and mcp-vllm-delegator without spinners
        success = self._restart_vllm_support_services_no_spinner(display_name)
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
        start_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{start_timestamp} | Restarting {display_name}...[/green]"
        )
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

        started_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{started_timestamp} |   Restarted {display_name}[/green]"
        )
        console.print()

        # Restart sys-services-vllm-proxy and mcp-vllm-delegator without spinners
        success = self._restart_vllm_support_services_no_spinner(display_name)
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
            # Import the global ai_agent_manager
            from ai_system.ai_agents import ai_agent_manager

            # Get the default agent from the manager
            default_agent = ai_agent_manager.get_agent()
            if default_agent:
                agent_name = default_agent.config.display_name
                agent_type = default_agent.config.agent_type
                return f"{agent_name} ({agent_type})"
            else:
                # Check if there are any configured agents
                available_agents = ai_agent_manager.list_available_agents()
                if available_agents:
                    return f"Agents configured but none available: {', '.join(available_agents)}"
                else:
                    all_agents = ai_agent_manager.list_agents()
                    if all_agents:
                        return f"Agents configured but unavailable: {', '.join(all_agents)}"
                    else:
                        return "No AI agents configured"
        except Exception as e:
            return f"AI agent detection failed: {str(e)}"

    def _restart_vllm_support_services_no_spinner(self, display_name: str) -> bool:
        """Restart sys-services-vllm-proxy and mcp-vllm-delegator services without spinners"""
        verbose_print(
            f"[cyan]restart_vllm_support_services_no_spinner called for {display_name}[/cyan]"
        )

        # Stop sys-services-vllm-proxy using systemctl
        stop_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{stop_timestamp} | Stopping sys-services-vllm-proxy...[/green]"
        )
        stop_result = self.service_manager.stop_service(
            "sys-services-vllm-proxy.service", "sys-services-vllm-proxy", quiet=True
        )
        stopped_timestamp = datetime.now().strftime("%H:%M:%S")
        if stop_result.returncode == 0:
            console.print(
                f"[green]{stopped_timestamp} |   Stopped sys-services-vllm-proxy[/green]"
            )
        else:
            console.print(
                f"[yellow]{stopped_timestamp} |   sys-services-vllm-proxy was not running or failed to stop[/yellow]"
            )
        console.print()

        # Start sys-services-vllm-proxy using systemctl
        start_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{start_timestamp} | Starting sys-services-vllm-proxy...[/green]"
        )
        start_result = self.service_manager.start_service(
            "sys-services-vllm-proxy.service", "sys-services-vllm-proxy", quiet=False
        )
        started_timestamp = datetime.now().strftime("%H:%M:%S")
        if start_result.returncode == 0:
            console.print(
                f"[green]{started_timestamp} |   Started sys-services-vllm-proxy[/green]"
            )
        else:
            console.print(
                f"[red]{started_timestamp} |   Failed to start sys-services-vllm-proxy[/red]"
            )
            return False
        console.print()
        console.print()

        # Start mcp-vllm-delegator using systemctl
        start_timestamp2 = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{start_timestamp2} | Starting mcp-vllm-delegator...[/green]"
        )
        start_result = self.service_manager.start_service(
            "mcp-vllm-delegator.service", "mcp-vllm-delegator", quiet=False
        )
        started_timestamp2 = datetime.now().strftime("%H:%M:%S")
        if start_result.returncode == 0:
            console.print(
                f"[green]{started_timestamp2} |   Started mcp-vllm-delegator[/green]"
            )
        else:
            console.print(
                f"[red]{started_timestamp2} |   Failed to start mcp-vllm-delegator[/red]"
            )
            return False
        console.print()

        success_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{success_timestamp} | Successfully reinitialized {display_name}[/green]"
        )
        return True
