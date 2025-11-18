"""Enhanced prompt generators for handling timeout scenarios and container runtime issues."""

from datetime import datetime
from typing import Any, Dict

from .prompt_generators import PromptGenerator


class TimeoutDiagnosticPromptGenerator(PromptGenerator):
    """Generate prompts for diagnosing timeout and container runtime issues."""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        timeout_context = data.get("timeout_context", {})
        system_state = data.get("system_state", {})
        error_details = data.get("start_error", "")

        return f"""You are a container runtime and systemd expert specializing in timeout and startup failure diagnosis.

A service reinit operation has failed with timeout issues:

Service: {target}
Timestamp: {timestamp}
Failure Type: Container startup timeout/error

Timeout Context:
{self._format_timeout_context(timeout_context)}

System State:
{self._format_system_state(system_state)}

Error Details:
{error_details or "Container status: error (commands timing out)"}

Diagnostic Analysis Required:

**CRITICAL ISSUE**: System commands (podman, journalctl) are timing out, indicating:
1. Container runtime (podman) may be hung or unresponsive
2. Systemd may be experiencing issues
3. System resources may be exhausted
4. Storage/filesystem issues may be present

**Please provide a comprehensive diagnostic analysis with:**

### 1. Root Cause Analysis
- Most likely causes of command timeouts
- Container runtime state assessment
- System resource implications

### 2. Immediate Diagnostic Steps
**Risk Level**: [low/medium/high]
**Commands to run**:
```bash
# Safe diagnostic commands that won't hang
command1
command2
```

### 3. Progressive Recovery Steps
**Step 1 - Gentle Recovery** (Risk: low)
```bash
# Commands for gentle recovery
```

**Step 2 - Container Runtime Reset** (Risk: medium)
```bash
# Commands for container runtime reset
```

**Step 3 - System Recovery** (Risk: high)
```bash
# Commands for system-level recovery if needed
```

### 4. Prevention Measures
- Steps to prevent future timeout issues
- Monitoring recommendations
- System health checks

**Service-Specific Context for {target}:**
{self._get_service_specific_timeout_guidance(target)}

**IMPORTANT**: Focus on timeout-resistant diagnostic commands and progressive recovery approach."""

    def _format_timeout_context(self, context: Dict[str, Any]) -> str:
        """Format timeout context information."""
        if not context:
            return "Commands timing out: podman inspect, podman ps, journalctl"

        formatted = []
        for key, value in context.items():
            formatted.append(f"{key}: {value}")

        return "\n".join(formatted)

    def _format_system_state(self, state: Dict[str, Any]) -> str:
        """Format system state information."""
        if not state:
            return "System state unknown due to command timeouts"

        formatted = []
        for key, value in state.items():
            formatted.append(f"{key}: {value}")

        return "\n".join(formatted)

    def _get_service_specific_timeout_guidance(self, target: str) -> str:
        """Get service-specific guidance for timeout scenarios."""
        guidance = []

        if "llama" in target.lower() or "vllm" in target.lower():
            guidance.extend(
                [
                    "- Large language models require significant memory and startup time",
                    "- Model loading can take several minutes and may appear hung",
                    "- Port 8005 conflicts with other models can cause startup issues",
                    "- Check for memory exhaustion during model loading",
                    "- Consider model file corruption or missing dependencies",
                ]
            )

        if "postgres" in target.lower():
            guidance.extend(
                [
                    "- Database recovery can cause extended startup times",
                    "- Check for corrupted database files or locks",
                    "- Verify sufficient disk space for database operations",
                ]
            )

        if not guidance:
            guidance = [
                "- Check for resource exhaustion (memory, disk, CPU)",
                "- Verify container image availability and integrity",
                "- Consider network connectivity issues",
            ]

        return "\n".join([f"  {item}" for item in guidance])


class ContainerRuntimeDiagnosticPromptGenerator(PromptGenerator):
    """Generate prompts for container runtime diagnostic issues."""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""You are a Podman and container runtime expert specializing in runtime failures and recovery.

Container Runtime Diagnostic Request:

Service: {target}
Timestamp: {timestamp}
Issue: Container runtime commands hanging/timing out

