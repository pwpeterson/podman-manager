# Editing AI Agents Configuration

You can now edit the available AI agents by modifying configuration files instead of changing code. The system supports both programmatic management and direct file editing.

## Configuration File

### `ai_agents_config.json` - Complete AI Configuration
This single file contains both agent definitions and default agent settings. If this file exists, it overrides the hardcoded defaults in the code.

The file structure includes:
- `default_agent`: Currently selected default agent
- `agent_preferences`: Fallback order and preferences
- `agents`: Array of all available agent configurations

## Methods to Edit Agents

### Method 1: Direct File Editing (Recommended)

Edit the [`ai_agents_config.json`](../ai_agents_config.json) file to add, remove, or modify agents:

```json
{
  "default_agent": "my-custom-agent",
  "agent_preferences": {
    "prefer_local": true,
    "fallback_order": [
      "my-custom-agent",
      "vllm-qwen25",
      "claude-sonnet"
    ]
  },
  "agents": [
    {
      "name": "my-custom-agent",
      "display_name": "My Custom AI Model",
      "agent_type": "local_vllm",
      "endpoint": "http://localhost:8005",
      "model_name": "my-custom-model",
      "api_key_env": null,
      "max_tokens": 4096,
      "temperature": 0.1,
      "timeout": 60,
      "enabled": true,
      "description": "My custom local AI model"
    }
  ]
}
```

### Method 2: Programmatic Management

Use the `AIAgentManager` methods in Python:

```python
from ai_system.ai_agents import ai_agent_manager, AIAgentConfig

# Add a new agent
config = AIAgentConfig(
    name="new-agent",
    display_name="New Agent",
    agent_type="local_vllm",
    endpoint="http://localhost:8005",
    model_name="new-model",
    description="A new custom agent"
)
ai_agent_manager.add_agent(config)

# Remove an agent
ai_agent_manager.remove_agent("agent-name")

# Update an agent
ai_agent_manager.update_agent("agent-name", updated_config)

# Export current configuration
ai_agent_manager.export_agents_config("my_agents.json")
```

## Agent Configuration Parameters

### Required Parameters
- **`name`**: Unique identifier for the agent (used in commands)
- **`display_name`**: Human-readable name shown in UI
- **`agent_type`**: Type of agent (`"local_vllm"`, `"claude"`, `"openai"`)

### Agent Type Specific Parameters

#### Local vLLM Agents (`"local_vllm"`)
- **`endpoint`**: URL of the vLLM service (e.g., `"http://localhost:8002"`)
- **`model_name`**: Model identifier used by vLLM service

#### Claude Agents (`"claude"`)
- **`model_name`**: Claude model version (e.g., `"claude-3-sonnet-20240229"`)
- **`api_key_env`**: Environment variable containing API key (default: `"ANTHROPIC_API_KEY"`)

#### OpenAI Agents (`"openai"`)
- **`model_name`**: OpenAI model name (e.g., `"gpt-4"`, `"gpt-3.5-turbo"`)
- **`api_key_env`**: Environment variable containing API key (default: `"OPENAI_API_KEY"`)

### Optional Parameters
- **`max_tokens`**: Maximum response length (default: `2048`)
- **`temperature`**: Response randomness 0.0-1.0 (default: `0.1`)
- **`timeout`**: Request timeout in seconds (default: `60`)
- **`enabled`**: Whether agent is active (default: `true`)
- **`description`**: Human-readable description

## Examples

### Adding a New Local Model

```json
{
  "name": "vllm-llama3",
  "display_name": "Llama 3 70B (Local)",
  "agent_type": "local_vllm",
  "endpoint": "http://localhost:8005",
  "model_name": "llama3-70b-instruct",
  "max_tokens": 4096,
  "temperature": 0.1,
  "timeout": 120,
  "enabled": true,
  "description": "Local Llama 3 70B model for advanced reasoning"
}
```

