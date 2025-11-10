"""Enhanced prompt generators for new AI analysis types in reinit process."""

from datetime import datetime
from typing import Any, Dict

from .prompt_generators import PromptGenerator


class PreReinitCheckPromptGenerator(PromptGenerator):
    """Generate prompts for pre-reinit health check analysis."""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        health_issues = data.get("health_check_failed", False)
        pre_reinit_state = data.get("pre_reinit_state", {})

        return f"""You are a system administration expert specializing in container and systemd service troubleshooting.

A pre-reinit health check has detected issues with the following service before attempting reinit:

Service: {target}
Timestamp: {timestamp}
Health Check Status: {'FAILED' if health_issues else 'PASSED'}

Pre-reinit State Information:
{self._format_pre_reinit_state(pre_reinit_state)}

Diagnostic Data:
{self._format_diagnostic_data(data)}

Please provide a focused analysis with:

1. **Risk Assessment**: What are the risks of proceeding with reinit given these health check results?
2. **Pre-reinit Fixes**: What issues should be resolved before attempting reinit?
3. **Reinit Strategy**: What specific reinit approach would be safest given the current state?
4. **Monitoring Points**: What should be watched carefully during the reinit process?

Focus on actionable recommendations that will improve reinit success probability."""

    def _format_pre_reinit_state(self, state: Dict[str, Any]) -> str:
        """Format pre-reinit state information."""
        if not state:
            return "No pre-reinit state captured"

        formatted = []

        if "service_properties" in state:
            formatted.append(f"Service Properties:\n{state['service_properties']}")

        if "container_state" in state:
            formatted.append(f"Container State: {state['container_state']}")

        if "timestamp" in state:
            formatted.append(
                f"State Captured: {datetime.fromtimestamp(state['timestamp'])}"
            )

        return "\n\n".join(formatted) if formatted else "No state information available"

    def _format_diagnostic_data(self, data: Dict[str, Any]) -> str:
        """Format diagnostic data for display."""
        formatted = []

        # Format logs if available
        if "recent_logs" in data:
            logs = data["recent_logs"]
            if logs:
                formatted.append("Recent Logs:")
                formatted.append(logs[:1000] + "..." if len(logs) > 1000 else logs)

        # Format systemd status if available
        if "systemd_status" in data:
            formatted.append(f"Systemd Status:\n{data['systemd_status']}")

        # Format container info if available
        if "container_info" in data:
            formatted.append(f"Container Info:\n{data['container_info']}")

        return "\n\n".join(formatted) if formatted else "No diagnostic data available"


class EnhancedReinitFailurePromptGenerator(PromptGenerator):
    """Generate prompts for enhanced reinit failure analysis with full context."""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        reinit_context = data.get("reinit_context", {})
        pre_reinit_state = data.get("pre_reinit_state", {})
        diagnostic_data = data.get("diagnostic_data", {})
        exception = data.get("exception")

        return f"""You are a system administration expert specializing in container reinit failure analysis.

A reinit operation has failed with comprehensive context available for analysis:

Service: {target}
Timestamp: {timestamp}
Failure Type: Enhanced Reinit Failure

Reinit Context:
{self._format_reinit_context(reinit_context)}

Pre-reinit State:
{self._format_pre_reinit_state(pre_reinit_state)}

{self._format_exception(exception or "")}

Diagnostic Data:
{self._format_diagnostic_data(diagnostic_data)}

System Information:
{self._format_system_info(data)}

Please provide a comprehensive failure analysis with:

1. **Root Cause Analysis**: What specifically caused the reinit to fail?
2. **Context Impact**: How did the pre-reinit state contribute to the failure?
3. **Recovery Strategy**: Step-by-step recovery plan with specific commands
4. **Prevention Measures**: How to prevent this failure in future reinits?
5. **Alternative Approaches**: What alternative reinit strategies might work?

Focus on actionable solutions that address the specific failure context."""

    def _format_reinit_context(self, context: Dict[str, Any]) -> str:
        """Format reinit context information."""
        if not context:
            return "No reinit context available"

        formatted = []

        if "target" in context:
            formatted.append(f"Target: {context['target']}")

        if "build" in context:
            formatted.append(f"Build Requested: {context['build']}")

        if "build_type" in context:
            formatted.append(f"Build Type: {context['build_type']}")

        if "vllm_model" in context:
            formatted.append(f"vLLM Model Switch: {context['vllm_model']}")

        if "start_time" in context:
            start_time = datetime.fromtimestamp(context["start_time"])
            formatted.append(f"Reinit Started: {start_time}")

        return "\n".join(formatted) if formatted else "No context information available"

    def _format_exception(self, exception: str) -> str:
        """Format exception information."""
        if exception:
            return f"Exception Details:\n{exception}\n"
        return ""

    def _format_pre_reinit_state(self, state: Dict[str, Any]) -> str:
        """Format pre-reinit state information."""
        if not state:
            return "No pre-reinit state captured"

        formatted = []

        if "service_properties" in state:
            formatted.append(f"Service Properties:\n{state['service_properties']}")

        if "container_state" in state:
            formatted.append(f"Container State: {state['container_state']}")

        if "timestamp" in state:
            formatted.append(
                f"State Captured: {datetime.fromtimestamp(state['timestamp'])}"
            )

        return "\n\n".join(formatted) if formatted else "No state information available"

    def _format_diagnostic_data(self, data: Dict[str, Any]) -> str:
        """Format diagnostic data for display."""
        formatted = []

        # Format logs if available
        if "recent_logs" in data:
            logs = data["recent_logs"]
            if logs:
                formatted.append("Recent Logs:")
                formatted.append(logs[:1000] + "..." if len(logs) > 1000 else logs)

        # Format systemd status if available
        if "systemd_status" in data:
            formatted.append(f"Systemd Status:\n{data['systemd_status']}")

        # Format container info if available
        if "container_info" in data:
            formatted.append(f"Container Info:\n{data['container_info']}")

        return "\n\n".join(formatted) if formatted else "No diagnostic data available"

    def _format_system_info(self, data: Dict[str, Any]) -> str:
        """Format system information."""
        formatted = []

        if "system_resources" in data:
            resources = data["system_resources"]
            if isinstance(resources, dict):
                for key, value in resources.items():
                    formatted.append(f"{key}: {value}")

        if "network_info" in data:
            formatted.append(f"Network: {data['network_info']}")

        if "storage_info" in data:
            formatted.append(f"Storage: {data['storage_info']}")

        return "\n".join(formatted) if formatted else "System information not available"


