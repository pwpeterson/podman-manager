# vLLM Quadlet Migration

The podman_manager has been updated to manage vLLM containers as systemd quadlets instead of using podman compose.

## What Changed

### New Architecture
- **QuadletManager**: Manages vLLM services via systemctl --user commands
- **QuadletOperations**: Service lifecycle operations (start, stop, restart, enable, disable)
- **QuadletDisplayManager**: Rich UI display for quadlet services

### Services Managed
- `qwen25-coder` → `vllm-qwen25-coder-32b-instruct-awq-simple.service`
- `proxy` → `vllm-proxy-working.service`
- `delegator` → `vllm-delegator-mcp-simple.service`
- `stack` → `vllm-stack.target` (manages all services together)

### New Commands

#### Service Lifecycle
```bash
pm start stack          # Start all vLLM services
pm stop qwen25-coder    # Stop specific service
pm restart proxy        # Restart proxy service
pm enable stack         # Enable stack to start at boot
pm disable delegator    # Disable delegator from starting at boot
```

#### Service Management
```bash
pm list                 # Show all services and their status
pm list qwen25-coder    # Show specific service details
pm status proxy         # Detailed service status
pm logs delegator --follow  # Follow service logs
```

#### Image Updates
```bash
pm update qwen25-coder  # Update images and restart service
pm auto-update          # Check/enable auto-update timer
pm reload               # Reload systemd daemon
```

### Backward Compatibility

The manager supports both modes:
- `--mode quadlet` (default): Use new quadlet management
- `--mode compose`: Fallback to original compose management

### Usage Examples

```bash
# Start all vLLM services
pm start stack

# Check service status
pm list

# Follow logs for Qwen2.5 Coder
pm logs qwen25-coder --follow

# Update images and restart
pm update proxy

# Enable services to start at boot
pm enable stack

# Show detailed service status
pm status delegator
```

### Benefits of Quadlets

1. **Native systemd integration**: Services managed like any other system service
2. **Boot-time startup**: Can enable services to start automatically
3. **Better logging**: Integrated with journalctl
4. **Dependency management**: systemd handles service dependencies
5. **Auto-updates**: Support for automatic image updates
6. **Resource management**: systemd resource controls

### Migration Notes

- Services are now managed via `systemctl --user` commands
- Logs are accessed via `journalctl --user -u <service>`
- The `vllm-stack.target` provides compose-like group operations
- Auto-update can be enabled with `pm auto-update`
- All container management commands (ps, images, volumes, etc.) still work

### Files Added

- `quadlet_manager.py`: Core quadlet management
- `quadlet_ops.py`: Service operations
- `quadlet_display.py`: Rich UI for quadlets
- `QUADLET_MIGRATION.md`: This documentation

The original compose-based functionality remains available via `--mode compose` for backward compatibility.
