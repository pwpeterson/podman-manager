# vLLM System Documentation

## Overview

This document consolidates all vLLM-related functionality in the Podman Manager, including model switching, enhanced reinit processes, URL management, and container operations.

## vLLM Model Switching Integration

### Enhanced Features

#### Automatic vLLM Service Detection
- Automatically detects vLLM services by name patterns (`vllm` in service name)
- Applies enhanced handling for all vLLM operations (start, restart, reinit)
- No manual configuration required

#### Progress Indicators
- **Stopping Phase**: Spinner shows graceful shutdown progress (up to 1 minute)
- **Starting Phase**: Spinner shows startup progress with health monitoring (up to 5 minutes)
- **Real-time Updates**: Progress messages show elapsed time

#### Robust Shutdown Process
1. **Graceful Stop**: Attempts `podman stop -t 30` for clean shutdown
2. **Port Monitoring**: Waits for port 8005 to be released
3. **Force Cleanup**: If needed, force kills processes using the port
4. **Verification**: Confirms port is fully available before proceeding

#### Smart Startup Monitoring
1. **Health Endpoint**: Tests `/health` endpoint for service readiness
2. **Container Status**: Monitors container state and port usage
3. **Timeout Handling**: 5-minute timeout with graceful degradation
4. **Fallback Logic**: Multiple methods to verify service readiness

### New Components

#### VLLMModelManager (`managers/vllm_model_manager.py`)

Enhanced manager class that handles:
- Graceful container shutdown with progress indicators
- Smart startup monitoring with health checks
- Port cleanup and process management
- Status monitoring and reporting
- Automatic vLLM service detection

#### Integration Points

1. **ReinitManager** - Enhanced to support vLLM model switching during reinit operations
2. **ServiceLifecycle** - Enhanced to support vLLM model switching during restart operations
3. **QuadletOperations** - Updated method signatures to pass through vLLM model parameters
4. **CommandRouter** - New command handlers for vLLM management
5. **CLI Parser** - New commands and parameters for vLLM operations

### New Commands

#### vLLM Management Commands

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

#### Enhanced Existing Commands

```bash
# Reinit with vLLM model switching
pm reinit vllm-proxy --vllm-model vllm-qwen25-coder-32b
pm reinit vllm-stack --vllm-model vllm-glm46

# Restart with vLLM model switching
pm restart vllm-proxy --vllm-model vllm-qwen25-coder-32b
pm restart vllm-stack --vllm-model vllm-glm46
```

## Enhanced vLLM Reinit Process

### Overview

When reinitializing a vLLM model container (e.g., `pm reinit 9b-chat`), the system now:

1. **Detects** the currently active vLLM model using port 8005
2. **Stops** the current vLLM container gracefully (always, to free port 8005)
3. **Removes** the systemd service file for the stopped container
4. **Proceeds** with the standard reinit process for the target container

### Expected Output Format

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

### Implementation Details

#### vLLM Container Detection and Logic

The system uses multiple methods to detect the currently active vLLM container:

1. **Container Inspection**: Checks all running vLLM containers and their network settings
2. **Port Mapping**: Examines container port mappings to find which container is using port 8005
3. **Process Enumeration**: Uses system process information to identify the container using port 8005

**Important Logic**: The system **always** stops and removes the **currently running** vLLM container to ensure port 8005 is available for the target container. This prevents port conflicts and ensures clean transitions between vLLM models.

#### Enhanced Reinit Manager

The `ReinitManager` class has been enhanced with:

- **vLLM Detection**: Automatically detects vLLM model services during reinit
- **Graceful Stopping**: Properly stops the current vLLM container with a 60-second timeout
- **Visual Feedback**: Uses animated spinners to show progress during stopping operations
- **Service File Cleanup**: Removes both the old and current vLLM service files
- **Verbose Logging**: Provides detailed output in verbose mode

## vLLM URL Management

### VLLM_URL Update Mechanism

During a `pm reinit vllm-model` command, the VLLM_URL environment variable needs to be updated to point to the new vLLM model container.

#### Current System Format

The system uses **systemd user environment variable** format:

- **Container File**: `~/.config/containers/systemd/sys-services-vllm-proxy.container`
  - Contains: `Environment=VLLM_URL=${VLLM_URL}`
  - This references a systemd user environment variable rather than hardcoding the URL

- **User Environment**: Set via `systemctl --user set-environment`
  - Command: `systemctl --user set-environment VLLM_URL=http://vllm-model-name:8005`
  - Accessible to all user systemd services

**Note**: Only `sys-services-vllm-proxy` uses VLLM_URL. The `mcp-vllm-delegator` service does not use this environment variable.

#### How VLLM_URL Gets Updated

**During Reinit Process**:

When `pm reinit vllm-model-name` is executed:

1. **Detection**: The system detects the current format by checking the container file
2. **Update**: Since the container file uses `${VLLM_URL}`, the system updates the systemd user environment
3. **Service Restart**: The container service is restarted to pick up the new environment variable