class PostReinitOptimizationPromptGenerator(PromptGenerator):
    """Generate prompts for post-reinit optimization suggestions."""

    def generate(self, target: str, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        verification_results = data.get("verification_results", [])
        reinit_context = data.get("reinit_context", {})
        pre_reinit_state = data.get("pre_reinit_state", {})

        return f"""You are a system optimization expert specializing in container and service performance.

A reinit operation has completed successfully. Please analyze the results and provide optimization suggestions:

Service: {target}
Timestamp: {timestamp}
Reinit Status: SUCCESS

Verification Results:
{self._format_verification_results(verification_results)}

Reinit Performance:
{self._format_reinit_performance(reinit_context, pre_reinit_state)}

System Context:
{self._format_system_info(data)}

Please provide optimization recommendations with:

1. **Performance Optimizations**: How to improve service startup time and resource usage
2. **Configuration Tuning**: Specific configuration changes for better performance
3. **Monitoring Setup**: What metrics to monitor for ongoing health
4. **Maintenance Schedule**: Recommended maintenance tasks and frequency
5. **Future Reinit Improvements**: How to make future reinits faster and more reliable

Focus on practical, implementable optimizations that will improve service reliability and performance."""

    def _format_verification_results(self, results: list) -> str:
        """Format verification results."""
        if not results:
            return "No verification results available"

        formatted = []
        for check_name, result in results:
            status = result.get("status", "unknown")
            details = result.get("details", "No details")
            formatted.append(f"{check_name}: {status.upper()} - {details}")

        return "\n".join(formatted)

    def _format_reinit_performance(
        self, reinit_context: Dict, pre_reinit_state: Dict
    ) -> str:
        """Format reinit performance information."""
        formatted = []

        if "start_time" in reinit_context and "timestamp" in pre_reinit_state:
            duration = reinit_context["start_time"] - pre_reinit_state["timestamp"]
            formatted.append(f"Total Reinit Duration: {duration:.1f} seconds")

        if "build" in reinit_context:
            formatted.append(
                f"Build Operation: {'Yes' if reinit_context['build'] else 'No'}"
            )

        if "vllm_model" in reinit_context and reinit_context["vllm_model"]:
            formatted.append(f"vLLM Model Switch: {reinit_context['vllm_model']}")

        return "\n".join(formatted) if formatted else "No performance data available"

    def _format_system_info(self, data: Dict[str, Any]) -> str:
        """Format system information."""
        formatted = []

        if "system_resources" in data:
            resources = data["system_resources"]
            if isinstance(resources, dict):
                for key, value in resources.items():
                    formatted.append(f"{key}: {value}")

        if "network_info" in data:
            formatted.append(f"Network: {data['network_info']}")

        if "storage_info" in data:
            formatted.append(f"Storage: {data['storage_info']}")

        return "\n".join(formatted) if formatted else "System information not available"
