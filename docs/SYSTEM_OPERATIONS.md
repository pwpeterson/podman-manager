# System Operations & Fixes

## Overview

This document consolidates system operations improvements, bug fixes, and operational enhancements made to the Podman Manager, including status discrepancy fixes, service stopping monitors, and spinner enhancements.

## Status Discrepancy Fix: pm list vs pm ps

### Problem Description

The user reported that `pm list` shows "vllm-glm4-9b-chat active (systemd)" but `pm ps` doesn't show it as active.

### Root Cause Analysis

#### The Issue
1. **`pm list`** uses [`QuadletDisplayManager.show_status()`](operations/quadlet_display.py:25) which:
   - Calls [`_get_all_container_statuses()`](operations/quadlet_display.py:666) with a 5-second timeout
   - When podman times out or is unresponsive, falls back to systemd status checking
   - The fallback only checked `systemctl --user is-active <service>` which returns "active" even when containers aren't actually running

2. **`pm ps`** directly runs `podman ps -a` command without any systemd fallback
   - If podman is slow/unresponsive, this command fails or times out
   - Shows no results or error, creating the discrepancy

#### Why This Happens
- Podman can become unresponsive due to various reasons (high load, network issues, etc.)
- Systemd services can be "active" even when the actual container has exited
- The original fallback logic was too simplistic, only checking ActiveState

### Solution Implemented

#### Enhanced Systemd Fallback Logic

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

#### Improved Status Accuracy

The fix now distinguishes between:
- `active + running` → `[green]active (systemd)[/green]`
- `active + starting` → `[yellow]starting (systemd)[/yellow]`
- `failed` → `[red]failed (systemd)[/red]`
- `inactive` → `[yellow]inactive (systemd)[/yellow]`
- `not loaded` → `[white]not found[/white]`

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

### Why This Fix Works

1. **More Accurate Systemd Status**: Instead of just checking if a service is "active", we now check both ActiveState and SubState to determine the actual service condition.

2. **Better Error Handling**: The fallback logic now properly handles different systemd states and provides more informative status messages.

3. **Consistent Behavior**: When podman is unresponsive, users will see clear indication that status is from systemd, and the status will be more accurate.

4. **Timeout Protection**: The existing 5-second timeout in `_get_all_container_statuses()` prevents hanging, and the improved fallback provides better information.

### Impact

- **Resolves the discrepancy** between `pm list` and `pm ps`
- **Improves status accuracy** when podman is unresponsive
- **Maintains backward compatibility** with existing functionality
- **Provides clearer feedback** to users about service states

## Final Fix Summary

### Root Cause Analysis

The user reported that `pm list` shows "vllm-glm4-9b-chat active (systemd)" but:
- `pm ps` shows no container
- `podman exec -it vllm-glm4-9b-chat sh` fails with "no such container"
- `systemctl list-units --type=service | grep 9b-chat` shows nothing

This revealed **two separate bugs**:

#### Bug 1: False Positive in Systemd Fallback
The systemd fallback logic was showing "active (systemd)" for services that don't actually exist. The `systemctl show` command can return default values even for non-existent services.

#### Bug 2: Showing Uninstalled Services
The service discovery logic was including services that are defined in source files but not actually installed as systemd services.

### Fixes Applied

#### Fix 1: Enhanced Systemd Service Validation

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

#### Fix 2: Filter Out Uninstalled Services

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

### Expected Behavior After Fix

#### For Non-Existent Services (like vllm-glm4-9b-chat)
- **Before**: `pm list` showed "active (systemd)" (false positive)
- **After**: Service won't appear in `pm list` at all (filtered out as uninstalled)

#### For Existing Services
- **Container Running**: Both `pm list` and `pm ps` show consistent status
- **Container Stopped**: Both show stopped/exited status
- **Podman Unresponsive**: `pm list` shows accurate systemd status, `pm ps` times out

#### Status Indicators
- **Green**: Service installed and running
- **Yellow**: Service installed but stopped/starting
- **Red**: Service installed but failed
- **Not Shown**: Service not installed (filtered out)

### Files Modified

1. **`operations/quadlet_display.py`**:
   - Enhanced `_get_service_status_from_cache()` with proper service existence validation
   - Modified `_get_all_projects_and_services()` to filter out uninstalled services
   - Added comprehensive systemd status checking with `list-units` verification

## Service Stopping Monitor Enhancement

### Overview

Added comprehensive real-time monitoring for services during the stopping process. This enhancement provides detailed visibility into service shutdown phases, detects stuck services, and offers both service and container monitoring capabilities.

### New Features Added

#### 1. Real-Time Service Stopping Monitor (`monitor_service_stopping`)

- **Live Status Display**: Real-time panel showing service stopping progress
- **Detailed State Tracking**: Monitors systemctl status transitions
- **Stuck Service Detection**: Identifies services that hang during shutdown
- **Timeout Handling**: Prevents indefinite waiting with configurable timeouts
- **Elapsed Time Tracking**: Shows how long the stopping process has taken

#### 2. Container Stopping Monitor (`monitor_container_stopping`)

