# AI Analysis System Documentation

## Overview

This document consolidates all AI analysis functionality in the Podman Manager, including agent selection enhancements, analysis improvements, and interactive keyboard shortcuts.

## AI Agent Selection Enhancement

### Overview

Enhanced the AI diagnostic analysis system to provide clear visibility into which AI agents are being tried and their availability status during the agent selection process.

### Changes Made

#### 1. Enhanced AI Analyzer (`ai_analyzer/analyzer.py`)

- **Modified `_analyze_with_fallback` method**: Now shows a clear "🤖 AI Agent Selection:" section with status indicators
- **Added `_find_fallback_agent_with_logging` method**: Provides detailed logging of each agent being tried
- **Enhanced fallback logic**: Uses configured fallback order from `ai_agents_config.json` instead of hardcoded values
- **Added `_get_unavailability_reason` method**: Provides specific reasons why agents are unavailable

#### 2. Enhanced AI Agent Manager (`ai_system/ai_agents.py`)

- **Modified `analyze_with_agent` method**: Added agent selection visibility
- **Added `_find_available_fallback_agent` method**: Provides detailed logging for agent fallback process
- **Added `_get_agent_unavailability_reason` method**: Provides specific diagnostic information for failed agents

#### 3. Fixed Configuration (`ai_agents_config.json`)

- **Fixed malformed endpoints**: Changed `http://localhost:8002:8002` to `http://localhost:8002` for local vLLM agents
- **Ensures proper fallback order**: Local vLLM agents are now properly checked before cloud agents

### User Experience Improvements

#### Before Enhancement
```
Using AI agent: GLM-4.1-9B-Thinking
```

#### After Enhancement
```
🤖 AI Agent Selection:
  ✅ GLM-4.1-9B-Thinking - Selected for analysis
```

#### Fallback Scenario
```
🤖 AI Agent Selection:
  ❌ GLM-4.1-9B-Thinking - Connection refused (service not running) (default)
  ✅ GLM-4-9B-Chat - Available (fallback)
  ✅ GLM-4-9B-Chat - Selected for analysis
```

#### Detailed Error Information
```
🤖 AI Agent Selection:
  ❌ GLM-4.1-9B-Thinking - Connection refused (service not running) (default)
  ❌ GLM-4-9B-Chat - Connection timeout
  ❌ claude-sonnet-4-5 - Missing ANTHROPIC_API_KEY environment variable
  ❌ GPT-4 - Missing OPENAI_API_KEY environment variable
  Checking all configured agents...
  ❌ No available AI agents found
No available AI agents found
```

### Key Features

1. **Clear Status Indicators**:
   - ✅ Available agents
   - ❌ Unavailable agents

2. **Detailed Context**:
   - Shows if agent was requested, default, or fallback
   - Indicates the selection process step-by-step

3. **Smart Fallback Logic**:
   - Uses configured fallback order from `ai_agents_config.json`
   - Falls back to any available agent if configured ones fail
   - Shows each step of the fallback process

4. **Configuration-Driven**:
   - Respects the `fallback_order` in `ai_agents_config.json`
   - Uses all configured agents if no fallback order specified
   - Graceful degradation to hardcoded fallback if config fails

5. **Detailed Error Reporting**:
   - Shows specific connection errors ("Connection refused", "Connection timeout")
   - Identifies missing API keys for cloud services
   - Provides actionable troubleshooting information

### Benefits

- **Transparency**: Users can see exactly which AI agents are being tried
- **Debugging**: Easy to identify why a specific agent wasn't used with detailed error messages
- **Confidence**: Clear indication of which agent is actually performing the analysis
- **Troubleshooting**: Immediate feedback on specific issues (network problems, missing API keys, etc.)
- **Proper Prioritization**: Fixed configuration ensures local vLLM agents are checked before cloud agents
- **Actionable Feedback**: Error messages help users understand what needs to be fixed

## AI Analysis Enhancements

### Overview
Enhanced the AI analysis process in the refactored reinit system to provide better visibility into which AI agents are being used and clear feedback when agents are not available.

### Enhancements Made

#### 1. AI Agent Information Display
**Before:**
- No indication of which AI agent was being used
- Generic error messages when AI analysis failed
- Users couldn't tell if AI agents were configured or available

**After:**
- Clear display of which AI agent is being used: `Using AI agent: Claude-3.5-Sonnet (openai_api)`
- Fallback messages when no agent is configured: `No AI agent configured`
- Graceful handling when agent detection fails: `AI agent detection failed`

#### 2. Enhanced Error Handling
**Improved error categories:**

##### Import Errors (AI Module Not Available)
```
❌ AI analyzer module not available: ai_analyzer module not found
Install ai_analyzer module to enable AI analysis
```

##### Configuration Issues
```
Using AI agent: No AI agent configured
⚠️ AI analysis completed but provided no insights
```

