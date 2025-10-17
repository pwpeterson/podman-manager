# Command Display Enhancement for All PM Commands

## Summary
Added comprehensive command display functionality to ALL PM commands so that all bash, systemctl, and podman commands are displayed as they are executed, similar to the example output shown in the task.

## Changes Made

### 1. Enhanced quadlet_ops.py (for pm reinit)

**Added missing helper method:**
- `_render_ansi_output()` - Renders ANSI-colored output from subprocess commands

**Updated command execution in `_reinit_service()` method:**
- All direct `subprocess.run()` calls now display the command before execution
- Commands are shown in cyan color using the format: `[cyan]exec: command args[/cyan]`
- Applied to the following systemctl commands:
  - `systemctl --user is-system-running`
  - `systemctl --user daemon-reload` (multiple instances)
  - `systemctl --user cat <service>`
  - `systemctl --user list-unit-files --type=service *quadlet*`
  - `systemctl --user list-unit-files --type=service *vllm*`
  - `systemctl --user daemon-reexec`
  - `journalctl --user -u systemd --since '1 minute ago' -n 10`

### 2. Enhanced installer.py (for pm install)

**Added command display to install_stack() method:**
- `systemctl --user status` - systemd health check
- `systemctl --user list-units --type=service --state=loaded` - systemd communication check
- `sudo mkdir -p <target_dir>` - directory creation (when using sudo)
- `sudo cp <source> <target>` - file copying (when using sudo)
- `sudo chmod 644 <files>` - permission setting (when using sudo)
- `systemctl --user daemon-reload` / `sudo systemctl daemon-reload` - daemon reload
- `systemctl --user reset-failed` - reset failed units
- `pm refresh` - PM service discovery refresh

**Added command display to uninstall_stack() method:**
- `systemctl --user stop <service>.service` / `sudo systemctl stop <service>.service` - stop services
- `systemctl --user disable <service>.service` / `sudo systemctl disable <service>.service` - disable services
- `sudo rm <file>` - file removal (when using sudo)
- `systemctl --user daemon-reload` / `sudo systemctl daemon-reload` - daemon reload

**Added command display to check_systemd_user_session() method:**
- `systemctl --user status` - session health check
- `systemctl --user list-units --type=service --state=loaded` - communication test

### 3. Enhanced display.py (for pm ps, images, stats, volumes, networks, system-df, events)

**Added command display to missing subprocess calls:**
- `podman images` / `podman images -a` - image listing
- `podman stats` / `podman stats --no-stream` - resource usage stats
- `podman volume ls --format table` - volume listing
- `podman network ls` - network listing
- `podman ps -a --format ...` - container status (already had some display)
- `podman system df` - disk usage (already had display)
- `podman events` - event streaming (already had display)

### 4. Enhanced container_ops.py (for compose mode operations)

**Added command display to missing subprocess calls:**
- `podman logs --tail <n> <service>` - log retrieval for analysis
- `podman container prune -f` - container pruning
- `podman image prune -f` - image pruning
- All `podman compose` commands already had display via `_run_compose_command`
- All container management commands already had display

### 5. Enhanced manager.py (for core functionality)

**Added command display to missing subprocess calls:**
- `podman compose --help` - prerequisite validation
- `which <command>` - command existence checks
- `podman ps --filter ...` - dependency checking
- All compose commands already had display via `_run_compose_command`

### 6. Enhanced prune.py (for enhanced pruning)

**Added command display to all subprocess calls:**
- `podman ps -a --format ...` - container analysis
- `podman images --format ... --all` - image analysis
- `podman rmi -f <images>` - image removal
- `podman system df` - disk usage analysis
- `podman container prune -f` - quick container pruning
- `podman image prune -f` - quick image pruning

### 7. Existing Command Display

**Already implemented in quadlet_manager.py:**
- The `_run_systemctl_command()` method already displays commands with:
  ```python
  if not quiet:
      console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
  ```
- This covers the main systemctl operations like start, stop, restart, enable, disable

**Already implemented in other methods:**
- `show_service_status()` - displays `systemctl --user status` commands
- `check_auto_update_status()` - displays timer-related commands
- `update_images_and_restart()` - displays `podman auto-update` commands
- Various other methods already show their commands

## Result

