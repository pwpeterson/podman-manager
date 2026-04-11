"""Prompt generation module for ai_analyzer (consolidated single-file).

This file contains all prompt generator implementations and the factory.

Historical note:
- This module was previously split into `ai_analyzer/prompts/generators.py` plus a thin
  re-exporting `__init__.py`. It has been merged into one file for simplicity.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict


class PromptGenerator(ABC):
    """Abstract base class for prompt generators"""

    @abstractmethod
    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate prompt for the given analysis type and data"""
        raise NotImplementedError

    def _create_base_context(
        self, analysis_type: str, target: str, data: Dict[str, Any]
    ) -> str:
        """Create base context for all prompts"""
        return f"""You are an expert system administrator and DevOps engineer.

Target: {target}
Analysis Type: {analysis_type}
Timestamp: {data.get('timestamp', 'Unknown')}
"""


class LogsPromptGenerator(PromptGenerator):
    """Generates prompts for log analysis"""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate comprehensive prompt for Podman Quadlet log analysis"""
        prompt_parts = [self._create_base_context("logs", target, data)]

        prompt_parts.append(
            """
Analyze the following Podman Quadlet service diagnostics and provide:

1. **Root Cause Analysis**: Identify the primary issues causing errors or warnings
2. **Recommended Solutions**: Specific, actionable steps to resolve the problems
3. **Quadlet-Specific Issues**: Check for common quadlet configuration problems
4. **System Resource Issues**: Identify any resource constraints or conflicts

IMPORTANT: This is a Podman Quadlet managed by systemd. Consider quadlet-specific issues like:
- Container image pull failures
- Volume/network configuration errors
- Port conflicts
- Resource constraints (disk space, memory)
- SELinux issues
- Systemd unit file problems
"""
        )

        # Add service information - use resolved service name for both Service and Target
        service_name = data.get("service_name", "Unknown")
        target_name = data.get("target", "Unknown")

        # If we have a resolved service name, use it as the target display name too
        display_target = service_name if service_name != "Unknown" else target_name

        prompt_parts.append(
            f"""
Service: {service_name}
Target: {display_target}
Log Lines Analyzed: {data.get('log_lines_count', 'Unknown')}
"""
        )

        # Add diagnostic data sections
        self._add_systemd_logs_section(prompt_parts, data)
        self._add_unit_status_section(prompt_parts, data)
        self._add_quadlet_section(prompt_parts, data)
        self._add_container_section(prompt_parts, data)
        self._add_system_resources_section(prompt_parts, data)
        self._add_network_section(prompt_parts, data)
        self._add_errors_section(prompt_parts, data)

        prompt_parts.append(
            """
Provide a structured analysis focusing on:
1. **Immediate Issues**: What's preventing the service from working right now?
2. **Root Causes**: Why are these issues occurring?
3. **Step-by-Step Fix**: Specific commands to resolve the problems
4. **Prevention**: How to avoid these issues in the future
5. **Monitoring**: What to watch for ongoing health

Use podman commands (not docker) in all recommendations. Consider quadlet-specific troubleshooting steps."""
        )

        return "\n".join(prompt_parts)

    def _add_systemd_logs_section(
        self, prompt_parts: list, data: Dict[str, Any]
    ) -> None:
        """Add systemd logs section to prompt"""
        # Use extended logs if available, otherwise fall back to regular logs
        logs_data = data.get("extended_systemd_logs") or data.get("systemd_logs")
        if logs_data:
            log_lines_count = data.get("extended_log_lines_count") or data.get(
                "log_lines_count", "Unknown"
            )
            prompt_parts.append(
                f"""
=== SYSTEMD SERVICE LOGS (Last {log_lines_count} lines) ===
{logs_data}
=== END SYSTEMD LOGS ===
"""
            )

    def _add_unit_status_section(
        self, prompt_parts: list, data: Dict[str, Any]
    ) -> None:
        """Add unit status section to prompt"""
        if data.get("unit_status"):
            prompt_parts.append(
                f"""
