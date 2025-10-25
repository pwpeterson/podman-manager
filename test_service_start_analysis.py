#!/usr/bin/env python3
"""
Test script to verify AI analysis integration for service start failures.
This simulates the error scenario described in the task.
"""

import sys
from pathlib import Path

# Add the project root to Python path before any local imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def test_service_start_failure_analysis():
    """Test the AI analysis for service start failures"""
    # Import here to avoid E402 issues
    from core.config import console
    from managers.quadlet_manager import QuadletManager

    console.print(
        "[bright_yellow]Testing AI analysis for service start failures...[/bright_yellow]"
    )

    # Create a QuadletManager instance
    manager = QuadletManager()

    # Test the AI analysis method directly
    try:
        manager._trigger_service_start_ai_analysis(
            target="taskflow-backend",
            service_name="taskflow-backend.service",
            start_command="systemctl --user start taskflow-backend.service",
            error_code=1,
            systemd_error="Job for taskflow-backend.service failed because the control process exited with error code.",
        )
        console.print("[green]✅ AI analysis integration test completed[/green]")
        return True
    except Exception as e:
        console.print(f"[red]❌ AI analysis test failed: {e}[/red]")
        return False


if __name__ == "__main__":
    success = test_service_start_failure_analysis()
    sys.exit(0 if success else 1)
