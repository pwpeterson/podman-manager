# VLLM Startup Monitoring

This document describes the VLLM startup monitoring functionality that ensures VLLM model services are completely ready before restarting dependent services.

## Overview

The VLLM startup monitoring system addresses the issue where `sys-services-vllm-proxy` and `mcp-vllm-delegator` were being restarted immediately after starting a VLLM model service, without waiting for the model to be fully loaded and operational.

## Key Components

### ModelStartupMonitor Class

Location: `docs/model_startup_monitor.py`

The main monitoring class that provides comprehensive startup verification for both vLLM and llama.cpp models using direct internal health checks on port 8005.

#### Primary Method

```python
monitor_model_startup(
    container_name: str,
    timeout: int = 300
) -> bool
```

**Parameters:**
- `container_name`: Name of the model container to monitor (vLLM or llama.cpp)
- `timeout`: Maximum time to wait in seconds (default: 5 minutes)

**Returns:**
- `True` if service is fully ready
- `False` if timeout or error occurs

## Monitoring Stages

The monitoring process follows a comprehensive 5-stage verification using direct internal health checks on port 8005:

### 1. 🐳 Container Status Check
- Verifies the container is in "running" state
- Detects container failures early

### 2. 🔌 Port Accessibility Check
- Tests if port 8005 is accessible for connections (direct internal check)
- Ensures the model service is binding to the correct port

### 3. ❤️ Health Endpoint Check
- Calls `GET http://127.0.0.1:8005/health` (direct internal)
- Verifies the model service is responding to HTTP requests

### 4. 🧠 Model Loading Check
- Calls `GET http://127.0.0.1:8005/v1/models` (direct internal)
- Confirms that models are actually loaded and available
- Parses response to count loaded models

### 5. 🚀 API Responsiveness Check
- Sends a test completion request to `http://127.0.0.1:8005/v1/completions` (direct internal)
- Verifies the API can handle actual inference requests
- Uses minimal test payload to avoid resource consumption

## Integration Points

### ModelReinitFlow Integration

The monitoring is integrated into both model reinit flows:

```python
# In both _reinit_active_model_service and _reinit_non_active_model_service
console.print(f"Waiting for {display_name} to be fully ready...")
if not self.startup_monitor.monitor_model_startup(display_name):
    console.print(f"❌ {display_name} failed to become ready")
    return False
console.print()

# Only after this check passes do we restart support services
success = self.restart_model_support_services(display_name)
```

### VLLMModelManager Integration

The model manager now waits for complete startup during model switching:

```python
# In _start_vllm_backend method
console.print(f"[cyan]Waiting for {container_name} to be fully ready...[/cyan]")
if not self._get_startup_monitor().monitor_model_startup(container_name):
    console.print(f"[red]❌ {container_name} failed to become ready[/red]")
    return False
```

## User Experience

### Before Fix
```
19:45:23 | Restarted vllm-qwen2-5-coder-32b
19:45:23 | Stopping sys-services-model-proxy...
19:45:24 |   Stopped sys-services-model-proxy
# Model still loading, but monitoring tries to check via proxy (port 8002)
# Proxy hasn't started yet, so monitoring fails
⏰ Timeout waiting for vllm-qwen2-5-coder-32b (300s)
❌ vllm-qwen2-5-coder-32b failed to become ready
```

### After Fix
```
19:45:23 | Restarted vllm-qwen2-5-coder-32b

Waiting for vllm-qwen2-5-coder-32b to be fully ready...
🔍 Monitoring vllm-qwen2-5-coder-32b startup...
Model type: vllm, Direct port: 8005
Waiting for vllm-qwen2-5-coder-32b to be ready on port 8005...

# Direct monitoring on port 8005 (internal)
✅ vllm-qwen2-5-coder-32b (vllm) is fully ready in 67.3s

19:46:30 | Stopping sys-services-model-proxy...
# Now proxy starts and connects to ready model
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
from docs.model_startup_monitor import ModelStartupMonitor

monitor = ModelStartupMonitor(manager)
if monitor.monitor_model_startup('vllm-model-name'):
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

## Key Fix

The critical fix was changing from proxy-based monitoring (port 8002) to direct internal monitoring (port 8005):

- **Before**: Tried to check model readiness via proxy service that hadn't started yet
- **After**: Checks model readiness directly on port 8005, then starts proxy services

This eliminates the circular dependency where the proxy needed the model to be ready, but the monitoring needed the proxy to be running.

## Future Enhancements

- **Health Metrics**: Add memory usage and GPU utilization monitoring
- **Model-Specific Timeouts**: Different timeouts based on model size
- **Parallel Monitoring**: Monitor multiple models simultaneously
- **Integration with Logging**: Enhanced logging of startup metrics
- **Webhook Notifications**: Alert external systems when models are ready
