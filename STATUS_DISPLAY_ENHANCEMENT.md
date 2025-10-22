# Enhanced Status Display Implementation

## Overview

Modified the `pm status` command to display a tree view of Stacks & Services that includes the running status for each listed service.

## Changes Made

### 1. Enhanced QuadletDisplayManager (`quadlet_display.py`)

- **Modified `show_status()` method**: Updated to include running status for each service
- **Added `_extract_clean_service_name()` method**: Removes Rich color formatting from service names
- **Added `_get_service_running_status()` method**: Determines service status using systemd and container checks
- **Added `_get_container_status()` method**: Checks container status using `podman ps`
- **Updated tree title**: Changed from "Projects & Services" to "Stacks & Services"

### 2. Enhanced DisplayManager (`display.py`)

- **Modified `show_status()` method**: Updated to include running status for compose services
- **Added `_get_service_running_status()` method**: Determines compose service status using container checks
- **Updated tree title**: Changed from "Projects & Services" to "Stacks & Services"

### 3. Updated Help Text (`podman_manager.py`)

- **Updated command descriptions**: Modified help text to reflect new functionality
- **Updated argument parser**: Enhanced descriptions for `list` and `status` commands

## Status Indicators

The enhanced display shows service status with color-coded indicators:

- `[green]running[/green]` - Service is active and running
- `[red]failed[/red]` - Service has failed
- `[red]exited (error)[/red]` - Container exited with error code
- `[yellow]exited[/yellow]` - Container exited cleanly (code 0)
- `[yellow]starting[/yellow]` - Service is starting up
- `[yellow]restarting[/yellow]` - Service is restarting
- `[dim]stopped[/dim]` - Service is stopped/inactive
- `[dim]created[/dim]` - Container created but not started
- `[dim]not found[/dim]` - Service/container not found
- `[red]error[/red]` - Error checking status

## Example Output

```
Stacks & Services
├── vllm-stack
│   ├── vllm-qwen25 > [green]running[/green]
│   ├── vllm-proxy > [green]running[/green]
│   └── vllm-delegator > [red]failed[/red]
├── local-ai-stack
│   ├── local-ai-caddy > [green]running[/green]
│   ├── local-ai-neo4j > [dim]stopped[/dim]
│   └── local-ai-ollama > [dim]not found[/dim]
└── supabase-stack
    ├── supabase-db > [green]running[/green]
    ├── supabase-auth > [yellow]starting[/yellow]
    └── supabase-api > [red]exited (error)[/red]
```

## Service Status Detection Logic

### For Quadlet Services
1. Check if service is in quadlet services registry
2. Query systemd service status using `systemctl --user show`
3. Parse `ActiveState` property for status
4. Fallback to container status check if needed

### For Compose Services
1. Check container status using `podman ps -a`
2. Try exact name match first
3. Try partial name match if exact fails
4. Check common service name variations
5. Parse container status and exit codes

## Service Name Variations Checked

The system checks multiple naming patterns to find containers:
- Original service name
- Underscore/hyphen variations (`service-name` ↔ `service_name`)
- Prefixed variations (`local-ai-service`, `supabase-service`)
- Stripped prefix variations (remove `local-ai-`, `supabase-`)

## Commands Enhanced

- `pm list` - Shows all stacks and services with running status
- `pm list <stack>` - Shows specific stack with service status
- `pm status <target>` - Shows status tree for specific target

## Testing

A test script `test_status_display.py` has been created to verify the functionality:

```bash
python test_status_display.py
```

## Backward Compatibility

All changes are backward compatible:
- Existing command syntax remains unchanged
- Only the display output is enhanced
- No breaking changes to command-line interface
- Graceful fallback for status detection errors

## Performance Considerations

- Status checks use timeouts (5 seconds) to prevent hanging
- Container status queries are optimized with specific filters
- Graceful error handling prevents display failures
- Minimal impact on command execution time

## Future Enhancements

Potential improvements for future versions:
- Health check integration for more detailed status
- Resource usage indicators (CPU, memory)
- Service dependency visualization
- Real-time status updates
- Custom status check configurations
