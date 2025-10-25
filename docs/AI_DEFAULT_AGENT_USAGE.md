# Setting Default AI Agent

You can now dynamically set the default AI agent using the PM command line interface.

## Usage

### Set Default Agent
```bash
pm set-default-ai <agent_name>
```

### Available Agent Names
- `qwen25` → `vllm-qwen25` (Local Qwen2.5 Coder 32B)
- `glm46` → `vllm-glm46` (Local GLM-4-6B)
- `claude` → `claude-sonnet` (Claude 3 Sonnet)
- `gpt4` → `gpt-4` (OpenAI GPT-4)
- Full names: `vllm-qwen25`, `vllm-glm46`, `claude-sonnet`, `gpt-4`

### Examples
```bash
# Set Claude as default
pm set-default-ai claude

# Set local Qwen2.5 as default
pm set-default-ai qwen25

# Set GPT-4 as default
pm set-default-ai gpt4
```

### View Current Status
```bash
pm ai-agents
```
This shows all available agents with the current default marked as `(default)`.

## Storage Locations

### Runtime (Memory)
- `AIAgentManager.default_agent` - Active default agent
- `AnalysisConfig.default_ai_agent` - Config override

### Persistent (File)
- `ai_agents_config.json` - JSON configuration file
- Automatically loaded on startup
- Automatically saved when changed

## How It Works

1. **Command Processing**: `pm set-default-ai claude`
2. **Name Resolution**: `claude` → `claude-sonnet`
3. **Validation**: Check if agent exists and is available
4. **Storage**: Save to both memory and `ai_agents_config.json`
5. **Confirmation**: Display success message with file path

## Integration

The default agent is used automatically in:
- AI log analysis (`pm logs <service> --ai-agent`)
- Build failure analysis
- Automatic error detection and analysis
- Interactive AI troubleshooting sessions

## Fallback Behavior

If the configured default agent is unavailable:
1. Try first available local agent (vllm-qwen25, vllm-glm46)
2. Fall back to first available cloud agent (claude-sonnet, gpt-4)
3. Show error if no agents are available
