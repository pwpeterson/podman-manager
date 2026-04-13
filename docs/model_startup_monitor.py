"""Model startup monitoring that handles different model types correctly.

Supports both vLLM and llama.cpp models with direct internal health checks:
- All models: Direct connection on port 8005 for startup verification
- Proxy services start AFTER model is confirmed ready
"""

import time
from typing import Dict

import requests
from rich.progress import Progress, SpinnerColumn, TextColumn

from core.config import console


class ModelStartupMonitor:
    """Model startup monitoring with direct internal health checks on port 8005."""

    def __init__(self, manager):
        self.manager = manager
        self.model_configs = self._load_model_configs()
        self.direct_model_port = 8005  # All models use port 8005 internally

    def _load_model_configs(self) -> Dict[str, Dict]:
        """Load model configurations.

        Legacy behavior loaded model metadata from a local agent config file. That approach
        has been removed in favor of abacus-proxy, so we avoid any file-based configuration
        here and infer model type from container naming conventions.
        """
        return {}

    def _detect_model_type(self, model_name: str) -> str:
        """Detect if model is vLLM or llama.cpp based on name."""
        if model_name.startswith("llama-"):
            return "llama.cpp"
        elif model_name.startswith("vllm-"):
            return "vllm"
        else:
            return "unknown"

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
        if container_name.startswith("llama-"):
            return {
                "model_type": "llama.cpp",
                "description": "llama.cpp model",
            }
        elif container_name.startswith("vllm-"):
            return {
                "model_type": "vllm",
                "description": "vLLM model",
            }
        else:
            return {
                "model_type": "unknown",
                "description": "Unknown model type",
            }

    def monitor_model_startup(self, container_name: str, timeout: int = 300) -> bool:
        """Monitor model startup with direct internal health checks on port 8005."""
        model_config = self.get_model_config(container_name)
        model_type = model_config["model_type"]

        console.print(f"  🔍 Monitoring {container_name} startup...")
        console.print(
            f"  Model type: {model_type}, Direct port: {self.direct_model_port}"
        )
        console.print(
            f"  Waiting for {container_name} to be ready on port {self.direct_model_port}..."
        )

        # All models use the same direct monitoring approach on port 8005
        return self._monitor_model_direct(container_name, model_type, timeout)

    def _monitor_model_direct(
        self, container_name: str, model_type: str, timeout: int
    ) -> bool:
        """Monitor model startup with direct internal health checks on port 8005."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("startup", total=None)

            start_time = time.time()
            consecutive_failures = 0
            # Allow up to 90 consecutive error checks (~180s) before giving up.
            # vLLM services can briefly show "error" status during early startup
            # while the container image is being pulled / GPU memory is allocated.
            # Large models (e.g. Gemma-4-31B) can take 3+ minutes to fully start.
            max_failures = 90
            # Don't declare failure until at least this many seconds have elapsed,
            # so transient early-startup errors are ignored.
            # 180s = 3 minutes matches observed vLLM startup time.
            min_elapsed_before_fail = 180

            while time.time() - start_time < timeout:
                elapsed = time.time() - start_time

                # Stage 1: Check container status first
                container_status = self._get_container_status(container_name)
                if container_status in ["error", "exited", "dead"]:
                    consecutive_failures += 1
                    if (
                        consecutive_failures >= max_failures
                        and elapsed >= min_elapsed_before_fail
                    ):
                        console.print(
                            f"  ❌ {container_name} container failed to start (status: {container_status})"
                        )
                        console.print(
                            f"  💡 {model_type} model startup failed - check container logs"
                        )
                        console.print(
                            f"     Try: journalctl --user -u {container_name}.service -n 20"
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

                # Stage 2: Check if port 8005 is accessible
                if not self._is_port_accessible(self.direct_model_port):
                    progress.update(
                        task,
                        description=f"[yellow]Port {self.direct_model_port} not ready - {elapsed:.1f}s[/yellow]",
                    )
                    time.sleep(2.0)
                    continue

                # Stage 3: Check health endpoint on port 8005
                health_status = self._check_health_endpoint_direct()
                if not health_status["healthy"]:
                    progress.update(
                        task,
                        description=f"[yellow]Health check: {health_status['details']} - {elapsed:.1f}s[/yellow]",
                    )
                    time.sleep(2.0)
                    continue

                # Stage 4: Check models endpoint on port 8005
                models_status = self._check_models_endpoint_direct()
                if not models_status["loaded"]:
                    progress.update(
                        task,
                        description=f"[yellow]Loading models: {models_status['details']} - {elapsed:.1f}s[/yellow]",
                    )
                    time.sleep(3.0)  # Longer wait for model loading
                    continue

                # Stage 5: Final API responsiveness test on port 8005
                api_status = self._check_api_responsiveness_direct()
                if not api_status["responsive"]:
                    progress.update(
                        task,
                        description=f"[yellow]API warming up: {api_status['details']} - {elapsed:.1f}s[/yellow]",
                    )
                    time.sleep(2.0)
                    continue

                # All checks passed
                console.print(
                    f"  ✅ {container_name} ({model_type}) is fully ready in {elapsed:.1f}s"
                )
                return True

            # Timeout
            console.print(f"  ⏰ Timeout waiting for {container_name} ({timeout}s)")
            console.print(f"  ❌ {container_name} failed to become ready")
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
                result = s.connect_ex(("127.0.0.1", port))
                return result == 0
        except Exception:
            return False

    def _check_health_endpoint_direct(self) -> Dict:
        """Check health endpoint directly on port 8005."""
        try:
            response = requests.get(
                f"http://127.0.0.1:{self.direct_model_port}/health", timeout=5
            )

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

    def _check_models_endpoint_direct(self) -> Dict:
        """Check models endpoint directly on port 8005."""
        try:
            response = requests.get(
                f"http://127.0.0.1:{self.direct_model_port}/v1/models", timeout=10
            )

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

    def _check_api_responsiveness_direct(self) -> Dict:
        """Check API responsiveness with a simple test directly on port 8005."""
        try:
            # Get model name first
            models_response = requests.get(
                f"http://127.0.0.1:{self.direct_model_port}/v1/models", timeout=5
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
                f"http://127.0.0.1:{self.direct_model_port}/v1/completions",
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
