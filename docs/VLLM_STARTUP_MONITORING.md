# VLLM Startup Monitoring

This document describes the VLLM startup monitoring functionality that ensures VLLM model services are completely ready before restarting dependent services.

## Overview

The VLLM startup monitoring system addresses the issue where `sys-services-vllm-proxy` and `mcp-vllm-delegator` were being restarted immediately after starting a VLLM model service, without waiting for the model to be fully loaded and operational.

## Key Components

### VLLMStartupMonitor Class

Location: `managers/reinit/vllm_startup_monitor.py`

The main monitoring class that provides comprehensive startup verification for VLLM services.

#### Primary Method

```python
vllm_service_monitor_for_complete_start(
    container_name: str,
    timeout: int = 300,
    check_interval: float = 2.0
) -> bool
```

**Parameters:**
- `container_name`: Name of the VLLM container to monitor
- `timeout`: Maximum time to wait in seconds (default: 5 minutes)
- `check_interval`: Time between checks in seconds (default: 2 seconds)

**Returns:**
- `True` if service is fully ready
- `False` if timeout or error occurs

## Monitoring Stages

The monitoring process follows a comprehensive 5-stage verification:

### 1. 🐳 Container Status Check
- Verifies the container is in "running" state
- Detects container failures early

### 2. 🔌 Port Accessibility Check
- Tests if port 8005 is accessible for connections
- Ensures the service is binding to the correct port

### 3. ❤️ Health Endpoint Check
- Calls `GET /health` endpoint
- Verifies the VLLM service is responding to HTTP requests

### 4. 🧠 Model Loading Check
- Calls `GET /v1/models` endpoint
- Confirms that models are actually loaded and available
- Parses response to count loaded models

### 5. 🚀 API Responsiveness Check
- Sends a test completion request to `/v1/completions`
- Verifies the API can handle actual inference requests
- Uses minimal test payload to avoid resource consumption

## Integration Points

### VLLMReinitFlow Integration

The monitoring is integrated into both VLLM reinit flows:

```python
# In both _reinit_active_vllm_model_service and _reinit_non_active_vllm_model_service
console.print(f"[cyan]Waiting for {display_name} to be fully ready...[/cyan]")
if not self.startup_monitor.vllm_service_monitor_for_complete_start(display_name):
    console.print(f"[red]❌ {display_name} failed to become ready[/red]")
    return False
console.print()

# Only after this check passes do we restart support services
success = self.restart_vllm_support_services(display_name)
```

### VLLMModelManager Integration

The model manager now waits for complete startup during model switching:

```python
# In _start_vllm_backend method
console.print(f"[cyan]Waiting for {container_name} to be fully ready...[/cyan]")
if not self._get_startup_monitor().vllm_service_monitor_for_complete_start(container_name):
    console.print(f"[red]❌ {container_name} failed to become ready[/red]")
    return False
```

## User Experience

### Before Enhancement
```
19:45:23 | Restarted vllm-qwen2-5-coder-32b
19:45:23 | Stopping sys-services-vllm-proxy...
19:45:24 |   Stopped sys-services-vllm-proxy
# Model still loading, proxy fails to connect
```

### After Enhancement
```
19:45:23 | Restarted vllm-qwen2-5-coder-32b

Waiting for vllm-qwen2-5-coder-32b to be fully ready...
🔍 Monitoring vllm-qwen2-5-coder-32b startup...

┌─ VLLM Startup Monitor ─────────────────────────┐
│ Container: vllm-qwen2-5-coder-32b              │
│ Status: Loading models...                      │
│ Elapsed: 45.2s                                │
│ Stage: 🧠 Model Loading                        │
│ Details: Loading model files into memory       │
│ ⏳ Startup in progress...                      │
└────────────────────────────────────────────────┘

✅ vllm-qwen2-5-coder-32b is fully ready in 67.3s

19:46:30 | Stopping sys-services-vllm-proxy...
# Now proxy can successfully connect to ready model
```

## Configuration

### Timeout Settings

Default timeout is 300 seconds (5 minutes), which can be adjusted based on:
- Model size (larger models take longer to load)
- Hardware capabilities (GPU memory, CPU speed)
- Network conditions (for downloading model files)

### Check Interval

Default check interval is 2 seconds, providing:
- Responsive feedback to users
- Reasonable resource usage
- Quick detection of readiness

## Error Handling

The monitor handles various error conditions:

- **Container not found**: Returns error immediately
- **Container exited**: Returns error immediately
- **Port not accessible**: Continues monitoring (service may be starting)
- **Health endpoint timeout**: Continues monitoring (service may be loading)
- **Models not loaded**: Continues monitoring (normal during startup)
- **API not responsive**: Continues monitoring (normal during warmup)

## Benefits

1. **Reliability**: Ensures support services only restart when VLLM is ready
2. **User Experience**: Clear progress indication during model loading
3. **Debugging**: Detailed stage information helps identify startup issues
4. **Flexibility**: Configurable timeouts and intervals
5. **Robustness**: Comprehensive error handling and recovery

## Usage Examples

### Manual Usage
```python
from managers.reinit.vllm_startup_monitor import VLLMStartupMonitor

monitor = VLLMStartupMonitor(manager)
if monitor.vllm_service_monitor_for_complete_start('vllm-model-name'):
    print("Model is ready!")
else:
    print("Model failed to start")
```

### Command Line Usage
```bash
# The monitoring is automatically used during reinit
pm reinit vllm-qwen2-5-coder-32b

# Or during model switching
pm vllm switch vllm-qwen2-5-coder-32b
```

## Alternative Method

For simpler use cases, there's also a progress bar version:

```python
monitor.wait_for_vllm_ready_with_progress('container-name', timeout=300)
```

This provides a simpler progress bar display instead of the detailed live status panel.

## Future Enhancements

- **Health Metrics**: Add memory usage and GPU utilization monitoring
- **Model-Specific Timeouts**: Different timeouts based on model size
- **Parallel Monitoring**: Monitor multiple models simultaneously
- **Integration with Logging**: Enhanced logging of startup metrics
- **Webhook Notifications**: Alert external systems when models are ready
