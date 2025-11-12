"""AI analysis integration for reinit operations."""

from typing import Any, Dict, List, Optional

from core.config import console


class ReinitAIAnalyzer:
    """Handles AI analysis integration for reinit operations."""

    def __init__(self, manager):
        self.manager = manager

    def run_pre_reinit_ai_analysis(self, target: str, pre_reinit_state: Dict) -> None:
        """Run AI analysis before reinit to identify potential issues."""
        console.print("\n[green]🤖 Pre-reinit AI Analysis[/green]")
        console.print("[dim]Analyzing potential issues before reinit...[/dim]")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Display which AI agent is being used
            ai_agent_info = self._get_ai_agent_info(analyzer)
            console.print(f"[cyan]Using AI agent: {ai_agent_info}[/cyan]\n")

            # Run AI analysis with pre-reinit context
            result = analyzer.ai_analyze(
                analysis_type="pre_reinit_check",
                target=target,
                context_data={
                    "health_check_failed": True,
                    "pre_reinit_state": pre_reinit_state,
                },
                verbose=True,
            )

            if not result:
                console.print(
                    "[yellow]⚠️  AI analysis completed but provided no insights[/yellow]"
                )

        except ImportError as e:
            console.print(f"[red]❌ AI analyzer module not available: {e}[/red]")
            console.print("[dim]Install ai_analyzer module to enable AI analysis[/dim]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Pre-reinit AI analysis failed: {e}[/yellow]")

    def run_enhanced_failure_analysis(
        self,
        target: str,
        reinit_context: Dict,
        pre_reinit_state: Dict,
        exception: Optional[str] = None,
    ) -> None:
        """Run enhanced AI failure analysis with reinit context."""
        console.print("\n[red]🔍 Enhanced Failure Analysis[/red]")
        console.print("[dim]Analyzing reinit failure with full context...[/dim]")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Display which AI agent is being used
            ai_agent_info = self._get_ai_agent_info(analyzer)
            console.print(f"[cyan]Using AI agent: {ai_agent_info}[/cyan]\n")

            # Prepare enhanced context data
            context_data: Dict[str, Any] = {
                "reinit_context": reinit_context,
                "pre_reinit_state": pre_reinit_state,
            }

            if exception:
                context_data["exception"] = exception

            # Run enhanced AI analysis
            result = analyzer.ai_analyze(
                analysis_type="enhanced_reinit_failure",
                target=target,
                context_data=context_data,
                verbose=True,
            )

            if not result:
                console.print(
                    "[yellow]⚠️  AI analysis completed but provided no insights[/yellow]"
                )

        except ImportError as e:
            console.print(f"[red]❌ AI analyzer module not available: {e}[/red]")
            console.print(
                "[dim]Install ai_analyzer module to enable failure analysis[/dim]"
            )
        except Exception as e:
            console.print(f"[yellow]⚠️  Enhanced failure analysis failed: {e}[/yellow]")

    def provide_optimization_suggestions(
        self,
        target: str,
        verification_results: List,
        reinit_context: Dict,
        pre_reinit_state: Dict,
    ) -> None:
        """Provide AI-powered optimization suggestions after successful reinit."""
        console.print("\n[cyan]💡 Optimization Suggestions[/cyan]")

        try:
            from ai_analyzer.analyzer import AIAnalyzer

            analyzer = AIAnalyzer(self.manager)

            # Display which AI agent is being used
            ai_agent_info = self._get_ai_agent_info(analyzer)
            console.print(f"[cyan]Using AI agent: {ai_agent_info}[/cyan]")

            # Run optimization analysis
            result = analyzer.ai_analyze(
                analysis_type="post_reinit_optimization",
                target=target,
                context_data={
                    "verification_results": verification_results,
                    "reinit_context": reinit_context,
                    "pre_reinit_state": pre_reinit_state,
                },
                verbose=False,
            )

            if not result:
                console.print(
                    "[yellow]⚠️  AI analysis completed but provided no optimization suggestions[/yellow]"
                )

        except ImportError as e:
            console.print(f"[red]❌ AI analyzer module not available: {e}[/red]")
            console.print(
                "[dim]Install ai_analyzer module to enable optimization suggestions[/dim]"
            )
        except Exception as e:
            console.print(f"[dim]⚠️  Optimization suggestions unavailable: {e}[/dim]")

    def _get_ai_agent_info(self, analyzer) -> str:
        """Get information about which AI agent is being used."""
        try:
            # Try to get the current AI agent from the analyzer
            if hasattr(analyzer, "current_agent") and analyzer.current_agent:
                agent_name = analyzer.current_agent.get("name", "Unknown")
                agent_type = analyzer.current_agent.get("agent_type", "Unknown")
                return f"{agent_name} ({agent_type})"
            elif hasattr(analyzer, "ai_agents") and analyzer.ai_agents:
                # Get the first available agent
                first_agent = next(iter(analyzer.ai_agents.values()), {})
                agent_name = first_agent.get("name", "Unknown")
                agent_type = first_agent.get("agent_type", "Unknown")
                return f"{agent_name} ({agent_type})"
            else:
                return "No AI agent configured"
        except Exception:
            return "AI agent detection failed"
