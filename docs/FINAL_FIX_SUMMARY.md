# Final Fix for pm list vs pm ps Discrepancy

## Root Cause Analysis

The user reported that `pm list` shows "vllm-glm4-9b-chat active (systemd)" but:
- `pm ps` shows no container
- `podman exec -it vllm-glm4-9b-chat sh` fails with "no such container"
- `systemctl list-units --type=service | grep 9b-chat` shows nothing

This revealed **two separate bugs**:

### Bug 1: False Positive in Systemd Fallback
The systemd fallback logic was showing "active (systemd)" for services that don't actually exist. The `systemctl show` command can return default values even for non-existent services.

### Bug 2: Showing Uninstalled Services
The service discovery logic was including services that are defined in source files but not actually installed as systemd services.

## Fixes Applied

### Fix 1: Enhanced Systemd Service Validation

**File**: `operations/quadlet_display.py`
**Method**: `_get_service_status_from_cache()`

**Before**:
```python
# Only checked systemctl show output
cmd_status = ["systemctl", "--user", "show", f"{service_name}.service", ...]
# Could return "active" for non-existent services
```

**After**:
```python
# First verify service actually exists
cmd_check = [
    "systemctl", "--user", "list-units", "--all", "--type=service",
    "--plain", "--no-legend", f"{service_name}.service"
]
# If no output, service doesn't exist
if not check_result.stdout.strip():
    return "[white]not found[/white]"

# Then get detailed status for existing services
```

### Fix 2: Filter Out Uninstalled Services

**File**: `operations/quadlet_display.py`
**Method**: `_get_all_projects_and_services()`

**Before**:
```python
# Showed all services including uninstalled ones
if not status["installed"] and status["source"]:
    color = "red"  # Red: available in source but not installed
    # Still added to display list
```

**After**:
```python
# Only show services that are actually installed
if not status["installed"]:
    continue  # Skip uninstalled services entirely
```

## Technical Details

### Service Discovery Process

1. **Source Scanning**: Scans `/home/pwp/srv/local-ai-packaged/quadlets/` for `.container` files
2. **Installation Check**: Checks `~/.config/containers/systemd/` for installed services
3. **Status Tracking**: Maintains `service_status` dict with `{"installed": bool, "source": bool}`
4. **Filtering**: Now only displays services where `installed = True`

### Systemd Fallback Process

1. **Container Status**: First tries `podman ps -a` (5-second timeout)
2. **Service Existence**: If podman fails, checks `systemctl list-units` to verify service exists
3. **Detailed Status**: If service exists, gets `ActiveState`, `SubState`, `LoadState`
4. **Accurate Reporting**: Returns precise status like "starting (systemd)", "failed (systemd)", etc.

## Expected Behavior After Fix

### For Non-Existent Services (like vllm-glm4-9b-chat)
- **Before**: `pm list` showed "active (systemd)" (false positive)
- **After**: Service won't appear in `pm list` at all (filtered out as uninstalled)

### For Existing Services
- **Container Running**: Both `pm list` and `pm ps` show consistent status
- **Container Stopped**: Both show stopped/exited status
- **Podman Unresponsive**: `pm list` shows accurate systemd status, `pm ps` times out

### Status Indicators
- **Green**: Service installed and running
- **Yellow**: Service installed but stopped/starting
- **Red**: Service installed but failed
- **Not Shown**: Service not installed (filtered out)

## Validation Commands

```bash
# Test the fix
cd /home/pwp/srv/apps/podman_manager

# Should no longer show vllm-glm4-9b-chat
python podman_manager.py list

# Should show consistent results with pm list
python podman_manager.py ps

# Verify service doesn't exist
systemctl --user list-units --type=service | grep glm4
# Should return nothing

# Check what services are actually installed
ls ~/.config/containers/systemd/*.container
```

## Files Modified

1. **`operations/quadlet_display.py`**:
   - Enhanced `_get_service_status_from_cache()` with proper service existence validation
   - Modified `_get_all_projects_and_services()` to filter out uninstalled services
   - Added comprehensive systemd status checking with `list-units` verification

## Impact

- **Eliminates false positives**: Services that don't exist won't show as "active"
- **Cleaner display**: Only shows services that are actually installed
- **Accurate status**: Systemd fallback provides precise service state information
- **Consistent behavior**: Resolves discrepancy between `pm list` and `pm ps`

The fix addresses both the immediate issue (false positive for vllm-glm4-9b-chat) and the underlying problems in service discovery and status reporting.
