# Build AI Analysis Integration

This document describes the AI analysis integration for the PM build process, providing automatic troubleshooting and solutions for container build failures.

## Overview

The PM build system now includes automatic AI analysis for build failures, providing:

- **Automatic Detection**: Build failures trigger AI analysis automatically
- **Comprehensive Context**: Dockerfile content, build output, and error messages are analyzed
- **Actionable Solutions**: Specific commands and fixes for common build issues
- **Agent Selection**: Support for multiple AI agents (local and cloud)
- **Opt-out Option**: Can be disabled with `--no-ai` flag

## Features

### Automatic Trigger

AI analysis is automatically triggered when:
- Container build fails with non-zero exit code
- Build errors are detected in stderr/stdout
- Dockerfile syntax or dependency issues occur

### Comprehensive Analysis

The AI analysis includes:
- **Build Information**: Target, command, paths, image names
- **Error Analysis**: Detailed error messages and build output
- **Dockerfile Review**: Content analysis for syntax and best practices
- **Context Data**: Build directory, service type, and environment info

### Intelligent Prompts

Specialized prompts for container build failures covering:
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

## Usage

### Basic Build with AI Analysis

```bash
# Build with automatic AI analysis on failure
pm build vllm-delegator

# Build with specific AI agent
pm build vllm-delegator --ai-agent claude

# Build with verbose output and AI analysis
pm build vllm-delegator -v
```

### AI Agent Options

```bash
# Use local Qwen2.5 model (default)
pm build vllm-delegator --ai-agent qwen25

# Use local GLM-4 model
pm build vllm-delegator --ai-agent glm46

# Use Claude Sonnet
pm build vllm-delegator --ai-agent claude

# Use GPT-4
pm build vllm-delegator --ai-agent gpt4
```

### Disable AI Analysis

```bash
# Disable automatic AI analysis
pm build vllm-delegator --no-ai

# Traditional build without AI features
pm build vllm-delegator --no-ai -v
```

## Integration Points

### Container Builder Integration

The `ContainerBuilder` class has been enhanced with:

#### Build Context Storage
```python
def _store_build_context(self, target: str, **context) -> None:
    """Store build context for AI analysis"""
    self._build_context[target] = context
```

#### AI Analysis Trigger
```python
def _trigger_build_ai_analysis(self, target: str, build_error: str,
                               build_output: str = "", build_command: str = "") -> None:
    """Trigger AI analysis for build failures"""
```

### Command Router Integration

The command router handles:
- AI agent selection from CLI arguments
- `--no-ai` flag processing
- Temporary disabling of AI analysis when requested

### AI Analyzer Integration

Enhanced `_generate_build_failure_prompt()` method provides:
- Comprehensive build failure analysis prompts
- Dockerfile content inclusion
- Structured output with actionable recommendations
- Podman-specific command suggestions

## Build Context Data

The following context is collected for AI analysis:

```python
context_data = {
    "build_error": "Error message from stderr",
    "build_output": "Complete build output",
    "build_command": "Full podman build command",
    "dockerfile_path": "/path/to/Dockerfile",
    "build_dir": "/path/to/build/directory",
    "image_name": "localhost/service:latest",
    "service_type": "quadlet_container|podman_container"
}
```

## AI Analysis Output

The AI analysis provides structured output with:

### 1. Root Cause Analysis
- Primary reason for build failure
- Contributing factors and dependencies

### 2. Immediate Fix
- Step-by-step commands to resolve the issue
- Specific file modifications needed

### 3. Dockerfile Improvements
- Syntax corrections and optimizations
- Best practice recommendations

### 4. Build Environment
- Environment-specific issues and solutions
- Resource constraint identification

### 5. Alternative Approaches
- Different build strategies if current approach is problematic
- Base image alternatives

### 6. Prevention
- Best practices to avoid similar issues
- Monitoring and validation recommendations

## Supported Build Types

AI analysis is integrated with:

### Quadlet Container Builds
- Uses `_build_with_dockerfile()` method
- Analyzes Dockerfile.service-name files
- Provides quadlet-specific troubleshooting

