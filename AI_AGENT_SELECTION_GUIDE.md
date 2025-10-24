# AI Agent Selection Guide

This guide explains how to choose and use different AI agents for log analysis in the PM (Podman Manager) system.

## Quick Start

### 1. View Available AI Agents

```bash
pm ai-agents
```

This command shows all configured AI agents and their availability status:

```
🤖 Available AI Agents for Log Analysis

✅ vllm-qwen25 (local_vllm) - Available
   Local Qwen2.5-Coder model via vLLM proxy
   Endpoint: http://localhost:8002

❌ vllm-glm46 (local_vllm) - Unavailable
   Local GLM-4-9B model via vLLM proxy
   Endpoint: http://localhost:8003

✅ claude-sonnet (claude) - Available
   Anthropic Claude 3.5 Sonnet via API
   Requires: ANTHROPIC_API_KEY environment variable

❌ gpt-4 (openai) - Unavailable
   OpenAI GPT-4 via API
   Requires: OPENAI_API_KEY environment variable
```

### 2. Use AI Analysis with Specific Agent

```bash
# New short syntax (recommended)
pm logs vllm-glm46 -ai qwen25
pm logs vllm-glm46 -ai claude
pm logs vllm-glm46 -ai glm46

# Original long syntax (still supported)
pm logs vllm-glm46 -ai --ai-agent vllm-qwen25

# Use specific agent for reinit failure analysis (automatic)
pm reinit vllm-glm46 -v  # Will use default agent if reinit fails
```

## Short Agent Names

For convenience, you can use short names instead of full agent names:

| Short Name | Full Agent Name | Description |
|------------|-----------------|-------------|
| `qwen25`   | `vllm-qwen25`   | Qwen2.5-Coder model (best for technical analysis) |
| `glm46`    | `vllm-glm46`    | GLM-4-9B model (good for general analysis) |
| `claude`   | `claude-sonnet` | Claude 3.5 Sonnet (excellent reasoning) |
| `gpt4`     | `gpt-4`         | OpenAI GPT-4 (general analysis) |

**Examples:**
```bash
pm logs service -ai qwen25    # Same as: pm logs service -ai --ai-agent vllm-qwen25
pm logs service -ai claude    # Same as: pm logs service -ai --ai-agent claude-sonnet
pm logs service -ai glm46     # Same as: pm logs service -ai --ai-agent vllm-glm46
```

## Available AI Agents

### Local vLLM Agents (Recommended)

#### vllm-qwen25
- **Model**: Qwen2.5-Coder-32B-Instruct-AWQ
- **Endpoint**: http://localhost:8002
- **Best for**: Code analysis, system administration, technical troubleshooting
- **Pros**: Fast, private, no API costs, excellent for technical content
- **Cons**: Requires local vLLM service running

#### vllm-glm46
- **Model**: GLM-4-9B-Chat
- **Endpoint**: http://localhost:8003
- **Best for**: General analysis, multilingual support
- **Pros**: Fast, private, no API costs, good general knowledge
- **Cons**: Requires local vLLM service running, smaller model

### Cloud-Based Agents

#### claude-sonnet
- **Model**: Claude 3.5 Sonnet
- **Provider**: Anthropic
- **Best for**: Complex reasoning, detailed analysis, code review
- **Pros**: Excellent reasoning, large context window, very reliable
- **Cons**: Requires API key, costs money per request
- **Setup**: Set `ANTHROPIC_API_KEY` environment variable

#### gpt-4
- **Model**: GPT-4
- **Provider**: OpenAI
- **Best for**: General analysis, creative problem solving
- **Pros**: Well-known, good general performance
- **Cons**: Requires API key, costs money per request, smaller context
- **Setup**: Set `OPENAI_API_KEY` environment variable

## How to Choose an Agent

### For Most Users (Recommended)
1. **First choice**: `vllm-qwen25` (if available)
   - Best balance of speed, privacy, and technical accuracy
   - No API costs
   - Excellent for system administration tasks

