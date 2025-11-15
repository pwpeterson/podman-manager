# VLLM_URL Update Mechanism

## Overview

During a `pm reinit vllm-model` command, the VLLM_URL environment variable needs to be updated to point to the new vLLM model container. This document explains how this process works and what files get changed.

## Current System Format

The system now uses **systemd user environment variable** format:

- **Container File**: `~/.config/containers/systemd/sys-services-vllm-proxy.container`
  - Contains: `Environment=VLLM_URL=${VLLM_URL}`
  - This references a systemd user environment variable rather than hardcoding the URL

- **User Environment**: Set via `systemctl --user set-environment`
  - Command: `systemctl --user set-environment VLLM_URL=http://vllm-model-name:8005`
  - Accessible to all user systemd services

**Note**: Only `sys-services-vllm-proxy` uses VLLM_URL. The `mcp-vllm-delegator` service does not use this environment variable.

## How VLLM_URL Gets Updated

### 1. During Reinit Process

When `pm reinit vllm-model-name` is executed:

1. **Detection**: The system detects the current format by checking the container file
2. **Update**: Since the container file uses `${VLLM_URL}`, the system updates the `.env` file
3. **Service Restart**: The container service is restarted to pick up the new environment variable

### 2. What Gets Changed

**Primary Change**: **Systemd user environment variable**
- **Command**: `systemctl --user set-environment VLLM_URL=http://new-model-name:8005`
- **Scope**: Available to all user systemd services
- **Persistence**: Remains set until explicitly unset or user session ends

**Container File**: `~/.config/containers/systemd/sys-services-vllm-proxy.container`
- **Remains unchanged** (uses `Environment=VLLM_URL=${VLLM_URL}`)

**Not Updated**: `~/.config/containers/systemd/mcp-vllm-delegator.container`
- **Reason**: This service does not use VLLM_URL environment variable

### 3. Implementation Details

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

## Environment Variable Precedence

The system works because of systemd environment variable precedence:

1. **User environment variables** (set via `systemctl --user set-environment`) - Available to all user services
2. **Environment** directives in container file - Can reference user environment variables
3. **${VARIABLE}** substitution - Resolved at container startup from user environment

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

## Cleanup Process

After reinit completes, the system optionally cleans up by removing the VLLM_URL from the systemd user environment:
```bash
systemctl --user unset-environment VLLM_URL
```

## Legacy Format Support

The system also supports the old format where the container file was modified directly:
- **Old format**: `Environment=VLLM_URL=REPLACED-DURING-REINIT` → `Environment=VLLM_URL=http://model:8005`
- **New format**: `Environment=VLLM_URL=${VLLM_URL}` + systemd user environment variable

## Testing

Use the provided test scripts to verify the mechanism:
- `test_enhanced_vllm_url_update.py` - Tests both formats and current system detection
- `test_container_file_update.py` - Tests current container state
- `test_simple_vllm_url_update.py` - Tests basic update logic

## Summary

**Question**: During a `pm reinit vllm-model`, how is the VLLM_URL updated? What file gets changed?

**Answer**:
- **Method**: `systemctl --user set-environment VLLM_URL=http://new-model-name:8005`
- **What changes**: Systemd user environment variable (not a file)
- **Why**: The `sys-services-vllm-proxy.container` file uses `${VLLM_URL}` substitution, so the actual value comes from the systemd user environment
- **When**: During the `restart_vllm_support_services()` phase of reinit, before the service is restarted
- **Scope**: Only affects `sys-services-vllm-proxy` service; `mcp-vllm-delegator` does not use VLLM_URL
