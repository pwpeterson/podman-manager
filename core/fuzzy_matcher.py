"""Unified fuzzy matching utility for service and stack names."""

from typing import List, Optional

from core.config import console
from core.service_discovery import get_service_discovery


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
            # Handle STACK: prefix from directory resolution
            if resolved_name.startswith("STACK:"):
                stack_name = resolved_name[6:]  # Remove "STACK:" prefix
                # Look for this specific stack in our items
                all_items = self._get_all_available_items()
                stack_matches = [
                    item
                    for item in all_items
                    if item["name"] == stack_name and item["type"] == "stack"
                ]
                if len(stack_matches) == 1:
                    return self._resolve_match(stack_matches[0])
                # If not found as stack, continue with normal flow using the stack name
                partial_name = stack_name
            else:
                # For service names, use as-is
                partial_name = resolved_name

        # Get all available services and stacks
        all_items = self._get_all_available_items()

        # PRIORITY 1: Check for exact stack matches first
        if self.quadlet_manager:
            # Check if it's any discovered stack name (exact match)
            if partial_name in self.quadlet_manager.stack_services:
                return f"STACK:{partial_name}"

            # Check if target ends with -stack and exists in our discovered stacks
            if (
                partial_name.endswith("-stack")
                and partial_name in self.quadlet_manager.stack_services
            ):
                return f"STACK:{partial_name}"

            # Handle stack name mapping (shortened names)
            if not partial_name.endswith("-stack"):
                stack_variant = f"{partial_name}-stack"
                if stack_variant in self.quadlet_manager.stack_services:
                    return f"STACK:{stack_variant}"

                # Also check if any stack starts with the target name
                for stack_name in self.quadlet_manager.stack_services.keys():
                    if stack_name.startswith(f"{partial_name}-"):
                        return f"STACK:{stack_name}"

            # Check for stack names that contain the partial_name as a prefix
            # This handles cases like "sys-services" matching "sys-services-stack"
            for stack_name in self.quadlet_manager.stack_services.keys():
                # Check if partial_name is a meaningful prefix of the stack name
                if stack_name.startswith(partial_name) and len(partial_name) >= 3:
                    # Ensure it's a logical word boundary (not just substring)
                    if len(stack_name) == len(partial_name) or stack_name[
                        len(partial_name) : len(partial_name) + 1
                    ] in ["-", "_"]:
                        return f"STACK:{stack_name}"

            # Check if it's a short name in quadlet services
            if partial_name in self.quadlet_manager.quadlet_services:
                return self.quadlet_manager.quadlet_services[partial_name]

            # Check if it's already a full service name in quadlet services
            if partial_name in self.quadlet_manager.quadlet_services.values():
                return partial_name

            # Check if it's any stack target
            if (
                partial_name == "stack"
                or partial_name == "vllm-stack"
                or partial_name == self.quadlet_manager.stack_target
            ):
                return self.quadlet_manager.stack_target

            # For any other service, try as-is first
            if partial_name.endswith(".service") or partial_name.endswith(".target"):
                return partial_name

        # PRIORITY 2: Enhanced stack prefix matching using all_items
        stack_prefix_matches = [
            item
            for item in all_items
            if item["type"] == "stack"
            and item["name"].startswith(partial_name)
            and len(partial_name) >= 3
            and (
                len(item["name"]) == len(partial_name)
                or item["name"][len(partial_name) : len(partial_name) + 1] in ["-", "_"]
            )
        ]
        if len(stack_prefix_matches) == 1:
            return self._resolve_match(stack_prefix_matches[0])

        # PRIORITY 3: Find exact matches
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
            # PRIORITIZE STACKS: If we have both stacks and services, prefer stacks
            stack_matches = [
                item for item in partial_matches if item["type"] == "stack"
            ]
            if len(stack_matches) == 1:
                # Single stack match found among multiple matches - prioritize it
                return self._resolve_match(stack_matches[0])
            elif len(stack_matches) > 1:
                # Multiple stack matches - show selection for stacks only
                return self._show_interactive_selection(
                    partial_name, stack_matches, command
                )
            # No stack matches or multiple service matches - show interactive selection menu
            return self._show_interactive_selection(
                partial_name, partial_matches, command
            )

        # No matches found
        return None

    def _get_all_available_items(self) -> List[dict]:
        """Get all available services and stacks from unified discovery."""
        items = []
        discovery = get_service_discovery()

        # Add services from discovery
        for service_name in discovery.quadlet_services.keys():
            items.append(
                {"name": service_name, "type": "service", "source": "discovery"}
            )

        # Add stacks from discovery
        for stack_name in discovery.stack_services.keys():
            items.append({"name": stack_name, "type": "stack", "source": "discovery"})

        # Add stack aliases for backward compatibility
        alias_items = [
            {"name": "stack", "type": "stack", "source": "discovery"},
            {"name": "vllm-stack", "type": "stack", "source": "discovery"},
        ]
        for alias_item in alias_items:
            if not any(item["name"] == alias_item["name"] for item in items):
                items.append(alias_item)

        # Fallback to legacy sources if discovery is empty
        if not items:
            items = self._get_legacy_items()

        return items

    def _get_legacy_items(self) -> List[dict]:
        """Fallback to legacy item discovery methods."""
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

        # Get items from QuadletInstaller if available
        if self.quadlet_installer:
            try:
                available_stacks = self.quadlet_installer.discover_stacks()
                for stack_name in available_stacks:
                    if not any(item["name"] == stack_name for item in items):
                        items.append(
                            {"name": stack_name, "type": "stack", "source": "installer"}
                        )

                for stack_name in available_stacks:
                    services = self.quadlet_installer.get_service_names(stack_name)
                    for service_name in services:
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
            console.print(
                f"\n[green]Multiple services and stacks match '{partial_name}':[/green]"
            )
        elif has_services:
            console.print(f"\n[green]Multiple services match '{partial_name}':[/green]")
        else:
            console.print(f"\n[green]Multiple stacks match '{partial_name}':[/green]")

        console.print(
            "[green]Please specify the full name or use the number prefix:[/green]"
        )

        # Show numbered options
        for i, item in enumerate(matches, 1):
            item_type = "stack" if item["type"] == "stack" else "service"
            console.print(
                f"  {i}. [cyan]pm {command} {item['name']}[/cyan] [dim]({item_type})[/dim]"
            )

        # Interactive selection with single prompt
        while True:
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
                        resolved = self._resolve_match(selected_item)
                        console.print(f"[dim]Selected: {selected_item['name']}[/dim]")
                        return resolved
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
                return "CANCELLED"

    def _resolve_match(self, item: dict) -> str:
        """Resolve a matched item to the appropriate return value."""
        discovery = get_service_discovery()

        if item["type"] == "stack":
            if item["source"] == "manager" and self.quadlet_manager:
                # For manager, return stack identifier
                if item["name"] in ["stack", "vllm-stack"]:
                    return self.quadlet_manager.stack_target
                else:
                    return f"STACK:{item['name']}"
            elif item["source"] == "discovery":
                # For discovery, handle special cases
                if item["name"] in ["stack", "vllm-stack"]:
                    # Return the first available stack target or default
                    if self.quadlet_manager:
                        return self.quadlet_manager.stack_target
                    else:
                        return "vllm-stack.target"
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
            elif item["source"] == "discovery":
                # Return full service name from discovery
                return discovery.quadlet_services.get(
                    item["name"], f"{item['name']}.service"
                )
            else:
                # Return service name for installer
                return item["name"]

    def _resolve_from_directory_structure(self, partial_name: str) -> Optional[str]:
        """Resolve service/stack names using unified service discovery."""
        discovery = get_service_discovery()
        return discovery.resolve_from_directory_structure(partial_name)

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
