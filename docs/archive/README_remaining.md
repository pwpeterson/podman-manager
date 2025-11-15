

## AI-Powered Analysis

### AI Agent System

The PM tool includes a flexible AI agent system for intelligent log analysis and troubleshooting:

#### View Available AI Agents
```bash
pm ai-agents
```

Shows all configured agents with availability status:
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
```

#### Available AI Agents

**Local Models (Recommended):**
- **qwen25** (`vllm-qwen25`): Qwen2.5-Coder-32B - Best for technical analysis
- **glm46** (`vllm-glm46`): GLM-4-9B - Good for general analysis

**Cloud Models:**
- **claude** (`claude-sonnet`): Claude 3.5 Sonnet - Excellent reasoning
- **gpt4** (`gpt-4`): OpenAI GPT-4 - General analysis

#### How to Choose an Agent

**For Most Users (Recommended):**
1. **First choice**: `qwen25` (if available) - Best balance of speed, privacy, and technical accuracy
2. **Fallback**: `claude` (if you have API key) - When local models are unavailable

**By Use Case:**
- **System Administration & DevOps**: `qwen25` - Trained specifically for coding/system tasks
- **Quick Troubleshooting**: `glm46` - Faster, smaller model for simple issues
- **Complex Multi-Service Issues**: `claude` - Superior reasoning and large context window
- **Privacy-Sensitive Environments**: Only use local agents (`qwen25`, `glm46`)

### AI Log Analysis

The enhanced logs command provides intelligent AI-powered analysis with comprehensive diagnostic data collection:

```bash
# Basic AI analysis (uses default agent)
pm logs service-name -ai

# Specific AI agent with short syntax (recommended)
pm logs vllm-qwen25 -ai qwen25
pm logs vllm-qwen25 -ai claude
pm logs vllm-qwen25 -ai glm46

# Original long syntax (still supported)
pm logs vllm-qwen25 -ai --ai-agent vllm-qwen25

# Comprehensive analysis with verbose diagnostics
pm logs service-name -ai claude -v
```

#### Comprehensive Diagnostic Data Collection

When using AI analysis with verbose mode (`-v`), the system collects and shows:

**1. Systemd Service Diagnostics:**
- `journalctl --user -u service-name -n 50 --no-pager`
- `systemctl --user status service-name --no-pager -l`
- `systemctl --user cat service-name`
- `systemctl --user show service-name -p ExecMainStatus,ExecMainCode,Result`

**2. Container Analysis:**
- `podman ps -a --format "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"`
- `podman logs container-name --since 2h --timestamps --tail 100`
- `podman inspect container-name`
- `podman pod ps --format "{{.ID}}\t{{.Name}}\t{{.Status}}"`

**3. System Resources:**
- `df -h /`
- `podman system info`
- `podman system df`

**4. Network & Storage:**
- `podman network ls`
- `podman volume ls`
- `ss -tulpen -H` (port conflict detection)

**5. Podman Quadlet Troubleshooting:**
- Service dependency analysis
- Environment variable resolution
- Systemd unit file validation
- Container image availability
- Port binding conflicts
- Volume mount permissions

#### Agent Selection Priority

When no agent is specified, the system uses this priority order:

1. **vllm-qwen25** (if available)
2. **vllm-glm46** (if available)
3. **claude-sonnet** (if API key available)
4. **gpt-4** (if API key available)
5. **Fallback to old vLLM system**

#### Setting Up AI Agents

**Local vLLM Agents:**
```bash
# Start the vLLM services
pm start vllm-qwen25    # For qwen25 agent
pm start vllm-glm46     # For glm46 agent

# Check if they're running
pm ai-agents
```

**Cloud API Agents:**
```bash
# Set up Anthropic Claude
export ANTHROPIC_API_KEY="your-api-key-here"

# Set up OpenAI GPT-4
export OPENAI_API_KEY="your-api-key-here"

# Add to your ~/.bashrc or ~/.zshrc to persist
echo 'export ANTHROPIC_API_KEY="your-key"' >> ~/.bashrc
```

### Automatic Reinit Failure Analysis

When services fail during reinit, AI analysis runs automatically:

```bash
pm reinit vllm-glm46 -v
# If it fails, AI analysis will run with the default agent
```

### Traditional Health Monitoring

The system also provides traditional health analysis:

- **HEALTHY**: Service running normally
- **MOSTLY_HEALTHY**: Minor warnings detected
- **WARNING**: Configuration issues present
- **UNHEALTHY**: Errors detected, requires attention

Health metrics include:
- Error patterns detection
- Warning analysis
- Startup indicators
- Connection issues
- Memory problems
- Permission errors

## Build AI Analysis

Automatic AI analysis for container build failures provides:

```bash
# Build with automatic AI analysis on failure (default)
pm build vllm-delegator

# Build with specific AI agent
pm build vllm-delegator --ai-agent claude

# Build with verbose output and AI analysis
pm build vllm-delegator -v

