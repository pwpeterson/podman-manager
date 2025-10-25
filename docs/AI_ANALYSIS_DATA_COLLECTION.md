# AI Analysis Data Collection Guide

This document explains exactly what log data and context information is collected and included in AI analysis prompts for different types of analysis.

## Overview

The AI analysis system collects different types of data depending on the analysis type. All data is collected locally and sent to the selected AI agent for analysis.

## Data Collection by Analysis Type

### 1. Log Analysis (`pm logs service -ai`)

**Commands executed:**
```bash
# Primary systemd logs
journalctl --user -u <service_name> -n <lines> --no-pager

# Systemd unit details
systemctl --user status <service_name> --no-pager -l
systemctl --user cat <service_name>
systemctl --user show <service_name> -p ExecMainStatus,ExecMainCode,Result,ActiveEnterTimestamp,InactiveEnterTimestamp,RestartCount

# Container information
podman ps -a --format "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"
podman logs <container_name> --since 2h --timestamps --tail 100
podman inspect <container_name>
podman pod ps --format "{{.ID}}\t{{.Name}}\t{{.Status}}"

# System resources
df -h /
podman system info
podman system df

# Network and storage
podman network ls
podman volume ls
ss -tulpen -H  # For port conflict detection
```

**Comprehensive data collected:**
- **Systemd logs**: Last 50 lines (default) from journalctl
- **Unit status**: Complete systemctl status output
- **Unit properties**: Failure analysis properties (exit codes, restart counts, etc.)
- **Unit file content**: Generated systemd unit file from quadlet
- **Container list**: All containers with status and images
- **Container logs**: Last 2 hours of container-specific logs
- **Container inspection**: Detailed container configuration (truncated if large)
- **Pod information**: Pod status if applicable
- **Disk space**: System and Podman storage usage
- **Network info**: Podman networks and port conflicts
- **Volume info**: Podman volumes
- **Service name**: Resolved service name (e.g., `vllm-glm46.service`)
- **Target**: Original service name provided by user

**Example prompt sent to AI:**
```
You are an expert system administrator and DevOps engineer.

Target: vllm-glm46
Analysis Type: logs
Timestamp: 2025-01-23T10:30:45.123456

Analyze the following Podman Quadlet service diagnostics and provide:

1. **Root Cause Analysis**: Identify the primary issues causing errors or warnings
2. **Recommended Solutions**: Specific, actionable steps to resolve the problems
3. **Quadlet-Specific Issues**: Check for common quadlet configuration problems
4. **System Resource Issues**: Identify any resource constraints or conflicts

IMPORTANT: This is a Podman Quadlet managed by systemd. Consider quadlet-specific issues like:
- Container image pull failures
- Volume/network configuration errors
- Port conflicts
- Resource constraints (disk space, memory)
- SELinux issues
- Systemd unit file problems

Service: vllm-glm46.service
Target: vllm-glm46
Log Lines Analyzed: 47

=== SYSTEMD SERVICE LOGS ===
Jan 23 10:25:12 hostname systemd[1234]: Starting vllm-glm46.service...
Jan 23 10:25:13 hostname podman[5678]: Trying to pull docker.io/vllm/vllm-openai:latest
[... actual systemd log content ...]
=== END SYSTEMD LOGS ===

=== SYSTEMD UNIT STATUS ===
● vllm-glm46.service - vllm-glm46 Podman Container
   Loaded: loaded (/home/user/.config/systemd/user/vllm-glm46.service; enabled)
   Active: failed (Result: exit-code) since Wed 2025-01-23 10:25:20 CST; 2min ago
[... complete status output ...]
=== END UNIT STATUS ===

=== CONTAINER LIST ===
CONTAINER ID  NAMES       STATUS                    IMAGE
abc123def456  vllm-glm46  Exited (125) 2 hours ago  docker.io/vllm/vllm-openai:latest
=== END CONTAINER LIST ===

=== CONTAINER LOGS (Last 2 hours) ===
2025-01-23T10:25:15.123Z Error: failed to pull image: connection timeout
2025-01-23T10:25:15.456Z Container startup failed
[... container-specific logs ...]
=== END CONTAINER LOGS ===

=== DISK SPACE ===
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        20G   18G  1.2G  94% /
=== END DISK SPACE ===

=== PORT USAGE (Potential Conflicts) ===
Port 8002: tcp   LISTEN  0   128   0.0.0.0:8002   0.0.0.0:*   users:(("python3",pid=1234,fd=3))
=== END PORT USAGE ===

Provide a structured analysis focusing on:
1. **Immediate Issues**: What's preventing the service from working right now?
2. **Root Causes**: Why are these issues occurring?
3. **Step-by-Step Fix**: Specific commands to resolve the problems
4. **Prevention**: How to avoid these issues in the future
5. **Monitoring**: What to watch for ongoing health

Use podman commands (not docker) in all recommendations.
```

