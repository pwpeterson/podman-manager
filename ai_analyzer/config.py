"""Configuration management for AI analyzer"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class AnalysisConfig:
    """Configuration for AI analysis operations"""

    # Default timeouts for various operations
    command_timeout: int = 30
    logs_timeout: int = 30
    status_timeout: int = 15
    container_timeout: int = 15
    performance_timeout: int = 10

    # Default log collection settings
    default_log_lines: int = 50
    max_log_lines: int = 200

    # Output formatting settings
    max_inspect_length: int = 3000
    max_build_output_length: int = 2000
    command_wrap_threshold: int = 100
    text_wrap_width: int = 116

    # Interactive analysis settings
    enable_interactive: bool = True
    show_spinner: bool = True

    # AI agent settings
    default_ai_agent: Optional[str] = None
    agent_timeout: int = 60


@dataclass
class DataCollectionConfig:
    """Configuration for data collection operations"""

    # Quadlet directories to search
    quadlet_dirs: Optional[List[str]] = None

    # Common ports to check for conflicts
    common_ports: Optional[List[str]] = None

    # Container naming patterns to try
    container_patterns: Optional[List[str]] = None

    def __post_init__(self):
        if self.quadlet_dirs is None:
            self.quadlet_dirs = [
                "~/.config/containers/systemd",
                "/etc/containers/systemd",
                "/usr/share/containers/systemd",
            ]

        if self.common_ports is None:
            self.common_ports = ["8000", "8001", "8002", "8003", "8080", "3000", "5000"]

        if self.container_patterns is None:
            self.container_patterns = [
                "{service_name}.container",
                "{service_name_underscore}.container",
                "{service_name_dash}.container",
            ]


@dataclass
class AgentMappingConfig:
    """Configuration for AI agent name mappings"""

    agent_mapping: Optional[Dict[str, str]] = None

    def __post_init__(self):
        if self.agent_mapping is None:
            self.agent_mapping = {
                "qwen25": "vllm-qwen25",
                "glm46": "vllm-glm46",
                "claude": "claude-sonnet",
                "gpt4": "gpt-4",
                "gpt-4": "gpt-4",
                "claude-sonnet": "claude-sonnet",
                "vllm-qwen25": "vllm-qwen25",
                "vllm-glm46": "vllm-glm46",
            }


class AIAnalyzerConfig:
    """Main configuration class for AI analyzer"""

    def __init__(self):
        self.analysis = AnalysisConfig()
        self.data_collection = DataCollectionConfig()
        self.agent_mapping = AgentMappingConfig()

    def resolve_agent_name(self, short_name: Optional[str]) -> Optional[str]:
        """Convert short AI agent names to full names"""
        if not short_name or short_name is True:
            return self.analysis.default_ai_agent

        if self.agent_mapping.agent_mapping is None:
            return short_name

        return self.agent_mapping.agent_mapping.get(short_name.lower(), short_name)

    def set_default_agent(self, agent_name: str) -> None:
        """Set the default AI agent"""
        self.analysis.default_ai_agent = agent_name

    def get_quadlet_patterns(self, service_name: str) -> List[str]:
        """Get container file patterns for a service name"""
        patterns = []
        if self.data_collection.container_patterns is None:
            return patterns

        for pattern in self.data_collection.container_patterns:
            patterns.append(
                pattern.format(
                    service_name=service_name,
                    service_name_underscore=service_name.replace("-", "_"),
                    service_name_dash=service_name.replace("_", "-"),
                )
            )
        return patterns


# Global configuration instance
config = AIAnalyzerConfig()