Now when running `pm reinit <service>` or `pm install <stack>`, users will see all commands being executed in real-time.

**For pm reinit:**
```
[cyan]exec: systemctl --user stop vllm-delegator-mcp.service[/cyan]
[cyan]exec: systemctl --user daemon-reload[/cyan]
[cyan]exec: systemctl --user cat vllm-delegator-mcp.service[/cyan]
[cyan]exec: systemctl --user start vllm-delegator-mcp.service[/cyan]
```

**For pm install:**
```
[cyan]exec: systemctl --user status[/cyan]
[cyan]exec: systemctl --user list-units --type=service --state=loaded[/cyan]
[cyan]exec: sudo mkdir -p /home/user/.config/containers/systemd[/cyan]
[cyan]exec: sudo cp /path/to/source.container /path/to/target.container[/cyan]
[cyan]exec: sudo chmod 644 /path/to/files[/cyan]
[cyan]exec: systemctl --user daemon-reload[/cyan]
[cyan]exec: pm refresh[/cyan]
```

**For pm ps:**
```
[cyan]exec: podman ps -a --format {{.Names}};{{.Image}};{{.Status}};{{.Ports}}[/cyan]
```

**For pm images:**
```
[cyan]exec: podman images[/cyan]
```

**For pm stats:**
```
[cyan]exec: podman stats --no-stream[/cyan]
```

**For pm prune:**
```
[cyan]exec: podman ps -a --format {{.ID}};{{.Names}};{{.Image}};{{.ImageID}};{{.Status}}[/cyan]
[cyan]exec: podman images --format {{.ID}};{{.Repository}};{{.Tag}};{{.Size}};{{.Created}} --all[/cyan]
[cyan]exec: podman rmi -f <image_ids>[/cyan]
[cyan]exec: podman container prune -f[/cyan]
[cyan]exec: podman image prune -f[/cyan]
```

**For compose mode commands:**
```
[cyan]exec: podman compose -f compose-file.yml up -d service[/cyan]
[cyan]exec: podman compose -f compose-file.yml logs service[/cyan]
[cyan]exec: podman compose -f compose-file.yml stop service[/cyan]
```

This matches the desired behavior shown in the task example where commands like `systemctl --user start local-ai-caddy.service` are displayed as they execute.

## Testing

A test script `test_command_display.py` was created to verify the command display format works correctly.

## Files Modified

1. `quadlet_ops.py` - Enhanced command display in reinit process
2. `installer.py` - Enhanced command display in install/uninstall processes
3. `display.py` - Enhanced command display for status/info commands
4. `container_ops.py` - Enhanced command display for compose operations
5. `manager.py` - Enhanced command display for core functionality
6. `prune.py` - Enhanced command display for pruning operations
7. `test_command_display.py` - Test script for verification
8. `COMMAND_DISPLAY_CHANGES.md` - This documentation

## Coverage Summary

Now ALL PM commands display their underlying bash, systemctl, and podman commands as they execute:

**Quadlet Mode Commands:**
- `pm reinit` - systemctl stop/start/reload, daemon operations
- `pm install/uninstall` - systemctl operations, file operations
- `pm start/stop/restart` - systemctl operations (via _run_systemctl_command)
- `pm enable/disable` - systemctl operations (via _run_systemctl_command)
- `pm logs` - journalctl operations (via show_logs)
- `pm status` - systemctl status operations

**Compose Mode Commands:**
- `pm start/stop/restart` - podman compose operations
- `pm logs` - podman compose/podman logs operations
- `pm build` - podman compose build operations
- `pm reinit` - podman compose down/up operations
- `pm exec` - podman compose exec operations

**Universal Commands (both modes):**
- `pm ps` - podman ps operations
- `pm images` - podman images operations
- `pm stats` - podman stats operations
- `pm volumes` - podman volume operations
- `pm networks` - podman network operations
- `pm system-df` - podman system df operations
- `pm events` - podman events operations
- `pm prune` - comprehensive podman pruning operations

**System Commands:**
- All prerequisite checks - which, podman compose --help
- All dependency checks - podman ps filtering
- All health checks - systemctl status operations

The changes ensure complete transparency for users to see exactly what commands are being executed during ALL PM operations, providing comprehensive debugging capabilities and command visibility across the entire tool.
