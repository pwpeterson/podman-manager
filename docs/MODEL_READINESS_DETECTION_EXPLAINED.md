# Model Readiness Detection in Podman Manager

## How the System Determines Model Readiness

The podman manager uses a sophisticated **Enhanced Model Startup Monitor** to determine when llama.cpp and vLLM models are truly ready, not just when systemctl reports success.

## Current Flow (Fixed)

### 1. Service Start
```
14:10:03 | Restarting llama-kimi-k2-thinking-q1...
14:10:03 |   Started llama-kimi-k2-thinking-q1
```
**Note**: "Started" means systemctl succeeded, NOT that the model is ready.

### 2. Model Readiness Monitoring
```
Waiting for llama-kimi-k2-thinking-q1 to be fully ready...
🔍 Monitoring llama-kimi-k2-thinking-q1 startup...
Model type: llama.cpp, Port: 8002, Endpoint: http://localhost:8002
```

### 3. Progressive Health Checks
The enhanced monitor performs these checks in sequence:

#### Container Status Check
- Verifies container is running (not error/exited/dead)
- Handles container startup time

#### Port Accessibility Check
- Tests if port 8002 (vllm-proxy) is accessible
- Waits for network binding

#### Health Endpoint Check
- `GET http://localhost:8002/health`
- Verifies basic service responsiveness

#### Models Endpoint Check
- `GET http://localhost:8002/v1/models`
- Confirms model is loaded and available
- **Critical for llama.cpp**: Model loading takes significant time

#### API Responsiveness Check
- `POST http://localhost:8002/v1/completions` (test request)
- Verifies model can actually process requests
- Final confirmation of readiness

### 4. Model Ready Confirmation
```
14:10:45 |   llama-kimi-k2-thinking-q1 is fully ready
```
**This is when the model is actually ready to serve requests.**

### 5. Support Services Restart
- sys-services-vllm-proxy restart
- mcp-vllm-delegator restart
- VLLM_URL updates

### 6. Final Success
```
14:10:50 | Successfully reinitialized llama-kimi-k2-thinking-q1
```

## Why llama.cpp Models Take Longer

### Model Loading Process
1. **Container Start**: ~2-5 seconds
2. **CUDA Backend Loading**: ~5-10 seconds
3. **Model File Loading**: **30-120 seconds** (depends on model size)
4. **Memory Allocation**: ~5-15 seconds
5. **API Initialization**: ~2-5 seconds

**Total**: 45-155 seconds for large models like Kimi-K2-Thinking

### Progress Indicators
During the wait, you'll see:
```
[yellow]Container starting (running) - 15.2s[/yellow]
[yellow]Port 8002 not ready - 18.5s[/yellow]
[yellow]Health check: Health endpoint not available - 25.1s[/yellow]
[yellow]Loading models: No models loaded yet - 45.8s[/yellow]
[yellow]API warming up: API timeout (warming up) - 67.2s[/yellow]
```

## Enhanced Monitor Configuration

### Model Type Detection
- **llama.cpp models**: Names starting with `llama-`
- **vLLM models**: Names starting with `vllm-`
- **Port routing**: All models use port 8002 (via vllm-proxy)

### Timeout Settings
- **Default timeout**: 300 seconds (5 minutes)
- **Health check timeout**: 5 seconds per request
- **Models check timeout**: 10 seconds per request
- **API test timeout**: 15 seconds per request

### Retry Logic
- **Container failures**: Max 3 consecutive failures before abort
- **Network checks**: 2-second intervals
- **Model loading**: 3-second intervals (longer for heavy operations)

## Architecture: models-stack

### Port Usage
- **Port 8005**: Direct model container port (internal)
- **Port 8002**: vllm-proxy (user-facing endpoint)
- **All models**: Accessed via vllm-proxy for consistency

### Service Dependencies
1. **Model service** (e.g., llama-kimi-k2-thinking-q1)
2. **sys-services-vllm-proxy** (routes requests to active model)
3. **mcp-vllm-delegator** (MCP integration)

## Troubleshooting Model Startup

### Common Issues
1. **"Port not ready"**: Model container starting
2. **"Health endpoint not available"**: Service initializing
3. **"No models loaded yet"**: Model file loading (normal for large models)
4. **"API timeout"**: Model warming up (normal)

### When to Be Concerned
- **Container status: error**: Check container logs
- **Timeout after 5 minutes**: Likely configuration issue
- **Health endpoint returns 500**: Service error

### Manual Verification
```bash
# Check container status
podman ps | grep llama-kimi-k2-thinking-q1

# Check service logs
journalctl --user -u llama-kimi-k2-thinking-q1.service -f

# Test health endpoint
curl http://localhost:8002/health

# Test models endpoint
curl http://localhost:8002/v1/models

# Test API
curl -X POST http://localhost:8002/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello", "max_tokens": 5}'
```

## Performance Optimization

### Model Loading Speed
- **SSD storage**: Faster model file loading
- **Sufficient RAM**: Avoid swapping during load
- **GPU memory**: Proper CUDA allocation

### Monitoring Efficiency
- **Progressive intervals**: Shorter waits for quick checks
- **Timeout protection**: Prevents hanging on unresponsive services
- **Graceful degradation**: Continues with warnings on non-critical failures

## Integration with AI Troubleshooting

The enhanced monitor integrates with:
- **llama.cpp troubleshooter**: Automatic fix for configuration issues
- **AI failure analysis**: Intelligent error diagnosis
- **Timeout diagnostics**: Specialized handling for system issues

## Summary

The **Enhanced Model Startup Monitor** ensures that:
1. ✅ Models are truly ready before reporting success
2. ✅ Support services are updated with correct endpoints
3. ✅ Users get accurate feedback on startup progress
4. ✅ Failures are detected and diagnosed intelligently
5. ✅ Large models get appropriate time to load

The "Started" message is just the beginning - the real confirmation is "is fully ready".
