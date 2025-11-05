#!/usr/bin/env python3
"""Example usage of the simplified fuzzy matcher and common actions."""

from core.simple_fuzzy_matcher import find_container
from operations.common_actions import CommonActionsFormatter


def example_usage():
    """Demonstrate the simplified fuzzy matching workflow."""

    print("=== Simplified Fuzzy Matching Example ===\n")

    # Example 1: Direct container lookup
    print("1. Direct container lookup:")
    container = find_container("neo4j")
    if container:
        print(
            f"   Found: {container['name']} ({container['status']}) on port {container['port']}"
        )
        print(f"   Image: {container['image']}")

    print()

    # Example 2: Using with CommonActionsFormatter
    print("2. Using with CommonActionsFormatter:")
    formatter = CommonActionsFormatter()

    # The target 'neo4j' will be fuzzy matched to find the actual container
    # and derive service_name, container_name, and port automatically
    formatter.show_common_actions(target="neo4j")

    print()

    # Example 3: Show how target and service_name are derived
    print("3. How target and service_name are derived:")

    test_targets = ["neo4j", "vllm-qwen", "supabase-db"]

    for target in test_targets:
        container = find_container(target)
        if container:
            # This is how service_name is derived in common_actions.py
            container_name = container["name"]
            simplified_name = (
                container_name.split("-")[-1]
                if "-" in container_name
                else container_name
            )
            service_name = f"{simplified_name}.service"

            print(
                f"   Target: '{target}' -> Container: '{container_name}' -> Service: '{service_name}'"
            )


if __name__ == "__main__":
    example_usage()