**What Gets Changed**:

**Primary Change**: **Systemd user environment variable**
- **Command**: `systemctl --user set-environment VLLM_URL=http://new-model-name:8005`
- **Scope**: Available to all user systemd services
- **Persistence**: Remains set until explicitly unset or user session ends

**Container File**: `~/.config/containers/systemd/sys-services-vllm-proxy.container`
- **Remains unchanged** (uses `Environment=VLLM_URL=${VLLM_URL}`)

#### Implementation Details

The update logic is implemented in `managers/reinit/vllm_reinit_flow.py`:

```python
def _update_container_file_vllm_url(self, container_name: str, vllm_url: str) -> bool:
    # Detects format and routes to appropriate update method
    if 'Environment=VLLM_URL=${VLLM_URL}' in content:
        # New format: Set systemd user environment variable
        return self._update_env_file_vllm_url(env_file_path, vllm_url)
    elif 'Environment=VLLM_URL=REPLACED-DURING-REINIT' in content:
        # Old format: Update container file directly
        # (legacy support)

def _update_env_file_vllm_url(self, env_file_path, vllm_url: str) -> bool:
    # Uses systemctl --user set-environment
    cmd = ["systemctl", "--user", "set-environment", f"VLLM_URL={vllm_url}"]
```

#### Environment Variable Precedence

The system works because of systemd environment variable precedence:

1. **User environment variables** (set via `systemctl --user set-environment`) - Available to all user services
2. **Environment** directives in container file - Can reference user environment variables
3. **${VARIABLE}** substitution - Resolved at container startup from user environment

### VLLM_URL Fix Implementation

#### Problem Description

During `pm reinit vllm-model` operations, the VLLM_URL environment variable was not being properly updated in the sys-services-vllm-proxy container. The container was showing `VLLM_URL=REPLACED-DURING-REINIT` instead of the correct URL pointing to the new vLLM model container.

#### Root Cause Analysis

**The Issue**:
1. **Container File**: The [`sys-services-vllm-proxy.container`](/home/pwp/.config/containers/systemd/sys-services-vllm-proxy.container) file contains:
   ```
   Environment=VLLM_URL=REPLACED-DURING-REINIT
   ```

2. **Reinit Process**: The reinit flow in [`managers/reinit/vllm_reinit_flow.py`](managers/reinit/vllm_reinit_flow.py) was:
   - Calculating the correct VLLM_URL: `vllm_url = f"http://{display_name}:8005"`
   - Showing update message: `console.print(f"[cyan]Updating VLLM_URL to: {vllm_url}[/cyan]")`
   - Removing service file: `self.service_manager.remove_service_file("sys-services-vllm-proxy.service")`
   - Restarting service: `self.service_manager.start_service("sys-services-vllm-proxy.service")`

3. **The Problem**: When the service restarted, it regenerated from the same container file with the hardcoded placeholder value `REPLACED-DURING-REINIT`.

#### Solution Implementation

**Approach: systemd Environment Variable Override**

Instead of modifying the container file directly, we use systemd's built-in environment management to set the `VLLM_URL` environment variable before calling `systemctl restart`. This overrides the container file value during service generation.

**Code Changes**:

**File: `managers/reinit/vllm_reinit_flow.py`**

**Change 1: sys-services-vllm-proxy restart**
```python
# Set VLLM_URL in systemd user environment to override the container file value
import subprocess
set_env_cmd = ["systemctl", "--user", "set-environment", f"VLLM_URL={vllm_url}"]
verbose_print(f"[cyan]exec: {' '.join(set_env_cmd)}[/cyan]")
subprocess.run(set_env_cmd, capture_output=True, text=True)

try:
    start_result = self.service_manager.start_service(
        "sys-services-vllm-proxy.service", "sys-services-vllm-proxy", quiet=False
    )
finally:
    # Clean up systemd environment variable
    unset_env_cmd = ["systemctl", "--user", "unset-environment", "VLLM_URL"]
    verbose_print(f"[cyan]exec: {' '.join(unset_env_cmd)}[/cyan]")
    subprocess.run(unset_env_cmd, capture_output=True, text=True)
```

**Change 2: mcp-vllm-delegator restart**
```python
# Same pattern applied to mcp-vllm-delegator restart
import subprocess
set_env_cmd = ["systemctl", "--user", "set-environment", f"VLLM_URL={vllm_url}"]
verbose_print(f"[cyan]exec: {' '.join(set_env_cmd)}[/cyan]")
subprocess.run(set_env_cmd, capture_output=True, text=True)

try:
    start_result = self.service_manager.start_service(
        "mcp-vllm-delegator.service", "mcp-vllm-delegator", quiet=False
    )
finally:
    # Clean up systemd environment variable
    unset_env_cmd = ["systemctl", "--user", "unset-environment", "VLLM_URL"]
    verbose_print(f"[cyan]exec: {' '.join(unset_env_cmd)}[/cyan]")
    subprocess.run(unset_env_cmd, capture_output=True, text=True)
```

