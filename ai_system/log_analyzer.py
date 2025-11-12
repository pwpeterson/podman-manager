"""Log analysis and diagnostic operations for quadlet containers."""

import re
import subprocess
from collections import Counter
from typing import List

from core.config import console, verbose_print


class LogAnalyzer:
    """Handles log analysis, pattern matching, and diagnostic operations"""

    def __init__(self, manager):
        self.manager = manager

    def _extract_log_message(self, log_line: str, msg_type: str) -> str:
        """Extract the actual error/warning message from a log line with timestamp"""
        # Extract timestamp first
        timestamp = ""
        timestamp_match = re.search(r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})", log_line)
        if timestamp_match:
            timestamp = timestamp_match.group(1)
        else:
            # Try ISO format timestamp
            timestamp_match = re.search(
                r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", log_line
            )
            if timestamp_match:
                timestamp = timestamp_match.group(1)

        # Common patterns to look for ERROR/WARNING messages - include the type in the result
        patterns = [
            rf"({msg_type}\s*-\s*.+)",  # ERROR - message
            rf"({msg_type}:\s*.+)",  # ERROR: message
            rf"({msg_type}\s+.+)",  # ERROR message
            rf"(\b{msg_type.lower()}\b.*?:\s*.+)",  # error: message
            rf"(.*logging\s*-\s*{msg_type}\s*-\s*.+)",  # logging - ERROR - message
            rf"(.*\s+-\s+{msg_type}\s+-\s+.+)",  # module - ERROR - message
            rf"(.*utils\.logging\s*-\s*{msg_type}\s*-\s*.+)",  # utils.logging - ERROR - message
        ]

        message_content = ""
        for pattern in patterns:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if match:
                message_content = match.group(1).strip()
                break

        if not message_content:
            # If no pattern matches, try to extract after common log prefixes
            # Remove timestamp and service name prefixes
            cleaned = re.sub(
                r"^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+\S+\[\d+\]:\s*",
                "",
                log_line,
            )
            cleaned = re.sub(
                r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d+\s*", "", cleaned
            )

            # Look for the message type in the cleaned content
            for pattern in [
                rf"({msg_type}\s*-\s*.+)",
                rf"({msg_type}:\s*.+)",
                rf"({msg_type}\s+.+)",
            ]:
                match = re.search(pattern, cleaned, re.IGNORECASE)
                if match:
                    message_content = match.group(1).strip()
                    break

            # Fallback: return the cleaned line or original if cleaning failed
            if not message_content:
                message_content = (
                    cleaned.strip() if cleaned.strip() else log_line.strip()
                )

        # Combine timestamp and message
        if timestamp:
            return f"[{timestamp}] {message_content}"
        else:
            return message_content

    def show_logs(self, target: str, follow: bool = False) -> None:
        """Show service logs using journalctl"""
        success = self.manager.show_logs(target, follow=follow)
        if not success:
            console.print("[dim]Try running: pm list to see available services[/dim]")

    def analyze_logs(self, target: str, lines: int = 50) -> None:
        """Analyze service logs for errors, warnings, and other issues"""
        self.manager._clear_auto_match_cache()
        service_name = self.manager._find_service_name(target)

        if not service_name:
            return

        console.print(f"Analyzing logs for {service_name} (last {lines} lines)...")

        # Get logs using journalctl
        cmd = [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "-n",
            str(lines),
            "--no-pager",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                console.print(
                    f"[red]Failed to get logs: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
                )
                return

            if not result.stdout.strip():
                console.print(f"[yellow]No logs found for {service_name}[/yellow]")
                return

            log_lines = result.stdout.strip().split("\n")

            # Define patterns for different issue types
            patterns = {
                "ERROR": [
                    r"\bERROR\b",
                    r"\bFATAL\b",
                    r"\bCRITICAL\b",
                    r"\bFailed\b",
                    r"\bException\b",
                    r"\bTraceback\b",
                    r"\berror\b.*:",
                    r"\bfailed to\b",
                    r"\bcannot\b",
                    r"\bunable to\b",
                    r"\bconnection refused\b",
                    r"\btimeout\b",
                    r"\bpermission denied\b",
                    r"- ERROR -",
                    r"\s+ERROR\s+",
                    r"logging - ERROR",
                    r"utils\.logging - ERROR",
                    r"tools will fail",
                    r"server will start anyway",
                ],
                "WARNING": [
                    r"\bWARNING\b",
                    r"\bWARN\b",
                    r"\bwarning\b.*:",
                    r"\bdeprecated\b",
                    r"\bretrying\b",
                    r"\bfallback\b",
                    r"\bignoring\b",
                ],
                "INFO": [
                    r"\bINFO\b",
                    r"\bstarted\b",
                    r"\bstopped\b",
                    r"\blistening\b",
                    r"\bconnected\b",
                    r"\binitialized\b",
                ],
            }

            # Analyze logs
            issue_counts = Counter()
            all_errors = []
            all_warnings = []

            for i, line in enumerate(log_lines):
                line_lower = line.lower()

                for issue_type, type_patterns in patterns.items():
                    for pattern in type_patterns:
                        if re.search(pattern, line_lower):
                            issue_counts[issue_type] += 1

                            # Keep track of ALL issues (not just recent 50 lines)
                            # For multi-line messages, try to capture continuation
                            full_line = line.strip()
                            # Check if next line might be a continuation (no timestamp/service prefix)
                            if i + 1 < len(log_lines):
                                next_line = log_lines[i + 1].strip()
                                # If next line doesn't start with timestamp or service name, it's likely a continuation
                                if (
                                    next_line
                                    and not re.match(
                                        r"^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}",
                                        next_line,
                                    )
                                    and not re.match(
                                        r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}",
                                        next_line,
                                    )
                                    and len(next_line) > 10
                                ):  # Reasonable length check
                                    full_line += " " + next_line

                            if issue_type == "ERROR":
                                all_errors.append(full_line)
                            elif issue_type == "WARNING":
                                all_warnings.append(full_line)
                            break

            # Display concise results
            errors = issue_counts.get("ERROR", 0)
            warnings = issue_counts.get("WARNING", 0)
            infos = issue_counts.get("INFO", 0)

            # Overall status
            if errors > 0:
                status = "[red]Critical Issues Detected[/red]"
            elif warnings > 10:
                status = "[yellow]High Warning Count[/yellow]"
            elif warnings > 0:
                status = "[yellow]Warnings Found[/yellow]"
            else:
                status = "[green]No Issues Detected[/green]"

            console.print(f"\nOverall Status: {status}")
            console.print(f"Analyzed {len(log_lines)} log lines")

            # Show counts if there are issues
            if errors > 0 or warnings > 0:
                console.print(
                    f"\n[red]Errors: {errors}[/red] | [yellow]Warnings: {warnings}[/yellow] | [dim]Info: {infos}[/dim]"
                )

            # Show all detected error/warning messages
            if all_errors or all_warnings:
                console.print("\nAll Detected Issues:")
                if all_errors:
                    console.print(f"  [red]All Errors ({len(all_errors)}):[/red]")
                    # Display each error line separately in chronological descending order (most recent first)
                    for error in all_errors:  # Most recent first
                        extracted_msg = self._extract_log_message(error, "ERROR")

                        if len(extracted_msg) > 120:
                            display_msg = extracted_msg[:117] + "..."
                        else:
                            display_msg = extracted_msg

                        # Format with red ERROR but white message
                        formatted_msg = display_msg.replace(
                            "ERROR -", "[red]ERROR[/red] -"
                        )
                        formatted_msg = formatted_msg.replace(
                            "ERROR:", "[red]ERROR[/red]:"
                        )
                        formatted_msg = formatted_msg.replace(
                            "ERROR ", "[red]ERROR[/red] "
                        )

                        console.print(f"    • {formatted_msg}")

                if all_warnings:
                    console.print(
                        f"  [yellow]All Warnings ({len(all_warnings)}):[/yellow]"
                    )
                    # Display each warning line separately in chronological descending order (most recent first)
                    for warning in all_warnings:  # Most recent first
                        extracted_msg = self._extract_log_message(warning, "WARNING")

                        if len(extracted_msg) > 120:
                            display_msg = extracted_msg[:117] + "..."
                        else:
                            display_msg = extracted_msg

                        # Format with yellow WARNING but white message
                        formatted_msg = display_msg.replace(
                            "WARNING -", "[yellow]WARNING[/yellow] -"
                        )
                        formatted_msg = formatted_msg.replace(
                            "WARNING:", "[yellow]WARNING[/yellow]:"
                        )
                        formatted_msg = formatted_msg.replace(
                            "WARNING ", "[yellow]WARNING[/yellow] "
                        )

                        console.print(f"    • {formatted_msg}")

            # Quick recommendations
            if errors > 0:
                console.print(
                    "\n[red]⚠ Check error logs immediately - service may be failing[/red]"
                )
            elif warnings > 10:
                console.print(
                    "\n[yellow]⚠ High warning count - investigate configuration[/yellow]"
                )

            # Follow-up commands with interactive menu
            self._show_interactive_menu(target, service_name, errors)

        except subprocess.TimeoutExpired:
            console.print("[red]Timeout while fetching logs[/red]")
        except Exception as e:
            console.print(f"[red]Error analyzing logs: {e}[/red]")

    def _show_interactive_menu(
        self, target: str, service_name: str, errors: int
    ) -> None:
        """Show interactive menu for follow-up commands"""
        # Use the resolved service name (without .service suffix) for commands
        resolved_service = (
            service_name.replace(".service", "")
            if service_name.endswith(".service")
            else service_name
        )
        # Convert back to short name for commands
        if resolved_service == "vllm-qwen25-mcp":
            cmd_service = "vllm-qwen25"
        elif resolved_service == "vllm-proxy-mcp":
            cmd_service = "vllm-proxy"
        elif resolved_service == "vllm-delegator-mcp":
            cmd_service = "vllm-delegator"
        else:
            cmd_service = resolved_service

        console.print("\nFollow-up Commands:")
        console.print(
            f"[cyan]1[/cyan]  pm log-ai-analyze {cmd_service}\t# Analyze logs with AI"
        )
        console.print(f"[cyan]2[/cyan]  pm logs {cmd_service:<20}\t\t# View logs")
        console.print(
            f"[cyan]3[/cyan]  pm logs {cmd_service} --follow\t# Monitor live logs"
        )
        console.print(
            f"[cyan]4[/cyan]  pm status {cmd_service:<18}\t\t# Check service status"
        )
        console.print(
            f"[cyan]5[/cyan]  pm diagnose {cmd_service:<15}\t\t# Diagnose startup failures"
        )
        if errors > 0:
            console.print(
                f"[cyan]6[/cyan]  pm restart {cmd_service:<17}\t\t# Restart if needed"
            )
            max_option = 6
        else:
            max_option = 5

        # Interactive command selection
        try:
            choice = input(
                f"\nSelect command (1-{max_option}) or press Enter to skip: "
            ).strip()
            if choice and choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= max_option:
                    cmd = []  # Initialize cmd variable

                    if choice_num == 1:
                        cmd = [
                            "python",
                            "podman_manager.py",
                            "log-ai-analyze",
                            cmd_service,
                        ]
                    elif choice_num == 2:
                        cmd = ["python", "podman_manager.py", "logs", cmd_service]
                    elif choice_num == 3:
                        cmd = [
                            "python",
                            "podman_manager.py",
                            "logs",
                            cmd_service,
                            "--follow",
                        ]
                    elif choice_num == 4:
                        cmd = ["python", "podman_manager.py", "status", cmd_service]
                    elif choice_num == 5:
                        cmd = [
                            "python",
                            "podman_manager.py",
                            "diagnose",
                            cmd_service,
                        ]
                    elif choice_num == 6:
                        cmd = [
                            "python",
                            "podman_manager.py",
                            "restart",
                            cmd_service,
                        ]

                    if cmd:  # Only execute if cmd was set
                        console.print(f"\n[cyan]Executing: {' '.join(cmd)}[/cyan]")
                        subprocess.run(cmd)
                else:
                    console.print(
                        f"[yellow]Invalid choice. Please select 1-{max_option}[/yellow]"
                    )
            elif choice:
                console.print(
                    f"[yellow]Invalid choice. Please select 1-{max_option}[/yellow]"
                )
        except KeyboardInterrupt:
            console.print("\n[yellow]Command selection cancelled[/yellow]")
        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")

    def diagnose_container_failure(self, target: str) -> None:
        """Diagnose why a container is failing to start"""
        from core.config import _verbose_enabled

        self.manager._clear_auto_match_cache()
        service_name = self.manager._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return

        console.print(f"\n[green]Troubleshooting {service_name}...[/green]")
        console.print()

        # Check systemd service status
        status_cmd = ["systemctl", "--user", "status", service_name, "--no-pager", "-l"]
        if _verbose_enabled:
            console.print(f"[cyan]exec: {' '.join(status_cmd)}[/cyan]")
        console.print("\n[green]Service Status:[/green]")
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)
        if status_result.stdout:
            console.print(status_result.stdout)

        # Try to run the container manually to see what fails
        from rich.progress import Progress, SpinnerColumn, TextColumn

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Testing container manually:[/cyan]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("testing", total=None)

            # Determine container name and image based on service
            if target == "vllm-delegator":
                container_name = "vllm-delegator-mcp-test"
                image_name = "localhost/vllm-delegator-mcp:latest"
                test_cmd = [
                    "podman",
                    "run",
                    "--rm",
                    "--name",
                    container_name,
                    "--network",
                    "host",
                    "--env",
                    "VLLM_API_URL=http://localhost:8002/v1/chat/completions",
                    "--env",
                    "VLLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
                    "--env",
                    "LOGGING_ON=true",
                    "--env",
                    "LOG_LEVEL=DEBUG",
                    image_name,
                ]
            elif target == "vllm-proxy":
                container_name = "vllm-proxy-test"
                image_name = "localhost/vllm-proxy:latest"
                test_cmd = [
                    "podman",
                    "run",
                    "--rm",
                    "--name",
                    container_name,
                    "--network",
                    "host",
                    image_name,
                ]
            else:
                progress.remove_task(task)
                # Use the resolved service name instead of original target for consistency
                resolved_name = (
                    service_name.replace(".service", "")
                    if service_name.endswith(".service")
                    else service_name
                )
                console.print(
                    f"[yellow]No diagnostic available for {resolved_name}[/yellow]"
                )
                return

            progress.remove_task(task)

        console.print(f"[dim]Running: {' '.join(test_cmd)}[/dim]")
        console.print("[dim]Press Ctrl+C to stop if it hangs...[/dim]")

        try:
            # Run with timeout to prevent hanging
            test_result = subprocess.run(
                test_cmd, capture_output=True, text=True, timeout=30
            )

            if test_result.returncode == 0:
                console.print("[green]✅ Container ran successfully![/green]")
                if test_result.stdout:
                    console.print("[cyan]Output:[/cyan]")
                    console.print(test_result.stdout)
            else:
                console.print(
                    f"[red]❌ Container failed with exit code {test_result.returncode}[/red]"
                )
                if test_result.stderr:
                    console.print("[red]Error output:[/red]")
                    console.print(test_result.stderr)
                if test_result.stdout:
                    console.print("[yellow]Standard output:[/yellow]")
                    console.print(test_result.stdout)

        except subprocess.TimeoutExpired:
            console.print(
                "[yellow]⏰ Container test timed out (30s) - may be running but not responding[/yellow]"
            )
            # Try to stop the test container
            service_name = f"{container_name}.service"
            subprocess.run(
                ["systemctl", "--user", "stop", service_name], capture_output=True
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Test interrupted by user[/yellow]")
            service_name = f"{container_name}.service"
            subprocess.run(
                ["systemctl", "--user", "stop", service_name], capture_output=True
            )

        self._show_troubleshooting_tips(target, service_name)

    def _show_troubleshooting_tips(self, target: str, service_name: str) -> None:
        """Show troubleshooting tips for container failures"""
        console.print("\n[cyan]💡 Troubleshooting tips:[/cyan]")
        console.print("1. Check if the image was built correctly")
        console.print("2. Verify all required files/configs are present")
        console.print("3. Check if ports are already in use")
        console.print("4. Verify environment variables are correct")
        console.print(f"5. Try: systemctl --user reset-failed {service_name}")
        console.print(f"6. Then: systemctl --user start {service_name}")

        # Special troubleshooting for vllm-delegator stdio/TCP mode issue
        if target == "vllm-delegator":
            console.print("\n[yellow]🔧 vLLM Delegator Specific Issues:[/yellow]")
            console.print(
                "[red]Issue detected:[/red] MCP server running in stdio mode instead of TCP mode"
            )
            console.print(
                "[yellow]Root cause:[/yellow] MCP server immediately shuts down when no stdin available"
            )
            console.print("\n[cyan]Investigation needed:[/cyan]")
            console.print("1. Check container's Dockerfile CMD/ENTRYPOINT")
            console.print("2. Look for MCP server configuration options")
            console.print("3. Find how to enable TCP mode in the MCP server")
            console.print("\n[cyan]Inspect container startup:[/cyan]")
            console.print(
                r"podman inspect localhost/vllm-delegator-mcp:latest | grep -A5 -B5 'Cmd\|Entrypoint'"
            )
            console.print("\n[cyan]Check if MCP_HOST/MCP_PORT are being used:[/cyan]")
            console.print("podman run --rm -e MCP_HOST=0.0.0.0 -e MCP_PORT=8003 \\")
            console.print(
                '  localhost/vllm-delegator-mcp:latest python -c "import os; print(f\'HOST: {os.getenv(\\"MCP_HOST\\")}, PORT: {os.getenv(\\"MCP_PORT\\")}\')"'
            )
            console.print(
                "\n[red]Current issue:[/red] Server starts in stdio mode → no stdin → immediate shutdown"
            )
            console.print(
                "[green]Solution needed:[/green] Configure MCP server to run in TCP/HTTP mode for systemd"
            )
            console.print("\n[cyan]Next steps to fix:[/cyan]")
            console.print(
                "1. Check the vllm_delegator.py file for TCP mode configuration"
            )
            console.print("2. Look for MCP server initialization code")
            console.print("3. Find how to enable TCP/HTTP transport instead of stdio")
            console.print("\n[cyan]Inspect the main delegator file:[/cyan]")
            console.print(
                "podman run --rm localhost/vllm-delegator-mcp:latest cat /app/vllm_delegator.py | head -100"
            )
            console.print("\n[cyan]Look for MCP server setup:[/cyan]")
            console.print(
                r"podman run --rm localhost/vllm-delegator-mcp:latest grep -n -A5 -B5 'server\|transport\|stdio\|tcp' /app/vllm_delegator.py"
            )
            console.print(
                "\n[red]Root cause:[/red] MCP server hardcoded to stdio mode in vllm_delegator.py"
            )
            console.print(
                "[green]Solution:[/green] Modify MCP server initialization to use TCP transport"
            )

    def show_startup_failure_logs(self, target: str, service_name: str) -> None:
        """Show recent logs when service fails to start properly"""
        from core.config import _verbose_enabled

        # Keep track of messages to avoid duplicates (empty set since no initial section)
        shown_messages = set()

        # Run extended journalctl command and extract timestamped messages
        if _verbose_enabled:
            console.print(f"[green]Journal extract for: {target}[/green]")
        else:
            console.print(f"[green]Journal extract for: {target}[/green]")

        # Use complete output without line limits in verbose mode to get all messages
        extended_logs_cmd = [
            "journalctl",
            "--user",
            "-xeu",
            service_name,
            "--output=short-precise",
            "--no-pager",
        ]

        verbose_print(f"[cyan]exec: {' '.join(extended_logs_cmd)}[/cyan]")
        if _verbose_enabled:
            print()  # Add newline after the exec command in verbose mode
        extended_result = subprocess.run(
            extended_logs_cmd, capture_output=True, text=True
        )

        if extended_result.returncode == 0 and extended_result.stdout:
            # Parse journal output to extract the most recent start-to-failure section
            extended_lines = extended_result.stdout.strip().split("\n")

            # Find the most recent section between start job and failed state
            start_pattern = r"A start job for unit .* has begun execution\."
            end_pattern = r"The unit .* has entered the \'failed\' state with result \'exit-code\'"

            # Find all start and end markers
            start_indices = []
            end_indices = []

            for i, line in enumerate(extended_lines):
                if re.search(start_pattern, line):
                    start_indices.append(i)
                elif re.search(end_pattern, line):
                    end_indices.append(i)

            # Always extract the most recent complete section, but in verbose mode show all messages in that section
            from core.config import _verbose_enabled

            # Extract the most recent complete section (both verbose and non-verbose modes)
            section_lines = []
            if start_indices and end_indices:
                # Find the most recent start that has a corresponding end
                most_recent_start = None
                corresponding_end = None

                # Work backwards through start indices to find the most recent complete section
                for start_idx in reversed(start_indices):
                    # Find the first end index after this start
                    for end_idx in end_indices:
                        if end_idx > start_idx:
                            most_recent_start = start_idx
                            corresponding_end = end_idx
                            break
                    if most_recent_start is not None:
                        break

                if most_recent_start is not None and corresponding_end is not None:
                    # Extract the section including start and end messages
                    section_lines = extended_lines[
                        most_recent_start : corresponding_end + 1
                    ]

            # If no complete section found, fall back to recent lines
            if not section_lines:
                section_lines = extended_lines[-20:]  # Show last 20 lines as fallback

            # In verbose mode, show ALL messages without any deduplication or filtering
            if _verbose_enabled:
                # Show all messages in the section without any filtering or deduplication
                unique_messages = section_lines  # Show ALL lines, even empty ones
            else:
                # Non-verbose mode: Remove duplicates from already shown messages but keep everything else
                all_messages = []
                for line in section_lines:
                    if line.strip() and line.strip() not in shown_messages:
                        all_messages.append(line)

                # Remove duplicates by message content but keep most recent timestamp
                message_dict = {}

                for msg in all_messages:
                    # Extract the actual message content (after timestamp and service info)
                    # Remove timestamp and service prefix to get the core message
                    cleaned_msg = re.sub(
                        r"^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\.?\d*\s+\S+\s+\S+\[?\d*\]?:?\s*",
                        "",
                        msg,
                    )
                    cleaned_msg = re.sub(
                        r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.?\d*\s+\S+\s+\S+\[?\d*\]?:?\s*",
                        "",
                        cleaned_msg,
                    )

                    # Use the cleaned message as key, keep the most recent full message
                    if cleaned_msg.strip():
                        message_dict[cleaned_msg.strip()] = msg

                # Convert back to list, sorted by original order (most recent last)
                unique_messages = list(message_dict.values())

            # Show all messages from the extracted section
            if unique_messages:
                for line in unique_messages:
                    if _verbose_enabled:
                        # In verbose mode, show ALL lines exactly as they are with original colors
                        if line.strip():  # Only skip completely empty lines
                            print(
                                line
                            )  # Use print() to preserve original journalctl colors
                        else:
                            print("")  # Preserve empty lines
                    else:
                        self._format_and_print_log_line(line)
            else:
                # Fallback: show last 5 lines from extended output that indicate problems
                self._show_fallback_problem_lines(extended_lines, shown_messages)
        else:
            console.print("[yellow]Could not retrieve extended logs[/yellow]")
            if extended_result.stderr:
                if _verbose_enabled:
                    console.print("[red]❌ Complete journalctl error:[/red]")
                    console.print("[dim]" + "─" * 60 + "[/dim]")
                    for line in extended_result.stderr.strip().split("\n"):
                        if line.strip():
                            console.print(f"[red]{line}[/red]")
                    console.print("[dim]" + "─" * 60 + "[/dim]")
                else:
                    console.print(f"[red]Error: {extended_result.stderr.strip()}[/red]")

        # Add diagnostic steps before recommended actions
        self._run_diagnostic_steps(target, service_name)

        # Show recommended actions
        self._show_recommended_actions(target, service_name)

    def _run_diagnostic_steps(self, target: str, service_name: str) -> None:
        """Run diagnostic steps similar to pm diagnose command"""
        from rich.progress import Progress, SpinnerColumn, TextColumn

        with Progress(
            SpinnerColumn(),
            TextColumn(f"[yellow]Running diagnostic steps for {target}...[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("diagnostic", total=None)

            # Step 2: Manual Container Testing
            self._test_container_manually(target)

            # Step 3: Troubleshooting Tips
            console.print("\n[green]Troubleshooting tips:[/green]")
            console.print("  [green]Check if the image was built correctly[/green]")
            console.print(
                "  [green]Verify all required files/configs are present[/green]"
            )
            console.print("  [green]Check if ports are already in use[/green]")
            console.print("  [green]Verify environment variables are correct[/green]")

            # Step 4: Specialized Diagnostics
            self._show_specialized_diagnostics(target)

            progress.remove_task(task)

    def _test_container_manually(self, target: str) -> None:
        """Test container manually to see what fails"""
        from rich.progress import Progress, SpinnerColumn, TextColumn

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Testing container manually:[/cyan]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("testing", total=None)

            # Determine container name and image based on service
            if target == "vllm-delegator":
                container_name = "vllm-delegator-mcp-test"
                image_name = "localhost/vllm-delegator-mcp:latest"
                test_cmd = [
                    "podman",
                    "run",
                    "--rm",
                    "--name",
                    container_name,
                    "--network",
                    "host",
                    "--env",
                    "VLLM_API_URL=http://localhost:8002/v1/chat/completions",
                    "--env",
                    "VLLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
                    "--env",
                    "LOGGING_ON=true",
                    "--env",
                    "LOG_LEVEL=DEBUG",
                    image_name,
                ]
            elif target == "vllm-proxy":
                container_name = "vllm-proxy-test"
                image_name = "localhost/vllm-proxy:latest"
                test_cmd = [
                    "podman",
                    "run",
                    "--rm",
                    "--name",
                    container_name,
                    "--network",
                    "host",
                    image_name,
                ]
            else:
                progress.remove_task(task)
                # Use a resolved name for consistency (target should already be resolved by this point)
                console.print(
                    f"\n[yellow]No manual test available for {target}[/yellow]"
                )
                return

            progress.remove_task(task)

        console.print(f"[dim]Running: {' '.join(test_cmd)}[/dim]")
        console.print("[dim]Press Ctrl+C to stop if it hangs...[/dim]")

        try:
            # Run with timeout to prevent hanging
            test_result = subprocess.run(
                test_cmd, capture_output=True, text=True, timeout=30
            )

            if test_result.returncode == 0:
                console.print("[green]✅ Container ran successfully![/green]")
                if test_result.stdout:
                    console.print("[cyan]Output:[/cyan]")
                    console.print(test_result.stdout)
            else:
                console.print(
                    f"[red]❌ Container failed with exit code {test_result.returncode}[/red]"
                )
                if test_result.stderr:
                    console.print("[red]Error output:[/red]")
                    console.print(test_result.stderr)
                if test_result.stdout:
                    console.print("[yellow]Standard output:[/yellow]")
                    console.print(test_result.stdout)

        except subprocess.TimeoutExpired:
            console.print(
                "[yellow]⏰ Container test timed out (30s) - may be running but not responding[/yellow]"
            )
            # Try to stop the test container
            service_name = f"{container_name}.service"
            subprocess.run(
                ["systemctl", "--user", "stop", service_name], capture_output=True
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Test interrupted by user[/yellow]")
            service_name = f"{container_name}.service"
            subprocess.run(
                ["systemctl", "--user", "stop", service_name], capture_output=True
            )
        except Exception as e:
            console.print(f"[red]Error running container test: {e}[/red]")

    def _show_specialized_diagnostics(self, target: str) -> None:
        """Show specialized diagnostics for specific services"""
        # Special troubleshooting for vllm-delegator stdio/TCP mode issue
        if target == "vllm-delegator":
            console.print("\n[yellow]🔧 vLLM Delegator Specific Issues:[/yellow]")
            console.print(
                "[red]Issue detected:[/red] MCP server running in stdio mode instead of TCP mode"
            )
            console.print(
                "[yellow]Root cause:[/yellow] MCP server immediately shuts down when no stdin available"
            )
            console.print("\n[cyan]Investigation needed:[/cyan]")
            console.print("1. Check container's Dockerfile CMD/ENTRYPOINT")
            console.print("2. Look for MCP server configuration options")
            console.print("3. Find how to enable TCP mode in the MCP server")
            console.print("\n[cyan]Inspect container startup:[/cyan]")
            console.print(
                r"podman inspect localhost/vllm-delegator-mcp:latest | grep -A5 -B5 'Cmd\|Entrypoint'"
            )
            console.print("\n[cyan]Check if MCP_HOST/MCP_PORT are being used:[/cyan]")
            console.print("podman run --rm -e MCP_HOST=0.0.0.0 -e MCP_PORT=8003 \\")
            console.print(
                '  localhost/vllm-delegator-mcp:latest python -c "import os; print(f\'HOST: {os.getenv(\\"MCP_HOST\\")}, PORT: {os.getenv(\\"MCP_PORT\\")}\')"'
            )
            console.print(
                "\n[red]Current issue:[/red] Server starts in stdio mode → no stdin → immediate shutdown"
            )
            console.print(
                "[green]Solution needed:[/green] Configure MCP server to run in TCP/HTTP mode for systemd"
            )
            console.print("\n[cyan]Next steps to fix:[/cyan]")
            console.print(
                "1. Check the vllm_delegator.py file for TCP mode configuration"
            )
            console.print("2. Look for MCP server initialization code")
            console.print("3. Find how to enable TCP/HTTP transport instead of stdio")
            console.print("\n[cyan]Inspect the main delegator file:[/cyan]")
            console.print(
                "podman run --rm localhost/vllm-delegator-mcp:latest cat /app/vllm_delegator.py | head -100"
            )
            console.print("\n[cyan]Look for MCP server setup:[/cyan]")
            console.print(
                r"podman run --rm localhost/vllm-delegator-mcp:latest grep -n -A5 -B5 'server\|transport\|stdio\|tcp' /app/vllm_delegator.py"
            )
            console.print(
                "\n[red]Root cause:[/red] MCP server hardcoded to stdio mode in vllm_delegator.py"
            )
            console.print(
                "[green]Solution:[/green] Modify MCP server initialization to use TCP transport"
            )

    def _show_fallback_problem_lines(
        self, extended_lines: List[str], shown_messages: set
    ) -> None:
        """Show fallback problem lines when no complete section is found"""
        problem_patterns = [
            "failed",
            "error",
            "invalid",
            "cannot",
            "unable",
            "denied",
            "refused",
            "timeout",
            "not found",
            "missing",
            "corrupt",
            "broken",
            "abort",
            "panic",
            "fatal",
            "critical",
            "exception",
        ]
        problem_lines = []
        for line in extended_lines:
            if line.strip():
                line_lower = line.lower()
                has_problem = any(pattern in line_lower for pattern in problem_patterns)
                # Only add if not already shown in the first section
                if has_problem and line.strip() not in shown_messages:
                    problem_lines.append(line)

        # Remove duplicates by message content but keep most recent timestamp
        problem_message_dict = {}

        for line in problem_lines:
            # Extract the actual message content (after timestamp and service info)
            cleaned_msg = re.sub(
                r"^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+\S+\[?\d*\]?:?\s*",
                "",
                line,
            )
            cleaned_msg = re.sub(
                r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+\S+\[?\d*\]?:?\s*",
                "",
                cleaned_msg,
            )

            # Use the cleaned message as key, keep the most recent full message
            if cleaned_msg.strip():
                problem_message_dict[cleaned_msg.strip()] = line

        # Convert back to list
        unique_problem_lines = list(problem_message_dict.values())

        # Show the most recent unique problem lines (last 5)
        for line in unique_problem_lines[-5:]:
            self._format_and_print_log_line(line)

    def _show_recommended_actions(self, target: str, service_name: str) -> None:
        """Show recommended actions for troubleshooting"""
        console.print("[green]Recommended actions:[/green]")
        console.print(
            f"[green]  View podman logs:[/green] [white]pm logs {target}[/white]"
        )
        console.print(
            f"[green]  View service config:[/green] [white]systemctl --user cat {service_name}[/white]"
        )
        console.print(
            f"[green]  Diagnose the issue:[/green] [white]pm diagnose {target}[/white]"
        )
        console.print(
            f"[green]  Reset failed state:[/green] [white]pm reset-failed {target}[/white]"
        )
        console.print()

    def _format_and_print_log_line(self, line: str) -> None:
        """Format and print a log line with appropriate colors"""
        # Split line into timestamp/service prefix and message content
        prefix_match = re.match(
            r"^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\.?\d*\s+\S+\s+\S+\[?\d*\]?:?)\s*(.*)",
            line,
        )
        if not prefix_match:
            # Try ISO timestamp format
            prefix_match = re.match(
                r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.?\d*\s+\S+\s+\S+\[?\d*\]?:?)\s*(.*)",
                line,
            )

        if prefix_match:
            prefix = prefix_match.group(1)
            message = prefix_match.group(2)

            # Apply colors based on message content only
            message_lower = message.lower()

            # Check for error patterns that should be red
            if any(
                pattern in message_lower
                for pattern in [
                    "failed",
                    "error",
                    "invalid",
                    "cannot",
                    "unable",
                    "denied",
                    "refused",
                    "timeout",
                    "not found",
                    "missing",
                    "corrupt",
                    "broken",
                    "abort",
                    "panic",
                    "fatal",
                    "critical",
                    "exception",
                ]
            ):
                console.print(f"[white]{prefix}[/white] [red]{message}[/red]")
            # Check for warning patterns that should be yellow
            elif any(
                pattern in message_lower
                for pattern in ["warning", "warn", "deprecated", "conflict"]
            ):
                console.print(f"[white]{prefix}[/white] [yellow]{message}[/yellow]")
            #
