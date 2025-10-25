"""Configuration and logging setup for Podman Manager."""

import sys
from pathlib import Path

__all__ = ["console", "verbose_print", "set_verbose", "is_verbose", "setup_logging"]

try:
    from loguru import logger
    from rich.console import Console
except ImportError:
    print("Error: Required libraries not found. Install with:")
    print("pip install rich pyyaml loguru")
    sys.exit(1)

# Configure Rich console with force color support
console = Console(force_terminal=True, color_system="truecolor", legacy_windows=False)

# Global verbose flag
_verbose_enabled = False


def set_verbose(enabled: bool) -> None:
    """Set the global verbose flag."""
    global _verbose_enabled
    _verbose_enabled = enabled


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return _verbose_enabled


def verbose_print(message: str) -> None:
    """Print message only if verbose mode is enabled."""
    if _verbose_enabled:
        # Add indentation to exec messages
        if "exec:" in message:
            console.print(f"  {message}")
        else:
            console.print(message)


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
