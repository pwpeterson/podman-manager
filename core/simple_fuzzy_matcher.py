"""Simplified fuzzy matching utility that returns container objects."""

from pathlib import Path
from typing import Dict, List, Optional

from core.config import console
from utils.secure_subprocess import podman_cmd


class SimpleFuzzyMatcher:
    """Simplified fuzzy matcher that returns container objects with name, port, image, and status."""

    def __init__(self):
        self.systemd_dir = Path("/etc/containers/systemd")

    def find_container(self, partial_name: str) -> Optional[Dict[str, str]]:
        """
        Find a container using fuzzy matching and return container object.

        Returns:
            Dict with keys: name, port, image, status
            None if no match found
        """
        # Get all container files
        container_files = self._get_container_files()

        if not container_files:
            return None

        # Find matches
        matches = self._find_matches(partial_name, container_files)

        if not matches:
            return None
        elif len(matches) == 1:
            return self._create_container_object(matches[0])
        else:
            # Multiple matches - show interactive selection
            return self._show_interactive_selection(partial_name, matches)

    def _get_container_files(self) -> List[Path]:
        """Get all .container files from systemd directory."""
        if not self.systemd_dir.exists():
            return []

        return list(self.systemd_dir.glob("*.container"))

    def _find_matches(
        self, partial_name: str, container_files: List[Path]
    ) -> List[Path]:
        """Find matching container files using fuzzy logic."""
        matches = []

        # Extract container names from file names (remove .container extension)
        container_names = [(f, f.stem) for f in container_files]

        # 1. Exact match
        exact_matches = [f for f, name in container_names if name == partial_name]
        if exact_matches:
            return exact_matches[:1]  # Return first exact match

        # 2. Partial match (case-insensitive)
        partial_matches = [
            f for f, name in container_names if partial_name.lower() in name.lower()
        ]
        if len(partial_matches) == 1:
            return partial_matches
        elif partial_matches:
            matches.extend(partial_matches)

        # 3. Prefix match
        if not matches:
            prefix_matches = [
                f
                for f, name in container_names
                if name.lower().startswith(partial_name.lower())
            ]
            if prefix_matches:
                matches.extend(prefix_matches)

        # 4. Fuzzy match with edit distance (for inputs >= 3 chars)
        if not matches and len(partial_name) >= 3:
            fuzzy_matches = []
            for f, name in container_names:
                distance = self._levenshtein_distance(
                    partial_name.lower(), name.lower()
                )
                if distance <= 2:  # Allow up to 2 character differences
                    fuzzy_matches.append((f, distance))

            # Sort by distance and take best matches
            fuzzy_matches.sort(key=lambda x: x[1])
            matches.extend([match[0] for match in fuzzy_matches[:5]])

        return matches

    def _show_interactive_selection(
        self, partial_name: str, matches: List[Path]
    ) -> Optional[Dict[str, str]]:
        """Show interactive selection menu for multiple matches."""
        console.print(f"\n[green]Multiple containers match '{partial_name}':[/green]")
        console.print("[green]Please select one:[/green]")

        # Show numbered options
        for i, container_file in enumerate(matches, 1):
            container_name = container_file.stem
            console.print(f"  {i}. [cyan]{container_name}[/cyan]")

        # Interactive selection
        while True:
            try:
                choice = input(
                    f"Select container (1-{len(matches)}) or press Enter to cancel: "
                ).strip()

                if not choice:
                    return None

                if choice.isdigit():
                    selection = int(choice)
                    if 1 <= selection <= len(matches):
                        selected_file = matches[selection - 1]
                        console.print(f"[dim]Selected: {selected_file.stem}[/dim]")
                        return self._create_container_object(selected_file)
                    else:
                        console.print(
                            f"[red]Invalid selection '{selection}'. Choose 1-{len(matches)}[/red]"
                        )
                        continue
                else:
                    console.print(
                        "[red]Please enter a number or press Enter to cancel[/red]"
                    )
                    continue

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Selection cancelled[/yellow]")
                return None

    def _create_container_object(self, container_file: Path) -> Dict[str, str]:
        """Create container object from .container file."""
        container_name = container_file.stem

        # Parse container file to extract information
        image = self._extract_image(container_file)
        port = self._extract_port(container_file)
        status = self._get_container_status(container_name)

        return {"name": container_name, "port": port, "image": image, "status": status}

    def _extract_image(self, container_file: Path) -> str:
        """Extract Image from container file."""
        try:
            content = container_file.read_text()
            for line in content.split("\n"):
                if line.strip().startswith("Image="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            pass
        return "unknown"

    def _extract_port(self, container_file: Path) -> str:
        """Extract first published port from container file."""
        try:
            content = container_file.read_text()
            for line in content.split("\n"):
                if line.strip().startswith("PublishPort="):
                    port_mapping = line.split("=", 1)[1].strip()
                    # Extract host port from mapping like "8001:8000" or "7474:7474"
                    if ":" in port_mapping:
                        return port_mapping.split(":")[0]
                    return port_mapping
        except Exception:
            pass
        return "unknown"

    def _get_container_status(self, container_name: str) -> str:
        """Get container status using podman ps."""
        try:
            # Try to get status from podman ps -a
            result = podman_cmd(
                [
                    "ps",
                    "-a",
                    "--format",
                    "{{.Names}} {{.Status}}",
                    "--filter",
                    f"name={container_name}",
                ],
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if line.strip():
                        parts = line.strip().split(" ", 1)
                        if len(parts) >= 2 and parts[0] == container_name:
                            status = parts[1]
                            # Simplify status
                            if "Up" in status:
                                return "running"
                            elif "Exited" in status:
                                return "stopped"
                            else:
                                return status.lower()

                # If we found output but no exact match, container might exist but with different status
                return "unknown"
            else:
                # Container not found in podman ps -a
                return "not_created"

        except Exception:
            return "unknown"

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]


# Convenience function
def find_container(partial_name: str) -> Optional[Dict[str, str]]:
    """Convenience function to find a container."""
    matcher = SimpleFuzzyMatcher()
    return matcher.find_container(partial_name)