=== SYSTEMD UNIT STATUS ===
{data['unit_status']}
=== END UNIT STATUS ===
"""
            )

        if data.get("unit_properties"):
            prompt_parts.append(
                f"""
=== UNIT PROPERTIES (Failure Analysis) ===
{data['unit_properties']}
=== END UNIT PROPERTIES ===
"""
            )

        if data.get("unit_file_content"):
            prompt_parts.append(
                f"""
=== SYSTEMD UNIT FILE CONTENT ===
{data['unit_file_content']}
=== END UNIT FILE ===
"""
            )

    def _add_quadlet_section(self, prompt_parts: list, data: Dict[str, Any]) -> None:
        """Add Quadlet .container file section to prompt"""
        if (
            data.get("quadlet_container_file")
            and data["quadlet_container_file"] != "No .container file found"
        ):
            container_content = data["quadlet_container_file"]
            formatted_content = "\n".join(
                f"  {line}" if line.strip() else ""
                for line in container_content.split("\n")
            )
            prompt_parts.append(
                f"""
=== QUADLET .CONTAINER FILE ===
File: {data.get('quadlet_container_file_path', 'Unknown path')}
{formatted_content}
=== END .CONTAINER FILE ===
"""
            )
        elif data.get("quadlet_container_file") == "No .container file found":
            prompt_parts.append(
                f"""
=== QUADLET .CONTAINER FILE ===
No .container file found for {data.get('service_name', 'service')}
{data.get('available_container_files', 'No available files listed')}
=== END .CONTAINER FILE ===
"""
            )

    def _add_container_section(self, prompt_parts: list, data: Dict[str, Any]) -> None:
        """Add container information section to prompt"""
        if data.get("container_list"):
            prompt_parts.append(
                f"""
=== CONTAINER LIST ===
{data['container_list']}
=== END CONTAINER LIST ===
"""
            )

        if data.get("container_logs"):
            prompt_parts.append(
                f"""
=== CONTAINER LOGS (Last 2 hours) ===
{data['container_logs']}
=== END CONTAINER LOGS ===
"""
            )

        if data.get("container_inspect"):
            inspect_data = data["container_inspect"]
            if len(inspect_data) > 3000:
                inspect_data = inspect_data[:3000] + "\n... [truncated for brevity]"
            prompt_parts.append(
                f"""
=== CONTAINER INSPECTION (Key Details) ===
{inspect_data}
=== END CONTAINER INSPECTION ===
"""
            )

    def _add_system_resources_section(
        self, prompt_parts: list, data: Dict[str, Any]
    ) -> None:
        """Add system resources section to prompt"""
        if data.get("disk_space"):
            prompt_parts.append(
                f"""
=== DISK SPACE ===
{data['disk_space']}
=== END DISK SPACE ===
"""
            )

        if data.get("podman_disk_usage"):
            prompt_parts.append(
                f"""
=== PODMAN DISK USAGE ===
{data['podman_disk_usage']}
=== END PODMAN DISK USAGE ===
"""
            )

    def _add_network_section(self, prompt_parts: list, data: Dict[str, Any]) -> None:
        """Add network and port information section to prompt"""
        if data.get("port_usage"):
            prompt_parts.append(
                f"""
=== PORT USAGE (Potential Conflicts) ===
{data['port_usage']}
=== END PORT USAGE ===
"""
            )

        if data.get("podman_networks"):
            prompt_parts.append(
                f"""
=== PODMAN NETWORKS ===
{data['podman_networks']}
=== END NETWORKS ===
"""
            )

    def _add_errors_section(self, prompt_parts: list, data: Dict[str, Any]) -> None:
        """Add diagnostic errors section to prompt"""
        errors = []
        for key in [
            "systemd_error",
            "container_error",
            "system_resources_error",
            "network_storage_error",
            "quadlet_error",
        ]:
            if data.get(key):
                errors.append(f"{key}: {data[key]}")

        if errors:
            prompt_parts.append(
                f"""
