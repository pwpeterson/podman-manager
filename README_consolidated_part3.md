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

---

## Appendix: Migrated Documentation

This README consolidates information from the following documentation files that were previously in the `docs/` directory:

- **AI_AGENT_SYSTEM.md** - AI agent configuration and usage
- **AI_ANALYSIS_INTEGRATION.md** - AI analysis system integration
- **AI_AGENT_SELECTION_GUIDE.md** - Guide for choosing AI agents
- **BUILD_AI_ANALYSIS_INTEGRATION.md** - Build failure AI analysis
- **COMMON_ACTIONS_SYSTEM.md** - Standardized troubleshooting commands
- **CONTAINER_VALIDATION.md** - Container file validation system
- **VOLUME_COPYING_GUIDE.md** - Advanced volume management
- **STATUS_DISPLAY_ENHANCEMENT.md** - Enhanced status display
- **TROUBLESHOOTING_AI_ANALYSIS.md** - AI analysis troubleshooting
- **REFACTORING_SUMMARY.md** - Architecture refactoring details

All information from these specialized documents has been integrated into the appropriate sections above, providing a single comprehensive reference for all PM tool functionality.