##### Runtime Failures
```
⚠️ AI analysis failed: [specific error message]
```

#### 3. Consistent Messaging Across All Analysis Types

##### Pre-reinit Analysis
```
🤖 Pre-reinit AI Analysis
Analyzing potential issues before reinit...
Using AI agent: Claude-3.5-Sonnet (openai_api)
```

##### Failure Analysis
```
🔍 Enhanced Failure Analysis
Analyzing reinit failure with full context...
Using AI agent: Claude-3.5-Sonnet (openai_api)
```

##### Optimization Suggestions
```
💡 Optimization Suggestions
Using AI agent: Claude-3.5-Sonnet (openai_api)
```

##### vLLM Failure Analysis
```
[container] is running but is generating error messages.
Starting AI failure analysis...
Using AI agent: Claude-3.5-Sonnet (openai_api)
```

### Implementation Details

#### New Method: `_get_ai_agent_info()`
Added to both `ReinitAIAnalyzer` and `VLLMReinitFlow` classes:

```python
def _get_ai_agent_info(self, analyzer) -> str:
    """Get information about which AI agent is being used."""
    try:
        # Try to get the current AI agent from the analyzer
        if hasattr(analyzer, 'current_agent') and analyzer.current_agent:
            agent_name = analyzer.current_agent.get('name', 'Unknown')
            agent_type = analyzer.current_agent.get('agent_type', 'Unknown')
            return f"{agent_name} ({agent_type})"
        elif hasattr(analyzer, 'ai_agents') and analyzer.ai_agents:
            # Get the first available agent
            first_agent = next(iter(analyzer.ai_agents.values()), {})
            agent_name = first_agent.get('name', 'Unknown')
            agent_type = first_agent.get('agent_type', 'Unknown')
            return f"{agent_name} ({agent_type})"
        else:
            return "No AI agent configured"
    except Exception:
        return "AI agent detection failed"
```

#### Enhanced Exception Handling
- **ImportError**: Specifically catches when ai_analyzer module is not installed
- **Generic Exception**: Catches runtime errors with specific error messages
- **Result Validation**: Checks if AI analysis returns meaningful results

### User Experience Improvements

#### 1. **Transparency**
Users now know exactly which AI agent is being used for analysis, helping with:
- Debugging AI-related issues
- Understanding analysis quality expectations
- Troubleshooting configuration problems

#### 2. **Clear Error Messages**
Instead of generic failures, users get specific guidance:
- Module installation instructions
- Configuration status information
- Actionable error descriptions

#### 3. **Consistent Formatting**
All AI analysis operations now follow the same messaging pattern:
- Clear section headers with emojis
- Consistent color coding (cyan for agent info, red for errors, yellow for warnings)
- Structured information display

## Interactive Analysis Keyboard Shortcuts

### Overview

The Interactive AI Analysis system has been updated to use keyboard shortcuts instead of text commands for a more intuitive user experience. Additionally, the follow-up analysis now displays the resolved service name instead of the raw target name.

### New Keyboard Shortcuts

#### Unix/Linux/macOS Systems (with termios support)

- **^enter**: Submit your question for AI analysis
- **^z**: Exit the interactive analysis session
- **Enter**: Create a new line in your question
- **Backspace**: Delete the last character on the current line
- **Ctrl+C**: Interrupt/cancel the session

#### Windows Systems (fallback mode)

- **Double Enter**: Submit your question (press Enter twice in a row)
- **Type 'quit', 'exit', or 'q'**: Exit the interactive analysis session
- **Enter**: Create a new line in your question

### How It Works

#### Multi-line Input Support

You can type multi-line questions naturally:

```
==> Why is my service failing?
==> I see these errors in the logs:
==> - Connection refused
==> - Timeout after 30 seconds
==> [Press ^enter to submit]
```

#### Real-time Character Input (Unix/Linux/macOS)

On systems with termios support, the system captures keystrokes in real-time:
- Characters appear as you type
- Backspace works immediately
- No need to press Enter to see your input
- ^enter submits immediately
- ^z exits immediately

#### Fallback Mode (Windows)

On Windows systems without termios:
- Type your question normally
- Press Enter for new lines
- Press Enter twice in a row to submit
- Type 'quit' to exit

### Implementation Details

#### Automatic Detection

The system automatically detects the platform capabilities:

```python
def _setup_keyboard_handler(self) -> None:
    """Setup keyboard handling for interactive input"""
    try:
        import termios
        import tty
        import sys
        self._has_termios = True
    except ImportError:
        # Windows or system without termios
        self._has_termios = False
```

#### Character Code Mapping

- **^enter**: ASCII code 10 (0x0A)
- **^z**: ASCII code 26 (0x1A)
- **Ctrl+C**: ASCII code 3 (0x03)
- **Enter**: ASCII code 13 (0x0D)
- **Backspace**: ASCII code 127 (0x7F)