=== DIAGNOSTIC COLLECTION ERRORS ===
{chr(10).join(errors)}
=== END ERRORS ===
"""
            )


class ReinitFailurePromptGenerator(PromptGenerator):
    """Generates prompts for reinit failure analysis"""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate comprehensive prompt for reinit failure analysis"""
        prompt_parts = [self._create_base_context("reinit_failure", target, data)]

        prompt_parts.append(
            """
Analyze the following Podman Quadlet service restart failure and provide:

1. **Root Cause Analysis**: Identify the primary issues causing the restart failure
2. **Recommended Solutions**: Specific, actionable steps to resolve the problems
3. **Quadlet-Specific Issues**: Check for common quadlet configuration problems
4. **System Resource Issues**: Identify any resource constraints or conflicts

IMPORTANT: This is a Podman Quadlet managed by systemd. Consider quadlet-specific issues like:
- Container image pull failures
- Volume/network configuration errors
- Port conflicts
- Resource constraints (disk space, memory)
- SELinux issues
- Systemd unit file problems

Provide a concise analysis with:
- **Immediate Issues**: What's preventing the service from restarting?
- **Root Causes**: Why are these issues occurring?
- **Step-by-Step Fix**: Specific commands to resolve the problems
"""
        )

        # Add service information - use resolved service name for both Service and Target
        service_name = data.get("service_name", "Unknown")
        target_name = data.get("target", "Unknown")
        display_target = service_name if service_name != "Unknown" else target_name

        prompt_parts.append(
            f"""
Service: {service_name}
Target: {display_target}
Operation: {data.get('operation', 'restart')}
Error: {data.get('restart_error', 'Service failed to restart')}
"""
        )

        # Add relevant data sections (reuse from LogsPromptGenerator)
        logs_generator = LogsPromptGenerator()
        logs_generator._add_systemd_logs_section(prompt_parts, data)
        logs_generator._add_unit_status_section(prompt_parts, data)

        if data.get("disk_space"):
            prompt_parts.append(
                f"""
=== DISK SPACE ===
{data['disk_space']}
=== END DISK SPACE ===
"""
            )

        if data.get("port_usage"):
            prompt_parts.append(
                f"""
=== PORT CONFLICTS ===
{data['port_usage']}
=== END PORT CONFLICTS ===
"""
            )

        if data.get("container_logs"):
            prompt_parts.append(
                f"""
=== CONTAINER LOGS (Recent) ===
{data['container_logs']}
=== END CONTAINER LOGS ===
"""
            )

        logs_generator._add_quadlet_section(prompt_parts, data)
        logs_generator._add_errors_section(prompt_parts, data)

        prompt_parts.append(
            """
Use podman commands (not docker) in all recommendations. Focus on the most critical issues first and provide specific, actionable solutions.
"""
        )

        return "\n".join(prompt_parts)


class StatusPromptGenerator(PromptGenerator):
    """Generates prompts for status analysis"""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate prompt for status analysis"""
        base_context = self._create_base_context("status", target, data)

        return f"""{base_context}
Analyze the following service status and provide insights:

Service: {data.get('service_name', 'Unknown')}

=== STATUS OUTPUT ===
{data.get('status_output', 'No status available')}
=== END STATUS ===

