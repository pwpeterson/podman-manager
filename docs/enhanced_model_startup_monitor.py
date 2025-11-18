"""Enhanced model startup monitoring that handles different model types and ports correctly.

Supports both vLLM and llama.cpp models with their specific configurations:
- llama.cpp models: Direct connection on port 8005
- vLLM models: Via vllm-proxy on port 8002 (proxied to port 8005)
"""

import json
import time
from pathlib import Path
from typing import Dict

import requests
from rich.progress import Progress, SpinnerColumn, TextColumn

from core.config import console, verbose_print


class EnhancedModelStartupMonitor:
    """Enhanced monitoring for both vLLM and llama.cpp models with correct port handling."""

    def __init__(self, manager):
        self.manager = manager
        self.model_configs = self._load_model_configs()

    def _load_model_configs(self) -> Dict[str, Dict]:
        """Load model configurations from ai_agents_config.json."""
        try:
            config_path = Path("ai_agents_config.json")
            if config_path.exists():
                with open(config_path, "r") as f:
                    config = json.load(f)

                # Create a mapping of model names to their configurations
                model_configs = {}
                for agent in config.get("agents", []):
                    model_name = agent.get("model_name", agent.get("name", ""))
                    model_configs[model_name] = {
                        "endpoint": agent.get("endpoint", "http://localhost:8005"),
                        "model_type": self._detect_model_type(model_name),
                        "port": self._extract_port(
                            agent.get("endpoint", "http://localhost:8005")
                        ),
                        "description": agent.get("description", ""),
                    }

                return model_configs
        except Exception as e:
            verbose_print(f"[cyan]Error loading model configs: {e}[/cyan]")

        # Fallback configuration
        return {}

    def _detect_model_type(self, model_name: str) -> str:
        """Detect if model is vLLM or llama.cpp based on name."""
        if model_name.startswith("llama-"):
            return "llama.cpp"
        elif model_name.startswith("vllm-"):
            return "vllm"
        else:
            return "unknown"

    def _extract_port(self, endpoint: str) -> int:
        """Extract port number from endpoint URL."""
        try:
            if ":" in endpoint:
                port_str = endpoint.split(":")[-1]
                # Remove any path components
                port_str = port_str.split("/")[0]
                return int(port_str)
        except (ValueError, IndexError):
            pass

        # Default fallback
        return 8005

    def get_model_config(self, container_name: str) -> Dict:
        """Get configuration for a specific model."""
        # Try exact match first
        if container_name in self.model_configs:
            return self.model_configs[container_name]

        # Try to find by partial match
        for model_name, config in self.model_configs.items():
            if model_name in container_name or container_name in model_name:
                return config

        # Fallback based on container name pattern
        # ALL models (llama.cpp and vLLM) are accessed via vllm-proxy on port 8002
        if container_name.startswith("llama-"):
            return {
                "endpoint": "http://localhost:8002",  # llama.cpp via proxy
                "model_type": "llama.cpp",
                "port": 8002,
                "description": "llama.cpp model (via vllm-proxy)",
            }
        elif container_name.startswith("vllm-"):
            return {
                "endpoint": "http://localhost:8002",  # vLLM via proxy
                "model_type": "vllm",
                "port": 8002,
                "description": "vLLM model (via vllm-proxy)",
            }
        else:
            # Default fallback - also via proxy
            return {
                "endpoint": "http://localhost:8002",
                "model_type": "unknown",
                "port": 8002,
                "description": "Unknown model type (via vllm-proxy)",
            }

    def monitor_model_startup(self, container_name: str, timeout: int = 300) -> bool:
        """Monitor model startup with correct port and endpoint configuration."""
        model_config = self.get_model_config(container_name)
        model_type = model_config["model_type"]
        port = model_config["port"]
        endpoint = model_config["endpoint"]

        console.print(f"[cyan]🔍 Monitoring {container_name} startup...[/cyan]")
        console.print(
            f"[dim]Model type: {model_type}, Port: {port}, Endpoint: {endpoint}[/dim]"
        )

        # All models use the same proxy architecture (port 8002)
        # but may have different startup characteristics
        if model_type == "llama.cpp":
            return self._monitor_llamacpp_via_proxy(container_name, port, timeout)
        elif model_type == "vllm":
            return self._monitor_vllm_via_proxy(container_name, port, timeout)
        else:
            # Fallback to generic monitoring via proxy
            return self._monitor_generic_via_proxy(container_name, port, timeout)

    def _monitor_llamacpp_via_proxy(
        self, container_name: str, port: int, timeout: int
    ) -> bool:
        """Monitor llama.cpp model startup via vllm-proxy with specific checks."""
        console.print(
            f"[cyan]Waiting for {container_name} (llama.cpp via proxy) to be ready...[/cyan]"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("startup", total=None)

            start_time = time.time()
            consecutive_failures = 0
            max_failures = 3

            while time.time() - start_time < timeout:
                elapsed = time.time() - start_time

                # Check container status first
                container_status = self._get_container_status(container_name)
                if container_status in ["error", "exited", "dead"]:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        console.print(
                            f"[red]❌ {container_name} container failed to start (status: {container_status})[/red]"
                        )
                        console.print(
                            "[yellow]💡 llama.cpp model startup failed - check container logs[/yellow]"
                        )
                        console.print(
                            f"[dim]   Try: journalctl --user -u {container_name}.service -n 20[/dim]"
                        )
                        return False
                else:
                    consecutive_failures = 0

                if container_status != "running":
                    progress.update(
                        task,
                        description=f"[yellow]Container starting ({container_status}) - {elapsed:.1f}s[/yellow]",
                    )
                    time.sleep(2.0)
                    continue

                # Check if port is accessible
                if not self._is_port_accessible(port):
                    progress.update(
                        task,
                        description=f"[yellow]Port {port} not ready - {elapsed:.1f}s[/yellow]",
                    )
                    time.sleep(2.0)
                    continue

                # Check health endpoint
                health_status = self._check_health_endpoint(port)
                if not health_status["healthy"]:
                    progress.update(
                        task,
                        description=f"[yellow]Health check: {health_status['details']} - {elapsed:.1f}s[/yellow]",
                    )
                    time.sleep(2.0)
                    continue

                # Check models endpoint
                models_status = self._check_models_endpoint(port)
                if not models_status["loaded"]:
                    progress.update(
                        task,
                        description=f"[yellow]Loading models: {models_status['details']} - {elapsed:.1f}s[/yellow]",
                    )
                    time.sleep(3.0)  # Longer wait for model loading
                    continue

                # Final API test
                api_status = self._check_api_responsiveness(port)
                if not api_status["responsive"]:
                    progress.update(
                        task,
                        description=f"[yellow]API warming up: {api_status['details']} - {elapsed:.1f}s[/yellow]",
                    )
                    time.sleep(2.0)
                    continue

                # All checks passed
                console.print(
                    f"[green]✅ {container_name} (llama.cpp via proxy) is fully ready in {elapsed:.1f}s[/green]"
                )
                return True

            # Timeout
            console.print(
                f"[red]⏰ Timeout waiting for {container_name} to be ready ({timeout}s)[/red]"
            )
            return False

    def _monitor_vllm_via_proxy(
        self, container_name: str, port: int, timeout: int
    ) -> bool:
        """Monitor vLLM model startup via vllm-proxy."""
        console.print(
            f"[cyan]Waiting for {container_name} (vLLM via proxy) to be ready...[/cyan]"
        )

        # vLLM models use similar monitoring via proxy
        return self._monitor_generic_via_proxy(container_name, port, timeout)

    def _monitor_generic_via_proxy(
        self, container_name: str, port: int, timeout: int
    ) -> bool:
        """Generic model startup monitoring via vllm-proxy."""
        console.print(
            f"[cyan]Waiting for {container_name} to be ready via proxy on port {port}...[/cyan]"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("startup", total=None)

            start_time = time.time()

            while time.time() - start_time < timeout:
                elapsed = time.time() - start_time

                # Basic health checks
                if self._is_port_accessible(port):
                    health_status = self._check_health_endpoint(port)
                    if health_status["healthy"]:
                        console.print(
                            f"[green]✅ {container_name} is ready in {elapsed:.1f}s[/green]"
                        )
                        return True
                    else:
                        progress.update(
                            task,
                            description=f"[yellow]{health_status['details']} - {elapsed:.1f}s[/yellow]",
                        )
                else:
                    progress.update(
                        task,
                        description=f"[yellow]Port {port} not accessible - {elapsed:.1f}s[/yellow]",
                    )

                time.sleep(2.0)

            console.print(
                f"[red]⏰ Timeout waiting for {container_name} ({timeout}s)[/red]"
            )
            return False

    def _get_container_status(self, container_name: str) -> str:
        """Get container status with timeout protection."""
        try:
            import subprocess

            result = subprocess.run(
                ["podman", "inspect", container_name, "--format", "{{.State.Status}}"],
                capture_output=True,
                text=True,
                timeout=3,
            )

            if result.returncode == 0:
                return result.stdout.strip().lower()
            else:
                if "no such container" in result.stderr.lower():
                    return "not_found"
                return "error"

        except subprocess.TimeoutExpired:
            return "timeout"
        except FileNotFoundError:
            return "no_runtime"
        except Exception:
            return "error"

    def _is_port_accessible(self, port: int) -> bool:
        """Check if port is accessible."""
        try:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("localhost", port))
                return result == 0
        except Exception:
            return False

    def _check_health_endpoint(self, port: int) -> Dict:
        """Check health endpoint."""
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=5)

            if response.status_code == 200:
                return {"healthy": True, "details": "Health endpoint responding"}
            else:
                return {
                    "healthy": False,
                    "details": f"Health returned {response.status_code}",
                }

        except requests.exceptions.ConnectionError:
            return {"healthy": False, "details": "Health endpoint not available"}
        except requests.exceptions.Timeout:
            return {"healthy": False, "details": "Health endpoint timeout"}
        except Exception as e:
            return {"healthy": False, "details": f"Health error: {str(e)[:50]}..."}

    def _check_models_endpoint(self, port: int) -> Dict:
        """Check models endpoint."""
        try:
            response = requests.get(f"http://localhost:{port}/v1/models", timeout=10)

            if response.status_code == 200:
                try:
                    models_data = response.json()
                    if "data" in models_data and len(models_data["data"]) > 0:
                        count = len(models_data["data"])
                        return {"loaded": True, "details": f"{count} model(s) loaded"}
                    else:
                        return {"loaded": False, "details": "No models loaded yet"}
                except Exception:
                    return {"loaded": False, "details": "Models response parsing error"}
            else:
                return {
                    "loaded": False,
                    "details": f"Models endpoint returned {response.status_code}",
                }

        except requests.exceptions.ConnectionError:
            return {"loaded": False, "details": "Models endpoint not available"}
        except requests.exceptions.Timeout:
            return {
                "loaded": False,
                "details": "Models endpoint timeout (still loading)",
            }
        except Exception as e:
            return {"loaded": False, "details": f"Models error: {str(e)[:50]}..."}

    def _check_api_responsiveness(self, port: int) -> Dict:
        """Check API responsiveness with a simple test."""
        try:
            # Get model name first
            models_response = requests.get(
                f"http://localhost:{port}/v1/models", timeout=5
            )
            if models_response.status_code != 200:
                return {"responsive": False, "details": "Models endpoint not ready"}

            try:
                models_data = models_response.json()
                if "data" not in models_data or len(models_data["data"]) == 0:
                    return {"responsive": False, "details": "No models available"}

                model_name = models_data["data"][0]["id"]
            except Exception:
                model_name = "default"

            # Test completion endpoint
            test_payload = {
                "model": model_name,
                "prompt": "Hello",
                "max_tokens": 1,
                "temperature": 0.1,
            }

            response = requests.post(
                f"http://localhost:{port}/v1/completions",
                json=test_payload,
                timeout=15,
            )

            if response.status_code in [
                200,
                422,
            ]:  # 422 might be model issue but API works
                return {"responsive": True, "details": "API responding"}
            else:
                return {
                    "responsive": False,
                    "details": f"API returned {response.status_code}",
                }

        except requests.exceptions.ConnectionError:
            return {"responsive": False, "details": "API not available"}
        except requests.exceptions.Timeout:
            return {"responsive": False, "details": "API timeout (warming up)"}
        except Exception as e:
            return {"responsive": False, "details": f"API error: {str(e)[:50]}..."}