- **Container-Specific Monitoring**: Tracks podman container stopping process
- **Status Transition Tracking**: Monitors container state changes
- **Integration with Service Monitor**: Can be used alongside service monitoring

#### 3. Enhanced Status Detection

- **Granular State Recognition**: Distinguishes between different stopping phases
- **Signal Tracking**: Detects SIGTERM vs SIGKILL phases
- **Failure Detection**: Identifies services that fail during stopping

### Service Stopping States Monitored

| Status | Description | Indication |
|--------|-------------|------------|
| **Still Running** | Service hasn't started stopping | Continue monitoring |
| **Deactivating** | Service is gracefully shutting down | Normal process |
| **Sending SIGTERM** | Graceful shutdown signal sent | Normal process |
| **Sending SIGKILL** | Force kill signal sent | Service stuck |
| **Stopped** | Service successfully stopped | Complete |
| **Failed** | Service failed during stop | Investigate |

### Usage Examples

#### Basic Service Monitoring
```python
from managers.reinit.monitoring import ReinitMonitor

monitor = ReinitMonitor(manager, health_checker)
success = monitor.monitor_service_stopping("vllm-qwen25", timeout=30)
```

#### Container Monitoring
```python
success = monitor.monitor_container_stopping("vllm-container", timeout=30)
```

#### Integration with Reinit Process
```python
# During reinit, monitor the stopping phase
if monitor.monitor_service_stopping(target):
    console.print("[green]Service stopped successfully, proceeding with reinit[/green]")
else:
    console.print("[red]Service stopping failed or timed out[/red]")
```

### Real-Time Display Features

#### Live Status Panel
```
┌─ Service Stopping Monitor ─────────────────┐
│                                            │
│  Service: vllm-qwen25                      │
│  Status: Deactivating                      │
│  Elapsed: 2.3s                            │
│  Details: Service is deactivating          │
│  ⏳ Stopping in progress...                │
│                                            │
└────────────────────────────────────────────┘
```

#### Container Status Panel
```
┌─ Container Stopping Monitor ───────────────┐
│                                            │
│  Container: vllm-container                 │
│  Status: Stopping                          │
│  Elapsed: 1.8s                            │
│  ⏳ Stopping in progress...                │
│                                            │
└────────────────────────────────────────────┘
```

### Error Detection and Handling

#### Stuck Service Detection
- Detects when services require SIGKILL (force termination)
- Identifies systemctl command timeouts
- Provides early warning for problematic services

#### Timeout Management
- Configurable timeout periods (default: 30 seconds)
- Prevents indefinite waiting
- Returns clear success/failure status

#### Error Reporting
- Detailed error messages for troubleshooting
- Distinguishes between different failure types
- Provides actionable feedback

### Integration Points

#### Reinit Operations
- Can be integrated into reinit workflows
- Provides feedback during service stopping phase
- Helps identify why reinit operations might fail

#### Health Checking
- Complements existing health check functionality
- Provides real-time feedback during transitions
- Enhances overall system monitoring

#### AI Analysis
- Stopping status can be included in AI diagnostic context
- Helps AI systems understand service behavior patterns
- Provides data for failure analysis

### Technical Implementation

#### Key Methods

1. **`monitor_service_stopping(target, timeout=30)`**
   - Main service monitoring function
   - Returns boolean success status
   - Uses Rich Live display for real-time updates

2. **`_get_service_stopping_status(service_name)`**
   - Parses systemctl status output
   - Returns structured status information
   - Handles various service states

3. **`monitor_container_stopping(target, timeout=30)`**
   - Container-specific monitoring
   - Uses podman ps for status checking
   - Integrates with fuzzy container matching

4. **`_create_stopping_status_panel()` / `_create_container_stopping_panel()`**
   - Creates Rich panels for live display
   - Formats status information attractively
   - Updates in real-time

#### Dependencies
- Rich library for live displays and panels
- subprocess for systemctl/podman commands
- Integration with existing fuzzy matching

### Benefits

#### For Users
- **Transparency**: See exactly what's happening during service stops
- **Confidence**: Know when services are stuck vs. taking time to stop gracefully
- **Troubleshooting**: Identify problematic services quickly
- **Feedback**: Real-time progress indication

#### For System Operations
- **Reliability**: Detect and handle stuck services
- **Efficiency**: Avoid waiting indefinitely for failed stops
- **Integration**: Easy to incorporate into existing workflows
- **Monitoring**: Comprehensive service lifecycle visibility

#### For Development
- **Debugging**: Understand service stopping behavior
- **Testing**: Verify service shutdown procedures
- **Optimization**: Identify slow-stopping services
- **Automation**: Programmatic service stopping with feedback

### Usage in Reinit Operations

The service stopping monitor can be integrated into reinit operations to provide better visibility:

```python
# Example integration in reinit flow
def enhanced_reinit_with_monitoring(target):
    console.print("[cyan]Starting enhanced reinit with stopping monitor[/cyan]")

    # Monitor the stopping phase
    if monitor.monitor_service_stopping(target):
        console.print("[green]✅ Service stopped cleanly, proceeding with reinit[/green]")
        # Continue with reinit process
        return perform_reinit(target)
    else:
        console.print("[red]❌ Service stopping failed, investigating...[/red]")
        # Run AI analysis or other troubleshooting
        return False
```

