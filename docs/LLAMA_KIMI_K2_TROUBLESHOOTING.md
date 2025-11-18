# llama-kimi-k2-thinking-q1 Service Troubleshooting Guide

## Problem
The service `llama-kimi-k2-thinking-q1` is failing with the error:
```
error: invalid argument: llama-server
```

## Root Cause
The llama.cpp container is receiving `llama-server` as an argument, but this is invalid. The correct argument should be `--server` (with double dashes) or no argument at all.

## Solution Steps

### Step 1: Locate the Container File
Find the container configuration file in one of these locations:
```bash
~/.config/containers/systemd/llama-kimi-k2-thinking-q1.container
~/.config/containers/systemd/llama-kimi-k2-thinking_q1.container
```

### Step 2: Examine the Current Configuration
```bash
cat ~/.config/containers/systemd/llama-kimi-k2-thinking-q1.container
```

Look for lines containing `llama-server`, particularly in `Exec=` lines.

### Step 3: Fix the Configuration

#### Option A: Replace with --server
Edit the container file and replace `llama-server` with `--server`:
```ini
# Before
Exec=/app/llama-server --host 0.0.0.0 --port 8005

# After  
Exec=/app/llama-server --server --host 0.0.0.0 --port 8005
```

#### Option B: Remove the argument entirely
Edit the container file and remove `llama-server`:
```ini
# Before
Exec=/app/llama-server llama-server --host 0.0.0.0 --port 8005

# After
Exec=/app/llama-server --host 0.0.0.0 --port 8005
```

### Step 4: Apply the Fix

1. **Backup the original file:**
   ```bash
   cp ~/.config/containers/systemd/llama-kimi-k2-thinking-q1.container ~/.config/containers/systemd/llama-kimi-k2-thinking-q1.container.backup
   ```

2. **Edit the file:**
   ```bash
   nano ~/.config/containers/systemd/llama-kimi-k2-thinking-q1.container
   ```
   
   Apply one of the fixes from Step 3.

3. **Reload systemd:**
   ```bash
   systemctl --user daemon-reload
   ```

4. **Restart the service:**
   ```bash
   systemctl --user restart llama-kimi-k2-thinking-q1.service
   ```

5. **Check the status:**
   ```bash
   systemctl --user status llama-kimi-k2-thinking-q1.service
   ```

### Step 5: Verify the Fix

Check the service logs to ensure it's starting correctly:
```bash
journalctl --user -u llama-kimi-k2-thinking-q1.service -f
```

You should see the service starting without the "invalid argument" error.

## Alternative Diagnosis

If the above doesn't work, the issue might be in:

1. **Container Image**: The container image itself might have incorrect entry point or command configuration.
2. **Environment Variables**: Check if there are environment variables affecting the command.
3. **Quadlet Configuration**: If using Quadlet, check the .container file format.

## Common Container File Patterns

### Correct llama.cpp Configuration
```ini
[Unit]
Description=Kimi-K2-Thinking via llama.cpp llama-server
Wants=network-online.target
After=network-online.target

[Container]
Image=your-llama-image:latest
Exec=--server --host 0.0.0.0 --port 8005 --model /models/model.gguf
PublishPort=8005:8005
Volume=/path/to/models:/models:ro

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=default.target
```

### Incorrect Configuration (causes the error)
```ini
# This will cause "invalid argument: llama-server" error
Exec=llama-server --host 0.0.0.0 --port 8005
```

## Testing the Fix

After applying the fix:

1. **Check service status:**
   ```bash
   systemctl --user status llama-kimi-k2-thinking-q1.service
   ```

2. **Test the endpoint:**
   ```bash
   curl http://localhost:8005/health
   ```

3. **Check if the model is responding:**
   ```bash
   curl -X POST http://localhost:8005/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}'
   ```

## Rollback Instructions

If the fix doesn't work, restore the backup:
```bash
cp ~/.config/containers/systemd/llama-kimi-k2-thinking-q1.container.backup ~/.config/containers/systemd/llama-kimi-k2-thinking-q1.container
systemctl --user daemon-reload
systemctl --user restart llama-kimi-k2-thinking-q1.service
```

## Additional Resources

- [llama.cpp server documentation](https://github.com/ggerganov/llama.cpp/tree/master/examples/server)
- [Podman Quadlet documentation](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
- [systemd user services](https://wiki.archlinux.org/title/Systemd/User)