2. **Fallback**: `claude-sonnet` (if you have API key)
   - When local models are unavailable
   - For complex analysis requiring advanced reasoning

### By Use Case

#### System Administration & DevOps
- **Best**: `vllm-qwen25` - Trained specifically for coding/system tasks
- **Alternative**: `claude-sonnet` - Excellent reasoning for complex issues

#### Quick Troubleshooting
- **Best**: `vllm-glm46` - Faster, smaller model for simple issues
- **Alternative**: `vllm-qwen25` - More thorough but slightly slower

#### Complex Multi-Service Issues
- **Best**: `claude-sonnet` - Superior reasoning and large context window
- **Alternative**: `vllm-qwen25` - Good technical knowledge

#### Privacy-Sensitive Environments
- **Only use**: Local vLLM agents (`vllm-qwen25`, `vllm-glm46`)
- **Avoid**: Cloud agents (data sent to external APIs)

## Usage Examples

### Basic Log Analysis

```bash
# Use default agent (automatic selection)
pm logs vllm-glm46 -ai

# Use specific agent (short syntax - recommended)
pm logs vllm-glm46 -ai qwen25
pm logs vllm-glm46 -ai claude
pm logs vllm-glm46 -ai glm46

# Use specific agent (long syntax - still supported)
pm logs vllm-glm46 -ai --ai-agent vllm-qwen25
pm logs vllm-glm46 -ai --ai-agent claude-sonnet
```

### Reinit Failure Analysis

```bash
# Automatic AI analysis on failure (uses default agent)
pm reinit vllm-glm46 -v

# The system will automatically run AI analysis if reinit fails
# You can't specify agent for automatic analysis, but you can run manual analysis:
pm logs vllm-glm46 -ai --ai-agent claude-sonnet
```

### Verbose Analysis with Comprehensive Diagnostics

```bash
# Show AI prompt and detailed execution (short syntax)
pm logs vllm-glm46 -ai qwen25 -v

# Show AI prompt and detailed execution (long syntax)
pm logs vllm-glm46 -ai --ai-agent vllm-qwen25 -v

# Verbose mode for comprehensive analysis
pm logs vllm-glm46 -ai qwen25 -v
```

#### What Verbose Mode Shows

When using `-v` with AI analysis, you'll see:

**1. Diagnostic Command Execution:**
```
  exec: ai_analyze(type=logs, target=vllm-glm46, agent=vllm-qwen25)
  exec: Starting comprehensive diagnostic data collection for logs analysis
  exec: Collecting comprehensive service diagnostics for vllm-glm46
  exec: Resolving service name for target 'vllm-glm46'
  exec: Resolved to service 'vllm-glm46.service'
  exec: journalctl --user -u vllm-glm46.service -n 50 --no-pager
  exec: Collected 47 lines of systemd logs
  exec: Collecting systemd unit details
  exec: systemctl --user status vllm-glm46.service --no-pager -l
  exec: Unit status collected (exit code: 0)
  exec: systemctl --user cat vllm-glm46.service
  exec: Unit file content collected (1247 chars)
```

**2. Container Diagnostics:**
```
  exec: Collecting container details
  exec: podman ps -a --format {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}
  exec: Found 3 containers
  exec: Found matching container: vllm-glm46
  exec: podman logs vllm-glm46 --since 2h --timestamps --tail 100
  exec: Container logs collected (23 lines)
  exec: podman inspect vllm-glm46
  exec: Container inspect data collected (5432 chars)
```

**3. System Resource Analysis:**
```
  exec: Collecting system resource information
  exec: df -h /
  exec: Disk space information collected
  exec: podman system info
  exec: Podman system info collected (3456 chars)
  exec: podman system df
  exec: Podman disk usage collected
```