Provide:
1. **Current State**: What is the current state of the service?
2. **Health Assessment**: Is the service healthy or are there issues?
3. **Recommendations**: Any actions needed to improve service health?
4. **Monitoring**: What should be monitored going forward?"""


class BuildFailurePromptGenerator(PromptGenerator):
    """Generates prompts for build failure analysis"""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate focused prompt for container build failure analysis"""
        prompt_parts = []

        prompt_parts.append(
            """You are an expert DevOps engineer. Analyze this container build failure and provide a concise solution.

Focus on:
- Dockerfile syntax and structure issues
- Base image problems
- Package installation failures
- File operations and permissions
- Common container build patterns

Provide specific, actionable fixes using podman commands."""
        )

        # Add build error - most important part
        if data.get("build_error"):
            prompt_parts.append(
                f"""
=== BUILD ERROR ===
{data['build_error']}
=== END ERROR ==="""
            )

        # Add build output if meaningful
        if data.get("build_output"):
            build_output = str(data["build_output"]).strip()
            if build_output and len(build_output) > 10:
                if len(build_output) > 2000:
                    build_output = "...\n" + build_output[-2000:]

                prompt_parts.append(
                    f"""
=== BUILD OUTPUT ===
{build_output}
=== END OUTPUT ==="""
                )

        # Add Dockerfile content if available
        dockerfile_path = data.get("dockerfile_path")
        if dockerfile_path:
            dockerfile_content = self._read_dockerfile(str(dockerfile_path))
            if dockerfile_content:
                prompt_parts.append(
                    f"""
=== DOCKERFILE ===
{dockerfile_content}
=== END DOCKERFILE ==="""
                )

        prompt_parts.append(
            """
Provide:
1. **Root Cause**: What caused the build to fail?
2. **Fix**: Specific commands or Dockerfile changes needed
3. **Explanation**: Brief explanation of why this fixes the issue

Be concise and actionable. Use podman commands, not docker."""
        )

        return "\n\n".join(prompt_parts)

    def _read_dockerfile(self, dockerfile_path: str) -> str:
        """Read Dockerfile content safely"""
        try:
            from pathlib import Path

            dockerfile = Path(dockerfile_path)
            if dockerfile.exists():
                return dockerfile.read_text().strip()
        except Exception:
            return ""
        return ""


class PerformancePromptGenerator(PromptGenerator):
    """Generates prompts for performance analysis"""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate prompt for performance analysis"""
        base_context = self._create_base_context("performance", target, data)

        return f"""{base_context}
Analyze the following performance data and provide optimization recommendations:

=== PERFORMANCE DATA ===
{data.get('performance_data', 'No performance data available')}
=== END DATA ===

Provide:
1. **Performance Assessment**: Current performance status
2. **Bottlenecks**: Identify any performance bottlenecks
3. **Optimization**: Specific recommendations to improve performance
4. **Resource Usage**: Analysis of CPU, memory, and I/O usage"""


class SecurityPromptGenerator(PromptGenerator):
    """Generates prompts for security analysis"""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate prompt for security analysis"""
        base_context = self._create_base_context("security", target, data)

        return f"""{base_context}
Perform a security analysis of the service configuration and provide recommendations:

Provide:
1. **Security Assessment**: Current security posture
2. **Vulnerabilities**: Potential security issues or vulnerabilities
3. **Hardening**: Specific steps to improve security
4. **Best Practices**: Security best practices for this type of service
5. **Monitoring**: Security monitoring recommendations"""


class GenericPromptGenerator(PromptGenerator):
    """Generates generic prompts for unknown analysis types"""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate generic prompt for unknown analysis types"""
        base_context = self._create_base_context("generic", target, data)

        return f"""{base_context}
Provide analysis and recommendations for the following:

=== CONTEXT DATA ===
{str(data)}
=== END DATA ===

