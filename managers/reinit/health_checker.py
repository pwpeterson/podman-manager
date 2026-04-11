"""Health checking functionality for reinit operations."""

import subprocess
import time
from typing import Dict, List, Tuple

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from core.config import console


class HealthChecker:
    """Handles comprehensive health checks before and after reinit operations."""

    def __init__(self, manager):
        self.manager = manager

    def perform_pre_reinit_health_check(self, target: str) -> bool:
        """Perform comprehensive pre-reinit health check."""
        console.print("[cyan]🔍 Pre-reinit Health Check[/cyan]")

        health_checks = [
            ("Service Status", self._check_service_status),
            ("Container State", self._check_container_state),
            ("Resource Usage", self._check_resource_usage),
            ("Network Connectivity", self._check_network_connectivity),
            ("Storage Health", self._check_storage_health),
        ]

        health_results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]Running health checks...[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("health_check", total=None)

            for check_name, check_func in health_checks:
                try:
                    result = check_func(target)
                    health_results.append(
                        (check_name, result["status"], result["details"])
                    )
                    progress.update(
                        task,
                        description=f"[yellow]Checking {check_name.lower()}...[/yellow]",
                    )
                    time.sleep(0.5)  # Brief pause for visual feedback
                except Exception as e:
                    health_results.append((check_name, "error", str(e)))

            progress.remove_task(task)

        # Display health check results
        self._display_health_check_results(health_results)

        # Determine if we should proceed
        critical_failures = [r for r in health_results if r[1] == "critical"]
        if critical_failures:
            console.print("\n[red]❌ Critical issues detected. Reinit may fail.[/red]")
            return False

        warnings = [r for r in health_results if r[1] == "warning"]
        if warnings:
            console.print(
                "\n[yellow]⚠️  Warnings detected. Proceeding with enhanced monitoring.[/yellow]"
            )
        else:
            console.print(
                "\n[green]✅ Health check passed. Proceeding with reinit.[/green]"
            )

        console.print()
        return True

    def _check_service_status(self, target: str) -> Dict[str, str]:
        """Check current service status and recent failures."""
        try:
            # Get service name
            service_name = self.manager._find_service_name(target)
            if not service_name or service_name.startswith("STACK:"):
                service_name = target

            # Check systemctl status
            result = subprocess.run(
                ["sudo", "systemctl", "status", service_name],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if "failed" in result.stdout.lower():
                return {"status": "warning", "details": "Service in failed state"}
            elif "active (running)" in result.stdout.lower():
                return {"status": "good", "details": "Service running normally"}
            elif "inactive" in result.stdout.lower():
                return {"status": "info", "details": "Service stopped"}
            else:
                return {"status": "warning", "details": "Service in unknown state"}

        except Exception as e:
            return {"status": "error", "details": f"Status check failed: {e}"}

    def _check_container_state(self, target: str) -> Dict[str, str]:
        """Check container state and recent exit codes."""
        try:
            # Use fuzzy matching to find container
            from core.simple_fuzzy_matcher import find_container

            container = find_container(target)

            if not container:
                return {"status": "warning", "details": "Container not found"}

            container_name = container["name"]

            # Check container status
            result = subprocess.run(
                [
                    "podman",
                    "ps",
                    "-a",
                    "--format",
                    "{{.Names}} {{.Status}}",
                    "--filter",
                    f"name={container_name}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                status_line = result.stdout.strip()
                if "Up" in status_line:
                    return {"status": "good", "details": "Container running"}
                elif "Exited (0)" in status_line:
                    return {"status": "info", "details": "Container stopped cleanly"}
                elif "Exited" in status_line:
                    return {
                        "status": "warning",
                        "details": "Container exited with error",
                    }
                else:
                    return {"status": "info", "details": "Container in transition"}
            else:
                return {"status": "warning", "details": "Container not created"}

        except Exception as e:
            return {"status": "error", "details": f"Container check failed: {e}"}

    def _check_resource_usage(self, target: str) -> Dict[str, str]:
        """Check system resource usage that might affect reinit."""
        try:
            import psutil

            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                return {
                    "status": "critical",
                    "details": f"High memory usage: {memory.percent:.1f}%",
                }
            elif memory.percent > 80:
                return {
                    "status": "warning",
                    "details": f"Elevated memory usage: {memory.percent:.1f}%",
                }

            # Check disk usage
            disk = psutil.disk_usage("/")
            if disk.percent > 95:
                return {
                    "status": "critical",
                    "details": f"Disk nearly full: {disk.percent:.1f}%",
                }
            elif disk.percent > 85:
                return {
                    "status": "warning",
                    "details": f"High disk usage: {disk.percent:.1f}%",
                }

            return {
                "status": "good",
                "details": f"Resources OK (Mem: {memory.percent:.1f}%, Disk: {disk.percent:.1f}%)",
            }

        except ImportError:
            return {
                "status": "info",
                "details": "Resource monitoring unavailable (psutil not installed)",
            }
        except Exception as e:
            return {"status": "error", "details": f"Resource check failed: {e}"}

    def _check_network_connectivity(self, target: str) -> Dict[str, str]:
        """Check network connectivity for services that need it."""
        try:
            # Check ports based on specific service types
            if "vllm" in target.lower() and target not in [
                "abacus-proxy",
                "mcp-vllm-delegator",
            ]:
                import socket

                # vLLM model services use port 8005
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    result = s.connect_ex(("localhost", 8005))
                    if result == 0:
                        return {
                            "status": "info",
                            "details": "vLLM model port 8005 in use",
                        }
                    else:
                        return {
                            "status": "good",
                            "details": "vLLM model port 8005 available",
                        }
            elif target == "abacus-proxy":
                import socket

                # abacus-proxy uses port 8003
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    result = s.connect_ex(("localhost", 8003))
                    if result == 0:
                        return {
                            "status": "info",
                            "details": "abacus proxy port 8003 in use",
                        }
                    else:
                        return {
                            "status": "good",
                            "details": "abacus proxy port 8003 available",
                        }
            elif target == "mcp-model-delegator":
                import socket

                # mcp-model-delegator uses port 8003
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    result = s.connect_ex(("localhost", 8003))
                    if result == 0:
                        return {
                            "status": "info",
                            "details": "MCP model delegator port 8003 in use",
                        }
                    else:
                        return {
                            "status": "good",
                            "details": "MCP model delegator port 8003 available",
                        }

            return {"status": "good", "details": "Network connectivity OK"}

        except Exception as e:
            return {"status": "error", "details": f"Network check failed: {e}"}

    def _check_storage_health(self, target: str) -> Dict[str, str]:
        """Check storage health and volume availability."""
        try:
            # Check if podman volumes are accessible
            result = subprocess.run(
                ["podman", "volume", "ls", "--quiet"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                volume_count = (
                    len(result.stdout.strip().split("\n"))
                    if result.stdout.strip()
                    else 0
                )
                return {
                    "status": "good",
                    "details": f"Storage OK ({volume_count} volumes)",
                }
            else:
                return {"status": "warning", "details": "Volume access issues"}

        except Exception as e:
            return {"status": "error", "details": f"Storage check failed: {e}"}

    def _display_health_check_results(
        self, results: List[Tuple[str, str, str]]
    ) -> None:
        """Display health check results in a formatted table."""
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Check", style="white", width=20)
        table.add_column("Status", width=12)
        table.add_column("Details", style="dim")

        status_styles = {
            "good": "[green]✅ Good[/green]",
            "info": "[blue]ℹ️  Info[/blue]",
            "warning": "[yellow]⚠️  Warning[/yellow]",
            "critical": "[red]❌ Critical[/red]",
            "error": "[red]💥 Error[/red]",
        }

        for check_name, status, details in results:
            styled_status = status_styles.get(status, f"[dim]{status}[/dim]")
            table.add_row(check_name, styled_status, details)

        console.print(table)

    def verify_service_status(self, target: str) -> Dict[str, str]:
        """Verify service is running properly after reinit."""
        try:
            service_name = self.manager._find_service_name(target)
            if not service_name or service_name.startswith("STACK:"):
                service_name = target

            result = subprocess.run(
                ["sudo", "systemctl", "is-active", service_name],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip() == "active":
                return {"status": "good", "details": "Service active and running"}
            else:
                return {
                    "status": "warning",
                    "details": f"Service state: {result.stdout.strip()}",
                }

        except Exception as e:
            return {"status": "error", "details": f"Status verification failed: {e}"}

    def verify_container_health(self, target: str) -> Dict[str, str]:
        """Verify container is healthy after reinit."""
        try:
            from core.simple_fuzzy_matcher import find_container

            container = find_container(target)

            if not container:
                return {"status": "warning", "details": "Container not found"}

            # Check if container is running
            if container["status"] == "running":
                # For different service types, check appropriate health endpoints
                if target == "mcp-model-delegator":
                    try:
                        import requests

                        response = requests.get(
                            "http://localhost:8003/health", timeout=5
                        )
                        if response.status_code == 200:
                            return {
                                "status": "good",
                                "details": "MCP model delegator healthy and responding",
                            }
                        else:
                            return {
                                "status": "warning",
                                "details": "MCP model delegator running but not responding",
                            }
                    except Exception:
                        return {
                            "status": "info",
                            "details": "MCP model delegator running (health check unavailable)",
                        }
                elif "vllm" in target.lower() and target not in [
                    "abacus-proxy",
                    "mcp-model-delegator",
                ]:
                    try:
                        import requests

                        # vLLM model services use port 8005
                        response = requests.get(
                            "http://localhost:8005/health", timeout=5
                        )
                        if response.status_code == 200:
                            return {
                                "status": "good",
                                "details": "vLLM model service healthy and responding",
                            }
                        else:
                            return {
                                "status": "warning",
                                "details": "vLLM model service running but not responding",
                            }
                    except Exception:
                        return {
                            "status": "info",
                            "details": "vLLM model service running (health check unavailable)",
                        }
                elif target == "abacus-proxy":
                    try:
                        import requests

                        response = requests.get(
                            "http://localhost:8003/health", timeout=5
                        )
                        if response.status_code == 200:
                            return {
                                "status": "good",
                                "details": "abacus proxy healthy and responding",
                            }
                        else:
                            return {
                                "status": "warning",
                                "details": "abacus proxy running but not responding",
                            }
                    except Exception:
                        return {
                            "status": "info",
                            "details": "abacus proxy running (health check unavailable)",
                        }
                else:
                    return {"status": "good", "details": "Container running normally"}
            else:
                return {
                    "status": "warning",
                    "details": f"Container status: {container['status']}",
                }

        except Exception as e:
            return {"status": "error", "details": f"Health verification failed: {e}"}

    def verify_performance(self, pre_reinit_state: Dict) -> Dict[str, str]:
        """Check performance metrics after reinit."""
        try:
            # Compare with pre-reinit state if available
            if "timestamp" in pre_reinit_state:
                reinit_duration = time.time() - pre_reinit_state["timestamp"]
                if reinit_duration < 30:
                    return {
                        "status": "good",
                        "details": f"Fast reinit ({reinit_duration:.1f}s)",
                    }
                elif reinit_duration < 60:
                    return {
                        "status": "info",
                        "details": f"Normal reinit ({reinit_duration:.1f}s)",
                    }
                else:
                    return {
                        "status": "warning",
                        "details": f"Slow reinit ({reinit_duration:.1f}s)",
                    }
            else:
                return {"status": "info", "details": "Performance baseline unavailable"}

        except Exception as e:
            return {"status": "error", "details": f"Performance check failed: {e}"}
