#!/usr/bin/env python3
"""Python version of setup-networks.sh for creating Podman networks from JSON config."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


class NetworkSetupError(Exception):
    """Custom exception for network setup errors."""

    pass


class NetworkManager:
    """Manages Podman network creation from JSON configuration."""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize NetworkManager with config file path.

        Args:
            config_file: Path to JSON config file. Defaults to ~/.config/containers/systemd/networks.config.json
        """
        if config_file:
            self.config_file = Path(config_file)
        else:
            self.config_file = (
                Path.home()
                / ".config"
                / "containers"
                / "systemd"
                / "networks.config.json"
            )

        self.source_config = Path(
            "/home/pwp/srv/local-ai-packaged/quadlets/networks.config.json"
        )
        self.config_data: Dict = {}

    def validate_dependencies(self) -> None:
        """Check if required dependencies are available."""
        # Check if podman is available
        try:
            subprocess.run(
                ["podman", "--version"], capture_output=True, check=True, timeout=10
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            raise NetworkSetupError("Podman is required but not found in PATH")

    def ensure_config_file(self) -> None:
        """Ensure config file exists, copying from source if needed."""
        if not self.config_file.exists():
            # Try to copy from source location
            if self.source_config.exists():
                console.print(
                    f"[yellow]Config file not found at {self.config_file}[/yellow]"
                )
                console.print(f"[blue]Copying from {self.source_config}...[/blue]")

                # Create destination directory if it doesn't exist
                self.config_file.parent.mkdir(parents=True, exist_ok=True)

                try:
                    shutil.copy2(self.source_config, self.config_file)
                    console.print("[green]✓ Config file copied successfully[/green]")
                except Exception as e:
                    raise NetworkSetupError(f"Failed to copy config file: {e}")
            else:
                raise NetworkSetupError(
                    f"Config file not found at {self.config_file} and source file not found at {self.source_config}"
                )

    def load_config(self) -> None:
        """Load and validate the JSON configuration file."""
        self.ensure_config_file()

        try:
            with open(self.config_file, "r") as f:
                self.config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise NetworkSetupError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise NetworkSetupError(f"Error reading config file: {e}")

        # Validate config structure
        if "networks" not in self.config_data:
            raise NetworkSetupError("Config file must contain 'networks' key")

        if not isinstance(self.config_data["networks"], list):
            raise NetworkSetupError("'networks' must be a list")

    def network_exists(self, name: str) -> bool:
        """Check if a Podman network already exists.

        Args:
            name: Network name to check

        Returns:
            True if network exists, False otherwise
        """
        try:
            result = subprocess.run(
                ["podman", "network", "exists", name], capture_output=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False

    def build_create_command(self, network_config: Dict) -> List[str]:
        """Build the podman network create command from network configuration.

        Args:
            network_config: Network configuration dictionary

        Returns:
            List of command arguments
        """
        cmd = ["podman", "network", "create"]

        # Add driver
        if "driver" in network_config:
            cmd.extend(["--driver", network_config["driver"]])

        # Add subnet and gateway from first subnet
        if "subnets" in network_config and network_config["subnets"]:
            subnet_config = network_config["subnets"][0]
            if "subnet" in subnet_config:
                cmd.extend(["--subnet", subnet_config["subnet"]])
            if "gateway" in subnet_config:
                cmd.extend(["--gateway", subnet_config["gateway"]])

        # Add internal flag
        if network_config.get("internal", False):
            cmd.append("--internal")

        # Add disable-dns flag
        if not network_config.get("dns_enabled", True):
            cmd.append("--disable-dns")

        # Add labels
        if "labels" in network_config and network_config["labels"]:
            for key, value in network_config["labels"].items():
                cmd.extend(["--label", f"{key}={value}"])

        # Add options
        if "options" in network_config and network_config["options"]:
            for key, value in network_config["options"].items():
                cmd.extend(["--opt", f"{key}={value}"])

        # Add network name
        cmd.append(network_config["name"])

        return cmd

    def create_network(self, network_config: Dict) -> bool:
        """Create a single network from configuration.

        Args:
            network_config: Network configuration dictionary

        Returns:
            True if network was created, False if it already existed
        """
        name = network_config.get("name")
        if not name:
            raise NetworkSetupError("Network configuration missing 'name' field")

        # Check if network already exists
        if self.network_exists(name):
            console.print(
                f"  ✓ Network '{name}' already exists, skipping...", style="yellow"
            )
            return False

        console.print(f"  → Creating network '{name}'...", style="blue")

        # Build and execute create command
        cmd = self.build_create_command(network_config)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                raise NetworkSetupError(
                    f"Failed to create network '{name}': {result.stderr.strip()}"
                )

            console.print(f"  ✓ Network '{name}' created successfully", style="green")
            return True

        except subprocess.TimeoutExpired:
            raise NetworkSetupError(f"Timeout creating network '{name}'")
        except Exception as e:
            raise NetworkSetupError(f"Error creating network '{name}': {e}")

    def list_networks(self) -> None:
        """Display current Podman networks in a table."""
        try:
            result = subprocess.run(
                ["podman", "network", "ls", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                console.print("[red]Failed to list networks[/red]")
                return

            networks = json.loads(result.stdout)

            if not networks:
                console.print("[yellow]No networks found[/yellow]")
                return

            table = Table(title="Current Podman Networks")
            table.add_column("Name", style="cyan")
            table.add_column("Driver", style="magenta")
            table.add_column("Subnet", style="green")
            table.add_column("Gateway", style="blue")
            table.add_column("Internal", style="yellow")

            for network in networks:
                name = network.get("name", "N/A")
                driver = network.get("driver", "N/A")

                # Extract subnet and gateway info
                subnets = network.get("subnets", [])
                subnet = subnets[0].get("subnet", "N/A") if subnets else "N/A"
                gateway = subnets[0].get("gateway", "N/A") if subnets else "N/A"

                internal = "Yes" if network.get("internal", False) else "No"

                table.add_row(name, driver, subnet, gateway, internal)

            console.print(table)

        except Exception as e:
            console.print(f"[red]Error listing networks: {e}[/red]")

    def setup_networks(self) -> None:
        """Main method to setup all networks from configuration."""
        console.print(
            Panel.fit(
                f"Setting up Podman networks\n" f"Config file: {self.config_file}",
                title="Network Setup",
                border_style="blue",
            )
        )

        networks = self.config_data["networks"]
        network_count = len(networks)

        console.print(f"Found {network_count} network(s) to process\n")

        created_count = 0
        skipped_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            for i, network_config in enumerate(networks):
                name = network_config.get("name", f"network-{i}")
                task = progress.add_task(f"Processing network: {name}", total=1)

                try:
                    was_created = self.create_network(network_config)
                    if was_created:
                        created_count += 1
                    else:
                        skipped_count += 1

                    progress.update(task, completed=1)

                except NetworkSetupError as e:
                    console.print(f"[red]Error: {e}[/red]")
                    progress.update(task, completed=1)

                console.print()  # Add spacing

        # Summary
        console.print(
            Panel.fit(
                f"Network setup complete!\n"
                f"Created: {created_count} networks\n"
                f"Skipped: {skipped_count} networks (already existed)",
                title="Summary",
                border_style="green",
            )
        )

        console.print("\n[bold]Current networks:[/bold]")
        self.list_networks()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Setup Podman networks from JSON configuration"
    )
    parser.add_argument(
        "--config",
        "-c",
        help="Path to JSON config file (default: ~/.config/containers/systemd/networks.config.json)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logger.configure(
            handlers=[
                {
                    "sink": sys.stderr,
                    "format": "{time} | {level} | {message}",
                    "level": "DEBUG",
                }
            ]
        )
    else:
        logger.configure(
            handlers=[
                {
                    "sink": sys.stderr,
                    "format": "{time} | {level} | {message}",
                    "level": "INFO",
                }
            ]
        )

    try:
        manager = NetworkManager(args.config)
        manager.validate_dependencies()
        manager.load_config()
        manager.setup_networks()

    except NetworkSetupError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        logger.exception("Unexpected error occurred")
        sys.exit(1)


if __name__ == "__main__":
    main()
