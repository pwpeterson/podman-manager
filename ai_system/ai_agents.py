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

    def __init__(self, config_file: str = "ai_config.json"):
        self.agents: Dict[str, AIAgent] = {}
        self.default_agent = None
        self.config_file = Path(config_file)
        self._load_default_configs()
        self._load_persistent_config()

    def _load_default_configs(self):
        """Load default agent configurations"""
        default_configs = [
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
        # Prefer local agents first
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

            except (json.JSONDecodeError, IOError) as e:
                console.print(
                    f"[yellow]Warning: Could not load AI config: {e}[/yellow]"
                )

    def _save_persistent_config(self) -> None:
        """Save persistent configuration to file"""
        try:
            config_data = {
                "default_agent": self.default_agent,
                "agent_preferences": {
                    "prefer_local": True,
                    "fallback_order": ["vllm-qwen25", "claude-sonnet", "gpt-4"],
                },
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
                    " [dim](default)[/dim]" if name == self.default_agent else ""
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
                    " [dim](default)[/dim]" if name == self.default_agent else ""
                )
                console.print(
                    f"  {status} [cyan]{name}[/cyan] - {agent.config.display_name}{default_marker}"
                )
                console.print(f"      {agent.config.description}")

        console.print()

    def analyze_with_agent(
        self, prompt: str, agent_name: Optional[str] = None, verbose: bool = False
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


# Global instance
ai_agent_manager = AIAgentManager()