# Disable automatic AI analysis
pm build vllm-delegator --no-ai
```

### What Build AI Analysis Provides

- **Root Cause Analysis**: Primary reason for build failure
- **Immediate Fix**: Step-by-step commands to resolve issues
- **Dockerfile Improvements**: Syntax corrections and optimizations
- **Build Environment**: Environment-specific issues and solutions
- **Alternative Approaches**: Different build strategies
- **Prevention**: Best practices to avoid similar issues

### Supported Build Issues

- Dockerfile syntax errors and best practices
- Base image availability and compatibility
- Package installation failures (apt, yum, pip, npm, etc.)
- File copy/ADD operations and path issues
- Network connectivity during build
- Permission and user context issues
- Multi-stage build problems
- Build context and .dockerignore issues
- Resource constraints (disk space, memory)
- Registry authentication issues

## Volume Management

### Advanced Volume Copying

The volume copying feature automatically copies share networks when stack volumes are copied:

```bash
# Copy volumes from source stack to target stack (includes networks)
pm copy-volumes vllm-stack vllm-dev-stack

# Copy with verbose output
pm copy-volumes vllm-stack vllm-backup-stack -v

# List volumes and networks for a stack
pm list-volumes vllm-stack

# Clean up orphaned volumes
pm cleanup-volumes vllm-stack
```

#### How Volume Copying Works

1. **Analysis Phase**:
   - Scan source stack for volumes and networks
   - Parse quadlet files for network dependencies
   - Generate target names based on stack naming patterns

2. **Planning Phase**:
   - Display copy plan showing what will be copied
   - Check for existing targets to avoid conflicts

3. **Execution Phase**:
   - Copy networks first (volumes may depend on them)
   - Copy volumes with data using temporary containers
   - Preserve network configurations when possible

#### Network Dependency Resolution

The system analyzes quadlet `.container` files to identify network dependencies:

```ini
[Container]
Image=myapp:latest
Network=myapp-network
Volume=myapp-data:/data
```

In this example, `myapp-network` would be identified as a dependency and copied along with any volumes.

#### Naming Conventions

Volumes and networks are renamed using stack-based patterns:

- **Source**: `vllm-postgres-data` → **Target**: `vllm-dev-postgres-data`
- **Source**: `local-ai-network` → **Target**: `local-ai-test-network`

The system replaces the source stack prefix with the target stack prefix.

### Resource Management

```bash
# List volumes with usage
pm volumes

# List networks
pm networks

# Show system disk usage
pm system-df

# Remove project orphans
pm remove-orphans project-name
```

## Container Validation

The system includes comprehensive container file validation that runs automatically during `pm install`:

### What Gets Validated

1. **Invalid/Deprecated Parameters**:
   - `Expose` → Should use `PublishPort`
   - `Port`/`Ports` → Should use `PublishPort`
   - `Env` → Should use `Environment`
   - `EnvFile` → Should use `EnvironmentFile`
   - `Volumes` → Should use `Volume`
   - `Networks` → Should use `Network`

2. **Section-Specific Issues**:
   - `Restart` in `[Container]` section → Should be in `[Service]` section
   - `RestartPolicy` in `[Container]` section → Should be in `[Service]` section

3. **Missing Environment Variables**:
   - Detects unresolved environment variable references like `${POSTGRES_DB}`
   - Distinguishes between variables with default values (`${VAR:-default}`) and those without
   - Reports missing variables as errors, variables with defaults as warnings

4. **Configuration Issues**:
   - Missing required `[Container]` section
   - Missing required `Image` parameter
   - Invalid port format in `PublishPort`
   - Non-existent `EnvironmentFile` references

### Example Validation Output

```
Validating 1 container file(s)...
✗ local-ai-postgres.container: 3 error(s)
  • Invalid parameter 'Expose' in [Container] section. Use 'PublishPort' instead.
  • Invalid parameter 'Restart' in [Container] section. Use 'RestartPolicy' in [Service] section instead.
  • Environment variable 'POSTGRES_DB' is not set and has no default value
⚠ local-ai-postgres.container: 1 warning(s)
  • Environment variable 'POSTGRES_VERSION' not set, will use default value

Validation failed: 3 error(s) found across 1 file(s)
Installation aborted due to validation errors.
Fix the errors above and try again.
```

### Benefits

1. **Prevents Service Loading Failures** - Catches issues before they cause systemd service loading problems
2. **Clear Error Messages** - Specific guidance on how to fix each issue
3. **Early Detection** - Problems are caught before files are copied to systemd
4. **Comprehensive Coverage** - Validates against known quadlet/systemd parameters

## Common Actions System

The system provides standardized "More available actions" across all pm commands with 8 categories:

1. **PM Command Shortcuts** - Quick pm command references
2. **Service Status** - systemctl status and service information commands
3. **Logs & Diagnostics** - journalctl and log analysis commands
4. **Container Operations** - podman container management commands
5. **System Resources** - disk space, memory, system info commands
6. **Network & Connectivity** - network testing and port checking commands
7. **Volume Management** - podman volume operations
8. **Troubleshooting** - systemd and general troubleshooting commands

### Essential Commands (Compact Format)
```
✓ podman logs      : pm logs SERVICE
✓ service logs     : journalctl --user -u SERVICE.service -n 100
✓ service status   : systemctl --user status SERVICE.service --no-pager -l
✓ service config   : systemctl --user cat SERVICE.service
✓ troubleshoot     : pm diag SERVICE
✓ restart service  : pm restart SERVICE
```

### Benefits

**For Users:**
- **Consistent Experience**: Same commands available regardless of which pm operation was used
- **Comprehensive Coverage**: All common troubleshooting scenarios covered
- **Easy Discovery**: Commands organized by category for easy navigation

**For Developers:**
- **DRY Principle**: Single source of truth for common actions
- **Easy Integration**: Simple function calls to add common actions
- **Maintainable**: Centralized command definitions easy to update
- **Extensible**: Easy to add new categories or commands
