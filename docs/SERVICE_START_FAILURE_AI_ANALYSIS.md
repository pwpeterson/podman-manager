# Service Start Failure AI Analysis Integration

## Overview

This document describes the AI analysis integration added for service start failures in the Podman Manager system. When a systemd service fails to start (like the `taskflow-backend.service` error in the original task), the system now automatically triggers AI analysis to help diagnose and resolve the issue.

## Implementation Details

### 1. New Prompt Generator

**File**: [`ai_analyzer/prompt_generators.py`](../ai_analyzer/prompt_generators.py)

- Added `ServiceStartFailurePromptGenerator` class
- Generates comprehensive prompts for analyzing systemd service start failures
- Focuses on common issues like:
  - Service configuration errors
  - Container image problems
  - Port conflicts
  - Resource constraints
  - Permission issues
  - Dependency failures

### 2. QuadletManager Integration

**File**: [`managers/quadlet_manager.py`](../managers/quadlet_manager.py)

#### Modified `start_service` method:
- When `systemctl --user start <service>` fails, automatically triggers AI analysis
- Captures error code and stderr output for analysis

#### Added `_trigger_service_start_ai_analysis` method:
- Collects comprehensive diagnostic information:
  - Service status details
  - Recent service logs (last 20 lines)
  - Container information (if applicable)
  - System resource usage (disk space, memory)
  - Systemd error messages
- Calls AI analyzer with `service_start_failure` analysis type
- Fails silently to avoid breaking service management if AI analysis has issues

### 3. AI Analyzer Updates

**File**: [`ai_analyzer/analyzer.py`](../ai_analyzer/analyzer.py)

- Added support for `service_start_failure` analysis type
- Uses provided context data without additional collection (since QuadletManager already collects comprehensive diagnostics)

### 4. Container Builder Integration

**File**: [`operations/container_builder.py`](../operations/container_builder.py)

- Enhanced error messaging in `rebuild_service` method
- Service start failures after successful builds will also trigger AI analysis (via QuadletManager)

## Usage Example

When a service fails to start:

```bash
pm build taskflow-backend -v
```

If the service fails to start, you'll see:

1. **Standard Error Message**:
   ```
   Failed to start taskflow-backend.service
   ```

2. **Automatic AI Analysis**:
   - Collects service logs, status, container info, and system resources
   - Analyzes the failure with AI
   - Provides:
     - Root cause analysis
     - Immediate solutions
     - Specific commands to try
     - Verification steps

## Error Scenario Addressed

The original task described this error:
```
Starting taskflow-backend.service
exec: systemctl --user start taskflow-backend.service
13:21:47 | ERROR | Command failed with code 1 in 3.80s
Failed to start taskflow-backend.service
13:21:47 | ERROR | Error output: Job for taskflow-backend.service failed because the control process exited with error code.
See "systemctl --user status taskflow-backend.service" and "journalctl --user -xeu taskflow-backend.service" for details.

Failed to start taskflow-backend after build
```

Now when this happens, the system will:
1. Show the same error messages
2. **Automatically run AI analysis** to diagnose the issue
3. Provide actionable recommendations without requiring manual log analysis

## Benefits

1. **Immediate Diagnosis**: No need to manually run `systemctl status` or `journalctl` commands
2. **Comprehensive Analysis**: Collects multiple data sources automatically
3. **Actionable Solutions**: AI provides specific commands and steps to resolve issues
4. **Non-Intrusive**: Fails silently if AI analysis has problems, doesn't break service management
5. **Consistent Experience**: Same AI analysis system used across all PM operations

## Testing

A test script is provided: [`test_service_start_analysis.py`](../test_service_start_analysis.py)

Run with:
```bash
python test_service_start_analysis.py
```

## Technical Notes

- AI analysis is triggered only on service start failures (return code != 0)
- Uses the default AI agent (can be configured via AI system)
- Respects verbose mode settings
- Collects diagnostics with timeouts to prevent hanging
- All diagnostic collection errors are handled gracefully
