# Volume Copying Guide

This guide explains how to use the new volume copying functionality that automatically copies share networks when stack volumes are copied.

## Overview

The volume copying feature allows you to copy all volumes and their associated share networks from one stack to another. This is particularly useful when:

- Creating development/testing environments from production stacks
- Migrating data between different stack configurations
- Backing up stack data with network dependencies
- Setting up multiple instances of the same stack

## Key Features

- **Automatic Network Copying**: Share networks are automatically copied when volumes are copied
- **Dependency Resolution**: Analyzes quadlet `.container` files to identify network dependencies
- **Smart Naming**: Automatically renames volumes and networks to match the target stack
- **Conflict Handling**: Skips existing volumes/networks to avoid conflicts
- **Progress Tracking**: Shows detailed progress and copy plans

## Available Commands

### Copy Volumes

Copy all volumes from a source stack to a target stack, including share networks:

```bash
pm copy-volumes <source_stack> <target_stack>
```

**Examples:**
```bash
# Copy volumes from vllm-stack to vllm-dev-stack
pm copy-volumes vllm-stack vllm-dev-stack

# Copy volumes from local-ai-stack to local-ai-test-stack
pm copy-volumes local-ai-stack local-ai-test-stack

# Verbose output
pm copy-volumes vllm-stack vllm-backup-stack -v
```

### List Volumes and Networks

List all volumes and networks for a specific stack:

```bash
pm list-volumes <stack_name>
```

**Examples:**
```bash
# List volumes and networks for vllm-stack
pm list-volumes vllm-stack

# List with verbose output
pm list-volumes local-ai-stack -v
```

### Cleanup Orphaned Volumes

Clean up volumes that are no longer used by any containers in the stack:

```bash
pm cleanup-volumes <stack_name>
```

**Examples:**
```bash
# Clean up orphaned volumes for vllm-stack
pm cleanup-volumes vllm-stack

# Clean up with verbose output
pm cleanup-volumes local-ai-stack -v
```

## How It Works

### Volume Detection

The system identifies stack volumes by:
1. Querying podman for all volumes
2. Filtering volumes that match the stack name pattern
3. Including volumes that contain the stack prefix in their name

### Network Detection

The system identifies share networks through:
1. **Runtime Detection**: Querying podman for existing networks
2. **Quadlet Analysis**: Parsing `.container` files for `Network=` entries
3. **Dependency Resolution**: Combining both sources for complete coverage

### Copy Process

1. **Analysis Phase**:
   - Scan source stack for volumes and networks
   - Parse quadlet files for network dependencies
   - Generate target names based on stack naming patterns

2. **Planning Phase**:
   - Display copy plan showing what will be copied
   - Check for existing targets to avoid conflicts

3. **Execution Phase**:
   - Copy networks first (volumes may depend on them)
   - Copy volumes with data using temporary containers
   - Preserve network configurations when possible

### Network Copying Details

When copying networks, the system:
- Inspects source network configuration (subnet, driver, etc.)
- Creates target network with similar configuration
- Handles missing source networks gracefully
- Preserves custom network settings

### Volume Copying Details

When copying volumes, the system:
- Creates new target volume
- Uses Alpine container to copy data: `cp -a /source/. /target/`
- Preserves file permissions and ownership
- Provides progress feedback for large copies
- Cleans up on failure

## Network Dependency Resolution

The system analyzes quadlet `.container` files to identify network dependencies:

```ini
[Container]
Image=myapp:latest
Network=myapp-network
Volume=myapp-data:/data
```

In this example, `myapp-network` would be identified as a dependency and copied along with any volumes.

## Naming Conventions

Volumes and networks are renamed using stack-based patterns:

- **Source**: `vllm-postgres-data` → **Target**: `vllm-dev-postgres-data`
- **Source**: `local-ai-network` → **Target**: `local-ai-test-network`

The system replaces the source stack prefix with the target stack prefix.

## Error Handling

- **Missing Networks**: Creates basic networks if source network doesn't exist
- **Existing Targets**: Skips copying if target already exists
- **Copy Failures**: Cleans up partial copies and reports errors
- **Timeout Handling**: 5-minute timeout for large volume copies

## Best Practices

1. **Stop Services First**: Stop services in both source and target stacks before copying
2. **Check Dependencies**: Use `pm list-volumes` to understand what will be copied
3. **Test Copies**: Use development stacks for testing before production copies
4. **Monitor Progress**: Use `-v` flag for detailed progress information
5. **Cleanup Regularly**: Use `pm cleanup-volumes` to remove unused volumes

## Troubleshooting

### Common Issues

**Volume copy fails with permission errors:**
```bash
# Ensure podman has access to volume data
sudo chown -R $(id -u):$(id -g) ~/.local/share/containers/storage/volumes/
```

**Network already exists:**
- The system will skip existing networks automatically
- Use `podman network rm <network_name>` to remove if needed

**Large volume copy times out:**
- The timeout is set to 5 minutes (300 seconds)
- For very large volumes, consider manual copying

### Debugging

Use verbose mode to see detailed execution:
```bash
pm copy-volumes source-stack target-stack -v
```

This shows:
- All podman commands being executed
- Network configuration details
- Volume copy progress
- Error details

## Integration with Existing Commands

The volume copying functionality integrates with existing podman manager commands:

- `pm volumes` - Lists all volumes (existing command)
- `pm networks` - Lists all networks (existing command)
- `pm list-volumes <stack>` - Lists volumes/networks for specific stack (new)
- `pm copy-volumes <source> <target>` - Copies volumes and networks (new)
- `pm cleanup-volumes <stack>` - Cleans up orphaned volumes (new)

## Technical Implementation

The functionality is implemented in:
- `operations/volume_manager.py` - Core volume/network management
- `operations/quadlet_ops.py` - Integration with quadlet operations
- `cli/command_router.py` - Command routing
- `cli/parser.py` - Argument parsing

Key classes:
- `VolumeNetworkManager` - Main volume/network operations
- `QuadletOperations` - Integration point for volume operations
