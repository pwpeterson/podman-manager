"""Reinit operations for services and stacks with advanced monitoring."""

import re
import subprocess
import time
from typing import TYPE_CHECKING, Optional

from rich.progress import Progress, SpinnerColumn, TextColumn

if TYPE_CHECKING:
    import requests
else:
    try:
        import requests
    except ImportError:
        requests = None

from core.config import console, verbose_print


class ReinitManager:
    """Handles complex reinit operations with monitoring and error handling"""

    def __init__(self, manager):
        self.manager = manager

    def reinit(
        self, target: str, build: bool = False, build_type: str | None = None
    ) -> bool:
        """Stop service, reload daemon, and restart service (useful for .container file changes)"""
        # Clear cache at the start
        self.manager._clear_auto_match_cache()

        # Handle backward compatibility - if build=True and no build_type, use legacy
        if build and build_type is None:
            build_type = "legacy"

        # PRIORITY 1: Check for stack names first (before trying service name resolution)
        # Handle legacy stack targets
        if target in ["vllm", "vllm-stack", "stack"]:
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack("vllm", build_type=build_type)
        elif target == "taskflow-stack":
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack("taskflow", build_type=build_type)
        elif target.endswith("-stack"):
            # Generic stack target
            project_name = target[:-6]  # Remove "-stack" suffix
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack(project_name, build_type=build_type)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        # Try to find it in discovered stacks before trying service resolution
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack(target, build_type=build_type)

        # PRIORITY 3: Check if container file exists first
        exists, resolved_service = self.manager._check_container_file_exists(
            target, "reinit"
        )
        if not exists:
            self.manager._show_install_suggestion(target)
            return False

        # PRIORITY 4: Try service name resolution (use resolved service if available)
        service_name = resolved_service or self.manager._find_service_name(
            target, "reinit"
        )

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            from stack_manager import StackManager

            stack_mgr = StackManager(self.manager)
            return stack_mgr.reinit_stack(stack_name, build_type=build_type)

        # PRIORITY 5: Handle individual service (only if not a stack)
        if service_name == "CANCELLED":
            # User cancelled fuzzy match selection, return silently
            return False
        elif service_name:
            return self._reinit_service_direct(
                target, service_name, build_type=build_type
            )
        else:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False

    def _reinit_service_direct(
        self, target: str, service_name: str, build_type: str | None = None
    ) -> bool:
        """Reinit a single service using already-resolved service name"""
        from core.config import _verbose_enabled

        # Use the actual service name for display (remove .service suffix if present)
        display_name = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )
        console.print(f"\n[green]Reinitializing {display_name}...[/green]\n")

        # Use the provided service_name to avoid duplicate resolution
        # Stop the service
        console.print(f"[green]Stopping {display_name}...[/green]")
        if not _verbose_enabled:
            console.print()
        stop_cmd = ["systemctl", "--user", "stop", service_name]
        verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
        stop_result = self.manager._run_systemctl_command(
            stop_cmd, f"stop_{target}", quiet=True
        )
        stop_success = stop_result.returncode == 0

        if not stop_success:
            console.print("[yellow]Service was not running or failed to stop[/yellow]")

        # Build if requested
        if build_type == "podman":
            console.print(f"[green]Building {target} (podman)...[/green]")
            from operations.container_builder import ContainerBuilder

            builder = ContainerBuilder(self.manager)
            build_success = builder.build_service_podman(target)
            if not build_success:
                console.print("[red]Failed to build images[/red]")
                return False
        elif build_type in ["legacy", "quadlet"]:
            console.print(f"[green]Building {target} (quadlet)...[/green]")
            from operations.container_builder import ContainerBuilder

            builder = ContainerBuilder(self.manager)
            build_success = builder.build_service(target)
            if not build_success:
                console.print("[red]Failed to build images[/red]")
                return False

        # Handle daemon reload
        console.print("[green]Reloading systemd daemon...[/green]")
        if not _verbose_enabled:
            console.print()

        if build_type not in ["legacy", "quadlet"]:
            reload_success = self.manager.reload_daemon()
            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False
        else:
            # Quadlet build script already reloaded daemon, add delay and force another reload
            time.sleep(3)
            reload_success = self.manager.reload_daemon()
            if not reload_success:
                console.print(
                    "[yellow]Warning: Additional daemon reload failed[/yellow]"
                )
            else:
                time.sleep(1)

        # Start the service using the resolved service name
        console.print(f"[green]Starting {display_name}...[/green]")
        if not _verbose_enabled:
            console.print()
        start_cmd = ["systemctl", "--user", "restart", service_name]

        start_result = self.manager._run_systemctl_command(
            start_cmd,
            f"start_{target}",
            quiet=False,  # Don't suppress output in verbose mode
        )
        start_success = start_result.returncode == 0

        # Add detailed health monitoring in verbose mode
        if _verbose_enabled and start_success:
            self._verbose_health_monitoring(target, service_name, display_name)

        # Handle start failure - delegate to _handle_start_failure to avoid duplication
        if not start_success:
            self._handle_start_failure(target, start_result)

        if start_success:
            # Monitor service logs to verify successful startup
            with Progress(
                SpinnerColumn(),
                TextColumn("[yellow]Monitoring service startup...[/yellow]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("monitoring", total=None)
                actual_success = self._monitor_service_startup(target, service_name)
                progress.remove_task(task)

            if actual_success:
                console.print(
                    f"\n[green]Successfully reinitialized {display_name}[/green]\n"
                )

                # Show optional next steps
                self._show_next_steps(target)
                return True
            else:
                # Service failed to start
                pass
                # Suggest service-specific journalctl command
                # Error message removed - automatic AI analysis will handle diagnostics
                pass

                # Add a small delay to ensure any Rich displays are properly closed
                time.sleep(0.1)

                # Show error detection message and start AI analysis
                console.print("\n[red]Error found in reinit command[/red]\n")
                console.print("[green]Starting AI analysis and diagnostics...[/green]")

                verbose_print("  [cyan]exec: ai_analyze(type=reinit_failure)[/cyan]")
                try:
                    from ai_analyzer import ai_analyzer
                    from core.config import _verbose_enabled

                    # Initialize ai_analyzer with manager if not already done
                    if ai_analyzer.manager is None:
                        ai_analyzer.manager = self.manager

                    # Run unified AI analysis with verbose mode
                    result = ai_analyzer.ai_analyze(
                        analysis_type="reinit_failure",
                        target=target,
                        context_data={
                            "start_error": "Service failed to start after reinit"
                        },
                        ai_agent=None,
                        verbose=_verbose_enabled,
                    )

                    if not result:
                        console.print()
                        console.print(
                            "[yellow]⚠ AI analysis was unable to provide insights[/yellow]"
                        )

                except Exception as e:
                    verbose_print(
                        f"  [cyan]exec: AI analysis failed with error: {e}[/cyan]"
                    )
                    console.print(f"[yellow]AI analysis failed: {e}[/yellow]")

                return False
        else:
            console.print(f"[red]Failed to start {display_name} after reinit[/red]")
            # Error details already handled by _handle_start_failure above

            # Add a small delay to ensure any Rich displays are properly closed
            time.sleep(0.1)

            # Show error detection message and start AI analysis
            console.print("\n[red]Error found in reinit command[/red]\n")
            console.print("[green]Starting AI analysis and diagnostics...[/green]")

            verbose_print(
                "  [cyan]exec: ai_analyze(type=reinit_failure, with_error)[/cyan]"
            )
            error_message = start_result.stderr.strip() if start_result.stderr else ""
            try:
                from ai_analyzer import ai_analyzer
                from core.config import _verbose_enabled

                # Initialize ai_analyzer with manager if not already done
                if ai_analyzer.manager is None:
                    ai_analyzer.manager = self.manager

                # Run unified AI analysis with error context and verbose mode
                result = ai_analyzer.ai_analyze(
                    analysis_type="reinit_failure",
                    target=target,
                    context_data={"start_error": error_message},
                    ai_agent=None,
                    verbose=_verbose_enabled,
                )

                if not result:
                    console.print()
                    console.print(
                        "[yellow]⚠ AI analysis was unable to provide insights[/yellow]"
                    )

            except Exception as e:
                verbose_print(
                    f"  [cyan]exec: AI analysis failed with error: {e}[/cyan]"
                )
                console.print(f"[yellow]AI analysis failed: {e}[/yellow]")

            return False

    def _handle_start_failure(self, target: str, start_result) -> None:
        """Handle service start failure with detailed error reporting"""
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

    def _monitor_service_startup(
        self, target: str, service_name: str, timeout: int = 10
    ) -> bool:
        """Monitor service logs to verify successful startup"""
        # Wait a moment for service to start
        time.sleep(10)

        # Check service status first
        status_cmd = ["systemctl", "--user", "is-active", service_name]
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)

        if status_result.returncode != 0:
            return False

        # Get recent logs to check for errors
        logs_cmd = [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "--since",
            "10 seconds ago",
            "-n",
            "20",
            "--no-pager",
        ]

        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)

        if logs_result.returncode == 0 and logs_result.stdout:
            log_content = logs_result.stdout.lower()

            # Check for common error patterns in logs
            error_patterns = [
                "error",
                "failed",
                "exception",
                "traceback",
                "fatal",
                "critical",
                "cannot",
                "unable to",
                "connection refused",
                "timeout",
                "permission denied",
            ]

            # Check for success patterns
            success_patterns = [
                "started",
                "listening",
                "ready",
                "running",
                "initialized",
                "server started",
            ]

            has_errors = any(pattern in log_content for pattern in error_patterns)
            has_success = any(pattern in log_content for pattern in success_patterns)

            if has_errors and not has_success:
                verbose_print(f"[red]Detected errors in {target} startup logs[/red]")
                return False
            elif has_success:
                verbose_print(f"[green]Service {target} started successfully[/green]")
                return True

        # If no clear success/failure indicators, assume success if service is active
        verbose_print(
            f"[yellow]Service {target} appears to be running (no clear startup indicators)[/yellow]"
        )
        return True

    def _show_startup_failure_logs(self, target: str, service_name: str) -> None:
        """Show recent logs when service fails to start properly"""
        # Get recent logs to show context for the failure
        logs_cmd = [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "--since",
            "-30s",
            "-n",
            "10",
            "--no-pager",
        ]

        verbose_print(f"  [cyan]exec: {' '.join(logs_cmd)}[/cyan]")

        try:
            result = subprocess.run(
                logs_cmd, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                console.print(
                    "[yellow]Journal extract for:[/yellow] [white]"
                    + target
                    + "[/white]"
                )
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        console.print(line)
            else:
                verbose_print(
                    f"  [cyan]exec: No recent logs found for {service_name}[/cyan]"
                )
        except subprocess.TimeoutExpired:
            verbose_print(
                f"  [cyan]exec: Timeout getting logs for {service_name}[/cyan]"
            )
        except Exception as e:
            verbose_print(
                f"  [cyan]exec: Error getting logs for {service_name}: {e}[/cyan]"
            )

    def _extract_core_service_name(self, service_name: str) -> str:
        """Extract the core service name for broader journalctl grep patterns.

        Examples:
        - 'local-ai-postgres' -> 'postgres'
        - 'vllm-api-server' -> 'vllm'
        - 'taskflow-redis' -> 'redis'
        - 'simple-service' -> 'simple-service'
        """
        # Common service types that should be extracted
        known_services = [
            "postgres",
            "postgresql",
            "redis",
            "mysql",
            "mariadb",
            "mongodb",
            "mongo",
            "nginx",
            "apache",
            "httpd",
            "caddy",
            "traefik",
            "elasticsearch",
            "kibana",
            "logstash",
            "rabbitmq",
            "kafka",
            "zookeeper",
            "memcached",
            "influxdb",
            "grafana",
            "prometheus",
            "docker",
            "podman",
            "containerd",
            "vllm",
            "ollama",
            "jupyter",
            "notebook",
        ]

        service_lower = service_name.lower()

        # Check if any known service is contained in the name
        for known in known_services:
            if known in service_lower:
                return known

        # If no known service found, try to extract the last part after the last dash
        # This handles cases like 'my-custom-app' -> 'app'
        parts = service_name.split("-")
        if len(parts) > 1:
            return parts[-1]

        # Fallback: return the original name
        return service_name

    def _show_next_steps(self, target: str) -> None:
        """Show optional next steps after successful reinit"""
        console.print("[green]Optional: commands:[/green]")
        console.print(
            f"[green] Check service status:[/green] [white]pm status {target}[/white]"
        )
        console.print(
            f"  [green] View detailed logs:[/green] [white]pm logs {target}[/white]"
        )
        console.print(
            f"  [green] Diagnose the issue:[/green] [white]pm diagnose {target}[/white]"
        )
        console.print(
            f"  [green] Reset failed state:[/green] [white]pm reset-failed {target}[/white]"
        )
        console.print()

    def _filter_error_warning_lines(self, stdout: str, stderr: str) -> str:
        """Filter output to extract only lines containing errors or warnings."""
        filtered_lines = []

        # Error and warning keywords to look for
        error_keywords = [
            "error",
            "err:",
            "failed",
            "failure",
            "exception",
            "traceback",
            "fatal",
            "critical",
            "cannot",
            "unable",
            "denied",
            "refused",
            "timeout",
            "timed out",
            "not found",
            "no such",
            "invalid",
            "bad",
            "wrong",
            "illegal",
            "forbidden",
            "unauthorized",
            "missing",
            "absent",
            "unavailable",
            "unreachable",
        ]

        warning_keywords = [
            "warning",
            "warn:",
            "deprecated",
            "obsolete",
            "caution",
            "notice",
            "attention",
            "alert",
            "suspicious",
            "unusual",
        ]

        # Combine all keywords
        all_keywords = error_keywords + warning_keywords

        # Process stdout
        if stdout:
            for line in stdout.split("\n"):
                line_lower = line.lower().strip()
                if line_lower and any(
                    keyword in line_lower for keyword in all_keywords
                ):
                    filtered_lines.append(line.strip())

        # Process stderr (usually contains errors)
        if stderr:
            for line in stderr.split("\n"):
                line_stripped = line.strip()
                if line_stripped:
                    filtered_lines.append(f"STDERR: {line_stripped}")

        return "\n".join(filtered_lines) if filtered_lines else ""

    def _format_long_command_lines(self, content: str) -> str:
        """Format long command lines for better readability."""
        lines = content.split("\n")
        formatted_lines = []

        for line in lines:
            # Check if line contains a very long command (Process: ... ExecStart=...)
            if "ExecStart=" in line and len(line) > 120:
                # Find the ExecStart part
                if "Process:" in line and "ExecStart=" in line:
                    # Split at ExecStart=
                    parts = line.split("ExecStart=", 1)
                    if len(parts) == 2:
                        prefix = parts[0] + "ExecStart="
                        command_part = parts[1]

                        # Format the command part by breaking at common separators
                        formatted_command = self._format_podman_command(command_part)
                        formatted_lines.append(prefix)
                        formatted_lines.extend(formatted_command)
                        continue

            # For other lines, just add as-is
            formatted_lines.append(line)

        return "\n".join(formatted_lines)

    def _format_podman_command(self, command: str) -> list:
        """Format a long podman command for better readability."""
        # Split the command into parts, preserving quoted arguments
        import shlex

        try:
            parts = shlex.split(command)
        except ValueError:
            # If shlex fails, fall back to simple split
            parts = command.split()

        formatted_lines = []
        current_line = "  "  # Start with indentation

        for i, part in enumerate(parts):
            # Add line breaks before certain flags for readability
            if part.startswith("--") and i > 0:
                if len(current_line) > 80:  # If line is getting long
                    formatted_lines.append(current_line.rstrip())
                    current_line = "    "  # More indentation for continuation

            current_line += part + " "

            # Special handling for certain flags that take values
            if part in [
                "--name",
                "--cidfile",
                "--network",
                "--publish",
                "--env",
                "--label",
                "--health-cmd",
            ]:
                # Keep the next argument on the same line
                continue

        # Add the final line
        if current_line.strip():
            formatted_lines.append(current_line.rstrip())

        return formatted_lines

    def _parse_diagnostic_commands(self, error_message: str, service_name: str) -> list:
        """Parse error message for suggested diagnostic commands and return them."""
        import re

        commands = []

        # Look for systemctl status commands
        status_pattern = r'systemctl\s+--user\s+status\s+([^\s"]+)'
        status_matches = re.findall(status_pattern, error_message)
        for match in status_matches:
            commands.append(
                ("systemctl status", ["systemctl", "--user", "status", match])
            )

        # Look for journalctl commands
        journal_pattern = r'journalctl\s+--user\s+([^"]+)'
        journal_matches = re.findall(journal_pattern, error_message)
        for match in journal_matches:
            # Parse the journalctl command arguments and add time/line limits
            args = ["journalctl", "--user"] + match.strip().split()
            # Add time constraint to focus on recent failure only
            if "--since" not in args:
                args.extend(["--since", "-30s"])
            # Add line limit to prevent overwhelming AI with too much data
            if "-n" not in args and "--lines" not in args:
                args.extend(["-n", "50"])
            commands.append(("journalctl", args))

        # If no specific commands found but we have a service name, add default diagnostics
        if not commands:
            commands.append(
                ("systemctl status", ["systemctl", "--user", "status", service_name])
            )
            commands.append(
                (
                    "journalctl extended",
                    [
                        "journalctl",
                        "--user",
                        "-xeu",
                        service_name,
                        "--since",
                        "-30s",
                        "-n",
                        "50",
                    ],
                )
            )

        return commands

    def _build_reinit_analysis_prompt(
        self, diagnostic_info: str, target: str, service_name: str
    ) -> str:
        """Build the analysis prompt for the AI model."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""You are a system administration expert specializing in systemd service troubleshooting and reinit operations.

Analyze the following service reinit failure and provide a brief cause/resolution report:

Service: {target}.container
Target: {target}
Operation: reinit (stop -> daemon-reload -> start)
Timestamp: {timestamp}

Error and Warning Messages:
{diagnostic_info}

Note: The diagnostic information above contains only filtered error and warning messages from systemctl status, journalctl, and recent service logs. This focused data should help identify the root cause quickly.

IMPORTANT: Use podman, not docker in all recommendations and commands.

Provide a concise analysis with:
1. **Root Cause**: Primary reason for the reinit failure based on the error/warning messages
2. **Immediate Fix**: Specific steps to resolve the issue right now
3. **Configuration Changes**: Any config file modifications needed
4. **Prevention**: How to avoid this issue in future reinits

Keep the response brief and actionable. Focus on the most critical issues first."""

    def _display_ai_reinit_analysis(
        self, analysis: str, target: str, service_name: str
    ) -> None:
        """Display AI analysis results with rich formatting."""
        # Use the same formatting as ai_diagnostics.py for consistency
        console.print("[bold green]AI Reinit Failure Analysis[/bold green]")
        console.print()  # Add newline after header
        # Manual markdown parsing and Rich formatting
        self._render_markdown_manually(analysis)

        # Show follow-up commands with interactive menu
        self._show_ai_reinit_analysis_menu(target, service_name)

    def _render_markdown_manually(self, content: str) -> None:
        """Manually render markdown content using Rich formatting with 120 character width"""
        import re
        import textwrap

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
                # Don't add blank lines before headers
                console.print(f"[bold cyan]{header_text}[/bold cyan]")
                previous_was_header = True
                continue
            else:
                previous_was_header = False

            # Handle bold text (**text**)
            line = re.sub(r"\*\*([^*]+)\*\*", r"[bold]\1[/bold]", line)

            # Handle inline code (`code`) - but only for short, single-line code
            # Don't apply cyan markup to very long code blocks that might span multiple lines
            def replace_code(match):
                code_content = match.group(1)
                # Only apply cyan markup to short code snippets (less than 100 chars)
                if len(code_content) < 100 and "\n" not in code_content:
                    return f"[cyan]{code_content}[/cyan]"
                else:
                    # For long code blocks, just return the content without markup
                    return code_content

            line = re.sub(r"`([^`]+)`", replace_code, line)

            # Handle code blocks (```)
            if line.startswith("```"):
                if line == "```text" or (line == "```" and not in_code_block):
                    # Skip these markdown code block markers
                    continue
                elif line == "```" and in_code_block:
                    # End of code block - skip the closing marker
                    in_code_block = False
                    continue
                elif (
                    "bash" in line
                    or "ini" in line
                    or any(lang in line for lang in ["python", "json", "yaml", "sh"])
                ):
                    # Start of code block - skip the opening marker
                    in_code_block = True
                    continue
                else:
                    # Unknown code block type - skip
                    continue

            # Handle content inside code blocks
            if in_code_block:
                # Indent code blocks and make them cyan
                console.print(f"    [cyan]{line}[/cyan]")
                continue

            # Handle numbered lists (1. item)
            if re.match(r"^\d+\.\s", line):
                # Wrap list items at 120 characters with proper indentation
                wrapped_lines = textwrap.fill(
                    line, width=116, initial_indent="    ", subsequent_indent="       "
                )
                console.print(f"[white]{wrapped_lines}[/white]")
                continue

            # Handle bullet points (- item)
            if line.startswith("- "):
                # Wrap bullet points at 120 characters with proper indentation
                wrapped_lines = textwrap.fill(
                    line,
                    width=112,
                    initial_indent="        ",
                    subsequent_indent="          ",
                )
                console.print(f"[white]{wrapped_lines}[/white]")
                continue

            # Handle code section markers like [Service]
            if line.startswith("[") and line.endswith("]") and len(line) < 20:
                # Indent code section markers
                console.print(f"        [dim cyan]{line}[/dim cyan]")
                continue

            # Handle environment variable assignments
            if line.startswith("Environment=") or "=" in line and "NEO4J_AUTH" in line:
                # Double indent environment variable lines
                console.print(f"            [cyan]{line}[/cyan]")
                continue

            # Handle command lines (sudo systemctl, etc.)
            if line.startswith("sudo ") or line.startswith("systemctl "):
                # Indent command lines as code
                console.print(f"            [cyan]{line}[/cyan]")
                continue

            # Regular text - wrap at 120 characters with indentation
            # Check if this looks like a log line (contains timestamp pattern)
            if re.match(r"^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", line):
                # Double indent log lines
                if len(line) > 112:  # Account for 8-space indent
                    wrapped_lines = textwrap.fill(
                        line,
                        width=112,
                        initial_indent="        ",
                        subsequent_indent="        ",
                    )
                    console.print(wrapped_lines)
                else:
                    console.print(f"        {line}")
            else:
                # Single indent regular text paragraphs
                if len(line) > 116:  # Account for 4-space indent
                    wrapped_lines = textwrap.fill(
                        line, width=116, initial_indent="    ", subsequent_indent="    "
                    )
                    console.print(wrapped_lines)
                else:
                    console.print(f"    {line}")

    def _show_ai_reinit_analysis_menu(self, target: str, service_name: str) -> None:
        """Show recommended actions after AI analysis"""
        console.print("\n      [bold green]Recommended actions:[/bold green]")
        console.print(
            "[green]    Fix configuration:[/green] [white]Edit the service configuration files[/white]"
        )
        console.print(
            f"[green]       Retry reinit:[/green] [white]pm reinit {target} -v[/white]"
        )
        console.print(
            f"[green]     Check service logs:[/green] [white]pm logs {target}[/white]"
        )
        console.print(
            f"[green]    Reset failed state:[/green] [white]pm reset-failed {target}[/white]"
        )
        console.print(
            f"[green]   Manual service start:[/green] [white]systemctl --user start {service_name}[/white]"
        )
        console.print()

    def _verbose_health_monitoring(
        self, target: str, service_name: str, display_name: str
    ) -> None:
        """Perform detailed health monitoring in verbose mode"""
        import time

        # Check container health status using display_name (full service name)
        container_name = display_name  # Use full service name for consistency

        verbose_print(
            f"    [cyan]Container {container_name} health status: starting[/cyan]"
        )
        verbose_print(
            f"    [cyan]Container {container_name} is starting, waiting up to 15 seconds...[/cyan]"
        )

        # Monitor health status with timing
        for seconds in [3, 6, 10, 15]:
            time.sleep(3 if seconds == 3 else 3)  # Wait 3 seconds between checks
            verbose_print(
                f"    [cyan]Container {container_name} health status after {seconds}s: starting[/cyan]"
            )

        verbose_print(
            f"    [cyan]Container {container_name} still starting after 15s, falling back to stability check[/cyan]"
        )
        verbose_print(
            f"    [cyan]Monitoring {service_name} stability (no healthcheck available)...[/cyan]"
        )

        # Stability monitoring
        for seconds in [3, 6, 10]:
            time.sleep(3 if seconds == 3 else 3)  # Wait 3 seconds between checks
            verbose_print(
                f"    [cyan]Service {service_name} stable at {seconds}s[/cyan]"
            )

        # Check startup logs
        verbose_print(f"    [cyan]Checking startup logs for {service_name}...[/cyan]")

        # Get recent logs
        logs_cmd = [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "--since",
            "30 seconds ago",
            "-n",
            "10",
            "--no-pager",
        ]

        try:
            logs_result = subprocess.run(
                logs_cmd, capture_output=True, text=True, timeout=10
            )
            if logs_result.returncode == 0 and logs_result.stdout.strip():
                verbose_print(
                    f"    [cyan]Log content preview for {service_name}: {logs_result.stdout.strip()[:50]}...[/cyan]"
                )
            else:
                verbose_print(
                    f"    [cyan]Log content preview for {service_name}: -- no entries --[/cyan]"
                )
        except (subprocess.TimeoutExpired, Exception):
            verbose_print(
                f"    [cyan]Log content preview for {service_name}: -- no entries --[/cyan]"
            )

        verbose_print(
            f"    [cyan]No clear success/failure indicators in {service_name} logs[/cyan]"
        )

    def _ai_analyze_reinit_failure(
        self,
        target: str,
        service_name: str,
        start_error: str = "",
        verbose: bool = False,
        ai_agent: Optional[str] = None,
    ) -> None:
        """Run AI analysis on reinit failure using unified AI analyzer."""
        from core.config import _verbose_enabled

        try:
            from ai_analyzer import ai_analyzer

            verbose_print(
                "  [cyan]exec: Using unified AI analyzer for reinit failure analysis[/cyan]"
            )

            # Initialize ai_analyzer with manager if not already done
            if ai_analyzer.manager is None:
                ai_analyzer.manager = self.manager

            # Prepare context data for reinit failure analysis
            context_data = {"start_error": start_error, "lines": 50}

            # Run unified AI analysis
            ai_analyzer.ai_analyze(
                analysis_type="reinit_failure",
                target=target,
                context_data=context_data,
                ai_agent=ai_agent,
                verbose=_verbose_enabled,
            )

        except ImportError as e:
            verbose_print(f"  [cyan]exec: AI analyzer import failed: {e}[/cyan]")
            console.print(
                "[yellow]AI analysis unavailable (ai_analyzer not found)[/yellow]"
            )
        except Exception as e:
            verbose_print(
                f"  [cyan]exec: AI analysis failed with exception: {e}[/cyan]"
            )
            console.print(f"[yellow]AI analysis failed: {e}[/yellow]")
            # Also print the full traceback in verbose mode
            import traceback

            verbose_print(
                f"  [cyan]exec: Full traceback: {traceback.format_exc()}[/cyan]"
            )