### Podman Container Builds
- Uses `build_service_podman()` method
- Supports standard Dockerfile builds
- Includes registry and authentication issues

### Stack Builds
- Multi-service build analysis
- Dependency resolution issues
- Service interaction problems

## Error Detection

Build failures are detected through:

### Return Code Analysis
```python
if build_result.returncode != 0:
    # Trigger AI analysis
```

### Error Message Parsing
- stderr content analysis
- stdout error pattern detection
- Build log parsing for specific failure types

### Context-Aware Detection
- Service type consideration
- Build environment factors
- Resource availability checks

## Configuration

### Default Behavior
- AI analysis is **enabled by default** for build failures
- Uses `qwen25` (local Qwen2.5) as default agent
- Provides comprehensive analysis with Dockerfile content

### Customization Options
- Agent selection via `--ai-agent` flag
- Disable with `--no-ai` flag
- Verbose mode for detailed build context

### Agent Availability
- Automatic fallback to available agents
- Local agents preferred over cloud agents
- Graceful degradation when no agents available

## Implementation Details

### Build Context Management
```python
class ContainerBuilder:
    def __init__(self, manager):
        self.manager = manager
        self._build_context = {}  # Store build context for AI analysis
```

### Error Handling
- Graceful failure when AI analysis unavailable
- Preserves original build error information
- Non-blocking AI analysis execution

### Performance Considerations
- Build context stored only during active builds
- AI analysis runs asynchronously after build failure
- Minimal impact on successful builds

## Future Enhancements

### Planned Features
- Build success analysis and optimization suggestions
- Historical build failure pattern analysis
- Automated fix application for common issues
- Integration with build caching strategies

### Extensibility
- Support for additional build systems
- Custom prompt templates for specific services
- Integration with external build tools
- Metrics and analytics for build failures

## Troubleshooting

### Common Issues

#### AI Analysis Not Triggering
- Check if `--no-ai` flag is used
- Verify AI agent availability with `pm ai-agents`
- Ensure build actually failed (non-zero exit code)

#### Incomplete Analysis
- Check Dockerfile accessibility
- Verify build output capture
- Review verbose mode output for context collection

#### Agent Selection Issues
- Use `pm ai-agents` to check available agents
- Try different agents with `--ai-agent` flag
- Check network connectivity for cloud agents

### Debug Mode
```bash
# Enable verbose mode for detailed analysis
pm build vllm-delegator -v

# Check AI agent status
pm ai-agents

# Test with specific agent
pm build vllm-delegator --ai-agent claude -v
```

## Examples

### Dockerfile Syntax Error
```bash
$ pm build my-service
[red]❌ Build failed![/red]
[yellow]Build failed - starting AI analysis...[/yellow]

[bold green]AI Build Analysis for my-service[/bold green]

### Root Cause Analysis
The build failed due to a syntax error in the Dockerfile on line 15.
The `RUN` instruction is missing a backslash for line continuation.

### Immediate Fix
1. Edit the Dockerfile at /path/to/Dockerfile.my-service
2. Add backslash at end of line 15: `RUN apt-get update \`
3. Rebuild with: `pm build my-service`

[green]✓ AI build analysis completed[/green]
```

### Dependency Installation Failure
```bash
$ pm build python-service
[red]❌ Build failed![/red]
[yellow]Build failed - starting AI analysis...[/yellow]

[bold green]AI Build Analysis for python-service[/bold green]

### Root Cause Analysis
Python package installation failed due to missing system dependencies.
The `psycopg2` package requires PostgreSQL development headers.

### Immediate Fix
1. Add system dependencies to Dockerfile:
   ```dockerfile
   RUN apt-get update && apt-get install -y \
       libpq-dev \
       gcc \
       && rm -rf /var/lib/apt/lists/*
   ```
2. Rebuild with: `pm build python-service`

[green]✓ AI build analysis completed[/green]
```

This integration provides comprehensive build failure analysis and troubleshooting, making container builds more reliable and easier to debug.
