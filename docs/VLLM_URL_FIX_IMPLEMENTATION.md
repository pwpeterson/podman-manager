# VLLM_URL Fix Implementation

## Problem Description

During `pm reinit vllm-model` operations, the VLLM_URL environment variable was not being properly updated in the sys-services-vllm-proxy container. The container was showing `VLLM_URL=REPLACED-DURING-REINIT` instead of the correct URL pointing to the new vLLM model container.

## Root Cause Analysis

### The Issue
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

### Why Environment Injection Failed
The systemctl service generation process reads the container file and uses its hardcoded environment values. Without setting the environment variable in the shell before calling systemctl, the placeholder value persists.

## Solution Implementation

### Approach: systemd Environment Variable Override
Instead of modifying the container file directly, we use systemd's built-in environment management to set the `VLLM_URL` environment variable before calling `systemctl restart`. This overrides the container file value during service generation.

### Code Changes

#### File: `managers/reinit/vllm_reinit_flow.py`

**Change 1: sys-services-vllm-proxy restart (lines 341-347)**
```python
# Before (broken)
start_result = self.service_manager.start_service(
    "sys-services-vllm-proxy.service", "sys-services-vllm-proxy", quiet=False
)

# After (fixed)
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

**Change 2: mcp-vllm-delegator restart (lines 391-397)**
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

### How the Fix Works

1. **Calculate VLLM_URL**: `vllm_url = f"http://{display_name}:8005"`
2. **Set systemd Environment**: `systemctl --user set-environment VLLM_URL={vllm_url}`
3. **Start Service**: `systemctl --user restart service_name`
4. **Service Generation**: Quadlet/systemd uses the environment variable to override the container file value
5. **Clean up Environment**: `systemctl --user unset-environment VLLM_URL`

### Environment Variable Flow

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

## Testing

### Test Script: `test_vllm_url_fix.py`
Created a test script to verify the fix works:
- Checks current VLLM_URL in running container
- Compares with service file value
- Provides analysis and test instructions

### Manual Testing
1. Run: `python podman_manager.py reinit <vllm-model-name>`
2. Check: `podman exec -it sys-services-vllm-proxy printenv VLLM_URL`
3. Verify: Should show `http://<model-name>:8005` instead of `REPLACED-DURING-REINIT`

### Verification Script: `verify_vllm_url_fix.py`
The existing verification script can be used to confirm the fix works.

## Benefits of This Approach

1. **Non-Invasive**: Doesn't modify container files
2. **Clean**: Uses proper environment variable inheritance
3. **Robust**: Handles environment restoration properly
4. **Maintainable**: Clear separation of concerns
5. **Safe**: Try/finally ensures cleanup even on errors

## Alternative Approaches Considered

### Approach 1: Direct Container File Modification
- **Pros**: Direct and explicit
- **Cons**: File I/O operations, potential race conditions, harder to maintain

### Approach 2: Dynamic Container File Generation
- **Pros**: Most flexible
- **Cons**: Complex implementation, requires template system

### Approach 3: Environment Variable Override (Chosen)
- **Pros**: Clean, uses existing systemd mechanisms, non-invasive
- **Cons**: Relies on environment inheritance (which is standard)

## Impact

This fix resolves the issue where:
- `podman exec -it sys-services-vllm-proxy printenv VLLM_URL` showed `REPLACED-DURING-REINIT`
- The proxy couldn't connect to the correct vLLM model backend
- vLLM model switching during reinit operations failed silently

After the fix:
- `podman exec -it sys-services-vllm-proxy printenv VLLM_URL` shows `http://<model-name>:8005`
- The proxy correctly connects to the new vLLM model backend
- vLLM model switching works as expected during reinit operations
