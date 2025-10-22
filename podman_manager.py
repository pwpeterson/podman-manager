#!/usr/bin/env python3
"""
Podman Container Management Script with Rich Console Output
Refactored modular version with clean separation of concerns
"""

import os
import sys
from pathlib import Path

from cli.command_router import CommandRouter
from cli.help_formatter import show_rich_help
from cli.parser import create_argument_parser
from config import console, set_verbose
from container_ops import ContainerOperations
from display import DisplayManager
from manager import PodmanManager
from project_detector import ProjectTypeDetector
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

        # Initialize project type detector
        compose_dir = os.environ.get("PODMAN_COMPOSE_DIR")
        detector = ProjectTypeDetector(Path(compose_dir) if compose_dir else None)

        # Determine the target for mode detection
        target = getattr(args, "target", None)

        # Get intelligent mode selection
        if args.mode == "auto":
            selected_mode, detection_reason = detector.get_intelligent_mode(target)
        else:
            selected_mode, detection_reason = detector.get_intelligent_mode(
                target, args.mode
            )

        # Show detection details if requested
        if args.debug_detection:
            console.print(
                f"[dim]Mode selection: {selected_mode} ({detection_reason})[/dim]"
            )

        # Initialize the appropriate manager based on detected/selected mode
        if selected_mode == "quadlet":
            # Use quadlet manager for vLLM services
            manager = QuadletManager()
            container_ops = QuadletOperations(manager)
            display = QuadletDisplayManager(manager)
        else:
            # Use compose manager
            manager = PodmanManager(compose_dir)
            container_ops = ContainerOperations(manager)
            display = DisplayManager(manager)

        # Create command router and execute command
        router = CommandRouter(manager, container_ops, display, selected_mode, detector)
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