### 2. Reinit Failure Analysis (Automatic)

**Commands executed:**
```bash
# Service logs
journalctl --user -u <service_name> -n 50 --no-pager

# Service status
systemctl --user status <service_name> --no-pager -l
```

**Data collected:**
- **Service logs**: Last 50 lines from journalctl
- **Start error**: Error message from failed systemctl start command
- **Service status**: Full systemctl status output
- **Service name**: Resolved service name
- **Operation context**: "reinit (stop -> daemon-reload -> start)"

**Example prompt sent to AI:**
```
You are an expert system administrator and DevOps engineer.

Target: vllm-glm46
Analysis Type: reinit_failure
Timestamp: 2025-01-23T10:30:45.123456

Analyze the following service reinit failure and provide a brief cause/resolution report:

Service: vllm-glm46.service
Operation: reinit (stop -> daemon-reload -> start)

Job for vllm-glm46.service failed because the control process exited with error code.

=== SERVICE LOGS ===
[... last 50 lines of journalctl output ...]
=== END LOGS ===

IMPORTANT: Use podman, not docker in all recommendations and commands.

Provide a concise analysis with:
1. **Root Cause**: Primary reason for the reinit failure
2. **Immediate Fix**: Specific steps to resolve the issue right now
3. **Configuration Changes**: Any config file modifications needed
4. **Prevention**: How to avoid this issue in future reinits
```

### 3. Status Analysis (`pm status service -ai` - future)

**Command executed:**
```bash
systemctl --user status <service_name> --no-pager -l
```

**Data collected:**
- **Status output**: Complete systemctl status output (stdout + stderr)
- **Status code**: Exit code from systemctl status command
- **Service name**: Resolved service name

### 4. Build Failure Analysis (future)

**Data collected:**
- **Build error**: Error message from build command
- **Build command**: The command that was executed
- **Build output**: Complete build output/logs

### 5. Performance Analysis (future)

**Command executed:**
```bash
podman stats --no-stream --format json
```

**Data collected:**
- **Performance data**: JSON output from podman stats
- **Container metrics**: CPU, memory, I/O usage

### 6. Security Analysis (future)

**Data collected:**
- **Security context**: Basic security analysis request
- **Target service**: Service name for security assessment

## Data Privacy and Security

### Local Agents (vllm-qwen25, vllm-glm46)
- **Privacy**: All data stays on your local machine
- **Network**: Only communicates with local vLLM services (localhost:8002, localhost:8003)
- **Storage**: No data is stored by the AI agents
- **Logs**: Your service logs never leave your system

### Cloud Agents (claude, gpt4)
- **Privacy**: Log data is sent to external APIs (Anthropic, OpenAI)
- **Network**: Data transmitted over HTTPS to cloud providers
- **Storage**: Subject to cloud provider data retention policies
- **Logs**: Your service logs are sent to third-party services

**⚠️ Privacy Recommendation**: Use local agents (qwen25, glm46) for sensitive systems or production environments.

## Customizing Data Collection

### Number of Log Lines

You can control how many log lines are analyzed:

```bash
# Default: 50 lines
pm logs vllm-glm46 -ai

# Standard analysis (uses default log collection)
pm logs vllm-glm46 -ai

# Verbose analysis for comprehensive diagnostics
pm logs vllm-glm46 -ai -v
```

### Verbose Mode

See exactly what data is being sent to the AI and every diagnostic command executed:

```bash
pm logs vllm-glm46 -ai qwen25 -v
```

This will show:
- **Every diagnostic command executed** with real-time feedback
- **Command execution status** with exit codes and data metrics
- **Data collection progress** for each diagnostic step
- The complete prompt being sent to the AI
- All collected log data
- AI agent selection process
- Response processing

