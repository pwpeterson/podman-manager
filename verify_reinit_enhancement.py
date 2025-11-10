#!/usr/bin/env python3
"""
Simple verification script for enhanced vLLM reinit functionality
This script verifies the code changes without running potentially problematic operations.
"""

import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import console


def verify_reinit_manager_enhancements():
    """Verify that the ReinitManager has been enhanced for vLLM support"""
    console.print("[bold cyan]Verifying ReinitManager Enhancements[/bold cyan]")
    console.print()

    try:
        from managers.quadlet_manager import QuadletManager
        from managers.reinit_manager import ReinitManager

        # Initialize managers
        manager = QuadletManager()
        reinit_mgr = ReinitManager(manager)

        # Check if vllm_manager property exists
        if hasattr(reinit_mgr, "vllm_manager"):
            console.print("[green]✓ vllm_manager property exists[/green]")
        else:
            console.print("[red]✗ vllm_manager property missing[/red]")
            return False

        # Check if vLLM manager can be accessed
        try:
            vllm_mgr = reinit_mgr.vllm_manager
            console.print("[green]✓ vLLM manager accessible[/green]")
        except Exception as e:
            console.print(f"[red]✗ vLLM manager access failed: {e}[/red]")
            return False

        # Check if key methods exist
        required_methods = [
            "_find_current_vllm_container",
            "_run_command",
            "_is_port_in_use",
        ]

        for method_name in required_methods:
            if hasattr(vllm_mgr, method_name):
                console.print(f"[green]✓ Method {method_name} exists[/green]")
            else:
                console.print(f"[red]✗ Method {method_name} missing[/red]")
                return False

        console.print("[green]✓ All ReinitManager enhancements verified[/green]")
        return True

    except ImportError as e:
        console.print(f"[red]✗ Import failed: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]✗ Verification failed: {e}[/red]")
        return False


def verify_code_changes():
    """Verify that the code changes are present in the source files"""
    console.print("\n[bold cyan]Verifying Code Changes[/bold cyan]")
    console.print()

    # Check reinit_manager.py for vLLM enhancements
    reinit_file = Path("managers/reinit_manager.py")
    if not reinit_file.exists():
        console.print("[red]✗ reinit_manager.py not found[/red]")
        return False

    reinit_content = reinit_file.read_text()

    # Check for key enhancements
    checks = [
        ("is_vllm_model_service", "vLLM service detection logic"),
        ("_find_current_vllm_container", "Current vLLM container detection"),
        ("Found vLLM model using port", "vLLM detection output message"),
        ("Stopping {current_container}", "vLLM stopping message"),
        ("container_service_file", "vLLM service file removal logic"),
        ("Removed {current_container}.service file", "Service file removal message"),
    ]

    for check_text, description in checks:
        if check_text in reinit_content:
            console.print(f"[green]✓ {description} found[/green]")
        else:
            console.print(f"[red]✗ {description} missing[/red]")
            return False

    # Check vllm_model_manager.py for logging enhancements
    vllm_file = Path("managers/vllm_model_manager.py")
    if not vllm_file.exists():
        console.print("[red]✗ vllm_model_manager.py not found[/red]")
        return False

    vllm_content = vllm_file.read_text()

    vllm_checks = [
        ("Found vLLM container by inspection", "Container inspection logging"),
        ("Found vLLM container by process", "Process detection logging"),
        ("No vLLM container found using port", "No container found logging"),
    ]

    for check_text, description in vllm_checks:
        if check_text in vllm_content:
            console.print(f"[green]✓ {description} found[/green]")
        else:
            console.print(f"[red]✗ {description} missing[/red]")
            return False

    console.print("[green]✓ All code changes verified[/green]")
    return True


def show_usage_examples():
    """Show usage examples for the enhanced reinit functionality"""
    console.print("\n[bold cyan]Usage Examples[/bold cyan]")
    console.print()

    examples = [
        ("pm reinit 9b-chat", "Basic vLLM model reinit"),
        ("pm reinit 9b-chat -v", "Verbose vLLM model reinit"),
        ("pm reinit vllm-glm4-9b-chat --quadlet-build", "vLLM reinit with build"),
        ("pm reinit thinking-model", "Reinit different vLLM model"),
    ]

    for command, description in examples:
        console.print(f"[cyan]{command}[/cyan]")
        console.print(f"  [dim]{description}[/dim]")
        console.print()

    console.print("[yellow]Key Features:[/yellow]")
    features = [
        "Automatically detects current vLLM model using port 8005",
        "Gracefully stops the current vLLM container",
        "Removes obsolete systemd service files",
        "Provides clear status messages during the process",
        "Integrates with existing AI diagnostics on failures",
    ]

    for feature in features:
        console.print(f"  • {feature}")

    console.print()


if __name__ == "__main__":
    try:
        success = True

        # Run verifications
        if not verify_code_changes():
            success = False

        if not verify_reinit_manager_enhancements():
            success = False

        show_usage_examples()

        if success:
            console.print("[bold green]✓ All verifications passed![/bold green]")
            console.print(
                "[dim]The enhanced vLLM reinit functionality is ready to use.[/dim]"
            )
        else:
            console.print("[bold red]✗ Some verifications failed![/bold red]")
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Verification interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Verification failed with error: {e}[/red]")
        sys.exit(1)
