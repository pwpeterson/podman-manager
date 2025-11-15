# Service Stopping Monitor Enhancement

## Overview

Added comprehensive real-time monitoring for services during the stopping process. This enhancement provides detailed visibility into service shutdown phases, detects stuck services, and offers both service and container monitoring capabilities.

## New Features Added

### 1. Real-Time Service Stopping Monitor (`monitor_service_stopping`)

- **Live Status Display**: Real-time panel showing service stopping progress
- **Detailed State Tracking**: Monitors systemctl status transitions
- **Stuck Service Detection**: Identifies services that hang during shutdown
- **Timeout Handling**: Prevents indefinite waiting with configurable timeouts
- **Elapsed Time Tracking**: Shows how long the stopping process has taken

### 2. Container Stopping Monitor (`monitor_container_stopping`)

- **Container-Specific Monitoring**: Tracks podman container stopping process
- **Status Transition Tracking**: Monitors container state changes
- **Integration with Service Monitor**: Can be used alongside service monitoring

### 3. Enhanced Status Detection

- **Granular State Recognition**: Distinguishes between different stopping phases
- **Signal Tracking**: Detects SIGTERM vs SIGKILL phases
- **Failure Detection**: Identifies services that fail during stopping

## Service Stopping States Monitored

| Status | Description | Indication |
|--------|-------------|------------|
| **Still Running** | Service hasn't started stopping | Continue monitoring |
| **Deactivating** | Service is gracefully shutting down | Normal process |
| **Sending SIGTERM** | Graceful shutdown signal sent | Normal process |
| **Sending SIGKILL** | Force kill signal sent | Service stuck |
| **Stopped** | Service successfully stopped | Complete |
| **Failed** | Service failed during stop | Investigate |

## Usage Examples

### Basic Service Monitoring
```python
from managers.reinit.monitoring import ReinitMonitor

monitor = ReinitMonitor(manager, health_checker)
success = monitor.monitor_service_stopping("vllm-qwen25", timeout=30)
```

### Container Monitoring
```python
success = monitor.monitor_container_stopping("vllm-container", timeout=30)
```

### Integration with Reinit Process
```python
# During reinit, monitor the stopping phase
if monitor.monitor_service_stopping(target):
    console.print("[green]Service stopped successfully, proceeding with reinit[/green]")
else:
    console.print("[red]Service stopping failed or timed out[/red]")
```

## Real-Time Display Features

### Live Status Panel
```
┌─ Service Stopping Monitor ─────────────────┐
│                                            │
│  Service: vllm-qwen25                      │
│  Status: Deactivating                      │
│  Elapsed: 2.3s                            │
│  Details: Service is deactivating          │
│  ⏳ Stopping in progress...                │
│                                            │
└────────────────────────────────────────────┘
```

### Container Status Panel
```
┌─ Container Stopping Monitor ───────────────┐
│                                            │
│  Container: vllm-container                 │
│  Status: Stopping                          │
│  Elapsed: 1.8s                            │
│  ⏳ Stopping in progress...                │
│                                            │
└────────────────────────────────────────────┘
```

## Error Detection and Handling

### Stuck Service Detection
- Detects when services require SIGKILL (force termination)
- Identifies systemctl command timeouts
- Provides early warning for problematic services

### Timeout Management
- Configurable timeout periods (default: 30 seconds)
- Prevents indefinite waiting
- Returns clear success/failure status

### Error Reporting
- Detailed error messages for troubleshooting
- Distinguishes between different failure types
- Provides actionable feedback

## Integration Points

### Reinit Operations
- Can be integrated into reinit workflows
- Provides feedback during service stopping phase
- Helps identify why reinit operations might fail

### Health Checking
- Complements existing health check functionality
- Provides real-time feedback during transitions
- Enhances overall system monitoring

### AI Analysis
- Stopping status can be included in AI diagnostic context
- Helps AI systems understand service behavior patterns
- Provides data for failure analysis

## Technical Implementation

### Key Methods

1. **`monitor_service_stopping(target, timeout=30)`**
   - Main service monitoring function
   - Returns boolean success status
   - Uses Rich Live display for real-time updates

2. **`_get_service_stopping_status(service_name)`**
   - Parses systemctl status output
   - Returns structured status information
   - Handles various service states

3. **`monitor_container_stopping(target, timeout=30)`**
   - Container-specific monitoring
   - Uses podman ps for status checking
   - Integrates with fuzzy container matching

4. **`_create_stopping_status_panel()`** / **`_create_container_stopping_panel()`**
   - Creates Rich panels for live display
   - Formats status information attractively
   - Updates in real-time

### Dependencies
- Rich library for live displays and panels
- subprocess for systemctl/podman commands
- Integration with existing fuzzy matching

## Benefits

### For Users
- **Transparency**: See exactly what's happening during service stops
- **Confidence**: Know when services are stuck vs. taking time to stop gracefully
- **Troubleshooting**: Identify problematic services quickly
- **Feedback**: Real-time progress indication

### For System Operations
- **Reliability**: Detect and handle stuck services
- **Efficiency**: Avoid waiting indefinitely for failed stops
- **Integration**: Easy to incorporate into existing workflows
- **Monitoring**: Comprehensive service lifecycle visibility

### For Development
- **Debugging**: Understand service stopping behavior
- **Testing**: Verify service shutdown procedures
- **Optimization**: Identify slow-stopping services
- **Automation**: Programmatic service stopping with feedback

## Files Modified

1. **[`managers/reinit/monitoring.py`](managers/reinit/monitoring.py)** - Added service and container stopping monitors

## Testing

Run the demo script to see the enhanced monitoring output:
```bash
python demo_service_stopping_monitor.py
```

## Future Enhancements

- **Stack Monitoring**: Monitor entire service stacks during stopping
- **Dependency Tracking**: Monitor service dependencies during shutdown
- **Performance Metrics**: Track stopping time patterns
- **Alert Integration**: Send notifications for stuck services
- **Log Analysis**: Parse service logs during stopping for additional context

## Usage in Reinit Operations

The service stopping monitor can be integrated into reinit operations to provide better visibility:

```python
# Example integration in reinit flow
def enhanced_reinit_with_monitoring(target):
    console.print("[cyan]Starting enhanced reinit with stopping monitor[/cyan]")

    # Monitor the stopping phase
    if monitor.monitor_service_stopping(target):
        console.print("[green]✅ Service stopped cleanly, proceeding with reinit[/green]")
        # Continue with reinit process
        return perform_reinit(target)
    else:
        console.print("[red]❌ Service stopping failed, investigating...[/red]")
        # Run AI analysis or other troubleshooting
        return False
```

This enhancement significantly improves the user experience during service management operations by providing clear, real-time feedback about what's happening during the critical stopping phase.