#### Verbose Output Example

```bash
pm logs vllm-glm46 -ai qwen25 -v
```

Shows detailed execution tracking:
```
  exec: ai_analyze(type=logs, target=vllm-glm46, agent=vllm-qwen25)
  exec: Starting comprehensive diagnostic data collection for logs analysis
  exec: Collecting comprehensive service diagnostics for vllm-glm46
  exec: Resolving service name for target 'vllm-glm46'
  exec: Resolved to service 'vllm-glm46.service'
  exec: journalctl --user -u vllm-glm46.service -n 50 --no-pager
  exec: Collected 47 lines of systemd logs
  exec: Collecting systemd unit details
  exec: systemctl --user status vllm-glm46.service --no-pager -l
  exec: Unit status collected (exit code: 0)
  exec: systemctl --user cat vllm-glm46.service
  exec: Unit file content collected (1247 chars)
  exec: systemctl --user show vllm-glm46.service -p ExecMainStatus,ExecMainCode,Result,ActiveEnterTimestamp,InactiveEnterTimestamp,RestartCount
  exec: Unit properties collected
  exec: Collecting container details
  exec: podman ps -a --format {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}
  exec: Found 3 containers
  exec: Found matching container: vllm-glm46
  exec: podman logs vllm-glm46 --since 2h --timestamps --tail 100
  exec: Container logs collected (23 lines)
  exec: podman inspect vllm-glm46
  exec: Container inspect data collected (5432 chars)
  exec: podman pod ps --format {{.ID}}\t{{.Name}}\t{{.Status}}
  exec: No pods found (exit code: 0)
  exec: Collecting system resource information
  exec: df -h /
  exec: Disk space information collected
  exec: podman system info
  exec: Podman system info collected (3456 chars)
  exec: podman system df
  exec: Podman disk usage collected
  exec: Collecting network and storage information
  exec: podman network ls
  exec: Found 2 Podman networks
  exec: podman volume ls
  exec: Found 1 Podman volumes
  exec: Checking port usage for common ports: 8000, 8001, 8002, 8003, 8080, 3000, 5000
  exec: ss -tulpen -H | grep :8002
  exec: Port 8002 is in use
  exec: Found 1 ports in use
  exec: Diagnostic data collection completed
  exec: Generated AI analysis prompt
  ────────────────────────────────────────────────────────────────────────────────
  [Complete AI prompt with all diagnostic data shown here]
  ────────────────────────────────────────────────────────────────────────────────
```

This comprehensive verbose output ensures complete transparency of:
- **Every command executed** during diagnostic data collection
- **Success/failure status** with exit codes for each command
- **Data metrics** (line counts, character counts, item counts)
- **Error handling** with detailed failure messages
- **Progress tracking** through each diagnostic phase

## Data Collection Process

1. **Service Resolution**: Target name is resolved to actual systemd service name
2. **Log Collection**: journalctl command is executed to get recent logs
3. **Data Filtering**: Raw logs are included without filtering (full context)
4. **Prompt Generation**: Structured prompt is created with context and logs
5. **AI Analysis**: Prompt is sent to selected AI agent
6. **Result Display**: AI response is formatted and displayed

## Example: Complete Data Flow

**User command:**
```bash
pm logs vllm-glm46 -ai qwen25 -v
```

**Data collection steps:**
1. Resolve `vllm-glm46` → `vllm-glm46.service`
2. Execute: `journalctl --user -u vllm-glm46.service -n 30 --no-pager`
3. Collect 30 lines of logs + metadata
4. Generate structured prompt with logs
5. Send to vllm-qwen25 agent (localhost:8002)
6. Display formatted AI analysis