Provide relevant insights and actionable recommendations based on the available information."""


class ServiceStartFailurePromptGenerator(PromptGenerator):
    """Generates prompts for service start failure analysis"""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate comprehensive prompt for service start failure analysis"""
        prompt_parts = [
            self._create_base_context("service_start_failure", target, data)
        ]

        prompt_parts.append(
            """
Analyze the following systemd service start failure and provide:

1. **Root Cause Analysis**: Identify why the service failed to start
2. **Immediate Solutions**: Specific, actionable steps to resolve the issue
3. **Systemd-Specific Issues**: Check for common systemd service problems
4. **Container Issues**: Identify container-related problems (if applicable)

IMPORTANT: This is a systemd-managed service that failed to start. Consider:
- Service configuration errors
- Container image issues
- Port conflicts
- Resource constraints
- Permission problems
- Dependency failures

Provide a focused analysis with:
- **Primary Issue**: What prevented the service from starting?
- **Quick Fix**: Immediate commands to try
- **Verification**: How to confirm the fix worked
"""
        )

        service_name = data.get("service_name", "Unknown")
        target_name = data.get("target", "Unknown")
        display_target = service_name if service_name != "Unknown" else target_name

        prompt_parts.append(
            f"""
Service: {service_name}
Target: {display_target}
Start Command: {data.get('start_command', 'sudo systemctl start <service>')}
Error Code: {data.get('error_code', 'Unknown')}
"""
        )

        if data.get("systemd_error"):
            prompt_parts.append(
                f"""
=== SYSTEMD START ERROR ===
{data['systemd_error']}
=== END ERROR ===
"""
            )

        if data.get("service_status"):
            prompt_parts.append(
                f"""
=== SERVICE STATUS ===
{data['service_status']}
=== END STATUS ===
"""
            )

        if data.get("recent_logs"):
            prompt_parts.append(
                f"""
=== RECENT SERVICE LOGS ===
{data['recent_logs']}
=== END LOGS ===
"""
            )

        if data.get("container_info"):
            prompt_parts.append(
                f"""
=== CONTAINER INFORMATION ===
{data['container_info']}
=== END CONTAINER INFO ===
"""
            )

        if data.get("system_resources"):
            prompt_parts.append(
                f"""
=== SYSTEM RESOURCES ===
{data['system_resources']}
=== END RESOURCES ===
"""
            )

        prompt_parts.append(
            """
Provide specific, actionable solutions using systemctl and podman commands. Focus on the most likely causes first.
"""
        )

        return "\n".join(prompt_parts)


class FollowupPromptGenerator(PromptGenerator):
    """Generates prompts for follow-up questions"""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate focused prompt for follow-up questions"""
        analysis_type = data.get("analysis_type", "unknown")
        question = data.get("question", "")

        context_summary = ""
        if data.get("original_prompt") and data.get("original_analysis"):
            context_summary = f"""\n\n=== PREVIOUS ANALYSIS SUMMARY ===
Original Issue: {analysis_type} analysis for service '{target}'

Key Diagnostic Data:
- Service logs and status information were analyzed
- System resources, container details, and network configuration were examined
- Quadlet configuration and systemd unit details were reviewed

Previous AI Analysis Report:
{data['original_analysis']}
=== END PREVIOUS ANALYSIS ===\n\n"""

        return f"""You are an expert system administrator and DevOps engineer.

Context: You previously completed a comprehensive {analysis_type} analysis for service '{target}' with full diagnostic data collection.{context_summary}
Follow-up Question: {question}

Provide a focused, practical response to this specific question based on the previous analysis above. Keep your answer:
1. **Direct**: Address the question specifically
2. **Actionable**: Include specific commands or steps when relevant
3. **Concise**: Be brief but comprehensive
4. **Practical**: Focus on real-world solutions
5. **Contextual**: Reference relevant information from the previous analysis when helpful

