# Unified AI Analysis System Integration Guide

This document explains how to integrate AI analysis into any PM command using the new unified `ai_analyze()` method.

## Overview

The new `ai_analyzer.py` module provides a single, unified method `ai_analyze()` that can handle different types of analysis with custom prompts. This replaces the previous approach of having separate methods for each command type.

## Key Benefits

1. **Single Method**: One `ai_analyze()` method handles all analysis types
2. **Custom Prompts**: Each analysis type gets a tailored prompt for better results
3. **Consistent Display**: All analysis results use the same formatting and menu system
4. **Easy Extension**: Adding AI analysis to new commands is straightforward
5. **Agent Support**: Works with the existing AI agent selection system

## How It Works

### Core Method Signature

```python
ai_analyzer.ai_analyze(
    analysis_type: str,          # Type of analysis (e.g., 'logs', 'reinit_failure', 'status')
    target: str,                 # Target service/stack name
    context_data: Dict[str, Any] = None,  # Additional context data
    ai_agent: str = None,        # Specific AI agent to use
    verbose: bool = False        # Enable verbose output
)
```

### Supported Analysis Types

- **`logs`**: General log analysis for troubleshooting
- **`reinit_failure`**: Specific analysis for reinit operation failures
- **`status`**: Service status analysis and health assessment
- **`build_failure`**: Build error analysis and resolution
- **`performance`**: Performance bottleneck analysis
- **`security`**: Security assessment and hardening recommendations

## Integration Examples

### Example 1: Adding AI Analysis to Status Command

```python
# In your command handler
from ai_analyzer import ai_analyzer

def status_command(target: str, ai_analysis: bool = False, ai_agent: str = None):
    # Show regular status first
    show_service_status(target)

    # Add AI analysis if requested
    if ai_analysis:
        # Initialize ai_analyzer with manager if needed
        if ai_analyzer.manager is None:
            ai_analyzer.manager = self.manager

        # Run AI analysis
        ai_analyzer.ai_analyze(
            analysis_type="status",
            target=target,
            context_data={},  # Status analysis doesn't need extra context
            ai_agent=ai_agent,
            verbose=False
        )
```

### Example 2: Adding AI Analysis to Build Command

```python
def build_command(target: str, ai_analysis: bool = False, ai_agent: str = None):
    # Attempt the build
    build_result = build_service(target)

    # If build failed and AI analysis requested
    if not build_result and ai_analysis:
        if ai_analyzer.manager is None:
            ai_analyzer.manager = self.manager

        # Prepare build failure context
        context_data = {
            "build_command": f"podman build -t {target} .",
            "build_error": "Build failed with errors",
            "build_output": get_build_output()  # Your method to get build logs
        }

        ai_analyzer.ai_analyze(
            analysis_type="build_failure",
            target=target,
            context_data=context_data,
            ai_agent=ai_agent,
            verbose=True
        )
```

### Example 3: Adding AI Analysis to Performance Command

```python
def performance_command(target: str, ai_agent: str = None):
    if ai_analyzer.manager is None:
        ai_analyzer.manager = self.manager

    ai_analyzer.ai_analyze(
        analysis_type="performance",
        target=target,
        context_data={},  # Performance analysis collects its own metrics
        ai_agent=ai_agent,
        verbose=False
    )
```

## CLI Integration Pattern

To add AI analysis to any command, follow this pattern:

### 1. Add CLI Parameter

```python
# In cli/parser.py
parser.add_argument('--ai', '-ai', action='store_true',
                   help='Run AI analysis after the operation')
parser.add_argument('--ai-agent', type=str,
                   help='Specific AI agent to use for analysis')
```

### 2. Update Command Handler

```python
# In your command handler
def handle_command(args):
    # Execute the main command
    result = execute_main_operation(args.target)

    # Add AI analysis if requested
    if args.ai:
        if ai_analyzer.manager is None:
            ai_analyzer.manager = self.manager

        # Determine analysis type based on command
        analysis_type = determine_analysis_type(args.command)

        # Prepare context data specific to this command
        context_data = prepare_context_data(args, result)

        ai_analyzer.ai_analyze(
            analysis_type=analysis_type,
            target=args.target,
            context_data=context_data,
            ai_agent=args.ai_agent,
            verbose=args.verbose
        )
```

## Adding New Analysis Types

To add a new analysis type:

### 1. Add Context Data Collection

In `ai_analyzer.py`, add a new case to `_collect_context_data()`:

```python
elif analysis_type == "my_new_analysis":
    # Collect specific data for this analysis type
    data.update(self._collect_my_analysis_data(target, context_data))
```

### 2. Add Prompt Generation

Add a new prompt generator method:

```python
def _generate_my_analysis_prompt(self, base_context: str, data: Dict[str, Any]) -> str:
    """Generate prompt for my custom analysis"""
    return f"""{base_context}
Analyze the following for my specific use case:

=== CUSTOM DATA ===
{data.get('custom_field', 'No data')}
=== END DATA ===

Provide:
1. **Analysis**: What does this data tell us?
2. **Recommendations**: What should be done?
"""
```

### 3. Update Prompt Router

Add the new case to `_generate_prompt()`:

```python
elif analysis_type == "my_new_analysis":
    return self._generate_my_analysis_prompt(base_context, data)
```

## Current Integrations

The following commands already use the unified AI analysis system:

- **`pm reinit`**: Automatically runs `reinit_failure` analysis on failure
- **`pm logs -ai`**: Runs `logs` analysis on service logs

## Migration from Old System

The old system with separate methods like `ai_analyze_reinit_failure()` has been replaced. All existing integrations have been updated to use the new unified system while maintaining backward compatibility.

## Best Practices

1. **Initialize Manager**: Always ensure `ai_analyzer.manager` is set before calling `ai_analyze()`
2. **Use Appropriate Types**: Choose the most specific analysis type for better prompts
3. **Provide Context**: Include relevant context data for more accurate analysis
4. **Handle Failures**: The method handles its own error display, but check for None returns
5. **Respect Verbose Mode**: Pass through the verbose flag for consistent behavior

## Future Enhancements

The unified system makes it easy to add:

- New analysis types for specific scenarios
- Enhanced context data collection
- Improved prompt engineering
- Better result formatting and actions
- Integration with more AI agents

This architecture provides a solid foundation for expanding AI analysis capabilities across all PM commands.
