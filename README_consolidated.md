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
- [Volume Management](#volume-management)
- [Container Validation](#container-validation)
- [Common Actions System](#common-actions-system)
- [Build AI Analysis](#build-ai-analysis)
- [Directory Structure](#directory-structure)
- [Migration and Compatibility](#migration-and-compatibility)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)
- [Contributing](#contributing)

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
