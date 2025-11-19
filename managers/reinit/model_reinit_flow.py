"""Model-specific reinit flow management for VLLM and llama.cpp models.

Supports the models-stack architecture where both VLLM and llama.cpp models use port 8005
and only one model runs at a time."""

from datetime import datetime

from core.config import console, verbose_print
from docs.model_startup_monitor import ModelStartupMonitor


class ModelReinitFlow:
    """Handles model service reinit flows (VLLM and llama.cpp) with proper routing and container management.

    Supports the models-stack architecture:
    - llama-kimi-k2-thinking_q1/q2 (llama.cpp models)
    - vllm-deepseek-coder-v2, vllm-glm4-9b-chat, vllm-glm41-9b-thinking, vllm-qwen25-coder-32b (VLLM models)

    All models use port 8005 and only one runs at a time.
    """

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
        """Lazy initialization of model startup monitor"""
        if not hasattr(self, "_startup_monitor") or self._startup_monitor is None:
            self._startup_monitor = ModelStartupMonitor(self.manager)
        return self._startup_monitor

    def reinit_model_service(
        self, target: str, service_name: str, dry_run: bool = False
    ) -> bool:
        """Handle model service reinit (VLLM or llama.cpp) - routes to appropriate flow based on active model detection"""
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

        # Detection step - find current active model (VLLM or llama.cpp)
        console.print("[cyan]Detecting active model using port 8005...[/cyan]")
        current_container = self.vllm_manager._find_current_vllm_container()
        verbose_print(
            f"[cyan]Detection result: current_container = {current_container}[/cyan]"
        )

        # Always show detection result first
        if current_container:
            # Detect model type for display
            model_type = self._detect_model_type(current_container)
            console.print(
                f"[green]Current 8005: {current_container} ({model_type})[/green]"
            )
            console.print()
        else:
            console.print("[yellow]No active model detected on port 8005[/yellow]")
            console.print()

        # Ensure we only follow one path to prevent duplicate service restarts
        if current_container:
            # Route to active model flow
            model_type = self._detect_model_type(current_container)
            verbose_print(
                f"[cyan]Detected active {model_type} container: {current_container}, using active flow[/cyan]"
            )
            result = self._reinit_active_model_service(
                target, service_name, current_container
            )
            console.print(f"  Active flow completed with result: {result}")
            return result
        else:
            # Route to non-active model flow
            verbose_print(
                "[cyan]No active model container detected, using non-active flow[/cyan]"
            )
            result = self._reinit_non_active_model_service(target, service_name)
            console.print(f"  Active flow completed with result: {result}")
            return result

    def _reinit_active_model_service(
        self, target: str, service_name: str, current_container: str
    ) -> bool:
        """Handle model reinit when there's an active model (VLLM or llama.cpp)"""
        verbose_print(
            f"[cyan]_reinit_active_model_service started for {service_name} with current_container={current_container}[/cyan]"
        )
        display_name = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )

        # Stop the current active model using model manager's robust stopping mechanism
        stop_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{stop_timestamp} | Stopping {current_container}...[/green]"
        )

        # Import spinner utility
        from ai_analyzer.spinner_manager import safe_spinner
        from core.config import _verbose_enabled

        # Use model manager's silent stopping method which has better timeout handling
        with safe_spinner(
            f"Stopping {current_container}...", console, verbose=_verbose_enabled
        ):
            stop_success = self.vllm_manager._stop_known_vllm_model_silent(
                current_container
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

        # Start the new model
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

        # Wait for model to be completely ready before restarting support services
        console.print(f"  Waiting for {display_name} to be fully ready...")
        if not self.startup_monitor.monitor_model_startup(display_name):
            console.print(f"  ❌ {display_name} failed to become ready")
            console.print("  Active flow completed with result: False")
            console.print()
            started_timestamp = datetime.now().strftime("%H:%M:%S")
            console.print(
                f"[green]{started_timestamp} |   Restarted {display_name}[/green]"
            )
            return False

        started_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{started_timestamp} |   Restarted {display_name}[/green]"
        )

        # Model is now fully ready
        ready_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{ready_timestamp} |   {display_name} is fully ready[/green]"
        )
        console.print()

        # Restart sys-services-model-proxy and mcp-model-delegator
        success = self.restart_model_support_services(display_name)
        verbose_print(
            f"[cyan]Active model service reinit completed with success={success}[/cyan]"
        )
        return success

    def _reinit_non_active_model_service(self, target: str, service_name: str) -> bool:
        """Handle model reinit when there's no active model"""
        verbose_print(
            f"[cyan]_reinit_non_active_model_service started for {service_name}[/cyan]"
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

        # Start the new model
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

        # Wait for model to be completely ready before restarting support services
        console.print(f"  Waiting for {display_name} to be fully ready...")
        if not self.startup_monitor.monitor_model_startup(display_name):
            console.print(f"  ❌ {display_name} failed to become ready")
            console.print("  Active flow completed with result: False")
            console.print()
            started_timestamp = datetime.now().strftime("%H:%M:%S")
            console.print(
                f"[green]{started_timestamp} |   Restarted {display_name}[/green]"
            )
            return False

        started_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{started_timestamp} |   Restarted {display_name}[/green]"
        )

        # Model is now fully ready
        ready_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{ready_timestamp} |   {display_name} is fully ready[/green]"
        )
        console.print()

        # Restart sys-services-model-proxy and mcp-vllm-delegator
        success = self.restart_model_support_services(display_name)
        verbose_print(
            f"[cyan]Non-active model service reinit completed with success={success}[/cyan]"
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

        # Check if this is a llama.cpp service and try specialized troubleshooting first
        if self._is_llama_cpp_service(target):
            if self._try_llama_cpp_troubleshooting(target, error_message):
                return  # Specialized troubleshooting handled the issue

        console.print("[dim]Starting AI failure analysis...[/dim]")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            # Create analyzer instance with manager
            analyzer = AIAnalyzer(self.manager)

            # Detect if this is a timeout scenario based on error patterns
            analysis_type = self._detect_failure_type(error_message)

            # Prepare context data based on failure type
            context_data = {"start_error": error_message}

            if analysis_type == "timeout_diagnostic":
                # Add timeout-specific context
                context_data.update(
                    {
                        "timeout_context": {
                            "commands_timing_out": [
                                "podman inspect",
                                "podman ps",
                                "journalctl",
                            ],
                            "container_status": "error",
                            "system_responsiveness": "degraded",
                        },
                        "system_state": {
                            "container_runtime": "potentially_hung",
                            "systemd_status": "unknown_due_to_timeouts",
                        },
                    }
                )

            # Run unified AI analysis with error context and verbose mode
            # The analyzer will handle AI agent selection and display
            result = analyzer.ai_analyze(
                analysis_type=analysis_type,
                target=target,
                context_data=context_data,
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

    def _detect_failure_type(self, error_message: str) -> str:
        """Detect the type of failure based on error patterns to choose appropriate analysis."""
        error_lower = error_message.lower() if error_message else ""

        # Check for timeout indicators
        timeout_indicators = [
            "timeout",
            "timed out",
            "command timeout",
            "connection timeout",
            "no response",
            "unresponsive",
            "hanging",
            "stuck",
        ]

        # Check for container runtime issues
        runtime_indicators = [
            "container status: error",
            "podman inspect",
            "container runtime",
            "runtime error",
            "container not found",
            "runtime unavailable",
        ]

        # Check for system resource issues
        resource_indicators = [
            "out of memory",
            "disk space",
            "resource exhausted",
            "no space left",
            "memory allocation",
            "resource limit",
        ]

        if any(indicator in error_lower for indicator in timeout_indicators):
            return "timeout_diagnostic"
        elif any(indicator in error_lower for indicator in runtime_indicators):
            return "container_runtime_diagnostic"
        elif any(indicator in error_lower for indicator in resource_indicators):
            return "system_health_check"
        else:
            # Default to standard reinit failure analysis
            return "reinit_failure"

    def restart_model_support_services(self, display_name: str) -> bool:
        """Restart sys-services-model-proxy and mcp-model-delegator services"""
        verbose_print(
            f"[cyan]restart_model_support_services called for {display_name}[/cyan]"
        )

        # Stop sys-services-model-proxy using systemctl
        stop_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{stop_timestamp} | Stopping sys-services-model-proxy...[/green]"
        )
        stop_result = self.service_manager.stop_service(
            "sys-services-model-proxy.service", "sys-services-model-proxy", quiet=False
        )
        stopped_timestamp = datetime.now().strftime("%H:%M:%S")
        if stop_result.returncode == 0:
            console.print(
                f"[green]{stopped_timestamp} |   Stopped sys-services-model-proxy[/green]"
            )
        else:
            console.print(
                f"[yellow]{stopped_timestamp} |   sys-services-model-proxy was not running or failed to stop[/yellow]"
            )
        console.print()

        # Show MODEL_VLLM update message
        vllm_url = f"http://{display_name}:8005"
        console.print(f"[cyan]Updating MODEL_VLLM to: {vllm_url}[/cyan]")
        console.print()

        # Update MODEL_VLLM in container file before service regeneration
        self._update_container_file_model_url("sys-services-model-proxy", vllm_url)

        # Remove service file to allow regeneration with updated MODEL_VLLM
        self.service_manager.remove_service_file(
            "sys-services-model-proxy.service", dry_run=False
        )
        console.print()

        # Reload systemd daemon
        if not self.service_manager.reload_daemon():
            return False
        console.print()

        # Start sys-services-model-proxy using systemctl (this will regenerate the service with new MODEL_VLLM)
        start_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{start_timestamp} | Restarting sys-services-model-proxy...[/green]"
        )
        start_result = self.service_manager.start_service(
            "sys-services-model-proxy.service", "sys-services-model-proxy", quiet=False
        )
        started_timestamp = datetime.now().strftime("%H:%M:%S")
        if start_result.returncode == 0:
            console.print(
                f"[green]{started_timestamp} |   Restarted sys-services-model-proxy[/green]"
            )
        else:
            console.print(
                f"[red]{started_timestamp} |   Failed to restart sys-services-model-proxy[/red]"
            )
            return False
        console.print()

        # Stop mcp-model-delegator using systemctl
        stop_timestamp2 = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{stop_timestamp2} | Stopping mcp-model-delegator...[/green]"
        )
        stop_result2 = self.service_manager.stop_service(
            "mcp-model-delegator.service", "mcp-model-delegator", quiet=False
        )
        stopped_timestamp2 = datetime.now().strftime("%H:%M:%S")
        if stop_result2.returncode == 0:
            console.print(
                f"[green]{stopped_timestamp2} |   Stopped mcp-model-delegator[/green]"
            )
        else:
            console.print(
                f"[yellow]{stopped_timestamp2} |   mcp-model-delegator was not running or failed to stop[/yellow]"
            )
        console.print()

        # Note: mcp-model-delegator does not use MODEL_VLLM, so no container file update needed

        # Remove mcp-model-delegator service file to allow regeneration
        self.service_manager.remove_service_file(
            "mcp-model-delegator.service", dry_run=False
        )
        console.print()

        # Reload systemd daemon again after removing mcp-model-delegator service file
        if not self.service_manager.reload_daemon():
            return False
        console.print()

        # Start mcp-model-delegator using systemctl
        start_timestamp2 = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{start_timestamp2} | Restarting mcp-model-delegator...[/green]"
        )
        start_result = self.service_manager.start_service(
            "mcp-model-delegator.service", "mcp-model-delegator", quiet=False
        )
        started_timestamp2 = datetime.now().strftime("%H:%M:%S")
        if start_result.returncode == 0:
            console.print(
                f"[green]{started_timestamp2} |   Restarted mcp-model-delegator[/green]"
            )
        else:
            console.print(
                f"[red]{started_timestamp2} |   Failed to restart mcp-model-delegator[/red]"
            )
            return False
        console.print()

        success_timestamp = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"[green]{success_timestamp} | Successfully reinitialized {display_name}[/green]"
        )

        # Restore placeholder values in container files for future reinits
        # Note: Only sys-services-model-proxy uses MODEL_VLLM, mcp-model-delegator does not
        self._restore_container_file_model_url("sys-services-model-proxy")

        return True

    def _detect_model_type(self, container_name: str) -> str:
        """Detect if container is VLLM or llama.cpp model"""
        if container_name.startswith("vllm-"):
            return "VLLM"
        elif container_name.startswith("llama-"):
            return "llama.cpp"
        else:
            return "model"

    def _update_container_file_model_url(
        self, container_name: str, vllm_url: str
    ) -> bool:
        """Update MODEL_VLLM or MODEL_URL in the container file to replace REPLACED-DURING-REINIT placeholder.

        Handles both old format (direct replacement) and new format (environment variable substitution).
        Also handles MODEL_URL as an alternative to MODEL_VLLM.
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

            # Check if using old format (direct replacement in container file) - MODEL_VLLM
            if "Environment=MODEL_VLLM=REPLACED-DURING-REINIT" in content:
                updated_content = content.replace(
                    "Environment=MODEL_VLLM=REPLACED-DURING-REINIT",
                    f"Environment=MODEL_VLLM={vllm_url}",
                )

                with open(container_file_path, "w") as f:
                    f.write(updated_content)

                verbose_print(
                    f"[cyan]Updated {container_name}.container with MODEL_VLLM={vllm_url} (old format)[/cyan]"
                )
                return True

            # Check if using old format (direct replacement in container file) - MODEL_URL
            elif "Environment=MODEL_URL=REPLACED-DURING-REINIT" in content:
                updated_content = content.replace(
                    "Environment=MODEL_URL=REPLACED-DURING-REINIT",
                    f"Environment=MODEL_URL={vllm_url}",
                )

                with open(container_file_path, "w") as f:
                    f.write(updated_content)

                verbose_print(
                    f"[cyan]Updated {container_name}.container with MODEL_URL={vllm_url} (old format)[/cyan]"
                )
                return True

            # Check if using new format (environment variable substitution) - MODEL_VLLM
            elif "Environment=MODEL_VLLM=${MODEL_VLLM}" in content:
                # Update the .env file instead
                env_file_path = container_file_path.parent / ".env"
                return self._update_env_file_model_vllm(env_file_path, vllm_url)

            # Check if using new format (environment variable substitution) - MODEL_URL
            elif "Environment=MODEL_URL=${MODEL_URL}" in content:
                # Update using systemctl set-environment for MODEL_URL
                return self._update_env_file_model_url(vllm_url)

            else:
                verbose_print(
                    f"[yellow]No MODEL_VLLM or MODEL_URL found in {container_name}.container[/yellow]"
                )
                return False

        except Exception as e:
            verbose_print(f"[cyan]Error updating container file: {e}[/cyan]")
            return False

    def _update_env_file_model_vllm(self, env_file_path, vllm_url: str) -> bool:
        """Update MODEL_VLLM using systemctl --user set-environment for environment variable substitution."""
        import subprocess

        try:
            # Use systemctl --user set-environment to set MODEL_VLLM
            cmd = ["systemctl", "--user", "set-environment", f"MODEL_VLLM={vllm_url}"]
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            verbose_print(
                f"[cyan]Set user environment MODEL_VLLM={vllm_url} via systemctl (new format)[/cyan]"
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

    def _update_env_file_model_url(self, vllm_url: str) -> bool:
        """Update MODEL_URL using systemctl --user set-environment for environment variable substitution."""
        import subprocess

        try:
            # Use systemctl --user set-environment to set MODEL_URL
            cmd = ["systemctl", "--user", "set-environment", f"MODEL_URL={vllm_url}"]
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            verbose_print(
                f"[cyan]Set user environment MODEL_URL={vllm_url} via systemctl (new format)[/cyan]"
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

    def _restore_container_file_model_url(self, container_name: str) -> bool:
        """Restore MODEL_VLLM or MODEL_URL placeholder in container file for future reinits.

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

            # Check if using old format (direct replacement in container file) - MODEL_VLLM
            if "Environment=MODEL_VLLM=http://" in content:
                import re

                updated_content = re.sub(
                    r"Environment=MODEL_VLLM=http://[^:\s]+:8005",
                    "Environment=MODEL_VLLM=REPLACED-DURING-REINIT",
                    content,
                )

                with open(container_file_path, "w") as f:
                    f.write(updated_content)

                verbose_print(
                    f"[cyan]Restored {container_name}.container MODEL_VLLM placeholder (old format)[/cyan]"
                )
                return True

            # Check if using old format (direct replacement in container file) - MODEL_URL
            elif "Environment=MODEL_URL=http://" in content:
                import re

                updated_content = re.sub(
                    r"Environment=MODEL_URL=http://[^:\s]+:8005",
                    "Environment=MODEL_URL=REPLACED-DURING-REINIT",
                    content,
                )

                with open(container_file_path, "w") as f:
                    f.write(updated_content)

                verbose_print(
                    f"[cyan]Restored {container_name}.container MODEL_URL placeholder (old format)[/cyan]"
                )
                return True

            # Check if using new format (environment variable substitution) - MODEL_VLLM
            elif "Environment=MODEL_VLLM=${MODEL_VLLM}" in content:
                # Remove MODEL_VLLM from .env file
                env_file_path = container_file_path.parent / ".env"
                return self._remove_env_file_model_vllm(env_file_path)

            # Check if using new format (environment variable substitution) - MODEL_URL
            elif "Environment=MODEL_URL=${MODEL_URL}" in content:
                # Remove MODEL_URL from user environment
                return self._remove_env_file_model_url()

            else:
                verbose_print(
                    f"[cyan]No MODEL_VLLM or MODEL_URL found to restore in {container_name}.container[/cyan]"
                )
                return True  # Nothing to restore is not an error

        except Exception as e:
            verbose_print(f"[cyan]Error restoring container file: {e}[/cyan]")
            return False

    def _remove_env_file_model_vllm(self, env_file_path) -> bool:
        """Remove MODEL_VLLM from user environment using systemctl --user unset-environment."""
        import subprocess

        try:
            # Use systemctl --user unset-environment to remove MODEL_VLLM
            cmd = ["systemctl", "--user", "unset-environment", "MODEL_VLLM"]
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            verbose_print(
                "[cyan]Unset user environment MODEL_VLLM via systemctl (new format cleanup)[/cyan]"
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

    def _remove_env_file_model_url(self) -> bool:
        """Remove MODEL_URL from user environment using systemctl --user unset-environment."""
        import subprocess

        try:
            # Use systemctl --user unset-environment to remove MODEL_URL
            cmd = ["systemctl", "--user", "unset-environment", "MODEL_URL"]
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            verbose_print(
                "[cyan]Unset user environment MODEL_URL via systemctl (new format cleanup)[/cyan]"
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

    def _is_llama_cpp_service(self, target: str) -> bool:
        """Check if the target is a llama.cpp service."""
        # Check if it's a llama.cpp service based on naming patterns
        llama_patterns = ["llama-", "llama_"]
        return any(pattern in target.lower() for pattern in llama_patterns)

    def _try_llama_cpp_troubleshooting(self, target: str, error_message: str) -> bool:
        """Try specialized llama.cpp troubleshooting.

        Returns:
            True if the issue was automatically fixed, False otherwise
        """
        try:
            from ai_analyzer.llama_cpp_troubleshooter import LlamaCppTroubleshooter

            console.print(
                "[cyan]🔍 Running specialized llama.cpp diagnostics...[/cyan]"
            )

            troubleshooter = LlamaCppTroubleshooter()

            # Get recent logs for diagnosis
            logs = self._get_recent_service_logs(target)

            # Diagnose the issue
            diagnosis = troubleshooter.diagnose_service_failure(
                target, error_message + "\n" + logs
            )

            # Generate and display the troubleshooting report
            report = troubleshooter.generate_troubleshooting_report(diagnosis)
            console.print(
                "\n[bold cyan]🔧 llama.cpp Troubleshooting Report:[/bold cyan]"
            )
            console.print("[cyan]" + "─" * 60 + "[/cyan]")
            for line in report.split("\n"):
                if line.strip():
                    console.print(f"[cyan]{line}[/cyan]")
            console.print("[cyan]" + "─" * 60 + "[/cyan]")

            # Try automatic fix if available
            if diagnosis["auto_fixable"]:
                console.print("\n[green]⚡ Automatic fix available![/green]")

                # Ask user for permission to apply fix
                try:
                    import sys

                    if sys.stdin.isatty():  # Only prompt if running interactively
                        response = input("Apply automatic fix? (y/N): ").strip().lower()
                        if response in ["y", "yes"]:
                            console.print("[cyan]Applying automatic fix...[/cyan]")

                            # Apply the fix
                            for fix in diagnosis["suggested_fixes"]:
                                if fix.get("auto_fixable", False):
                                    if troubleshooter.apply_automatic_fix(fix):
                                        console.print(
                                            "[green]✅ Fix applied successfully![/green]"
                                        )
                                        console.print(
                                            "[cyan]Reloading systemd and restarting service...[/cyan]"
                                        )

                                        # Reload systemd daemon
                                        if self.service_manager.reload_daemon():
                                            # Try to restart the service
                                            start_result = (
                                                self.service_manager.start_service(
                                                    f"{target}.service",
                                                    target,
                                                    quiet=False,
                                                )
                                            )

                                            if start_result.returncode == 0:
                                                console.print(
                                                    "[green]🎉 Service restarted successfully after fix![/green]"
                                                )
                                                return True
                                            else:
                                                console.print(
                                                    "[yellow]⚠️  Fix applied but service still fails to start[/yellow]"
                                                )
                                                console.print(
                                                    "[dim]Continuing with standard AI analysis...[/dim]"
                                                )
                                        else:
                                            console.print(
                                                "[red]❌ Failed to reload systemd daemon[/red]"
                                            )
                                    else:
                                        console.print(
                                            "[red]❌ Failed to apply automatic fix[/red]"
                                        )
                                        console.print(
                                            "[dim]Continuing with standard AI analysis...[/dim]"
                                        )
                        else:
                            console.print("[yellow]Automatic fix not applied[/yellow]")
                            console.print(
                                "[dim]Continuing with standard AI analysis...[/dim]"
                            )
                    else:
                        console.print(
                            "[yellow]Non-interactive mode: automatic fix not applied[/yellow]"
                        )
                        console.print(
                            "[dim]Run with interactive terminal to apply fixes automatically[/dim]"
                        )
                        console.print(
                            "[dim]Continuing with standard AI analysis...[/dim]"
                        )
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[yellow]User cancelled fix application[/yellow]")
                    console.print("[dim]Continuing with standard AI analysis...[/dim]")
            else:
                console.print(
                    "\n[yellow]No automatic fix available for this issue[/yellow]"
                )
                console.print("[dim]Continuing with standard AI analysis...[/dim]")

            return False  # Continue with standard AI analysis

        except ImportError:
            verbose_print(
                "[cyan]llama.cpp troubleshooter not available, using standard analysis[/cyan]"
            )
            return False
        except Exception as e:
            verbose_print(f"[cyan]llama.cpp troubleshooting failed: {e}[/cyan]")
            console.print(
                f"[yellow]⚠️  Specialized troubleshooting failed: {e}[/yellow]"
            )
            console.print("[dim]Continuing with standard AI analysis...[/dim]")
            return False

    def _get_recent_service_logs(self, target: str, lines: int = 30) -> str:
        """Get recent service logs for troubleshooting.

        Args:
            target: Service name
            lines: Number of recent log lines to retrieve

        Returns:
            Recent log content or error message
        """
        import subprocess

        try:
            # Try to get logs with a timeout to avoid hanging
            result = subprocess.run(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    f"{target}.service",
                    "-n",
                    str(lines),
                    "--no-pager",
                ],
                capture_output=True,
                text=True,
                timeout=10,  # 10 second timeout
            )

            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error getting logs: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "Error: journalctl command timed out (system may be unresponsive)"
        except Exception as e:
            return f"Error getting logs: {e}"
