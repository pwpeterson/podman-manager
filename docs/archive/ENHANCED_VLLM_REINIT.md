# Enhanced vLLM Reinit Process

This document describes the enhanced reinit process for vLLM model containers that properly detects, stops, and removes the current active vLLM model before reinitializing.

## Overview

When reinitializing a vLLM model container (e.g., `pm reinit 9b-chat`), the system now:

1. **Detects** the currently active vLLM model using port 8005
2. **Stops** the current vLLM container gracefully (always, to free port 8005)
3. **Removes** the systemd service file for the stopped container
4. **Proceeds** with the standard reinit process for the target container

## Expected Output Format

When running `pm reinit 9b-chat`, you should see output like this:

```
Reinitializing vllm-glm4-9b-chat...

Current 8005: vllm-glm4-9b-Thinking
🔄 Stopping vllm-glm4-9b-Thinking... (animated spinner)
  Stopped vllm-glm4-9b-Thinking

Removing vllm-glm4-9b-Thinking.service file...
  Removed vllm-glm4-9b-Thinking.service file

Reloading systemd daemon...
  Reloaded systemd daemon.

... (rest of reinit process continues)
```

## Implementation Details

### vLLM Container Detection and Logic

The system uses multiple methods to detect the currently active vLLM container:

1. **Container Inspection**: Checks all running vLLM containers and their network settings
2. **Port Mapping**: Examines container port mappings to find which container is using port 8005
3. **Process Enumeration**: Uses system process information to identify the container using port 8005

**Important Logic**: The system **always** stops and removes the **currently running** vLLM container to ensure port 8005 is available for the target container. This prevents port conflicts and ensures clean transitions between vLLM models.

### Enhanced Reinit Manager

The `ReinitManager` class has been enhanced with:

- **vLLM Detection**: Automatically detects vLLM model services during reinit
- **Graceful Stopping**: Properly stops the current vLLM container with a 60-second timeout
- **Visual Feedback**: Uses animated spinners to show progress during stopping operations
- **Service File Cleanup**: Removes both the old and current vLLM service files
- **Verbose Logging**: Provides detailed output in verbose mode

### Key Files Modified

- `managers/reinit_manager.py`: Enhanced `_reinit_service_direct()` method
- `managers/vllm_model_manager.py`: Improved container detection logging

## Usage Examples

### Basic vLLM Reinit
```bash
pm reinit 9b-chat
```

### Verbose vLLM Reinit
```bash
pm reinit 9b-chat -v
```

### vLLM Reinit with Build
```bash
pm reinit 9b-chat --quadlet-build
```

## Troubleshooting

### No vLLM Container Detected
If no vLLM container is detected:
- Check if any vLLM containers are running: `podman ps | grep vllm`
- Verify port 8005 usage: `netstat -tlnp | grep 8005`
- Use verbose mode for detailed detection logs: `pm reinit target -v`

### Container Stop Failures
If the vLLM container fails to stop:
- The system will show a warning but continue with reinit
- Check container logs: `podman logs <container-name>`
- Force stop if needed: `podman stop -t 0 <container-name>`

### Service File Removal Issues
If service file removal fails:
- The system shows a warning but continues
- Manually remove if needed: `rm ~/.config/systemd/user/<container>.service`
- Reload daemon: `systemctl --user daemon-reload`

## Benefits

1. **Clean Transitions**: Properly stops old vLLM models before starting new ones
2. **Port Conflict Prevention**: Ensures port 8005 is available for the new model
3. **Service File Hygiene**: Removes obsolete systemd service files
4. **Reliable Detection**: Uses multiple methods to find the active vLLM container
5. **Visual Feedback**: Animated spinners show progress during long operations
6. **Professional UX**: Consistent with other podman manager operations
7. **Verbose Feedback**: Provides clear status messages during the process

## Integration with Existing Features

This enhancement integrates seamlessly with:

- **vLLM Model Switching**: Works with `pm vllm-switch` commands
- **Stack Management**: Handles vLLM stacks properly
- **AI Diagnostics**: Triggers AI analysis on failures
- **Build Systems**: Compatible with quadlet and podman builds
- **Verbose Mode**: Provides detailed logging when enabled

The enhanced reinit process ensures reliable vLLM model management while maintaining compatibility with all existing podman manager features.
