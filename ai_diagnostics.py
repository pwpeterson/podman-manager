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
        self,
        target: str,
        lines: int = 50,
        vllm_url: str = "http://localhost:8002",
        verbose: bool = False,
    ) -> None:
        """AI-powered analysis of service logs for root causes and solutions"""
        if requests is None:
            console.print("[red]requests library not available for AI analysis[/red]")
            return

        # Determine if we're in quadlet or compose mode
        is_quadlet_mode = hasattr(self.manager, "_find_service_name")

        if is_quadlet_mode:
            # Quadlet mode - use journalctl
            self.manager._clear_auto_match_cache()
            service_name = self.manager._find_service_name(target)

            if not service_name:
                return

            console.print()
            console.print(
                f"[green]AI analyzing logs for {service_name} (last {lines} lines)...[/green]"
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
        else:
            # Compose mode - use podman logs
            project = self.manager._find_service_project(target)
            if not project:
                console.print(f"[red]Service '{target}' not found[/red]")
                return

            # Get the actual matched service name
            matched_service = self.manager.get_matched_service_name(target)
            service_name = matched_service

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

            console.print()
            console.print(
                f"[green]AI analyzing logs for {matched_service} (last {lines} lines)...[/green]"
            )

            # Get logs using podman logs
            cmd = ["podman", "logs", "--tail", str(lines), matched_service]

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
            if not self._check_vllm_availability(vllm_url, verbose):
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

    def _check_vllm_availability(self, vllm_url: str, verbose: bool = False) -> bool:
        """Check if vLLM proxy is available"""
        if requests is None:
            console.print("[red]requests library not available for health check[/red]")
            return False

        try:
            health_response = requests.get(f"{vllm_url}/health", timeout=5)
            if health_response.status_code != 200:
                if verbose:
                    console.print(f"[red]vLLM proxy not healthy at {vllm_url}[/red]")
                else:
                    console.print("[red]Cannot connect to your local vllm server[/red]")
                    console.print()
                    console.print(
                        "[green]Make sure vLLM proxy is running:[/green] [white]pm start vllm-proxy[/white]"
                    )
                    console.print()
                return False
            return True
        except requests.exceptions.RequestException as e:
            if verbose:
                console.print(
                    f"[red]Cannot connect to vLLM proxy at {vllm_url}: {e}[/red]"
                )
            else:
                console.print("[red]Cannot connect to your local vllm server[/red]")
            console.print()
            console.print(
                "[green]Make sure vLLM proxy is running:[/green] [white]pm start vllm-proxy[/white]"
            )
            console.print()
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

        from rich.progress import Progress, SpinnerColumn, TextColumn

        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]Analyzing logs with AI...[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("analyzing", total=None)

            try:
                api_response = requests.post(
                    f"{vllm_url}/v1/chat/completions",
                    json=api_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )

                progress.remove_task(task)

                if api_response.status_code != 200:
                    console.print(
                        f"[red]AI analysis failed: HTTP {api_response.status_code}[/red]"
                    )
                    console.print(f"[red]{api_response.text}[/red]")
                    return None

                response_data = api_response.json()
                return response_data["choices"][0]["message"]["content"]

            except requests.exceptions.Timeout:
                progress.remove_task(task)
                console.print("[red]AI analysis timed out (60s limit)[/red]")
                return None
            except requests.exceptions.RequestException as e:
                progress.remove_task(task)
                console.print(f"[red]AI analysis request failed: {e}[/red]")
                return None
            except json.JSONDecodeError as e:
                progress.remove_task(task)
                console.print(f"[red]Invalid JSON response from AI: {e}[/red]")
                return None
            except KeyError as e:
                progress.remove_task(task)
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

        # The spinner will be replaced with the header when it disappears (transient=True)
        console.print(f"[bold green]AI Log Analysis for {display_service}[/bold green]")
        console.print()  # Add newline after header
        # Manual markdown parsing and Rich formatting
        self._render_markdown_manually(ai_analysis)

        # Show follow-up commands with interactive menu
        self._show_ai_analysis_menu(display_service)

    def _render_markdown_manually(self, content: str) -> None:
        """Manually render markdown content using Rich formatting with 120 character width"""
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
                # Don't add blank lines before headers
                console.print(f"[bold cyan]{header_text}[/bold cyan]")
                previous_was_header = True
                continue
            else:
                previous_was_header = False

            # Handle bold text (**text**)
            line = re.sub(r"\*\*([^*]+)\*\*", r"[bold]\1[/bold]", line)

            # Handle inline code (`code`)
            line = re.sub(r"`([^`]+)`", r"[cyan]\1[/cyan]", line)

            # Handle code blocks (```)
            if line.startswith("```"):
                if line == "```text" or (line == "```" and not in_code_block):
                    # Skip these markdown code block markers
                    continue
                elif line == "```" and in_code_block:
                    # End of code block - skip the closing marker
                    in_code_block = False
                    continue
                elif (
                    "bash" in line
                    or "ini" in line
                    or any(lang in line for lang in ["python", "json", "yaml", "sh"])
                ):
                    # Start of code block - skip the opening marker
                    in_code_block = True
                    continue
                else:
                    # Unknown code block type - skip
                    continue

            # Handle content inside code blocks
            if in_code_block:
                # Indent code blocks and make them cyan
                console.print(f"    [cyan]{line}[/cyan]")
                continue

            # Handle numbered lists (1. item)
            if re.match(r"^\d+\.\s", line):
                # Wrap list items at 120 characters with proper indentation
                wrapped_lines = textwrap.fill(
                    line, width=116, initial_indent="    ", subsequent_indent="       "
                )
                console.print(f"[white]{wrapped_lines}[/white]")
                continue

            # Handle bullet points (- item)
            if line.startswith("- "):
                # Wrap bullet points at 120 characters with proper indentation
                wrapped_lines = textwrap.fill(
                    line,
                    width=112,
                    initial_indent="        ",
                    subsequent_indent="          ",
                )
                console.print(f"[white]{wrapped_lines}[/white]")
                continue

            # Handle code section markers like [Service]
            if line.startswith("[") and line.endswith("]") and len(line) < 20:
                # Indent code section markers
                console.print(f"        [dim cyan]{line}[/dim cyan]")
                continue

            # Handle environment variable assignments
            if line.startswith("Environment=") or "=" in line and "NEO4J_AUTH" in line:
                # Double indent environment variable lines
                console.print(f"            [cyan]{line}[/cyan]")
                continue

            # Handle command lines (sudo systemctl, etc.)
            if line.startswith("sudo ") or line.startswith("systemctl "):
                # Indent command lines as code
                console.print(f"            [cyan]{line}[/cyan]")
                continue

            # Regular text - wrap at 120 characters with indentation
            # Check if this looks like a log line (contains timestamp pattern)
            if re.match(r"^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", line):
                # Double indent log lines
                if len(line) > 112:  # Account for 8-space indent
                    wrapped_lines = textwrap.fill(
                        line,
                        width=112,
                        initial_indent="        ",
                        subsequent_indent="        ",
                    )
                    console.print(wrapped_lines)
                else:
                    console.print(f"        {line}")
            else:
                # Single indent regular text paragraphs
                if len(line) > 116:  # Account for 4-space indent
                    wrapped_lines = textwrap.fill(
                        line, width=116, initial_indent="    ", subsequent_indent="    "
                    )
                    console.print(wrapped_lines)
                else:
                    console.print(f"    {line}")

    def _show_ai_analysis_menu(self, display_service: str) -> None:
        """Show recommended actions after AI analysis"""
        console.print("\n  [bold green]Recommended actions:[/bold green]")
        console.print(
            f"[green]   View detailed logs:[/green] [white]pm logs {display_service}[/white]"
        )
        console.print(
            f"[green]    Monitor live logs:[/green] [white]pm logs {display_service} --f[/white]"
        )
        console.print(
            f"[green]   Diagnose the issue:[/green] [white]pm diagnose {display_service}[/white]"
        )
        console.print(
            f"[green]   Reset failed state:[/green] [white]pm reset-failed {display_service}[/white]"
        )
        console.print(
            f"[green]    Restart if needed:[/green] [white]pm restart {display_service}[/white]"
        )
        console.print(
            f"[green]   Re-run AI analysis:[/green] [white]pm logs {display_service} -ai[/white]"
        )
        console.print(
            f"[green]         Reinitialize:[/green] [white]pm reinit {display_service} -v[/white]"
        )
        console.print()
