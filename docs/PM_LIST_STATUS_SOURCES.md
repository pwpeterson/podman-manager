# Data Sources for `pm list` Status

## Overview

The `pm list` command gets its status information through a multi-layered approach with fallback mechanisms. Here's the complete data flow:

## Primary Data Flow

### 1. Command Entry Point
- **File**: [`cli/command_router.py`](cli/command_router.py:275)
- **Method**: `_handle_list(args)`
- **Action**: Calls `self.display.show_status(args.target)`

### 2. Display Manager
- **File**: [`operations/quadlet_display.py`](operations/quadlet_display.py:25)
- **Method**: `show_status(target=None, verbose=False)`
- **Actions**:
  1. Gets all projects/services: `self._get_all_projects_and_services()`
  2. Gets container statuses: `self._get_all_container_statuses(verbose=verbose)`
  3. For each service, calls: `self._get_service_status_from_cache(clean_service_name, all_container_statuses)`

## Data Sources (in Priority Order)

### Source 1: Podman Container Status (Primary)
- **Method**: [`_get_all_container_statuses()`](operations/quadlet_display.py:666)
- **Command**: `podman ps -a --format "{{.Names}};{{.Status}}"`
- **Timeout**: 5 seconds
- **Returns**: Dictionary of container_name → status
- **Status Examples**:
  - `"Up 2 hours (healthy)"` → `[green]Up 2 hours (healthy)[/green]`
  - `"Exited (0) 5 minutes ago"` → `[orange1]Exited (0) 5 minutes ago[/orange1]`
  - `"Exited (1) 1 hour ago"` → `[red]Exited (1) 1 hour ago[/red]`

### Source 2: Systemd Service Status (Fallback)
- **Method**: [`_get_service_status_from_cache()`](operations/quadlet_display.py:640)
- **Triggered When**: Podman times out or returns empty results
- **Command**: `systemctl --user show <service>.service --property=ActiveState,SubState,LoadState`
- **Timeout**: 3 seconds
- **Status Logic**:
  ```python
  if load_state != "loaded":
      return "[white]not found[/white]"
  elif active_state == "active" and sub_state == "running":
      return "[green]active (systemd)[/green]"
  elif active_state == "active" and sub_state in ["start", "start-pre", "start-post"]:
      return "[yellow]starting (systemd)[/yellow]"
  elif active_state == "failed":
      return "[red]failed (systemd)[/red]"
  elif active_state == "inactive":
      return "[yellow]inactive (systemd)[/yellow]"
  ```

### Source 3: Container Name Variations
The system tries multiple container name variations to find matches:
- Exact service name
- Service name with hyphens/underscores swapped
- Prefixed versions: `local-ai-{service}`, `supabase-{service}`
- Stripped versions: remove `local-ai-` or `supabase-` prefixes
- Suffixed versions: `{service}-1`, `{service}_1`

## Status Resolution Process

### Step 1: Container Status Lookup
```python
# In _get_service_status_from_cache()
if all_container_statuses:  # If podman responded
    # Check exact match
    if service_name in all_container_statuses:
        return self._format_status(all_container_statuses[service_name])
    
    # Check variations and partial matches
    for variation in variations:
        if variation in all_container_statuses:
            return self._format_status(all_container_statuses[variation])
```

### Step 2: Systemd Fallback
```python
# If no container status found or podman timed out
try:
    cmd_status = [
        "systemctl", "--user", "show", f"{service_name}.service",
        "--property=ActiveState,SubState,LoadState"
    ]
    # Parse and return systemd status
except subprocess.TimeoutExpired:
    return "[red]timeout[/red]"
```

## Status Color Coding

### Container Status Colors
- **Green**: `Up`, `running`, `healthy`
- **Yellow**: `unhealthy`, `starting`, `restarting`
- **Red**: `Exited (non-zero)`, failed states
- **Orange**: `Exited (0)` - clean exit
- **Dim**: `created`, unknown states

### Systemd Status Colors
- **Green**: `active (systemd)` - service running
- **Yellow**: `starting (systemd)`, `inactive (systemd)`
- **Red**: `failed (systemd)`, `timeout`
- **White**: `not found`
- **Dim**: Other states

## Why "active (systemd)" Can Show When Container Isn't Running

### Before the Fix
The original code only checked:
```bash
systemctl --user is-active <service>.service
```
This returns "active" even when:
- Container has exited but systemd hasn't detected it
- Service is in restart loop
- Container failed but systemd is still trying to restart it

### After the Fix
Now checks detailed status:
```bash
systemctl --user show <service>.service --property=ActiveState,SubState,LoadState
```
This provides:
- `ActiveState=active, SubState=running` → Actually running
- `ActiveState=active, SubState=start` → Starting up
- `ActiveState=failed` → Service failed
- `ActiveState=inactive` → Service stopped

## Service Discovery Sources

### Quadlet Services Discovery
- **Source Directory**: `/home/pwp/srv/local-ai-packaged/quadlets/`
- **Installed Directory**: `~/.config/containers/systemd/`
- **File Types**: `*.container`, `*.target`
- **Method**: [`_discover_quadlet_services()`](managers/quadlet_manager.py:60)

### Stack Organization
- **Stack Detection**: Directories ending with `-stack`
- **Service Grouping**: Services with common prefixes
- **Stack Services**: Stored in `self.manager.stack_services`

## Comparison with `pm ps`

### `pm ps` Data Source
- **File**: [`cli/command_router.py`](cli/command_router.py:280)
- **Method**: `_handle_ps(args)`
- **Command**: `podman ps -a --format "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"`
- **No Fallback**: If podman fails, command fails
- **Direct Output**: Shows raw podman results in table format

### Key Differences
1. **`pm list`**: Has systemd fallback when podman is unresponsive
2. **`pm ps`**: Direct podman command, no fallback
3. **`pm list`**: Shows service-oriented view with stacks
4. **`pm ps`**: Shows container-oriented view with ports

## Troubleshooting Status Discrepancies

### When Statuses Differ
1. **Check podman responsiveness**: `podman ps -a` (should complete in <5 seconds)
2. **Check systemd status**: `systemctl --user status <service>.service`
3. **Check container existence**: `podman ps -a | grep <service>`
4. **Check service definition**: `ls ~/.config/containers/systemd/<service>.container`

### Common Scenarios
- **Podman timeout**: `pm list` shows systemd status, `pm ps` fails
- **Container name mismatch**: `pm list` may find via variations, `pm ps` shows exact names
- **Service vs Container**: `pm list` shows service status, `pm ps` shows container status