**4. Network & Storage Diagnostics:**
```
  exec: Collecting network and storage information
  exec: podman network ls
  exec: Found 2 Podman networks
  exec: podman volume ls
  exec: Found 1 Podman volumes
  exec: Checking port usage for common ports: 8000, 8001, 8002, 8003, 8080, 3000, 5000
  exec: ss -tulpen -H | grep :8002
  exec: Port 8002 is in use
  exec: Found 1 ports in use
```

**5. Complete AI Prompt:**
```
  exec: Generated AI analysis prompt
  ────────────────────────────────────────────────────────────────────────────────
  You are an expert system administrator and DevOps engineer.

  Target: vllm-glm46
  Analysis Type: logs
  [... complete prompt with all diagnostic data ...]
  ────────────────────────────────────────────────────────────────────────────────
```

This comprehensive verbose output provides complete transparency into:
- Every diagnostic command executed
- Success/failure status with exit codes
- Data collection metrics (lines, characters, counts)
- Error handling and progress tracking
- The exact prompt sent to the AI agent

## Agent Selection Priority

When no agent is specified, the system uses this priority order:

1. **vllm-qwen25** (if available)
2. **vllm-glm46** (if available)
3. **claude-sonnet** (if API key available)
4. **gpt-4** (if API key available)
5. **Fallback to old vLLM system**

## Setting Up Agents

### Local vLLM Agents

```bash
# Start the vLLM services
pm start vllm-qwen25    # For vllm-qwen25 agent
pm start vllm-glm46     # For vllm-glm46 agent

# Check if they're running
pm ai-agents
```

### Cloud API Agents

```bash
# Set up Anthropic Claude
export ANTHROPIC_API_KEY="your-api-key-here"

# Set up OpenAI GPT-4
export OPENAI_API_KEY="your-api-key-here"

# Add to your ~/.bashrc or ~/.zshrc to persist
echo 'export ANTHROPIC_API_KEY="your-key"' >> ~/.bashrc
```

## Troubleshooting Agent Issues

### Agent Shows as Unavailable

```bash
# Check agent status
pm ai-agents

# For local vLLM agents - check if service is running
pm status vllm-qwen25
pm logs vllm-qwen25

# Start the service if needed
pm start vllm-qwen25
```

### API Key Issues

```bash
# Check if environment variable is set
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY

# Test the API key (for Claude)
curl -H "x-api-key: $ANTHROPIC_API_KEY" \
     -H "anthropic-version: 2023-06-01" \
     https://api.anthropic.com/v1/messages
```

### Agent Selection Not Working

```bash
# Use verbose mode to see what's happening
pm logs service-name -ai --ai-agent agent-name -v

# Check the AI agent system
python3 -c "from ai_agents import ai_agent_manager; ai_agent_manager.show_agents_status()"
```

## Advanced Configuration

The AI agents are configured in `ai_agents.py`. You can modify:

- **Endpoints**: Change local vLLM service URLs
- **Models**: Update model names for local services
- **Timeouts**: Adjust request timeout values
- **Parameters**: Modify temperature, max_tokens, etc.

## Best Practices

1. **Start with local agents**: Use `vllm-qwen25` for most tasks
2. **Keep API keys secure**: Use environment variables, not hardcoded keys
3. **Use verbose mode**: Add `-v` to see comprehensive diagnostic execution
4. **Check agent status**: Run `pm ai-agents` before analysis
5. **Match agent to task**: Use technical agents for system issues
6. **Consider privacy**: Local agents keep data private
7. **Monitor costs**: Cloud agents charge per request
8. **Use verbose for transparency**: See exactly what diagnostic data is collected
9. **Combine with log limits**: Use `-n 100 -v` for comprehensive analysis
10. **Review diagnostic commands**: Verbose mode shows every command executed

## Integration with Commands

Currently supported commands with AI agent selection:

- `pm logs <service> -ai --ai-agent <agent>`
- `pm reinit <service>` (automatic analysis on failure)

Future commands will support the `--ai-agent` parameter as the system expands.