#### Terminal State Management

The system properly manages terminal state:
1. Saves current terminal settings
2. Switches to raw mode for character-by-character input
3. Restores original settings when done

### User Experience Improvements

#### Before (OLD - 'END' commands)
```
==> Why is my service failing?
I see connection errors
END
```

#### After (NEW - Keyboard shortcuts)
```
==> Why is my service failing?
==> I see connection errors
==> [Press ^enter to submit, ^z to exit]
```

### Service Name Resolution

The system now displays resolved service names in follow-up analysis headers:

#### Before
```
Follow-up Analysis for kong
```

#### After
```
Follow-up Analysis for kong-gateway
```

This improvement shows the actual resolved service name (e.g., `kong-gateway.service` becomes `kong-gateway`) instead of the user's input target (e.g., `kong`).

### Error Handling

- **Empty submissions**: Warns user and continues session
- **Keyboard interrupts**: Gracefully exits with message
- **Terminal errors**: Falls back to basic input mode
- **Import errors**: Automatically uses fallback mode

### Compatibility

- ✅ **Linux**: Full keyboard shortcut support
- ✅ **macOS**: Full keyboard shortcut support
- ✅ **Windows**: Fallback mode with double-Enter submit
- ✅ **SSH/Remote**: Works with proper terminal forwarding
- ✅ **Docker/Containers**: Works in interactive containers

### Migration Notes

This change is **backward compatible** in terms of functionality:
- All existing AI analysis features work the same
- Only the input method has changed
- No changes to AI prompts or responses
- No changes to analysis results or formatting

Users will see the new instructions automatically when they enter interactive analysis mode.

## Testing Results

✅ **All imports work correctly**
✅ **New methods added successfully**
✅ **Enhanced error handling functional**
✅ **Backward compatibility maintained**
✅ **Agent selection visibility implemented**
✅ **Keyboard shortcuts working on all platforms**
✅ **Service name resolution improved**

## Benefits

### For Users
- **Better visibility** into AI analysis process
- **Clear feedback** when AI agents are not available
- **Actionable error messages** for troubleshooting
- **Intuitive keyboard shortcuts** for interactive analysis
- **Multi-line input support** for complex questions
- **Platform-specific optimizations** for best experience

### For Developers
- **Consistent error handling** patterns
- **Reusable agent detection** logic
- **Better debugging** capabilities
- **Cross-platform compatibility** with graceful fallbacks
- **Clean terminal state management**

### For System Administration
- **Easy diagnosis** of AI configuration issues
- **Clear installation guidance** for missing components
- **Transparent operation** status
- **Detailed troubleshooting information**

## Usage

The enhancements are automatically active for all AI diagnostic analysis operations:
- `pm reinit <service>` (when AI analysis is triggered)
- `pm diag <service>`
- `pm interactive-analysis <service>`
- Any other command that uses AI analysis

No configuration changes are required - the system will automatically show the enhanced agent selection process and use the improved keyboard shortcuts.

### Testing

Run the demo script to see the enhanced output:
```bash
python demo_ai_agent_selection.py
```

Test the implementation:
```bash
python test_ai_analyzer_enhancement.py
```

Test interactive analysis:
```bash
pm interactive-analysis <service-name>
```

## Future Enhancements

The new architecture makes it easy to add:
- **Agent health checks** before analysis
- **Multiple agent fallback** support
- **Agent performance metrics** display
- **Custom agent selection** options
- **Voice input support** for interactive analysis
- **Analysis result caching** for improved performance
- **Custom keyboard shortcuts** configuration

## Files Modified

1. [`ai_analyzer/analyzer.py`](ai_analyzer/analyzer.py) - Enhanced fallback logic with detailed logging and error reporting
2. [`ai_system/ai_agents.py`](ai_system/ai_agents.py) - Added agent selection visibility and detailed error reporting to AIAgentManager
3. [`ai_agents_config.json`](ai_agents_config.json) - Fixed malformed endpoint URLs for local vLLM agents
4. [`managers/reinit/ai_analyzer.py`](managers/reinit/ai_analyzer.py) - Added AI agent information display
5. [`managers/reinit/vllm_reinit_flow.py`](managers/reinit/vllm_reinit_flow.py) - Enhanced AI analysis integration
6. Interactive analysis modules - Added keyboard shortcut support and service name resolution

## Conclusion

These enhancements significantly improve the user experience of AI analysis in the reinit system by providing:
- **Clear visibility** into which AI agents are being used
- **Helpful error messages** when agents are not available
- **Consistent messaging** across all analysis types
- **Better troubleshooting** capabilities
- **Intuitive interaction** methods with keyboard shortcuts
- **Cross-platform compatibility** with appropriate fallbacks

The improvements maintain full backward compatibility while adding valuable transparency and user guidance features.
