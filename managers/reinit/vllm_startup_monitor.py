"""VLLM startup monitoring functionality for reinit operations."""

import time
from typing import Optional

import requests
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from core.config import console, verbose_print


class VLLMStartupMonitor:
    """Monitors VLLM model service startup to ensure complete initialization before proceeding."""

    def __init__(self, manager):
        self.manager = manager
        self.vllm_port = 8005
        self.health_endpoint = f"http://localhost:{self.vllm_port}/health"
        self.models_endpoint = f"http://localhost:{self.vllm_port}/v1/models"

    def vllm_service_monitor_for_complete_start(
        self, container_name: str, timeout: int = 300, check_interval: float = 2.0
    ) -> bool:
        """Monitor VLLM service until it's completely started and ready.

        Args:
            container_name: Name of the VLLM container to monitor
            timeout: Maximum time to wait in seconds (default: 5 minutes)
            check_interval: Time between checks in seconds (default: 2 seconds)

        Returns:
            bool: True if service is fully ready, False if timeout or error
        """
        console.print(f"[cyan]🔍 Monitoring {container_name} startup...[/cyan]")

        start_time = time.time()

        with Live(
            self._create_startup_status_panel(container_name, "Initializing...", 0),
            console=console,
            refresh_per_second=1,
        ) as live:

            while time.time() - start_time < timeout:
                elapsed = time.time() - start_time

                # Check startup status
                status_info = self._check_vllm_startup_status(container_name)

                # Update live display
                live.update(
                    self._create_startup_status_panel(
                        container_name, status_info["status"], elapsed, status_info
                    )
                )

                # Check if fully ready
                if status_info["ready"]:
                    console.print(
                        f"[green]✅ {container_name} is fully ready in {elapsed:.1f}s[/green]"
                    )
                    return True

                # Check for critical errors
                if status_info["error"]:
                    console.print(
                        f"[red]❌ {container_name} startup failed: {status_info['details']}[/red]"
                    )
                    return False

                time.sleep(check_interval)

            # Timeout reached
            console.print(
                f"[red]⏰ Timeout waiting for {container_name} to be ready ({timeout}s)[/red]"
            )
            return False

    def _check_vllm_startup_status(self, container_name: str):
        """Check the current startup status of a VLLM service.

        Returns:
            Dict with keys: status, ready, error, details, stage
        """
        try:
            # Stage 1: Check if container is running
            container_status = self._get_container_status(container_name)
            if container_status != "running":
                return {
                    "status": f"Container {container_status}",
                    "ready": False,
                    "error": container_status in ["exited", "dead", "error"],
                    "details": f"Container status: {container_status}",
                    "stage": "container_check",
                }

            # Stage 2: Check if port is accessible
            if not self._is_port_accessible(self.vllm_port):
                return {
                    "status": "Starting up (port not ready)",
                    "ready": False,
                    "error": False,
                    "details": f"Port {self.vllm_port} not yet accessible",
                    "stage": "port_check",
                }

            # Stage 3: Check health endpoint
            health_status = self._check_health_endpoint()
            if not health_status["healthy"]:
                return {
                    "status": "Starting up (health check failed)",
                    "ready": False,
                    "error": health_status["error"],
                    "details": health_status["details"],
                    "stage": "health_check",
                }

            # Stage 4: Check if models are loaded
            models_status = self._check_models_endpoint()
            if not models_status["loaded"]:
                return {
                    "status": "Loading models...",
                    "ready": False,
                    "error": models_status["error"],
                    "details": models_status["details"],
                    "stage": "model_loading",
                }

            # Stage 5: Verify API responsiveness
            api_status = self._check_api_responsiveness()
            if not api_status["responsive"]:
                return {
                    "status": "API warming up...",
                    "ready": False,
                    "error": api_status["error"],
                    "details": api_status["details"],
                    "stage": "api_warmup",
                }

            # All checks passed - service is ready
            return {
                "status": "Ready",
                "ready": True,
                "error": False,
                "details": "All systems operational",
                "stage": "ready",
            }

        except Exception as e:
            verbose_print(f"[cyan]Error checking VLLM startup status: {e}[/cyan]")
            return {
                "status": "Status check error",
                "ready": False,
                "error": True,
                "details": f"Monitoring error: {str(e)[:100]}...",
                "stage": "error",
            }

    def _get_container_status(self, container_name: str) -> str:
        """Get the current status of a container."""
        try:
            import subprocess

            result = subprocess.run(
                ["podman", "inspect", container_name, "--format", "{{.State.Status}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                return result.stdout.strip().lower()
            else:
                return "not_found"

        except Exception as e:
            verbose_print(f"[cyan]Error getting container status: {e}[/cyan]")
            return "error"

    def _is_port_accessible(self, port: int) -> bool:
        """Check if a port is accessible for connections."""
        try:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("localhost", port))
                return result == 0
        except Exception:
            return False

    def _check_health_endpoint(self):
        """Check the VLLM health endpoint."""
        try:
            response = requests.get(self.health_endpoint, timeout=5)

            if response.status_code == 200:
                return {
                    "healthy": True,
                    "error": False,
                    "details": "Health endpoint responding",
                }
            else:
                return {
                    "healthy": False,
                    "error": False,
                    "details": f"Health endpoint returned {response.status_code}",
                }

        except requests.exceptions.ConnectionError:
            return {
                "healthy": False,
                "error": False,
                "details": "Health endpoint not yet available",
            }
        except requests.exceptions.Timeout:
            return {
                "healthy": False,
                "error": False,
                "details": "Health endpoint timeout",
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": True,
                "details": f"Health check error: {str(e)[:50]}...",
            }

    def _check_models_endpoint(self):
        """Check if models are loaded via the models endpoint."""
        try:
            response = requests.get(self.models_endpoint, timeout=10)

            if response.status_code == 200:
                try:
                    models_data = response.json()
                    if "data" in models_data and len(models_data["data"]) > 0:
                        model_count = len(models_data["data"])
                        return {
                            "loaded": True,
                            "error": False,
                            "details": f"{model_count} model(s) loaded",
                        }
                    else:
                        return {
                            "loaded": False,
                            "error": False,
                            "details": "No models loaded yet",
                        }
                except Exception as e:
                    return {
                        "loaded": False,
                        "error": False,
                        "details": f"Models endpoint response parsing error: {str(e)[:50]}...",
                    }
            else:
                return {
                    "loaded": False,
                    "error": False,
                    "details": f"Models endpoint returned {response.status_code}",
                }

        except requests.exceptions.ConnectionError:
            return {
                "loaded": False,
                "error": False,
                "details": "Models endpoint not yet available",
            }
        except requests.exceptions.Timeout:
            return {
                "loaded": False,
                "error": False,
                "details": "Models endpoint timeout (still loading)",
            }
        except Exception as e:
            return {
                "loaded": False,
                "error": True,
                "details": f"Models check error: {str(e)[:50]}...",
            }

    def _check_api_responsiveness(self):
        """Check if the API is responsive with a simple test request."""
        try:
            # Try a simple completion request to verify the API is fully operational
            test_payload = {
                "model": "default",  # VLLM typically uses a default model name
                "prompt": "Hello",
                "max_tokens": 1,
                "temperature": 0.1,
            }

            response = requests.post(
                f"http://localhost:{self.vllm_port}/v1/completions",
                json=test_payload,
                timeout=15,  # Longer timeout for first API call
            )

            if response.status_code in [
                200,
                422,
            ]:  # 422 might be model name issue, but API is responsive
                return {
                    "responsive": True,
                    "error": False,
                    "details": "API responding to requests",
                }
            else:
                return {
                    "responsive": False,
                    "error": False,
                    "details": f"API returned {response.status_code}",
                }

        except requests.exceptions.ConnectionError:
            return {
                "responsive": False,
                "error": False,
                "details": "API not yet available",
            }
        except requests.exceptions.Timeout:
            return {
                "responsive": False,
                "error": False,
                "details": "API still warming up (timeout)",
            }
        except Exception as e:
            return {
                "responsive": False,
                "error": True,
                "details": f"API test error: {str(e)[:50]}...",
            }

    def _create_startup_status_panel(
        self,
        container_name: str,
        status: str,
        elapsed: float,
        status_info: Optional[dict] = None,
    ) -> Panel:
        """Create a rich panel showing VLLM startup status."""

        # Create status content
        content_lines = [
            f"Container: [bold cyan]{container_name}[/bold cyan]",
            f"Status: [yellow]{status}[/yellow]",
            f"Elapsed: [dim]{elapsed:.1f}s[/dim]",
        ]

        if status_info:
            if "stage" in status_info:
                stage_names = {
                    "container_check": "🐳 Container Status",
                    "port_check": "🔌 Port Accessibility",
                    "health_check": "❤️ Health Endpoint",
                    "model_loading": "🧠 Model Loading",
                    "api_warmup": "🚀 API Warmup",
                    "ready": "✅ Ready",
                    "error": "❌ Error",
                }
                stage_display = stage_names.get(
                    status_info["stage"], status_info["stage"]
                )
                content_lines.append(f"Stage: [cyan]{stage_display}[/cyan]")

            if "details" in status_info:
                content_lines.append(f"Details: [dim]{status_info['details']}[/dim]")

            # Add progress indicators
            if status_info.get("ready"):
                content_lines.append("[green]🎉 Service fully operational![/green]")
            elif status_info.get("error"):
                content_lines.append("[red]💥 Startup failed[/red]")
            else:
                content_lines.append("[yellow]⏳ Startup in progress...[/yellow]")

        content = "\n".join(content_lines)

        return Panel(
            content,
            title="[bold]VLLM Startup Monitor[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )

    def wait_for_vllm_ready_with_progress(
        self, container_name: str, timeout: int = 300
    ) -> bool:
        """Wait for VLLM to be ready with a progress bar instead of live display.

        Alternative method that uses a progress bar for simpler display.
        """
        console.print(f"[cyan]Waiting for {container_name} to be ready...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]Initializing VLLM service...[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("startup", total=None)

            start_time = time.time()
            last_status = ""

            while time.time() - start_time < timeout:
                status_info = self._check_vllm_startup_status(container_name)

                # Update progress description if status changed
                if status_info["status"] != last_status:
                    progress.update(
                        task, description=f"[yellow]{status_info['status']}...[/yellow]"
                    )
                    last_status = status_info["status"]

                if status_info["ready"]:
                    elapsed = time.time() - start_time
                    progress.update(
                        task, description=f"[green]Ready in {elapsed:.1f}s[/green]"
                    )
                    time.sleep(0.5)  # Brief pause to show completion
                    progress.remove_task(task)
                    return True

                if status_info["error"]:
                    progress.update(
                        task,
                        description=f"[red]Startup failed: {status_info['details']}[/red]",
                    )
                    time.sleep(0.5)  # Brief pause to show error
                    progress.remove_task(task)
                    return False

                time.sleep(2.0)

            # Timeout
            progress.update(task, description=f"[red]Timeout after {timeout}s[/red]")
            time.sleep(0.5)
            progress.remove_task(task)
            return False
