#!/usr/bin/env bash

# Podman Manager Compatibility Wrapper
# This script ensures existing aliases continue to work with both
# the original monolithic script and the new refactored version

# Resolve the real path if this script is a symlink
if [ -L "${BASH_SOURCE[0]}" ]; then
    SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
else
    SCRIPT_PATH="${BASH_SOURCE[0]}"
fi

SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"

# Change to the script directory to ensure proper module resolution
cd "$SCRIPT_DIR"

exec uv run python "$SCRIPT_DIR/podman_manager.py" "$@"