Use podman commands (not docker) in all recommendations."""


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
        if not context:
            return "Commands timing out: podman inspect, podman ps, journalctl"
        return "\n".join([f"{key}: {value}" for key, value in context.items()])

    def _format_system_state(self, state: Dict[str, Any]) -> str:
        if not state:
            return "System state unknown due to command timeouts"
        return "\n".join([f"{key}: {value}" for key, value in state.items()])

    def _get_service_specific_timeout_guidance(self, target: str) -> str:
        guidance: list[str] = []

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
timeout 3s sudo systemctl is-active podman.socket || echo "Podman socket inactive"
```

### 3. Progressive Recovery Strategy
**Phase 1 - Service Level** (Risk: low)
```bash
# Reset specific service
sudo systemctl reset-failed {target}.service
sudo systemctl daemon-reload
```

**Phase 2 - Container Runtime** (Risk: medium)
```bash
# Reset container runtime
sudo systemctl restart podman.socket
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
        if not results:
            return "Health check data not available (system may be unresponsive)"

        formatted: list[str] = []
        for check, result in results.items():
            status = "PASS" if result.get("healthy", False) else "FAIL"
            details = result.get("details", "No details")
            formatted.append(f"{check}: {status} - {details}")

        return "\n".join(formatted)

    def _get_service_health_requirements(self, target: str) -> str:
        requirements: list[str] = []

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


class IntelligentRetryFixesPromptGenerator(PromptGenerator):
    """Generate prompts for intelligent retry with AI-guided fixes."""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        retry_attempt = data.get("retry_attempt", 1)
        max_retries = data.get("max_retries", 3)
        retry_history = data.get("retry_history", [])
        applied_fixes = data.get("applied_fixes", [])

        return f"""You are a system administration expert specializing in intelligent failure recovery and automated fixes.

A service reinit operation has failed and requires intelligent retry with AI-guided fixes:

Service: {target}
Timestamp: {timestamp}
Retry Attempt: {retry_attempt}/{max_retries}
Request: Provide specific, actionable fixes for this retry attempt

Retry History:
{self._format_retry_history(retry_history)}

Previously Applied Fixes:
{self._format_applied_fixes(applied_fixes)}

System Context:
{self._format_system_info(data)}

Please provide SPECIFIC, ACTIONABLE fixes for retry attempt {retry_attempt}:

**IMPORTANT**: Format your response with clear fix sections like this:

### Fix 1: [Title]
**Risk Level**: [low/medium/high]
**Description**: [What this fix does]
**Commands**:
```bash
command1
command2
```

### Fix 2: [Title]
**Risk Level**: [low/medium/high]
**Description**: [What this fix does]
**Commands**:
```bash
command1
command2
```

Guidelines for fixes:

1. **Retry Attempt {retry_attempt} Strategy**:
   {self._get_retry_strategy(retry_attempt)}

2. **Risk Levels**:
   - **low**: Safe operations (reset-failed, daemon-reload)
   - **medium**: Container operations (stop, remove, prune)
   - **high**: System-wide operations (system reset, force kills)

3. **Command Requirements**:
   - Use podman, not docker
   - Include error suppression with `|| true` for non-critical commands
   - Provide specific, executable commands
   - Consider systemd service management

4. **Service-Specific Considerations**:
   {self._get_service_specific_guidance(target)}

