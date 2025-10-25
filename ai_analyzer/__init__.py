"""AI Analyzer package for Podman Manager"""

from .analyzer import AIAnalyzer
from .config import config

# Global instance for backward compatibility
ai_analyzer = AIAnalyzer(None)

__all__ = ["AIAnalyzer", "ai_analyzer", "config"]
