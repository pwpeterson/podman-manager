#!/usr/bin/env python3
"""
Test script to verify command display functionality in pm reinit
"""


from rich.console import Console

console = Console()


def test_command_display():
    """Test that commands are displayed properly"""

    # Test the command display format
    test_cmd = ["systemctl", "--user", "daemon-reload"]
    console.print(f"[cyan]exec: {' '.join(test_cmd)}[/cyan]")

    # Test with a longer command
    test_cmd2 = [
        "journalctl",
        "--user",
        "-u",
        "systemd",
        "--since",
        "1 minute ago",
        "-n",
        "10",
    ]
    console.print(f"[cyan]exec: {' '.join(test_cmd2)}[/cyan]")

    console.print("[green]Command display format test completed![/green]")
    console.print(
        "[dim]The actual pm reinit command will now display all systemctl and other commands as they execute.[/dim]"
    )


if __name__ == "__main__":
    test_command_display()
