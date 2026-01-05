# Podman Container Manager

A comprehensive Python-based container management tool for Podman with rich terminal UI, health monitoring, intelligent project detection, AI-powered analysis, and both compose and systemd quadlet support.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Usage](#usage)
- [AI-Powered Analysis](#ai-powered-analysis)
- [Build AI Analysis](#build-ai-analysis)
- [Volume Management](#volume-management)
- [Container Validation](#container-validation)
- [Common Actions System](#common-actions-system)
- [Directory Structure](#directory-structure)
- [Migration and Compatibility](#migration-and-compatibility)
- [Examples](#examples)
- [Error Handling](#error-handling)
- [Performance Features](#performance-features)
- [Benefits of Quadlets](#benefits-of-quadlets)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)
- [Appendix: Migrated Documentation](#appendix-migrated-documentation)

## Features

- **Rich Terminal Interface** - Beautiful colors, panels, and tables using Rich library
- **Intelligent Project Detection** - Automatically detects whether to use compose or quadlet mode
- **Dual Management Modes** - Support for both podman compose and systemd quadlets
- **Enhanced Prune System** - Intelligent image cleanup with usage analysis and duplicate detection
- **Health Monitoring** - Analyze service logs with pattern detection and health recommendations
- **AI-Powered Analysis** - Intelligent log analysis with multiple AI agents (local and cloud)
- **Live Build Output** - Stream build processes in real-time with AI failure analysis
- **Smart Detection** - Automatically detects projects vs services
- **Dependency Checking** - Validates service dependencies before startup
- **Progress Tracking** - Visual feedback with spinners and elapsed time
- **YAML Validation** - Comprehensive compose file validation
- **Container Validation** - Validates .container files before installation
- **Safety Checks** - Confirmations for destructive operations
- **Volume Management** - Advanced volume copying with network dependencies
- **Common Actions System** - Standardized troubleshooting commands across all operations
- **Verbose Diagnostics** - Detailed command execution tracking for transparency

## Prerequisites

- **Podman** with compose plugin installed
- **Python 3.8+**
- **Required Python packages**: `rich`, `pyyaml`, `loguru`
- **systemd** (for quadlet mode)
- **uv** (recommended for dependency management)

## Installation

### Quick Setup (Recommended)

1. **Create pm symlink in ~/.local/bin:**
   ```bash
   # Ensure the script has proper shebang and is executable
   sed -n '1p' /home/pwp/srv/apps/podman_manager/pm
   chmod +x /home/pwp/srv/apps/podman_manager/pm

   # Create the symlink
   mkdir -p ~/.local/bin
   ln -sf /home/pwp/srv/apps/podman_manager/pm ~/.local/bin/pm

   # Ensure ~/.local/bin is on your PATH
   echo "$PATH" | tr ':' '\n' | grep -x "$HOME/.local/bin" || \
   { echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc; source ~/.bashrc; }

   # Test the setup
   which pm
   readlink -f ~/.local/bin/pm
   pm --help
   ```

2. **Configure passwordless sudo for environment management:**
   ```bash
   # Create sudoers configuration file
   sudo visudo -f /etc/sudoers.d/user_pwp_rules
   ```

   Add this content to `/etc/sudoers.d/user_pwp_rules`:
   ```bash
   # Allow pwp user to run pm command and specific environment commands without password
   # This enables pm install to create system-wide environment files

   # Allow running pm command with sudo
   pwp ALL=(root) NOPASSWD: /home/pwp/.local/bin/pm

   # Allow specific environment management commands that pm uses internally
   pwp ALL=(root) NOPASSWD: /bin/mkdir -p /etc/environment.d
   pwp ALL=(root) NOPASSWD: /bin/cp /tmp/00env.conf /etc/environment.d/00env.conf
   pwp ALL=(root) NOPASSWD: /bin/chmod 644 /etc/environment.d/00env.conf
   ```

   Verify the syntax:
   ```bash
   sudo visudo -c -f /etc/sudoers.d/user_pwp_rules
   ```

3. **Test the complete setup:**
   ```bash
   # Test regular pm command
   pm status

   # Test sudo pm command (should not prompt for password)
   sudo pm --help

   # Test environment file creation (creates /etc/environment.d/00env.conf)
   pm install neo4j -v
   ```

#### Benefits of This Setup

**Symlink Benefits:**
- Clean command access: `pm` works from anywhere
- Easy updates: Just update the source, symlink automatically points to latest
- No system-wide installation required
- Follows standard Unix conventions

**Sudoers Configuration Benefits:**
- **Automatic Environment Management**: `pm install` automatically creates system-wide environment files
- **No Password Prompts**: Seamless operation without interrupting workflows
- **Security**: Only specific commands are allowed, not full sudo access
- **Quadlet Support**: Enables systemd services to access environment variables like `${POSTGRES_PASSWORD}`

**Environment Variable Integration:**
The sudoers setup enables the `pm install` command to automatically:
1. Filter `.env` files (removes comments and empty lines)
2. Create `/etc/environment.d/00env.conf` with system-wide environment variables
3. Make variables available to systemd quadlet services
4. Resolve issues like "Unit local-ai-postgres.service not found" caused by unresolved variables

### Modern Installation (Alternative)

1. **Install dependencies using uv:**
   ```bash
   uv add rich pyyaml loguru
   ```

2. **Use the smart wrapper script:**
   ```bash
   # Make executable
   chmod +x pm

   # Add to PATH or create symlink
   sudo ln -s $(pwd)/pm /usr/local/bin/pm
   ```

### Legacy Installation

1. **Copy the script to system location:**
   ```bash
   sudo cp podman-manager.py /usr/local/bin/podman-manager.py
   ```

2. **Create wrapper script:**
   ```bash
   sudo tee /usr/local/bin/podman-manager > /dev/null << 'EOF'
   #!/bin/bash
   set -euo pipefail

   VENV_PATH="/home/$(whoami)/.venv"
   SCRIPT_PATH="/usr/local/bin/podman-manager.py"
   USER_HOME="/home/$(whoami)"

   [[ -d "$VENV_PATH" ]] || { echo "ERROR: Virtual environment not found" >&2; exit 1; }
   [[ -f "$SCRIPT_PATH" ]] || { echo "ERROR: Script not found" >&2; exit 1; }

   source "$VENV_PATH/bin/activate"
   cd "$USER_HOME"
   exec python3 "$SCRIPT_PATH" "$@"
   EOF
   ```

3. **Make executable and create alias:**
   ```bash
   sudo chmod +x /usr/local/bin/podman-manager
   sudo ln -sf /usr/local/bin/podman-manager /usr/local/bin/pm
   ```

## Architecture

### Modular Design

The tool features a modular architecture with clean separation of concerns:

```
Root Directory:
├── config.py          # Logging & Rich console setup
├── manager.py         # Core business logic
├── container_ops.py   # Container operations (compose mode)
├── quadlet_ops.py     # Quadlet operations (systemd mode)
├── quadlet_manager.py # Quadlet service management
├── display.py         # Rich display components
├── project_detector.py # Intelligent project type detection
├── main.py           # New modular entry point
├── podman-manager.py # Original monolithic script
└── pm               # Smart compatibility wrapper
```

### Intelligent Mode Detection

The `pm` command features automatic project type detection:

- **Default mode**: `auto` (intelligent detection)
- **Detection logic**:
  1. Known vLLM services → `quadlet`
  2. Systemd service exists → `quadlet`
  3. Found in compose files → `compose`
  4. Fallback to compose if compose files available
  5. Final fallback to quadlet

## Configuration

Set the compose directory environment variable (optional):
```bash
export PODMAN_COMPOSE_DIR="/path/to/your/compose/files"
# Default: ~/srv/local-ai-packaged
```

## Usage

### Mode Selection

```bash
# Automatic mode detection (default)
pm list vllm-qwen25     # → Uses quadlet mode
pm restart postgres     # → Uses compose mode

# Manual mode override
pm --mode compose restart vllm-qwen25  # Force compose mode
pm --mode quadlet start postgres       # Force quadlet mode

# Debug detection logic
pm --debug-detection list vllm-qwen25

# List available targets by type
pm targets
```

### Basic Commands

```bash
# Show project and service overview
pm status

# Display container status table
pm ps

# Show detailed help
pm help
```

### Container Lifecycle

#### Compose Mode
```bash
# Recreate service with fresh start
pm reinit ollama

# Rebuild and recreate
pm reinit --build service-name

# Restart entire project
pm restart vllm-models

# Stop services gracefully
pm stop project-name

# Remove containers (preserves volumes)
pm remove service-name
```

#### Quadlet Mode (systemd)
```bash
# Start all vLLM services
pm start stack

# Stop specific service
pm stop qwen25-coder

# Restart proxy service
pm restart proxy

# Enable stack to start at boot
pm enable stack

# Disable delegator from starting at boot
pm disable delegator

# Show detailed service status
pm status proxy

# Follow service logs
pm logs delegator --follow

# Update images and restart service
pm update qwen25-coder

# Check/enable auto-update timer
pm auto-update

# Reload systemd daemon
pm reload
```

### Build and Images

```bash
# Build without cache
pm build --no-cache service

# Build with AI analysis on failure (default)
pm build service

# Build with specific AI agent
pm build service --ai-agent claude

# Build without AI analysis
pm build service --no-ai

# Pull latest images
pm pull vllm-models

# List all images
pm images --all
```

### Enhanced Prune System

The enhanced prune functionality provides intelligent image cleanup based on container usage analysis:

```bash
# Intelligent cleanup with full analysis (default)
pm prune

# Quick cleanup (dangling images and containers only)
pm prune --quick

# Basic cleanup without analysis (original behavior)
pm prune --basic
```

#### Enhanced Prune Workflow

When you run `pm prune`, the system follows this workflow:

1. **System Analysis**
   - Lists all running and stopped containers with their image IDs
   - Catalogs all images with size and metadata
   - Identifies which images are referenced by containers
   - Finds dangling (untagged) images
   - Detects potential duplicate images

2. **Analysis Summary**
   - Shows total images vs. images in use
   - Displays potential space savings
   - Categorizes cleanup opportunities

3. **Safe Cleanup Execution**
   - Confirms large removals with user
   - Removes dangling images first
   - Removes duplicate images (keeping one per group)
   - Shows before/after disk usage

#### What Gets Removed

**Always Safe to Remove:**
- **Dangling images**: Untagged images (`<none>:<none>`) not used by any container
- **Unused containers**: Stopped containers not needed

**Removed with Analysis:**
- **Duplicate images**: Multiple tags pointing to same image content
  - Example: `localhost/vllm-delegator-mcp:latest` and `localhost/vllm_vllm-delegator-mcp:latest` with same image ID
  - Keeps the first tag, removes additional tags

**Never Removed:**
- Images used by running containers
- Images used by stopped containers you might restart
- Images explicitly tagged and in use

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

✅ vllm-qwen25 (local-vllm) - Available
   Local Qwen2.5-Coder model via vLLM proxy
   Endpoint: http://localhost:8002

❌ vllm-glm46 (local-vllm) - Unavailable
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
✓ View podman logs    : pm logs vllm-qwen25
✓ Diagnose issues     : pm diag vllm-qwen25
✓ Restart service     : pm restart vllm-qwen25
✓ Reinitialize        : pm reinit vllm-qwen25
✓ service logs        : journalctl --user -u vllm-qwen25.service -n 100
✓ service status      : systemctl --user status vllm-qwen25.service --no-pager -l
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

## Directory Structure

### Compose Mode
The tool expects compose files in the following format:
```
~/srv/local-ai-packaged/
├── podman-compose.yml              # Default project
├── podman-compose-vllm.yml         # VLLM project
├── podman-compose-supabase.yml     # Supabase project
└── podman-compose-web-apps.yml     # Web apps project
```

### Quadlet Mode
Systemd quadlet services are managed via systemctl:
- `qwen25-coder` → `vllm-qwen25-coder-32b-instruct-awq-simple.service`
- `proxy` → `vllm-proxy-working.service`
- `delegator` → `vllm-delegator-mcp-simple.service`
- `stack` → `vllm-stack.target` (manages all services together)

## Target Types

- **PROJECT**: Operates on all services in a compose file (e.g., `vllm-models`)
- **SERVICE**: Operates on a specific service (e.g., `open-webui`)
- **QUADLET**: Systemd service or target (e.g., `vllm-stack`)

The tool automatically detects whether your target is a project, service, or quadlet.

## Migration and Compatibility

### Backward Compatibility

The refactoring maintains **100% backward compatibility**. All existing bash aliases and scripts will continue to work without any changes.

#### Compatibility Wrapper
A smart wrapper script `pm` automatically detects your environment:
- **With uv available**: Uses the new refactored modular version (`main.py`)
- **Without uv**: Falls back to the original monolithic script (`podman-manager.py`)

#### Available Entry Points
1. **`./pm`** - Smart wrapper (recommended)
2. **`uv run python main.py`** - New refactored version
3. **`./podman-manager.py`** - Original monolithic version
4. **`python3 podman-manager.py`** - Original version (fallback)

### Migration Benefits

**Performance:**
- **Faster startup**: Modular loading only imports what's needed
- **Better caching**: uv provides faster dependency resolution

**Development:**
- **Easier maintenance**: Code is organized into logical modules
- **Better testing**: Individual components can be tested separately
- **Extensibility**: Easy to add new features without touching core logic

### Refactoring Summary

**Before Refactoring:**
- **Single file**: 1,386 lines
- **Massive main() function**: 850+ lines handling all command routing
- **Mixed responsibilities**: CLI parsing, command execution, and business logic all in one file

**After Refactoring:**
- **Main file**: 1,386 lines → 73 lines (95% reduction)
- **Modular structure**: Distributed across focused modules
- **Clear separation**: Each module has a single responsibility

## Examples

### Development Workflow
```bash
# Check service status
pm status

# Rebuild and restart a service
pm reinit --build my-service

# Monitor logs for issues with AI analysis
pm logs my-service -ai qwen25

# Check resource usage
pm stats
```

### Quadlet Workflow
```bash
# Start all vLLM services
pm start stack

# Check service status
pm list

# Follow logs for Qwen2.5 Coder
pm logs qwen25-coder --follow

# Update images and restart
pm update proxy

# Enable services to start at boot
pm enable stack
```

### AI-Powered Troubleshooting
```bash
# Analyze service health with AI
pm logs problematic-service -ai claude -v

# Build with AI failure analysis
pm build my-service --ai-agent qwen25

# Automatic AI analysis on reinit failure
pm reinit service-name -v
```

### Volume Management
```bash
# Copy volumes and networks between stacks
pm copy-volumes source-stack target-stack

# List volumes for a specific stack
pm list-volumes vllm-stack

# Clean up orphaned volumes
pm cleanup-volumes local-ai-stack
```

### Maintenance
```bash
# Update all images
pm pull project-name

# Intelligent system cleanup with analysis
pm prune

# Check disk usage
pm system-df

# Remove orphaned containers
pm remove-orphans project-name
```

## Error Handling

The tool provides comprehensive error handling:
- **Dependency validation** before service startup
- **YAML syntax checking** for compose files
- **Container file validation** before installation
- **Service existence verification**
- **Clear error messages** with suggested solutions
- **Graceful failure recovery**
- **Intelligent fallback suggestions** when operations fail
- **AI-powered failure analysis** for complex issues

## Performance Features

- **Caching**: Project and service information cached for speed
- **Parallel operations**: Where safe and beneficial
- **Resource monitoring**: Built-in stats and usage tracking
- **Efficient logging**: Structured logging with rotation
- **Modular loading**: Only load required components
- **Intelligent detection**: Minimize unnecessary operations
- **AI agent optimization**: Local agents preferred for speed and privacy

## Benefits of Quadlets

1. **Native systemd integration**: Services managed like any other system service
2. **Boot-time startup**: Can enable services to start automatically
3. **Better logging**: Integrated with journalctl
4. **Dependency management**: systemd handles service dependencies
5. **Auto-updates**: Support for automatic image updates
6. **Resource management**: systemd resource controls

## Troubleshooting

### Common Issues

**Command not found:**
```bash
# Check if wrapper script exists and is executable
ls -la /usr/local/bin/pm
# Ensure virtual environment is activated
source ~/.venv/bin/activate
```

**Permission errors:**
```bash
# Ensure user is in podman group
sudo usermod -aG podman $USER
newgrp podman
```

**Compose file not found:**
```bash
# Set correct directory
export PODMAN_COMPOSE_DIR="/path/to/compose/files"
# Or check default location
ls ~/srv/local-ai-packaged/
```

**Service dependencies missing:**
```bash
# Check dependency status first
pm logs service-name -ai qwen25
# Start dependencies manually
pm reinit dependency-service
```

**Quadlet services not found:**
```bash
# Reload systemd daemon
pm reload
# Check systemd user services
systemctl --user list-units --type=service | grep vllm
```

**AI Agent Issues:**
```bash
# Check agent status
pm ai-agents

# For local vLLM agents - check if service is running
pm status vllm-qwen25
pm logs vllm-qwen25

# Start the service if needed
pm start vllm-qwen25

# For cloud agents - check environment variables
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY
```

**Symlink setup issues:**
```bash
# Check if symlink exists and points to correct location
ls -la ~/.local/bin/pm
readlink -f ~/.local/bin/pm

# Recreate symlink if needed
ln -sf /home/pwp/srv/apps/podman_manager/pm ~/.local/bin/pm

# Check PATH includes ~/.local/bin
echo $PATH | tr ':' '\n' | grep ~/.local/bin
```

**Sudoers configuration issues:**
```bash
# Test if sudoers rules are working
sudo -l | grep pm

# Verify sudoers file syntax
sudo visudo -c -f /etc/sudoers.d/user_pwp_rules

# Test specific commands
sudo mkdir -p /etc/environment.d  # Should not prompt for password
```

**Environment file creation issues:**
```bash
# Check if .env file exists
ls -la /home/pwp/srv/local-ai-packaged/.env

# Manually verify environment file creation
pm install neo4j -v
ls -la /etc/environment.d/00env.conf

# Check file contents
head -5 /etc/environment.d/00env.conf
```

**Enhanced prune fails:**
```bash
# Falls back to basic prune automatically
# Or use basic mode explicitly
pm prune --basic
```

**Volume copying issues:**
```bash
# Ensure podman has access to volume data
sudo chown -R $(id -u):$(id -g) ~/.local/share/containers/storage/volumes/

# Use verbose mode to see detailed execution
pm copy-volumes source-stack target-stack -v

# For large volumes, consider manual copying if timeout occurs
```

### Debug Mode
```bash
# Enable verbose mode for detailed analysis
pm build vllm-delegator -v
pm logs service-name -ai qwen25 -v
pm copy-volumes source target -v

# Check AI agent status
pm ai-agents

# Test with specific agent
pm logs service-name -ai claude -v
```

## Contributing

The tool is designed to be extensible. Key areas for enhancement:
- Additional health monitoring patterns
- More sophisticated dependency resolution
- Integration with container registries
- Advanced resource management features
- Enhanced quadlet integration
- Improved detection algorithms
- Additional AI agents and analysis types
- Enhanced volume management features
- Better container validation rules

### Development Structure

The modular architecture makes it easy to contribute:

```
├── cli/                    # Command-line interface
│   ├── command_router.py   # Command routing logic
│   ├── help_formatter.py   # Help display
│   └── parser.py          # Argument parsing
├── managers/              # Service management
│   ├── quadlet_manager.py # Quadlet operations
│   ├── reinit_manager.py  # Reinit operations
│   └── stack_manager.py   # Stack management
├── operations/            # Core operations
│   ├── common_actions.py  # Standardized actions
│   ├── container_builder.py # Build operations
│   ├── volume_manager.py  # Volume operations
│   └── installer.py       # Installation logic
├── ai_analyzer/           # AI analysis system
│   ├── analyzer.py        # Core AI analysis
│   ├── display_formatters.py # AI result display
│   └── prompt_generators.py # AI prompts
└── utils/                 # Utilities
    └── supabase_fixer.py  # Environment utilities
```

## License

This tool is provided as-is for container management workflows. Modify and distribute according to your needs.

## Support

For issues and feature requests:
1. Check the logs: `~/.local/share/podman-manager.log`
2. Run with debug logging: Set log level to DEBUG in script
3. Verify prerequisites: Podman, compose plugin, Python packages
4. Test with simple commands: `pm status`, `pm ps`
5. Use debug detection: `pm --debug-detection <command>`
6. Check available targets: `pm targets`
7. Check AI agents: `pm ai-agents`
8. Use verbose mode: Add `-v` to see detailed execution
9. Test AI analysis: `pm logs service-name -ai qwen25 -v`

## Documentation

### Complete Documentation

For comprehensive technical documentation, architecture details, and advanced topics, see the [`docs/`](docs/) directory:

- **[📚 Documentation Index](docs/README.md)** - Complete guide to all documentation
- **[🏗️ Architecture Enhancements](docs/ARCHITECTURE_ENHANCEMENTS.md)** - Code consolidation and system improvements
- **[🧠 vLLM System](docs/VLLM_SYSTEM.md)** - Complete vLLM model management
- **[🤖 AI Analysis System](docs/AI_ANALYSIS_SYSTEM.md)** - AI-powered troubleshooting
- **[🗄️ Supabase Stack](docs/SUPABASE_STACK.md)** - Supabase service orchestration
- **[🔧 System Operations](docs/SYSTEM_OPERATIONS.md)** - Operational improvements and fixes

### Quick Reference

This README provides essential usage information and getting started guides. For detailed technical information, troubleshooting guides, and implementation details, refer to the comprehensive documentation in the [`docs/`](docs/) directory.

### Legacy Documentation

Previous documentation files have been consolidated and archived in [`docs/archive/`](docs/archive/) for historical reference.