Focus on fixes that are most likely to resolve the specific failure pattern for this retry attempt."""

    def _format_retry_history(self, history: list) -> str:
        if not history:
            return "No previous retry attempts"

        formatted = []
        for entry in history:
            attempt = entry.get("attempt", "unknown")
            success = entry.get("success", False)
            fixes_applied = entry.get("fixes_applied", 0)
            exception = entry.get("exception")

            status = "SUCCESS" if success else "FAILED"
            line = f"Attempt {attempt}: {status} (fixes applied: {fixes_applied})"

            if exception:
                line += f" - Exception: {exception}"

            formatted.append(line)

        return "\n".join(formatted)

    def _format_applied_fixes(self, fixes: list) -> str:
        if not fixes:
            return "No fixes applied yet"

        formatted = []
        for fix_entry in fixes:
            attempt = fix_entry.get("attempt", "unknown")
            success = fix_entry.get("success", False)
            fix_info = fix_entry.get("fix", {})

            title = fix_info.get("title", "Unknown fix")
            status = "SUCCESS" if success else "FAILED"

            formatted.append(f"Attempt {attempt}: {title} - {status}")

        return "\n".join(formatted)

    def _get_retry_strategy(self, attempt: int) -> str:
        strategies = {
            1: "First retry - Use gentle, low-risk fixes. Focus on clearing failed states and reloading configurations.",
            2: "Second retry - Use medium-risk fixes. Clean up containers and resources that might be blocking the operation.",
            3: "Final retry - Use more aggressive fixes if necessary. Consider system-wide cleanup and force operations.",
        }
        return strategies.get(
            attempt, "Use appropriate fixes based on failure analysis."
        )

    def _get_service_specific_guidance(self, target: str) -> str:
        guidance = []

        if "vllm" in target.lower():
            guidance.extend(
                [
                    "- Check for processes using port 8005: `fuser -k 8005/tcp || true`",
                    "- Verify vLLM model containers are not conflicting",
                    "- Consider vLLM proxy restart if applicable",
                ]
            )

        if "postgres" in target.lower():
            guidance.extend(
                [
                    "- Check for database lock files",
                    "- Verify port 5432 availability",
                    "- Consider database recovery procedures",
                ]
            )

        if "redis" in target.lower():
            guidance.extend(
                [
                    "- Check Redis data directory permissions",
                    "- Verify port 6379 availability",
                    "- Consider Redis persistence file issues",
                ]
            )

        if not guidance:
            guidance = [
                "- Check service-specific ports and resources",
                "- Verify configuration file syntax",
                "- Consider service dependencies",
            ]

        return "\n   ".join(guidance)

    def _format_system_info(self, data: Dict[str, Any]) -> str:
        formatted = []

        if "system_resources" in data:
            resources = data["system_resources"]
            if isinstance(resources, dict):
                for key, value in resources.items():
                    formatted.append(f"{key}: {value}")

        if "recent_logs" in data:
            logs = data["recent_logs"]
            if logs:
                formatted.append(f"Recent Logs Preview: {str(logs)[:200]}...")

        return "\n".join(formatted) if formatted else "System information not available"


class PromptGeneratorFactory:
    """Factory for creating appropriate prompt generators"""

    _generators: dict[str, type[PromptGenerator]] = {
        "logs": LogsPromptGenerator,
        "reinit_failure": ReinitFailurePromptGenerator,
        "status": StatusPromptGenerator,
        "build_failure": BuildFailurePromptGenerator,
        "service_start_failure": ServiceStartFailurePromptGenerator,
        "performance": PerformancePromptGenerator,
        "security": SecurityPromptGenerator,
        "followup": FollowupPromptGenerator,
        "timeout_diagnostic": TimeoutDiagnosticPromptGenerator,
        "container_runtime_diagnostic": ContainerRuntimeDiagnosticPromptGenerator,
        "system_health_check": SystemHealthPromptGenerator,
        "intelligent_retry_fixes": IntelligentRetryFixesPromptGenerator,
    }

    @classmethod
    def create(cls, analysis_type: str) -> PromptGenerator:
        """Create appropriate prompt generator for analysis type."""
        generator_class = cls._generators.get(analysis_type, GenericPromptGenerator)
        return generator_class()


__all__ = [
    "PromptGenerator",
    "PromptGeneratorFactory",
    "LogsPromptGenerator",
    "ReinitFailurePromptGenerator",
    "StatusPromptGenerator",
    "BuildFailurePromptGenerator",
    "ServiceStartFailurePromptGenerator",
    "PerformancePromptGenerator",
    "SecurityPromptGenerator",
    "GenericPromptGenerator",
    "FollowupPromptGenerator",
    "TimeoutDiagnosticPromptGenerator",
    "ContainerRuntimeDiagnosticPromptGenerator",
    "SystemHealthPromptGenerator",
    "IntelligentRetryFixesPromptGenerator",
]
