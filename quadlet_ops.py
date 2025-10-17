"""Quadlet container operations for vLLM services."""

import subprocess
import time
from pathlib import Path
from typing import List

try:
    import requests
except ImportError:
    requests = None

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from config import console, verbose_print


class QuadletOperations:
    """Quadlet container operations for vLLM services"""

    def __init__(self, manager):
        self.manager = manager

    def _render_ansi_output(self, output: str) -> None:
        """Render ANSI-colored output from subprocess"""
        # For now, just print the output directly
        # Rich console should handle ANSI codes properly
        console.print(output)

    def _extract_log_message(self, log_line: str, msg_type: str) -> str:
        """Extract the actual error/warning message from a log line with timestamp"""
        import re

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

    def show_logs(self, target: str, follow: bool = False, tail: int = 100) -> None:
        """Show service logs using journalctl"""
        success = self.manager.show_logs(target, follow=follow, lines=tail)
        if not success:
            console.print("[dim]Try running: pm list to see available services[/dim]")

    def analyze_logs(self, target: str, lines: int = 50) -> None:
        """Analyze service logs for errors, warnings, and other issues"""
        import re
        import subprocess
        from collections import Counter

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

        except subprocess.TimeoutExpired:
            console.print("[red]Timeout while fetching logs[/red]")
        except Exception as e:
            console.print(f"[red]Error analyzing logs: {e}[/red]")

    def ai_analyze_logs(
        self, target: str, lines: int = 50, vllm_url: str = "http://localhost:8002"
    ) -> None:
        """AI-powered analysis of service logs for root causes and solutions"""
        import json
        import subprocess
        from datetime import datetime

        import requests

        self.manager._clear_auto_match_cache()
        service_name = self.manager._find_service_name(target)

        if not service_name:
            return

        console.print(
            f"[cyan]AI analyzing logs for {service_name} (last {lines} lines)...[/cyan]"
        )

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

            log_content = result.stdout.strip()

            # Check vLLM proxy availability
            try:
                health_response = requests.get(f"{vllm_url}/health", timeout=5)
                if health_response.status_code != 200:
                    console.print(f"[red]vLLM proxy not healthy at {vllm_url}[/red]")
                    return
            except requests.exceptions.RequestException as e:
                console.print(
                    f"[red]Cannot connect to vLLM proxy at {vllm_url}: {e}[/red]"
                )
                console.print(
                    "[dim]Make sure vLLM proxy is running: pm start vllm-proxy[/dim]"
                )
                return

            # Prepare AI analysis prompt
            analysis_prompt = f"""You are an expert system administrator and DevOps engineer. Analyze the following systemd service logs and provide:

1. **Root Cause Analysis**: Identify the primary issues causing errors or warnings
2. **Impact Assessment**: Severity and potential consequences of identified issues
3. **Recommended Solutions**: Specific, actionable steps to resolve the problems
4. **Prevention Strategies**: How to prevent these issues in the future

Service: {service_name}
Timestamp: {datetime.now().isoformat()}
Log Lines Analyzed: {len(log_content.split())}

=== LOG CONTENT ===
{log_content}
=== END LOG CONTENT ===

Provide a structured analysis focusing on actionable insights. If no significant issues are found, provide a brief health assessment."""

            # Call vLLM API
            api_payload = {
                "model": "qwen2.5-coder",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert system administrator and DevOps engineer specializing in systemd service log analysis and troubleshooting.",
                    },
                    {"role": "user", "content": analysis_prompt},
                ],
                "max_tokens": 2048,
                "temperature": 0.1,
                "stream": False,
            }

            console.print("[yellow]Analyzing logs with AI...[/yellow]")

            try:
                api_response = requests.post(
                    f"{vllm_url}/v1/chat/completions",
                    json=api_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )

                if api_response.status_code != 200:
                    console.print(
                        f"[red]AI analysis failed: HTTP {api_response.status_code}[/red]"
                    )
                    console.print(f"[red]{api_response.text}[/red]")
                    return

                response_data = api_response.json()
                ai_analysis = response_data["choices"][0]["message"]["content"]

                # Display results
                resolved_service = (
                    service_name.replace(".service", "")
                    if service_name.endswith(".service")
                    else service_name
                )
                # Convert back to short name for display
                if resolved_service == "vllm-qwen25-mcp":
                    display_service = "vllm-qwen25"
                elif resolved_service == "vllm-proxy-mcp":
                    display_service = "vllm-proxy"
                elif resolved_service == "vllm-delegator-mcp":
                    display_service = "vllm-delegator"
                else:
                    display_service = resolved_service

                console.print(
                    f"\n[bold green]🤖 AI Log Analysis for {display_service}[/bold green]"
                )
                console.print("=" * 60)
                console.print(ai_analysis)
                console.print("=" * 60)

                # Show follow-up commands with interactive menu
                console.print("\n[bold cyan]Follow-up Commands:[/bold cyan]")
                console.print(
                    f"[cyan]1[/cyan]  pm logs {display_service:<20}\t\t# View logs"
                )
                console.print(
                    f"[cyan]2[/cyan]  pm logs {display_service} --follow\t# Monitor live logs"
                )
                console.print(
                    f"[cyan]3[/cyan]  pm status {display_service:<18}\t\t# Check service status"
                )
                console.print(
                    f"[cyan]4[/cyan]  pm restart {display_service:<17}\t\t# Restart if needed"
                )
                console.print(
                    f"[cyan]5[/cyan]  pm log-ai-analyze {display_service}\t# Re-run AI analysis"
                )

                # Interactive command selection
                try:
                    choice = input(
                        "\nSelect command (1-5) or press Enter to skip: "
                    ).strip()
                    if choice and choice.isdigit():
                        choice_num = int(choice)
                        if 1 <= choice_num <= 5:

                            if choice_num == 1:
                                cmd = [
                                    "python",
                                    "podman_manager.py",
                                    "logs",
                                    display_service,
                                ]
                            elif choice_num == 2:
                                cmd = [
                                    "python",
                                    "podman_manager.py",
                                    "logs",
                                    display_service,
                                    "--follow",
                                ]
                            elif choice_num == 3:
                                cmd = [
                                    "python",
                                    "podman_manager.py",
                                    "status",
                                    display_service,
                                ]
                            elif choice_num == 4:
                                cmd = [
                                    "python",
                                    "podman_manager.py",
                                    "restart",
                                    display_service,
                                ]
                            elif choice_num == 5:
                                cmd = [
                                    "python",
                                    "podman_manager.py",
                                    "log-ai-analyze",
                                    display_service,
                                ]

                            console.print(f"\n[cyan]Executing: {' '.join(cmd)}[/cyan]")
                            subprocess.run(cmd)
                        else:
                            console.print(
                                "[yellow]Invalid choice. Please select 1-5[/yellow]"
                            )
                    elif choice:
                        console.print(
                            "[yellow]Invalid choice. Please select 1-5[/yellow]"
                        )
                except KeyboardInterrupt:
                    console.print("\n[yellow]Command selection cancelled[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error executing command: {e}[/red]")

            except requests.exceptions.Timeout:
                console.print("[red]AI analysis timed out (60s limit)[/red]")
            except requests.exceptions.RequestException as e:
                console.print(f"[red]AI analysis request failed: {e}[/red]")
            except json.JSONDecodeError as e:
                console.print(f"[red]Invalid JSON response from AI: {e}[/red]")
            except KeyError as e:
                console.print(f"[red]Unexpected AI response format: {e}[/red]")

        except subprocess.TimeoutExpired:
            console.print("[red]Timeout while fetching logs[/red]")
        except Exception as e:
            console.print(f"[red]Error in AI log analysis: {e}[/red]")

    def start(self, target: str, build: bool = False) -> bool:
        """Start a service or stack"""
        # PRIORITY 1: Check for stack names first
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._start_stack(project_name)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            return self._start_stack(target)

        # PRIORITY 3: Try service name resolution
        service_name = self.manager._find_service_name(target, allow_interactive=False)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._start_stack(stack_name)

        return self._start_service_with_build(target, build=build)

    def stop(self, target: str) -> bool:
        """Stop a service or stack"""
        # PRIORITY 1: Check for stack names first
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._stop_stack(project_name)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            return self._stop_stack(target)

        # PRIORITY 3: Try service name resolution
        service_name = self.manager._find_service_name(target, allow_interactive=False)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._stop_stack(stack_name)

        return self.manager.stop_service(target)

    def down(self, target: str = "vllm-stack") -> bool:
        """Stop all services in a stack or project"""
        console.print(f"[yellow]Stopping {target}...[/yellow]")

        # Handle stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._stop_stack(project_name)

        # For quadlet mode, we primarily work with the vllm-stack
        if target in ["vllm-stack", "stack", "vllm"]:
            # Try to stop the stack target first (suppress errors since it may not exist)
            service_name = self.manager._find_service_name("vllm-stack")
            if service_name:
                cmd = ["systemctl", "--user", "stop", service_name]
                result = self.manager._run_systemctl_command(
                    cmd, "stop_vllm-stack", suppress_errors=True, quiet=True
                )

                if result.returncode == 0:
                    console.print("[green]✓ All services stopped[/green]")
                    return True

            # Stack target doesn't exist or failed, stop individual services with force
            all_success = True

            # Only stop vLLM services for vllm-stack, not all quadlet services
            vllm_services = ["vllm-qwen25", "vllm-proxy", "vllm-delegator"]
            for service_name in vllm_services:
                if not self.manager.stop_service(service_name, force=True, quiet=False):
                    all_success = False

            if all_success:
                console.print("[green]✓ All services stopped[/green]")
                return True
            else:
                console.print("[yellow]⚠ Some services may still be running[/yellow]")
                return False
        else:
            # For other targets, try to stop as a single service/target with force
            success = self.manager.stop_service(target, force=True, quiet=False)
            return success

    def reset_failed(self, target: str) -> bool:
        """Reset failed service state"""
        self.manager._clear_auto_match_cache()
        service_name = self.manager._find_service_name(target, allow_interactive=False)

        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False

        console.print(f"[yellow]Resetting failed state for {target}...[/yellow]")

        cmd = ["systemctl", "--user", "reset-failed", service_name]
        verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(
                    f"[green]Successfully reset failed state for {target}[/green]"
                )
                return True
            else:
                console.print(
                    f"[red]Failed to reset failed state: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
                )
                return False
        except Exception as e:
            console.print(f"[red]Error resetting failed state: {e}[/red]")
            return False

    def show_service_file(self, target: str) -> bool:
        """Show service file contents"""
        self.manager._clear_auto_match_cache()
        service_name = self.manager._find_service_name(target, allow_interactive=False)

        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False

        console.print(f"[yellow]Showing service file for {target}...[/yellow]")

        cmd = ["systemctl", "--user", "cat", service_name]
        verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(f"\n[bold cyan]=== {service_name} ===[/bold cyan]")
                console.print(result.stdout)
                return True
            else:
                console.print(
                    f"[red]Failed to show service file: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
                )
                return False
        except Exception as e:
            console.print(f"[red]Error showing service file: {e}[/red]")
            return False

    def uninstall_stack(self, stack: str) -> bool:
        """Uninstall quadlet stack from systemd directory"""
        from installer import QuadletInstaller

        console.print(f"[green]Uninstalling {stack} stack...[/green]")

        try:
            installer = QuadletInstaller()
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            return False

        # Validate the stack or service first to get the resolved name
        is_valid, resolved_stack, service_file = installer.validate_stack_or_service(
            stack
        )
        if not is_valid:
            return False

        # Use the resolved stack name from validation
        full_stack_name = resolved_stack

        # Check systemd health
        if not installer.check_systemd_user_session():
            console.print(
                "[yellow]Systemd health check failed. Uninstallation may encounter issues.[/yellow]"
            )

        # Uninstall the stack
        success = installer.uninstall_stack(full_stack_name)

        if success:
            # Final success message
            console.print(f"[green]Successfully uninstalled {stack} stack[/green]")

        return success

    def restart(self, target: str, build: bool = False) -> bool:
        """Restart a service or stack"""
        # Clear cache at the start of the operation
        self.manager._clear_auto_match_cache()

        # PRIORITY 1: Check for stack names first
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._restart_stack(project_name)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            return self._restart_stack(target)

        # PRIORITY 3: Try service name resolution
        service_name = self.manager._find_service_name(target, allow_interactive=False)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._restart_stack(stack_name)

        # If we found a service, call manager.restart_service directly to avoid duplicate resolution
        if service_name:
            if build:
                # Stop first
                self.manager.stop_service(target, quiet=True)
                # Build
                if not self._build_service(target):
                    return False
                # Reload daemon
                self.manager.reload_daemon()

            # Call systemctl restart directly since we already resolved the service name
            cmd = ["systemctl", "--user", "restart", service_name]
            result = self.manager._run_systemctl_command(cmd, f"restart_{target}")

            if result.returncode == 0:
                console.print(f"[green]Restarted {service_name}[/green]")
                return True
            else:
                console.print(f"[red]Failed to restart {service_name}[/red]")
                return False
        else:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False

    def rebuild(self, target: str) -> bool:
        """Rebuild container image and restart service"""
        console.print(f"[yellow]Rebuilding {target}...[/yellow]")

        service_name = self.manager._find_service_name(target, allow_interactive=False)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._rebuild_stack(stack_name)

        # Handle legacy stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._rebuild_stack(project_name)

        # Handle individual service
        return self._rebuild_service(target)

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
            return self._reinit_stack("vllm", build_type=build_type)
        elif target == "taskflow-stack":
            return self._reinit_stack("taskflow", build_type=build_type)
        elif target.endswith("-stack"):
            # Generic stack target
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._reinit_stack(project_name, build_type=build_type)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        # Try to find it in discovered stacks before trying service resolution
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            return self._reinit_stack(target, build_type=build_type)

        # PRIORITY 3: Try service name resolution
        service_name = self.manager._find_service_name(target, allow_interactive=False)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._reinit_stack(stack_name, build_type=build_type)

        # PRIORITY 4: Handle individual service (only if not a stack)
        if service_name:
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
        console.print(f"\n[green]Reinitializing {target}...[/green]\n")

        # Use the provided service_name to avoid duplicate resolution
        # Stop the service
        verbose_print(f"[green]Stopping {target}...[/green]")
        stop_cmd = ["systemctl", "--user", "stop", service_name]
        verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
        stop_result = self.manager._run_systemctl_command(
            stop_cmd, f"stop_{target}", quiet=True
        )
        stop_success = stop_result.returncode == 0

        if stop_success:
            console.print(f"[green]Stopped {target}[/green]")
        else:
            console.print("[yellow]Service was not running or failed to stop[/yellow]")

        # Build if requested
        if build_type == "podman":
            console.print(f"[green]Building {target} (podman)...[/green]")
            build_success = self._build_service_podman(target)
            if not build_success:
                console.print("[red]Failed to build images[/red]")
                return False
        elif build_type in ["legacy", "quadlet"]:
            console.print(f"[green]Building {target} (quadlet)...[/green]")
            build_success = self._build_service(target)
            if not build_success:
                console.print("[red]Failed to build images[/red]")
                return False

        # Handle daemon reload
        verbose_print("[green]Reloading systemd daemon...[/green]")

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
        verbose_print(f"[green]Starting {target}...[/green]")
        start_cmd = ["systemctl", "--user", "start", service_name]
        verbose_print(f"[cyan]exec: {' '.join(start_cmd)}[/cyan]")
        start_result = self.manager._run_systemctl_command(
            start_cmd, f"start_{target}", quiet=True
        )
        start_success = start_result.returncode == 0

        if not start_success and start_result.stderr:
            # Extract and summarize the error message
            error_msg = start_result.stderr.strip()
            if "Job for" in error_msg and "failed because" in error_msg:
                # Extract service name from error
                import re

                service_match = re.search(r"Job for ([^\s]+) failed", error_msg)
                service_name_from_error = (
                    service_match.group(1) if service_match else target
                )

                console.print(
                    f"[red]❌ Service startup failed: {service_name_from_error}[/red]"
                )
                console.print("[yellow]💡 Recommended actions:[/yellow]")

                # Extract systemd-recommended commands from error message
                systemd_commands = []
                if 'See "' in error_msg:
                    # Find all commands between quotes after "See"
                    see_pattern = r'See "([^"]+)"'
                    matches = re.findall(see_pattern, error_msg)
                    systemd_commands = matches

                action_num = 1
                # Add systemd-recommended commands first
                for cmd in systemd_commands:
                    console.print(
                        f"[cyan]{action_num}.[/cyan] Run systemd command: [white]{cmd}[/white]"
                    )
                    action_num += 1

                # Add our standard troubleshooting commands
                console.print(
                    f"[cyan]{action_num}.[/cyan] Check service status: [white]pm status {target}[/white]"
                )
                console.print(
                    f"[cyan]{action_num + 1}.[/cyan] View detailed logs: [white]pm logs {target}[/white]"
                )
                console.print(
                    f"[cyan]{action_num + 2}.[/cyan] Diagnose the issue: [white]pm diagnose {target}[/white]"
                )
                console.print(
                    f"[cyan]{action_num + 3}.[/cyan] Reset failed state: [white]pm reset-failed {target}[/white]"
                )
            else:
                console.print(f"[red]Start failed: {error_msg}[/red]")

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
                console.print(f"[green]Started {target}[/green]")
                console.print(f"\n[green]Successfully reinitialized {target}[/green]\n")

                # Show optional next steps
                console.print("[green]Optional:[/green]")
                console.print(
                    f"[cyan]1.[/cyan] Check service status: [white]pm status {target}[/white]"
                )
                console.print(
                    f"[cyan]2.[/cyan] View detailed logs: [white]pm logs {target}[/white]"
                )
                console.print(
                    f"[cyan]3.[/cyan] Diagnose the issue: [white]pm diagnose {target}[/white]"
                )
                console.print(
                    f"[cyan]4.[/cyan] Reset failed state: [white]pm reset-failed {target}[/white]"
                )
                console.print()

                return True
            else:
                console.print(
                    f"[red]Failed to reinitialize {target} - service did not start properly[/red]\n"
                )
                # Show the detailed error logs and recommendations after the failure message
                self._show_startup_failure_logs(target, service_name)
                return False
        else:
            console.print(f"[red]Failed to start {target} after reinit[/red]")
            return False

    def _reinit_service(
        self, target: str, build: bool = False, build_type: str | None = None
    ) -> bool:
        """Reinit a single service"""
        # Handle backward compatibility
        if build and build_type is None:
            build_type = "legacy"

        # All services now use the standard reinit process with quadlet build

        # Standard reinit process for other services or when build=False
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold white]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            # Step 1: Stop the service
            task1 = progress.add_task("Step 1: Stopping service...", total=None)
            stop_success = self.manager.stop_service(target)
            progress.remove_task(task1)

            if not stop_success:
                console.print(
                    "[yellow]Service was not running or failed to stop[/yellow]"
                )
                # Check for systemd transport issues
                try:
                    test_cmd = ["systemctl", "--user", "is-system-running"]
                    console.print(f"[cyan]exec: {' '.join(test_cmd)}[/cyan]")
                    test_result = subprocess.run(
                        test_cmd,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if "Transport endpoint is not connected" in test_result.stderr:
                        console.print(
                            "[red]CRITICAL: Systemd user session is completely corrupted![/red]"
                        )
                        console.print(
                            "[red]This requires a complete user session restart:[/red]"
                        )
                        console.print("")
                        console.print("[yellow]REQUIRED RECOVERY STEPS:[/yellow]")
                        console.print("[cyan]1. Kill all systemd processes:[/cyan]")
                        console.print("[white]   pkill -u $USER systemd[/white]")
                        console.print("[cyan]2. Kill any remaining processes:[/cyan]")
                        console.print(
                            "[white]   pkill -u $USER -f 'systemd|dbus'[/white]"
                        )
                        console.print(
                            "[cyan]3. LOGOUT and LOGIN again (required!)[/cyan]"
                        )
                        console.print(
                            "[red]   - Close all terminals and applications[/red]"
                        )
                        console.print(
                            "[red]   - Logout from your desktop session[/red]"
                        )
                        console.print(
                            "[red]   - Login again to get fresh systemd session[/red]"
                        )
                        console.print("")
                        console.print(
                            "[red]WARNING: daemon-reexec will hang - don't try it![/red]"
                        )
                        console.print(
                            "[red]Cannot proceed with any systemd operations until fixed![/red]"
                        )
                        return False  # Abort the operation
                except (subprocess.TimeoutExpired, Exception):
                    console.print(
                        "[yellow]Systemd may be in an unstable state[/yellow]"
                    )

            # Step 2: Build if requested
            if build_type == "podman":
                task2 = progress.add_task(
                    "Step 2: Building images (podman build)...", total=None
                )
                build_success = self._build_service_podman(target)
                progress.remove_task(task2)

                if not build_success:
                    console.print("[red]Failed to build images[/red]")
                    return False
            elif build_type in ["legacy", "quadlet"]:
                task2 = progress.add_task(
                    "Step 2: Building images (quadlet build)...", total=None
                )
                build_success = self._build_service(target)
                progress.remove_task(task2)

                if not build_success:
                    console.print("[red]Failed to build images[/red]")
                    return False

            # Step 3: Handle daemon reload and timing
            if build_type not in ["legacy", "quadlet"]:
                # For podman build, we need to reload daemon manually
                task3 = progress.add_task(
                    f"Step {'3' if build_type else '2'}: Reloading systemd daemon...",
                    total=None,
                )
                reload_success = self.manager.reload_daemon()
                progress.remove_task(task3)

                if not reload_success:
                    console.print("[red]Failed to reload systemd daemon[/red]")
                    return False
            else:
                # Quadlet build script already reloaded daemon, add delay and force another reload

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold white]{task.description}"),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(
                        "Waiting for systemd to process new quadlet files...",
                        total=None,
                    )
                    time.sleep(5)  # Give systemd more time to process new quadlet files
                    progress.remove_task(task)

                # Force another daemon reload to ensure new services are recognized
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold white]{task.description}"),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(
                        "Running additional daemon reload to ensure service recognition...",
                        total=None,
                    )
                    reload_success = self.manager.reload_daemon()
                    progress.remove_task(task)

                if not reload_success:
                    console.print(
                        "[yellow]Warning: Additional daemon reload failed[/yellow]"
                    )
                else:
                    time.sleep(2)  # Brief pause after reload

            # Debug: Check if service is available before starting
            if build_type in ["legacy", "quadlet"]:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold white]{task.description}"),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(
                        f"Checking if {target} service is available...", total=None
                    )
                    # Try to find the actual service name
                    service_name = self.manager._find_service_name(
                        target, allow_interactive=False
                    )
                    progress.remove_task(task)

                if service_name:
                    console.print(f"Found service: {service_name}")

                    # Additional verification: check if service file exists and add extra delay
                    from pathlib import Path

                    # Check if the .container file exists
                    container_file = (
                        Path.home()
                        / ".config/containers/systemd"
                        / f"{target.replace('-mcp', '')}-mcp.container"
                    )
                    if container_file.exists():
                        console.print(
                            f"[dim]Container file exists: {container_file}[/dim]"
                        )
                    else:
                        console.print(
                            f"[yellow]Warning: Container file not found: {container_file}[/yellow]"
                        )

                    # Force systemd to re-scan for new units
                    console.print(
                        "[dim]Forcing systemd to re-scan for new units...[/dim]"
                    )

                    scan_cmd = ["systemctl", "--user", "daemon-reload"]
                    console.print(f"[cyan]exec: {' '.join(scan_cmd)}[/cyan]")
                    scan_result = subprocess.run(
                        scan_cmd,
                        capture_output=True,
                        text=True,
                    )
                    if scan_result.returncode != 0:
                        console.print(
                            f"[yellow]Warning: Final daemon-reload failed: {scan_result.stderr}[/yellow]"
                        )

                    # Check what systemd actually sees
                    console.print(
                        f"[dim]Checking systemd unit status for {service_name}...[/dim]"
                    )
                    status_cmd = ["systemctl", "--user", "cat", service_name]
                    console.print(f"[cyan]exec: {' '.join(status_cmd)}[/cyan]")
                    status_result = subprocess.run(
                        status_cmd,
                        capture_output=True,
                        text=True,
                    )
                    if status_result.returncode == 0:
                        console.print("[dim]Systemd can see the unit definition[/dim]")
                    else:
                        console.print(
                            f"[yellow]Systemd cannot see unit: {status_result.stderr.strip() if status_result.stderr else 'Unknown error'}[/yellow]"
                        )
                        # Try to manually trigger quadlet generation
                        console.print(
                            "[dim]Attempting to manually trigger quadlet generation...[/dim]"
                        )

                        # Force quadlet to regenerate service files

                        quadlet_dir = Path.home() / ".config/containers/systemd"
                        console.print(f"[dim]Quadlet directory: {quadlet_dir}[/dim]")

                        # List all .container files to verify they exist
                        container_files = list(quadlet_dir.glob("*.container"))
                        console.print(
                            f"[dim]Found {len(container_files)} .container files[/dim]"
                        )
                        for cf in container_files:
                            console.print(f"[dim]  - {cf.name}[/dim]")

                        # Try multiple approaches to trigger quadlet
                        console.print(
                            "[dim]Triggering quadlet service generation...[/dim]"
                        )

                        # Method 1: Force daemon-reload with verbose output
                        reload_cmd = ["systemctl", "--user", "daemon-reload"]
                        console.print(f"[cyan]exec: {' '.join(reload_cmd)}[/cyan]")
                        reload_result = subprocess.run(
                            reload_cmd,
                            capture_output=True,
                            text=True,
                        )
                        if reload_result.returncode != 0:
                            console.print(
                                f"[yellow]Daemon reload failed: {reload_result.stderr}[/yellow]"
                            )

                        # Method 2: Check if quadlet generator is working
                        gen_cmd = [
                            "systemctl",
                            "--user",
                            "list-unit-files",
                            "--type=service",
                            "*quadlet*",
                        ]
                        console.print(f"[cyan]exec: {' '.join(gen_cmd)}[/cyan]")
                        gen_check = subprocess.run(
                            gen_cmd,
                            capture_output=True,
                            text=True,
                        )
                        if gen_check.returncode == 0 and gen_check.stdout:
                            console.print("[dim]Quadlet generator services found[/dim]")

                        # Method 3: Try to manually run quadlet generator (if available)
                        # This is a last resort - quadlet should work automatically
                        time.sleep(3)

                        # Final daemon reload
                        final_reload_cmd = ["systemctl", "--user", "daemon-reload"]
                        console.print(
                            f"[cyan]exec: {' '.join(final_reload_cmd)}[/cyan]"
                        )
                        subprocess.run(
                            final_reload_cmd,
                            capture_output=True,
                            text=True,
                        )
                        time.sleep(2)

                        # Check again if service is now visible
                        recheck_cmd = ["systemctl", "--user", "cat", service_name]
                        console.print(f"[cyan]exec: {' '.join(recheck_cmd)}[/cyan]")
                        recheck_result = subprocess.run(
                            recheck_cmd,
                            capture_output=True,
                            text=True,
                        )
                        if recheck_result.returncode == 0:
                            console.print(
                                "[green]Service is now visible to systemd![/green]"
                            )
                        else:
                            console.print(
                                f"[red]Service still not visible: {recheck_result.stderr.strip() if recheck_result.stderr else 'Unknown error'}[/red]"
                            )

                            # Last resort: Check quadlet logs and try user systemd restart
                            console.print(
                                "[dim]Checking for quadlet generation errors...[/dim]"
                            )
                            try:
                                journal_cmd = [
                                    "journalctl",
                                    "--user",
                                    "-u",
                                    "systemd",
                                    "--since",
                                    "1 minute ago",
                                    "-n",
                                    "10",
                                ]
                                console.print(
                                    f"[cyan]exec: {' '.join(journal_cmd)}[/cyan]"
                                )
                                journal_result = subprocess.run(
                                    journal_cmd,
                                    capture_output=True,
                                    text=True,
                                    timeout=5,
                                )
                                if (
                                    journal_result.returncode == 0
                                    and "quadlet" in journal_result.stdout.lower()
                                ):
                                    console.print(
                                        "[dim]Recent quadlet activity in journal:[/dim]"
                                    )
                                    for line in journal_result.stdout.split("\n")[-3:]:
                                        if line.strip():
                                            console.print(
                                                f"[dim]  {line.strip()}[/dim]"
                                            )
                                else:
                                    console.print(
                                        "[dim]No recent quadlet errors found in journal[/dim]"
                                    )
                            except subprocess.TimeoutExpired:
                                console.print(
                                    "[yellow]Journal check timed out, skipping log analysis[/yellow]"
                                )
                            except Exception as e:
                                console.print(
                                    f"[yellow]Journal check failed: {e}[/yellow]"
                                )

                            # Try restarting user systemd (with timeout to prevent hanging)
                            console.print(
                                "[yellow]Attempting to restart user systemd instance...[/yellow]"
                            )
                            try:
                                restart_cmd = ["systemctl", "--user", "daemon-reexec"]
                                console.print(
                                    f"[cyan]exec: {' '.join(restart_cmd)}[/cyan]"
                                )
                                restart_result = subprocess.run(
                                    restart_cmd,
                                    capture_output=True,
                                    text=True,
                                    timeout=10,
                                )
                                if restart_result.returncode == 0:
                                    console.print(
                                        "[dim]User systemd restarted, waiting for stabilization...[/dim]"
                                    )
                                    time.sleep(3)

                                    # Final check after restart
                                    final_check_cmd = [
                                        "systemctl",
                                        "--user",
                                        "cat",
                                        service_name,
                                    ]
                                    console.print(
                                        f"[cyan]exec: {' '.join(final_check_cmd)}[/cyan]"
                                    )
                                    final_check = subprocess.run(
                                        final_check_cmd,
                                        capture_output=True,
                                        text=True,
                                    )
                                    if final_check.returncode == 0:
                                        console.print(
                                            "[green]Service is now visible after systemd restart![/green]"
                                        )
                                    else:
                                        console.print(
                                            f"[red]Service still not visible after restart: {final_check.stderr.strip() if final_check.stderr else 'Unknown error'}[/red]"
                                        )
                                        console.print(
                                            "[red]This indicates a deeper quadlet configuration issue[/red]"
                                        )
                                else:
                                    console.print(
                                        f"[red]Failed to restart user systemd: {restart_result.stderr}[/red]"
                                    )
                            except subprocess.TimeoutExpired:
                                console.print(
                                    "[yellow]Systemd restart timed out, skipping this step[/yellow]"
                                )
                            except Exception as e:
                                console.print(
                                    f"[yellow]Systemd restart failed: {e}[/yellow]"
                                )

                            # Final attempt: Just proceed with the start attempt anyway
                            console.print(
                                "[dim]Proceeding with service start attempt despite visibility issues...[/dim]"
                            )

                    # Add extra delay before starting to ensure systemd fully processes the service
                    console.print(
                        "[dim]Adding final delay to ensure service is fully ready...[/dim]"
                    )

                    time.sleep(5)  # Increased to 5 seconds

                else:
                    console.print(
                        f"[yellow]Warning: Could not find service for {target}[/yellow]"
                    )
                    # List available services for debugging

                    list_cmd = [
                        "systemctl",
                        "--user",
                        "list-unit-files",
                        "--type=service",
                        "*vllm*",
                    ]
                    console.print(f"[cyan]exec: {' '.join(list_cmd)}[/cyan]")
                    result = subprocess.run(
                        list_cmd,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0 and result.stdout:
                        console.print("[dim]Available vLLM services:[/dim]")
                        for line in result.stdout.split("\n"):
                            if "vllm" in line.lower():
                                console.print(f"[dim]  {line.strip()}[/dim]")

            # Step 4: Restart the service
            task4 = progress.add_task(
                f"Step {'4' if build_type else '3'}: Restarting service...", total=None
            )

            service_name = self.manager._find_service_name(
                target, allow_interactive=False
            )
            if service_name:
                restart_cmd = ["systemctl", "--user", "restart", service_name]
                console.print(f"  [cyan]exec: {' '.join(restart_cmd)}[/cyan]")
                restart_result = subprocess.run(
                    restart_cmd, capture_output=True, text=True
                )
                start_success = restart_result.returncode == 0
                if not start_success and restart_result.stderr:
                    console.print(
                        f"[red]Restart failed: {restart_result.stderr.strip() if restart_result.stderr else 'Unknown error'}[/red]"
                    )
            else:
                console.print(f"[red]Could not find service for {target}[/red]")
                start_success = False

            progress.remove_task(task4)

            if start_success:
                console.print(f"[green]Successfully reinitialized {target}[/green]")
                return True
            else:
                console.print(f"[red]Failed to start {target} after reinit[/red]")
                return False

    def _reinit_stack(
        self, project: str, build: bool = False, build_type: str | None = None
    ) -> bool:
        """Reinit an entire project stack"""
        console.print(f"\n[green]Reinitializing {project} stack...[/green]\n")

        services = self._get_stack_services(project)

        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        verbose_print(f"[green]Stopping all {project} services...[/green]")
        stop_success = True
        for service in services:
            verbose_print(f"  Stopping {service}...")
            if not self.manager.stop_service(service, quiet=False):
                stop_success = False

        if not stop_success:
            console.print(
                "[yellow]Some services were not running or failed to stop[/yellow]"
            )

        # Step 2: Build if requested
        if build_type:
            # Handle backward compatibility
            if build and build_type is None:
                build_type = "legacy"

            if build_type == "podman":
                console.print(
                    f"[green]Building {project} images (podman build)...[/green]"
                )
                build_success = self._build_stack_podman(project, services)
            elif build_type in ["legacy", "quadlet"]:
                console.print(
                    f"[green]Building {project} images (quadlet build)...[/green]"
                )
                build_success = self._build_stack(project, services)
            else:
                build_success = True  # No build requested

            if not build_success:
                console.print(f"[red]Failed to build images for {project} stack[/red]")
                return False

        # Handle daemon reload and timing
        verbose_print("[green]Reloading systemd daemon...[/green]")

        if build_type not in ["legacy", "quadlet"]:
            # For podman build, we need to reload daemon manually
            reload_success = self.manager.reload_daemon()

            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False
        else:
            # Quadlet build script already reloaded daemon, add delay and force another reload

            time.sleep(3)  # Give systemd time to process new quadlet files

            # Force another daemon reload to ensure new services are recognized
            reload_success = self.manager.reload_daemon()

            if not reload_success:
                console.print(
                    "[yellow]Warning: Additional daemon reload failed[/yellow]"
                )
            else:
                time.sleep(1)  # Brief pause after reload

        # Restart all services
        verbose_print(f"[green]Starting all {project} services...[/green]")
        start_success = True
        for service in services:
            verbose_print(f"[dim]  Starting {service}...[/dim]")
            service_name = self.manager._find_service_name(
                service, allow_interactive=False
            )
            if service_name:
                restart_cmd = ["systemctl", "--user", "restart", service_name]
                verbose_print(f"  [cyan]exec: {' '.join(restart_cmd)}[/cyan]")
                restart_result = subprocess.run(
                    restart_cmd, capture_output=True, text=True
                )
                if restart_result.returncode == 0:
                    # Monitor service startup for this service
                    with Progress(
                        SpinnerColumn(),
                        TextColumn(f"[yellow]Monitoring {service} startup...[/yellow]"),
                        console=console,
                        transient=True,
                    ) as progress:
                        task = progress.add_task("monitoring", total=None)
                        service_success = self._monitor_service_startup(
                            service, service_name
                        )
                        progress.remove_task(task)

                    if service_success:
                        console.print(f"[green]Started {service}[/green]")
                    else:
                        start_success = False
                        # Show detailed error logs after spinner disappears
                        console.print(
                            f"[red]Failed to start {service} - service did not start properly[/red]\n"
                        )
                        self._show_startup_failure_logs(service, service_name)
                else:
                    start_success = False
                    if restart_result.stderr:
                        # Extract and summarize the error message
                        error_msg = restart_result.stderr.strip()
                        if "Job for" in error_msg and "failed because" in error_msg:
                            # Extract service name from error
                            import re

                            service_match = re.search(
                                r"Job for ([^\s]+) failed", error_msg
                            )
                            service_name_from_error = (
                                service_match.group(1) if service_match else service
                            )

                            console.print(
                                f"[red]❌ Service startup failed: {service} ({service_name_from_error})[/red]"
                            )
                            console.print(
                                f"[yellow]💡 Recommended actions for {service}:[/yellow]"
                            )

                            # Extract systemd-recommended commands from error message
                            systemd_commands = []
                            if 'See "' in error_msg:
                                # Find all commands between quotes after "See"
                                see_pattern = r'See "([^"]+)"'
                                matches = re.findall(see_pattern, error_msg)
                                systemd_commands = matches

                            action_num = 1
                            # Add systemd-recommended commands first
                            for cmd in systemd_commands:
                                console.print(
                                    f"[cyan]{action_num}.[/cyan] Run systemd command: [white]{cmd}[/white]"
                                )
                                action_num += 1

                            # Add our standard troubleshooting commands
                            console.print(
                                f"[cyan]{action_num}.[/cyan] Check service status: [white]pm status {service}[/white]"
                            )
                            console.print(
                                f"[cyan]{action_num + 1}.[/cyan] View detailed logs: [white]pm logs {service}[/white]"
                            )
                            console.print(
                                f"[cyan]{action_num + 2}.[/cyan] Diagnose the issue: [white]pm diagnose {service}[/white]"
                            )
                            console.print(
                                f"[cyan]{action_num + 3}.[/cyan] Reset failed state: [white]pm reset-failed {service}[/white]"
                            )
                        else:
                            console.print(
                                f"[red]Restart failed for {service}: {error_msg}[/red]"
                            )
            else:
                console.print(f"[red]Could not find service for {service}[/red]")
                start_success = False

        if start_success:
            console.print(
                f"\n[green]Successfully reinitialized {project} stack[/green]\n"
            )

            # Show optional next steps for the stack
            console.print("[green]Optional:[/green]")
            console.print(
                f"[cyan]1.[/cyan] Check service status: [white]pm status {project}[/white]"
            )
            console.print(
                f"[cyan]2.[/cyan] View detailed logs: [white]pm logs {project}[/white]"
            )
            console.print(
                f"[cyan]3.[/cyan] Diagnose the issue: [white]pm diagnose {project}[/white]"
            )
            console.print(
                f"[cyan]4.[/cyan] Reset failed state: [white]pm reset-failed {project}[/white]"
            )
            console.print()

            return True
        else:
            console.print(
                f"[red]Failed to start some services in {project} stack[/red]"
            )
            return False

    def enable(self, target: str) -> bool:
        """Enable a service or stack to start at boot"""
        service_name = self.manager._find_service_name(target, allow_interactive=False)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._enable_stack(stack_name)

        # Handle legacy stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._enable_stack(project_name)

        return self.manager.enable_service(target)

    def disable(self, target: str) -> bool:
        """Disable a service or stack from starting at boot"""
        service_name = self.manager._find_service_name(target, allow_interactive=False)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._disable_stack(stack_name)

        # Handle legacy stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._disable_stack(project_name)

        return self.manager.disable_service(target)

    def reload_daemon(self) -> bool:
        """Reload systemd user daemon"""
        return self.manager.reload_daemon()

    def show_service_status(self, target: str) -> None:
        """Show detailed status for a specific service"""
        self.manager._clear_auto_match_cache()
        service_name = self.manager._find_service_name(target, allow_interactive=False)

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            self._show_stack_status(stack_name)
            return

        # Handle legacy stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            self._show_stack_status(project_name)
            return

        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return

        # Use systemctl status for detailed output
        cmd = ["systemctl", "--user", "status", service_name]
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[yellow]{result.stderr}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error getting service status: {e}[/red]")

    def install_stack(self, stack: str) -> bool:
        """Install/build quadlet stack or service using integrated installer module"""
        from installer import QuadletInstaller

        try:
            installer = QuadletInstaller()
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            return False

        # Check if it's a stack or service first to show correct message
        is_valid, resolved_stack, service_file = installer.validate_stack_or_service(
            stack
        )
        if not is_valid:
            return False

        console.print()
        if service_file:
            console.print(f"[green]Installing {stack} service...[/green]")
        else:
            console.print(f"[green]Installing {stack} stack...[/green]")
        console.print()

        # Check systemd health
        if not installer.check_systemd_user_session():
            console.print(
                "[yellow]Systemd health check failed. Installation may encounter issues.[/yellow]"
            )

        # Install the stack or service - pass original user input, not resolved stack
        success = installer.install_stack(stack)

        if success:
            # Final success message - use appropriate term based on what was installed
            if service_file:
                console.print(f"[green]Successfully installed {stack} service[/green]")
            else:
                console.print(f"[green]Successfully installed {stack} stack[/green]")
            console.print()

        return success

    def update_images_and_restart(self, target: str) -> bool:
        """Update container images and restart service (for quadlets with auto-update)"""
        console.print(f"[yellow]Updating images for {target}...[/yellow]")

        # For quadlets, we can trigger podman auto-update
        update_cmd = ["podman", "auto-update"]
        console.print(f"[cyan]exec: {' '.join(update_cmd)}[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Updating container images", total=None)
            result = subprocess.run(update_cmd, capture_output=True, text=True)
            progress.remove_task(task)

        if result.returncode == 0:
            console.print("[green]Images updated successfully[/green]")
            if result.stdout:
                console.print(result.stdout)

            # Restart the service to use updated images
            return self.restart(target)
        else:
            console.print(
                f"[red]Failed to update images: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
            )
            return False

    def check_auto_update_status(self) -> None:
        """Check if podman auto-update timer is enabled"""
        console.print("[yellow]Checking auto-update status...[/yellow]")

        # Check if auto-update timer is enabled
        timer_cmd = ["systemctl", "--user", "is-enabled", "podman-auto-update.timer"]
        console.print(f"[cyan]exec: {' '.join(timer_cmd)}[/cyan]")

        result = subprocess.run(timer_cmd, capture_output=True, text=True)

        if result.returncode == 0 and "enabled" in result.stdout:
            console.print("[green]Podman auto-update timer is enabled[/green]")

            # Show next run time
            next_cmd = [
                "systemctl",
                "--user",
                "list-timers",
                "podman-auto-update.timer",
            ]
            next_result = subprocess.run(next_cmd, capture_output=True, text=True)
            if next_result.returncode == 0:
                console.print(next_result.stdout)
        else:
            console.print("[yellow]Podman auto-update timer is not enabled[/yellow]")
            console.print(
                "[dim]Enable with: systemctl --user enable --now podman-auto-update.timer[/dim]"
            )

    def enable_auto_update(self) -> bool:
        """Enable podman auto-update timer"""
        console.print("[yellow]Enabling podman auto-update timer...[/yellow]")

        cmd = ["systemctl", "--user", "enable", "--now", "podman-auto-update.timer"]
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print("[green]Podman auto-update timer enabled[/green]")
            return True
        else:
            console.print(
                f"[red]Failed to enable auto-update timer: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
            )
            return False

    def trigger_auto_update(self) -> bool:
        """Manually trigger podman auto-update"""
        console.print("[yellow]Triggering manual auto-update...[/yellow]")

        cmd = ["systemctl", "--user", "start", "podman-auto-update.service"]
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print("[green]Auto-update triggered successfully[/green]")
            return True
        else:
            console.print(
                f"[red]Failed to trigger auto-update: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
            )
            return False

    def show_container_status(self) -> None:
        """Show status of containers managed by quadlets"""
        console.print("[yellow]Checking container status...[/yellow]")

        # Get containers that might be managed by our quadlets
        cmd = [
            "podman",
            "ps",
            "-a",
            "--format",
            "{{.Names}};{{.Image}};{{.Status}};{{.Ports}}",
            "--filter",
            "label=io.containers.autoupdate=registry",
        ]

        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            from rich.table import Table

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Image", style="dim", max_width=40)
            table.add_column("Status", no_wrap=True)
            table.add_column("Ports", style="blue", max_width=30)

            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split(";")
                    if len(parts) >= 4:
                        name, image, status, ports = parts[:4]

                        # Color code status
                        if "Up" in status or "running" in status.lower():
                            colored_status = f"[green]{status}[/green]"
                        elif "Exited" in status:
                            colored_status = f"[red]{status}[/red]"
                        else:
                            colored_status = f"[yellow]{status}[/yellow]"

                        table.add_row(name, image, colored_status, ports)

            console.print(table)
        else:
            console.print("[dim]No containers with auto-update labels found[/dim]")

    def exec_command(self, target: str, command: List[str]) -> None:
        """Execute command in container (find container by service name)"""
        # First, we need to find the container name from the service
        self.manager._clear_auto_match_cache()
        service_name = self.manager._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return

        # Get the container name associated with this service
        # This is tricky with quadlets - we need to infer the container name
        # Usually it's based on the service name
        container_name = target
        if target in self.manager.vllm_services:
            # Use the short name as container name
            container_name = target

        cmd = ["podman", "exec", "-it", container_name] + command
        console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            subprocess.run(cmd)
        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")
            console.print(
                f"[dim]Container '{container_name}' may not be running or accessible[/dim]"
            )

    def prune_containers(self, enhanced: bool = True, quick: bool = False) -> None:
        """Remove unused containers and images with intelligent analysis

        Args:
            enhanced: Use enhanced prune with analysis (default: True)
            quick: Use quick prune mode (default: False)
        """
        if enhanced and not quick:
            # Use enhanced prune with full analysis
            from prune import EnhancedPruner

            pruner = EnhancedPruner(console)
            success = pruner.run_safe_prune_workflow()
            if not success:
                console.print(
                    "[yellow]Enhanced prune failed, falling back to basic prune[/yellow]"
                )
                self._basic_prune_containers()
        elif quick:
            # Use quick prune from enhanced pruner
            from prune import EnhancedPruner

            pruner = EnhancedPruner(console)
            pruner.run_quick_prune()
        else:
            # Use basic prune
            self._basic_prune_containers()

    def _basic_prune_containers(self) -> None:
        """Basic prune functionality (original implementation)"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold white]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                # Step 1: Prune containers
                task1 = progress.add_task("Pruning unused containers...", total=None)
                result1 = subprocess.run(
                    ["podman", "container", "prune", "-f"],
                    capture_output=True,
                    text=True,
                )
                progress.remove_task(task1)

                if result1.returncode != 0:
                    console.print(
                        f"[yellow]Container prune warning: {result1.stderr.strip()}[/yellow]"
                    )

                # Step 2: Prune images
                task2 = progress.add_task("Pruning unused images...", total=None)
                result2 = subprocess.run(
                    ["podman", "image", "prune", "-f"], capture_output=True, text=True
                )
                progress.remove_task(task2)

                if result2.returncode != 0:
                    console.print(
                        f"[yellow]Image prune warning: {result2.stderr.strip()}[/yellow]"
                    )

            console.print("[green]Prune completed[/green]")

            # Show what was cleaned up if there's output
            if result1.stdout.strip():
                console.print(f"[dim]Containers: {result1.stdout.strip()}[/dim]")
            if result2.stdout.strip():
                console.print(f"[dim]Images: {result2.stdout.strip()}[/dim]")

        except Exception as e:
            console.print(f"[red]Error pruning: {e}[/red]")

    def prune(self, enhanced: bool = True, quick: bool = False) -> None:
        """Alias for prune_containers for compatibility"""
        self.prune_containers(enhanced=enhanced, quick=quick)

    def show_system_df(self) -> None:
        """Show system disk usage"""
        df_cmd = ["podman", "system", "df"]
        console.print(f"[cyan]exec: {' '.join(df_cmd)}[/cyan]")

        result = subprocess.run(df_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            console.print(result.stdout)
        else:
            error_msg = (
                result.stderr.strip() if result.stderr.strip() else "Unknown error"
            )
            console.print(f"[red]Failed to get system disk usage: {error_msg}[/red]")

    def _get_stack_services(self, project: str) -> List[str]:
        """Get list of services for a project stack"""
        # Normalize project name to stack name format
        if not project.endswith("-stack"):
            stack_name = f"{project}-stack"
        else:
            stack_name = project

        # Look up in discovered stack services
        if (
            hasattr(self.manager, "stack_services")
            and stack_name in self.manager.stack_services
        ):
            return self.manager.stack_services[stack_name]

        # If not found, return empty list
        return []

    def _start_stack(self, project: str) -> bool:
        """Start all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Starting {project} stack...[/yellow]")

        success = True
        for service in services:
            console.print(f"[dim]  Starting {service}...[/dim]")
            if not self.manager.start_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully started {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to start[/yellow]"
            )
        return success

    def _stop_stack(self, project: str) -> bool:
        """Stop all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Stopping {project} stack...[/yellow]")

        success = True
        stopped_services = []
        failed_services = []

        for service in services:
            console.print(f"  Stopping {service}...")
            if self.manager.stop_service(service, quiet=False):
                stopped_services.append(service)
            else:
                failed_services.append(service)
                success = False

        if success:
            console.print(
                f"[green]Successfully stopped {project} stack ({len(stopped_services)} services)[/green]"
            )
        else:
            if stopped_services:
                console.print(
                    f"[yellow]Partially stopped {project} stack: {len(stopped_services)} succeeded, {len(failed_services)} failed[/yellow]"
                )
                console.print(f"[dim]  Stopped: {', '.join(stopped_services)}[/dim]")
                console.print(f"[dim]  Failed: {', '.join(failed_services)}[/dim]")
            else:
                console.print(
                    f"[yellow]No services in {project} stack were running or could be stopped[/yellow]"
                )
        return success

    def _restart_stack(self, project: str) -> bool:
        """Restart all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Restarting {project} stack...[/yellow]")

        success = True
        for service in services:
            console.print(f"[dim]  Restarting {service}...[/dim]")
            if not self.manager.restart_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully restarted {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to restart[/yellow]"
            )
        return success

    def _enable_stack(self, project: str) -> bool:
        """Enable all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Enabling {project} stack...[/yellow]")
        success = True
        for service in services:
            console.print(f"[dim]  Enabling {service}...[/dim]")
            if not self.manager.enable_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully enabled {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to enable[/yellow]"
            )
        return success

    def _disable_stack(self, project: str) -> bool:
        """Disable all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Disabling {project} stack...[/yellow]")
        success = True
        for service in services:
            console.print(f"[dim]  Disabling {service}...[/dim]")
            if not self.manager.disable_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully disabled {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to disable[/yellow]"
            )
        return success

    def _show_stack_logs(
        self, project: str, follow: bool = False, tail: int = 100
    ) -> None:
        """Show logs for all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return

        console.print(f"[yellow]Showing logs for {project} stack services...[/yellow]")

        if follow:
            console.print(
                "[dim]Note: Following logs for multiple services - press Ctrl+C to stop[/dim]"
            )
            # For follow mode, show logs for all services in parallel (simplified approach)
            for service in services:
                console.print(f"\n[bold cyan]=== {service} ===[/bold cyan]")
                self.manager.show_logs(
                    service, follow=False, lines=tail // len(services)
                )

            # Then follow the first service (most common use case)
            if services:
                console.print(
                    f"\n[bold cyan]=== Following {services[0]} ===[/bold cyan]"
                )
                self.manager.show_logs(services[0], follow=True, lines=tail)
        else:
            # For non-follow mode, show logs for each service
            for service in services:
                console.print(f"\n[bold cyan]=== {service} ===[/bold cyan]")
                self.manager.show_logs(
                    service, follow=False, lines=tail // len(services)
                )

    def _show_stack_status(self, project: str) -> None:
        """Show status for all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return

        console.print(f"[bold cyan]{project.title()} Stack Status[/bold cyan]")

        for service in services:
            console.print(f"\n[bold yellow]=== {service} ===[/bold yellow]")
            service_name = self.manager._find_service_name(service)
            if service_name:
                cmd = [
                    "systemctl",
                    "--user",
                    "status",
                    service_name,
                    "--no-pager",
                    "-l",
                ]
                console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.stdout:
                        console.print(result.stdout)
                    if result.stderr:
                        console.print(f"[yellow]{result.stderr}[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error getting status for {service}: {e}[/red]")
            else:
                console.print(f"[red]Service '{service}' not found[/red]")

    def _update_stack(self, project: str) -> bool:
        """Update images and restart all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Updating images for {project} stack...[/yellow]")

        # For quadlets, we can trigger podman auto-update
        update_cmd = ["podman", "auto-update"]
        console.print(f"[cyan]exec: {' '.join(update_cmd)}[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Updating {project} stack images", total=None)
            result = subprocess.run(update_cmd, capture_output=True, text=True)
            progress.remove_task(task)

        if result.returncode == 0:
            console.print("[green]Images updated successfully[/green]")
            if result.stdout:
                console.print(result.stdout)

            # Restart all services in the stack
            return self._restart_stack(project)
        else:
            console.print(
                f"[red]Failed to update images: {result.stderr.strip()}[/red]"
            )
            return False

    def _build_service(self, target: str) -> bool:
        """Build images for a single service using quadlet build process"""
        try:
            # Use the quadlet installation script for building
            return self._build_service_quadlet(target)

        except Exception as e:
            console.print(f"[red]Error building {target}: {e}[/red]")
            return False

    def _build_service_quadlet(self, target: str) -> bool:
        """Build service using quadlet installation script"""
        try:
            from pathlib import Path

            # Path to the quadlet installation script
            script_path = "/home/pwp/srv/apps/podman_manager/pm_install_containers.py"

            if not Path(script_path).exists():
                console.print(
                    f"[red]Quadlet installation script not found: {script_path}[/red]"
                )
                return False

            # Map service names to quadlet groups
            # Remove -mcp suffix if present to get the base service name
            service_name = target.replace("-mcp", "")

            # Map service names to quadlet group names
            service_to_group = {
                "vllm-delegator": "vllm",
                "vllm-proxy": "vllm",
                "vllm-qwen25": "vllm",
                "taskflow-backend": "taskflow",
                "taskflow-frontend": "taskflow",
            }

            # Determine the quadlet group
            if service_name in service_to_group:
                quadlet_group = service_to_group[service_name]
            else:
                # For other services, try to extract group from service name
                if "-" in service_name:
                    quadlet_group = service_name.split("-")[0]
                else:
                    quadlet_group = service_name

            console.print(
                f"[yellow]🔨 Building quadlet group '{quadlet_group}' for service '{target}'...[/yellow]"
            )

            # Run the quadlet installation script with timeout
            build_cmd = [script_path, quadlet_group, "user"]
            console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")

            try:
                result = subprocess.run(
                    build_cmd, capture_output=True, text=True, timeout=120
                )  # 2 minute timeout
            except subprocess.TimeoutExpired:
                console.print(
                    "[red]❌ Quadlet build script timed out after 2 minutes[/red]"
                )
                return False

            if result.returncode == 0:
                if result.stdout:
                    # Show the script output with ANSI colors rendered
                    self._render_ansi_output(result.stdout.strip())
                console.print(f"[green]✅ Quadlet build completed for {target}[/green]")
                return True
            else:
                console.print(f"[red]❌ Quadlet build failed for {target}[/red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr.strip()}[/red]")
                if result.stdout:
                    self._render_ansi_output(result.stdout.strip())
                return False

        except Exception as e:
            console.print(f"[red]Error in quadlet build for {target}: {e}[/red]")
            return False

    def _build_service_podman(self, target: str) -> bool:
        """Build images using regular podman build (not specialized rebuild)"""
        try:
            # For podman build, we need to find Dockerfiles in standard locations
            import os
            from pathlib import Path

            # Common Dockerfile locations for different services
            dockerfile_locations = {
                "vllm-delegator": (
                    "/home/pwp/srv/coding_agent/mcp/mcp-vllm-delegator",
                    "Dockerfile-vllm-delegator",
                ),
                "vllm-delegator-mcp": (
                    "/home/pwp/srv/coding_agent/mcp/mcp-vllm-delegator",
                    "Dockerfile-vllm-delegator",
                ),
                "vllm-proxy": (
                    "/home/pwp/srv/local-ai-packaged/vllm-proxy",
                    "Dockerfile.vllm_proxy",
                ),
                "vllm-proxy-mcp": (
                    "/home/pwp/srv/local-ai-packaged/vllm-proxy",
                    "Dockerfile.vllm_proxy",
                ),
            }

            if target in dockerfile_locations:
                build_dir, dockerfile = dockerfile_locations[target]
                if not Path(build_dir).exists():
                    console.print(f"[red]Build directory not found: {build_dir}[/red]")
                    return False

                original_cwd = os.getcwd()
                try:
                    os.chdir(build_dir)

                    if not Path(dockerfile).exists():
                        console.print(f"[red]Dockerfile not found: {dockerfile}[/red]")
                        return False

                    # Determine image name
                    if target in ["vllm-delegator", "vllm-delegator-mcp"]:
                        image_name = "localhost/vllm-delegator-mcp:latest"
                    elif target in ["vllm-proxy", "vllm-proxy-mcp"]:
                        image_name = "localhost/vllm-proxy:latest"
                    else:
                        image_name = f"localhost/{target}:latest"

                    build_cmd = [
                        "podman",
                        "build",
                        "--no-cache",
                        "-f",
                        dockerfile,
                        "-t",
                        image_name,
                        ".",
                    ]
                    console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")

                    result = subprocess.run(build_cmd, capture_output=True, text=True)

                    if result.returncode == 0:
                        console.print(
                            f"[green]Podman build completed for {target}[/green]"
                        )
                        return True
                    else:
                        console.print(f"[red]Podman build failed for {target}[/red]")
                        if result.stderr:
                            console.print(f"[red]{result.stderr.strip()}[/red]")
                        return False

                finally:
                    os.chdir(original_cwd)
            else:
                console.print(
                    f"[yellow]No podman build configuration for {target}, skipping[/yellow]"
                )
                return True  # Not an error, just no build needed

        except Exception as e:
            console.print(f"[red]Error in podman build for {target}: {e}[/red]")
            return False

    def _rebuild_vllm_delegator_mcp(self) -> bool:
        """Rebuild vLLM Delegator MCP container image (for quadlet management)"""
        import os

        # Initialize original_cwd to prevent unbound variable error
        original_cwd = os.getcwd()

        # Configuration for vLLM Delegator MCP rebuild
        CONTAINER_NAME = "vllm-delegator-mcp"
        IMAGE_NAME = "localhost/vllm-delegator-mcp:latest"
        DOCKERFILE = "Dockerfile-vllm-delegator"
        MCP_SERVICE_DIR = "/home/pwp/srv/coding_agent/mcp/mcp-vllm-delegator"

        console.print("[yellow]🔨 Rebuilding vLLM Delegator MCP image...[/yellow]")

        try:
            # Change to the MCP service directory
            original_cwd = os.getcwd()
            if not Path(MCP_SERVICE_DIR).exists():
                console.print(
                    f"[red]MCP service directory not found: {MCP_SERVICE_DIR}[/red]"
                )
                return False

            os.chdir(MCP_SERVICE_DIR)

            # Function to check if container exists
            def container_exists():
                result = subprocess.run(
                    ["podman", "container", "exists", CONTAINER_NAME],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0

            # Function to check if container is running
            def container_running():
                result = subprocess.run(
                    [
                        "podman",
                        "container",
                        "inspect",
                        CONTAINER_NAME,
                        "--format",
                        "{{.State.Running}}",
                    ],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0 and result.stdout.strip() == "true"

            # Stop and remove existing container if it exists (quietly)
            if container_exists():
                if container_running():
                    subprocess.run(
                        ["podman", "stop", CONTAINER_NAME],
                        capture_output=True,
                        text=True,
                    )
                subprocess.run(
                    ["podman", "rm", CONTAINER_NAME], capture_output=True, text=True
                )

            # Remove old image to force rebuild (quietly)
            subprocess.run(
                ["podman", "rmi", IMAGE_NAME], capture_output=True, text=True
            )

            # Build new image
            console.print(f"[yellow]🔨 Building new image: {IMAGE_NAME}[/yellow]")
            if not Path(DOCKERFILE).exists():
                console.print(f"[red]Dockerfile not found: {DOCKERFILE}[/red]")
                return False

            build_cmd = [
                "podman",
                "build",
                "--no-cache",
                "-f",
                DOCKERFILE,
                "-t",
                IMAGE_NAME,
                ".",
            ]
            console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")
            build_result = subprocess.run(build_cmd, capture_output=True, text=True)

            if build_result.returncode != 0:
                console.print("[red]❌ Build failed![/red]")
                if build_result.stderr:
                    console.print(f"[red]{build_result.stderr.strip()}[/red]")
                return False

            console.print("[green]✅ Image rebuilt successfully[/green]")

            return True

        except Exception as e:
            console.print(f"[red]Error during vLLM Delegator MCP rebuild: {e}[/red]")
            return False
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    def _rebuild_vllm_proxy(self) -> bool:
        """Rebuild vLLM Proxy container image (for quadlet management)"""
        import os

        # Initialize original_cwd to prevent unbound variable error
        original_cwd = os.getcwd()

        # Configuration for vLLM Proxy rebuild
        CONTAINER_NAME = "vllm-proxy"
        IMAGE_NAME = "localhost/vllm-proxy:latest"
        DOCKERFILE = "Dockerfile.vllm_proxy"
        PROXY_SERVICE_DIR = "/home/pwp/srv/local-ai-packaged/vllm-proxy"

        console.print("[yellow]🔨 Rebuilding vLLM Proxy image...[/yellow]")

        try:
            # Change to the proxy service directory
            original_cwd = os.getcwd()
            if not Path(PROXY_SERVICE_DIR).exists():
                console.print(
                    f"[red]Proxy service directory not found: {PROXY_SERVICE_DIR}[/red]"
                )
                return False

            os.chdir(PROXY_SERVICE_DIR)

            # Function to check if container exists
            def container_exists():
                result = subprocess.run(
                    ["podman", "container", "exists", CONTAINER_NAME],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0

            # Function to check if container is running
            def container_running():
                result = subprocess.run(
                    [
                        "podman",
                        "container",
                        "inspect",
                        CONTAINER_NAME,
                        "--format",
                        "{{.State.Running}}",
                    ],
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0 and result.stdout.strip() == "true"

            # Stop and remove existing container if it exists (quietly)
            if container_exists():
                if container_running():
                    subprocess.run(
                        ["podman", "stop", CONTAINER_NAME],
                        capture_output=True,
                        text=True,
                    )
                subprocess.run(
                    ["podman", "rm", CONTAINER_NAME], capture_output=True, text=True
                )

            # Remove old image to force rebuild (quietly)
            subprocess.run(
                ["podman", "rmi", IMAGE_NAME], capture_output=True, text=True
            )

            # Build new image
            console.print(f"[yellow]🔨 Building new image: {IMAGE_NAME}[/yellow]")
            if not Path(DOCKERFILE).exists():
                console.print(f"[red]Dockerfile not found: {DOCKERFILE}[/red]")
                return False

            build_cmd = [
                "podman",
                "build",
                "--no-cache",
                "-f",
                DOCKERFILE,
                "-t",
                IMAGE_NAME,
                ".",
            ]
            console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")
            build_result = subprocess.run(build_cmd, capture_output=True, text=True)

            if build_result.returncode != 0:
                console.print("[red]❌ Build failed![/red]")
                if build_result.stderr:
                    console.print(f"[red]{build_result.stderr.strip()}[/red]")
                return False

            console.print("[green]✅ Image rebuilt successfully[/green]")

            return True

        except Exception as e:
            console.print(f"[red]Error during vLLM Proxy rebuild: {e}[/red]")
            return False
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    def diagnose_container_failure(self, target: str) -> None:
        """Diagnose why a container is failing to start"""
        self.manager._clear_auto_match_cache()
        service_name = self.manager._find_service_name(target)
        if not service_name:
            console.print(f"[red]Service '{target}' not found[/red]")
            return

        console.print(f"[yellow]🔍 Diagnosing {target} container failure...[/yellow]")

        # Check systemd service status
        console.print("\n[cyan]📊 Service Status:[/cyan]")
        status_cmd = ["systemctl", "--user", "status", service_name, "--no-pager", "-l"]
        console.print(f"[cyan]exec: {' '.join(status_cmd)}[/cyan]")
        status_result = subprocess.run(status_cmd, capture_output=True, text=True)
        if status_result.stdout:
            console.print(status_result.stdout)

        # Try to run the container manually to see what fails
        console.print("\n[cyan]🧪 Testing container manually:[/cyan]")

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
            console.print(f"[yellow]No diagnostic available for {target}[/yellow]")
            return

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
            subprocess.run(["podman", "stop", container_name], capture_output=True)
        except KeyboardInterrupt:
            console.print("\n[yellow]Test interrupted by user[/yellow]")
            subprocess.run(["podman", "stop", container_name], capture_output=True)

        # Show recent logs from the actual service
        console.print("\n[cyan]📋 Recent service logs:[/cyan]")
        logs_cmd = [
            "journalctl",
            "--user",
            "-u",
            service_name,
            "-n",
            "20",
            "--no-pager",
        ]
        console.print(f"[cyan]exec: {' '.join(logs_cmd)}[/cyan]")
        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)
        if logs_result.stdout:
            console.print(logs_result.stdout)

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

    def _rebuild_service(self, target: str) -> bool:
        """Rebuild a single service"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold white]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            # Step 1: Stop the service
            task1 = progress.add_task("Step 1: Stopping service...", total=None)
            stop_success = self.manager.stop_service(target)
            progress.remove_task(task1)

            if not stop_success:
                console.print(
                    "[yellow]Service was not running or failed to stop[/yellow]"
                )

            # Step 2: Build the service (this will call our specialized rebuild methods)
            task2 = progress.add_task("Step 2: Rebuilding image...", total=None)
            build_success = self._build_service(target)
            progress.remove_task(task2)

            if not build_success:
                console.print("[red]Failed to rebuild image[/red]")
                return False

            # Step 3: Reload systemd daemon
            task3 = progress.add_task("Step 3: Reloading systemd daemon...", total=None)
            reload_success = self.manager.reload_daemon()
            progress.remove_task(task3)

            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False

            # Step 4: Start the service
            task4 = progress.add_task("Step 4: Starting service...", total=None)
            start_success = self.manager.start_service(target)
            progress.remove_task(task4)

            if start_success:
                console.print(f"[green]Successfully rebuilt {target}[/green]")
                return True
            else:
                console.print(f"[red]Failed to start {target} after rebuild[/red]")
                return False

    def _rebuild_stack(self, project: str) -> bool:
        """Rebuild an entire project stack"""
        if project == "vllm":
            services = ["vllm-qwen25", "vllm-proxy", "vllm-delegator"]
            display_name = "vLLM stack"
        elif project == "taskflow":
            services = ["taskflow-frontend", "taskflow-backend"]
            display_name = "taskflow stack"
        else:
            # Generic project - find services that start with project name
            services = [
                short_name
                for short_name in self.manager.quadlet_services.keys()
                if short_name.startswith(f"{project}-")
            ]
            display_name = f"{project} stack"

        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold white]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            # Step 1: Stop all services
            task1 = progress.add_task(
                f"Step 1: Stopping all {project} services...", total=None
            )
            stop_success = True
            for service in services:
                if not self.manager.stop_service(service, quiet=False):
                    stop_success = False
            progress.remove_task(task1)

            if not stop_success:
                console.print(
                    "[yellow]Some services were not running or failed to stop[/yellow]"
                )

            # Step 2: Rebuild all services
            task2 = progress.add_task(
                f"Step 2: Rebuilding {project} images...", total=None
            )
            build_success = self._build_stack(project, services)
            progress.remove_task(task2)

            if not build_success:
                console.print(
                    f"[red]Failed to rebuild images for {project} stack[/red]"
                )
                return False

            # Step 3: Reload systemd daemon
            task3 = progress.add_task("Step 3: Reloading systemd daemon...", total=None)
            reload_success = self.manager.reload_daemon()
            progress.remove_task(task3)

            if not reload_success:
                console.print("[red]Failed to reload systemd daemon[/red]")
                return False

            # Step 4: Start all services
            task4 = progress.add_task(
                f"Step 4: Starting all {project} services...", total=None
            )
            start_success = True
            for service in services:
                if not self.manager.start_service(service):
                    start_success = False
            progress.remove_task(task4)

            if start_success:
                console.print(f"[green]Successfully rebuilt {display_name}[/green]")
                return True
            else:
                console.print(
                    f"[red]Failed to start some services in {display_name}[/red]"
                )
                return False

    def _build_stack(self, project: str, services: List[str]) -> bool:
        """Build images for all services in a stack using quadlet build process"""
        success = True
        for service in services:
            if not self._build_service(service):
                success = False
        return success

    def _build_stack_podman(self, project: str, services: List[str]) -> bool:
        """Build images for all services in a stack using podman build"""
        success = True
        for service in services:
            if not self._build_service_podman(service):
                success = False
        return success

    def _start_service_with_build(self, target: str, build: bool = False) -> bool:
        """Start a service with optional build"""
        if build:
            if not self._build_service(target):
                return False
        return self.manager.start_service(target)

    def _monitor_service_startup(
        self, target: str, service_name: str, timeout: int = 10
    ) -> bool:
        """Monitor service logs to verify successful startup"""
        import time

        # Wait a moment for service to start
        time.sleep(5)

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
        console.print(f"[red]❌ Service startup failed for {target}[/red]")
        console.print("[yellow]Recent error logs:[/yellow]")

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

        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)

        if logs_result.returncode == 0 and logs_result.stdout:
            # Filter and show only error-related lines
            lines = logs_result.stdout.strip().split("\n")
            error_lines = []

            for line in lines:
                line_lower = line.lower()
                if any(
                    pattern in line_lower
                    for pattern in [
                        "error",
                        "failed",
                        "exception",
                        "traceback",
                        "fatal",
                        "critical",
                    ]
                ):
                    error_lines.append(line)

            if error_lines:
                for line in error_lines[-5:]:  # Show last 5 error lines
                    console.print(f"[dim]{line}[/dim]")
            else:
                # Show last few lines if no specific errors found
                for line in lines[-3:]:
                    if line.strip():
                        console.print(f"[dim]{line}[/dim]")

        # Show recommended actions
        console.print("[yellow]💡 Recommended actions:[/yellow]")
        console.print(
            f"[cyan]1.[/cyan] Check service status: [white]systemctl --user status {service_name}[/white]"
        )
        console.print(
            f"[cyan]2.[/cyan] View detailed logs: [white]journalctl --user -xeu {service_name}[/white]"
        )
        console.print(
            f"[cyan]3.[/cyan] Check service status: [white]pm status {target}[/white]"
        )
        console.print(
            f"[cyan]4.[/cyan] View detailed logs: [white]pm logs {target}[/white]"
        )
        console.print(
            f"[cyan]5.[/cyan] Diagnose the issue: [white]pm diagnose {target}[/white]"
        )
        console.print(
            f"[cyan]6.[/cyan] Reset failed state: [white]pm reset-failed {target}[/white]"
        )

    def _restart_service_with_build(self, target: str, build: bool = False) -> bool:
        """Restart a service with optional build"""
        if build:
            # Stop first (clear cache to prevent duplicate messages)
            self.manager._clear_auto_match_cache()
            self.manager.stop_service(target, quiet=True)
            # Build
            if not self._build_service(target):
                return False
            # Reload daemon
            self.manager.reload_daemon()
            # Clear cache again before restart
            self.manager._clear_auto_match_cache()
        return self.manager.restart_service(target)
