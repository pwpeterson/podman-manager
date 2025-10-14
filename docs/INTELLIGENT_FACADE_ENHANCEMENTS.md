# Intelligent PM Facade Enhancements

## Overview

The `pm` command now features intelligent project type detection that automatically determines whether to use podman compose or quadlet (systemd) mode based on the target service.

## Key Features

### 1. Automatic Mode Detection

- **Default mode**: `auto` (was previously `quadlet`)
- **Detection logic**:
  1. Known vLLM services → `quadlet`
  2. Systemd service exists → `quadlet`
  3. Found in compose files → `compose`
  4. Fallback to compose if compose files available
  5. Final fallback to quadlet

### 2. Enhanced Command Options

```bash
# New options
pm --mode [auto|quadlet|compose] <command>  # Mode selection
pm --debug-detection <command>              # Show detection details
pm targets                                   # List available targets by type
```

### 3. Intelligent Fallback

- When operations fail, suggests alternative mode
- Example: If quadlet command fails, suggests trying compose mode
- Provides helpful command suggestions

### 4. Detection Examples

| Target | Detected Mode | Reason |
|--------|---------------|--------|
| `vllm-qwen25` | quadlet | Known vLLM service |
| `vllm-stack` | quadlet | Known vLLM service |
| `postgres` | compose | Found in compose file |
| `unknown-service` | compose | Default (compose files available) |
| `test.service` | unknown | Systemd unit not found |

## Usage Examples

### Basic Usage (Auto-Detection)
```bash
# Automatically detects project type
pm list vllm-qwen25     # → Uses quadlet mode
pm restart postgres     # → Uses compose mode
pm start vllm-stack     # → Uses quadlet mode
```

### Debug Mode
```bash
# See detection logic
pm --debug-detection list vllm-qwen25
# Output: Mode selection: quadlet (Auto-detected: Known vLLM service: vllm-qwen25)
```

### Manual Mode Override
```bash
# Force specific mode
pm --mode compose restart vllm-qwen25  # Force compose mode
pm --mode quadlet start postgres       # Force quadlet mode
```

### List Available Targets
```bash
pm targets
# Shows table of quadlet vs compose services
```

## Architecture

### New Components

1. **`project_detector.py`** - Core detection logic
   - `ProjectTypeDetector` class
   - Methods: `detect_project_type()`, `get_intelligent_mode()`, `suggest_alternative_mode()`

2. **Enhanced `podman_manager.py`**
   - Integrated detection system
   - Fallback handling
   - New `targets` command

### Detection Flow

```
User Command → ProjectTypeDetector → Mode Selection → Manager Initialization → Command Execution
                     ↓
              [Auto/Manual Mode] → [Quadlet/Compose Manager] → [Operation Success/Failure]
                     ↓                                                    ↓
              [Debug Output]                                    [Fallback Suggestion]
```

## Benefits

1. **Seamless Experience**: Users don't need to remember which services use which technology
2. **Backward Compatibility**: All existing commands work unchanged
3. **Intelligent Defaults**: Auto-detection reduces cognitive load
4. **Helpful Feedback**: Debug mode and fallback suggestions aid troubleshooting
5. **Unified Interface**: Single `pm` command for all container management

## Implementation Details

### Known vLLM Services
```python
vllm_services = {
    "vllm-qwen25": "vllm-qwen25-coder-32b-instruct-awq.service",
    "vllm-proxy": "vllm-proxy.service",
    "vllm-delegator": "vllm-delegator-mcp.service",
    "vllm-stack": "vllm-stack.target"
}
```

### Detection Priority
1. User-specified mode (highest priority)
2. Known vLLM services
3. Systemd unit existence check
4. Compose file service lookup
5. Default fallback logic

### Fallback Logic
- **Quadlet fails** → Suggest compose if service found in compose files
- **Compose fails** → Suggest quadlet if systemd service exists
- **Both available** → Show both options

## Testing

Run the test suite:
```bash
uv run python test_detection.py
```

Test real commands:
```bash
./pm targets                              # List all targets
./pm --debug-detection list vllm-qwen25  # Test quadlet detection
./pm --debug-detection list postgres     # Test compose detection
```

## Migration Notes

- **Breaking Change**: Default mode changed from `quadlet` to `auto`
- **Compatibility**: All existing scripts work unchanged due to intelligent detection
- **New Features**: `targets` command and `--debug-detection` flag
- **Enhanced Help**: Updated help text reflects new capabilities

## Future Enhancements

1. **Real-time Fallback**: Automatically retry with alternative mode on failure
2. **Service Discovery**: Dynamic discovery of new services
3. **Configuration**: User-configurable detection rules
4. **Performance**: Cache detection results for faster subsequent calls
5. **Integration**: Extend detection to other container orchestrators
