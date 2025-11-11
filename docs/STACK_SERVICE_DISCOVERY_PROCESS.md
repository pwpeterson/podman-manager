# How pm list Gets Stacks and Services

## Overview

The `pm list` command discovers stacks and services through a two-phase process that scans both source definitions and installed services.

## Discovery Process Flow

### Phase 1: Source Directory Scanning
**Location**: `/home/pwp/srv/local-ai-packaged/quadlets/`
**Method**: `_scan_source_directory()` in `QuadletManager`

1. **Stack Discovery**:
   - Scans for directories ending with `-stack` (e.g., `vllm-stack/`, `supabase-stack/`)
   - Each stack directory represents a logical grouping of related services

2. **Service Discovery Within Stacks**:
   - Scans each stack directory for `.container` and `.target` files
   - Example: `vllm-stack/vllm-qwen25.container` → service `vllm-qwen25`
   - Creates mapping: `service_name → full_service_name.service`

3. **Status Tracking**:
   - Marks all found services as `{"installed": False, "source": True}`
   - This means "available in source but not yet installed"

### Phase 2: Installed Directory Scanning
**Location**: `~/.config/containers/systemd/`
**Method**: `_scan_installed_directory()` in `QuadletManager`

1. **Installation Verification**:
   - Scans for `.container` and `.target` files in systemd directory
   - Updates status for services found in Phase 1: `{"installed": True, "source": True}`

2. **Standalone Service Discovery**:
   - Finds services that exist only in systemd (not in source)
   - Marks as `{"installed": True, "source": False}`
   - Groups these into a "standalone" stack

## Data Structures Created

### 1. `quadlet_services` Dictionary
```python
# Maps short names to full service names
{
    "vllm-qwen25": "vllm-qwen25.service",
    "vllm-proxy": "vllm-proxy.service",
    "vllm-delegator": "vllm-delegator.service",
    "vllm-stack": "vllm-stack.target"
}
```

### 2. `stack_services` Dictionary
```python
# Maps stack names to their service lists
{
    "vllm-stack": ["vllm-qwen25", "vllm-proxy", "vllm-delegator"],
    "supabase-stack": ["supabase-db", "supabase-auth", "supabase-api"],
    "standalone": ["some-standalone-service"]
}
```

### 3. `service_status` Dictionary
```python
# Tracks installation status for each service
{
    "vllm-qwen25": {"installed": True, "source": True},    # Green: fully available
    "vllm-glm4-9b-chat": {"installed": False, "source": True}, # Red: source only
    "some-old-service": {"installed": True, "source": False}   # Yellow: systemd only
}
```

## Display Logic in `pm list`

### Service Filtering (After Fix)
**File**: `operations/quadlet_display.py`
**Method**: `_get_all_projects_and_services()`

```python
# Only show services that are actually installed
if not status["installed"]:
    continue  # Skip uninstalled services
```

### Color Coding
- **Green**: `installed=True, source=True` - Fully available service
- **Yellow**: `installed=True, source=False` - Systemd-only service
- **Red**: `installed=False, source=True` - Source-only (NOW FILTERED OUT)

## Example Directory Structure

### Source Directory
```
/home/pwp/srv/local-ai-packaged/quadlets/
├── vllm-stack/
│   ├── vllm-qwen25.container
│   ├── vllm-proxy.container
│   ├── vllm-delegator.container
│   └── vllm-stack.target
├── supabase-stack/
│   ├── supabase-db.container
│   ├── supabase-auth.container
│   └── supabase-api.container
└── local-ai-stack/
    ├── local-ai-backend.container
    └── local-ai-frontend.container
```

### Installed Directory
```
~/.config/containers/systemd/
├── vllm-qwen25.container      # Installed
├── vllm-proxy.container       # Installed
├── vllm-delegator.container   # Installed
├── vllm-stack.target          # Installed
└── some-old-service.container # Standalone (no source)
```

## Discovery Commands You Can Run

### Check Source Directory
```bash
# See what stacks are available in source
ls /home/pwp/srv/local-ai-packaged/quadlets/

# See services in a specific stack
ls /home/pwp/srv/local-ai-packaged/quadlets/vllm-stack/
```

### Check Installed Directory
```bash
# See what's actually installed
ls ~/.config/containers/systemd/

# Check for specific service
ls ~/.config/containers/systemd/vllm-glm4-9b-chat.container
```

### Verify Service Status
```bash
# Check if systemd knows about the service
systemctl --user list-units --all --type=service | grep vllm-glm4-9b-chat

# Check service file exists
test -f ~/.config/containers/systemd/vllm-glm4-9b-chat.container && echo "exists" || echo "not found"
```

## Why vllm-glm4-9b-chat Appeared

### Before the Fix
1. **Source Discovery**: Found `vllm-glm4-9b-chat.container` in source directory
2. **Status**: Marked as `{"installed": False, "source": True}`
3. **Display**: Showed in red as "available in source but not installed"
4. **Status Check**: Systemd fallback gave false positive "active (systemd)"

### After the Fix
1. **Source Discovery**: Still finds the service in source
2. **Status**: Still marked as `{"installed": False, "source": True}`
3. **Display**: **FILTERED OUT** - service not shown at all
4. **Status Check**: Enhanced validation prevents false positives

## Key Methods in Code

### Discovery Methods
- **`QuadletManager.__init__()`**: Triggers discovery process
- **`_discover_quadlet_services()`**: Orchestrates both phases
- **`_scan_source_directory()`**: Phase 1 - source scanning
- **`_scan_installed_directory()`**: Phase 2 - installation verification

### Display Methods
- **`QuadletDisplayManager.show_status()`**: Main display logic
- **`_get_all_projects_and_services()`**: Builds display data structure
- **`_get_service_status_from_cache()`**: Gets runtime status

## Installation Process

When you run `pm install <service>`, it:
1. Copies `.container` file from source to `~/.config/containers/systemd/`
2. Runs `systemctl --user daemon-reload`
3. Updates `service_status[service]["installed"] = True`
4. Service then appears in `pm list` with proper status

## Summary

The system discovers services by:
1. **Scanning source definitions** to know what's available
2. **Checking installed files** to know what's actually usable
3. **Filtering display** to show only installed services (after fix)
4. **Getting runtime status** from podman/systemd for display

This two-phase approach allows the system to know about available services while only showing those that are actually installed and usable.
