"""Data collection classes for AI analysis system"""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import verbose_print


class DataCollector(ABC):
    """Abstract base class for data collectors"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    @abstractmethod
    def collect(self, target: str, **kwargs) -> Dict[str, Any]:
        """Collect data for the given target"""
        pass

    def _run_command(self, cmd: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run a command and return structured result"""
        if self.verbose:
            verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "returncode": -1,
                "success": False,
            }
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "returncode": -1, "success": False}


class SystemdDataCollector(DataCollector):
    """Collects systemd service data"""

    def collect(self, target: str, **kwargs) -> Dict[str, Any]:
        """Collect systemd service information"""
        service_name = self._resolve_service_name(target, kwargs.get("manager"))
        if not service_name:
            return {"error": f"Service '{target}' not found"}

        data = {"service_name": service_name, "target": target}

        # Get service status
        status_result = self._run_command(
            ["systemctl", "--user", "status", service_name, "--no-pager", "-l"],
            timeout=15,
        )

        if status_result["success"]:
            data["unit_status"] = self._format_systemd_status_output(
                status_result["stdout"] + (status_result["stderr"] or "")
            )
            data["unit_status_code"] = status_result["returncode"]

        # Get unit file content
        cat_result = self._run_command(
            ["systemctl", "--user", "cat", service_name], timeout=10
        )

        if cat_result["success"]:
            data["unit_file_content"] = cat_result["stdout"].strip()

        # Get unit properties
        show_result = self._run_command(
            [
                "systemctl",
                "--user",
                "show",
                service_name,
                "-p",
                "ExecMainStatus,ExecMainCode,Result,ActiveEnterTimestamp,InactiveEnterTimestamp,RestartCount",
            ],
            timeout=10,
        )

        if show_result["success"]:
            data["unit_properties"] = show_result["stdout"].strip()

        return data

    def _resolve_service_name(self, target: str, manager) -> Optional[str]:
        """Resolve target to actual service name"""
        if not manager:
            return target

        if hasattr(manager, "get_matched_service_name"):
            return manager.get_matched_service_name(target)
        elif hasattr(manager, "_find_service_project"):
            project = manager._find_service_project(target)
            return target if project else None
        else:
            return target

    def _format_systemd_status_output(self, status_output: str) -> str:
        """Format systemd status output for better readability"""
        import re

        lines = status_output.split("\n")
        formatted_lines = []

        for line in lines:
            # Format long Process: ExecStart= commands
            if "Process:" in line and "ExecStart=" in line and len(line) > 120:
                process_match = re.match(
                    r"^(\s*Process:\s+\d+\s+ExecStart=)(.+)(\s+\(code=.+\))$", line
                )
                if process_match:
                    prefix = process_match.group(1)
                    command = process_match.group(2)
                    suffix = process_match.group(3)

                    formatted_command = self._format_podman_command(command)
                    formatted_lines.append(prefix)
                    formatted_lines.extend(formatted_command)
                    formatted_lines.append(f"    {suffix}")
                else:
                    formatted_lines.append(line)
            # Format long CGroup podman commands
            elif (
                ("└─" in line or "├─" in line)
                and "/usr/local/bin/podman" in line
                and len(line) > 120
            ):
                cgroup_match = re.match(r"^(\s*[└├]─\d+\s+)(.+)$", line)
                if cgroup_match:
                    prefix = cgroup_match.group(1)
                    command = cgroup_match.group(2)
                    formatted_command = self._format_podman_command(command)

                    if formatted_command:
                        formatted_lines.append(prefix + formatted_command[0].strip())
                        for continuation_line in formatted_command[1:]:
                            formatted_lines.append(
                                " " * len(prefix) + continuation_line.strip()
                            )
                    else:
                        formatted_lines.append(line)
                else:
                    formatted_lines.append(line)
            else:
                formatted_lines.append(line)

        return "\n".join(formatted_lines)

    def _format_podman_command(self, command: str) -> List[str]:
        """Format a long podman command for better readability"""
        import shlex

        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()

        formatted_lines = []
        current_line = "    "

        for i, part in enumerate(parts):
            if part.startswith("--") and i > 0:
                if len(current_line) > 80:
                    formatted_lines.append(current_line.rstrip())
                    current_line = "      "

            current_line += part + " "

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
                continue

        if current_line.strip():
            formatted_lines.append(current_line.rstrip())

        return formatted_lines


class ContainerDataCollector(DataCollector):
    """Collects Podman container data"""

    def collect(self, target: str, **kwargs) -> Dict[str, Any]:
        """Collect container information"""
        data = {}

        # List all containers
        ps_result = self._run_command(
            [
                "podman",
                "ps",
                "-a",
                "--format",
                "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}",
            ],
            timeout=10,
        )

        if ps_result["success"]:
            data["container_list"] = ps_result["stdout"].strip()
            container_name = self._find_matching_container(target, ps_result["stdout"])

            if container_name:
                # Get container logs
                logs_result = self._run_command(
                    [
                        "podman",
                        "logs",
                        container_name,
                        "--since",
                        "2h",
                        "--timestamps",
                        "--tail",
                        "100",
                    ],
                    timeout=15,
                )

                if logs_result["success"]:
                    data["container_logs"] = logs_result["stdout"].strip()

                # Get container inspection
                inspect_result = self._run_command(
                    ["podman", "inspect", container_name], timeout=10
                )

                if inspect_result["success"]:
                    data["container_inspect"] = inspect_result["stdout"].strip()
            else:
                # Try direct service-based log collection
                direct_logs_result = self._run_command(
                    [
                        "podman",
                        "logs",
                        target,
                        "--since",
                        "2h",
                        "--timestamps",
                        "--tail",
                        "100",
                    ],
                    timeout=15,
                )

                if direct_logs_result["success"]:
                    data["container_logs"] = direct_logs_result["stdout"].strip()

        # Check for pods
        pod_result = self._run_command(
            ["podman", "pod", "ps", "--format", "{{.ID}}\t{{.Name}}\t{{.Status}}"],
            timeout=10,
        )

        if pod_result["success"] and pod_result["stdout"].strip():
            data["pod_list"] = pod_result["stdout"].strip()

        return data

    def _find_matching_container(
        self, target: str, container_list: str
    ) -> Optional[str]:
        """Find container name that matches target"""
        for line in container_list.strip().split("\n"):
            if line and target.lower() in line.lower():
                parts = line.split("\t")
                if len(parts) >= 2:
                    return parts[1]  # Container name
        return None


