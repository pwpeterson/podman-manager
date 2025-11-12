"""Monitoring and display functionality for reinit operations."""

import time
from typing import Dict, List, Tuple

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from core.config import console


class ReinitMonitor:
    """Handles monitoring, progress display, and verification for reinit operations."""

    def __init__(self, manager, health_checker):
        self.manager = manager
        self.health_checker = health_checker

    def perform_post_reinit_verification(
        self, target: str, enable_ai_guidance: bool
    ) -> None:
        """Perform post-reinit verification and provide optimization suggestions."""
        console.print("\n[cyan]🔍 Post-reinit Verification[/cyan]")

        verification_results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]Verifying reinit success...[/yellow]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("verification", total=None)

            # Wait a moment for services to stabilize
            time.sleep(3)

            # Check service status
            progress.update(
                task, description="[yellow]Checking service status...[/yellow]"
            )
            service_status = self.health_checker.verify_service_status(target)
            verification_results.append(("Service Status", service_status))

            # Check container health
            progress.update(
                task, description="[yellow]Checking container health...[/yellow]"
            )
            container_health = self.health_checker.verify_container_health(target)
            verification_results.append(("Container Health", container_health))

            # Check performance metrics
            progress.update(
                task, description="[yellow]Checking performance...[/yellow]"
            )
            # Note: This would need pre_reinit_state passed in for full functionality
            performance_check = {
                "status": "info",
                "details": "Performance baseline unavailable",
            }
            verification_results.append(("Performance", performance_check))

            # Show completion message without spinner
            progress.update(task, description="[green]Verification completed[/green]")
            time.sleep(0.5)  # Brief pause to show completion
            progress.remove_task(task)

        # Display verification results
        self._display_verification_results(verification_results)

        # Provide optimization suggestions if AI guidance is enabled
        if enable_ai_guidance:
            self._provide_optimization_suggestions(target, verification_results)

    def _display_verification_results(
        self, results: List[Tuple[str, Dict[str, str]]]
    ) -> None:
        """Display verification results."""
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Verification", style="white", width=20)
        table.add_column("Status", width=12)
        table.add_column("Details", style="dim")

        status_styles = {
            "good": "[green]✅ Good[/green]",
            "info": "[blue]ℹ️  Info[/blue]",
            "warning": "[yellow]⚠️  Warning[/yellow]",
            "error": "[red]❌ Error[/red]",
        }

        for check_name, result in results:
            status = result["status"]
            details = result["details"]
            styled_status = status_styles.get(status, f"[dim]{status}[/dim]")
            table.add_row(check_name, styled_status, details)

        console.print(table)

    def _provide_optimization_suggestions(
        self, target: str, verification_results: List
    ) -> None:
        """Provide AI-powered optimization suggestions after successful reinit."""
        console.print("\n[cyan]💡 Optimization Suggestions[/cyan]")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Run optimization analysis
            analyzer.ai_analyze(
                analysis_type="post_reinit_optimization",
                target=target,
                context_data={
                    "verification_results": verification_results,
                },
                verbose=False,
            )

        except Exception as e:
            console.print(f"[dim]Optimization suggestions unavailable: {e}[/dim]")

    def show_next_steps(self, target: str) -> None:
        """Show optional next steps after successful reinit"""
        # Common actions are now handled by the command router's try_with_fallback method
        # This method is kept for potential future use but no longer displays actions
        pass

    def execute_enhanced_reinit(
        self,
        target: str,
        build: bool,
        build_type: str | None,
        vllm_model: str | None,
        enable_ai_guidance: bool,
        reinit_func,
    ) -> bool:
        """Execute reinit with enhanced monitoring and real-time diagnostic parsing."""
        console.print("[cyan]🔄 Enhanced Reinit Execution[/cyan]")

        # Store context for potential AI analysis
        reinit_context = {
            "target": target,
            "build": build,
            "build_type": build_type,
            "vllm_model": vllm_model,
            "start_time": time.time(),
        }

        # Execute the standard reinit process with enhanced monitoring
        try:
            # Use the provided reinit function
            success = reinit_func(target, build, build_type, vllm_model)

            if not success and enable_ai_guidance:
                # Enhanced failure analysis with context
                self._run_enhanced_failure_analysis(target, reinit_context)

            return success

        except Exception as e:
            console.print(f"[red]Reinit execution failed: {e}[/red]")
            if enable_ai_guidance:
                self._run_enhanced_failure_analysis(
                    target, reinit_context, exception=str(e)
                )
            return False

    def _run_enhanced_failure_analysis(
        self, target: str, reinit_context: Dict, exception: str | None = None
    ) -> None:
        """Run enhanced AI failure analysis with reinit context."""
        console.print("\n[red]🔍 Enhanced Failure Analysis[/red]")
        console.print("[dim]Analyzing reinit failure with full context...[/dim]\n")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Prepare enhanced context data
            context_data = {
                "reinit_context": reinit_context,
            }

            if exception:
                context_data["exception"] = {"error": exception}

            # Run enhanced AI analysis
            analyzer.ai_analyze(
                analysis_type="enhanced_reinit_failure",
                target=target,
                context_data=context_data,
                verbose=True,
            )

        except Exception as e:
            console.print(f"[yellow]Enhanced failure analysis failed: {e}[/yellow]")

    def run_pre_reinit_ai_analysis(self, target: str, pre_reinit_state: Dict) -> None:
        """Run AI analysis before reinit to identify potential issues."""
        console.print("\n[green]🤖 Pre-reinit AI Analysis[/green]")
        console.print("[dim]Analyzing potential issues before reinit...[/dim]\n")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Run AI analysis with pre-reinit context
            analyzer.ai_analyze(
                analysis_type="pre_reinit_check",
                target=target,
                context_data={
                    "health_check_failed": True,
                    "pre_reinit_state": pre_reinit_state,
                },
                verbose=True,
            )

        except Exception as e:
            console.print(f"[yellow]Pre-reinit AI analysis failed: {e}[/yellow]")