Symptoms Observed:
- podman inspect commands timeout
- podman ps commands timeout
- journalctl commands timeout
- Container status shows "error"
- System appears to have container runtime issues

**Diagnostic Analysis Required:**

### 1. Container Runtime Health Assessment
**Provide commands to check:**
- Podman daemon status
- Container runtime processes
- Storage driver health
- Network namespace issues

### 2. Safe Diagnostic Commands
**Commands that won't hang:**
```bash
# Use timeout prefixes and non-blocking operations
timeout 5s podman version || echo "Podman unresponsive"
timeout 3s systemctl --user is-active podman.socket || echo "Podman socket inactive"
```

### 3. Progressive Recovery Strategy
**Phase 1 - Service Level** (Risk: low)
```bash
# Reset specific service
systemctl --user reset-failed {target}.service
systemctl --user daemon-reload
```

**Phase 2 - Container Runtime** (Risk: medium)
```bash
# Reset container runtime
systemctl --user restart podman.socket
podman system reset --force
```

**Phase 3 - System Level** (Risk: high)
```bash
# System-wide container cleanup
# Only if other methods fail
```

### 4. Root Cause Investigation
**Check for:**
- Storage driver issues (overlay2, etc.)
- Network namespace corruption
- Resource exhaustion
- Filesystem issues
- Systemd service conflicts

### 5. Prevention and Monitoring
**Recommendations for:**
- Container runtime health monitoring
- Resource limit configuration
- Cleanup automation
- Early warning systems

**Focus on timeout-resistant diagnostics and progressive recovery for {target}.**"""


class SystemHealthPromptGenerator(PromptGenerator):
    """Generate prompts for system health checks before operations."""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        health_data = data.get("health_check_results", {})

        return f"""You are a system health expert specializing in pre-operation health validation.

System Health Assessment Request:

Target Operation: Reinit {target}
Timestamp: {timestamp}
Purpose: Validate system health before attempting service operations

Health Check Results:
{self._format_health_results(health_data)}

**Analysis Required:**

### 1. System Readiness Assessment
**Evaluate:**
- Container runtime health
- Systemd service manager status
- Resource availability
- Storage system health
- Network connectivity

### 2. Pre-Operation Validation
**Check if system is ready for:**
- Service stop/start operations
- Container management
- Systemd daemon operations
- Resource allocation

### 3. Risk Assessment
**Identify potential issues:**
- Resource constraints that could cause failures
- Runtime conflicts
- System instability indicators
- Service dependency problems

### 4. Go/No-Go Recommendation
**Provide clear recommendation:**
- PROCEED: System is healthy for operation
- CAUTION: System has issues but operation may succeed
- ABORT: System issues likely to cause operation failure

### 5. Remediation Steps
**If issues found, provide:**
- Immediate fixes for critical issues
- System stabilization steps
- Resource cleanup procedures

**Service-Specific Health Considerations for {target}:**
{self._get_service_health_requirements(target)}

**Provide actionable health assessment with clear go/no-go decision.**"""

    def _format_health_results(self, results: Dict[str, Any]) -> str:
        """Format health check results."""
        if not results:
            return "Health check data not available (system may be unresponsive)"

        formatted = []
        for check, result in results.items():
            status = "PASS" if result.get("healthy", False) else "FAIL"
            details = result.get("details", "No details")
            formatted.append(f"{check}: {status} - {details}")

        return "\n".join(formatted)

    def _get_service_health_requirements(self, target: str) -> str:
        """Get service-specific health requirements."""
        requirements = []

        if "llama" in target.lower() or "vllm" in target.lower():
            requirements.extend(
                [
                    "- Minimum 8GB available memory for model loading",
                    "- Port 8005 must be available",
                    "- No conflicting model services running",
                    "- Sufficient disk space for model files",
                    "- Container runtime must be responsive",
                ]
            )

        if "postgres" in target.lower():
            requirements.extend(
                [
                    "- Port 5432 availability",
                    "- Sufficient disk space for database",
                    "- No database lock files present",
                    "- Memory available for database operations",
                ]
            )

        if not requirements:
            requirements = [
                "- Container runtime operational",
                "- Systemd service manager responsive",
                "- Adequate system resources",
                "- No conflicting services",
            ]

        return "\n".join([f"  {req}" for req in requirements])
