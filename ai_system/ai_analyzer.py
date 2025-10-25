"""Unified AI Analysis System for all PM commands - Refactored Version"""

# Import the refactored AI analyzer
from ai_analyzer import AIAnalyzer, ai_analyzer

# Re-export for backward compatibility
__all__ = ["AIAnalyzer", "ai_analyzer"]

# The global instance is now created in the ai_analyzer package
# This maintains backward compatibility with existing code
