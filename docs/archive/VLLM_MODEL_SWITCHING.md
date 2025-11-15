# vLLM Model Switching Integration

This document describes the enhanced vLLM model switching functionality integrated into the Podman Manager application.

## Overview

The vLLM model switching feature allows you to dynamically switch between different vLLM model containers while maintaining the proxy configuration. This version includes enhanced startup/shutdown monitoring with progress indicators for the multi-minute operations typical of vLLM models.

## Enhanced Features

### Automatic vLLM Service Detection
- Automatically detects vLLM services by name patterns (`vllm` in service name)
- Applies enhanced handling for all vLLM operations (start, restart, reinit)
- No manual configuration required

### Progress Indicators
- **Stopping Phase**: Spinner shows graceful shutdown progress (up to 1 minute)
- **Starting Phase**: Spinner shows startup progress with health monitoring (up to 5 minutes)
- **Real-time Updates**: Progress messages show elapsed time

### Robust Shutdown Process
1. **Graceful Stop**: Attempts `podman stop -t 30` for clean shutdown
2. **Port Monitoring**: Waits for port 8005 to be released
3. **Force Cleanup**: If needed, force kills processes using the port
4. **Verification**: Confirms port is fully available before proceeding

### Smart Startup Monitoring
1. **Health Endpoint**: Tests `/health` endpoint for service readiness
2. **Container Status**: Monitors container state and port usage
3. **Timeout Handling**: 5-minute timeout with graceful degradation
4. **Fallback Logic**: Multiple methods to verify service readiness

## New Components

### VLLMModelManager (`managers/vllm_model_manager.py`)

Enhanced manager class that handles:
- Graceful container shutdown with progress indicators
- Smart startup monitoring with health checks
- Port cleanup and process management
- Status monitoring and reporting
- Automatic vLLM service detection

### Integration Points

1. **ReinitManager** - Enhanced to support vLLM model switching during reinit operations
2. **ServiceLifecycle** - Enhanced to support vLLM model switching during restart operations
3. **QuadletOperations** - Updated method signatures to pass through vLLM model parameters
4. **CommandRouter** - New command handlers for vLLM management
5. **CLI Parser** - New commands and parameters for vLLM operations

## New Commands

### vLLM Management Commands

```bash
# Switch vLLM backend to a different model container
pm vllm-switch <model-container-name>
pm vllm-switch vllm-qwen25-coder-32b
pm vllm-switch vllm-glm46 --proxy-image custom-proxy:latest

# Show current vLLM configuration and status
pm vllm-status

# List available vLLM model containers
pm vllm-models
```

### Enhanced Existing Commands

```bash
# Reinit with vLLM model switching
pm reinit vllm-proxy --vllm-model vllm-qwen25-coder-32b
pm reinit vllm-stack --vllm-model vllm-glm46

# Restart with vLLM model switching
pm restart vllm-proxy --vllm-model vllm-qwen25-coder-32b
pm restart vllm-stack --vllm-model vllm-glm46
```

## How It Works

### vLLM Model Switching Process

1. **Graceful Shutdown**: Attempts to gracefully stop the current vLLM container (30s timeout)
2. **Port Cleanup**: Waits for port 8005 to be released, with spinner progress indication
3. **Force Cleanup**: If needed, force kills processes using port 8005 (vLLM port)
4. **Backend Start**: Starts the new vLLM model container with startup monitoring
5. **Readiness Check**: Waits up to 5 minutes for the vLLM service to be ready (health endpoint)
6. **Proxy Restart**: Stops and removes the old proxy, starts new proxy with updated `VLLM_URL`

### Enhanced vLLM Service Handling

When working with vLLM services (detected automatically), the system now:
- **Automatic Detection**: Recognizes vLLM services by name patterns
- **Proper Shutdown**: Ensures current vLLM models are fully stopped before starting new ones
- **Progress Indicators**: Shows spinners during stopping (up to 1 minute) and starting (up to 5 minutes)
- **Health Monitoring**: Tests the `/health` endpoint to confirm service readiness
- **Graceful Fallbacks**: Uses container status and port checks if health endpoint unavailable

### Configuration

The VLLMModelManager uses these default settings:
- **vLLM Port**: 8005
- **Proxy Container**: `vllm-proxy`
- **Proxy Port**: 8002
- **Network**: `local-ai-network`
- **Proxy Image**: `vllm-proxy:latest` (configurable)
- **Shutdown Timeout**: 30 seconds graceful, 60 seconds total
- **Startup Timeout**: 300 seconds (5 minutes)

### Integration with Existing Operations

When you specify `--vllm-model` with `reinit` or `restart` commands:
1. The vLLM model switch happens first
2. Then the regular reinit/restart operation proceeds
3. This ensures the new model is active before the service restarts

## Usage Examples

### Basic Model Switching

```bash
# Switch to Qwen2.5 Coder 32B model
pm vllm-switch vllm-qwen25-coder-32b

# Check current status
pm vllm-status

# List available models
pm vllm-models
```

### Combined Operations

```bash
# Reinit vLLM proxy with model switch
pm reinit vllm-proxy --vllm-model vllm-qwen25-coder-32b -v

# Restart entire vLLM stack with model switch
pm restart vllm-stack --vllm-model vllm-glm46 -v

# Automatic enhanced handling for vLLM services
pm reinit vllm-glm4-9b-chat  # Automatically uses enhanced vLLM handling
pm start vllm-qwen25-coder-32b  # Automatically monitors startup
pm restart vllm-proxy  # Automatically ensures proper shutdown
```

### Advanced Usage

```bash
# Switch with custom proxy image
pm vllm-switch vllm-qwen25-coder-32b --proxy-image my-custom-proxy:v1.0

# Verbose model switching
pm vllm-switch vllm-glm46 -v
```

## Error Handling

The vLLM model manager includes comprehensive error handling:
- Port cleanup failures are reported and abort the operation
- Container start failures are caught and reported
- Proxy restart failures are handled gracefully
- All operations include verbose logging when `-v` flag is used

## Dependencies

The vLLM model switching functionality requires:
- `psutil` - For process management and port cleanup
- `requests` - For health endpoint checking (optional, graceful fallback if unavailable)
- `loguru` - For logging (already used in the project)
- `rich` - For console output and progress indicators (already used in the project)

## Files Modified/Added

### New Files
- `managers/vllm_model_manager.py` - Main vLLM model management class
- `VLLM_MODEL_SWITCHING.md` - This documentation
- `test_vllm_integration.py` - Integration test script

### Modified Files
- `managers/reinit_manager.py` - Added automatic vLLM detection and enhanced handling
- `managers/service_lifecycle.py` - Added enhanced vLLM startup/restart handling
- `operations/quadlet_ops.py` - Updated method signatures
- `cli/command_router.py` - Added new command handlers
- `cli/parser.py` - Added new commands and parameters
- `cli/help_formatter.py` - Added vLLM commands to help

## Testing

Run the integration test to verify the setup:

```bash
python test_vllm_integration.py
```

This will test:
- VLLMModelManager creation
- Method functionality
- Integration with ReinitManager
- CLI parser integration

## Future Enhancements

Potential future improvements:
- Configuration file support for custom ports/networks
- Health checking for model containers
- Automatic model discovery
- Model performance metrics
- Integration with AI agent selection
