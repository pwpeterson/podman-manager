# AI Agent Selection System

A flexible AI agent system that allows you to choose between different AI models for log analysis and troubleshooting.

## Features

### Supported AI Agents

#### Local Models
- **vllm-qwen25**: Qwen2.5 Coder 32B (via vllm-proxy on port 8002)
- **vllm-glm46**: GLM-4-6B (via port 8003) - *Your new model*

#### Cloud Models
- **claude-sonnet**: Claude 3 Sonnet (requires ANTHROPIC_API_KEY)
- **claude-haiku**: Claude 3 Haiku (faster, cheaper)
- **gpt-4**: OpenAI GPT-4 (requires OPENAI_API_KEY)
- **gpt-3.5-turbo**: OpenAI GPT-3.5 Turbo (faster, cheaper)

## Usage

### 1. View Available AI Agents
```bash
pm ai-agents
```
Shows all configured agents with their availability status.

### 2. Use AI Analysis with Specific Agent
```bash
# Use default agent (first available local, then cloud)
pm logs vllm-delegator -ai

# Use specific agent
pm logs vllm-delegator -ai --ai-agent vllm-glm46
pm logs vllm-delegator -ai --ai-agent claude-sonnet
pm logs vllm-delegator -ai --ai-agent gpt-4
```

### 3. AI Analysis During Reinit Failures
When services fail during reinit, AI analysis runs automatically:
```bash
pm reinit vllm-glm46 -v
# If it fails, AI analysis will run with the default agent
```

## Configuration

### Local Models
Local models require their respective services to be running:
- **vllm-qwen25**: Requires `vllm-proxy` service on port 8002
- **vllm-glm46**: Requires `vllm-glm46` service on port 8003

### Cloud Models
Cloud models require API keys as environment variables:
```bash
# For Claude models
export ANTHROPIC_API_KEY="your-api-key-here"

# For OpenAI models
export OPENAI_API_KEY="your-api-key-here"
```

## Agent Selection Priority

1. **Explicit Selection**: If `--ai-agent` is specified, use that agent
2. **Local First**: Prefer available local models (faster, private)
3. **Cloud Fallback**: Use available cloud models if no local models available
4. **Graceful Degradation**: Fall back to old vLLM system if new system fails

## Architecture

### Core Components

#### `ai_agents.py`
- **AIAgentConfig**: Configuration for each agent
- **AIAgent**: Abstract base class for all agents
- **LocalVLLMAgent**: Handles local vLLM services
- **ClaudeAgent**: Handles Anthropic Claude API
- **OpenAIAgent**: Handles OpenAI API
- **AIAgentManager**: Manages all agents and provides selection interface

#### Integration Points
- **CLI Parser**: Added `--ai-agent` option to logs command
- **Command Router**: Passes agent selection to operations
- **AI Diagnostics**: Updated to use new agent system with fallback
- **Reinit Manager**: Uses new system for failure analysis

### Agent Types

#### Local vLLM Agents
```python
AIAgentConfig(
    name="vllm-glm46",
    display_name="GLM-4-6B (Local)",
    agent_type="local_vllm",
    endpoint="http://localhost:8003",
    model_name="vllm-glm46",
    description="Local GLM-4-6B model"
)
```

#### Cloud Agents
```python
AIAgentConfig(
    name="claude-sonnet",
    display_name="Claude 3 Sonnet",
    agent_type="claude",
    model_name="claude-3-sonnet-20240229",
    api_key_env="ANTHROPIC_API_KEY",
    description="Anthropic Claude 3 Sonnet"
)
```

## Examples

### Basic Usage
```bash
# Show available agents
pm ai-agents

# Use default agent for analysis
pm logs vllm-delegator -ai

# Use specific local model
pm logs vllm-delegator -ai --ai-agent vllm-glm46

# Use cloud model
pm logs vllm-delegator -ai --ai-agent claude-sonnet
```

### Advanced Usage
```bash
# Verbose mode shows which agent is being used
pm logs vllm-delegator -ai --ai-agent gpt-4 -v

# AI analysis during reinit (uses default agent)
pm reinit vllm-glm46 -v
```

## Adding New Agents

To add a new AI agent, modify `ai_agents.py`:

1. **Add configuration** to `_load_default_configs()`:
```python
AIAgentConfig(
    name="your-model",
    display_name="Your Model Name",
    agent_type="local_vllm",  # or "claude", "openai"
    endpoint="http://localhost:8004",
    model_name="your-model-name",
    description="Description of your model"
)
```

2. **Create agent class** if needed (for new API types)
3. **Update agent creation** in `_load_default_configs()`

## Benefits

1. **Flexibility**: Choose the best AI model for your needs
2. **Privacy**: Use local models for sensitive data
3. **Cost Control**: Use cheaper models for routine analysis
4. **Reliability**: Automatic fallback if preferred agent unavailable
5. **Extensibility**: Easy to add new AI models and APIs
6. **Backward Compatibility**: Existing commands work unchanged

## Troubleshooting

### Agent Not Available
- **Local models**: Ensure the service is running (`pm start vllm-glm46`)
- **Cloud models**: Check API key environment variables
- **Network**: Verify connectivity to endpoints

### Fallback Behavior
If the new agent system fails, it automatically falls back to the original vLLM system for compatibility.

### Verbose Mode
Use `-v` flag to see detailed agent selection and execution information:
```bash
pm logs vllm-delegator -ai --ai-agent claude-sonnet -v
```

This will show:
- Which agent is being selected
- Agent availability checks
- API calls and responses
- Fallback behavior if needed
