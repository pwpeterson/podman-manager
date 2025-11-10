"""Prompt generator for intelligent retry fixes."""

from datetime import datetime
from typing import Any, Dict

from .prompt_generators import PromptGenerator


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
        """Format retry history information."""
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
        """Format previously applied fixes."""
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
        """Get strategy guidance for specific retry attempt."""
        strategies = {
            1: "First retry - Use gentle, low-risk fixes. Focus on clearing failed states and reloading configurations.",
            2: "Second retry - Use medium-risk fixes. Clean up containers and resources that might be blocking the operation.",
            3: "Final retry - Use more aggressive fixes if necessary. Consider system-wide cleanup and force operations.",
        }

        return strategies.get(
            attempt, "Use appropriate fixes based on failure analysis."
        )

    def _get_service_specific_guidance(self, target: str) -> str:
        """Get service-specific guidance for fixes."""
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
        """Format system information for context."""
        formatted = []

        if "system_resources" in data:
            resources = data["system_resources"]
            if isinstance(resources, dict):
                for key, value in resources.items():
                    formatted.append(f"{key}: {value}")

        if "recent_logs" in data:
            logs = data["recent_logs"]
            if logs:
                formatted.append(f"Recent Logs Preview: {logs[:200]}...")

        return "\n".join(formatted) if formatted else "System information not available"
