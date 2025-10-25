"""AI-powered diagnostics and log analysis operations."""

from ai_analyzer import ai_analyzer


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
        ai_agent: str | None = None,
    ) -> None:
        """AI-powered analysis of service logs using unified AI analyzer"""
        # Initialize ai_analyzer with manager if not already done
        if ai_analyzer.manager is None:
            ai_analyzer.manager = self.manager

        # Prepare context data for log analysis
        context_data = {"lines": lines}

        # Use unified AI analyzer
        ai_analyzer.ai_analyze(
            analysis_type="logs",
            target=target,
            context_data=context_data,
            ai_agent=ai_agent,
            verbose=verbose,
        )
