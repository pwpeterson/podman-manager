# VLLM_URL Update Fix

## Problem Description

During a vLLM model reinit, the `VLLM_URL` environment variable in the `sys-services-vllm-proxy` container was not being updated properly. The logs showed:

```
Nov 14 10:53:35 ubuntu-01 sys-services-vllm-proxy[415147]: Starting vLLM Proxy Server...
Nov 14 10:53:35 ubuntu-01 sys-services-vllm-proxy[415147]: vLLM Backend URL: http://localhost:8005
Nov 14 10:53:35 ubuntu-01 sys-services-vllm-proxy[415147]: vLLM API Key configured: No
```

The URL should have been updated to use the new vLLM model container name (e.g., `http://vllm-qwen25-coder-32b:8005`) instead of `localhost:8005`.

## Root Cause

The issue was in the [`restart_vllm_support_services`](managers/reinit/vllm_reinit_flow.py:298) method. The current flow was:

1. Stop `sys-services-vllm-proxy` service
2. Show message about updating VLLM_URL
3. Reload systemd daemon
4. Start the service again

**The problem**: The systemd service file (`.config/containers/systemd/sys-services-vllm-proxy.container`) was never removed and regenerated. When the service restarted, it used the old service file with the old `VLLM_URL=http://localhost:8005` environment variable.

## Solution

The fix adds proper service file removal to ensure the service is regenerated with the updated `VLLM_URL`:

### Changes Made

1. **Added service file removal for sys-services-vllm-proxy**:
   ```python
   # Remove service file to allow regeneration with updated VLLM_URL
   self.service_manager.remove_service_file("sys-services-vllm-proxy.service", dry_run=False)
   ```

2. **Added proper stop/remove/start flow for mcp-vllm-delegator**:
   ```python
   # Stop mcp-vllm-delegator using systemctl
   stop_result2 = self.service_manager.stop_service(
       "mcp-vllm-delegator.service", "mcp-vllm-delegator", quiet=False
   )

   # Remove mcp-vllm-delegator service file to allow regeneration
   self.service_manager.remove_service_file("mcp-vllm-delegator.service", dry_run=False)
   ```

### Updated Flow

The corrected flow now follows the same pattern as the standard reinit process:

1. **Stop** the service
2. **Remove** the service file (allows regeneration with new environment variables)
3. **Reload** systemd daemon
4. **Start** the service (generates new service file with updated VLLM_URL)

## Files Modified

- [`managers/reinit/vllm_reinit_flow.py`](managers/reinit/vllm_reinit_flow.py): Added service file removal in `restart_vllm_support_services` method

## Testing

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

## Verification Script

A verification script [`verify_vllm_url_fix.py`](verify_vllm_url_fix.py) has been created to check:
- Service file existence and content
- Container environment variables
- Recent container logs
- Fix implementation status

Run with:
```bash
python3 verify_vllm_url_fix.py
```

## Impact

This fix ensures that:
- The vLLM proxy correctly points to the new model container
- Network communication works properly between containers
- The reinit process fully updates all dependent services
- The system maintains consistency across service restarts

## Related Code

The fix follows the same pattern used in the standard reinit flow in [`_reinit_standard_service`](managers/reinit_manager.py:175), which properly removes service files before restarting services.