### Adding a Custom Cloud API

```json
{
  "name": "custom-api",
  "display_name": "Custom API Service",
  "agent_type": "openai",
  "endpoint": null,
  "model_name": "custom-model-v1",
  "api_key_env": "CUSTOM_API_KEY",
  "max_tokens": 2048,
  "temperature": 0.2,
  "timeout": 90,
  "enabled": true,
  "description": "Custom API service with OpenAI-compatible interface"
}
```

### Modifying Existing Agents

To modify an existing agent, find it in [`ai_agents_config.json`](../ai_agents_config.json) and change the desired parameters:

```json
{
  "default_agent": "claude-sonnet",
  "agent_preferences": {
    "prefer_local": true,
    "fallback_order": ["vllm-qwen25", "claude-sonnet", "gpt-4"]
  },
  "agents": [
    {
      "name": "claude-sonnet",
      "display_name": "Claude 3 Sonnet (Modified)",
      "agent_type": "claude",
      "model_name": "claude-3-sonnet-20240229",
      "api_key_env": "ANTHROPIC_API_KEY",
      "max_tokens": 4096,
      "temperature": 0.2,
      "timeout": 120,
      "enabled": true,
      "description": "Modified Claude 3 Sonnet with higher token limit"
    }
  ]
}
```

### Disabling Agents

Set `"enabled": false` to temporarily disable an agent without removing it:

```json
{
  "name": "gpt-4",
  "display_name": "GPT-4",
  "agent_type": "openai",
  "model_name": "gpt-4",
  "api_key_env": "OPENAI_API_KEY",
  "enabled": false,
  "description": "OpenAI GPT-4 (temporarily disabled)"
}
```

## How It Works

1. **Startup**: System checks for [`ai_agents_config.json`](../ai_agents_config.json)
2. **If found**: Loads agents and default settings from the file
3. **If not found**: Uses hardcoded defaults from [`ai_system/ai_agents.py`](../ai_system/ai_agents.py)
4. **Agent creation**: Creates appropriate agent instances based on `agent_type`
5. **Persistence**: Changes made programmatically are saved back to the file

## File Locations

- **Complete configuration**: [`ai_agents_config.json`](../ai_agents_config.json) (root directory)
- **Legacy files** (deprecated): [`agents_config.json`](../agents_config.json)

## Usage After Editing

After editing the configuration:

1. **Restart the application** or reload the agent manager
2. **Check agent status**: `pm ai-agents`
3. **Set new default**: `pm set-default-ai <agent-name>`
4. **Test the agent**: `pm logs <service> -ai <agent-name>`

## Validation

The system validates:
- Required parameters are present
- Agent types are supported (`local_vllm`, `claude`, `openai`)
- Numeric parameters are valid
- No duplicate agent names

Invalid configurations will show warnings and fall back to defaults.

## Backup and Recovery

Before making changes:

1. **Backup current config**: `cp ai_agents_config.json ai_agents_config.json.backup`
2. **Export current agents**: Use `ai_agent_manager.export_agents_config("backup.json")`
3. **Test changes**: Verify agents work with `pm ai-agents`
4. **Restore if needed**: `cp ai_agents_config.json.backup ai_agents_config.json`

## Troubleshooting

### Agent Not Appearing
- Check JSON syntax with a validator
- Ensure all required parameters are present
- Verify `agent_type` is valid
- Check for duplicate `name` values

### Agent Shows as Unavailable
- **Local agents**: Ensure the service is running at the specified endpoint
- **Cloud agents**: Verify API key environment variable is set
- **Network**: Check connectivity to endpoints
- **Permissions**: Ensure file permissions allow reading the config

### Changes Not Taking Effect
- Restart the application
- Check for JSON syntax errors
- Verify file is in the correct location
- Check console for warning messages

This system provides flexible agent management while maintaining backward compatibility with the existing hardcoded defaults.
