"""Unified AI Analysis System for all PM commands - Refactored Version"""

# Import the refactored AI analyzer API (no import-time singleton side effects)
from ai_analyzer import AIAnalyzer, get_ai_analyzer

# Re-export for backward compatibility
__all__ = ["AIAnalyzer", "get_ai_analyzer"]
