"""AI-powered diagnostics and log analysis operations."""

from ai_analyzer import get_ai_analyzer


class AIDiagnostics:
    """Handles AI-powered log analysis and diagnostics"""

    def __init__(self, manager):
        self.manager = manager

    def ai_analyze_logs(
        self,
        target: str,
        lines: int = 50,
        vllm_url: str = "http://localhost:8003",
        verbose: bool = False,
        ai_model: str | None = None,
    ) -> None:
        """AI-powered analysis of service logs using unified AI analyzer"""
        analyzer = get_ai_analyzer(self.manager)

        # Prepare context data for log analysis
        context_data = {"lines": lines}

        # Use unified AI analyzer (abacus-proxy)
        analyzer.ai_analyze(
            analysis_type="logs",
            target=target,
            context_data=context_data,
            ai_model=ai_model,
            verbose=verbose,
        )
