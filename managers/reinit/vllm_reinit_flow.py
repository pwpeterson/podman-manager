"""vLLM-specific reinit flow management."""

from datetime import datetime

from core.config import console, verbose_print
from managers.reinit.vllm_startup_monitor import VLLMStartupMonitor


class VLLMReinitFlow:
    """Handles vLLM model service reinit flows with proper routing and container management."""

    def __init__(self, manager, container_manager, service_manager):
        self.manager = manager
        self.container_manager = container_manager
        self.service_manager = service_manager
        self._vllm_manager = None
        self._startup_monitor = None

    @property
    def vllm_manager(self):
        """Lazy initialization of vLLM manager"""
        if self._vllm_manager is None:
            from managers.vllm_model_manager import VLLMModelManager

            self._vllm_manager = VLLMModelManager(self.manager)
        return self._vllm_manager

    @property
    def startup_monitor(self):
        """Lazy initialization of VLLM startup monitor"""
        if self._startup_monitor is None:
            self._startup_monitor = VLLMStartupMonitor(self.manager)
        return self._startup_monitor

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

        # Stop the current active vLLM model using vLLM manager's robust stopping mechanism
        stop_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{stop_timestamp} | Stopping {current_container}...[/green]"
        )

        # Import spinner utility
        from ai_analyzer.spinner_manager import safe_spinner
        from core.config import _verbose_enabled

        # Use vLLM manager's silent stopping method which has better timeout handling
        with safe_spinner(
            f"Stopping {current_container}...", console, verbose=_verbose_enabled
        ):
            stop_success = (
                self.vllm_manager._detect_and_stop_current_vllm_model_silent()
            )

        stopped_timestamp = datetime.now().strftime("%H:%M:%S")
        if stop_success:
            console.print(
                f"[green]{stopped_timestamp} |   Stopped {current_container}[/green]"
            )
        else:
            console.print(
                f"[yellow]{stopped_timestamp} |   {current_container} stop failed or timed out[/yellow]"
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

        # Wait for VLLM model to be completely ready before restarting support services
        console.print(f"[cyan]Waiting for {display_name} to be fully ready...[/cyan]")
        if not self.startup_monitor.vllm_service_monitor_for_complete_start(
            display_name
        ):
            console.print(f"[red]❌ {display_name} failed to become ready[/red]")
            return False
        console.print()

        # Restart sys-services-vllm-proxy and mcp-vllm-delegator
        success = self.restart_vllm_support_services(display_name)
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

        # Wait for VLLM model to be completely ready before restarting support services
        console.print(f"[cyan]Waiting for {display_name} to be fully ready...[/cyan]")
        if not self.startup_monitor.vllm_service_monitor_for_complete_start(
            display_name
        ):
            console.print(f"[red]❌ {display_name} failed to become ready[/red]")
            return False
        console.print()

        # Restart sys-services-vllm-proxy and mcp-vllm-delegator
        success = self.restart_vllm_support_services(display_name)
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

            # Run unified AI analysis with error context and verbose mode
            # The analyzer will handle AI agent selection and display
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

    def restart_vllm_support_services(self, display_name: str) -> bool:
        """Restart sys-services-vllm-proxy and mcp-vllm-delegator services"""
        verbose_print(
            f"[cyan]restart_vllm_support_services called for {display_name}[/cyan]"
        )

        # Stop sys-services-vllm-proxy using systemctl
        stop_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{stop_timestamp} | Stopping sys-services-vllm-proxy...[/green]"
        )
        stop_result = self.service_manager.stop_service(
            "sys-services-vllm-proxy.service", "sys-services-vllm-proxy", quiet=False
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

        # Show VLLM_URL update message
        vllm_url = f"http://{display_name}:8005"
        console.print(f"[cyan]Updating VLLM_URL to: {vllm_url}[/cyan]")
        console.print()

        # Update VLLM_URL in container file before service regeneration
        self._update_container_file_vllm_url("sys-services-vllm-proxy", vllm_url)

        # Remove service file to allow regeneration with updated VLLM_URL
        self.service_manager.remove_service_file(
            "sys-services-vllm-proxy.service", dry_run=False
        )
        console.print()

        # Reload systemd daemon
        if not self.service_manager.reload_daemon():
            return False
        console.print()

        # Start sys-services-vllm-proxy using systemctl (this will regenerate the service with new VLLM_URL)
        start_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{start_timestamp} | Restarting sys-services-vllm-proxy...[/green]"
        )
        start_result = self.service_manager.start_service(
            "sys-services-vllm-proxy.service", "sys-services-vllm-proxy", quiet=False
        )
        started_timestamp = datetime.now().strftime("%H:%M:%S")
        if start_result.returncode == 0:
            console.print(
                f"[green]{started_timestamp} |   Restarted sys-services-vllm-proxy[/green]"
            )
        else:
            console.print(
                f"[red]{started_timestamp} |   Failed to restart sys-services-vllm-proxy[/red]"
            )
            return False
        console.print()

        # Stop mcp-vllm-delegator using systemctl
        stop_timestamp2 = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{stop_timestamp2} | Stopping mcp-vllm-delegator...[/green]"
        )
        stop_result2 = self.service_manager.stop_service(
            "mcp-vllm-delegator.service", "mcp-vllm-delegator", quiet=False
        )
        stopped_timestamp2 = datetime.now().strftime("%H:%M:%S")
        if stop_result2.returncode == 0:
            console.print(
                f"[green]{stopped_timestamp2} |   Stopped mcp-vllm-delegator[/green]"
            )
        else:
            console.print(
                f"[yellow]{stopped_timestamp2} |   mcp-vllm-delegator was not running or failed to stop[/yellow]"
            )
        console.print()

        # Note: mcp-vllm-delegator does not use VLLM_URL, so no container file update needed

        # Remove mcp-vllm-delegator service file to allow regeneration
        self.service_manager.remove_service_file(
            "mcp-vllm-delegator.service", dry_run=False
        )
        console.print()

        # Reload systemd daemon again after removing mcp-vllm-delegator service file
        if not self.service_manager.reload_daemon():
            return False
        console.print()

        # Start mcp-vllm-delegator using systemctl
        start_timestamp2 = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{start_timestamp2} | Restarting mcp-vllm-delegator...[/green]"
        )
        start_result = self.service_manager.start_service(
            "mcp-vllm-delegator.service", "mcp-vllm-delegator", quiet=False
        )
        started_timestamp2 = datetime.now().strftime("%H:%M:%S")
        if start_result.returncode == 0:
            console.print(
                f"[green]{started_timestamp2} |   Restarted mcp-vllm-delegator[/green]"
            )
        else:
            console.print(
                f"[red]{started_timestamp2} |   Failed to restart mcp-vllm-delegator[/red]"
            )
            return False
        console.print()

        success_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{success_timestamp} | Successfully reinitialized {display_name}[/green]"
        )

        # Restore placeholder values in container files for future reinits
        # Note: Only sys-services-vllm-proxy uses VLLM_URL, mcp-vllm-delegator does not
        self._restore_container_file_vllm_url("sys-services-vllm-proxy")

        return True

    def _update_container_file_vllm_url(
        self, container_name: str, vllm_url: str
    ) -> bool:
        """Update VLLM_URL in the container file to replace REPLACED-DURING-REINIT placeholder.

        Handles both old format (direct replacement) and new format (environment variable substitution).
        """
        from pathlib import Path

        container_file_path = (
            Path.home() / ".config/containers/systemd" / f"{container_name}.container"
        )

        if not container_file_path.exists():
            verbose_print(
                f"[cyan]Container file not found: {container_file_path}[/cyan]"
            )
            return False

        try:
            # Read the current container file
            with open(container_file_path, "r") as f:
                content = f.read()

            # Check if using old format (direct replacement in container file)
            if "Environment=VLLM_URL=REPLACED-DURING-REINIT" in content:
                updated_content = content.replace(
                    "Environment=VLLM_URL=REPLACED-DURING-REINIT",
                    f"Environment=VLLM_URL={vllm_url}",
                )

                with open(container_file_path, "w") as f:
                    f.write(updated_content)

                verbose_print(
                    f"[cyan]Updated {container_name}.container with VLLM_URL={vllm_url} (old format)[/cyan]"
                )
                return True

            # Check if using new format (environment variable substitution)
            elif "Environment=VLLM_URL=${VLLM_URL}" in content:
                # Update the .env file instead
                env_file_path = container_file_path.parent / ".env"
                return self._update_env_file_vllm_url(env_file_path, vllm_url)

            else:
                verbose_print(
                    f"[yellow]No VLLM_URL found in {container_name}.container[/yellow]"
                )
                return False

        except Exception as e:
            verbose_print(f"[cyan]Error updating container file: {e}[/cyan]")
            return False

    def _update_env_file_vllm_url(self, env_file_path, vllm_url: str) -> bool:
        """Update VLLM_URL using systemctl --user set-environment for environment variable substitution."""
        import subprocess

        try:
            # Use systemctl --user set-environment to set VLLM_URL
            cmd = ["systemctl", "--user", "set-environment", f"VLLM_URL={vllm_url}"]
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            verbose_print(
                f"[cyan]Set user environment VLLM_URL={vllm_url} via systemctl (new format)[/cyan]"
            )
            return True

        except subprocess.CalledProcessError as e:
            verbose_print(
                f"[cyan]Error setting user environment via systemctl: {e}[/cyan]"
            )
            verbose_print(f"[cyan]stderr: {e.stderr}[/cyan]")
            return False
        except Exception as e:
            verbose_print(f"[cyan]Error updating user environment: {e}[/cyan]")
            return False

    def _restore_container_file_vllm_url(self, container_name: str) -> bool:
        """Restore VLLM_URL placeholder in container file for future reinits.

        Handles both old format (direct replacement) and new format (environment variable substitution).
        """
        from pathlib import Path

        container_file_path = (
            Path.home() / ".config/containers/systemd" / f"{container_name}.container"
        )

        if not container_file_path.exists():
            return False

        try:
            # Read the current container file
            with open(container_file_path, "r") as f:
                content = f.read()

            # Check if using old format (direct replacement in container file)
            if "Environment=VLLM_URL=http://" in content:
                import re

                updated_content = re.sub(
                    r"Environment=VLLM_URL=http://[^:\s]+:8005",
                    "Environment=VLLM_URL=REPLACED-DURING-REINIT",
                    content,
                )

                with open(container_file_path, "w") as f:
                    f.write(updated_content)

                verbose_print(
                    f"[cyan]Restored {container_name}.container VLLM_URL placeholder (old format)[/cyan]"
                )
                return True

            # Check if using new format (environment variable substitution)
            elif "Environment=VLLM_URL=${VLLM_URL}" in content:
                # Remove VLLM_URL from .env file
                env_file_path = container_file_path.parent / ".env"
                return self._remove_env_file_vllm_url(env_file_path)

            else:
                verbose_print(
                    f"[cyan]No VLLM_URL found to restore in {container_name}.container[/cyan]"
                )
                return True  # Nothing to restore is not an error

        except Exception as e:
            verbose_print(f"[cyan]Error restoring container file: {e}[/cyan]")
            return False

    def _remove_env_file_vllm_url(self, env_file_path) -> bool:
        """Remove VLLM_URL from user environment using systemctl --user unset-environment."""
        import subprocess

        try:
            # Use systemctl --user unset-environment to remove VLLM_URL
            cmd = ["systemctl", "--user", "unset-environment", "VLLM_URL"]
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            verbose_print(
                "[cyan]Unset user environment VLLM_URL via systemctl (new format cleanup)[/cyan]"
            )
            return True

        except subprocess.CalledProcessError as e:
            verbose_print(
                f"[cyan]Error unsetting user environment via systemctl: {e}[/cyan]"
            )
            verbose_print(f"[cyan]stderr: {e.stderr}[/cyan]")
            return False
        except Exception as e:
            verbose_print(f"[cyan]Error removing user environment: {e}[/cyan]")
            return False

    def _update_container_file_vllm_url_test(self, container_file_path, model_name):
        """Test version of container file update method."""
        return self._update_container_file_vllm_url(container_file_path, model_name)
