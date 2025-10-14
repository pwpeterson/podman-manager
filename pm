#!/usr/bin/env bash

# Podman Manager Compatibility Wrapper
# This script ensures existing aliases continue to work with both
# the original monolithic script and the new refactored version

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the script directory to ensure proper module resolution
cd "$SCRIPT_DIR"

exec uv run python "$SCRIPT_DIR/podman_manager.py" "$@"
