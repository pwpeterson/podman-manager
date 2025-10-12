# Podman Container Manager

A comprehensive Python-based container management tool for Podman with rich terminal UI, health monitoring, and compose file integration.

## Features

- **Rich Terminal Interface** - Beautiful colors, panels, and tables using Rich library
- **Health Monitoring** - Analyze service logs with pattern detection and health recommendations
- **Live Build Output** - Stream build processes in real-time
- **Smart Detection** - Automatically detects projects vs services
- **Dependency Checking** - Validates service dependencies before startup
- **Progress Tracking** - Visual feedback with spinners and elapsed time
- **YAML Validation** - Comprehensive compose file validation
- **Safety Checks** - Confirmations for destructive operations

## Prerequisites

- **Podman** with compose plugin installed
- **Python 3.8+**
- **Required Python packages**: `rich`, `pyyaml`, `loguru`

## Installation

1. **Install dependencies using uv (recommended):**
   ```bash
   uv add rich pyyaml loguru
   ```

2. **Copy the script to system location:**
   ```bash
   sudo cp podman-manager.py /usr/local/bin/podman-manager.py
   ```

3. **Create wrapper script:**
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

4. **Make executable and create alias:**
   ```bash
   sudo chmod +x /usr/local/bin/podman-manager
   sudo ln -sf /usr/local/bin/podman-manager /usr/local/bin/pm
   ```

## Configuration

Set the compose directory environment variable (optional):
```bash
export PODMAN_COMPOSE_DIR="/path/to/your/compose/files"
# Default: ~/srv/local-ai-packaged
```

## Usage

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

### Build and Images

```bash
# Build without cache
pm build --no-cache service

# Pull latest images
pm pull vllm-models

# List all images
pm images --all

# Clean up unused resources
pm prune --all --volumes
```

### Monitoring and Debugging

```bash
# Analyze logs with health metrics
pm logs open-webui

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

The tool expects compose files in the following format:
```
~/srv/local-ai-packaged/
├── podman-compose.yml              # Default project
├── podman-compose-vllm.yml         # VLLM project
├── podman-compose-supabase.yml     # Supabase project
└── podman-compose-web-apps.yml     # Web apps project
```

## Target Types

- **PROJECT**: Operates on all services in a compose file (e.g., `vllm-models`)
- **SERVICE**: Operates on a specific service (e.g., `open-webui`)

The tool automatically detects whether your target is a project or service.

## Health Monitoring

The logs command provides intelligent health analysis:

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

### Troubleshooting
```bash
# Analyze service health
pm logs problematic-service

# Check running processes
pm top service-name

# Execute diagnostic commands
pm exec service-name "ps aux"
pm exec service-name "df -h"

# Clean up resources
pm prune --all --volumes
```

### Maintenance
```bash
# Update all images
pm pull project-name

# Clean system
pm prune --all --volumes

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

## Performance Features

- **Caching**: Project and service information cached for speed
- **Parallel operations**: Where safe and beneficial
- **Resource monitoring**: Built-in stats and usage tracking
- **Efficient logging**: Structured logging with rotation

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

## Contributing

The tool is designed to be extensible. Key areas for enhancement:
- Additional health monitoring patterns
- More sophisticated dependency resolution
- Integration with container registries
- Advanced resource management features

## License

This tool is provided as-is for container management workflows. Modify and distribute according to your needs.

## Support

For issues and feature requests:
1. Check the logs: `~/.local/share/podman-manager.log`
2. Run with debug logging: Set log level to DEBUG in script
3. Verify prerequisites: Podman, compose plugin, Python packages
4. Test with simple commands: `pm status`, `pm ps`