#### How the Fix Works

1. **Calculate VLLM_URL**: `vllm_url = f"http://{display_name}:8005"`
2. **Set systemd Environment**: `systemctl --user set-environment VLLM_URL={vllm_url}`
3. **Start Service**: `systemctl --user restart service_name`
4. **Service Generation**: Quadlet/systemd uses the environment variable to override the container file value
5. **Clean up Environment**: `systemctl --user unset-environment VLLM_URL`

#### Environment Variable Flow

```
Python Process
    ↓
subprocess.run(["systemctl", "--user", "set-environment", "VLLM_URL={vllm_url}"])
    ↓
systemd user environment now contains VLLM_URL
    ↓
ServiceManager.start_service()
    ↓
subprocess.run(["systemctl", "--user", "restart", service_name])
    ↓
systemctl reads VLLM_URL from systemd user environment
    ↓
Quadlet service generation uses VLLM_URL from systemd environment
    ↓
Container starts with correct VLLM_URL
    ↓
subprocess.run(["systemctl", "--user", "unset-environment", "VLLM_URL"])
```

## vLLM Model Switching Process

### How It Works

#### vLLM Model Switching Process

1. **Graceful Shutdown**: Attempts to gracefully stop the current vLLM container (30s timeout)
2. **Port Cleanup**: Waits for port 8005 to be released, with spinner progress indication
3. **Force Cleanup**: If needed, force kills processes using port 8005 (vLLM port)
4. **Backend Start**: Starts the new vLLM model container with startup monitoring
5. **Readiness Check**: Waits up to 5 minutes for the vLLM service to be ready (health endpoint)
6. **Proxy Restart**: Stops and removes the old proxy, starts new proxy with updated `VLLM_URL`

#### Enhanced vLLM Service Handling

When working with vLLM services (detected automatically), the system now:
- **Automatic Detection**: Recognizes vLLM services by name patterns
- **Proper Shutdown**: Ensures current vLLM models are fully stopped before starting new ones
- **Progress Indicators**: Shows spinners during stopping (up to 1 minute) and starting (up to 5 minutes)
- **Health Monitoring**: Tests the `/health` endpoint to confirm service readiness
- **Graceful Fallbacks**: Uses container status and port checks if health endpoint unavailable

#### Configuration

The VLLMModelManager uses these default settings:
- **vLLM Port**: 8005
- **Proxy Container**: `vllm-proxy`
- **Proxy Port**: 8002
- **Network**: `local-ai-network`
- **Proxy Image**: `vllm-proxy:latest` (configurable)
- **Shutdown Timeout**: 30 seconds graceful, 60 seconds total
- **Startup Timeout**: 300 seconds (5 minutes)

#### Integration with Existing Operations

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

## Verification

To verify the VLLM_URL is correctly set:

```bash
# Check container environment
podman exec -it sys-services-vllm-proxy printenv VLLM_URL

# Check systemd user environment
systemctl --user show-environment | grep VLLM_URL

# Check container file format
grep VLLM_URL ~/.config/containers/systemd/sys-services-vllm-proxy.container
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

### VLLM_URL Update Issues

To verify the fix works:

1. **Run a vLLM model reinit**:
   ```bash
   python podman_manager.py reinit <vllm-model-name>
   ```

2. **Check the proxy logs**:
   ```bash
   podman logs sys-services-vllm-proxy
   ```

3. **Verify the VLLM_URL**:
   The logs should now show:
   ```
   vLLM Backend URL: http://<vllm-model-container-name>:8005
   ```
   Instead of:
   ```
   vLLM Backend URL: http://localhost:8005
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

## Benefits

1. **Clean Transitions**: Properly stops old vLLM models before starting new ones
2. **Port Conflict Prevention**: Ensures port 8005 is available for the new model
3. **Service File Hygiene**: Removes obsolete systemd service files
4. **Reliable Detection**: Uses multiple methods to find the active vLLM container
5. **Visual Feedback**: Animated spinners show progress during long operations
6. **Professional UX**: Consistent with other podman manager operations
7. **Verbose Feedback**: Provides clear status messages during the process
8. **Proper URL Management**: Ensures proxy services connect to correct backends
9. **Environment Variable Handling**: Clean systemd environment management
10. **Legacy Support**: Maintains compatibility with older configuration formats

## Integration with Existing Features

This enhancement integrates seamlessly with:

- **vLLM Model Switching**: Works with `pm vllm-switch` commands
- **Stack Management**: Handles vLLM stacks properly
- **AI Diagnostics**: Triggers AI analysis on failures
- **Build Systems**: Compatible with quadlet and podman builds
- **Verbose Mode**: Provides detailed logging when enabled
- **Enhanced Reinit**: Full integration with intelligent troubleshooting
- **Service Lifecycle**: Proper integration with start/stop/restart operations

The vLLM system ensures reliable model management while maintaining compatibility with all existing podman manager features.
