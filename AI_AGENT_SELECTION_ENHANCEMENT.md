# AI Agent Selection Enhancement

## Overview

Enhanced the AI diagnostic analysis system to provide clear visibility into which AI agents are being tried and their availability status during the agent selection process.

## Changes Made

### 1. Enhanced AI Analyzer (`ai_analyzer/analyzer.py`)

- **Modified `_analyze_with_fallback` method**: Now shows a clear "🤖 AI Agent Selection:" section with status indicators
- **Added `_find_fallback_agent_with_logging` method**: Provides detailed logging of each agent being tried
- **Enhanced fallback logic**: Uses configured fallback order from `ai_agents_config.json` instead of hardcoded values
- **Added `_get_unavailability_reason` method**: Provides specific reasons why agents are unavailable

### 2. Enhanced AI Agent Manager (`ai_system/ai_agents.py`)

- **Modified `analyze_with_agent` method**: Added agent selection visibility
- **Added `_find_available_fallback_agent` method**: Provides detailed logging for agent fallback process
- **Added `_get_agent_unavailability_reason` method**: Provides specific diagnostic information for failed agents

### 3. Fixed Configuration (`ai_agents_config.json`)

- **Fixed malformed endpoints**: Changed `http://localhost:8002:8002` to `http://localhost:8002` for local vLLM agents
- **Ensures proper fallback order**: Local vLLM agents are now properly checked before cloud agents

## User Experience Improvements

### Before Enhancement
```
Using AI agent: GLM-4.1-9B-Thinking
```

### After Enhancement
```
🤖 AI Agent Selection:
  ✅ GLM-4.1-9B-Thinking - Selected for analysis
```

### Fallback Scenario
```
🤖 AI Agent Selection:
  ❌ GLM-4.1-9B-Thinking - Connection refused (service not running) (default)
  ✅ GLM-4-9B-Chat - Available (fallback)
  ✅ GLM-4-9B-Chat - Selected for analysis
```

### Detailed Error Information
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

## Key Features

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

## Benefits

- **Transparency**: Users can see exactly which AI agents are being tried
- **Debugging**: Easy to identify why a specific agent wasn't used with detailed error messages
- **Confidence**: Clear indication of which agent is actually performing the analysis
- **Troubleshooting**: Immediate feedback on specific issues (network problems, missing API keys, etc.)
- **Proper Prioritization**: Fixed configuration ensures local vLLM agents are checked before cloud agents
- **Actionable Feedback**: Error messages help users understand what needs to be fixed

## Files Modified

1. [`ai_analyzer/analyzer.py`](ai_analyzer/analyzer.py) - Enhanced fallback logic with detailed logging and error reporting
2. [`ai_system/ai_agents.py`](ai_system/ai_agents.py) - Added agent selection visibility and detailed error reporting to AIAgentManager
3. [`ai_agents_config.json`](ai_agents_config.json) - Fixed malformed endpoint URLs for local vLLM agents

## Testing

Run the demo script to see the enhanced output:
```bash
python demo_ai_agent_selection.py
```

Test the implementation:
```bash
python test_ai_analyzer_enhancement.py
```

## Usage

The enhancement is automatically active for all AI diagnostic analysis operations:
- `pm reinit <service>` (when AI analysis is triggered)
- `pm diag <service>`
- Any other command that uses AI analysis

No configuration changes are required - the system will automatically show the enhanced agent selection process.
