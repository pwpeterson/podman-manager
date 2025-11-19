# vLLM Model Startup Troubleshooting Guide

## Current Issue Analysis

Based on the error message:
```
Restarting vllm-glm4-9b-chat...
Waiting for vllm-glm4-9b-chat to be ready via proxy on port 8002...
⠇ Port 8002 not accessible - 178.0s
```

## System Architecture

- **Port 8005**: Actual model services (vLLM/llama.cpp models)
- **Port 8002**: Proxy service (`sys-services-model-proxy`)
- **vllm-glm4-9b-chat**: Should run on port 8005
- **Proxy**: Routes requests from port 8002 to model on port 8005

## Diagnostic Steps

### 1. Quick Health Check

Run the health check script:
```bash
python3 health_check_script.py
```

### 2. Check Service Status

```bash
# Check if the model service is running
systemctl --user status vllm-glm4-9b-chat

# Check if the proxy service is running
systemctl --user status sys-services-model-proxy

# Check all user services
systemctl --user list-units --type=service --state=running | grep vllm
```

### 3. Check Service Logs

```bash
# Check model service logs
journalctl --user -u vllm-glm4-9b-chat -f --no-pager

# Check proxy service logs
journalctl --user -u sys-services-model-proxy -f --no-pager

# Check recent errors
journalctl --user -u vllm-glm4-9b-chat --since "10 minutes ago" --no-pager
```

### 4. Check Port Usage

```bash
# Check what's using port 8005 (model port)
ss -tlnp | grep :8005
netstat -tlnp | grep :8005

# Check what's using port 8002 (proxy port)
ss -tlnp | grep :8002
netstat -tlnp | grep :8002

# Check all ports in use
ss -tlnp | grep -E ':(800[0-9]|801[0-9])'
```

### 5. Check Container Status

```bash
# Check if containers are running
podman ps -a | grep vllm
podman ps -a | grep proxy

# Check container logs
podman logs vllm-glm4-9b-chat
podman logs sys-services-model-proxy
```

## Common Issues & Solutions

### Issue 1: Model Service Won't Start

**Symptoms**: Port 8005 not accessible, service fails to start

**Solutions**:
```bash
# Stop and restart the service
systemctl --user stop vllm-glm4-9b-chat
systemctl --user start vllm-glm4-9b-chat

# Reset failed state
systemctl --user reset-failed vllm-glm4-9b-chat
systemctl --user start vllm-glm4-9b-chat

# Check for resource issues
free -h
df -h
```

### Issue 2: Proxy Can't Connect to Model

**Symptoms**: Port 8002 accessible but can't reach model on 8005

**Solutions**:
```bash
# Restart proxy after model is running
systemctl --user restart sys-services-model-proxy

# Check proxy configuration
systemctl --user cat sys-services-model-proxy
```

### Issue 3: Port Conflicts

**Symptoms**: "Port already in use" errors

**Solutions**:
```bash
# Find what's using the port
sudo lsof -i :8005
sudo lsof -i :8002

# Kill conflicting processes (be careful!)
# sudo kill -9 <PID>
```

### Issue 4: Resource Exhaustion

**Symptoms**: Out of memory, disk space issues

**Solutions**:
```bash
# Check memory usage
free -h
top -o %MEM

# Check disk space
df -h

# Check GPU memory (if applicable)
nvidia-smi
```

## Recovery Procedures

### Full Service Restart

```bash
# Stop all related services
systemctl --user stop vllm-glm4-9b-chat
systemctl --user stop sys-services-model-proxy

# Wait a moment
sleep 5

# Start model service first
systemctl --user start vllm-glm4-9b-chat

# Wait for model to be ready (check port 8005)
while ! nc -z localhost 8005; do sleep 1; done

# Start proxy service
systemctl --user start sys-services-model-proxy
```

### Using Podman Manager

```bash
# Use the podman manager for restart
python3 podman_manager.py reinit vllm-glm4-9b-chat

# Or enhanced reinit with AI troubleshooting
python3 podman_manager.py enhanced-reinit vllm-glm4-9b-chat

# Check status
python3 podman_manager.py list vllm
```

### Switch to Different Model

```bash
# Switch to a different working model
python3 podman_manager.py vllm-switch vllm-qwen25-coder-32b

# Or switch to llama.cpp model
python3 podman_manager.py vllm-switch llama-kimi-k2-thinking_q2
```

## Monitoring Commands

```bash
# Monitor service status in real-time
watch -n 2 'systemctl --user is-active vllm-glm4-9b-chat sys-services-model-proxy'

# Monitor ports
watch -n 2 'ss -tlnp | grep -E ":(8002|8005)"'

# Monitor logs
journalctl --user -u vllm-glm4-9b-chat -f
```

## Testing Endpoints

```bash
# Test model endpoint directly (port 8005)
curl -f http://localhost:8005/health || echo "Model not responding"

# Test proxy endpoint (port 8002)
curl -f http://localhost:8002/health || echo "Proxy not responding"

# Test with timeout
timeout 10 curl http://localhost:8005/health
```

## Next Steps

1. **Run the health check script** to get current status
2. **Check service logs** for specific error messages
3. **Try the recovery procedures** based on what you find
4. **Consider switching models** if vllm-glm4-9b-chat continues to fail

## Getting Help

If issues persist, gather this information:
- Output of `python3 health_check_script.py`
- Service status: `systemctl --user status vllm-glm4-9b-chat`
- Recent logs: `journalctl --user -u vllm-glm4-9b-chat --since "30 minutes ago"`
- System resources: `free -h && df -h`
- Port usage: `ss -tlnp | grep -E ':(8002|8005)'`
