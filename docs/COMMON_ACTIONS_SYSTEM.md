# Common Actions System

## Overview

The Common Actions System provides a standardized set of "More available actions" that can be used consistently across all pm commands. This replaces the previous inconsistent approach where each command had its own custom set of optional actions.

## Key Features

### 🎯 Standardized Commands
- **Consistent Experience**: Same diagnostic commands available across all pm operations
- **Comprehensive Coverage**: 8 categories covering all common troubleshooting scenarios
- **Smart Substitution**: Dynamic placeholder replacement for service names, ports, etc.

### 📋 Command Categories

1. **PM Command Shortcuts** - Quick pm command references
2. **Service Status** - systemctl status and service information commands
3. **Logs & Diagnostics** - journalctl and log analysis commands
4. **Container Operations** - podman container management commands
5. **System Resources** - disk space, memory, system info commands
6. **Network & Connectivity** - network testing and port checking commands
7. **Volume Management** - podman volume operations
8. **Troubleshooting** - systemd and general troubleshooting commands

### 🎨 Display Formats

- **Compact Format**: Essential commands only (6 key commands)
- **Detailed Format**: Full categorized command list
- **Category-Specific**: Show only specific categories

## Usage Examples

### Basic Usage

```python
from operations.common_actions import show_essential_actions, show_compact_actions

# Show essential actions for a service
show_essential_actions("vllm-qwen25")

# Show compact format
show_compact_actions(target="supabase-analytics", port="3000")
```

### Advanced Usage

```python
from operations.common_actions import CommonActionsFormatter

formatter = CommonActionsFormatter()

# Show specific categories
formatter.show_common_actions(
    target="vllm-delegator",
    service_name="vllm-delegator.service",
    container_name="vllm-delegator",
    port="8002",
    categories=["service_status", "logs_diagnostics", "troubleshooting"],
    compact=False
)

# Show single category
formatter.show_category_actions("network_connectivity", target="studio", port="3000")
```

## Integration Points

### Existing Code Integration

The system has been integrated into key areas:

1. **Reinit Manager** (`managers/reinit_manager.py`)
   - Replaced custom `_show_next_steps()` with `show_essential_actions()`

2. **AI Display Formatter** (`ai_analyzer/display_formatters.py`)
   - Updated `_show_analysis_menu()` to use common actions with analysis-specific recommendations

3. **Installer** (`operations/installer.py`)
   - Updated service and stack installation completion messages

### Command Categories by Use Case

| PM Command | Recommended Categories |
|------------|----------------------|
| `pm install` | service_management, service_status, logs_diagnostics |
| `pm reinit` | pm_shortcuts, service_status, logs_diagnostics |
| `pm diag` | troubleshooting, logs_diagnostics, system_resources |
| `pm logs` | logs_diagnostics, troubleshooting, pm_shortcuts |
| `pm build` | container_ops, logs_diagnostics, troubleshooting |

## Command Reference

### Essential Commands (Compact Format)
```
✓ podman logs      : pm logs SERVICE
✓ service logs     : journalctl --user -u SERVICE.service -n 100
✓ service status   : systemctl --user status SERVICE.service --no-pager -l
✓ service config   : systemctl --user cat SERVICE.service
✓ troubleshoot     : pm diag SERVICE
✓ restart service  : pm restart SERVICE
```

### Complete Command Set

#### Service Status & Information
- `systemctl --user status {service_name} --no-pager -l`
- `systemctl --user show {service_name} -p ExecMainStatus,ExecMainCode,Result,ActiveEnterTimestamp,InactiveEnterTimestamp,RestartCount`
- `systemctl --user cat {service_name}`
- `systemctl --user is-enabled {service_name}`
- `systemctl --user is-active {service_name}`

#### Logs & Diagnostics
- `journalctl --user -u {service_name} -n 100 --no-pager`
- `journalctl --user -u {service_name} -f`
- `journalctl --user -u {service_name} --since '1 hour ago' --no-pager`
- `journalctl --user -u {service_name} -n 50 --no-pager -o short-precise`
- `journalctl --user -u {service_name} -n 200 --no-pager | grep -i error`

#### Container Operations
- `podman ps -a --format '{{.ID}} {{.Names}} {{.Status}} {{.Image}}'`
- `podman logs {container_name} --since 2h --timestamps --tail 100`
- `podman inspect {container_name}`
- `podman stats {container_name} --no-stream`
- `podman exec -it {container_name} /bin/bash`

#### System Resources
- `df -h /`
- `podman system info`
- `podman system df`
- `free -h`
- `ps aux | grep {container_name}`

#### Network & Connectivity
- `podman network ls`
- `ss -tulpen -H`
- `ss -tulpen | grep :{port}`
- `curl -I http://localhost:{port} || echo 'Connection failed'`
- `nslookup {hostname} || echo 'DNS failed'`

#### Volume Management
- `podman volume ls`
- `podman volume inspect {volume_name}`
- `podman system df -v`
- `podman inspect {container_name} | grep -A 10 'Mounts'`

#### Service Management
- `systemctl --user start {service_name}`
- `systemctl --user stop {service_name}`
- `systemctl --user restart {service_name}`
- `systemctl --user enable {service_name}`
- `systemctl --user disable {service_name}`
- `systemctl --user reset-failed {service_name}`

#### PM Command Shortcuts
- `pm logs {target}`
- `pm diag {target}`
- `pm status {target}`
- `pm restart {target}`
- `pm reinit {target}`
- `pm ps`

#### Troubleshooting
- `systemctl --user status`
- `systemctl --user daemon-reload`
- `systemctl --user --failed`
- `journalctl --user -n 50 --no-pager`
- `systemctl --user status podman.service`

## Placeholder Substitution

The system automatically substitutes placeholders in command templates:

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{target}` | PM target name | `vllm-qwen25` |
| `{service_name}` | Full service name | `vllm-qwen25.service` |
| `{container_name}` | Container name | `vllm-qwen25` |
| `{port}` | Port number | `8002` |
| `{volume_name}` | Volume name | `vllm-qwen25-volume` |
| `{hostname}` | Hostname | `localhost` |

## Benefits

### For Users
- **Consistent Experience**: Same commands available regardless of which pm operation was used
- **Comprehensive Coverage**: All common troubleshooting scenarios covered
- **Easy Discovery**: Commands organized by category for easy navigation

### For Developers
- **DRY Principle**: Single source of truth for common actions
- **Easy Integration**: Simple function calls to add common actions
- **Maintainable**: Centralized command definitions easy to update
- **Extensible**: Easy to add new categories or commands

## Migration Guide

### Before (Inconsistent)
```python
# Each command had its own custom actions
console.print("[green]Optional actions:[/green]")
console.print(f"  View logs: pm logs {target}")
console.print(f"  Check status: systemctl --user status {target}.service")
# ... different commands for each operation
```

### After (Standardized)
```python
# Use common actions system
from operations.common_actions import show_essential_actions
show_essential_actions(target)
```

## Demo Script

Run the demonstration script to see the system in action:

```bash
python demo_common_actions.py
```

This shows:
- Basic usage examples
- Category-specific actions
- Integration examples
- Customization capabilities

## Future Enhancements

- **Context-Aware Commands**: Commands that adapt based on detected issues
- **Interactive Mode**: Allow users to select and execute commands directly
- **Command History**: Track which commands users run most frequently
- **Custom Categories**: Allow users to define their own command categories
