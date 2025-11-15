# Supabase Stack Management

## Overview

This document consolidates all Supabase stack management functionality, including the correct startup order, implementation details, and usage instructions.

## Supabase Services Startup Order

### Correct Dependency Order

Based on the service dependencies and troubleshooting experience, here's the proper startup sequence:

#### 1. Foundation Layer (Infrastructure)
```bash
# Network and volumes (if using systemd services)
systemctl --user start supabase-network.service  # Optional
systemctl --user start supabase-volumes.service  # Optional
```

#### 2. Database Layer (Core Data)
```bash
# PostgreSQL database - everything depends on this
systemctl --user start supabase-db.service
sleep 15  # Wait for database initialization
```

#### 3. Core Services Layer (Authentication & API)
```bash
# Authentication service - required by most other services
systemctl --user start supabase-auth.service
sleep 5

# REST API - provides database access via HTTP
systemctl --user start supabase-rest.service
sleep 5

# Meta service - provides database schema information
systemctl --user start supabase-meta.service
sleep 5
```

#### 4. Supporting Services Layer
```bash
# Analytics/Logging service
systemctl --user start supabase-analytics.service
sleep 5

# Storage service (if using)
systemctl --user start supabase-storage.service  # Optional
sleep 3

# Real-time service (if using)
systemctl --user start supabase-realtime.service  # Optional
sleep 3

# Edge Functions (if using)
systemctl --user start supabase-edge-functions.service  # Optional
sleep 3
```

#### 5. Gateway Layer (Traffic Routing)
```bash
# Kong API Gateway - routes all API traffic
systemctl --user start supabase-kong.service
sleep 15  # Kong needs time to configure routes
```

#### 6. Frontend Layer (User Interface)
```bash
# Studio Web Interface - depends on all backend services
systemctl --user start supabase-studio.service
sleep 15  # Studio needs time to connect to backends
```

### Complete Startup Script

```bash
#!/bin/bash
# Complete Supabase startup sequence

echo "Starting Supabase services in dependency order..."

# 1. Database (foundation)
echo "Starting database..."
systemctl --user start supabase-db.service
echo "Waiting 15 seconds for database initialization..."
sleep 15

# 2. Core services
echo "Starting authentication..."
systemctl --user start supabase-auth.service
sleep 5

echo "Starting REST API..."
systemctl --user start supabase-rest.service
sleep 5

echo "Starting meta service..."
systemctl --user start supabase-meta.service
sleep 5

# 3. Supporting services
echo "Starting analytics..."
systemctl --user start supabase-analytics.service
sleep 5

# 4. Gateway
echo "Starting Kong gateway..."
systemctl --user start supabase-kong.service
echo "Waiting 15 seconds for Kong to configure routes..."
sleep 15

# 5. Frontend
echo "Starting Studio..."
systemctl --user start supabase-studio.service
echo "Waiting 15 seconds for Studio to connect..."
sleep 15

echo "All services started!"
```

## Service Dependencies Explained

### supabase-db (PostgreSQL)
- **Dependencies**: None (foundation service)
- **Required by**: All other services
- **Wait time**: 15 seconds (database initialization)

### supabase-auth (GoTrue)
- **Dependencies**: supabase-db
- **Required by**: supabase-kong, supabase-studio
- **Wait time**: 5 seconds

### supabase-rest (PostgREST)
- **Dependencies**: supabase-db
- **Required by**: supabase-kong, supabase-studio
- **Wait time**: 5 seconds

### supabase-meta (pg-meta)
- **Dependencies**: supabase-db
- **Required by**: supabase-studio
- **Wait time**: 5 seconds

### supabase-analytics (Logflare)
- **Dependencies**: supabase-db
- **Required by**: supabase-studio (optional)
- **Wait time**: 5 seconds

### supabase-kong (Kong Gateway)
- **Dependencies**: supabase-auth, supabase-rest, supabase-meta
- **Required by**: supabase-studio
- **Wait time**: 15 seconds (route configuration)

### supabase-studio (Studio UI)
- **Dependencies**: supabase-kong, supabase-meta, supabase-analytics
- **Required by**: None (frontend)
- **Wait time**: 15 seconds (backend connections)

## Why This Order Matters

1. **Database First**: Everything depends on PostgreSQL being ready
2. **Core Services**: Auth, REST, and Meta provide essential APIs
3. **Kong Last in Backend**: Needs all backend services running to configure routes
4. **Studio Last**: Needs Kong and Meta to be fully operational
5. **Proper Wait Times**: Each service needs time to initialize before dependents start

## Common Startup Issues

- **Starting Kong too early**: Kong fails if backend services aren't ready
- **Starting Studio too early**: Studio shows API errors if Kong/Meta aren't ready
- **Insufficient wait times**: Services appear running but aren't fully initialized
- **Database not ready**: All services fail if database isn't accepting connections

## Startup Order Implementation

### Overview

The Supabase stack requires services to be started in a specific dependency order to ensure proper initialization. This implementation incorporates the startup order defined above directly into the codebase.

### Implementation Details

#### Files Modified/Created

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

#### Startup Order Implementation

The implementation follows the exact order from the documentation:

##### Layer 1: Database Layer (Core Data)
- **Services**: `supabase-db`
- **Wait Time**: 15 seconds
- **Description**: PostgreSQL database - everything depends on this

##### Layer 2: Core Services Layer (Authentication & API)
- **Services**: `supabase-auth`, `supabase-rest`, `supabase-meta`
- **Wait Time**: 5 seconds
- **Description**: Authentication, REST API, and Meta services

