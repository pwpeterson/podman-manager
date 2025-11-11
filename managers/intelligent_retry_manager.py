"""Intelligent retry manager with AI-guided fixes for reinit failures."""

import subprocess
import time
from typing import Callable, Dict, List, Optional

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from core.config import console, verbose_print


class IntelligentRetryManager:
    """Manages intelligent retry attempts with AI-guided fixes."""

    def __init__(self, manager):
        self.manager = manager
        self.retry_history = []
        self.applied_fixes = []
        self.max_retries = 3

    def retry_with_ai_guidance(
        self,
        target: str,
        original_operation: Callable,
        operation_args: tuple = (),
        operation_kwargs: Optional[Dict] = None,
        enable_auto_fixes: bool = True,
    ) -> bool:
        """Retry failed operation with AI-guided fixes."""
        operation_kwargs = operation_kwargs or {}

        console.print("\n[cyan]🤖 Intelligent Retry with AI Guidance[/cyan]")
        console.print(
            "[dim]Analyzing failure and applying intelligent fixes...[/dim]\n"
        )

        for attempt in range(1, self.max_retries + 1):
            console.print(
                f"[yellow]Retry Attempt {attempt}/{self.max_retries}[/yellow]"
            )

            # Get AI-guided fixes for this attempt
            fixes = self._get_ai_guided_fixes(target, attempt)

            if fixes and enable_auto_fixes:
                # Apply fixes automatically or with user confirmation
                if self._apply_fixes(target, fixes, attempt):
                    console.print("[green]✅ Fixes applied successfully[/green]")
                else:
                    console.print("[yellow]⚠️  Some fixes could not be applied[/yellow]")

            # Wait a moment for system to stabilize
            time.sleep(2)

            # Retry the operation
            console.print(f"[cyan]Retrying operation for {target}...[/cyan]")

            try:
                success = original_operation(*operation_args, **operation_kwargs)

                if success:
                    console.print(
                        f"[green]✅ Retry attempt {attempt} succeeded![/green]"
                    )
                    self._log_successful_retry(target, attempt, fixes)
                    return True
                else:
                    console.print(f"[red]❌ Retry attempt {attempt} failed[/red]")
                    self._log_failed_retry(target, attempt, fixes)

            except Exception as e:
                console.print(
                    f"[red]❌ Retry attempt {attempt} failed with exception: {e}[/red]"
                )
                self._log_failed_retry(target, attempt, fixes, str(e))

            # Don't wait after the last attempt
            if attempt < self.max_retries:
                console.print("[dim]Waiting before next attempt...[/dim]\n")
                time.sleep(5)

        console.print(f"[red]❌ All {self.max_retries} retry attempts failed[/red]")
        self._show_final_recommendations(target)
        return False

    def _get_ai_guided_fixes(self, target: str, attempt: int) -> List[Dict[str, str]]:
        """Get AI-guided fixes for the current retry attempt."""
        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Prepare context for AI analysis
            context_data = {
                "retry_attempt": attempt,
                "max_retries": self.max_retries,
                "retry_history": self.retry_history,
                "applied_fixes": self.applied_fixes,
                "request_fixes": True,
            }

            # Get AI analysis with fix recommendations
            with Progress(
                SpinnerColumn(),
                TextColumn("[yellow]Getting AI-guided fixes...[/yellow]"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("ai_analysis", total=None)

                result = analyzer.ai_analyze(
                    analysis_type="intelligent_retry_fixes",
                    target=target,
                    context_data=context_data,
                    verbose=False,
                )

                progress.remove_task(task)

            if result:
                # Parse AI response for actionable fixes
                fixes = self._parse_ai_fixes(result)
                return fixes

        except Exception as e:
            verbose_print(f"  [cyan]exec: AI-guided fixes failed: {e}[/cyan]")

        # Fallback to common fixes if AI analysis fails
        return self._get_common_fixes(target, attempt)

    def _parse_ai_fixes(self, ai_response: str) -> List[Dict[str, str]]:
        """Parse AI response to extract actionable fixes."""
        fixes = []

        # Look for fix patterns in AI response
        lines = ai_response.split("\n")
        current_fix = None

        for line in lines:
            line = line.strip()

            # Look for fix headers
            if (
                line.startswith("**Fix")
                or line.startswith("### Fix")
                or "FIX:" in line.upper()
            ):
                if current_fix:
                    fixes.append(current_fix)
                current_fix = {
                    "title": line.replace("**", "")
                    .replace("###", "")
                    .replace("FIX:", "")
                    .strip(),
                    "commands": [],
                    "description": "",
                    "risk_level": "medium",
                }

            # Look for commands
            elif (
                line.startswith("```")
                or line.startswith("sudo ")
                or line.startswith("systemctl ")
                or line.startswith("podman ")
            ):
                if current_fix and not line.startswith("```"):
                    current_fix["commands"].append(line)

            # Look for risk indicators
            elif "low risk" in line.lower():
                if current_fix:
                    current_fix["risk_level"] = "low"
            elif "high risk" in line.lower():
                if current_fix:
                    current_fix["risk_level"] = "high"

            # Collect description
            elif current_fix and line and not line.startswith("#"):
                current_fix["description"] += line + " "

        # Add the last fix
        if current_fix:
            fixes.append(current_fix)

        # Clean up descriptions
        for fix in fixes:
            fix["description"] = fix["description"].strip()

        return fixes

    def _get_common_fixes(self, target: str, attempt: int) -> List[Dict[str, str]]:
        """Get common fixes based on attempt number and target type."""
        fixes = []

        if attempt == 1:
            # First attempt: gentle fixes
            fixes.extend(
                [
                    {
                        "title": "Clear systemd failed state",
                        "commands": [f"systemctl --user reset-failed {target}"],
                        "description": "Reset any failed service state",
                        "risk_level": "low",
                    },
                    {
                        "title": "Reload systemd daemon",
                        "commands": ["systemctl --user daemon-reload"],
                        "description": "Reload systemd configuration",
                        "risk_level": "low",
                    },
                ]
            )

        elif attempt == 2:
            # Second attempt: more aggressive fixes
            fixes.extend(
                [
                    {
                        "title": "Stop and remove container",
                        "commands": [
                            f"podman stop {target} || true",
                            f"podman rm {target} || true",
                        ],
                        "description": "Force remove existing container",
                        "risk_level": "medium",
                    },
                    {
                        "title": "Clean up container resources",
                        "commands": ["podman system prune -f --volumes"],
                        "description": "Clean up unused containers and volumes",
                        "risk_level": "medium",
                    },
                ]
            )

        elif attempt == 3:
            # Final attempt: aggressive fixes
            fixes.extend(
                [
                    {
                        "title": "Force kill processes",
                        "commands": [f"pkill -f {target} || true"],
                        "description": "Force kill any related processes",
                        "risk_level": "high",
                    },
                    {
                        "title": "Reset container storage",
                        "commands": ["podman system reset --force"],
                        "description": "Reset podman storage (WARNING: removes all containers)",
                        "risk_level": "high",
                    },
                ]
            )

        # Add vLLM-specific fixes
        if "vllm" in target.lower():
            fixes.append(
                {
                    "title": "Clear vLLM port",
                    "commands": ["fuser -k 8005/tcp || true"],
                    "description": "Kill any process using vLLM port 8005",
                    "risk_level": "medium",
                }
            )

        return fixes

    def _apply_fixes(
        self, target: str, fixes: List[Dict[str, str]], attempt: int
    ) -> bool:
        """Apply the suggested fixes with user confirmation for high-risk fixes."""
        if not fixes:
            return True

        console.print(
            f"\n[cyan]Applying {len(fixes)} suggested fixes for attempt {attempt}:[/cyan]"
        )

        applied_count = 0

        for i, fix in enumerate(fixes, 1):
            title = fix.get("title", f"Fix {i}")
            description = fix.get("description", "No description")
            commands = fix.get("commands", [])
            risk_level = fix.get("risk_level", "medium")

            # Show fix information
            risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(
                risk_level, "yellow"
            )

            console.print(f"\n[bold]{i}. {title}[/bold]")
            console.print(f"[dim]{description}[/dim]")
            console.print(
                f"[{risk_color}]Risk Level: {risk_level.upper()}[/{risk_color}]"
            )

            if commands:
                console.print("[cyan]Commands:[/cyan]")
                for cmd in commands:
                    console.print(f"  [dim]{cmd}[/dim]")

            # Ask for confirmation for high-risk fixes
            should_apply = True
            if risk_level == "high":
                should_apply = Confirm.ask(
                    "[red]This is a HIGH RISK fix. Apply it?[/red]", default=False
                )
            elif risk_level == "medium":
                should_apply = Confirm.ask("Apply this fix?", default=True)

            if should_apply:
                # Ensure commands is a list of strings
                if isinstance(commands, str):
                    commands = [commands]
                elif not isinstance(commands, list):
                    commands = []
                success = self._execute_fix_commands(commands)
                if success:
                    console.print(f"[green]✅ Fix {i} applied successfully[/green]")
                    applied_count += 1
                    self.applied_fixes.append(
                        {"attempt": attempt, "fix": fix, "success": True}
                    )
                else:
                    console.print(f"[red]❌ Fix {i} failed to apply[/red]")
                    self.applied_fixes.append(
                        {"attempt": attempt, "fix": fix, "success": False}
                    )
            else:
                console.print(f"[yellow]⏭️  Fix {i} skipped by user[/yellow]")

        return applied_count > 0

    def _execute_fix_commands(self, commands: List[str]) -> bool:
        """Execute fix commands safely."""
        if not commands:
            return True

        success = True

        for cmd in commands:
            try:
                verbose_print(f"  [cyan]exec: {cmd}[/cyan]")

                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30
                )

                if result.returncode != 0 and "|| true" not in cmd:
                    verbose_print(
                        f"  [cyan]exec: Command failed: {result.stderr}[/cyan]"
                    )
                    success = False
                else:
                    verbose_print("  [cyan]exec: Command succeeded[/cyan]")

            except subprocess.TimeoutExpired:
                verbose_print(f"  [cyan]exec: Command timed out: {cmd}[/cyan]")
                success = False
            except Exception as e:
                verbose_print(f"  [cyan]exec: Command error: {e}[/cyan]")
                success = False

        return success

    def _log_successful_retry(
        self, target: str, attempt: int, fixes: List[Dict]
    ) -> None:
        """Log successful retry attempt."""
        self.retry_history.append(
            {
                "target": target,
                "attempt": attempt,
                "success": True,
                "fixes_applied": len(
                    [
                        f
                        for f in self.applied_fixes
                        if f["attempt"] == attempt and f["success"]
                    ]
                ),
                "timestamp": time.time(),
            }
        )

    def _log_failed_retry(
        self,
        target: str,
        attempt: int,
        fixes: List[Dict],
        exception: Optional[str] = None,
    ) -> None:
        """Log failed retry attempt."""
        self.retry_history.append(
            {
                "target": target,
                "attempt": attempt,
                "success": False,
                "fixes_applied": len(
                    [
                        f
                        for f in self.applied_fixes
                        if f["attempt"] == attempt and f["success"]
                    ]
                ),
                "exception": exception,
                "timestamp": time.time(),
            }
        )

    def _show_final_recommendations(self, target: str) -> None:
        """Show final recommendations after all retries failed."""
        console.print("\n[red]🚨 All Retry Attempts Failed[/red]")
        console.print("[dim]Here are some final recommendations:[/dim]\n")

        recommendations = [
            "Check system logs for hardware or kernel issues: `journalctl -p err -n 50`",
            "Verify disk space and system resources: `df -h && free -h`",
            "Check for conflicting services: `systemctl --user list-units --failed`",
            "Review container configuration files for syntax errors",
            "Consider rebuilding the container image from scratch",
            "Check network connectivity and DNS resolution",
            "Verify SELinux/AppArmor policies are not blocking the service",
        ]

        for i, rec in enumerate(recommendations, 1):
            console.print(f"  {i}. [cyan]{rec}[/cyan]")

        console.print(
            "\n[yellow]💡 Consider running 'pm diag {target}' for detailed analysis[/yellow]"
        )

    def get_retry_statistics(self) -> Dict:
        """Get statistics about retry attempts."""
        if not self.retry_history:
            return {}

        total_attempts = len(self.retry_history)
        successful_attempts = len([r for r in self.retry_history if r["success"]])

        return {
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "success_rate": (
                successful_attempts / total_attempts if total_attempts > 0 else 0
            ),
            "fixes_applied": len(self.applied_fixes),
            "successful_fixes": len([f for f in self.applied_fixes if f["success"]]),
        }
