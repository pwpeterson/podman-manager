# Build AI Analysis - Quick Reference

## Basic Usage

```bash
# Build with automatic AI analysis on failure
pm build <service-name>

# Build with verbose output
pm build <service-name> -v
```

## How It Works

- **Automatic**: AI analysis runs automatically when builds fail
- **Focused**: Analyzes Dockerfile content and build errors only
- **Simple**: No configuration needed - just run `pm build`
- **Non-blocking**: Build failures are reported immediately, AI analysis runs after

## Common Build Commands

```bash
# Build vLLM services
pm build vllm-delegator
pm build vllm-proxy
pm build vllm-qwen25

# Verbose build with full diagnostics
pm build vllm-delegator -v
```

## What AI Analysis Provides

### On Build Failure
- **Root Cause**: What caused the build to fail
- **Fix**: Specific commands or Dockerfile changes needed
- **Explanation**: Brief explanation of why this fixes the issue

### Analysis Focuses On
- Dockerfile syntax and structure issues
- Base image problems
- Package installation failures
- File operations and permissions
- Common container build patterns

## Example Output

```
❌ Build failed!
🤖 Analyzing build failure...

### Root Cause
The build failed because the base image 'python:3.9-slim' cannot be found.

### Fix
1. Update the Dockerfile FROM line to use a valid base image:
   ```dockerfile
   FROM python:3.9-slim-bullseye
   ```
2. Rebuild with: `pm build <service>`

### Explanation
The image tag 'python:3.9-slim' may have been deprecated. Using the specific
Debian version ensures the image is available.

✓ Build analysis completed
```

## Integration with Other Commands

```bash
# Build and restart with AI analysis
pm reinit <service> --build

# Start with build and AI analysis
pm start <service> --build

# Restart with build and AI analysis
pm restart <service> --build
```

## Troubleshooting

### AI Analysis Not Working?
```bash
# Check available AI agents
pm ai-agents

# Check with verbose mode
pm build <service> -v
```

### Build Still Failing?
```bash
# Check service logs
pm logs <service>

# Diagnose container issues
pm diagnose <service>

# Reset failed state
pm reset-failed <service>
```

## Quick Commands Reference

| Task | Command |
|------|----------|
| Basic build | `pm build <service>` |
| Verbose build | `pm build <service> -v` |
| Check AI agents | `pm ai-agents` |
| View logs | `pm logs <service>` |
| Diagnose issues | `pm diagnose <service>` |

## Key Features

- **Zero Configuration**: Works out of the box
- **Automatic Trigger**: Runs on every build failure
- **Focused Analysis**: Only Dockerfile and error messages
- **Concise Output**: Brief, actionable recommendations
- **Silent Failure**: Won't break builds if AI is unavailable

For detailed technical information, see `BUILD_AI_ANALYSIS_INTEGRATION.md`.
