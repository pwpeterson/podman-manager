# Podman Container Manager

A comprehensive Python-based container management tool for Podman with rich terminal UI, health monitoring, intelligent project detection, and both compose and systemd quadlet support.

## Features

- **Rich Terminal Interface** - Beautiful colors, panels, and tables using Rich library
- **Intelligent Project Detection** - Automatically detects whether to use compose or quadlet mode
- **Dual Management Modes** - Support for both podman compose and systemd quadlets
- **Enhanced Prune System** - Intelligent image cleanup with usage analysis and duplicate detection
- **Health Monitoring** - Analyze service logs with pattern detection and health recommendations
- **Live Build Output** - Stream build processes in real-time
- **Smart Detection** - Automatically detects projects vs services
- **Dependency Checking** - Validates service dependencies before startup
- **Progress Tracking** - Visual feedback with spinners and elapsed time
- **YAML Validation** - Comprehensive compose file validation
- **Safety Checks** - Confirmations for destructive operations
- **AI-Powered Analysis** - Intelligent log analysis with comprehensive diagnostic data collection
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

### Monitoring and Debugging

```bash
# Analyze logs with health metrics
pm logs open-webui

# AI-powered log analysis with comprehensive diagnostics
pm logs vllm-qwen25 -ai qwen25 -v

# AI analysis with different agents
pm logs service-name -ai claude    # Use Claude Sonnet
pm logs service-name -ai gpt4      # Use GPT-4
pm logs service-name -ai glm46     # Use local GLM-4-6B

# Verbose AI analysis showing all diagnostic commands
pm logs service-name -ai qwen25 -v

# Execute interactive shell
pm exec ollama bash

# Execute specific command
pm exec service-name "ls -la /app"

# Show resource usage
pm stats --follow

# Stream real-time events
pm events --since "1h"
```

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

## AI-Powered Analysis & Health Monitoring

### AI Log Analysis

The enhanced logs command provides intelligent AI-powered analysis with comprehensive diagnostic data collection:

```bash
# Basic AI analysis
pm logs service-name -ai

# Specific AI agent with verbose diagnostics
pm logs vllm-qwen25 -ai qwen25 -v

# Comprehensive analysis with comprehensive diagnostics
pm logs service-name -ai claude -v
```

#### Available AI Agents

**Local vLLM Models:**
- `qwen25` → `vllm-qwen25` (Qwen2.5-Coder-32B-Instruct)
- `glm46` → `vllm-glm46` (GLM-4-6B-Chat)

**Cloud Models:**
- `claude` → `claude-sonnet` (Claude 3.5 Sonnet)
- `gpt4` → `gpt-4` (GPT-4)

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

#### Verbose Output Example

```bash
pm logs vllm-qwen25 -ai qwen25 -v
```

Shows detailed execution:
```
  exec: Resolving service name for target 'vllm-qwen25'
  exec: Resolved to service 'vllm-qwen25-coder-32b-instruct-awq-simple.service'
  exec: journalctl --user -u vllm-qwen25-coder-32b-instruct-awq-simple.service -n 50 --no-pager
  exec: Collected 45 lines of systemd logs
  exec: systemctl --user status vllm-qwen25-coder-32b-instruct-awq-simple.service --no-pager -l
  exec: Unit status collected (exit code: 0)
  exec: podman ps -a --format {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}
  exec: Found 3 containers
  exec: Found matching container: vllm-qwen25-coder
  exec: podman logs vllm-qwen25-coder --since 2h --timestamps --tail 100
  exec: Container logs collected (23 lines)
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

## Logging

Logs are written to `~/.local/share/podman-manager.log` with:
- **Console**: Warnings and errors only (clean output)
- **File**: Debug level for troubleshooting
- **JSON format**: Structured logs for analysis

## Examples

### Development Workflow
```bash
# Check service status
pm status

# Rebuild and restart a service
pm reinit --build my-service

# Monitor logs for issues
pm logs my-service

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

### Troubleshooting
```bash
# Analyze service health
pm logs problematic-service

# Check running processes
pm top service-name

# Execute diagnostic commands
pm exec service-name "ps aux"
pm exec service-name "df -h"

# Intelligent cleanup with analysis
pm prune
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
- **Service existence verification**
- **Clear error messages** with suggested solutions
- **Graceful failure recovery**
- **Intelligent fallback suggestions** when operations fail

## Performance Features

- **Caching**: Project and service information cached for speed
- **Parallel operations**: Where safe and beneficial
- **Resource monitoring**: Built-in stats and usage tracking
- **Efficient logging**: Structured logging with rotation
- **Modular loading**: Only load required components
- **Intelligent detection**: Minimize unnecessary operations

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
pm logs service-name
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

**Quadlet service reinstall process (when pm reinit fails):**
```bash
# Complete quadlet service reinstall process
# 1. Stop the service (if running)
systemctl --user stop local-ai-fastapi.service

# 2. Force systemd to regenerate quadlet services
# Modern Podman (5.0+): Quadlet generation is automatic during daemon-reload
systemctl --user daemon-reload

# 3. If automatic generation fails, try manual trigger
# Check if quadlet generator exists
ls -la /usr/lib/systemd/user-generators/*quadlet* 2>/dev/null || echo "No quadlet generator found"

# 4. For older Podman versions, use deprecated generate command
# podman generate systemd --new --files --name local-ai-fastapi

# 5. Start the service
systemctl --user start local-ai-fastapi.service

# Alternative: Use the pm tool after manual steps
pm reload  # Reload daemon
pm start local-ai-fastapi  # Start service
```

**Why quadlet generation might fail:**
- Missing `podman quadlet generate` command (older podman versions)
- Corrupted systemd user session (requires logout/login)
- Duplicate entries in `/etc/subuid` or `/etc/subgid` files
- Missing `XDG_RUNTIME_DIR` environment variable

**Fix systemd session issues:**
```bash
# Set runtime directory
export XDG_RUNTIME_DIR=/run/user/$(id -u)
echo 'export XDG_RUNTIME_DIR=/run/user/$(id -u)' >> ~/.bashrc

# Check for duplicate namespace mappings
cat /etc/subuid | grep $USER
cat /etc/subgid | grep $USER

# If duplicates exist, clean them (requires sudo)
sudo sed -i "/^$USER:/d" /etc/subuid
echo "$USER:100000:65536" | sudo tee -a /etc/subuid
sudo sed -i "/^$USER:/d" /etc/subgid
echo "$USER:100000:65536" | sudo tee -a /etc/subgid
```

**Enhanced prune fails:**
```bash
# Falls back to basic prune automatically
# Or use basic mode explicitly
pm prune --basic
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

# Check if includedir is enabled in main sudoers
sudo grep -E "^#includedir|^@includedir" /etc/sudoers

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

**Quadlet variable resolution issues:**
```bash
# Check if systemd can access environment variables
sudo systemctl show-environment | grep POSTGRES

# Reload systemd to pick up new environment files
sudo systemctl daemon-reload
systemctl --user daemon-reload

# Test quadlet service after environment setup
pm reinit local-ai-caddy
```

## Contributing

The tool is designed to be extensible. Key areas for enhancement:
- Additional health monitoring patterns
- More sophisticated dependency resolution
- Integration with container registries
- Advanced resource management features
- Enhanced quadlet integration
- Improved detection algorithms

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
