#!/usr/bin/env python3
"""
Podman Container Management Script with Rich Console Output
Quadlet-only version with clean separation of concerns
"""

import sys

from cli.command_router import CommandRouter
from cli.help_formatter import show_rich_help
from cli.parser import create_argument_parser
from config import console, set_verbose
from quadlet_display import QuadletDisplayManager
from quadlet_manager import QuadletManager
from quadlet_ops import QuadletOperations


def main():
    """Main entry point for podman manager"""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Handle help with Rich formatting
    if args.help or (not args.command and len(sys.argv) == 1):
        show_rich_help()
        return

    try:
        # Set verbose mode from global flag
        set_verbose(args.verbose)

        # Initialize quadlet manager (quadlet-only mode)
        manager = QuadletManager()
        container_ops = QuadletOperations(manager)
        display = QuadletDisplayManager(manager)

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
