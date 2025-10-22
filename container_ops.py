"""Container lifecycle operations."""

import subprocess
import time
from pathlib import Path
from typing import List

try:
    import requests
except ImportError:
    requests = None

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ai_diagnostics import AIDiagnostics
from config import console


class ContainerOperations:
    """Container lifecycle operations"""

    def __init__(self, manager):
        self.manager = manager
        self.ai_diagnostics = AIDiagnostics(manager)

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

    def handle_container_dependencies(self, service: str) -> bool:
        """Handle container removal by checking status first, then stopping if needed"""
        try:
            # First, check if container exists and its status
            status_cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                f"name=^{service}$",
                "--format",
                "{{.Names}} {{.Status}}",
            ]
            console.print(f"  [cyan]exec: {' '.join(status_cmd)}[/cyan]")
            status_result = subprocess.run(status_cmd, capture_output=True, text=True)

            if status_result.returncode != 0:
                console.print("[yellow]Warning checking container status[/yellow]")
                # Continue with removal attempt anyway

            container_info = status_result.stdout.strip()
            if not container_info:
                console.print(f"[dim]Container {service} does not exist[/dim]")
                return True  # Already removed, success

            # Check if container is running and stop it first if needed
            if "Up" in container_info or "running" in container_info.lower():
                console.print("[green]Stopping container...[/green]")
                # Stop the container first
                stop_cmd = ["podman", "stop", service]
                console.print(f"  [cyan]exec: {' '.join(stop_cmd)}[/cyan]")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(
                        f"Stopping container: {service}", total=None
                    )
                    stop_result = subprocess.run(
                        stop_cmd, capture_output=True, text=True
                    )
                    progress.remove_task(task)

                if stop_result.returncode != 0:
                    stop_error = stop_result.stderr.strip()
                    if "did not die within timeout" in stop_error.lower():
                        console.print(
                            "[green]Container took longer than expected to stop (SIGKILL used)[/green]"
                        )
                    else:
                        console.print(
                            f"[yellow]Warning stopping container: {stop_error}[/yellow]"
                        )

                # Verify container has fully stopped before attempting removal
                max_wait = 5  # Maximum seconds to wait
                wait_time = 0.0
                while wait_time < max_wait:
                    time.sleep(0.5)
                    wait_time += 0.5

                    # Check if container is still stopping
                    status_check_cmd = [
                        "podman",
                        "ps",
                        "-a",
                        "--filter",
                        f"name=^{service}$",
                        "--format",
                        "{{.Status}}",
                    ]
                    status_check = subprocess.run(
                        status_check_cmd, capture_output=True, text=True
                    )

                    if status_check.returncode == 0:
                        status = status_check.stdout.strip()
                        if (
                            "stopping" not in status.lower()
                            and "up" not in status.lower()
                        ):
                            break
                        elif wait_time >= max_wait:
                            console.print(
                                f"[yellow]Container still stopping after {max_wait}s, proceeding anyway[/yellow]"
                            )
                    else:
                        break  # If status check fails, proceed with removal

            # Now remove the container (after ensuring it's stopped)
            console.print(f"[green]Removing: {service}[/green]")
            rm_cmd = ["podman", "rm", service]
            console.print(f"  [cyan]exec: {' '.join(rm_cmd)}[/cyan]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Removing container: {service}", total=None)
                rm_result = subprocess.run(rm_cmd, capture_output=True, text=True)
                progress.remove_task(task)

            if rm_result.returncode == 0:
                console.print(f"[green]Container removed: {service}[/green]")
                return True
            else:
                error_msg = rm_result.stderr.strip()
                if "dependent containers" in error_msg.lower():
                    console.print(
                        "[yellow]Container has dependencies, handling...[/yellow]"
                    )
                    return self._handle_dependent_containers(service, error_msg)
                elif "no such container" in error_msg.lower():
                    console.print(f"[dim]Container {service} already removed[/dim]")
                    return True
                else:
                    console.print(
                        f"[red]Error removing container: {error_msg or 'Unknown error'}[/red]"
                    )
                    return False

        except Exception as e:
            console.print(f"[red]Error handling container removal: {e}[/red]")
            return False

    def _handle_dependent_containers(self, service: str, error_msg: str) -> bool:
        """Handle containers with dependencies"""
        try:
            # Extract dependent container IDs from error message
            import re

            dep_pattern = r"dependent containers.*?before it: ([a-f0-9]+):"
            matches = re.findall(dep_pattern, error_msg)

            if matches:
                # Get names of dependent containers and remove them
                for dep_id in matches:
                    name_cmd = [
                        "podman",
                        "ps",
                        "-a",
                        "--filter",
                        f"id={dep_id}",
                        "--format",
                        "{{.Names}}",
                    ]
                    console.print(f"  [cyan]exec: {' '.join(name_cmd)}[/cyan]")
                    name_result = subprocess.run(
                        name_cmd, capture_output=True, text=True
                    )

                    if name_result.returncode == 0 and name_result.stdout.strip():
                        dep_name = name_result.stdout.strip()
                        console.print(
                            f"[green]Removing dependent container: {dep_name} ({dep_id[:12]})[/green]"
                        )

                        # Remove dependent container with force
                        dep_rm_cmd = ["podman", "rm", "-f", dep_name]
                        console.print(f"  [cyan]exec: {' '.join(dep_rm_cmd)}[/cyan]")
                        dep_result = subprocess.run(
                            dep_rm_cmd, capture_output=True, text=True
                        )

                        if dep_result.returncode == 0:
                            console.print(
                                f"[green]Removed dependent container: {dep_name}[/green]"
                            )
                        else:
                            console.print(
                                f"[yellow]Warning removing {dep_name}: {dep_result.stderr.strip()}[/yellow]"
                            )

                # Now try to remove the main container again
                console.print(f"[green]Retrying removal of {service}...[/green]")
                rm_cmd = ["podman", "rm", service]
                console.print(f"  [cyan]exec: {' '.join(rm_cmd)}[/cyan]")
                rm_result = subprocess.run(rm_cmd, capture_output=True, text=True)

                if rm_result.returncode == 0:
                    console.print(
                        f"[green]Successfully removed container: {service}[/green]"
                    )
                    return True
                else:
                    console.print(
                        f"[red]Still failed to remove {service}: {rm_result.stderr.strip()}[/red]"
                    )
                    return False
            else:
                console.print(
                    "[yellow]Could not parse dependency information from error[/yellow]"
                )
                return False

        except Exception as e:
            console.print(f"[red]Error handling dependencies: {e}[/red]")
            return False

    def show_logs(self, target: str, follow: bool = False, tail: int = 100) -> None:
        """Show container logs"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            # Check if container exists first
            check_cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                f"name={target}",
                "--format",
                "{{.Names}}",
            ]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True)

            if not check_result.stdout.strip():
                console.print(
                    f"[yellow]Container '{target}' not found or not running[/yellow]"
                )
                console.print(
                    "[dim]Try running: pm list to see available services[/dim]"
                )
                return

            cmd = ["podman", "compose", "-f", project, "logs", target, "--"]
            if tail > 0:
                cmd.extend(["-n", str(tail)])
            if follow:
                cmd.append("-f")

            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode != 0:
                console.print(
                    f"[yellow]No logs available for {target} or container not running[/yellow]"
                )

        except Exception as e:
            console.print(f"[red]Error showing logs: {e}[/red]")

    def analyze_logs(self, target: str, lines: int = 50) -> None:
        """Analyze container logs for errors, warnings, and other issues"""
        import re
        import subprocess
        from collections import Counter

        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            # Get the actual matched service name
            matched_service = self.manager.get_matched_service_name(target)

            # Check if container exists first
            check_cmd = [
                "podman",
                "ps",
                "-a",
                "--filter",
                f"name={matched_service}",
                "--format",
                "{{.Names}}",
            ]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True)

            if not check_result.stdout.strip():
                console.print(
                    f"[yellow]Container '{matched_service}' not found or not running[/yellow]"
                )
                console.print(
                    "[dim]Try running: pm list to see available services[/dim]"
                )
                return

            console.print(
                f"Analyzing logs for {matched_service} (last {lines} lines)..."
            )

            # Get logs using podman logs
            cmd = ["podman", "logs", "--tail", str(lines), matched_service]
            console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                console.print(
                    f"[red]Failed to get logs: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
                )
                return

            if not result.stdout.strip():
                console.print(f"[yellow]No logs found for {matched_service}[/yellow]")
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
                    r"\b500\b",
                    r"\b404\b",  # HTTP errors
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
                    "\n[red]⚠ Check error logs immediately - container may be failing[/red]"
                )
            elif warnings > 10:
                console.print(
                    "\n[yellow]⚠ High warning count - investigate configuration[/yellow]"
                )

            # Follow-up commands with interactive menu
            # Use the matched service name for commands
            cmd_service = matched_service

            console.print("\nFollow-up Commands:")
            console.print(
                f"[cyan]1[/cyan]  pm logs {cmd_service} -ai\t\t# Analyze logs with AI"
            )
            console.print(f"[cyan]2[/cyan]  pm logs {cmd_service:<20}\t\t# View logs")
            console.print(
                f"[cyan]3[/cyan]  pm logs {cmd_service} --follow\t# Monitor live logs"
            )
            console.print(
                f"[cyan]4[/cyan]  pm status {cmd_service:<18}\t\t# Check service status"
            )
            if errors > 0:
                console.print(
                    f"[cyan]5[/cyan]  pm restart {cmd_service:<17}\t\t# Restart if needed"
                )
                max_option = 5
            else:
                max_option = 4

            # Interactive command selection
            try:
                choice = input(
                    f"\nSelect command (1-{max_option}) or press Enter to skip: "
                ).strip()
                if choice and choice.isdigit():
                    choice_num = int(choice)
                    if 1 <= choice_num <= max_option:
                        import subprocess

                        if choice_num == 1:
                            cmd = [
                                "python",
                                "podman_manager.py",
                                "logs",
                                cmd_service,
                                "-ai",
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
        self,
        target: str,
        lines: int = 50,
        vllm_url: str = "http://localhost:8002",
        verbose: bool = False,
    ) -> None:
        """AI-powered analysis of container logs for root causes and solutions"""
        # For compose mode, we need to adapt the target to work with the AI diagnostics
        # The AI diagnostics expects a service name that can be resolved by the manager
        self.ai_diagnostics.ai_analyze_logs(target, lines, vllm_url, verbose)

    def exec_command(self, target: str, command: List[str]) -> None:
        """Execute command in container"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            cmd = ["podman", "compose", "-f", project, "exec", target] + command
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            subprocess.run(cmd, cwd=self.manager.compose_dir)

        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")

    def build(self, target: str, no_cache: bool = False) -> None:
        """Build container images"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            cmd = ["podman", "compose", "-f", project, "build"]
            if no_cache:
                cmd.append("--no-cache")
            cmd.append(target)

            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Build completed for {target}[/green]")
            else:
                console.print(f"[red]Build failed for {target}[/red]")

        except Exception as e:
            console.print(f"[red]Error building: {e}[/red]")

    def prune(self, enhanced: bool = True, quick: bool = False) -> None:
        """Remove unused images and containers with intelligent analysis

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
                self._basic_prune()
        elif quick:
            # Use quick prune from enhanced pruner
            from prune import EnhancedPruner

            pruner = EnhancedPruner(console)
            pruner.run_quick_prune()
        else:
            # Use basic prune
            self._basic_prune()

    def _basic_prune(self) -> None:
        """Basic prune functionality (original implementation)"""
        try:
            console.print("[yellow]Pruning unused containers...[/yellow]")
            prune_containers_cmd = ["podman", "container", "prune", "-f"]
            console.print(f"  [cyan]exec: {' '.join(prune_containers_cmd)}[/cyan]")
            subprocess.run(prune_containers_cmd)

            console.print("[yellow]Pruning unused images...[/yellow]")
            prune_images_cmd = ["podman", "image", "prune", "-f"]
            console.print(f"  [cyan]exec: {' '.join(prune_images_cmd)}[/cyan]")
            subprocess.run(prune_images_cmd)

            console.print("[green]Prune completed[/green]")

        except Exception as e:
            console.print(f"[red]Error pruning: {e}[/red]")

    def diagnose_container_failure(self, target: str) -> bool:
        """Diagnose container startup failures - only available in quadlet mode"""
        console.print("[red]Diagnose command only available in quadlet mode[/red]")
        return False

    def reset_failed(self, target: str) -> bool:
        """Reset failed service state - only available in quadlet mode"""
        console.print("[red]Reset-failed command only available in quadlet mode[/red]")
        return False

    def show_service_file(self, target: str) -> bool:
        """Show service file contents - only available in quadlet mode"""
        console.print(
            "[red]Show-service-file command only available in quadlet mode[/red]"
        )
        return False

    def install_stack(self, target: str) -> bool:
        """Install quadlet stack - only available in quadlet mode"""
        console.print("[red]Install command only available in quadlet mode[/red]")
        return False

    def uninstall_stack(self, target: str) -> bool:
        """Uninstall quadlet stack - only available in quadlet mode"""
        console.print("[red]Uninstall command only available in quadlet mode[/red]")
        return False

    def remove(self, target: str) -> None:
        """Remove containers"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            cmd = ["podman", "compose", "-f", project, "rm", "-f", target]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Removed {target}[/green]")
            else:
                console.print(f"[red]Failed to remove {target}[/red]")

        except Exception as e:
            console.print(f"[red]Error removing: {e}[/red]")

    def pull(self, target: str) -> None:
        """Pull latest images"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            cmd = ["podman", "compose", "-f", project, "pull", target]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Pulled latest images for {target}[/green]")
            else:
                console.print(f"[red]Failed to pull images for {target}[/red]")

        except Exception as e:
            console.print(f"[red]Error pulling: {e}[/red]")

    def reinit(
        self,
        target: str,
        build: bool = False,
        dry_run: bool = False,
        remove_orphans: bool = False,
        build_type: str | None = None,
    ) -> bool:
        """Reinitialize containers (remove and recreate)

        Args:
            target: Stack or service name
            build: Whether to build images (legacy parameter)
            dry_run: Show what would be done without executing
            remove_orphans: Remove orphaned containers
            build_type: Type of build ('legacy', 'podman', 'quadlet') - for compatibility with QuadletOperations
        """
        try:
            # Check if target is a stack name first
            stacks = self.manager._parse_compose_files()
            compose_file = None
            is_stack = False

            # Check if target is a stack name
            for stack_name, stack_info in stacks.items():
                if target == stack_name:
                    compose_file = stack_info["file"]
                    is_stack = True
                    break

            # If not a stack, try to find by service name
            if not compose_file:
                service_stack = self.manager._find_service_project(target)
                if not service_stack:
                    console.print(f"[red]Service or stack '{target}' not found[/red]")
                    return False
                compose_file = self.manager.compose_dir / service_stack
                is_stack = False

            if dry_run:
                console.print(f"[yellow]DRY RUN: Would reinitialize {target}[/yellow]")
                console.print("[dim]Steps that would be performed:[/dim]")
                if is_stack:
                    console.print("[dim]1. Stop all services in stack[/dim]")
                    console.print("[dim]2. Remove all containers in stack[/dim]")
                    if build or build_type:
                        console.print("[dim]3. Build all images in stack[/dim]")
                    console.print("[dim]3/4. Start all services in stack[/dim]")
                else:
                    console.print("[dim]1. Stop service[/dim]")
                    console.print("[dim]2. Remove container[/dim]")
                    if build or build_type:
                        console.print("[dim]3. Build image[/dim]")
                    console.print("[dim]3/4. Start service[/dim]")
                return True

            if is_stack:
                console.print(
                    f"[yellow]Reinitializing stack {target} (all services)...[/yellow]"
                )
                return self._reinit_stack(
                    compose_file, build or build_type is not None, remove_orphans
                )
            else:
                console.print(f"[yellow]Reinitializing service {target}...[/yellow]")
                return self._reinit_service(
                    target,
                    compose_file,
                    build or build_type is not None,
                    remove_orphans,
                )

        except Exception as e:
            console.print(f"[red]Error reinitializing: {e}[/red]")
            return False

    def _reinit_stack(
        self, compose_file: Path, should_build: bool, remove_orphans: bool
    ) -> bool:
        """Reinitialize entire stack (all services)"""
        try:
            # Stop all services
            down_cmd = ["podman", "compose", "-f", compose_file.name, "down"]
            console.print(f"[cyan]exec: {' '.join(down_cmd)}[/cyan]")
            result = subprocess.run(
                down_cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            if result.returncode != 0:
                console.print(
                    f"[yellow]Warning stopping services: {result.stderr.strip() if result.stderr else 'Unknown error'}[/yellow]"
                )

            # Build if requested
            if should_build:
                build_cmd = [
                    "podman",
                    "compose",
                    "-f",
                    compose_file.name,
                    "build",
                    "--no-cache",
                ]
                console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")
                result = subprocess.run(
                    build_cmd,
                    cwd=self.manager.compose_dir,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    console.print("[red]Build failed for stack[/red]")
                    if result.stderr:
                        console.print(f"[red]{result.stderr.strip()}[/red]")
                    return False
                else:
                    console.print("[green]Build completed for stack[/green]")

            # Start all services
            up_cmd = ["podman", "compose", "-f", compose_file.name, "up", "-d"]
            if remove_orphans:
                up_cmd.append("--remove-orphans")

            console.print(f"[cyan]exec: {' '.join(up_cmd)}[/cyan]")
            result = subprocess.run(
                up_cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            if result.returncode == 0:
                console.print("[green]✓ Stack reinitialized successfully[/green]")
                return True
            else:
                console.print("[red]✗ Failed to start stack services[/red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr.strip()}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error reinitializing stack: {e}[/red]")
            return False

    def _reinit_service(
        self, target: str, compose_file: Path, should_build: bool, remove_orphans: bool
    ) -> bool:
        """Reinitialize single service"""
        try:
            # Stop
            stop_cmd = ["podman", "compose", "-f", compose_file.name, "stop", target]
            console.print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
            subprocess.run(
                stop_cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            # Remove using direct podman command (compose rm not supported by podman-compose)
            rm_cmd = ["podman", "rm", "-f", target]
            console.print(f"[cyan]exec: {' '.join(rm_cmd)}[/cyan]")
            subprocess.run(rm_cmd, capture_output=True, text=True)

            # Build if requested
            if should_build:
                build_cmd = [
                    "podman",
                    "compose",
                    "-f",
                    compose_file.name,
                    "build",
                    "--no-cache",
                    target,
                ]
                console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")
                result = subprocess.run(
                    build_cmd,
                    cwd=self.manager.compose_dir,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    console.print(f"[red]Build failed for {target}[/red]")
                    if result.stderr:
                        console.print(f"[red]{result.stderr.strip()}[/red]")
                    return False
                else:
                    console.print(f"[green]Build completed for {target}[/green]")

            # Start
            up_cmd = ["podman", "compose", "-f", compose_file.name, "up", "-d", target]
            if remove_orphans:
                up_cmd.append("--remove-orphans")

            console.print(f"[cyan]exec: {' '.join(up_cmd)}[/cyan]")
            result = subprocess.run(
                up_cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            if result.returncode == 0:
                console.print(f"[green]✓ {target} reinitialized[/green]")
                return True
            else:
                console.print(f"[red]✗ Failed to reinitialize {target}[/red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr.strip()}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error reinitializing service: {e}[/red]")
            return False

    def restart(
        self, target: str, build: bool = False, remove_orphans: bool = False
    ) -> bool:
        """Restart services"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return False

            # Build if requested
            if build:
                build_cmd = [
                    "podman",
                    "compose",
                    "-f",
                    project,
                    "build",
                    "--no-cache",
                    target,
                ]
                console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")
                build_result = subprocess.run(
                    build_cmd,
                    cwd=self.manager.compose_dir,
                    capture_output=True,
                    text=True,
                )
                if build_result.returncode != 0:
                    console.print(f"[red]Build failed for {target}[/red]")
                    if build_result.stderr:
                        console.print(f"[red]{build_result.stderr.strip()}[/red]")
                    return False
                else:
                    console.print(f"[green]Build completed for {target}[/green]")

            cmd = ["podman", "compose", "-f", project, "restart", target]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Restarted {target}[/green]")
                return True
            else:
                console.print(f"[red]Failed to restart {target}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error restarting: {e}[/red]")
            return False

    def stop(self, target: str, remove_orphans: bool = False) -> bool:
        """Stop services"""
        try:
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return False

            cmd = ["podman", "compose", "-f", project, "stop", target]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, cwd=self.manager.compose_dir)

            if result.returncode == 0:
                console.print(f"[green]Stopped {target}[/green]")
                return True
            else:
                console.print(f"[red]Failed to stop {target}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error stopping: {e}[/red]")
            return False

    def down(self, target: str) -> bool:
        """Stop all services in a project"""
        try:
            # Find the compose file for the target project
            projects = self.manager._parse_compose_files()

            # Check if target is a project name
            compose_file = None
            for project_name, project_info in projects.items():
                if target == project_name:
                    compose_file = project_info["file"]
                    break

            if not compose_file:
                # Try to find by service name
                service_project = self.manager._find_service_project(target)
                if service_project:
                    compose_file = self.manager.compose_dir / service_project
                else:
                    console.print(f"[red]Project or service '{target}' not found[/red]")
                    return False

            cmd = ["podman", "compose", "-f", compose_file.name, "down"]
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

            # Suppress verbose output from podman-compose
            result = subprocess.run(
                cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            if result.returncode == 0:
                # Parse output to show clean service list
                if result.stdout:
                    lines = result.stdout.split("\n")
                    stopped_services = []
                    for line in lines:
                        # Look for service names being stopped
                        if "podman stop" in line and "-t 10" in line:
                            service = line.split()[-1]
                            if service and service not in stopped_services:
                                stopped_services.append(service)

                    # Show clean output
                    for service in stopped_services:
                        console.print(f"[green]{service} stopped[/green]")

                console.print("[green]✓ All services stopped[/green]")
                return True
            else:
                console.print(f"[red]Failed to stop services in {target}[/red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr.strip()}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error stopping project: {e}[/red]")
            return False

    def show_service_status(self, target: str) -> None:
        """Show detailed service status (compatibility method)"""
        console.print(
            f"[yellow]Service status unavailable in compose mode for {target}[/yellow]"
        )
        console.print("[dim]Use 'pm list' to see available services[/dim]")

    def prune_containers(self) -> None:
        """Remove unused containers and images (compatibility method)"""
        self.prune()

    def show_system_df(self) -> None:
        """Show system disk usage (compatibility method)"""
        console.print("[yellow]System df not available in compose mode[/yellow]")
        console.print("[dim]Use 'pm system-df' command instead[/dim]")

    def start(self, target: str, build: bool = False) -> bool:
        """Start services in a stack or individual service"""
        try:
            # Find the compose file for the target stack
            stacks = self.manager._parse_compose_files()
            compose_file = None
            is_stack = False

            # Check if target is a stack name
            for stack_name, stack_info in stacks.items():
                if target == stack_name:
                    compose_file = stack_info["file"]
                    is_stack = True
                    break

            if not compose_file:
                # Try to find by service name
                service_stack = self.manager._find_service_project(target)
                if service_stack:
                    compose_file = self.manager.compose_dir / service_stack
                    is_stack = False
                else:
                    console.print(f"[red]Stack or service '{target}' not found[/red]")
                    return False

            # Build if requested
            if build:
                if is_stack:
                    build_cmd = [
                        "podman",
                        "compose",
                        "-f",
                        compose_file.name,
                        "build",
                        "--no-cache",
                    ]
                    console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")
                else:
                    build_cmd = [
                        "podman",
                        "compose",
                        "-f",
                        compose_file.name,
                        "build",
                        "--no-cache",
                        target,
                    ]
                    console.print(f"[cyan]exec: {' '.join(build_cmd)}[/cyan]")

                build_result = subprocess.run(
                    build_cmd,
                    cwd=self.manager.compose_dir,
                    capture_output=True,
                    text=True,
                )
                if build_result.returncode != 0:
                    console.print(f"[red]Build failed for {target}[/red]")
                    if build_result.stderr:
                        console.print(f"[red]{build_result.stderr.strip()}[/red]")
                    return False
                else:
                    console.print(f"[green]Build completed for {target}[/green]")

            # Start services
            if is_stack:
                cmd = ["podman", "compose", "-f", compose_file.name, "up", "-d"]
                console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
            else:
                cmd = ["podman", "compose", "-f", compose_file.name, "up", "-d", target]
                console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

            # Suppress verbose output from podman-compose
            result = subprocess.run(
                cmd, cwd=self.manager.compose_dir, capture_output=True, text=True
            )

            if result.returncode == 0:
                if is_stack:
                    console.print(
                        f"[green]✓ All services in {target} stack started[/green]"
                    )
                else:
                    console.print(f"[green]✓ {target} service started[/green]")
                return True
            else:
                if is_stack:
                    console.print(
                        f"[red]Failed to start services in stack {target}[/red]"
                    )
                else:
                    console.print(f"[red]Failed to start service {target}[/red]")
                if result.stderr:
                    console.print(f"[red]{result.stderr.strip()}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error starting project: {e}[/red]")
            return False

    def enable(self, target: str) -> bool:
        """Enable service (compatibility method)"""
        console.print(
            f"[yellow]Enable command not available in compose mode for {target}[/yellow]"
        )
        console.print("[cyan]Compose services don't have enable/disable concept[/cyan]")
        return False

    def disable(self, target: str) -> bool:
        """Disable service (compatibility method)"""
        console.print(
            f"[yellow]Disable command not available in compose mode for {target}[/yellow]"
        )
        console.print("[cyan]Compose services don't have enable/disable concept[/cyan]")
        return False

    def update_images_and_restart(self, target: str) -> bool:
        """Update images and restart (compatibility method)"""
        console.print(
            f"[yellow]Update command not available in compose mode for {target}[/yellow]"
        )
        console.print("[cyan]Use 'pm pull' and 'pm restart' commands instead[/cyan]")
        return False

    def check_auto_update_status(self) -> None:
        """Check auto-update status (compatibility method)"""
        console.print("[yellow]Auto-update not available in compose mode[/yellow]")
        console.print("[cyan]Auto-update is a quadlet/systemd feature[/cyan]")

    def reload_daemon(self) -> bool:
        """Reload daemon (compatibility method)"""
        console.print("[yellow]Reload daemon not available in compose mode[/yellow]")
        console.print("[cyan]This is a systemd-specific command[/cyan]")
        return False

    def rebuild(self, target: str) -> bool:
        """Rebuild container image and restart service (compatibility method)"""
        console.print(
            f"[yellow]Rebuilding {target} using compose build and restart...[/yellow]"
        )

        try:
            # Build with no-cache
            self.build(target, no_cache=True)

            # Restart the service
            return self.restart(target)

        except Exception as e:
            console.print(f"[red]Error rebuilding {target}: {e}[/red]")
            return False