## Spinner Enhancement Summary

### Overview
Added spinner functionality specifically for the "9b-thinking" service (vllm-glm41-9b-thinking) when using the `pm stop` command.

### Changes Made

#### 1. Import Addition
- Added import for `safe_spinner` from `ai_analyzer.spinner_manager` in `managers/quadlet_manager.py`

#### 2. Service Detection Logic
- Added detection logic to identify 9b-thinking service variants:
  - `"9b-thinking"` in target name (case-insensitive)
  - `"vllm-glm41-9b-thinking"` in service name (case-insensitive)

#### 3. Spinner Integration
- When stopping the 9b-thinking service, displays spinner with text: `"Stopping vllm-glm41-9b-thinking"`
- Spinner respects verbose mode settings
- Only shows spinner when not in quiet mode

#### 4. Success Message Customization
- Modified all success messages for 9b-thinking service to show:
  - `"Stopping  vllm-glm41-9b-thinking"` (with spinner)
  - `"stopped vllm-glm41-9b-thinking"` (completion message)
- Applied to all stop scenarios:
  - Normal stop
  - Force stop with SIGTERM
  - Force stop with SIGKILL
  - Container elimination

### Usage

#### Command Examples
```bash
# Any of these will trigger the spinner for 9b-thinking service:
pm stop 9b-thinking
pm stop vllm-glm41-9b-thinking
pm stop glm41-9b-thinking
```

#### Expected Output
1. **During stop**: Spinner displays "Stopping vllm-glm41-9b-thinking"
2. **On success**: Shows "stopped vllm-glm41-9b-thinking"

### Technical Details
- Uses existing `safe_spinner` context manager from `ai_analyzer.spinner_manager`
- Maintains compatibility with verbose/quiet modes:
  - **Verbose mode (`-v`)**: Shows "Stopping vllm-glm41-9b-thinking..." without spinner
  - **Non-verbose mode**: Shows spinner with "Stopping vllm-glm41-9b-thinking"
- Only affects the 9b-thinking service - other services remain unchanged
- Handles all stop scenarios (normal, force, container elimination)
- Fixed hanging issue in verbose mode by conditionally using spinner

### Files Modified
- `managers/quadlet_manager.py` - Added spinner and custom messaging for 9b-thinking service

## Testing

### Manual Testing

#### Status Discrepancy Fix
```bash
# Test the fix
cd /home/pwp/srv/apps/podman_manager

# Run both commands and compare
python podman_manager.py list
python podman_manager.py ps

# The discrepancy should now be resolved or clearly explained
```

#### Service Stopping Monitor
```bash
# Test service stopping with monitoring
pm stop <service-name> -v

# Should show real-time stopping progress
```

#### Spinner Enhancement
```bash
# Test 9b-thinking service spinner
pm stop 9b-thinking

# Should show spinner during stop operation
```

### Verification Commands

```bash
# Verify service existence
systemctl --user list-units --type=service | grep <service-name>

# Check what services are actually installed
ls ~/.config/containers/systemd/*.container

# Test service status accuracy
systemctl --user status <service-name>.service
```

## Future Enhancements

### Service Stopping Monitor
- **Stack Monitoring**: Monitor entire service stacks during stopping
- **Dependency Tracking**: Monitor service dependencies during shutdown
- **Performance Metrics**: Track stopping time patterns
- **Alert Integration**: Send notifications for stuck services
- **Log Analysis**: Parse service logs during stopping for additional context

### Status System
- **Real-time Status Updates**: Live status monitoring for all services
- **Health Check Integration**: Combine container and service health checks
- **Performance Monitoring**: Track service performance metrics
- **Alerting System**: Notifications for service state changes

### Spinner System
- **Configurable Spinners**: Allow users to customize spinner styles
- **Service-Specific Spinners**: Different spinners for different service types
- **Progress Bars**: Replace spinners with progress bars for long operations
- **Sound Notifications**: Audio feedback for completion events

## Conclusion

The system operations enhancements provide:

### Reliability Improvements
- **Accurate Status Reporting**: Eliminates false positives in service status
- **Real-time Monitoring**: Live feedback during service operations
- **Stuck Service Detection**: Early identification of problematic services
- **Comprehensive Error Handling**: Better error detection and reporting

### User Experience Enhancements
- **Clear Visual Feedback**: Spinners and progress indicators
- **Consistent Status Display**: Unified status reporting across commands
- **Real-time Updates**: Live monitoring of service operations
- **Actionable Error Messages**: Clear guidance for troubleshooting

### Operational Intelligence
- **Service Lifecycle Visibility**: Complete view of service operations
- **Performance Monitoring**: Track service behavior patterns
- **Proactive Issue Detection**: Identify problems before they cause failures
- **Integration Ready**: Easy integration with monitoring and alerting systems

These improvements significantly enhance the reliability and user experience of the Podman Manager while providing better operational visibility and troubleshooting capabilities.
