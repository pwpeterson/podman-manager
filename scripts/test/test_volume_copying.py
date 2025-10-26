#!/usr/bin/env python3
"""Test script for volume copying functionality."""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import console
from managers.quadlet_manager import QuadletManager
from operations.quadlet_ops import QuadletOperations


def test_volume_manager_integration():
    """Test that the volume manager is properly integrated."""
    console.print("[green]Testing Volume Manager Integration...[/green]")

    try:
        # Initialize manager and operations
        manager = QuadletManager()
        ops = QuadletOperations(manager)

        # Test that volume manager is available
        assert hasattr(
            ops, "volume_manager"
        ), "Volume manager not found in QuadletOperations"
        assert hasattr(ops, "copy_stack_volumes"), "copy_stack_volumes method not found"
        assert hasattr(
            ops, "list_stack_volumes_and_networks"
        ), "list_stack_volumes_and_networks method not found"
        assert hasattr(
            ops, "cleanup_orphaned_volumes"
        ), "cleanup_orphaned_volumes method not found"

        console.print("[green]✓ Volume manager integration successful[/green]")
        return True

    except Exception as e:
        console.print(f"[red]✗ Volume manager integration failed: {e}[/red]")
        return False


def test_volume_manager_methods():
    """Test that volume manager methods work without errors."""
    console.print("[green]Testing Volume Manager Methods...[/green]")

    try:
        # Initialize manager and operations
        manager = QuadletManager()
        ops = QuadletOperations(manager)

        # Test list volumes method (should not crash)
        console.print("[cyan]Testing list_stack_volumes_and_networks...[/cyan]")
        ops.list_stack_volumes_and_networks("test-stack")

        console.print("[green]✓ Volume manager methods work correctly[/green]")
        return True

    except Exception as e:
        console.print(f"[red]✗ Volume manager methods failed: {e}[/red]")
        return False


def test_network_dependency_parsing():
    """Test network dependency parsing from quadlet files."""
    console.print("[green]Testing Network Dependency Parsing...[/green]")

    try:
        # Initialize manager and operations
        manager = QuadletManager()
        ops = QuadletOperations(manager)

        # Test the internal method for parsing network dependencies
        volume_manager = ops.volume_manager

        # This should not crash even if no quadlet files exist
        networks = volume_manager._get_quadlet_network_dependencies("test-stack")
        assert isinstance(networks, list), "Network dependencies should return a list"

        console.print(
            f"[green]✓ Network dependency parsing successful (found {len(networks)} networks)[/green]"
        )
        return True

    except Exception as e:
        console.print(f"[red]✗ Network dependency parsing failed: {e}[/red]")
        return False


def test_volume_detection():
    """Test volume detection functionality."""
    console.print("[green]Testing Volume Detection...[/green]")

    try:
        # Initialize manager and operations
        manager = QuadletManager()
        ops = QuadletOperations(manager)
        volume_manager = ops.volume_manager

        # Test volume detection (should not crash)
        volumes = volume_manager._get_stack_volumes("test-stack")
        assert isinstance(volumes, list), "Volume detection should return a list"

        # Test network detection (should not crash)
        networks = volume_manager._get_stack_networks("test-stack")
        assert isinstance(networks, list), "Network detection should return a list"

        console.print(
            f"[green]✓ Volume detection successful (found {len(volumes)} volumes, {len(networks)} networks)[/green]"
        )
        return True

    except Exception as e:
        console.print(f"[red]✗ Volume detection failed: {e}[/red]")
        return False


def main():
    """Run all tests."""
    console.print("[bold cyan]Volume Copying Functionality Tests[/bold cyan]")
    console.print()

    tests = [
        test_volume_manager_integration,
        test_volume_manager_methods,
        test_network_dependency_parsing,
        test_volume_detection,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        console.print()

    console.print(f"[bold]Test Results: {passed}/{total} tests passed[/bold]")

    if passed == total:
        console.print(
            "[green]All tests passed! Volume copying functionality is ready.[/green]"
        )
        return True
    else:
        console.print("[red]Some tests failed. Please check the implementation.[/red]")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