**Verbose output shows complete diagnostic command execution:**
```
[cyan]exec: ai_analyze(type=logs, target=vllm-glm46, agent=vllm-qwen25)[/cyan]
[cyan]exec: Starting comprehensive diagnostic data collection for logs analysis[/cyan]
[cyan]exec: Collecting comprehensive service diagnostics for vllm-glm46[/cyan]
[cyan]exec: Resolving service name for target 'vllm-glm46'[/cyan]
[cyan]exec: Resolved to service 'vllm-glm46.service'[/cyan]
[cyan]exec: journalctl --user -u vllm-glm46.service -n 30 --no-pager[/cyan]
[cyan]exec: Collected 28 lines of systemd logs[/cyan]
[cyan]exec: Collecting systemd unit details[/cyan]
[cyan]exec: systemctl --user status vllm-glm46.service --no-pager -l[/cyan]
[cyan]exec: Unit status collected (exit code: 0)[/cyan]
[cyan]exec: systemctl --user cat vllm-glm46.service[/cyan]
[cyan]exec: Unit file content collected (1247 chars)[/cyan]
[cyan]exec: Collecting container details[/cyan]
[cyan]exec: podman ps -a --format {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}[/cyan]
[cyan]exec: Found 3 containers[/cyan]
[cyan]exec: Found matching container: vllm-glm46[/cyan]
[cyan]exec: podman logs vllm-glm46 --since 2h --timestamps --tail 100[/cyan]
[cyan]exec: Container logs collected (15 lines)[/cyan]
[cyan]exec: Collecting system resource information[/cyan]
[cyan]exec: df -h /[/cyan]
[cyan]exec: Disk space information collected[/cyan]
[cyan]exec: podman system info[/cyan]
[cyan]exec: Podman system info collected (3456 chars)[/cyan]
[cyan]exec: Collecting network and storage information[/cyan]
[cyan]exec: podman network ls[/cyan]
[cyan]exec: Found 2 Podman networks[/cyan]
[cyan]exec: podman volume ls[/cyan]
[cyan]exec: Found 1 Podman volumes[/cyan]
[cyan]exec: Checking port usage for common ports: 8000, 8001, 8002, 8003, 8080, 3000, 5000[/cyan]
[cyan]exec: ss -tulpen -H | grep :8002[/cyan]
[cyan]exec: Port 8002 is in use[/cyan]
[cyan]exec: Found 1 ports in use[/cyan]
[cyan]exec: Diagnostic data collection completed[/cyan]
[cyan]exec: Generated AI analysis prompt[/cyan]
[cyan]────────────────────────────────────────────────────────────────────────────────[/cyan]
[cyan]You are an expert system administrator and DevOps engineer.[/cyan]
[cyan][/cyan]
[cyan]Target: vllm-glm46[/cyan]
[cyan]Analysis Type: logs[/cyan]
[cyan]Timestamp: 2025-01-23T10:30:45.123456[/cyan]
[cyan][... complete prompt with all diagnostic data ...][/cyan]
[cyan]────────────────────────────────────────────────────────────────────────────────[/cyan]
```

## Log Data Examples

### Typical Log Content Included

```
Jan 23 10:25:12 hostname systemd[1234]: Starting vllm-glm46.service...
Jan 23 10:25:13 hostname podman[5678]: Trying to pull docker.io/vllm/vllm-openai:latest
Jan 23 10:25:15 hostname podman[5678]: Getting image source signatures
Jan 23 10:25:16 hostname podman[5678]: Copying blob sha256:abc123...
Jan 23 10:25:20 hostname podman[5678]: Error: failed to pull image: connection timeout
Jan 23 10:25:20 hostname systemd[1234]: vllm-glm46.service: Main process exited, code=exited, status=125/n/a
Jan 23 10:25:20 hostname systemd[1234]: vllm-glm46.service: Failed with result 'exit-code'.
Jan 23 10:25:20 hostname systemd[1234]: Failed to start vllm-glm46.service.
```

### What's NOT Included

- **Sensitive environment variables**: Not directly included in logs
- **API keys or passwords**: Not collected separately (may appear in logs if misconfigured)
- **File contents**: Only log output, not configuration files
- **Network traffic**: Only what appears in service logs
- **System-wide logs**: Only the specific service's logs

## Best Practices

1. **Use local agents** for sensitive systems
2. **Review logs first** with `pm logs service` before AI analysis
3. **Use verbose mode** (`-v`) to see exactly what data is sent
4. **Limit log lines** (`-n 20`) for faster analysis of recent issues
5. **Check service status** first to understand the current state
6. **Sanitize logs** if they contain sensitive information before using cloud agents

This data collection approach provides the AI with comprehensive context while allowing you to control privacy and data exposure based on your agent choice.
