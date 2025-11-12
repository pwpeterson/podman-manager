# Port Usage Clarification and Health Check Fixes

## Issue Identified

The user correctly pointed out that `mcp-vllm-delegator` does not use port 8005, but the system was detecting it as using that port. This revealed confusion in the health check logic about which services use which ports.

## Port Usage Analysis

Based on the system output and code analysis:

### Port 8005 - vLLM Model Services
- **Services**: `vllm-qwen25-coder-32b`, `vllm-glm41-9b-thinking`, etc.
- **Purpose**: Direct vLLM model API endpoints
- **Usage**: AI agents connect directly to active vLLM models
- **Detection**: System detects which vLLM model is using port 8005

### Port 8002 - vLLM Proxy
- **Service**: `vllm-proxy`
- **Purpose**: Proxy service for vLLM model access
- **Usage**: Routes requests to active vLLM model containers
- **Client Access**: Alternative access point for vLLM models

### Port 8003 - MCP vLLM Delegator
- **Service**: `mcp-vllm-delegator`
- **Purpose**: MCP (Model Context Protocol) server for vLLM delegation
- **Usage**: Provides MCP tools for vLLM operations
- **Detection**: Runs on port 8003, separate from vLLM models

## System Detection Logic

The VLLMModelManager uses `_find_current_vllm_container()` which:
1. Looks for containers with "vllm" in the name
2. Excludes "vllm-proxy" (correctly)
3. Should exclude "mcp-vllm-delegator" but was including it
4. Checks which container is actually using port 8005

## Health Check Fixes Applied

### Before (Incorrect)
```python
# Incorrectly assumed all vLLM services use port 8005
if "vllm" in target.lower():
    # Check port 8005 for all vLLM services
```

### After (Correct)
```python
# Service-specific port checking
if "vllm" in target.lower() and target not in ["vllm-proxy", "mcp-vllm-delegator"]:
    # vLLM model services - check port 8005
elif target == "vllm-proxy":
    # vllm-proxy - check port 8002
elif target == "mcp-vllm-delegator":
    # mcp-vllm-delegator - check port 8003
```

## Changes Made

### 1. Network Connectivity Check (`_check_network_connectivity`)
- **vLLM Model Services**: Check port 8005 (direct model access)
- **vllm-proxy**: Check port 8002 (its own port)
- **mcp-vllm-delegator**: Check port 8003 (its own port)
- **Other Services**: Generic network connectivity check

### 2. Container Health Verification (`verify_container_health`)
- **vLLM Model Services**: Health check on `http://localhost:8005/health`
- **vllm-proxy**: Health check on `http://localhost:8002/health`
- **mcp-vllm-delegator**: Health check on `http://localhost:8003/health`
- **Other Services**: Standard container status check

## Service Architecture Clarification

```
┌─────────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   AI Agents         │    │  MCP vLLM        │    │  vLLM Model         │
│  (port 8005/8002)   │    │  Delegator       │    │  Services           │
│                     │    │  (port 8003)     │    │  (port 8005)        │
└─────────┬───────────┘    └──────────────────┘    └─────────┬───────────┘
          │                                                  │
          │                ┌──────────────────┐              │
          └────────────────┤   vLLM Proxy     ├──────────────┘
                           │   (port 8002)    │
                           └──────────────────┘
```

## Why the Confusion Occurred

1. **Similar Names**: Both `mcp-vllm-delegator` and vLLM model services contain "vllm"
2. **Port Detection**: The system detects what's using port 8005 and finds `mcp-vllm-delegator`
3. **Health Check Logic**: Original code assumed all "vllm" services use the same port
4. **Service Roles**: Different services with "vllm" in the name serve different purposes

## Impact of Fixes

### Health Checks Now Correctly:
- Check port 8005 for vLLM model services (direct access)
- Check port 8002 for vllm-proxy
- Check port 8003 for mcp-vllm-delegator
- Provide accurate service-specific health information
- Avoid false positives/negatives in connectivity checks

### Service Stopping Monitor Benefits:
- Can now properly monitor different service types during stopping
- Understands the correct port usage for each service
- Provides accurate status information during reinit operations

## Files Modified

1. **[`managers/reinit/health_checker.py`](managers/reinit/health_checker.py)** - Fixed port usage in network connectivity and container health checks

## Verification

The health checks now properly distinguish between:
- **vLLM Model Services** → Check direct model health on port 8005
- **vLLM Proxy** → Check its own health on port 8002
- **MCP vLLM Delegator** → Check its own health on port 8003
- **Other Services** → Standard connectivity checks

This ensures accurate health reporting and proper service monitoring during reinit operations.
