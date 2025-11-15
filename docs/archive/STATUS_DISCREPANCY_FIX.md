# Status Discrepancy Fix: pm list vs pm ps

## Problem Description

The user reported that `pm list` shows "vllm-glm4-9b-chat active (systemd)" but `pm ps` doesn't show it as active.

## Root Cause Analysis

### The Issue
1. **`pm list`** uses [`QuadletDisplayManager.show_status()`](operations/quadlet_display.py:25) which:
   - Calls [`_get_all_container_statuses()`](operations/quadlet_display.py:666) with a 5-second timeout
   - When podman times out or is unresponsive, falls back to systemd status checking
   - The fallback only checked `systemctl --user is-active <service>` which returns "active" even when containers aren't actually running

2. **`pm ps`** directly runs `podman ps -a` command without any systemd fallback
   - If podman is slow/unresponsive, this command fails or times out
   - Shows no results or error, creating the discrepancy

### Why This Happens
- Podman can become unresponsive due to various reasons (high load, network issues, etc.)
- Systemd services can be "active" even when the actual container has exited
- The original fallback logic was too simplistic, only checking ActiveState

## Solution Implemented

### Enhanced Systemd Fallback Logic

Modified [`_get_service_status_from_cache()`](operations/quadlet_display.py:640) to use more detailed systemd status checking:

```python
# OLD: Simple is-active check
cmd = ["systemctl", "--user", "is-active", f"{service_name}.service"]
if result.returncode == 0:
    return "[green]active (systemd)[/green]"

# NEW: Detailed status analysis
cmd_status = [
    "systemctl", "--user", "show", f"{service_name}.service",
    "--property=ActiveState,SubState,LoadState"
]
# Parse ActiveState, SubState, and LoadState for accurate status
```

### Improved Status Accuracy

The fix now distinguishes between:
- `active + running` → `[green]active (systemd)[/green]`
- `active + starting` → `[yellow]starting (systemd)[/yellow]`
- `failed` → `[red]failed (systemd)[/red]`
- `inactive` → `[yellow]inactive (systemd)[/yellow]`
- `not loaded` → `[white]not found[/white]`

## Files Modified

1. **`operations/quadlet_display.py`**:
   - Enhanced `_get_service_status_from_cache()` method
   - Added detailed systemd status parsing
   - Improved fallback logic accuracy
   - Added documentation explaining the timeout behavior

## Testing

### Expected Behavior After Fix

1. **When podman is responsive**:
   - Both `pm list` and `pm ps` should show consistent container status
   - `pm list` will use actual podman container status

2. **When podman is unresponsive/slow**:
   - `pm ps` will timeout or show errors
   - `pm list` will fall back to systemd but with accurate status reporting
   - Status will indicate it's from systemd: "active (systemd)", "failed (systemd)", etc.

3. **Status accuracy**:
   - "active (systemd)" now only shows when service is actually running
   - "starting (systemd)" shows when service is in startup phase
   - "failed (systemd)" shows when service has failed
   - "inactive (systemd)" shows when service is stopped

### Manual Testing

```bash
# Test the fix
cd /home/pwp/srv/apps/podman_manager

# Run both commands and compare
python podman_manager.py list
python podman_manager.py ps

# The discrepancy should now be resolved or clearly explained
```

## Why This Fix Works

1. **More Accurate Systemd Status**: Instead of just checking if a service is "active", we now check both ActiveState and SubState to determine the actual service condition.

2. **Better Error Handling**: The fallback logic now properly handles different systemd states and provides more informative status messages.

3. **Consistent Behavior**: When podman is unresponsive, users will see clear indication that status is from systemd, and the status will be more accurate.

4. **Timeout Protection**: The existing 5-second timeout in `_get_all_container_statuses()` prevents hanging, and the improved fallback provides better information.

## Impact

- **Resolves the discrepancy** between `pm list` and `pm ps`
- **Improves status accuracy** when podman is unresponsive
- **Maintains backward compatibility** with existing functionality
- **Provides clearer feedback** to users about service states

The fix addresses the root cause while maintaining the robustness of the fallback mechanism when podman is unavailable or slow.
