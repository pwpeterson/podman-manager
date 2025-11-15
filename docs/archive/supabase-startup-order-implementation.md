# Supabase Startup Order Implementation

This document describes the implementation of the Supabase startup order in the Podman Manager.

## Overview

The Supabase stack requires services to be started in a specific dependency order to ensure proper initialization. This implementation incorporates the startup order defined in [`docs/supabase-stack-startup-order.md`](supabase-stack-startup-order.md) directly into the codebase.

## Implementation Details

### Files Modified/Created

1. **`managers/supabase_stack_manager.py`** (NEW)
   - Dedicated Supabase stack manager with proper startup order
   - Implements dependency layers with appropriate wait times
   - Includes service health monitoring and error detection

2. **`managers/stack_manager.py`** (MODIFIED)
   - Integrated Supabase-specific handling for `reinit_stack()`, `_start_stack()`, and `_stop_stack()`
   - Delegates Supabase operations to the specialized manager

3. **`managers/service_lifecycle.py`** (MODIFIED)
   - Added Supabase handling to `start()`, `_start_stack()`, and `_stop_stack()` methods
   - Ensures `pm start supabase` uses proper startup order

4. **`operations/container_builder.py`** (MODIFIED)
   - Added `build_stack_supabase()` and `build_stack_supabase_podman()` methods
   - Supports both quadlet and podman build modes

### Startup Order Implementation

The implementation follows the exact order from the documentation:

#### Layer 1: Database Layer (Core Data)
- **Services**: `supabase-db`
- **Wait Time**: 15 seconds
- **Description**: PostgreSQL database - everything depends on this

#### Layer 2: Core Services Layer (Authentication & API)
- **Services**: `supabase-auth`, `supabase-rest`, `supabase-meta`
- **Wait Time**: 5 seconds
- **Description**: Authentication, REST API, and Meta services

#### Layer 3: Supporting Services Layer
- **Services**: `supabase-analytics`, `supabase-storage`, `supabase-realtime`, `supabase-edge-functions`
- **Wait Time**: 3 seconds
- **Description**: Analytics, Storage, Real-time, and Edge Functions

#### Layer 4: Gateway Layer (Traffic Routing)
- **Services**: `supabase-kong`
- **Wait Time**: 15 seconds
- **Description**: Kong API Gateway - routes all API traffic

#### Layer 5: Frontend Layer (User Interface)
- **Services**: `supabase-studio`
- **Wait Time**: 15 seconds
- **Description**: Studio Web Interface - depends on all backend services

## Usage

### Starting Supabase Stack
```bash
# Start with proper dependency order
pm start supabase

# Start with build
pm start supabase --build
```

### Reinitializing Supabase Stack
```bash
# Reinit with proper startup order
pm reinit supabase

# Reinit with quadlet build
pm reinit supabase --quadlet-build

# Reinit with podman build
pm reinit supabase --podman-build
```

### Stopping Supabase Stack
```bash
# Stop in reverse dependency order
pm stop supabase
```

## Features

### Service Health Monitoring
- Checks service active status after startup
- Monitors logs for critical error patterns
- Provides detailed feedback on service health

### Error Handling
- Graceful handling of missing services
- Continues with remaining services if some fail
- Provides clear error messages and troubleshooting guidance

### Integration with Existing Tools
- Works with existing AI diagnostic capabilities
- Integrates with common actions and troubleshooting workflows
- Maintains compatibility with existing command structure

### Wait Time Optimization
- Database services: 15 seconds (initialization time)
- Core services: 5 seconds (API startup)
- Supporting services: 3 seconds (lightweight services)
- Gateway services: 15 seconds (route configuration)
- Frontend services: 15 seconds (backend connection time)

## Testing

A test script is available at [`scripts/test_supabase_startup_order.py`](../scripts/test_supabase_startup_order.py) to verify the implementation:

```bash
python3 scripts/test_supabase_startup_order.py
```

## Benefits

1. **Reliability**: Services start in proper dependency order
2. **Efficiency**: Optimized wait times prevent unnecessary delays
3. **Maintainability**: Centralized startup logic in dedicated manager
4. **Compatibility**: Seamless integration with existing commands
5. **Monitoring**: Built-in health checking and error detection
6. **Flexibility**: Supports both quadlet and podman build modes

## Troubleshooting

If services fail to start:

1. **Check individual service status**:
   ```bash
   pm status supabase-db
   pm logs supabase-db
   ```

2. **Use AI diagnostics**:
   ```bash
   pm diagnose supabase-kong
   pm reinit supabase-studio
   ```

3. **Reset failed services**:
   ```bash
   pm reset-failed supabase
   ```

4. **Check environment variables**:
   ```bash
   pm fix-supabase-env
   ```

## Future Enhancements

- Health check endpoints integration
- Configurable wait times via environment variables
- Parallel startup within layers for better performance
- Integration with Supabase CLI for additional validation
