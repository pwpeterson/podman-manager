"""AI Agent Configuration and Management System"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

from rich.progress import Progress, SpinnerColumn, TextColumn

from core.config import console, verbose_print


@dataclass
class AIAgentConfig:
    """Configuration for an AI agent"""

    name: str
    display_name: str
    agent_type: str  # 'local_vllm', 'claude', 'openai'
    endpoint: Optional[str] = None
    model_name: Optional[str] = None
    api_key_env: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.1
    timeout: int = 60
    enabled: bool = True
    description: str = ""


class AIAgent(ABC):
    """Abstract base class for AI agents"""

    def __init__(self, config: AIAgentConfig):
        self.config = config

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the agent is available and ready to use"""
        pass

    @abstractmethod
    def analyze_logs(self, prompt: str) -> Optional[str]:
        """Send prompt to AI agent and return response"""
        pass

    def get_display_info(self) -> str:
        """Get display information for this agent"""
        status = "✅ Available" if self.is_available() else "❌ Unavailable"
        return f"{self.config.display_name} ({self.config.agent_type}) - {status}"


class LocalVLLMAgent(AIAgent):
    """Local vLLM agent (via vllm-proxy or direct endpoint)"""

    def is_available(self) -> bool:
        """Check if local vLLM service is available"""
        if not requests or not self.config.endpoint:
            return False

        try:
            response = requests.get(f"{self.config.endpoint}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def analyze_logs(self, prompt: str) -> Optional[str]:
        """Send prompt to local vLLM service"""
        if not requests or not self.config.endpoint:
            return None

        payload = {
            "model": self.config.model_name or "vllm-model",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert system administrator and DevOps engineer specializing in systemd service log analysis and troubleshooting.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False,
        }

        try:
            response = requests.post(
                f"{self.config.endpoint}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.config.timeout,
            )

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    if "message" in choice:
                        return choice["message"]["content"].strip()
                    elif "text" in choice:
                        return choice["text"].strip()

            return None

        except requests.RequestException:
            return None


class ClaudeAgent(AIAgent):
    """Anthropic Claude agent"""

    def is_available(self) -> bool:
        """Check if Claude API key is available"""
        api_key = os.getenv(self.config.api_key_env or "ANTHROPIC_API_KEY")
        return api_key is not None and requests is not None

    def analyze_logs(self, prompt: str) -> Optional[str]:
        """Send prompt to Claude API"""
        if not requests:
            return None

        api_key = os.getenv(self.config.api_key_env or "ANTHROPIC_API_KEY")
        if not api_key:
            return None

        payload = {
            "model": self.config.model_name or "claude-3-sonnet-20240229",
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )

            if response.status_code == 200:
                result = response.json()
                if "content" in result and len(result["content"]) > 0:
                    return result["content"][0]["text"]

            return None

        except requests.RequestException:
            return None


class OpenAIAgent(AIAgent):
    """OpenAI ChatGPT agent"""

    def is_available(self) -> bool:
        """Check if OpenAI API key is available"""
        api_key = os.getenv(self.config.api_key_env or "OPENAI_API_KEY")
        return api_key is not None and requests is not None

    def analyze_logs(self, prompt: str) -> Optional[str]:
        """Send prompt to OpenAI API"""
        if not requests:
            return None

        api_key = os.getenv(self.config.api_key_env or "OPENAI_API_KEY")
        if not api_key:
            return None

        payload = {
            "model": self.config.model_name or "gpt-4",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert system administrator and DevOps engineer specializing in systemd service log analysis and troubleshooting.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]

            return None

        except requests.RequestException:
            return None


class AIAgentManager:
    """Manages AI agents and provides selection interface"""

    def __init__(self, config_file: str = "ai_agents_config.json"):
        self.agents: Dict[str, AIAgent] = {}
        self.default_agent = None

        # If config_file is relative, make it relative to this module's directory
        if not Path(config_file).is_absolute():
            # Get the directory where this script is located
            script_dir = Path(__file__).parent.parent
            self.config_file = script_dir / config_file
        else:
            self.config_file = Path(config_file)

        self._load_default_configs()
        self._load_persistent_config()

    def _load_agents_config(self) -> Optional[List[AIAgentConfig]]:
        """Load agent configurations from ai_agents_config.json file"""
        if not self.config_file.exists():
            return None

        try:
            with open(self.config_file, "r") as f:
                config_data = json.load(f)

            agents = []
            for agent_data in config_data.get("agents", []):
                # Convert dict to AIAgentConfig
                config = AIAgentConfig(
                    name=agent_data["name"],
                    display_name=agent_data["display_name"],
                    agent_type=agent_data["agent_type"],
                    endpoint=agent_data.get("endpoint"),
                    model_name=agent_data.get("model_name"),
                    api_key_env=agent_data.get("api_key_env"),
                    max_tokens=agent_data.get("max_tokens", 2048),
                    temperature=agent_data.get("temperature", 0.1),
                    timeout=agent_data.get("timeout", 60),
                    enabled=agent_data.get("enabled", True),
                    description=agent_data.get("description", ""),
                )
                agents.append(config)

            return agents

        except (json.JSONDecodeError, IOError, KeyError) as e:
            console.print(
                f"[yellow]Warning: Could not load agents config: {e}[/yellow]"
            )
            return None

    def _save_agents_config(self, agents: List[AIAgentConfig]) -> None:
        """Save agent configurations to ai_agents_config.json file"""
        try:
            # Load existing config to preserve default_agent and preferences
            existing_config = {}
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r") as f:
                        existing_config = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass

            config_data = {
                "default_agent": existing_config.get(
                    "default_agent", self.default_agent
                ),
                "agent_preferences": existing_config.get(
                    "agent_preferences",
                    {
                        "prefer_local": True,
                        "fallback_order": ["vllm-qwen25", "claude-sonnet", "gpt-4"],
                    },
                ),
                "agents": [
                    {
                        "name": agent.name,
                        "display_name": agent.display_name,
                        "agent_type": agent.agent_type,
                        "endpoint": agent.endpoint,
                        "model_name": agent.model_name,
                        "api_key_env": agent.api_key_env,
                        "max_tokens": agent.max_tokens,
                        "temperature": agent.temperature,
                        "timeout": agent.timeout,
                        "enabled": agent.enabled,
                        "description": agent.description,
                    }
                    for agent in agents
                ],
            }

            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=2)

        except IOError as e:
            console.print(
                f"[yellow]Warning: Could not save agents config: {e}[/yellow]"
            )

    def _load_default_configs(self):
        """Load default agent configurations"""
        # Load agents from config file if it exists, otherwise use defaults
        agents_config = self._load_agents_config()
        default_configs = (
            agents_config
            if agents_config
            else [
                # Local vLLM agents
                AIAgentConfig(
                    name="vllm-qwen25",
                    display_name="Qwen2.5 Coder 32B (Local)",
                    agent_type="local_vllm",
                    endpoint="http://localhost:8002",
                    model_name="vllm-qwen25-coder-32b-instruct-awq",
                    description="Local Qwen2.5 Coder 32B model via vllm-proxy",
                ),
                AIAgentConfig(
                    name="vllm-glm46",
                    display_name="GLM-4-6B (Local)",
                    agent_type="local_vllm",
                    endpoint="http://localhost:8003",  # Assuming different port
                    model_name="vllm-glm46",
                    description="Local GLM-4-6B model",
                ),
                # Cloud agents
                AIAgentConfig(
                    name="claude-sonnet",
                    display_name="Claude 3 Sonnet",
                    agent_type="claude",
                    model_name="claude-3-sonnet-20240229",
                    api_key_env="ANTHROPIC_API_KEY",
                    description="Anthropic Claude 3 Sonnet",
                ),
                AIAgentConfig(
                    name="claude-haiku",
                    display_name="Claude 3 Haiku",
                    agent_type="claude",
                    model_name="claude-3-haiku-20240307",
                    api_key_env="ANTHROPIC_API_KEY",
                    max_tokens=1024,
                    description="Anthropic Claude 3 Haiku (faster, cheaper)",
                ),
                AIAgentConfig(
                    name="gpt-4",
                    display_name="GPT-4",
                    agent_type="openai",
                    model_name="gpt-4",
                    api_key_env="OPENAI_API_KEY",
                    description="OpenAI GPT-4",
                ),
                AIAgentConfig(
                    name="gpt-3.5-turbo",
                    display_name="GPT-3.5 Turbo",
                    agent_type="openai",
                    model_name="gpt-3.5-turbo",
                    api_key_env="OPENAI_API_KEY",
                    max_tokens=1024,
                    description="OpenAI GPT-3.5 Turbo (faster, cheaper)",
                ),
            ]
        )

        # Create agent instances
        for config in default_configs:
            if config.agent_type == "local_vllm":
                self.agents[config.name] = LocalVLLMAgent(config)
            elif config.agent_type == "claude":
                self.agents[config.name] = ClaudeAgent(config)
            elif config.agent_type == "openai":
                self.agents[config.name] = OpenAIAgent(config)

        # Set default agent (first available local, then first available cloud)
        self.default_agent = self._find_default_agent()

    def _find_default_agent(self) -> Optional[str]:
        """Find the best default agent"""
        # Try to load fallback order from config file
        fallback_order = [
            "vllm-qwen25",
            "claude-sonnet",
            "gpt-4",
        ]  # Default fallback order

        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    config_data = json.load(f)
                    agent_preferences = config_data.get("agent_preferences", {})
                    fallback_order = agent_preferences.get(
                        "fallback_order", fallback_order
                    )
            except (json.JSONDecodeError, IOError):
                pass

        # Check agents in fallback order
        for agent_name in fallback_order:
            if agent_name in self.agents and self.agents[agent_name].is_available():
                return agent_name

        # If none from fallback order are available, prefer local agents first
        local_agents = [
            name
            for name, agent in self.agents.items()
            if agent.config.agent_type == "local_vllm" and agent.is_available()
        ]
        if local_agents:
            return local_agents[0]

        # Fall back to cloud agents
        cloud_agents = [
            name
            for name, agent in self.agents.items()
            if agent.config.agent_type in ["claude", "openai"] and agent.is_available()
        ]
        if cloud_agents:
            return cloud_agents[0]

        return None

    def set_default_agent(self, agent_name: str, persist: bool = True) -> bool:
        """Set a specific agent as the default"""
        if agent_name in self.agents:
            self.default_agent = agent_name
            if persist:
                self._save_persistent_config()
            return True
        return False

    def refresh_default_agent(self) -> Optional[str]:
        """Re-evaluate and set the default agent based on availability"""
        self.default_agent = self._find_default_agent()
        return self.default_agent

    def _load_persistent_config(self) -> None:
        """Load persistent configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    config_data = json.load(f)

                # Load default agent if specified and available
                saved_default = config_data.get("default_agent")
                if saved_default and saved_default in self.agents:
                    self.default_agent = saved_default
                    # If saved default is not available, fall back to auto-selection
                    if not self.agents[saved_default].is_available():
                        self.default_agent = self._find_default_agent()

            except (json.JSONDecodeError, IOError) as e:
                console.print(
                    f"[yellow]Warning: Could not load AI config: {e}[/yellow]"
                )

    def _save_persistent_config(self) -> None:
        """Save persistent configuration to file"""
        try:
            # Load existing config to preserve agents list
            existing_config = {}
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r") as f:
                        existing_config = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass

            config_data = {
                "default_agent": self.default_agent,
                "agent_preferences": existing_config.get(
                    "agent_preferences",
                    {
                        "prefer_local": True,
                        "fallback_order": ["vllm-qwen25", "claude-sonnet", "gpt-4"],
                    },
                ),
                "agents": existing_config.get("agents", []),
            }

            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=2)

        except IOError as e:
            console.print(f"[yellow]Warning: Could not save AI config: {e}[/yellow]")

    def get_config_file_path(self) -> str:
        """Get the path to the configuration file"""
        return str(self.config_file.absolute())

    def get_agent(self, agent_name: Optional[str] = None) -> Optional[AIAgent]:
        """Get an agent by name, or return default agent"""
        if agent_name and agent_name in self.agents:
            return self.agents[agent_name]
        elif self.default_agent:
            return self.agents[self.default_agent]
        else:
            return None

    def list_agents(self) -> List[str]:
        """List all available agent names"""
        return list(self.agents.keys())

    def list_available_agents(self) -> List[str]:
        """List only available agent names"""
        return [name for name, agent in self.agents.items() if agent.is_available()]

    def show_agents_status(self):
        """Display status of all agents"""
        console.print("\n[bold cyan]Available AI Agents:[/bold cyan]")

        # Group by type
        local_agents = [
            (name, agent)
            for name, agent in self.agents.items()
            if agent.config.agent_type == "local_vllm"
        ]
        cloud_agents = [
            (name, agent)
            for name, agent in self.agents.items()
            if agent.config.agent_type in ["claude", "openai"]
        ]

        if local_agents:
            console.print("\n[bold green]Local Models:[/bold green]")
            for name, agent in local_agents:
                status = "✅" if agent.is_available() else "❌"
                default_marker = (
                    " [bright_yellow](default)[/bright_yellow]"
                    if name == self.default_agent
                    else ""
                )
                console.print(
                    f"  {status} [cyan]{name}[/cyan] - {agent.config.display_name}{default_marker}"
                )
                console.print(f"      {agent.config.description}")

        if cloud_agents:
            console.print("\n[bold blue]Cloud Models:[/bold blue]")
            for name, agent in cloud_agents:
                status = "✅" if agent.is_available() else "❌"
                default_marker = (
                    " [bright_yellow](default)[/bright_yellow]"
                    if name == self.default_agent
                    else ""
                )
                console.print(
                    f"  {status} [cyan]{name}[/cyan] - {agent.config.display_name}{default_marker}"
                )
                console.print(f"      {agent.config.description}")

        console.print()

    def analyze_with_agent(
        self,
        prompt: str,
        agent_name: Optional[str] = None,
        verbose: bool = False,
        target: Optional[str] = None,
    ) -> Optional[str]:
        """Analyze logs using specified agent or default"""
        agent = self.get_agent(agent_name)
        if not agent:
            if verbose:
                verbose_print("  [cyan]exec: No AI agent available[/cyan]")
            return None

        if not agent.is_available():
            if verbose:
                verbose_print(
                    f"  [cyan]exec: Agent {agent.config.name} is not available[/cyan]"
                )
            return None

        # Show spinner before starting AI analysis
        with Progress(
            SpinnerColumn(),
            TextColumn("[green]Analyzing error data...[/green]"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("analyzing", total=None)

            if verbose:
                verbose_print(
                    f"  [cyan]exec: Using AI agent: {agent.config.display_name}[/cyan]"
                )

            try:
                result = agent.analyze_logs(prompt)
                progress.remove_task(task)
                return result
            except Exception as e:
                progress.remove_task(task)
                if verbose:
                    verbose_print(f"  [cyan]exec: Agent analysis failed: {e}[/cyan]")
                return None

    def add_agent(self, config: AIAgentConfig) -> bool:
        """Add a new agent configuration"""
        if config.name in self.agents:
            return False  # Agent already exists

        # Create agent instance
        if config.agent_type == "local_vllm":
            self.agents[config.name] = LocalVLLMAgent(config)
        elif config.agent_type == "claude":
            self.agents[config.name] = ClaudeAgent(config)
        elif config.agent_type == "openai":
            self.agents[config.name] = OpenAIAgent(config)
        else:
            return False  # Unknown agent type

        # Save to config file
        self._save_current_agents_config()
        return True

    def remove_agent(self, agent_name: str) -> bool:
        """Remove an agent configuration"""
        if agent_name not in self.agents:
            return False

        # Don't allow removing the default agent
        if agent_name == self.default_agent:
            return False

        del self.agents[agent_name]
        self._save_current_agents_config()
        return True

    def update_agent(self, agent_name: str, config: AIAgentConfig) -> bool:
        """Update an existing agent configuration"""
        if agent_name not in self.agents:
            return False

        # Create new agent instance with updated config
        if config.agent_type == "local_vllm":
            self.agents[agent_name] = LocalVLLMAgent(config)
        elif config.agent_type == "claude":
            self.agents[agent_name] = ClaudeAgent(config)
        elif config.agent_type == "openai":
            self.agents[agent_name] = OpenAIAgent(config)
        else:
            return False

        self._save_current_agents_config()
        return True

    def _save_current_agents_config(self) -> None:
        """Save current agents to config file"""
        configs = [agent.config for agent in self.agents.values()]
        self._save_agents_config(configs)

    def export_agents_config(self, filename: str = "agents_config.json") -> bool:
        """Export current agent configurations to a file"""
        try:
            configs = [agent.config for agent in self.agents.values()]
            config_data = {
                "agents": [
                    {
                        "name": agent.name,
                        "display_name": agent.display_name,
                        "agent_type": agent.agent_type,
                        "endpoint": agent.endpoint,
                        "model_name": agent.model_name,
                        "api_key_env": agent.api_key_env,
                        "max_tokens": agent.max_tokens,
                        "temperature": agent.temperature,
                        "timeout": agent.timeout,
                        "enabled": agent.enabled,
                        "description": agent.description,
                    }
                    for agent in configs
                ]
            }

            with open(filename, "w") as f:
                json.dump(config_data, f, indent=2)

            console.print(f"[green]Agents configuration exported to {filename}[/green]")
            return True

        except IOError as e:
            console.print(f"[red]Error exporting agents config: {e}[/red]")
            return False

    def reload_config(self) -> None:
        """Reload configuration from file"""
        import importlib
        import sys

        # Clear current state
        self.agents.clear()
        self.default_agent = None

        # Force reload of this module to clear any cached imports
        if "ai_system.ai_agents" in sys.modules:
            importlib.reload(sys.modules["ai_system.ai_agents"])

        # Reload configuration
        self._load_default_configs()
        self._load_persistent_config()


# Global instance
ai_agent_manager = AIAgentManager()
