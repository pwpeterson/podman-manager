"""AI-powered diagnostics and log analysis operations."""

import json
import subprocess
from datetime import datetime
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

from config import console


class AIDiagnostics:
    """Handles AI-powered log analysis and diagnostics"""

    def __init__(self, manager):
        self.manager = manager

    def ai_analyze_logs(
        self, target: str, lines: int = 50, vllm_url: str = "http://localhost:8002"
    ) -> None:
        """AI-powered analysis of service logs for root causes and solutions"""
        if requests is None:
            console.print("[red]requests library not available for AI analysis[/red]")
            return

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
            if not self._check_vllm_availability(vllm_url):
                return

            # Prepare AI analysis prompt
            analysis_prompt = self._prepare_analysis_prompt(
                service_name, log_content, lines
            )

            # Call vLLM API
            ai_analysis = self._call_vllm_api(vllm_url, analysis_prompt)
            if ai_analysis is None:
                return

            # Display results
            self._display_ai_analysis_results(target, service_name, ai_analysis)

        except subprocess.TimeoutExpired:
            console.print("[red]Timeout while fetching logs[/red]")
        except Exception as e:
            console.print(f"[red]Error in AI log analysis: {e}[/red]")

    def _check_vllm_availability(self, vllm_url: str) -> bool:
        """Check if vLLM proxy is available"""
        if requests is None:
            console.print("[red]requests library not available for health check[/red]")
            return False

        try:
            health_response = requests.get(f"{vllm_url}/health", timeout=5)
            if health_response.status_code != 200:
                console.print(f"[red]vLLM proxy not healthy at {vllm_url}[/red]")
                return False
            return True
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Cannot connect to vLLM proxy at {vllm_url}: {e}[/red]")
            console.print(
                "[dim]Make sure vLLM proxy is running: pm start vllm-proxy[/dim]"
            )
            return False

    def _prepare_analysis_prompt(
        self, service_name: str, log_content: str, lines: int
    ) -> str:
        """Prepare the AI analysis prompt"""
        return f"""You are an expert system administrator and DevOps engineer. Analyze the following systemd service logs and provide:

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

    def _call_vllm_api(self, vllm_url: str, analysis_prompt: str) -> Optional[str]:
        """Call vLLM API for analysis"""
        if requests is None:
            console.print("[red]requests library not available for API calls[/red]")
            return None

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
                return None

            response_data = api_response.json()
            return response_data["choices"][0]["message"]["content"]

        except requests.exceptions.Timeout:
            console.print("[red]AI analysis timed out (60s limit)[/red]")
            return None
        except requests.exceptions.RequestException as e:
            console.print(f"[red]AI analysis request failed: {e}[/red]")
            return None
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON response from AI: {e}[/red]")
            return None
        except KeyError as e:
            console.print(f"[red]Unexpected AI response format: {e}[/red]")
            return None

    def _display_ai_analysis_results(
        self, target: str, service_name: str, ai_analysis: str
    ) -> None:
        """Display AI analysis results and interactive menu"""
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
        self._show_ai_analysis_menu(display_service)

    def _show_ai_analysis_menu(self, display_service: str) -> None:
        """Show interactive menu after AI analysis"""
        console.print("\n[bold cyan]Follow-up Commands:[/bold cyan]")
        console.print(f"[cyan]1[/cyan]  pm logs {display_service:<20}\t\t# View logs")
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
            choice = input("\nSelect command (1-5) or press Enter to skip: ").strip()
            if choice and choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= 5:
                    # Initialize cmd variable
                    cmd = ["python", "podman_manager.py"]

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
                    console.print("[yellow]Invalid choice. Please select 1-5[/yellow]")
            elif choice:
                console.print("[yellow]Invalid choice. Please select 1-5[/yellow]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Command selection cancelled[/yellow]")
        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")