class SystemResourceCollector(DataCollector):
    """Collects system resource information"""

    def collect(self, target: str, **kwargs) -> Dict[str, Any]:
        """Collect system resource data"""
        data = {}

        # Disk space
        df_result = self._run_command(["df", "-h", "/"], timeout=5)
        if df_result["success"]:
            data["disk_space"] = df_result["stdout"].strip()

        # Podman system info
        info_result = self._run_command(["podman", "system", "info"], timeout=10)
        if info_result["success"]:
            data["podman_system_info"] = info_result["stdout"].strip()

        # Podman disk usage
        df_podman_result = self._run_command(["podman", "system", "df"], timeout=10)
        if df_podman_result["success"]:
            data["podman_disk_usage"] = df_podman_result["stdout"].strip()

        return data


class NetworkStorageCollector(DataCollector):
    """Collects network and storage information"""

    def collect(self, target: str, **kwargs) -> Dict[str, Any]:
        """Collect network and storage data"""
        data = {}

        # Podman networks
        net_result = self._run_command(["podman", "network", "ls"], timeout=10)
        if net_result["success"]:
            data["podman_networks"] = net_result["stdout"].strip()

        # Podman volumes
        vol_result = self._run_command(["podman", "volume", "ls"], timeout=10)
        if vol_result["success"]:
            data["podman_volumes"] = vol_result["stdout"].strip()

        # Check port usage
        common_ports = ["8000", "8001", "8002", "8003", "8080", "3000", "5000"]
        port_info = []

        ss_result = self._run_command(["ss", "-tulpen", "-H"], timeout=5)
        if ss_result["success"]:
            for port in common_ports:
                for line in ss_result["stdout"].split("\n"):
                    if f":{port}" in line:
                        port_info.append(f"Port {port}: {line.strip()}")

        if port_info:
            data["port_usage"] = "\n".join(port_info)

        return data


class QuadletDataCollector(DataCollector):
    """Collects Quadlet .container file information"""

    def collect(self, target: str, **kwargs) -> Dict[str, Any]:
        """Collect Quadlet .container file contents"""
        data = {}
        service_name = kwargs.get("service_name", target)

        # Common locations for Quadlet .container files
        quadlet_dirs = [
            Path.home() / ".config" / "containers" / "systemd",
            Path("/etc/containers/systemd"),
            Path("/usr/share/containers/systemd"),
        ]

        # Try different naming patterns
        container_file_patterns = [
            f"{service_name}.container",
            f"{service_name.replace('-', '_')}.container",
            f"{service_name.replace('_', '-')}.container",
        ]

        container_file_found = False

        for quadlet_dir in quadlet_dirs:
            if not quadlet_dir.exists():
                continue

            for pattern in container_file_patterns:
                container_file = quadlet_dir / pattern
                if container_file.exists():
                    try:
                        with open(container_file, "r") as f:
                            data["quadlet_container_file"] = f.read().strip()
                            data["quadlet_container_file_path"] = str(container_file)
                            container_file_found = True
                            break
                    except Exception as e:
                        if self.verbose:
                            verbose_print(
                                f"  [cyan]exec: Failed to read {container_file}: {e}[/cyan]"
                            )

            if container_file_found:
                break

        if not container_file_found:
            data["quadlet_container_file"] = "No .container file found"

            # List available .container files for debugging
            for quadlet_dir in quadlet_dirs:
                if quadlet_dir.exists():
                    try:
                        container_files = list(quadlet_dir.glob("*.container"))
                        if container_files:
                            available_files = [f.name for f in container_files]
                            data["available_container_files"] = (
                                f"Available in {quadlet_dir}: {', '.join(available_files)}"
                            )
                            break
                    except Exception:
                        pass

        return data


class LogsDataCollector(DataCollector):
    """Collects service logs"""

    def collect(self, target: str, **kwargs) -> Dict[str, Any]:
        """Collect service logs"""
        service_name = kwargs.get("service_name", target)
        lines = kwargs.get("lines", 50)

        # Get systemd unit logs
        logs_result = self._run_command(
            [
                "journalctl",
                "--user",
                "-u",
                service_name,
                "-n",
                str(lines),
                "--no-pager",
            ],
            timeout=30,
        )

        data = {"service_name": service_name, "target": target}

        if logs_result["success"] and logs_result["stdout"].strip():
            data["systemd_logs"] = logs_result["stdout"].strip()
            data["log_lines_count"] = len(logs_result["stdout"].strip().split("\n"))
        else:
            data["systemd_logs"] = "No systemd logs found"
            data["log_lines_count"] = 0

        return data


class PerformanceDataCollector(DataCollector):
    """Collects performance metrics"""

    def collect(self, target: str, **kwargs) -> Dict[str, Any]:
        """Collect performance data"""
        stats_result = self._run_command(
            ["podman", "stats", "--no-stream", "--format", "json"], timeout=10
        )

        if stats_result["success"]:
            return {"performance_data": stats_result["stdout"]}
        else:
            return {"performance_data": "No performance data available"}
