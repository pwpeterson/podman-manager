"""Unified fuzzy matching utility for service and stack names."""

from pathlib import Path
from typing import List, Optional

from config import console


class FuzzyMatcher:
    """Unified fuzzy matching for services and stacks across all commands."""

    def __init__(self, quadlet_manager=None, quadlet_installer=None):
        self.quadlet_manager = quadlet_manager
        self.quadlet_installer = quadlet_installer

    def fuzzy_match_service_or_stack(
        self, partial_name: str, command: str = "install"
    ) -> Optional[str]:
        """
        Find service or stack using fuzzy matching with interactive selection.

        Returns:
            - Full service name (e.g., "vllm-qwen25.service")
            - Stack identifier (e.g., "STACK:local-ai-stack")
            - None if no matches or user cancels
        """
        # First, try to resolve using directory structure and file names
        resolved_name = self._resolve_from_directory_structure(partial_name)
        if resolved_name:
            partial_name = resolved_name

        # Get all available services and stacks
        all_items = self._get_all_available_items()

        # Find exact matches first
        exact_matches = [item for item in all_items if item["name"] == partial_name]
        if len(exact_matches) == 1:
            return self._resolve_match(exact_matches[0])

        # Find partial matches (case-insensitive)
        partial_matches = [
            item for item in all_items if partial_name.lower() in item["name"].lower()
        ]

        # If no partial matches, try prefix matching
        if not partial_matches:
            partial_matches = [
                item
                for item in all_items
                if item["name"].lower().startswith(partial_name.lower())
            ]

        # If still no matches, try fuzzy matching with edit distance
        if not partial_matches:
            partial_matches = self._fuzzy_match_by_distance(partial_name, all_items)

        if len(partial_matches) == 1:
            # Single match found
            matched_item = partial_matches[0]
            return self._resolve_match(matched_item)
        elif len(partial_matches) > 1:
            # Multiple matches - show interactive selection menu
            return self._show_interactive_selection(
                partial_name, partial_matches, command
            )

        # No matches found
        return None

    def _get_all_available_items(self) -> List[dict]:
        """Get all available services and stacks from both manager and installer."""
        items = []

        # Get items from QuadletManager if available
        if self.quadlet_manager:
            # Add services
            for service_name in self.quadlet_manager.quadlet_services.keys():
                items.append(
                    {"name": service_name, "type": "service", "source": "manager"}
                )

            # Add stacks
            for stack_name in self.quadlet_manager.stack_services.keys():
                items.append({"name": stack_name, "type": "stack", "source": "manager"})

            # Add stack aliases (only if not already present)
            alias_items = [
                {"name": "stack", "type": "stack", "source": "manager"},
                {"name": "vllm-stack", "type": "stack", "source": "manager"},
            ]
            for alias_item in alias_items:
                if not any(item["name"] == alias_item["name"] for item in items):
                    items.append(alias_item)

        # Get items from QuadletInstaller if available
        if self.quadlet_installer:
            # Add available stacks
            try:
                available_stacks = self.quadlet_installer.discover_stacks()
                for stack_name in available_stacks:
                    # Only add if not already present
                    if not any(item["name"] == stack_name for item in items):
                        items.append(
                            {"name": stack_name, "type": "stack", "source": "installer"}
                        )
            except Exception:
                pass

            # Add available services
            try:
                available_stacks = self.quadlet_installer.discover_stacks()
                for stack_name in available_stacks:
                    services = self.quadlet_installer.get_service_names(stack_name)
                    for service_name in services:
                        # Only add if not already present
                        if not any(item["name"] == service_name for item in items):
                            items.append(
                                {
                                    "name": service_name,
                                    "type": "service",
                                    "source": "installer",
                                }
                            )
            except Exception:
                pass

        return items

    def _fuzzy_match_by_distance(
        self, partial_name: str, all_items: List[dict]
    ) -> List[dict]:
        """Find items using Levenshtein distance."""

        def levenshtein_distance(s1: str, s2: str) -> int:
            """Calculate Levenshtein distance between two strings"""
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
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

        # Find items with small edit distance (max 2 for reasonable matches)
        fuzzy_matches = []
        for item in all_items:
            distance = levenshtein_distance(partial_name.lower(), item["name"].lower())
            if (
                distance <= 2 and len(partial_name) >= 3
            ):  # Only for reasonable length inputs
                fuzzy_matches.append((item, distance))

        # Sort by distance and take best matches
        fuzzy_matches.sort(key=lambda x: x[1])
        return [match[0] for match in fuzzy_matches[:5]]  # Top 5 matches

    def _show_interactive_selection(
        self, partial_name: str, matches: List[dict], command: str = "install"
    ) -> Optional[str]:
        """Show interactive selection menu for multiple matches."""
        # Determine if we have services, stacks, or both
        has_services = any(item["type"] == "service" for item in matches)
        has_stacks = any(item["type"] == "stack" for item in matches)

        if has_services and has_stacks:
            console.print()
            console.print(
                f"\n[green]Multiple services and stacks match '{partial_name}':[/green]"
            )
            console.print()
        elif has_services:
            console.print()
            console.print(f"[green]Multiple services match '{partial_name}':[/green]")
            console.print()
        else:
            console.print()
            console.print(f"[green]Multiple stacks match '{partial_name}':[/green]")
            console.print()

        console.print(
            "[green]Please specify the full name or use the number prefix:[/green]"
        )

        # Show numbered options
        for i, item in enumerate(matches, 1):
            item_type = "stack" if item["type"] == "stack" else "service"
            console.print(
                f"  {i}. [cyan]pm {command} {item['name']}[/cyan] [dim]({item_type})[/dim]"
            )

        # Interactive selection
        try:
            choice = input(
                f"Select {('service' if has_services else 'stack')} (1-{len(matches)}) or press Enter to cancel: "
            ).strip()

            if not choice:
                return "CANCELLED"

            if choice.isdigit():
                selection = int(choice)
                if 1 <= selection <= len(matches):
                    selected_item = matches[selection - 1]
                    return self._resolve_match(selected_item)
                else:
                    console.print(
                        f"[red]Invalid selection '{selection}'. Choose 1-{len(matches)}[/red]"
                    )
                    return None
            else:
                console.print(
                    "[red]Please enter a number or press Enter to cancel[/red]"
                )
                return None

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Selection cancelled[/yellow]")
            return "CANCELLED"

    def _resolve_match(self, item: dict) -> str:
        """Resolve a matched item to the appropriate return value."""
        if item["type"] == "stack":
            if item["source"] == "manager" and self.quadlet_manager:
                # For manager, return stack identifier
                if item["name"] in ["stack", "vllm-stack"]:
                    return self.quadlet_manager.stack_target
                else:
                    return f"STACK:{item['name']}"
            else:
                # For installer, return the stack name directly
                return item["name"]
        else:  # service
            if item["source"] == "manager" and self.quadlet_manager:
                # Return full service name from manager
                return self.quadlet_manager.quadlet_services.get(
                    item["name"], f"{item['name']}.service"
                )
            else:
                # Return service name for installer
                return item["name"]

    def _resolve_from_directory_structure(self, partial_name: str) -> Optional[str]:
        """Resolve service/stack names using directory structure and file names."""
        quadlets_base_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")

        if not quadlets_base_dir.exists():
            return None

        try:
            # Get all stack directories
            stack_dirs = [d for d in quadlets_base_dir.iterdir() if d.is_dir()]

            # 1. Check for exact stack name match
            for stack_dir in stack_dirs:
                if partial_name == stack_dir.name:
                    return f"STACK:{stack_dir.name}"

            # 2. Check if partial_name matches first part of stack directory name
            for stack_dir in stack_dirs:
                stack_name = stack_dir.name
                # Check if input matches the beginning of stack name (e.g., "local" matches "local-ai-stack")
                if (
                    stack_name.startswith(f"{partial_name}-")
                    or partial_name in stack_name.split("-")[0]
                ):
                    return f"STACK:{stack_name}"

            # 3. Look for service files in all stack directories
            all_services = {}
            for stack_dir in stack_dirs:
                try:
                    # Look for .container, .service, or Dockerfile.* files
                    service_files = []
                    service_files.extend(stack_dir.glob("*.container"))
                    service_files.extend(stack_dir.glob("*.service"))
                    service_files.extend(stack_dir.glob("Dockerfile.*"))

                    for service_file in service_files:
                        if service_file.name.startswith("Dockerfile."):
                            # Extract service name from Dockerfile.service-name
                            service_name = service_file.name.replace("Dockerfile.", "")
                        else:
                            # Extract service name from service-name.container or service-name.service
                            service_name = service_file.stem

                        all_services[service_name] = stack_dir.name
                except Exception:
                    continue

            # 4. Check for exact service name match
            if partial_name in all_services:
                return partial_name

            # 5. Check for partial service name matches
            matching_services = []
            for service_name in all_services.keys():
                if partial_name.lower() in service_name.lower():
                    matching_services.append(service_name)

            # If single match, return it
            if len(matching_services) == 1:
                return matching_services[0]

            # 6. Check for prefix matches in service names
            prefix_matches = []
            for service_name in all_services.keys():
                if service_name.lower().startswith(partial_name.lower()):
                    prefix_matches.append(service_name)

            if len(prefix_matches) == 1:
                return prefix_matches[0]

            # 7. Try fuzzy matching with edit distance for services
            if len(partial_name) >= 3:  # Only for reasonable length inputs
                fuzzy_matches = []
                for service_name in all_services.keys():
                    distance = self._levenshtein_distance(
                        partial_name.lower(), service_name.lower()
                    )
                    if distance <= 2:  # Allow up to 2 character differences
                        fuzzy_matches.append((service_name, distance))

                # Sort by distance and return best match if unique
                fuzzy_matches.sort(key=lambda x: x[1])
                if len(fuzzy_matches) == 1:
                    return fuzzy_matches[0][0]

            return None

        except Exception as e:
            console.print(f"[dim]Error scanning directory structure: {e}[/dim]")
            return None

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
