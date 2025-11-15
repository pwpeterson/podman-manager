#!/usr/bin/env python3
"""
Podman Container Management Script with Rich Console Output
Quadlet-only version with clean separation of concerns
"""

import signal
import sys

# Load environment variables from .env file
from contextlib import suppress
from pathlib import Path

with suppress(ImportError):
    from dotenv import load_dotenv

    # Load .env file from the current directory
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        # Use override=True to force .env values over system environment
        load_dotenv(env_path, override=True)

from rich.console import Console

from cli.command_router import CommandRouter
from cli.help_formatter import show_rich_help
from cli.parser import create_argument_parser
from core.config import console, set_verbose
from managers.quadlet_manager import QuadletManager
from operations.quadlet_display import QuadletDisplayManager
from operations.quadlet_ops import QuadletOperations


def handle_sigtstp(signum, frame):
    """Handle Ctrl+Z (SIGTSTP) signal to provide clean exit instead of suspension"""
    _ = signum, frame  # Explicitly mark as unused for vulture
    console = Console()
    console.print("\n[yellow]Operation cancelled by user (Ctrl+Z)[/yellow]")
    sys.exit(130)  # Exit with code 130 (128 + SIGINT equivalent for user interruption)


def main():
    """Main entry point for podman manager"""
    args = create_argument_parser().parse_args()

    # Handle help with Rich formatting
    if args.help or (not args.command and len(sys.argv) == 1):
        show_rich_help()
        return

    try:
        # Set up signal handler for Ctrl+Z
        signal.signal(signal.SIGTSTP, handle_sigtstp)

        # Set verbose mode from global flag
        set_verbose(args.verbose)

        # Initialize quadlet manager (quadlet-only mode)
        manager = QuadletManager()
        container_ops, display = QuadletOperations(manager), QuadletDisplayManager(
            manager
        )

        # Create command router and execute command (quadlet-only mode)
        router = CommandRouter(manager, container_ops, display, "quadlet", None)
        success = router.route_command(args)

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception:
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
