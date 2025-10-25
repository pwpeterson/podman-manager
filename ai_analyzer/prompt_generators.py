"""Prompt generation classes for AI analysis system"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class PromptGenerator(ABC):
    """Abstract base class for prompt generators"""

    @abstractmethod
    def generate(self, target: str, data: Dict[str, Any]) -> str:
        """Generate prompt for the given analysis type and data"""
        pass

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

        # If we have a resolved service name, use it as the target display name too
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
            build_output = data["build_output"].strip()
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
            dockerfile_content = self._read_dockerfile(dockerfile_path)
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
                with open(dockerfile, "r") as f:
                    return f.read().strip()
        except Exception:
            pass
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

        # Add service information - use resolved service name for both Service and Target
        service_name = data.get("service_name", "Unknown")
        target_name = data.get("target", "Unknown")

        # If we have a resolved service name, use it as the target display name too
        display_target = service_name if service_name != "Unknown" else target_name

        prompt_parts.append(
            f"""
Service: {service_name}
Target: {display_target}
Start Command: {data.get('start_command', 'systemctl --user start <service>')}
Error Code: {data.get('error_code', 'Unknown')}
"""
        )

        # Add systemd error output if available
        if data.get("systemd_error"):
            prompt_parts.append(
                f"""
=== SYSTEMD START ERROR ===
{data['systemd_error']}
=== END ERROR ===
"""
            )

        # Add service status information
        if data.get("service_status"):
            prompt_parts.append(
                f"""
=== SERVICE STATUS ===
{data['service_status']}
=== END STATUS ===
"""
            )

        # Add recent logs if available
        if data.get("recent_logs"):
            prompt_parts.append(
                f"""
=== RECENT SERVICE LOGS ===
{data['recent_logs']}
=== END LOGS ===
"""
            )

        # Add container information if available
        if data.get("container_info"):
            prompt_parts.append(
                f"""
=== CONTAINER INFORMATION ===
{data['container_info']}
=== END CONTAINER INFO ===
"""
            )

        # Add system resource information
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


class PromptGeneratorFactory:
    """Factory for creating appropriate prompt generators"""

    _generators = {
        "logs": LogsPromptGenerator,
        "reinit_failure": ReinitFailurePromptGenerator,
        "status": StatusPromptGenerator,
        "build_failure": BuildFailurePromptGenerator,
        "service_start_failure": ServiceStartFailurePromptGenerator,
        "performance": PerformancePromptGenerator,
        "security": SecurityPromptGenerator,
        "followup": FollowupPromptGenerator,
    }

    @classmethod
    def create(cls, analysis_type: str) -> PromptGenerator:
        """Create appropriate prompt generator for analysis type"""
        generator_class = cls._generators.get(analysis_type, GenericPromptGenerator)
        return generator_class()
