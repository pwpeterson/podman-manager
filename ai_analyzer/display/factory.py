"""Factory helpers for display/formatting components."""

from __future__ import annotations

from .interactive import InteractiveAnalysisHandler
from .markdown import MarkdownDisplayFormatter
from .troubleshooting import BasicTroubleshootingFormatter


class DisplayFormatterFactory:
    """Factory for creating appropriate display formatters."""

    @staticmethod
    def create_markdown_formatter() -> MarkdownDisplayFormatter:
        """Create markdown display formatter."""
        return MarkdownDisplayFormatter()

    @staticmethod
    def create_basic_troubleshooting_formatter() -> BasicTroubleshootingFormatter:
        """Create basic troubleshooting formatter."""
        return BasicTroubleshootingFormatter()

    @staticmethod
    def create_interactive_handler() -> InteractiveAnalysisHandler:
        """Create interactive analysis handler."""
        return InteractiveAnalysisHandler()
