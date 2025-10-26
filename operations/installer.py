"""Quadlet Stack Installation Module

Refactored installer for quadlet stacks with improved separation of concerns.
"""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from rich.table import Table

if TYPE_CHECKING:
    import requests
else:
    try:
        import requests
    except ImportError:
        requests = None

from core.config import console, is_verbose, verbose_print
from core.fuzzy_matcher import FuzzyMatcher


class EnvironmentManager:
    """Handles environment file processing and system environment setup."""

    def __init__(self):
        self.env_file_path = Path("/home/pwp/srv/local-ai-packaged/.env")
        self.system_env_target = Path.home() / ".config/containers/systemd/.env"

    def load_and_clean_env_file(self) -> bool:
        """Copy .env file directly to systemd containers directory."""
        if not self.env_file_path.exists():
            self._print_warning(f"Environment file not found: {self.env_file_path}")
            return False

        console.print()
        self._print_success("Copying .env file to systemd containers directory.")
        if not is_verbose():
            console.print()
        verbose_print(
            "  [cyan]exec: Copy .env file to ~/.config/containers/systemd/[/cyan]"
        )

        return self._copy_env_file_directly()

    def _copy_env_file_directly(self) -> bool:
        """Copy .env file directly to systemd containers directory."""
        try:
            # Create the systemd directory if it doesn't exist
            self.system_env_target.parent.mkdir(parents=True, exist_ok=True)

            # Copy the .env file directly to systemd containers directory (no sudo needed!)
            import shutil

            shutil.copy2(self.env_file_path, self.system_env_target)

            # Set appropriate permissions
            self.system_env_target.chmod(0o644)

            verbose_print(
                f"  [cyan]exec: Copied {self.env_file_path} to {self.system_env_target}[/cyan]"
            )

            if self.system_env_target.exists():
                return True
            else:
                self._print_error(
                    f"Failed to create {self.system_env_target} - file does not exist after creation"
                )
                return False

        except Exception as e:
            self._print_error(f"Failed to copy environment file: {e}")
            return False

    def _print_success(self, message: str) -> None:
        console.print(f"[green]{message}[/green]")

    def _print_warning(self, message: str) -> None:
        console.print(f"[yellow]{message}[/yellow]")

    def _print_error(self, message: str) -> None:
        console.print(f"[red]{message}[/red]")


class SystemdManager:
    """Handles systemd operations and service management."""

    def check_user_session(self) -> bool:
        """Check systemd user session health."""
        console.print("[green]Checking systemd user session health...[/green]")

        try:
            # Check if systemd user session is running
            cmd = ["systemctl", "--user", "status"]
            verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                console.print(
                    "[yellow]Systemd user session appears to be disconnected[/yellow]"
                )
                console.print("[blue]This may cause daemon-reload to fail[/blue]")
                console.print(
                    "[blue]Consider restarting your user session if issues persist[/blue]"
                )
                return False

            # Check if we can communicate with systemd
            cmd = [
                "systemctl",
                "--user",
                "list-units",
                "--type=service",
                "--state=loaded",
            ]
            verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                console.print(
                    "[yellow]Cannot communicate with systemd user session[/yellow]"
                )
                console.print("[blue]Transport endpoint may be disconnected[/blue]")
                return False

            console.print()
            console.print("[green]Systemd user session is healthy[/green]")
            return True

        except subprocess.TimeoutExpired:
            console.print("[yellow]Systemd health check timed out[/yellow]")
            return False
        except Exception as e:
            console.print(f"[yellow]Systemd health check failed: {e}[/yellow]")
            return False

    def reload_daemon(self, use_sudo: bool = False) -> bool:
        """Reload systemd daemon."""
        console.print("[green]Reloading systemd daemon...[/green]")
        if not is_verbose():
            console.print()

        if use_sudo:
            return self._reload_system_daemon()
        else:
            return self._reload_user_daemon()

    def _reload_system_daemon(self) -> bool:
        """Reload system daemon with sudo."""
        cmd = ["sudo", "systemctl", "daemon-reload"]
        verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(
                "[red]Failed to reload system daemon. You may need to manually run: sudo systemctl daemon-reload[/red]"
            )
            return False
        return True

    def _reload_user_daemon(self) -> bool:
        """Reload user daemon with retry logic."""
        cmd = ["systemctl", "--user", "daemon-reload"]
        verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(
                "[yellow]Failed to reload user daemon (systemd connection issue)[/yellow]"
            )
            console.print("[blue]Attempting to restart user systemd session...[/blue]")
            return self._retry_user_daemon_reload()
        return True

    def _retry_user_daemon_reload(self) -> bool:
        """Retry user daemon reload after resetting failed units."""
        reset_cmd = ["systemctl", "--user", "reset-failed"]
        verbose_print(f"  [cyan]exec: {' '.join(reset_cmd)}[/cyan]")
        reset_result = subprocess.run(reset_cmd, capture_output=True, text=True)

        if reset_result.returncode == 0:
            console.print("[blue]Reset failed units, retrying daemon-reload...[/blue]")
            retry_cmd = ["systemctl", "--user", "daemon-reload"]
            verbose_print(f"  [cyan]exec: {' '.join(retry_cmd)}[/cyan]")
            retry_result = subprocess.run(retry_cmd, capture_output=True, text=True)

            if retry_result.returncode == 0:
                console.print("[green]Successfully reloaded daemon after reset[/green]")
                return True
            else:
                self._show_manual_reload_instructions()
                return False
        else:
            console.print("[yellow]Could not reset systemd user session[/yellow]")
            self._show_manual_reload_instructions()
            return False

    def _show_manual_reload_instructions(self):
        """Show manual daemon reload instructions."""
        console.print(
            "[yellow]Daemon reload still failing. Manual intervention may be required.[/yellow]"
        )
        console.print("[blue]Try: systemctl --user daemon-reload[/blue]")
        console.print(
            f"[blue]Or restart user session: loginctl terminate-user {os.getenv('USER')}[/blue]"
        )


