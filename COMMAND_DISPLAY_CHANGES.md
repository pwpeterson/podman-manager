# Command Display Changes

## Overview
Changed the error message display when commands require stack or service arguments but none are provided. Instead of showing the generic message "A stack or service is required, use pm list for names", the system now displays contextual hierarchical lists.

## Implementation Details

### Changes Made
1. **Modified `CustomArgumentParser.error()` method** in `podman_manager.py`
   - Replaced generic error message with call to `_show_required_target_list()`

2. **Added new methods to `CustomArgumentParser` class**:
   - `_show_required_target_list()` - Determines command type and shows appropriate display
   - `_show_stack_list()` - Shows only stacks for stack-only commands
   - `_show_service_hierarchy()` - Shows full hierarchy with optional stack dimming

### Command Categories

#### Stack-Only Commands
- `down`, `uninstall`
- **Display**: Simple list of available stacks only
- **Example**: `pm down` shows only stack names in a tree format

#### Service-Only Commands
- `logs`, `exec`, `diagnose`, `reset-failed`, `show-service-file`, `rebuild`
- **Display**: Full hierarchy with stacks dimmed (using `[dim cyan]` formatting)
- **Example**: `pm logs` and `pm rebuild` show all stacks and services but stacks are visually de-emphasized

#### Mixed Commands (Accept Both)
- `install`, `start`, `stop`, `restart`, `enable`, `disable`, etc.
- **Display**: Full hierarchy with normal stack highlighting
- **Example**: `pm install` and `pm start` show all stacks and services with full color formatting

## Behavior Examples

### Stack-Only Command (`pm down`)
```
Available stacks:
Stacks
├── local-ai-stack
├── mcp-services-stack
├── supabase-stack
├── sys-services-stack
├── taskflow-stack
├── user-mgmt-stack
├── vllm-stack
└── web-apps-stack
```

### Service-Only Command (`pm rebuild`)
```
Available stacks and services:

Services available:
├── local-ai-stack          # Dimmed stack name
│   ├── local-ai-caddy-dav.service (quadlet)     # Green services
│   ├── local-ai-caddy.service (quadlet)
│   └── ...
├── vllm-stack              # Dimmed stack name
│   ├── vllm-delegator-mcp.service (quadlet)     # Green services
│   ├── vllm-proxy.service (quadlet)
│   └── vllm-qwen25-coder-32b-instruct-awq.service (quadlet)
└── ...
```

### Mixed Command (`pm install`)
```
Available stacks and services:

Stacks & Services
├── local-ai-stack          # Normal stack highlighting
│   ├── local-ai-caddy-dav.service (quadlet)     # Status-colored services
│   ├── local-ai-caddy.service (quadlet)
│   └── ...
├── vllm-stack              # Normal stack highlighting
│   ├── vllm-delegator-mcp.service (quadlet)
│   ├── vllm-proxy.service (quadlet)
│   └── vllm-qwen25-coder-32b-instruct-awq.service (quadlet)
└── ...
```

## Technical Implementation

### Command Detection
The system analyzes `sys.argv` to determine which command was used, then categorizes it:
- Extracts the command name from command line arguments
- Matches against predefined command categories
- Applies appropriate display logic

### Display Logic
- **Stack-only**: Uses `QuadletManager` and `PodmanManager` to discover available stacks
- **Service hierarchy**: Leverages existing `QuadletDisplayManager._get_all_projects_and_services()` method
- **Stack dimming**: Applies `[dim cyan]` Rich formatting to stack names when `dim_stacks=True`
- **Service cleaning**: Removes existing color codes from service names when stacks are dimmed

### Fallback Handling
- Primary: Uses QuadletManager for quadlet services
- Secondary: Falls back to PodmanManager for compose services
- Final: Shows "No services or stacks found" if both fail

## Benefits

1. **Contextual Help**: Users see exactly what they need for each command type
2. **Visual Hierarchy**: Clear distinction between stacks and services
3. **Reduced Cognitive Load**: Service-only commands dim irrelevant stack information
4. **Consistent UX**: Maintains the same rich tree display format as `pm list`
5. **Backward Compatibility**: No breaking changes to existing functionality

## Files Modified
- `podman_manager.py` - Added new error handling and display methods
- `test_command_display.py` - Created for testing the new functionality
- `COMMAND_DISPLAY_CHANGES.md` - This documentation file