##### Layer 3: Supporting Services Layer
- **Services**: `supabase-analytics`, `supabase-storage`, `supabase-realtime`, `supabase-edge-functions`
- **Wait Time**: 3 seconds
- **Description**: Analytics, Storage, Real-time, and Edge Functions

##### Layer 4: Gateway Layer (Traffic Routing)
- **Services**: `supabase-kong`
- **Wait Time**: 15 seconds
- **Description**: Kong API Gateway - routes all API traffic

##### Layer 5: Frontend Layer (User Interface)
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

## Verification Commands

```bash
# Check service status
systemctl --user status supabase-*.service

# Check service health
curl http://localhost:8000/  # Kong
curl http://localhost:8080/  # Meta
curl http://localhost:3000/  # Studio

# Check database connectivity
podman exec supabase-db pg_isready -U postgres
```

## Troubleshooting

If services fail to start:

### 1. Check individual service status
```bash
pm status supabase-db
pm logs supabase-db
```

### 2. Use AI diagnostics
```bash
pm diagnose supabase-kong
pm reinit supabase-studio
```

### 3. Reset failed services
```bash
pm reset-failed supabase
```

### 4. Check environment variables
```bash
pm fix-supabase-env
```

### 5. Manual startup verification
```bash
# Start services manually in order
systemctl --user start supabase-db.service
sleep 15
systemctl --user start supabase-auth.service
sleep 5
# ... continue with remaining services
```

### 6. Check service logs for errors
```bash
# Check database logs
podman logs supabase-db

# Check Kong logs
podman logs supabase-kong

# Check Studio logs
podman logs supabase-studio
```

### 7. Verify network connectivity
```bash
# Test internal service connectivity
curl http://localhost:54321/rest/v1/  # REST API
curl http://localhost:54321/auth/v1/  # Auth API
curl http://localhost:54321/  # Kong Gateway
```

## Advanced Usage

### Custom Wait Times
You can customize wait times by setting environment variables:

```bash
export SUPABASE_DB_WAIT=20        # Database wait time
export SUPABASE_CORE_WAIT=7       # Core services wait time
export SUPABASE_SUPPORT_WAIT=5    # Supporting services wait time
export SUPABASE_GATEWAY_WAIT=20   # Gateway wait time
export SUPABASE_FRONTEND_WAIT=20  # Frontend wait time
```

### Selective Service Startup
```bash
# Start only core services
pm start supabase-core

# Start only database
pm start supabase-db

# Start everything except Studio
pm start supabase --exclude supabase-studio
```

### Health Check Integration
```bash
# Start with health checks
pm start supabase --health-check

# Start with detailed monitoring
pm start supabase --monitor
```

## Configuration

### Service Configuration Files
- Database: `~/.config/containers/systemd/supabase-db.container`
- Auth: `~/.config/containers/systemd/supabase-auth.container`
- REST: `~/.config/containers/systemd/supabase-rest.container`
- Meta: `~/.config/containers/systemd/supabase-meta.container`
- Analytics: `~/.config/containers/systemd/supabase-analytics.container`
- Kong: `~/.config/containers/systemd/supabase-kong.container`
- Studio: `~/.config/containers/systemd/supabase-studio.container`

### Environment Variables
Key environment variables used by Supabase services:
- `POSTGRES_PASSWORD`: Database password
- `JWT_SECRET`: JWT signing secret
- `ANON_KEY`: Anonymous access key
- `SERVICE_ROLE_KEY`: Service role key
- `SUPABASE_URL`: Base Supabase URL
- `SUPABASE_ANON_KEY`: Anonymous key for client connections

## Future Enhancements

- Health check endpoints integration
- Configurable wait times via environment variables
- Parallel startup within layers for better performance
- Integration with Supabase CLI for additional validation
- Automatic service dependency detection
- Dynamic wait time adjustment based on service health
- Integration with monitoring systems (Prometheus, Grafana)
- Backup and restore integration with startup process

## Performance Considerations

### Startup Time Optimization
- **Total startup time**: ~60-90 seconds for full stack
- **Database layer**: 15 seconds (cannot be reduced)
- **Core services**: 15 seconds total (5s each, can be parallelized)
- **Supporting services**: 9 seconds total (3s each, can be parallelized)
- **Gateway layer**: 15 seconds (route configuration time)
- **Frontend layer**: 15 seconds (backend connection time)

### Resource Usage
- **Memory**: ~2-4GB total for full stack
- **CPU**: Moderate during startup, low during operation
- **Disk**: ~1-2GB for containers and data
- **Network**: Internal container networking, external ports 3000, 8000, 54321

### Scaling Considerations
- Database is the bottleneck for scaling
- Core services can be horizontally scaled
- Kong can handle load balancing
- Studio is stateless and can be replicated

## Security Considerations

### Network Security
- Services communicate via internal container network
- Only necessary ports exposed to host
- Kong provides API gateway security

### Authentication
- JWT-based authentication via GoTrue
- Row-level security in PostgreSQL
- API key management for service access

### Data Protection
- Database encryption at rest
- TLS encryption for API communications
- Secure secret management

## Conclusion

The Supabase stack management implementation provides:
- **Reliable startup order** based on service dependencies
- **Optimized wait times** for efficient initialization
- **Comprehensive error handling** and troubleshooting
- **Integration with existing tools** and workflows
- **Flexible configuration** options for different use cases
- **Health monitoring** and diagnostic capabilities

This ensures that Supabase services start reliably and operate correctly in the Podman Manager environment.