class ValidationManager:
    """Handles container file validation using podman-quadlet after deployment."""

    def __init__(self):
        self.quadlet_generator = "/usr/lib/systemd/user-generators/podman-quadlet"

    def validate_after_deployment(
        self, stack_name: str, files: List[str], use_sudo: bool = False
    ) -> bool:
        """Validate container files by running podman-quadlet and checking journalctl."""
        container_files = [f for f in files if f.endswith(".container")]

        if not container_files:
            return True

        if not Path(self.quadlet_generator).exists():
            console.print(
                "[yellow]Warning: podman-quadlet not found, skipping validation[/yellow]"
            )
            return True

        console.print("[green]Validating installed quadlet containers...[/green]")
        console.print()

        # Run podman-quadlet and check for container-specific errors
        success, container_errors = self._run_quadlet_generator_and_check_errors(
            container_files, use_sudo
        )

        if container_errors:
            console.print()
            console.print("[red]Validation errors found:[/red]")
            for error in container_errors:
                console.print(f"  {error}")
            return False
        else:
            return True

    def _run_quadlet_generator_and_check_errors(
        self, container_files: List[str], use_sudo: bool
    ) -> Tuple[bool, List[str]]:
        """Run podman-quadlet generator with grep filtering for specific container errors."""
        container_errors = []

        for container_file in container_files:

            # Build command with grep filtering
            quadlet_cmd = [self.quadlet_generator, "--user", "--dryrun"]
            if use_sudo:
                quadlet_cmd = [self.quadlet_generator, "--dryrun"]

            grep_cmd = ["grep", container_file]
            full_cmd = " | ".join([" ".join(quadlet_cmd), " ".join(grep_cmd)])

            verbose_print(f"  [cyan]exec: {full_cmd}[/cyan]")

            try:
                # Run podman-quadlet and pipe to grep
                quadlet_process = subprocess.Popen(
                    quadlet_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                grep_process = subprocess.Popen(
                    grep_cmd,
                    stdin=quadlet_process.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                if quadlet_process.stdout:
                    quadlet_process.stdout.close()
                grep_output, grep_error = grep_process.communicate(timeout=30)
                quadlet_process.wait()

                if grep_output.strip():
                    # Parse and format the errors
                    formatted_errors = self._format_quadlet_errors(
                        grep_output.strip(), container_file
                    )
                    container_errors.extend(formatted_errors)

            except subprocess.TimeoutExpired:
                console.print(
                    "[yellow]Quadlet validation timed out, assuming validation passed[/yellow]"
                )
            except Exception as e:
                console.print(
                    f"[yellow]Quadlet validation error: {e}, assuming validation passed[/yellow]"
                )

        return True, container_errors

    def _format_quadlet_errors(
        self, grep_output: str, container_file: str
    ) -> List[str]:
        """Format quadlet error messages for clean display."""
        formatted_errors = []
        lines = grep_output.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Parse typical quadlet error format:
            # quadlet-generator[2696881]: converting "local-ai-caddy-dav.container": unsupported key 'Env' in group 'Container' in /path/file
            if "unsupported key" in line.lower():
                # Extract the key and format cleanly
                import re

                match = re.search(
                    r"unsupported key '([^']+)' in group '([^']+)'", line, re.IGNORECASE
                )
                if match:
                    key = match.group(1)
                    group = match.group(2)
                    formatted_errors.append(
                        f"[red]Unsupported key '{key}' in group '{group}' in {container_file}[/red]"
                    )
                else:
                    # Fallback to original line if parsing fails
                    formatted_errors.append(f"[red]{line}[/red]")
            elif any(
                keyword in line.lower()
                for keyword in ["error", "invalid", "failed", "cannot", "missing"]
            ):
                # Format other error types
                formatted_errors.append(f"[red]{line}[/red]")

        return formatted_errors

    def _filter_quadlet_output_for_containers(
        self, quadlet_output: str, container_files: List[str]
    ) -> List[str]:
        """Filter podman-quadlet output for errors related to specific container files."""
        lines = quadlet_output.strip().split("\n")
        container_errors = []

        # Create patterns to match our container files
        container_patterns = []
        for container_file in container_files:
            # Match both the full filename and the service name
            container_name = container_file.replace(".container", "")
            container_patterns.extend([container_file, container_name])

        # Keywords that indicate validation errors
        error_keywords = [
            "error",
            "failed",
            "invalid",
            "unsupported",
            "cannot",
            "unable",
            "missing",
            "bad",
            "wrong",
            "illegal",
            "denied",
            "unknown",
        ]

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            line_lower = line_stripped.lower()

            # Check if line contains error keywords
            has_error_keyword = any(
                error_word in line_lower for error_word in error_keywords
            )

            # Check if line mentions our container files
            mentions_our_containers = any(
                pattern.lower() in line_lower for pattern in container_patterns
            )

            # Include line if it has error keywords and mentions our containers
            if has_error_keyword and mentions_our_containers:
                container_errors.append(line_stripped)

        return container_errors

    def _check_journalctl_for_errors(
        self, container_files: List[str], use_sudo: bool
    ) -> bool:
        """Check journalctl for quadlet-related errors."""
        journal_cmd = ["journalctl", "-b", "--grep=quadlet", "-o", "cat", "--no-pager"]
        if not use_sudo:
            journal_cmd.insert(1, "--user")

        verbose_print(f"  [cyan]exec: {' '.join(journal_cmd)}[/cyan]")

        try:
            result = subprocess.run(
                journal_cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Filter and analyze journal output for relevant errors
                relevant_errors = self._filter_relevant_quadlet_errors(
                    result.stdout, container_files
                )

                if relevant_errors:
                    console.print("[red]✗ Validation errors found[/red]")
                    console.print("[yellow]Relevant quadlet errors:[/yellow]")
                    for error in relevant_errors:
                        console.print(f"  [dim]{error}[/dim]")
                    console.print(
                        "[yellow]Run 'journalctl --user -b | grep -i quadlet' for full details[/yellow]"
                    )
                    return False
                else:
                    console.print(
                        "[green]✓ No validation errors found in journal[/green]"
                    )
                    return True
            else:
                console.print("[green]✓ No quadlet errors in journal[/green]")
                return True

        except subprocess.TimeoutExpired:
            console.print(
                "[yellow]Journal check timed out, assuming validation passed[/yellow]"
            )
            return True
        except Exception as e:
            console.print(
                f"[yellow]Journal check error: {e}, assuming validation passed[/yellow]"
            )
            return True

    def _filter_relevant_quadlet_errors(
        self, journal_output: str, container_files: List[str]
    ) -> List[str]:
        """Filter journal output to show only relevant quadlet errors for our container files."""
        lines = journal_output.strip().split("\n")
        relevant_errors = []
        container_names = [f.replace(".container", "") for f in container_files]

        # Keywords that indicate actual errors (not just info/debug messages)
        error_keywords = [
            "error",
            "failed",
            "invalid",
            "cannot",
            "unable",
            "missing",
            "bad",
            "wrong",
            "illegal",
            "unsupported",
            "denied",
        ]

        # Keywords to filter out (informational/debug messages)
        ignore_keywords = [
            "debug",
            "info",
            "starting",
            "stopping",
            "created",
            "removed",
            "pulled",
            "tagged",
            "loaded successfully",
        ]

        for line in lines:
            line_lower = line.lower()

            # Skip empty lines
            if not line.strip():
                continue

            # Skip lines that are just informational
            if any(ignore_word in line_lower for ignore_word in ignore_keywords):
                continue

            # Check if line contains error keywords
            has_error_keyword = any(
                error_word in line_lower for error_word in error_keywords
            )

            # Check if line mentions our container files
            mentions_our_containers = any(
                container_name in line_lower for container_name in container_names
            )

            # Include line if it has error keywords and either:
            # 1. Mentions our containers specifically, or
            # 2. Is a general quadlet error that could affect our containers
            if has_error_keyword and (
                mentions_our_containers or "quadlet" in line_lower
            ):
                relevant_errors.append(line.strip())

        # Limit to most recent/relevant errors (max 10)
        return relevant_errors[-10:] if relevant_errors else []

    def validate_with_ai_troubleshooting(
        self, stack_name: str, files: List[str], use_sudo: bool = False
    ) -> bool:
        """Validate container files and automatically run AI analysis if errors are found.

        Returns False and ends installation if validation errors occur.
        """
        # First run normal validation
        validation_success = self.validate_after_deployment(stack_name, files, use_sudo)

        # If validation failed, automatically run AI analysis and end installation
        if not validation_success:
            verbose_print("  [cyan]exec: ai_analyze_validation_errors()[/cyan]")
            self.ai_analyze_validation_errors(stack_name, files)
            console.print("[red]Installation stopped due to validation errors[/red]")
            console.print()
            return False

        return validation_success

    def ai_analyze_validation_errors(
        self, stack_name: str, files: List[str], use_sudo: bool = False
    ) -> None:
        """Analyze validation errors using AI and provide troubleshooting suggestions."""
        if not requests:
            console.print(
                "[red]Error: requests library not available for AI analysis[/red]"
            )
            return

        from rich.progress import Progress, SpinnerColumn, TextColumn

        # Collect validation errors
        container_files = [f for f in files if f.endswith(".container")]
        if not container_files:
            console.print("[yellow]No container files to analyze[/yellow]")
            return

        # Get quadlet errors
        quadlet_errors = self._collect_quadlet_errors(container_files, use_sudo)

        if not quadlet_errors:
            console.print("[green]No validation errors found to analyze[/green]")
            return

        # Show spinner while analyzing
        with Progress(
            SpinnerColumn(),
            TextColumn("[green]Running AI analysis of validation errors...[/green]"),
            console=console,
            transient=False,  # Keep visible after completion
        ) as progress:
            task = progress.add_task("analyzing", total=None)

            # Analyze with AI
            analysis = self._get_ai_analysis(
                quadlet_errors, stack_name, container_files
            )

            progress.remove_task(task)

        console.print()

        if analysis:
            self._display_ai_analysis(analysis, stack_name, container_files)
        else:
            console.print(
                "[yellow]AI analysis unavailable (vLLM service may be down)[/yellow]"
            )

    def _collect_quadlet_errors(
        self, container_files: List[str], use_sudo: bool
    ) -> str:
        """Collect quadlet validation errors for AI analysis."""
        all_errors = []

        for container_file in container_files:
            # Build command with grep filtering
            quadlet_cmd = [self.quadlet_generator, "--user", "--dryrun"]
            if use_sudo:
                quadlet_cmd = [self.quadlet_generator, "--dryrun"]

            grep_cmd = ["grep", container_file]

            try:
                # Run podman-quadlet and pipe to grep
                quadlet_process = subprocess.Popen(
                    quadlet_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                grep_process = subprocess.Popen(
                    grep_cmd,
                    stdin=quadlet_process.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                if quadlet_process.stdout:
                    quadlet_process.stdout.close()
                grep_output, _ = grep_process.communicate(timeout=30)
                quadlet_process.wait()

                if grep_output.strip():
                    all_errors.append(f"=== {container_file} ===")
                    all_errors.append(grep_output.strip())
                    all_errors.append("")

            except (subprocess.TimeoutExpired, Exception) as e:
                all_errors.append(f"Error analyzing {container_file}: {e}")

        return "\n".join(all_errors)

    def _get_ai_analysis(
        self, errors: str, stack_name: str, container_files: List[str]
    ) -> Optional[str]:
        """Get AI analysis of validation errors from local vLLM."""
        if requests is None:
            verbose_print("  [cyan]exec: requests library not available[/cyan]")
            return None

        verbose_print(
            "  [cyan]exec: Checking vLLM health at curl -X GET http://localhost:8002/health[/cyan]"
        )
        try:
            # Check if vLLM is available
            health_response = requests.get("http://localhost:8002/health", timeout=5)
            verbose_print(
                f"  [cyan]exec: Health check response: status={health_response.status_code}[/cyan]"
            )
            if health_response.status_code != 200:
                verbose_print(
                    f"  [cyan]exec: Health check failed with status {health_response.status_code}[/cyan]"
                )
                return None
            verbose_print("  [cyan]exec: vLLM health check passed[/cyan]")

        except requests.RequestException as e:
            verbose_print(f"  [cyan]exec: Health check request failed: {e}[/cyan]")
            return None

        # Prepare the analysis prompt
        prompt = self._build_analysis_prompt(errors, stack_name, container_files)

        verbose_print(
            "  [cyan]exec: Sending AI analysis request to curl -X POST http://localhost:8002/v1/chat/completions \\[/cyan]"
        )
        verbose_print("  [cyan]    -H 'Content-Type: application/json' \\[/cyan]")
        verbose_print("  [cyan]    -d '{[/cyan]")
        verbose_print(
            '  [cyan]      "model": "vllm-qwen25-coder-32b-instruct-awq",[/cyan]'
        )
        verbose_print('  [cyan]      "messages": [{{[/cyan]')
        verbose_print('  [cyan]        "role": "user",[/cyan]')
        verbose_print('  [cyan]        "content": "[/cyan]')

        # Display content with proper line breaks
        content_lines = prompt.replace("\\n\\n", "\n").split("\n")
        for line in content_lines:
            if line.strip():
                verbose_print(f"  [cyan]          {line.strip()}[/cyan]")
            else:
                verbose_print("  [cyan][/cyan]")

        verbose_print('  [cyan]        "[/cyan]')
        verbose_print("  [cyan]      }}],[/cyan]")
        verbose_print('  [cyan]      "max_tokens": 1000,[/cyan]')
        verbose_print('  [cyan]      "temperature": 0.1[/cyan]')
        verbose_print("  [cyan]    }'[/cyan]")
        try:
            response = requests.post(
                "http://localhost:8002/v1/chat/completions",
                json={
                    "model": "vllm-qwen25-coder-32b-instruct-awq",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.1,
                    "stop": ["\n\n---", "\n\nUser:", "\n\nHuman:"],
                },
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            verbose_print(
                f"  [cyan]exec: AI analysis response: status={response.status_code}[/cyan]"
            )
            if response.status_code == 200:
                result = response.json()
                verbose_print(
                    f"  [cyan]exec: Response JSON keys: {list(result.keys()) if result else 'None'}[/cyan]"
                )
                if "choices" in result and len(result["choices"]) > 0:
                    verbose_print(
                        "  [cyan]exec: AI analysis successful, returning response[/cyan]"
                    )
                    # Handle both completions and chat completions response formats
                    choice = result["choices"][0]
                    if "message" in choice:
                        return choice["message"]["content"].strip()
                    elif "text" in choice:
                        return choice["text"].strip()
                else:
                    verbose_print(
                        "  [cyan]exec: No choices in response or empty choices[/cyan]"
                    )
            else:
                verbose_print(
                    f"  [cyan]exec: AI analysis request failed with status {response.status_code}[/cyan]"
                )
                verbose_print(
                    f"  [cyan]exec: Response text: {response.text[:200]}...[/cyan]"
                )

        except requests.RequestException as e:
            verbose_print(f"  [cyan]exec: AI analysis request failed: {e}[/cyan]")

        return None

    def _build_analysis_prompt(
        self, errors: str, stack_name: str, container_files: List[str]
    ) -> str:
        """Build the analysis prompt for the AI model."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""You are a system administration expert specializing in Podman Quadlet troubleshooting.

Analyze the following quadlet validation errors and provide a brief cause/resolution report:

Stack: {stack_name}
Container Files: {', '.join(container_files)}
Timestamp: {timestamp}

Validation Errors:
{errors}

Provide a concise analysis with:
1. Root cause of each error
2. Specific resolution steps
3. Provide a list of valid optional values for the correct parameter. Indicate which optional value is recommended.
4. Prevention recommendations

Keep the response brief and actionable."""

    def _display_ai_analysis(
        self, analysis: str, stack_name: str, container_files: List[str]
    ) -> None:
        """Display AI analysis results with rich formatting."""
        # Use the same formatting as ai_diagnostics.py for consistency
        console.print("[bold green]AI Validation Analysis[/bold green]")
        console.print()  # Add newline after header
        # Manual markdown parsing and Rich formatting
        self._render_markdown_manually(analysis)

        # Show follow-up commands with interactive menu
        self._show_ai_analysis_menu(stack_name, container_files)

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

    def _show_ai_analysis_menu(
        self, stack_name: str, container_files: List[str]
    ) -> None:
        """Show recommended actions after AI analysis"""
        # Use the first container file or fallback to stack name
        container_file = (
            container_files[0] if container_files else f"{stack_name}.container"
        )

        console.print("\n      [bold green]Recommended actions:[/bold green]")
        console.print(
            f"[green]    Fix validation errors:[/green] [white]Edit the source {container_file}[/white]"
        )
        console.print(
            f"[green]       Retry installation:[/green] [white]pm install {container_file} -v[/white]"
        )
        console.print(
            f"[green]     Check quadlet syntax:[/green] [white]podman-quadlet --user --dryrun | grep {container_file}[/white]"
        )
        console.print(
            "[green]View installed containers:[/green] [white]ls ~/.config/containers/systemd/[/white]"
        )
        console.print()


class FileManager:
    """Handles file operations during installation."""

    def create_target_directory(self, target_dir: Path, use_sudo: bool = False):
        """Create target directory with appropriate permissions."""
        if use_sudo:
            cmd = ["sudo", "mkdir", "-p", str(target_dir)]
            subprocess.run(cmd, check=True)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)

    def copy_quadlet_files(
        self,
        files: List[str],
        stack_dir: Path,
        target_dir: Path,
        use_sudo: bool = False,
    ):
        """Copy quadlet files to target directory."""
        # Show mkdir command once at the beginning
        console.print("[green]Creating the required system directory[/green]")
        verbose_print("  [cyan]exec: mkdir -p .../systemd[/cyan]")
        if not is_verbose():
            console.print()

        # Group files by type for better organization
        container_files = [f for f in files if f.endswith(".container")]
        network_files = [f for f in files if f.endswith(".network")]
        volume_files = [f for f in files if f.endswith(".volume")]
        other_files = [
            f
            for f in files
            if not any(f.endswith(ext) for ext in [".container", ".network", ".volume"])
        ]

        # Check for network dependencies in container files and show message if networks will be processed
        network_dependencies = self._get_network_dependencies_from_containers(
            stack_dir, container_files
        )
        if network_files or network_dependencies:
            if network_files:
                console.print("[green]Copying share networks to systemd[/green]")
                if not is_verbose():
                    console.print()
            if network_dependencies and not network_files:
                console.print(
                    "[green]Network dependencies detected in container files[/green]"
                )
                if not is_verbose():
                    console.print()

        # Process files in order: networks first (volumes may depend on them), then containers, volumes, others
        all_files_ordered = network_files + container_files + volume_files + other_files

        for file in all_files_ordered:
            if file.endswith(".container"):
                service_name = file.replace(".container", "")
                console.print(
                    f"[green]Copying & validating master {service_name} .container to systemd[/green]"
                )
                if not is_verbose():
                    console.print()
            elif file.endswith(".network"):
                # Network files are processed but message is shown once at the beginning
                pass
            elif file.endswith(".volume"):
                service_name = self._extract_service_name_from_file(file)
                console.print(
                    f"[green]Copying {service_name} volumes & shared networks to systemd[/green]"
                )
                if not is_verbose():
                    console.print()
            else:
                console.print(f"[green]Copying {file} to systemd[/green]")
                if not is_verbose():
                    console.print()

            # Determine source file location - shared network files are in root directory
            if file.endswith(".network") and not (stack_dir / file).exists():
                # This is a shared network file in the root quadlets directory
                source_file = stack_dir.parent / file
            else:
                # Regular file in the stack directory
                source_file = stack_dir / file

            target_file = target_dir / file

            # Copy the file
            if use_sudo:
                cmd = ["sudo", "cp", str(source_file), str(target_file)]
                verbose_print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                subprocess.run(cmd, check=True)
            else:
                verbose_print(f"  [cyan]exec: cp .../{file} .../systemd/{file}[/cyan]")
                shutil.copy2(source_file, target_file)

            # Set permissions immediately after copying
            if use_sudo:
                chmod_cmd = ["sudo", "chmod", "644", str(target_file)]
                verbose_print(f"  [cyan]exec: chmod 644 .../systemd/{file}[/cyan]")
                subprocess.run(chmod_cmd, check=True)
            else:
                verbose_print(f"  [cyan]exec: chmod 644 .../systemd/{file}[/cyan]")
                target_file.chmod(0o644)

            # Run validation immediately after each container file
            if file.endswith(".container"):
                self._validate_single_container_file(file, use_sudo)

    def _validate_single_container_file(
        self, container_file: str, use_sudo: bool = False
    ):
        """Validate a single container file immediately after copying."""
        quadlet_generator = "/usr/lib/systemd/user-generators/podman-quadlet"

        if not Path(quadlet_generator).exists():
            return

        # Build command with grep filtering
        quadlet_cmd = [quadlet_generator, "--user", "--dryrun"]
        if use_sudo:
            quadlet_cmd = [quadlet_generator, "--dryrun"]

        grep_cmd = ["grep", container_file]
        full_cmd = " | ".join([" ".join(quadlet_cmd), " ".join(grep_cmd)])

        verbose_print(f"  [cyan]exec: {full_cmd}[/cyan]")

        try:
            # Run podman-quadlet and pipe to grep
            quadlet_process = subprocess.Popen(
                quadlet_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            grep_process = subprocess.Popen(
                grep_cmd,
                stdin=quadlet_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if quadlet_process.stdout:
                quadlet_process.stdout.close()
            grep_output, _ = grep_process.communicate(timeout=30)
            quadlet_process.wait()

            # Only show errors if there are any
            if grep_output.strip():
                # Check if it's actually an error or just informational
                if any(
                    keyword in grep_output.lower()
                    for keyword in [
                        "error",
                        "invalid",
                        "failed",
                        "cannot",
                        "missing",
                        "unsupported",
                    ]
                ):
                    console.print(
                        f"[bright_yellow]Validation warning for {container_file}:[/bright_yellow]"
                    )
                    for line in grep_output.strip().split("\n"):
                        console.print(f"  [dim]{line.strip()}[/dim]")

        except (subprocess.TimeoutExpired, Exception):
            # Silently ignore validation errors during individual file processing
            pass

    def _extract_service_name_from_file(self, file: str) -> str:
        """Extract service name from network/volume file for display."""
        # Remove extension and try to find service name pattern
        base_name = file.replace(".network", "").replace(".volume", "")

        # For files like "local-ai-postgres.network", extract "local-ai"
        # For files like "postgres.network", just use "postgres"
        if base_name.startswith("local-ai"):
            return "local-ai"
        elif "-" in base_name:
            parts = base_name.split("-")
            if len(parts) >= 2:
                # Return first two parts for names like "service-name"
                return "-".join(parts[:2])

        return base_name

    def _get_network_dependencies_from_containers(
        self, stack_dir: Path, container_files: List[str]
    ) -> List[str]:
        """Get network dependencies from container files."""
        networks = []

        for container_file in container_files:
            try:
                container_path = stack_dir / container_file
                if container_path.exists():
                    with open(container_path, "r") as f:
                        content = f.read()

                    # Look for Network= lines
                    for line in content.split("\n"):
                        line = line.strip()
                        if line.startswith("Network="):
                            network_name = line.split("=", 1)[1].strip()
                            if network_name and network_name not in networks:
                                networks.append(network_name)

            except Exception as e:
                verbose_print(
                    f"[yellow]Warning: Could not parse {container_file}: {e}[/yellow]"
                )

        return networks

    def _extract_stack_name_from_network_file(self, file: str) -> str:
        """Extract stack name from network file for consistent messaging."""
        # Remove .network extension
        base_name = file.replace(".network", "")

        # For files like "supabase-network.network" -> "supabase"
        # For files like "local-ai-network.network" -> "local-ai"
        # For files like "postgres-network.network" -> "postgres"
        if base_name.endswith("-network"):
            return base_name.replace("-network", "")

        # For files like "supabase-volumes.network" -> "supabase"
        if "-" in base_name:
            parts = base_name.split("-")
            # Return the first part as the stack name
            return parts[0]

        # Fallback to the base name
        return base_name

    def set_file_permissions(
        self, files: List[str], target_dir: Path, use_sudo: bool = False
    ):
        """Set proper permissions on installed files."""
        if use_sudo:
            for file in files:
                cmd = ["sudo", "chmod", "644", str(target_dir / file)]
                verbose_print(f"  [cyan]exec: chmod 644 .../systemd/{file}[/cyan]")
                subprocess.run(cmd, check=True)
        else:
            for file in files:
                verbose_print(f"  [cyan]exec: chmod 644 .../systemd/{file}[/cyan]")
                (target_dir / file).chmod(0o644)


class QuadletInstaller:
    """Main Quadlet Stack Installation Manager with refactored architecture."""

    def __init__(self):
        """Initialize the installer with component managers."""
        self.quadlet_base_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")

        # Component managers
        self.env_manager = EnvironmentManager()
        self.systemd_manager = SystemdManager()
        self.validation_manager = ValidationManager()
        self.file_manager = FileManager()

        self._validate_base_directory()

    def _validate_base_directory(self):
        """Validate that the quadlet base directory exists."""
        if not self.quadlet_base_dir.exists():
            console.print(
                f"[red]Quadlet base directory not found: {self.quadlet_base_dir}[/red]"
            )
            raise FileNotFoundError(
                f"Quadlet base directory not found: {self.quadlet_base_dir}"
            )

    def discover_stacks(self) -> List[str]:
        """Discover available stacks in the quadlet directory."""
        stacks = []
        for item in self.quadlet_base_dir.iterdir():
            if (
                item.is_dir()
                and item.name not in ["scripts", "docs"]
                and self._has_quadlet_files(item)
            ):
                stacks.append(item.name)
        return sorted(stacks)

    def _has_quadlet_files(self, directory: Path) -> bool:
        """Check if directory contains quadlet files (excluding .disabled files)."""
        quadlet_extensions = [".container", ".network", ".volume"]
        for ext in quadlet_extensions:
            for file in directory.glob(f"*{ext}"):
                if not file.name.endswith(".disabled"):
                    return True
        return False

    def get_stack_files(self, stack_name: str) -> List[str]:
        """Get quadlet files for a stack, including shared network files."""
        stack_dir = self.quadlet_base_dir / stack_name
        if not stack_dir.exists():
            return []

        files = []
        quadlet_extensions = [".container", ".network", ".volume"]
        for ext in quadlet_extensions:
            for file in stack_dir.glob(f"*{ext}"):
                if not file.name.endswith(".disabled"):
                    files.append(file.name)

        # Add shared network files from root quadlets directory
        # These are network files that are shared across multiple stacks
        shared_network_files = self._get_shared_network_files_for_stack(stack_name)
        files.extend(shared_network_files)

        return sorted(files)

    def _get_shared_network_files_for_stack(self, stack_name: str) -> List[str]:
        """Get shared network files that should be included for a specific stack."""
        shared_networks = []

        # Map stack names to their corresponding shared network files
        stack_network_mapping = {
            "local-ai-stack": ["local-ai-network.network"],
            "supabase-stack": ["supabase-network.network"],
            # Add more mappings as needed for other stacks
        }

        # Get the network files for this stack
        network_files = stack_network_mapping.get(stack_name, [])

        # Verify the files actually exist in the root quadlets directory
        for network_file in network_files:
            network_path = self.quadlet_base_dir / network_file
            if network_path.exists() and not network_file.endswith(".disabled"):
                shared_networks.append(network_file)

        return shared_networks

    def get_service_names(self, stack_name: str) -> List[str]:
        """Get service names from quadlet files."""
        stack_dir = self.quadlet_base_dir / stack_name
        if not stack_dir.exists():
            return []

        services = []
        for file in stack_dir.glob("*.container"):
            if not file.name.endswith(".disabled"):
                services.append(file.stem)
        return sorted(services)

    def find_service_in_stacks(self, service_name: str) -> Optional[Tuple[str, str]]:
        """Find which stack contains a specific service."""
        available_stacks = self.discover_stacks()
        for stack in available_stacks:
            stack_dir = self.quadlet_base_dir / stack
            container_file = f"{service_name}.container"
            container_path = stack_dir / container_file

            if container_path.exists() and not container_file.endswith(".disabled"):
                return (stack, container_file)
        return None

    def validate_stack_or_service(self, name: str) -> Tuple[bool, str, Optional[str]]:
        """Validate that a stack or service exists with fuzzy matching support."""
        # Try exact match as a service within stacks FIRST (prioritize individual services)
        service_result = self.find_service_in_stacks(name)
        verbose_print(
            f"  [cyan]exec: find_service_in_stacks('{name}') returned: {service_result}[/cyan]"
        )
        if service_result:
            stack_name, container_file = service_result
            verbose_print(
                f"  [cyan]exec: Found service '{name}' in stack '{stack_name}' with container file '{container_file}'[/cyan]"
            )
            return (True, stack_name, container_file)

        # Try exact match as a stack only if no service found
        stack_dir = self.quadlet_base_dir / name
        if stack_dir.exists():
            files = self.get_stack_files(name)
            if files:
                return (True, name, None)

        # Use fuzzy matcher
        fuzzy_matcher = FuzzyMatcher(quadlet_installer=self)
        fuzzy_result = fuzzy_matcher.fuzzy_match_service_or_stack(name)

        if fuzzy_result:
            if fuzzy_result.endswith(".service"):
                service_name = fuzzy_result.replace(".service", "")
                service_result = self.find_service_in_stacks(service_name)
                if service_result:
                    stack_name, container_file = service_result
                    return (True, stack_name, container_file)
            else:
                # Check if fuzzy result is a service name first
                service_result = self.find_service_in_stacks(fuzzy_result)
                if service_result:
                    stack_name, container_file = service_result
                    return (True, stack_name, container_file)
                # Otherwise treat as stack
                return (True, fuzzy_result, None)
        elif fuzzy_result == "CANCELLED":
            return (False, name, None)
        elif fuzzy_result is None:
            console.print(f"[red]Stack or service '{name}' not found[/red]")
            return (False, name, None)

        console.print(f"[red]Stack or service '{name}' not found[/red]")
        return (False, name, None)

    def validate_stack(self, stack_name: str) -> bool:
        """Validate that a stack exists and has files."""
        is_valid, resolved_stack, service_file = self.validate_stack_or_service(
            stack_name
        )
        return is_valid and service_file is None

    def check_systemd_user_session(self) -> bool:
        """Check systemd user session health."""
        return self.systemd_manager.check_user_session()

    def install_stack(
        self,
        name: str,
        target_dir: Optional[Path] = None,
        use_sudo: bool = False,
    ) -> bool:
        """Install stack or service to target directory."""
        if target_dir is None:
            target_dir = Path.home() / ".config/containers/systemd"

        # Validate and determine if it's a stack or service
        is_valid, resolved_stack, service_file = self.validate_stack_or_service(name)
        verbose_print(
            f"  [cyan]exec: validate_stack_or_service returned: is_valid={is_valid}, resolved_stack={resolved_stack}, service_file={service_file}[/cyan]"
        )
        if not is_valid or resolved_stack in ["CANCELLED", None]:
            return False

        stack_dir = self.quadlet_base_dir / resolved_stack
        files, install_type, display_name = self._determine_installation_scope(
            service_file, name, resolved_stack
        )

        # Load environment
        if not self.env_manager.load_and_clean_env_file():
            return False

        # Perform installation
        return self._perform_installation(
            files,
            stack_dir,
            target_dir,
            display_name,
            install_type,
            resolved_stack,
            name,
            service_file,
            use_sudo,
        )

    def _determine_installation_scope(
        self, service_file: Optional[str], name: str, resolved_stack: str
    ) -> Tuple[List[str], str, str]:
        """Determine what files to install and installation type."""
        # Debug output to understand what's happening
        verbose_print(
            f"  [cyan]exec: service_file={service_file}, name={name}, resolved_stack={resolved_stack}[/cyan]"
        )

        if service_file:
            files = [service_file]
            install_type = "service"
            display_name = name
            verbose_print(
                f"  [cyan]exec: Installing single service - files={files}[/cyan]"
            )
            self._show_dependency_warning(name, resolved_stack)
        else:
            files = self.get_stack_files(resolved_stack)
            install_type = "stack"
            display_name = resolved_stack
            verbose_print(f"  [cyan]exec: Installing full stack - files={files}[/cyan]")

        return files, install_type, display_name

    def _show_dependency_warning(self, name: str, resolved_stack: str):
        """Show warning about service dependencies."""
        stack_files = self.get_stack_files(resolved_stack)
        network_files = [f for f in stack_files if f.endswith(".network")]
        volume_files = [f for f in stack_files if f.endswith(".volume")]

        if network_files or volume_files:
            console.print()
            console.print(
                f"[yellow]Service {name} may require shared resources:[/yellow]"
            )
            if network_files:
                console.print(f"  Networks: {', '.join(network_files)}")
            if volume_files:
                console.print(f"  Volumes: {', '.join(volume_files)}")
            console.print(
                "[yellow]Installing only the service file. Install the full stack if needed.[/yellow]"
            )

    def _perform_installation(
        self,
        files: List[str],
        stack_dir: Path,
        target_dir: Path,
        display_name: str,
        install_type: str,
        resolved_stack: str,
        name: str,
        service_file: Optional[str],
        use_sudo: bool,
    ) -> bool:
        """Perform the actual installation process."""

        try:
            # File operations
            self.file_manager.create_target_directory(target_dir, use_sudo)
            self.file_manager.copy_quadlet_files(files, stack_dir, target_dir, use_sudo)
            # Note: file permissions are now set during copy_quadlet_files

            # Note: Validation is now done per-file during copy_quadlet_files

            # System operations
            if not self.systemd_manager.reload_daemon(use_sudo):
                return False

            self._refresh_pm_discovery(display_name)
            self._show_next_steps(service_file, name, resolved_stack, use_sudo)

            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Installation failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Unexpected error during installation: {e}[/red]")
            return False

    def _refresh_pm_discovery(self, display_name: str) -> None:
        """Restart podman service to load changes (refresh functionality removed)."""
        console.print("[green]Restarting podman service to load changes...[/green]")
        try:
            restart_cmd = ["systemctl", "--user", "restart", "podman.service"]
            verbose_print(f"  [cyan]exec: {' '.join(restart_cmd)}[/cyan]")
            restart_result = subprocess.run(
                restart_cmd, capture_output=True, text=True, timeout=30
            )

            if restart_result.returncode != 0:
                console.print(
                    "[yellow]Failed to restart podman service - you may need to run: systemctl --user restart podman.service[/yellow]"
                )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            console.print(f"[yellow]Failed to restart podman service: {e}[/yellow]")

    def _show_next_steps(
        self,
        service_file: Optional[str],
        name: str,
        resolved_stack: str,
        use_sudo: bool,
    ):
        """Show next steps after installation."""
        if service_file:
            self._show_service_next_steps(name, use_sudo)
        else:
            self._show_stack_next_steps(resolved_stack, use_sudo)

    def _show_service_next_steps(self, service_name: str, use_sudo: bool) -> None:
        """Show next steps after single service installation."""
        from operations.common_actions import CommonActionsFormatter

        formatter = CommonActionsFormatter()

        # Show installation-specific actions
        console.print()
        console.print("[green]Installation completed successfully![/green]")

        # Show common actions with appropriate categories for installation
        formatter.show_common_actions(
            target=service_name,
            service_name=f"{service_name}.service",
            categories=["service_management", "service_status", "logs_diagnostics"],
        )

    def _show_stack_next_steps(self, stack_name: str, use_sudo: bool) -> None:
        """Show next steps after stack installation."""
        from operations.common_actions import CommonActionsFormatter

        services = self.get_service_names(stack_name)
        formatter = CommonActionsFormatter()

        if services:
            console.print()
            console.print("[green]Stack installation completed successfully![/green]")
            example_service = services[0] if services else stack_name

            # Show common actions for the example service
            formatter.show_common_actions(
                target=example_service,
                service_name=f"{example_service}.service",
                categories=["service_management", "service_status", "logs_diagnostics"],
            )

    def list_stacks(self) -> None:
        """List all available stacks."""
        console.print("[blue]Available Stacks:[/blue]")
        console.print()

        available_stacks = self.discover_stacks()
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Stack Name", style="green", no_wrap=True)
        table.add_column("Files", style="cyan")
        table.add_column("Services", style="yellow")

        for stack in available_stacks:
            files = self.get_stack_files(stack)
            services = self.get_service_names(stack)
            table.add_row(
                stack,
                ", ".join(files) if files else "None",
                ", ".join(services) if services else "None",
            )

        console.print(table)

    def uninstall_stack(
        self, name: str, target_dir: Optional[Path] = None, use_sudo: bool = False
    ) -> bool:
        """Uninstall stack or service from target directory."""
        if target_dir is None:
            target_dir = Path.home() / ".config/containers/systemd"

        # Validate and determine if it's a stack or service
        is_valid, resolved_stack, service_file = self.validate_stack_or_service(name)
        if not is_valid:
            return False

        files, services, install_type, display_name = self._determine_uninstall_scope(
            service_file, name, resolved_stack
        )

        console.print(
            f"[blue]Uninstalling {display_name} {install_type} from {target_dir}[/blue]"
        )

        try:
            self._stop_and_disable_services(services, use_sudo)
            self._remove_quadlet_files(files, target_dir, use_sudo)

            if not self.systemd_manager.reload_daemon(use_sudo):
                console.print(
                    "[yellow]Warning: Failed to reload daemon, but uninstallation completed[/yellow]"
                )

            console.print("[green]Uninstallation complete![/green]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Uninstallation failed: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Unexpected error during uninstallation: {e}[/red]")
            return False

    def _determine_uninstall_scope(
        self, service_file: Optional[str], name: str, resolved_stack: str
    ) -> Tuple[List[str], List[str], str, str]:
        """Determine what to uninstall."""
        if service_file:
            files = [service_file]
            services = [name]
            install_type = "service"
            display_name = name
        else:
            files = self.get_stack_files(resolved_stack)
            services = self.get_service_names(resolved_stack)
            install_type = "stack"
            display_name = resolved_stack

        return files, services, install_type, display_name

    def _stop_and_disable_services(self, services: List[str], use_sudo: bool):
        """Stop and disable services before uninstallation."""
        for service in services:
            console.print(f"[blue]Stopping {service}.service[/blue]")

            if use_sudo:
                stop_cmd = ["sudo", "systemctl", "stop", f"{service}.service"]
                disable_cmd = ["sudo", "systemctl", "disable", f"{service}.service"]
            else:
                stop_cmd = ["systemctl", "--user", "stop", f"{service}.service"]
                disable_cmd = ["systemctl", "--user", "disable", f"{service}.service"]

            verbose_print(f"  [cyan]exec: {' '.join(stop_cmd)}[/cyan]")
            subprocess.run(stop_cmd, capture_output=True)

            verbose_print(f"  [cyan]exec: {' '.join(disable_cmd)}[/cyan]")
            subprocess.run(disable_cmd, capture_output=True)

    def _remove_quadlet_files(self, files: List[str], target_dir: Path, use_sudo: bool):
        """Remove quadlet files from target directory."""
        for file in files:
            file_path = target_dir / file
            if file_path.exists():
                console.print(f"[blue]Removing {file}[/blue]")

                if use_sudo:
                    rm_cmd = ["sudo", "rm", str(file_path)]
                    verbose_print(f"  [cyan]exec: {' '.join(rm_cmd)}[/cyan]")
                    subprocess.run(rm_cmd, check=True)
                else:
                    verbose_print(f"  [cyan]exec: rm .../systemd/{file}[/cyan]")
                    file_path.unlink()
