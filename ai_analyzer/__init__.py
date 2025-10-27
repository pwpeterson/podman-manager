"""AI Analyzer package for Podman Manager"""

from pathlib import Path

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv

    # Load .env file from the project root (parent of this package)
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        # Use override=True to force .env values over system environment
        load_dotenv(env_path, override=True)
except ImportError:
    # python-dotenv not installed, skip loading
    pass

from .analyzer import AIAnalyzer
from .config import config

# Global instance for backward compatibility
ai_analyzer = AIAnalyzer(None)

__all__ = ["AIAnalyzer", "ai_analyzer", "config"]
