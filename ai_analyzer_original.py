"""Unified AI Analysis System for all PM commands"""

import subprocess
from datetime import datetime
from typing import Any, Dict, Optional

from ai_agents import ai_agent_manager
from config import console, verbose_print


class AIAnalyzer:
    """Unified AI analyzer that can handle different types of analysis with custom prompts"""

    def __init__(self, manager):
        self.manager = manager

    def _resolve_ai_agent_name(self, short_name):
        """Convert short AI agent names to full names"""
        if not short_name or short_name is True:
            return None

        # Mapping of short names to full agent names
        agent_mapping = {
            "qwen25": "vllm-qwen25",
            "glm46": "vllm-glm46",
            "claude": "claude-sonnet",
            "gpt4": "gpt-4",
            "gpt-4": "gpt-4",  # Allow both formats
            "claude-sonnet": "claude-sonnet",  # Allow full names too
            "vllm-qwen25": "vllm-qwen25",
            "vllm-glm46": "vllm-glm46",
        }

        return agent_mapping.get(short_name.lower(), short_name)

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
        resolved_agent = self._resolve_ai_agent_name(ai_agent)

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
                console.print(" ", end="")  # Add space for spinner

            # Get AI analysis using the agent system
            result = ai_agent_manager.analyze_with_agent(
                prompt, resolved_agent, verbose=verbose
            )

            # Clear the analyzing message if not in verbose mode
            if not verbose and result:
                console.print("\r" + "" * 30 + "\r", end="")  # Clear the line

            if result:
                # Store the original prompt and AI response for follow-up context
                self._original_prompt = prompt
                self._original_analysis_result = result
                # Display the results with appropriate formatting
                self._display_analysis_results(analysis_type, target, result, verbose)
                return result
            else:
                if verbose:
                    verbose_print("  [cyan]exec: No AI analysis result returned[/cyan]")

                # Show basic troubleshooting guide when AI analysis fails
                self._show_basic_troubleshooting_guide(
                    analysis_type, target, collected_data
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
        """Collect context data based on analysis type"""
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

        if analysis_type in ["logs", "reinit_failure"]:
            # Collect service logs
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Collecting comprehensive service diagnostics for {target}[/cyan]"
                )
            data.update(
                self._collect_service_logs(
                    target, context_data.get("lines", 50), verbose
                )
            )

        elif analysis_type == "status":
            # Collect service status information
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Collecting service status information for {target}[/cyan]"
                )
            data.update(self._collect_service_status(target, verbose))

        elif analysis_type == "build_failure":
            # Collect build logs and error information
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Collecting build failure information for {target}[/cyan]"
                )
            data.update(self._collect_build_logs(target, context_data))

        elif analysis_type == "performance":
            # Collect performance metrics
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Collecting performance metrics for {target}[/cyan]"
                )
            data.update(self._collect_performance_data(target, verbose))

        elif analysis_type == "security":
            # Collect security-related information
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Collecting security information for {target}[/cyan]"
                )
            data.update(self._collect_security_data(target))

        if verbose:
            verbose_print("  [cyan]exec: Diagnostic data collection completed[/cyan]")

        return data

    def _collect_service_logs(
        self, target: str, lines: int = 50, verbose: bool = False
    ) -> Dict[str, Any]:
        """Collect comprehensive service logs and diagnostic data for analysis"""
        try:
            # Resolve service name
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Resolving service name for target '{target}'[/cyan]"
                )
            # For compose mode, try to get the matched service name
            if hasattr(self.manager, "get_matched_service_name"):
                service_name = self.manager.get_matched_service_name(target)
            elif hasattr(self.manager, "_find_service_project"):
                # If it's a compose manager, we need to find the service differently
                project = self.manager._find_service_project(target)
                service_name = target if project else None
            else:
                # For quadlet mode, assume the target is the service name
                service_name = target
            if not service_name:
                return {"error": f"Service '{target}' not found"}

            if verbose:
                verbose_print(
                    f"  [cyan]exec: Resolved to service '{service_name}'[/cyan]"
                )

            data = {"service_name": service_name, "target": target}

            # 1. Get systemd unit logs (primary)
            logs_cmd = [
                "journalctl",
                "--user",
                "-u",
                service_name,
                "-n",
                str(lines),
                "--no-pager",
            ]

            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(logs_cmd)}[/cyan]")
            result = subprocess.run(
                logs_cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                data["systemd_logs"] = result.stdout.strip()
                data["log_lines_count"] = len(result.stdout.strip().split("\n"))
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Collected {data['log_lines_count']} lines of systemd logs[/cyan]"
                    )
            else:
                data["systemd_logs"] = "No systemd logs found"
                data["log_lines_count"] = 0
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: No systemd logs found (exit code: {result.returncode})[/cyan]"
                    )

            # 2. Get systemd unit status and details
            if verbose:
                verbose_print("  [cyan]exec: Collecting systemd unit details[/cyan]")
            data.update(self._collect_systemd_unit_details(service_name, verbose))

            # 3. Get container-specific information
            if verbose:
                verbose_print("  [cyan]exec: Collecting container details[/cyan]")
            data.update(self._collect_container_details(target, verbose))

            # 4. Get system resource information
            if verbose:
                verbose_print(
                    "  [cyan]exec: Collecting system resource information[/cyan]"
                )
            data.update(self._collect_system_resources(verbose))

            # 5. Get network and storage information
            if verbose:
                verbose_print(
                    "  [cyan]exec: Collecting network and storage information[/cyan]"
                )
            data.update(self._collect_network_storage_info(verbose))

            return data

        except Exception as e:
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Failed to collect comprehensive logs: {e}[/cyan]"
                )
            return {"error": f"Failed to collect comprehensive logs: {e}"}

    def _collect_service_status(
        self, target: str, verbose: bool = False
    ) -> Dict[str, Any]:
        """Collect service status information"""
        try:
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Resolving service name for target '{target}'[/cyan]"
                )
            # For compose mode, try to get the matched service name
            if hasattr(self.manager, "get_matched_service_name"):
                service_name = self.manager.get_matched_service_name(target)
            elif hasattr(self.manager, "_find_service_project"):
                # If it's a compose manager, we need to find the service differently
                project = self.manager._find_service_project(target)
                service_name = target if project else None
            else:
                # For quadlet mode, assume the target is the service name
                service_name = target
            if not service_name:
                return {"error": f"Service '{target}' not found"}

            if verbose:
                verbose_print(
                    f"  [cyan]exec: Resolved to service '{service_name}'[/cyan]"
                )

            # Get service status
            status_cmd = [
                "systemctl",
                "--user",
                "status",
                service_name,
                "--no-pager",
                "-l",
            ]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(status_cmd)}[/cyan]")
            result = subprocess.run(
                status_cmd, capture_output=True, text=True, timeout=15
            )

            if verbose:
                verbose_print(
                    f"  [cyan]exec: Service status collected (exit code: {result.returncode})[/cyan]"
                )

            return {
                "service_name": service_name,
                "status_output": result.stdout + (result.stderr or ""),
                "status_code": result.returncode,
            }

        except Exception as e:
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Service status collection failed: {e}[/cyan]"
                )
            return {"error": f"Failed to collect status: {e}"}

    def _collect_build_logs(
        self, target: str, context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Collect build logs and error information"""
        return {
            "build_error": context_data.get("build_error", ""),
            "build_command": context_data.get("build_command", ""),
            "build_output": context_data.get("build_output", ""),
        }

    def _collect_performance_data(
        self, target: str, verbose: bool = False
    ) -> Dict[str, Any]:
        """Collect performance metrics"""
        try:
            # Get container stats if available
            stats_cmd = ["podman", "stats", "--no-stream", "--format", "json"]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(stats_cmd)}[/cyan]")
            result = subprocess.run(
                stats_cmd, capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Performance data collected ({len(result.stdout)} chars)[/cyan]"
                    )
                return {"performance_data": result.stdout}
            else:
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: No performance data available (exit code: {result.returncode})[/cyan]"
                    )
                return {"performance_data": "No performance data available"}
        except Exception as e:
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Performance data collection failed: {e}[/cyan]"
                )
            return {"error": f"Failed to collect performance data: {e}"}

    def _collect_security_data(self, target: str) -> Dict[str, Any]:
        """Collect security-related information"""
        return {"security_context": "Security analysis requested", "target": target}

    def _collect_systemd_unit_details(
        self, service_name: str, verbose: bool = False
    ) -> Dict[str, Any]:
        """Collect detailed systemd unit information including .container files"""
        data = {}

        try:
            # Get unit status with detailed information
            status_cmd = [
                "systemctl",
                "--user",
                "status",
                service_name,
                "--no-pager",
                "-l",
            ]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(status_cmd)}[/cyan]")
            result = subprocess.run(
                status_cmd, capture_output=True, text=True, timeout=15
            )
            # Format the unit status to make long Podman commands more readable
            formatted_status = self._format_systemd_status_output(
                result.stdout + (result.stderr or "")
            )
            data["unit_status"] = formatted_status
            data["unit_status_code"] = result.returncode
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Unit status collected and formatted (exit code: {result.returncode})[/cyan]"
                )

            # Get unit file contents
            cat_cmd = ["systemctl", "--user", "cat", service_name]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(cat_cmd)}[/cyan]")
            result = subprocess.run(cat_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data["unit_file_content"] = result.stdout.strip()
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Unit file content collected ({len(result.stdout)} chars)[/cyan]"
                    )
            elif verbose:
                verbose_print(
                    f"  [cyan]exec: Unit file not accessible (exit code: {result.returncode})[/cyan]"
                )

            # Get unit properties for failure analysis
            show_cmd = [
                "systemctl",
                "--user",
                "show",
                service_name,
                "-p",
                "ExecMainStatus,ExecMainCode,Result,ActiveEnterTimestamp,InactiveEnterTimestamp,RestartCount",
            ]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(show_cmd)}[/cyan]")
            result = subprocess.run(
                show_cmd, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                data["unit_properties"] = result.stdout.strip()
                if verbose:
                    verbose_print("  [cyan]exec: Unit properties collected[/cyan]")
            elif verbose:
                verbose_print(
                    f"  [cyan]exec: Unit properties not available (exit code: {result.returncode})[/cyan]"
                )

            # Collect .container file for Quadlet services
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Looking for Quadlet .container file for {service_name}[/cyan]"
                )
            data.update(self._collect_quadlet_container_file(service_name, verbose))

        except Exception as e:
            data["systemd_error"] = f"Failed to collect systemd details: {e}"
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Systemd details collection failed: {e}[/cyan]"
                )

        return data

    def _collect_quadlet_container_file(
        self, service_name: str, verbose: bool = False
    ) -> Dict[str, Any]:
        """Collect Quadlet .container file contents"""
        data = {}

        try:
            from pathlib import Path

            # Common locations for Quadlet .container files
            quadlet_dirs = [
                Path.home() / ".config" / "containers" / "systemd",
                Path("/etc/containers/systemd"),
                Path("/usr/share/containers/systemd"),
            ]

            # Try different naming patterns for the container file
            container_file_patterns = [
                f"{service_name}.container",
                f"{service_name.replace('-', '_')}.container",
                f"{service_name.replace('_', '-')}.container",
            ]

            container_file_found = False

            for quadlet_dir in quadlet_dirs:
                if not quadlet_dir.exists():
                    continue

                if verbose:
                    verbose_print(f"  [cyan]exec: Searching in {quadlet_dir}[/cyan]")

                for pattern in container_file_patterns:
                    container_file = quadlet_dir / pattern
                    if container_file.exists():
                        if verbose:
                            verbose_print(
                                f"  [cyan]exec: Found .container file: {container_file}[/cyan]"
                            )

                        try:
                            with open(container_file, "r") as f:
                                data["quadlet_container_file"] = f.read().strip()
                                data["quadlet_container_file_path"] = str(
                                    container_file
                                )
                                container_file_found = True
                                if verbose:
                                    verbose_print(
                                        f"  [cyan]exec: .container file content collected ({len(data['quadlet_container_file'])} chars)[/cyan]"
                                    )
                                break
                        except Exception as e:
                            if verbose:
                                verbose_print(
                                    f"  [cyan]exec: Failed to read {container_file}: {e}[/cyan]"
                                )

                if container_file_found:
                    break

            if not container_file_found:
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: No .container file found for {service_name}[/cyan]"
                    )
                data["quadlet_container_file"] = "No .container file found"

                # Try to list available .container files for debugging
                for quadlet_dir in quadlet_dirs:
                    if quadlet_dir.exists():
                        try:
                            container_files = list(quadlet_dir.glob("*.container"))
                            if container_files:
                                available_files = [f.name for f in container_files]
                                data["available_container_files"] = (
                                    f"Available in {quadlet_dir}: {', '.join(available_files)}"
                                )
                                if verbose:
                                    verbose_print(
                                        f"  [cyan]exec: Available .container files in {quadlet_dir}: {', '.join(available_files)}[/cyan]"
                                    )
                                break
                        except Exception:
                            pass

        except Exception as e:
            data["quadlet_error"] = f"Failed to collect .container file: {e}"
            if verbose:
                verbose_print(
                    f"  [cyan]exec: .container file collection failed: {e}[/cyan]"
                )

        return data

    def _collect_container_details(
        self, target: str, verbose: bool = False
    ) -> Dict[str, Any]:
        """Collect Podman container-specific information"""
        data = {}

        try:
            # List all containers to find the target
            ps_cmd = [
                "podman",
                "ps",
                "-a",
                "--format",
                "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}",
            ]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(ps_cmd)}[/cyan]")
            result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data["container_list"] = result.stdout.strip()
                if verbose:
                    container_count = len(
                        [
                            line
                            for line in result.stdout.strip().split("\n")
                            if line.strip()
                        ]
                    )
                    verbose_print(
                        f"  [cyan]exec: Found {container_count} containers[/cyan]"
                    )

                # Find container name that matches target
                container_name = None
                for line in result.stdout.strip().split("\n"):
                    if line and target.lower() in line.lower():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            container_name = parts[1]  # Container name
                            if verbose:
                                verbose_print(
                                    f"  [cyan]exec: Found matching container: {container_name}[/cyan]"
                                )
                            break

                if container_name:
                    # Get container logs using container name
                    logs_cmd = [
                        "podman",
                        "logs",
                        container_name,
                        "--since",
                        "2h",
                        "--timestamps",
                        "--tail",
                        "100",
                    ]
                    if verbose:
                        verbose_print(f"  [cyan]exec: {' '.join(logs_cmd)}[/cyan]")
                    result = subprocess.run(
                        logs_cmd, capture_output=True, text=True, timeout=15
                    )
                    if result.returncode == 0:
                        data["container_logs"] = result.stdout.strip()
                        if verbose:
                            log_lines = (
                                len(result.stdout.strip().split("\n"))
                                if result.stdout.strip()
                                else 0
                            )
                            verbose_print(
                                f"  [cyan]exec: Container logs collected ({log_lines} lines)[/cyan]"
                            )
                    elif verbose:
                        verbose_print(
                            f"  [cyan]exec: No container logs (exit code: {result.returncode})[/cyan]"
                        )
                    # Get container inspection details
                    inspect_cmd = ["podman", "inspect", container_name]
                    if verbose:
                        verbose_print(f"  [cyan]exec: {' '.join(inspect_cmd)}[/cyan]")
                    result = subprocess.run(
                        inspect_cmd, capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        data["container_inspect"] = result.stdout.strip()
                        if verbose:
                            verbose_print(
                                f"  [cyan]exec: Container inspect data collected ({len(result.stdout)} chars)[/cyan]"
                            )
                    elif verbose:
                        verbose_print(
                            f"  [cyan]exec: Container inspect failed (exit code: {result.returncode})[/cyan]"
                        )
                else:
                    # Try direct service-based log collection if no container found by name matching
                    service_logs_cmd = [
                        "podman",
                        "logs",
                        target,
                        "--since",
                        "2h",
                        "--timestamps",
                        "--tail",
                        "100",
                    ]
                    if verbose:
                        verbose_print(
                            f"  [cyan]exec: Trying direct service logs: {' '.join(service_logs_cmd)}[/cyan]"
                        )
                    result = subprocess.run(
                        service_logs_cmd, capture_output=True, text=True, timeout=15
                    )
                    if result.returncode == 0:
                        data["container_logs"] = result.stdout.strip()
                        if verbose:
                            log_lines = (
                                len(result.stdout.strip().split("\n"))
                                if result.stdout.strip()
                                else 0
                            )
                            verbose_print(
                                f"  [cyan]exec: Direct service logs collected ({log_lines} lines)[/cyan]"
                            )
                    elif verbose:
                        verbose_print(
                            f"  [cyan]exec: Direct service logs failed (exit code: {result.returncode})[/cyan]"
                        )

                    if verbose and not data.get("container_logs"):
                        verbose_print(
                            f"  [cyan]exec: No container found matching '{target}'[/cyan]"
                        )
            elif verbose:
                verbose_print(
                    f"  [cyan]exec: No containers found (exit code: {result.returncode})[/cyan]"
                )

            # Check for pods
            pod_cmd = [
                "podman",
                "pod",
                "ps",
                "--format",
                "{{.ID}}\t{{.Name}}\t{{.Status}}",
            ]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(pod_cmd)}[/cyan]")
            result = subprocess.run(pod_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                data["pod_list"] = result.stdout.strip()
                if verbose:
                    pod_count = len(
                        [
                            line
                            for line in result.stdout.strip().split("\n")
                            if line.strip()
                        ]
                    )
                    verbose_print(f"  [cyan]exec: Found {pod_count} pods[/cyan]")
            elif verbose:
                verbose_print(
                    f"  [cyan]exec: No pods found (exit code: {result.returncode})[/cyan]"
                )

        except Exception as e:
            data["container_error"] = f"Failed to collect container details: {e}"
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Container details collection failed: {e}[/cyan]"
                )

        return data

    def _collect_system_resources(self, verbose: bool = False) -> Dict[str, Any]:
        """Collect system resource information"""
        data = {}

        try:
            # Disk space
            df_cmd = ["df", "-h", "/"]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(df_cmd)}[/cyan]")
            result = subprocess.run(df_cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                data["disk_space"] = result.stdout.strip()
                if verbose:
                    verbose_print(
                        "  [cyan]exec: Disk space information collected[/cyan]"
                    )
            elif verbose:
                verbose_print(
                    f"  [cyan]exec: Disk space check failed (exit code: {result.returncode})[/cyan]"
                )

            # Podman system info
            info_cmd = ["podman", "system", "info"]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(info_cmd)}[/cyan]")
            result = subprocess.run(
                info_cmd, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                data["podman_system_info"] = result.stdout.strip()
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Podman system info collected ({len(result.stdout)} chars)[/cyan]"
                    )
            elif verbose:
                verbose_print(
                    f"  [cyan]exec: Podman system info failed (exit code: {result.returncode})[/cyan]"
                )

            # Podman system df
            df_cmd = ["podman", "system", "df"]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(df_cmd)}[/cyan]")
            result = subprocess.run(df_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data["podman_disk_usage"] = result.stdout.strip()
                if verbose:
                    verbose_print("  [cyan]exec: Podman disk usage collected[/cyan]")
            elif verbose:
                verbose_print(
                    f"  [cyan]exec: Podman disk usage failed (exit code: {result.returncode})[/cyan]"
                )

        except Exception as e:
            data["system_resources_error"] = f"Failed to collect system resources: {e}"
            if verbose:
                verbose_print(
                    f"  [cyan]exec: System resources collection failed: {e}[/cyan]"
                )

        return data

    def _collect_network_storage_info(self, verbose: bool = False) -> Dict[str, Any]:
        """Collect network and storage information"""
        data = {}

        try:
            # Podman networks
            net_cmd = ["podman", "network", "ls"]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(net_cmd)}[/cyan]")
            result = subprocess.run(net_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data["podman_networks"] = result.stdout.strip()
                if verbose:
                    network_count = (
                        len(
                            [
                                line
                                for line in result.stdout.strip().split("\n")
                                if line.strip()
                            ]
                        )
                        - 1
                    )  # -1 for header
                    verbose_print(
                        f"  [cyan]exec: Found {max(0, network_count)} Podman networks[/cyan]"
                    )
            elif verbose:
                verbose_print(
                    f"  [cyan]exec: Podman networks failed (exit code: {result.returncode})[/cyan]"
                )

            # Podman volumes
            vol_cmd = ["podman", "volume", "ls"]
            if verbose:
                verbose_print(f"  [cyan]exec: {' '.join(vol_cmd)}[/cyan]")
            result = subprocess.run(vol_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data["podman_volumes"] = result.stdout.strip()
                if verbose:
                    volume_count = (
                        len(
                            [
                                line
                                for line in result.stdout.strip().split("\n")
                                if line.strip()
                            ]
                        )
                        - 1
                    )  # -1 for header
                    verbose_print(
                        f"  [cyan]exec: Found {max(0, volume_count)} Podman volumes[/cyan]"
                    )
            elif verbose:
                verbose_print(
                    f"  [cyan]exec: Podman volumes failed (exit code: {result.returncode})[/cyan]"
                )

            # Check for port conflicts (common ports)
            common_ports = ["8000", "8001", "8002", "8003", "8080", "3000", "5000"]
            port_info = []
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Checking port usage for common ports: {', '.join(common_ports)}[/cyan]"
                )

            for port in common_ports:
                ss_cmd = ["ss", "-tulpen", "-H"]
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: {' '.join(ss_cmd)} | grep :{port}[/cyan]"
                    )
                result = subprocess.run(
                    ss_cmd, capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if f":{port}" in line:
                            port_info.append(f"Port {port}: {line.strip()}")
                            if verbose:
                                verbose_print(
                                    f"  [cyan]exec: Port {port} is in use[/cyan]"
                                )

            if port_info:
                data["port_usage"] = "\n".join(port_info)
                if verbose:
                    verbose_print(
                        f"  [cyan]exec: Found {len(port_info)} ports in use[/cyan]"
                    )
            elif verbose:
                verbose_print("  [cyan]exec: No common ports in use[/cyan]")

        except Exception as e:
            data["network_storage_error"] = (
                f"Failed to collect network/storage info: {e}"
            )
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Network/storage info collection failed: {e}[/cyan]"
                )

        return data

    def _format_systemd_status_output(self, status_output: str) -> str:
        """Format systemd status output to make long Podman commands more readable"""
        import re

        lines = status_output.split("\n")
        formatted_lines = []

        for line in lines:
            # Check if this line contains a long Process: ExecStart= command
            if "Process:" in line and "ExecStart=" in line and len(line) > 120:
                # Extract the parts
                process_match = re.match(
                    r"^(\s*Process:\s+\d+\s+ExecStart=)(.+)(\s+\(code=.+\))$", line
                )
                if process_match:
                    prefix = process_match.group(1)
                    command = process_match.group(2)
                    suffix = process_match.group(3)

                    # Format the command part
                    formatted_command = self._format_podman_command_for_status(command)

                    # Reconstruct the line with formatting
                    formatted_lines.append(prefix)
                    formatted_lines.extend(formatted_command)
                    formatted_lines.append(f"    {suffix}")
                else:
                    formatted_lines.append(line)
            # Check if this line contains a long CGroup podman command
            elif (
                ("└─" in line or "├─" in line)
                and "/usr/local/bin/podman" in line
                and len(line) > 120
            ):
                # Extract the parts for CGroup lines
                cgroup_match = re.match(r"^(\s*[└├]─\d+\s+)(.+)$", line)
                if cgroup_match:
                    prefix = cgroup_match.group(1)
                    command = cgroup_match.group(2)

                    # Format the command part
                    formatted_command = self._format_podman_command_for_status(command)

                    # Reconstruct the line with formatting
                    formatted_lines.append(
                        prefix + formatted_command[0].strip()
                        if formatted_command
                        else line
                    )
                    # Add continuation lines with proper indentation
                    for continuation_line in formatted_command[1:]:
                        formatted_lines.append(
                            " " * len(prefix) + continuation_line.strip()
                        )
                else:
                    formatted_lines.append(line)
            else:
                formatted_lines.append(line)

        return "\n".join(formatted_lines)

    def _format_podman_command_for_status(self, command: str) -> list:
        """Format a long podman command for better readability in status output"""
        import shlex

        try:
            # Try to parse the command properly
            parts = shlex.split(command)
        except ValueError:
            # If shlex fails, fall back to simple split
            parts = command.split()

        formatted_lines = []
        current_line = "    "  # Start with indentation

        for i, part in enumerate(parts):
            # Add line breaks before certain flags for readability
            if part.startswith("--") and i > 0:
                if len(current_line) > 80:  # If line is getting long
                    formatted_lines.append(current_line.rstrip())
                    current_line = "      "  # More indentation for continuation

            current_line += part + " "

            # Special handling for flags that take values - keep them together
            if part in [
                "--name",
                "--cidfile",
                "--network",
                "--publish",
                "--env",
                "--label",
                "--health-cmd",
                "--health-interval",
                "--health-retries",
                "--health-start-period",
                "--health-timeout",
            ]:
                # Keep the next argument on the same line if it exists
                continue

        # Add the final line
        if current_line.strip():
            formatted_lines.append(current_line.rstrip())

        return formatted_lines

    def _generate_prompt(
        self, analysis_type: str, target: str, data: Dict[str, Any]
    ) -> str:
        """Generate appropriate prompt based on analysis type"""
        base_context = f"""You are an expert system administrator and DevOps engineer.

Target: {target}
Analysis Type: {analysis_type}
Timestamp: {data.get('timestamp', 'Unknown')}
"""

        if analysis_type == "logs":
            return self._generate_logs_prompt(base_context, data)
        elif analysis_type == "reinit_failure":
            return self._generate_reinit_failure_prompt(base_context, data)
        elif analysis_type == "status":
            return self._generate_status_prompt(base_context, data)
        elif analysis_type == "build_failure":
            return self._generate_build_failure_prompt(base_context, data)
        elif analysis_type == "performance":
            return self._generate_performance_prompt(base_context, data)
        elif analysis_type == "security":
            return self._generate_security_prompt(base_context, data)
        else:
            return self._generate_generic_prompt(base_context, data)

    def _generate_logs_prompt(self, base_context: str, data: Dict[str, Any]) -> str:
        """Generate comprehensive prompt for Podman Quadlet log analysis"""
        prompt_parts = [base_context]

        prompt_parts.append(
            """
Analyze the following Podman Quadlet service diagnostics and provide:

1. **Root Cause Analysis**: Identify the primary issues causing errors or warnings
2. **Recommended Solutions**: Specific, actionable steps to resolve the problems
3. **Quadlet-Specific Issues**: Check for common quadlet configuration problems
4. **System Resource Issues**: Identify any resource constraints or conflicts

IMPORTANT: This is a Podman Quadlet managed by systemd. Consider quadlet-specific issues like:
- Container image pull failures
- Volume/network configuration errors
- Port conflicts
- Resource constraints (disk space, memory)
- SELinux issues
- Systemd unit file problems
"""
        )

        # Add service information
        prompt_parts.append(
            f"""
Service: {data.get('service_name', 'Unknown')}
Target: {data.get('target', 'Unknown')}
Log Lines Analyzed: {data.get('log_lines_count', 'Unknown')}
"""
        )

        # 1. Systemd logs (primary)
        if data.get("systemd_logs"):
            prompt_parts.append(
                f"""
=== SYSTEMD SERVICE LOGS ===
{data['systemd_logs']}
=== END SYSTEMD LOGS ===
"""
            )

        # 2. Unit status and properties
        if data.get("unit_status"):
            prompt_parts.append(
                f"""
=== SYSTEMD UNIT STATUS ===
{data['unit_status']}
=== END UNIT STATUS ===
"""
            )

        if data.get("unit_properties"):
            prompt_parts.append(
                f"""
=== UNIT PROPERTIES (Failure Analysis) ===
{data['unit_properties']}
=== END UNIT PROPERTIES ===
"""
            )

        # 3. Unit file content
        if data.get("unit_file_content"):
            prompt_parts.append(
                f"""
=== SYSTEMD UNIT FILE CONTENT ===
{data['unit_file_content']}
=== END UNIT FILE ===
"""
            )

        # 4. Quadlet .container file content (crucial for Quadlet troubleshooting)
        if (
            data.get("quadlet_container_file")
            and data["quadlet_container_file"] != "No .container file found"
        ):
            # Format the .container file content with proper indentation for readability
            container_content = data["quadlet_container_file"]
            formatted_content = "\n".join(
                f"  {line}" if line.strip() else ""
                for line in container_content.split("\n")
            )
            prompt_parts.append(
                f"""
=== QUADLET .CONTAINER FILE ===
File: {data.get('quadlet_container_file_path', 'Unknown path')}
{formatted_content}
=== END .CONTAINER FILE ===
"""
            )
        elif data.get("quadlet_container_file") == "No .container file found":
            prompt_parts.append(
                f"""
=== QUADLET .CONTAINER FILE ===
No .container file found for {data.get('service_name', 'service')}
{data.get('available_container_files', 'No available files listed')}
=== END .CONTAINER FILE ===
"""
            )

        # 5. Container information
        if data.get("container_list"):
            prompt_parts.append(
                f"""
=== CONTAINER LIST ===
{data['container_list']}
=== END CONTAINER LIST ===
"""
            )

        if data.get("container_logs"):
            prompt_parts.append(
                f"""
=== CONTAINER LOGS (Last 2 hours) ===
{data['container_logs']}
=== END CONTAINER LOGS ===
"""
            )

        if data.get("container_inspect"):
            # Truncate inspect output to avoid overwhelming the AI
            inspect_data = data["container_inspect"]
            if len(inspect_data) > 3000:
                inspect_data = inspect_data[:3000] + "\n... [truncated for brevity]"
            prompt_parts.append(
                f"""
=== CONTAINER INSPECTION (Key Details) ===
{inspect_data}
=== END CONTAINER INSPECTION ===
"""
            )

        # 6. System resources
        if data.get("disk_space"):
            prompt_parts.append(
                f"""
=== DISK SPACE ===
{data['disk_space']}
=== END DISK SPACE ===
"""
            )

        if data.get("podman_disk_usage"):
            prompt_parts.append(
                f"""
=== PODMAN DISK USAGE ===
{data['podman_disk_usage']}
=== END PODMAN DISK USAGE ===
"""
            )

        # 7. Network and port information
        if data.get("port_usage"):
            prompt_parts.append(
                f"""
=== PORT USAGE (Potential Conflicts) ===
{data['port_usage']}
=== END PORT USAGE ===
"""
            )

        if data.get("podman_networks"):
            prompt_parts.append(
                f"""
=== PODMAN NETWORKS ===
{data['podman_networks']}
=== END NETWORKS ===
"""
            )

        # 8. Error summaries
        errors = []
        for key in [
            "systemd_error",
            "container_error",
            "system_resources_error",
            "network_storage_error",
        ]:
            if data.get(key):
                errors.append(f"{key}: {data[key]}")

        # Add quadlet-specific errors
        if data.get("quadlet_error"):
            errors.append(f"quadlet_error: {data['quadlet_error']}")

        if errors:
            prompt_parts.append(
                f"""
=== DIAGNOSTIC COLLECTION ERRORS ===
{chr(10).join(errors)}
=== END ERRORS ===
"""
            )

        prompt_parts.append(
            """
Provide a structured analysis focusing on:
1. **Immediate Issues**: What's preventing the service from working right now?
2. **Root Causes**: Why are these issues occurring?
3. **Step-by-Step Fix**: Specific commands to resolve the problems
4. **Prevention**: How to avoid these issues in the future
5. **Monitoring**: What to watch for ongoing health

Use podman commands (not docker) in all recommendations. Consider quadlet-specific troubleshooting steps."""
        )

        return "\n".join(prompt_parts)

    def _generate_reinit_failure_prompt(
        self, base_context: str, data: Dict[str, Any]
    ) -> str:
        """Generate comprehensive prompt for reinit failure analysis"""
        prompt_parts = [base_context]

        prompt_parts.append(
            """
Analyze the following Podman Quadlet service restart failure and provide:

1. **Root Cause Analysis**: Identify the primary issues causing the restart failure
2. **Recommended Solutions**: Specific, actionable steps to resolve the problems
3. **Quadlet-Specific Issues**: Check for common quadlet configuration problems
4. **System Resource Issues**: Identify any resource constraints or conflicts

IMPORTANT: This is a Podman Quadlet managed by systemd. Consider quadlet-specific issues like:
- Container image pull failures
- Volume/network configuration errors
- Port conflicts
- Resource constraints (disk space, memory)
- SELinux issues
- Systemd unit file problems

Provide a concise analysis with:
- **Immediate Issues**: What's preventing the service from restarting?
- **Root Causes**: Why are these issues occurring?
- **Step-by-Step Fix**: Specific commands to resolve the problems
"""
        )

        # Add service information
        prompt_parts.append(
            f"""
Service: {data.get('service_name', 'Unknown')}
Target: {data.get('target', 'Unknown')}
Operation: {data.get('operation', 'restart')}
Error: {data.get('restart_error', 'Service failed to restart')}
"""
        )

        # 1. Systemd service logs (primary)
        if data.get("systemd_logs"):
            prompt_parts.append(
                f"""
=== SYSTEMD SERVICE LOGS ===
{data['systemd_logs']}
=== END SYSTEMD LOGS ===
"""
            )

        # 2. Unit status and properties
        if data.get("unit_status"):
            prompt_parts.append(
                f"""
=== SYSTEMD UNIT STATUS ===
{data['unit_status']}
=== END UNIT STATUS ===
"""
            )

        if data.get("unit_properties"):
            prompt_parts.append(
                f"""
=== UNIT PROPERTIES (Failure Analysis) ===
{data['unit_properties']}
=== END UNIT PROPERTIES ===
"""
            )

        # 3. System resources
        if data.get("disk_space"):
            prompt_parts.append(
                f"""
=== DISK SPACE ===
{data['disk_space']}
=== END DISK SPACE ===
"""
            )

        # 4. Port conflicts
        if data.get("port_usage"):
            prompt_parts.append(
                f"""
=== PORT CONFLICTS ===
{data['port_usage']}
=== END PORT CONFLICTS ===
"""
            )

        # 5. Container information if available
        if data.get("container_logs"):
            prompt_parts.append(
                f"""
=== CONTAINER LOGS (Recent) ===
{data['container_logs']}
=== END CONTAINER LOGS ===
"""
            )

        # 6. Quadlet .container file content if available
        if (
            data.get("quadlet_container_file")
            and data["quadlet_container_file"] != "No .container file found"
        ):
            container_content = data["quadlet_container_file"]
            formatted_content = "\n".join(
                f"  {line}" if line.strip() else ""
                for line in container_content.split("\n")
            )
            prompt_parts.append(
                f"""
=== QUADLET .CONTAINER FILE ===
File: {data.get('quadlet_container_file_path', 'Unknown path')}
{formatted_content}
=== END .CONTAINER FILE ===
"""
            )

        # 7. Error summaries
        errors = []
        for key in [
            "systemd_error",
            "container_error",
            "system_resources_error",
            "network_storage_error",
        ]:
            if data.get(key):
                errors.append(f"{key}: {data[key]}")

        if data.get("quadlet_error"):
            errors.append(f"quadlet_error: {data['quadlet_error']}")

        if errors:
            prompt_parts.append(
                f"""
=== DIAGNOSTIC COLLECTION ERRORS ===
{chr(10).join(errors)}
=== END ERRORS ===
"""
            )

        prompt_parts.append(
            """
Use podman commands (not docker) in all recommendations. Focus on the most critical issues first and provide specific, actionable solutions.
"""
        )

        return "\n".join(prompt_parts)

    def _generate_status_prompt(self, base_context: str, data: Dict[str, Any]) -> str:
        """Generate prompt for status analysis"""
        return f"""{base_context}
Analyze the following service status and provide insights:

Service: {data.get('service_name', 'Unknown')}

=== STATUS OUTPUT ===
{data.get('status_output', 'No status available')}
=== END STATUS ===

Provide:
1. **Current State**: What is the current state of the service?
2. **Health Assessment**: Is the service healthy or are there issues?
3. **Recommendations**: Any actions needed to improve service health?
4. **Monitoring**: What should be monitored going forward?"""

    def _generate_build_failure_prompt(
        self, base_context: str, data: Dict[str, Any]
    ) -> str:
        """Generate focused prompt for container build failure analysis"""
        prompt_parts = []

        prompt_parts.append(
            """You are an expert DevOps engineer. Analyze this container build failure and provide a concise solution.

Focus on:
- Dockerfile syntax and structure issues
- Base image problems
- Package installation failures
- File operations and permissions
- Common container build patterns

Provide specific, actionable fixes using podman commands."""
        )

        # Add build error - this is the most important part
        if data.get("build_error"):
            prompt_parts.append(
                f"""
=== BUILD ERROR ===
{data['build_error']}
=== END ERROR ==="""
            )

        # Add build output if available and contains useful info
        if data.get("build_output"):
            build_output = data["build_output"].strip()
            if (
                build_output and len(build_output) > 10
            ):  # Only if there's meaningful output
                # Keep it concise - just the last part with the actual error
                if len(build_output) > 2000:
                    build_output = "...\n" + build_output[-2000:]

                prompt_parts.append(
                    f"""
=== BUILD OUTPUT ===
{build_output}
=== END OUTPUT ==="""
                )

        # Add Dockerfile content - this is crucial for analysis
        dockerfile_path = data.get("dockerfile_path")
        if dockerfile_path:
            try:
                from pathlib import Path

                dockerfile = Path(dockerfile_path)
                if dockerfile.exists():
                    with open(dockerfile, "r") as f:
                        dockerfile_content = f.read().strip()
                        if dockerfile_content:
                            prompt_parts.append(
                                f"""
=== DOCKERFILE ===
{dockerfile_content}
=== END DOCKERFILE ==="""
                            )
            except Exception:
                pass  # Skip if can't read Dockerfile

        prompt_parts.append(
            """
Provide:
1. **Root Cause**: What caused the build to fail?
2. **Fix**: Specific commands or Dockerfile changes needed
3. **Explanation**: Brief explanation of why this fixes the issue

Be concise and actionable. Use podman commands, not docker."""
        )

        return "\n\n".join(prompt_parts)

    def _generate_performance_prompt(
        self, base_context: str, data: Dict[str, Any]
    ) -> str:
        """Generate prompt for performance analysis"""
        return f"""{base_context}
Analyze the following performance data and provide optimization recommendations:

=== PERFORMANCE DATA ===
{data.get('performance_data', 'No performance data available')}
=== END DATA ===

Provide:
1. **Performance Assessment**: Current performance status
2. **Bottlenecks**: Identify any performance bottlenecks
3. **Optimization**: Specific recommendations to improve performance
4. **Resource Usage**: Analysis of CPU, memory, and I/O usage"""

    def _generate_security_prompt(self, base_context: str, data: Dict[str, Any]) -> str:
        """Generate prompt for security analysis"""
        return f"""{base_context}
Perform a security analysis of the service configuration and provide recommendations:

Provide:
1. **Security Assessment**: Current security posture
2. **Vulnerabilities**: Potential security issues or vulnerabilities
3. **Hardening**: Specific steps to improve security
4. **Best Practices**: Security best practices for this type of service
5. **Monitoring**: Security monitoring recommendations"""

    def _generate_generic_prompt(self, base_context: str, data: Dict[str, Any]) -> str:
        """Generate generic prompt for unknown analysis types"""
        return f"""{base_context}
Provide analysis and recommendations for the following:

=== CONTEXT DATA ===
{str(data)}
=== END DATA ===

Provide relevant insights and actionable recommendations based on the available information."""

    def _display_analysis_results(
        self, analysis_type: str, target: str, result: str, verbose: bool = False
    ) -> None:
        """Display AI analysis results with appropriate formatting"""
        # Create a title based on analysis type
        titles = {
            "logs": "AI Log Analysis",
            "reinit_failure": "AI Reinit Failure Analysis",
            "status": "AI Status Analysis",
            "build_failure": "AI Build Failure Analysis",
            "performance": "AI Performance Analysis",
            "security": "AI Security Analysis",
        }

        title = titles.get(analysis_type, "AI Analysis")
        console.print(f"\n[bold green]{title} for {target}[/bold green]")
        console.print()  # Add newline after header

        # Use the same markdown rendering as the original system
        self._render_markdown_manually(result)

        # Show follow-up commands
        self._show_analysis_menu(analysis_type, target, verbose)

    def _render_markdown_manually(self, content: str) -> None:
        """Manually render markdown content using Rich formatting"""
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
                console.print(f"[bold cyan]{header_text}[/bold cyan]")
                previous_was_header = True
                continue
            else:
                previous_was_header = False

            # Handle bold text (**text**)
            line = re.sub(r"\*\*([^*]+)\*\*", r"[bold]\1[/bold]", line)

            # Handle inline code (`code`)
            def replace_code(match):
                code_content = match.group(1)
                if len(code_content) < 100 and "\n" not in code_content:
                    return f"[cyan]{code_content}[/cyan]"
                else:
                    return code_content

            line = re.sub(r"`([^`]+)`", replace_code, line)

            # Handle code blocks (```)
            if line.startswith("```"):
                if line == "```text" or (line == "```" and not in_code_block):
                    continue
                elif line == "```" and in_code_block:
                    in_code_block = False
                    continue
                elif any(
                    lang in line
                    for lang in ["bash", "ini", "python", "json", "yaml", "sh"]
                ):
                    in_code_block = True
                    continue
                else:
                    continue

            # Handle content inside code blocks
            if in_code_block:
                console.print(f"    [cyan]{line}[/cyan]")
                continue

            # Handle numbered lists (1. item)
            if re.match(r"^\d+\.\s", line):
                wrapped_lines = textwrap.fill(
                    line, width=116, initial_indent="    ", subsequent_indent="       "
                )
                console.print(f"[white]{wrapped_lines}[/white]")
                continue

            # Handle bullet points (- item)
            if line.startswith("- "):
                wrapped_lines = textwrap.fill(
                    line,
                    width=112,
                    initial_indent="        ",
                    subsequent_indent="          ",
                )
                console.print(f"[white]{wrapped_lines}[/white]")
                continue

            # Handle long command lines (ExecStart, podman run, etc.)
            if self._is_long_command_line(line):
                formatted_command = self._format_long_command_line(line)
                for cmd_line in formatted_command:
                    console.print(f"    [cyan]{cmd_line}[/cyan]")
                continue

            # Regular text - wrap at 120 characters with indentation
            if len(line) > 116:
                wrapped_lines = textwrap.fill(
                    line, width=116, initial_indent="    ", subsequent_indent="    "
                )
                console.print(wrapped_lines)
            else:
                console.print(f"    {line}")

    def _show_analysis_menu(
        self, analysis_type: str, target: str, verbose: bool = False
    ) -> None:
        """Show recommended actions after AI analysis"""
        console.print("\n  [bold green]Recommended actions:[/bold green]")

        # Common actions for all analysis types
        console.print(
            f"[green]   View detailed logs:[/green] [white]pm logs {target}[/white]"
        )

        if analysis_type == "reinit_failure":
            console.print(
                f"[green]         Retry reinit:[/green] [white]pm reinit {target} -v[/white]"
            )
            console.print(
                f"[green]    Reset failed state:[/green] [white]pm reset-failed {target}[/white]"
            )
        elif analysis_type == "build_failure":
            console.print(
                f"[green]        Retry build:[/green] [white]pm build {target}[/white]"
            )
            console.print(
                f"[green]    Clean and rebuild:[/green] [white]pm reinit {target} -b[/white]"
            )
        elif analysis_type == "status":
            console.print(
                f"[green]    Restart service:[/green] [white]pm restart {target}[/white]"
            )
            console.print(
                f"[green]   Monitor live logs:[/green] [white]pm logs {target} --f[/white]"
            )

        # Universal actions
        console.print(
            f"[green]   Diagnose the issue:[/green] [white]pm diagnose {target}[/white]"
        )
        console.print(
            f"[green]   Re-run AI analysis:[/green] [white]pm logs {target}[/white]"
        )
        console.print()

        # Start interactive analysis session
        self._start_interactive_analysis(analysis_type, target, verbose)

    def _start_interactive_analysis(
        self, analysis_type: str, target: str, verbose: bool = False
    ) -> None:
        """Start interactive AI analysis session with follow-up questions"""
        console.print("\n[bold green]Interactive AI Analysis[/bold green]")
        console.print(
            "[yellow]Ask follow-up questions about the analysis. Press Enter with empty input to exit.[/yellow]"
        )

        while True:
            try:
                # Show interactive prompt
                console.print("\n[bold yellow]==>[/bold yellow] ", end="")
                user_input = input().strip()

                # Exit if empty input
                if not user_input:
                    break

                # Process the follow-up question
                self._process_followup_question(
                    analysis_type, target, user_input, verbose
                )

            except KeyboardInterrupt:
                console.print("\n[dim]Interactive analysis interrupted.[/dim]")
                break
            except EOFError:
                console.print("\n[dim]Interactive analysis ended.[/dim]")
                break

        # Show completion message
        console.print(f"\n[green]AI analysis for {target} completed[/green]")
        console.print(
            f"    [green]For further analysis try:[/green] [white]pm logs {target} -ai[/white]"
        )
        console.print()

    def _process_followup_question(
        self, analysis_type: str, target: str, question: str, verbose: bool = False
    ) -> None:
        """Process a follow-up question and generate AI response"""
        console.print(f"\n[bold green]Follow-up Analysis for {target}[/bold green]")
        console.print()

        # Create a focused prompt for the follow-up question
        followup_prompt = self._generate_followup_prompt(
            analysis_type, target, question
        )

        # Display the follow-up prompt in verbose mode
        if verbose:
            console.print("\n[bold cyan]Follow-up AI Analysis Prompt:[/bold cyan]")
            console.print("[cyan]" + "─" * 80 + "[/cyan]")
            for line in followup_prompt.split("\n"):
                console.print(f"[cyan]{line}[/cyan]")
            console.print("[cyan]" + "─" * 80 + "[/cyan]")
            console.print()

        # Show analyzing spinner before AI agent call for follow-up
        if not verbose:
            if analysis_type == "build_failure":
                console.print("[green]Analyzing build failure...[/green]", end="")
            else:
                console.print("[green]Analyzing error data...[/green]", end="")
            console.print(" ", end="")  # Add space for spinner

        # Get AI analysis using the same agent system
        result = ai_agent_manager.analyze_with_agent(followup_prompt)

        # Clear the analyzing message if not in verbose mode
        if not verbose and result:
            console.print("\r" + "" * 30 + "\r", end="")  # Clear the line

        if result:
            # Display the follow-up analysis results
            self._render_markdown_manually(result)
        else:
            console.print(
                "[yellow]Unable to generate follow-up analysis. Please try again.[/yellow]"
            )

    def _generate_followup_prompt(
        self, analysis_type: str, target: str, question: str
    ) -> str:
        """Generate a focused prompt for follow-up questions"""
        # Create summarized context from original prompt and analysis result
        context_summary = ""
        if hasattr(self, "_original_prompt") and hasattr(
            self, "_original_analysis_result"
        ):
            # Extract key information from original prompt for summary
            analysis_result = self._original_analysis_result

            # Create a concise summary of the original analysis
            context_summary = f"""\n\n=== PREVIOUS ANALYSIS SUMMARY ===
Original Issue: {analysis_type} analysis for service '{target}'

Key Diagnostic Data:
- Service logs and status information were analyzed
- System resources, container details, and network configuration were examined
- Quadlet configuration and systemd unit details were reviewed

Previous AI Analysis Report:
{analysis_result}
=== END PREVIOUS ANALYSIS ===\n\n"""

        return f"""You are an expert system administrator and DevOps engineer.

Context: You previously completed a comprehensive {analysis_type} analysis for service '{target}' with full diagnostic data collection.{context_summary}
Follow-up Question: {question}

Provide a focused, practical response to this specific question based on the previous analysis above. Keep your answer:
1. **Direct**: Address the question specifically
2. **Actionable**: Include specific commands or steps when relevant
3. **Concise**: Be brief but comprehensive
4. **Practical**: Focus on real-world solutions
5. **Contextual**: Reference relevant information from the previous analysis when helpful

Use podman commands (not docker) in all recommendations."""

    def _is_long_command_line(self, line: str) -> bool:
        """Check if a line contains a long command that should be formatted"""
        # Check for common command patterns that need formatting
        command_indicators = [
            "ExecStart=",
            "podman run",
            "/usr/local/bin/podman",
            "--name",
            "--cidfile",
            "--replace",
            "--rm",
            "--network",
            "--publish",
            "--env",
            "--label",
            "--health-cmd",
        ]

        # Only format if line is long and contains command indicators
        if len(line) > 100:
            return any(indicator in line for indicator in command_indicators)
        return False

    def _format_long_command_line(self, line: str) -> list:
        """Format a long command line for better readability"""
        import shlex

        # Handle ExecStart= prefix
        exec_start_prefix = ""
        command_part = line

        if "ExecStart=" in line:
            parts = line.split("ExecStart=", 1)
            if len(parts) == 2:
                exec_start_prefix = parts[0] + "ExecStart="
                command_part = parts[1]

        # Handle numbered list prefix (like "2. Modify the ExecStart line...")
        list_prefix = ""
        if line.strip().startswith(
            ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")
        ):
            # Extract the list number and description before the command
            import re

            match = re.match(r"^(\d+\.\s+[^:]+:\s*)", line.strip())
            if match:
                list_prefix = match.group(1)
                command_part = line.strip()[len(list_prefix) :].strip()
                if "ExecStart=" in command_part:
                    parts = command_part.split("ExecStart=", 1)
                    if len(parts) == 2:
                        exec_start_prefix = list_prefix + parts[0] + "ExecStart="
                        command_part = parts[1]
                    else:
                        exec_start_prefix = list_prefix
                else:
                    exec_start_prefix = list_prefix

        try:
            # Try to parse the command properly
            parts = shlex.split(command_part.strip())
        except ValueError:
            # If shlex fails, fall back to simple split
            parts = command_part.strip().split()

        if not parts:
            return [line]

        formatted_lines = []

        # Add the prefix line if it exists
        if exec_start_prefix:
            formatted_lines.append(exec_start_prefix)

        # Format the command with each --parameter on a separate line
        base_indent = "        "  # Base indentation for continuation lines
        current_line = "    "  # First line indentation
        if exec_start_prefix:
            current_line = base_indent  # Extra indentation for continuation

        i = 0
        while i < len(parts):
            part = parts[i]

            # For --parameters, put each on its own line
            if part.startswith("--") and i > 0:
                # Finish current line and start new one
                if current_line.strip():
                    formatted_lines.append(current_line.rstrip())
                current_line = base_indent + part

                # Check if this parameter takes a value (next part doesn't start with --)
                if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                    current_line += " " + parts[i + 1]
                    i += 1  # Skip the value part since we already added it

                current_line += " \\"
            else:
                # For non-parameter parts, add to current line
                current_line += part + " "

            i += 1

        # Add the final line (remove trailing backslash if present)
        if current_line.strip():
            final_line = current_line.rstrip()
            if final_line.endswith(" \\"):
                final_line = final_line[:-3].rstrip()
            formatted_lines.append(final_line)

        return formatted_lines if formatted_lines else [line]

    def _show_basic_troubleshooting_guide(
        self, analysis_type: str, target: str, data: Dict[str, Any]
    ) -> None:
        """Show basic troubleshooting guide when AI analysis fails"""
        console.print(
            f"\n[bold yellow]Basic Troubleshooting Guide for {target}[/bold yellow]"
        )
        console.print()

        # For build failures, show the actual build error
        if analysis_type == "build_failure":
            console.print("[bold cyan]Build Error Analysis:[/bold cyan]")

            # Show build error if available
            if data.get("build_error"):
                console.print("\n[bold red]Build Error:[/bold red]")
                error_lines = data["build_error"].strip().split("\n")
                for line in error_lines[-10:]:  # Show last 10 lines
                    if line.strip():
                        console.print(f"    [red]{line}[/red]")

            # Show build output if available
            if data.get("build_output"):
                console.print("\n[bold red]Build Output (last part):[/bold red]")
                output_lines = data["build_output"].strip().split("\n")
                for line in output_lines[-15:]:  # Show last 15 lines
                    if line.strip():
                        console.print(f"    [white]{line}[/white]")

            console.print("\n[bold cyan]Common Build Issues:[/bold cyan]")
            console.print("    1. [white]Missing dependencies in Dockerfile[/white]")
            console.print("    2. [white]Incorrect base image or version[/white]")
            console.print(
                "    3. [white]File not found errors (check COPY/ADD paths)[/white]"
            )
            console.print("    4. [white]Permission issues with files[/white]")
            console.print(
                "    5. [white]Network issues during package installation[/white]"
            )

            console.print("\n[bold green]Next Steps:[/bold green]")
            console.print(
                "    [white]Retry build:[/white] [cyan]pm build {}[/cyan]".format(
                    target
                )
            )
            console.print(
                "    [white]Clean rebuild:[/white] [cyan]pm reinit {} -b[/cyan]".format(
                    target
                )
            )
            console.print(
                "    [white]Check Dockerfile:[/white] [cyan]cat Dockerfile.{}[/cyan]".format(
                    target
                )
            )
            console.print()
            return

        # Check for common issues in the data
        if analysis_type in ["reinit_failure", "logs"]:
            console.print("[bold cyan]Common Issues to Check:[/bold cyan]")
            console.print(
                "    1. [white]Check service status:[/white] [cyan]systemctl --user status {}.service[/cyan]".format(
                    target
                )
            )
            console.print(
                "    2. [white]View recent logs:[/white] [cyan]journalctl --user -u {}.service -n 20[/cyan]".format(
                    target
                )
            )
            console.print("    3. [white]Check disk space:[/white] [cyan]df -h[/cyan]")
            console.print(
                "    4. [white]Check for port conflicts:[/white] [cyan]ss -tulpen | grep :8000[/cyan]"
            )
            console.print(
                "    5. [white]Restart the service:[/white] [cyan]pm restart {}[/cyan]".format(
                    target
                )
            )

            # Check for specific issues in the data
            if data.get("systemd_logs"):
                logs = data["systemd_logs"].lower()
                if "port already in use" in logs or "bind" in logs:
                    console.print("\n[bold red]⚠ Port Conflict Detected[/bold red]")
                    console.print(
                        "    [white]Try:[/white] [cyan]pm stop {} && pm start {}[/cyan]".format(
                            target, target
                        )
                    )
                elif "no space left" in logs or "disk" in logs:
                    console.print("\n[bold red]⚠ Disk Space Issue Detected[/bold red]")
                    console.print(
                        "    [white]Try:[/white] [cyan]podman system prune -f[/cyan]"
                    )
                elif "permission denied" in logs:
                    console.print("\n[bold red]⚠ Permission Issue Detected[/bold red]")
                    console.print(
                        "    [white]Try:[/white] [cyan]pm reset-failed {}[/cyan]".format(
                            target
                        )
                    )

            console.print("\n[bold green]Next Steps:[/bold green]")
            console.print(
                "    [white]For detailed analysis:[/white] [cyan]pm logs {} -ai claude[/cyan]".format(
                    target
                )
            )
            console.print(
                "    [white]For manual diagnosis:[/white] [cyan]pm diagnose {}[/cyan]".format(
                    target
                )
            )
            console.print()


# Global instance
ai_analyzer = AIAnalyzer(None)  # Will be initialized with manager when needed
