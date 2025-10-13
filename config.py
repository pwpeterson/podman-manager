"""Configuration and logging setup for Podman Manager."""

import sys
from pathlib import Path

try:
    from loguru import logger
    from rich.console import Console
except ImportError:
    print("Error: Required libraries not found. Install with:")
    print("pip install rich pyyaml loguru")
    sys.exit(1)

# Configure Rich console
console = Console()


def setup_logging():
    """Configure Loguru with Rich integration."""
    # Remove default handler
    logger.remove()
    
    # Add stderr handler with rich formatting
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level="WARNING",
        colorize=True,
        enqueue=True,
    )
    
    # Add file logging for debugging
    logger.add(
        Path.home() / ".local/share/podman-manager.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
        serialize=True,  # JSON format for structured logs
    )


# Initialize logging on import
setup_logging()
