# STDIO Services Detection

## Overview

STDIO services are services that run via `podman run` with the `--rm` flag and are not managed by systemd. These services are typically MCP (Model Context Protocol) servers that communicate via standard input/output.

## Configuration

STDIO services are defined in `stdio_services_config.json` at the project root:

```json
{
  "stdio_services": {
    "service-name": {
      "description": "Service description",
      "container_name": "container-name",
      "image": "localhost/image-name:latest",
      "managed_by": "stdio",
      "stack": "stack-name",
      "run_command": "podman run command...",
      "notes": "Additional notes"
    }
  },
  "detection_patterns": {
    "container_name_patterns": ["^pattern$"],
    "image_patterns": ["pattern"]
  }
}
```

## Example: MCP Model Proxy Assistant

```json
{
  "stdio_services": {
    "mcp-model-proxy-assistant": {
      "description": "MCP Model Proxy Assistant - STDIO service",
      "container_name": "mcp-model-proxy-assistant",
      "image": "localhost/mcp-model-proxy-assistant:latest",
      "managed_by": "stdio",
      "stack": "mcp-services-stack",
      "run_command": "podman run --rm -i --network=host -e MODEL_PROXY_URL=http://localhost:8002 localhost/mcp-model-proxy-assistant:latest",
      "notes": "Runs via podman with --rm flag, not managed by systemd"
    }
  }
}
```

## Display in `pm list`

STDIO services are displayed with special formatting:

- **Service Name**: Shown in cyan color
- **systemd Column**: Shows `stdio` in green (not managed by systemd)
- **podman ps Column**: Shows `not applicable` in green (container is ephemeral with --rm flag)

Example output:
```
Stacks & Services              systemd    podman ps
mcp-services-stack
  mcp-model-proxy-assistant    stdio      not applicable
```

## Service Discovery

The `ServiceDiscovery` class automatically:

1. Loads STDIO services from `stdio_services_config.json`
2. Adds them to the appropriate stacks
3. Marks them with `stdio: true` in service status
4. Provides helper methods:
   - `is_stdio_service(service_name)` - Check if service is STDIO
   - `get_stdio_service_info(service_name)` - Get STDIO service config

## Adding New STDIO Services

To add a new STDIO service:

1. Add entry to `stdio_services_config.json`:
```json
{
  "stdio_services": {
    "your-service-name": {
      "description": "Your service description",
      "container_name": "your-container-name",
      "image": "localhost/your-image:latest",
      "managed_by": "stdio",
      "stack": "your-stack-name",
      "run_command": "podman run --rm -i ... your-image:latest",
      "notes": "Additional information"
    }
  }
}
```

2. The service will automatically appear in `pm list` output

## Detection Patterns

The `detection_patterns` section allows for automatic detection of STDIO services based on:

- **container_name_patterns**: Regex patterns for container names
- **image_patterns**: Regex patterns for image names

These patterns can be used for future automatic detection features.

## Implementation Details

### Files Modified

1. **core/service_discovery.py**
   - Added `stdio_services` dictionary
   - Added `_discover_stdio_services()` method
   - Added `is_stdio_service()` and `get_stdio_service_info()` helpers

2. **operations/quadlet_display.py**
   - Added `_get_stdio_service_status()` method
   - Updated `_get_service_status_columns()` to detect STDIO services
   - Updated service color coding to show STDIO services in cyan

3. **stdio_services_config.json**
   - Configuration file for STDIO services

### Status Representation

STDIO services have a special status structure:
```python
{
    "installed": False,  # Not installed via systemd
    "source": False,     # Not in quadlet source
    "stdio": True        # Managed via STDIO
}
```

## Testing

Run the test script to verify STDIO service detection:

```bash
python test_stdio_detection.py
```

This will show:
- Discovered STDIO services
- Service status details
- Stack membership
- Service configuration

## Troubleshooting

### Service Not Showing as STDIO

If a STDIO service is showing as "not found" instead of "stdio":

1. **Clear Python cache**: Run this command to clear cached bytecode:
   ```bash
   cd /home/pwp/srv/apps/podman_manager
   rm -rf $(find . -type d -name __pycache__)
   rm -f $(find . -name "*.pyc")
   ```

2. **Check the config file**: Ensure the service is listed in `stdio_services_config.json` in the project root

3. **Verify the service name**: The name in the config must exactly match the service name

4. **Test from project directory**: Run `pm list` to verify it works

### Placeholder .container Files

STDIO services may have placeholder `.container` files in `~/.config/containers/systemd/` to:
- Make them appear in `pm list` output
- Show the buildable indicator (🔨)
- Maintain consistency with other services

These placeholder files don't affect the STDIO detection - the service will still show as `stdio` in the systemd column.

## Future Enhancements

Potential improvements:

1. **Automatic Detection**: Use detection patterns to automatically discover STDIO services
2. **Runtime Status**: Check if STDIO service containers are currently running
3. **Management Commands**: Add `pm` commands to start/stop STDIO services
4. **Health Checks**: Monitor STDIO service health and connectivity
