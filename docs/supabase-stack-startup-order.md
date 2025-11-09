# Supabase Services Startup Order

## Correct Dependency Order

Based on the service dependencies and our troubleshooting experience, here's the proper startup sequence:

### 1. Foundation Layer (Infrastructure)
```bash
# Network and volumes (if using systemd services)
systemctl --user start supabase-network.service  # Optional
systemctl --user start supabase-volumes.service  # Optional
```

### 2. Database Layer (Core Data)
```bash
# PostgreSQL database - everything depends on this
systemctl --user start supabase-db.service
sleep 15  # Wait for database initialization
```

### 3. Core Services Layer (Authentication & API)
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

### 4. Supporting Services Layer
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

### 5. Gateway Layer (Traffic Routing)
```bash
# Kong API Gateway - routes all API traffic
systemctl --user start supabase-kong.service
sleep 15  # Kong needs time to configure routes
```

### 6. Frontend Layer (User Interface)
```bash
# Studio Web Interface - depends on all backend services
systemctl --user start supabase-studio.service
sleep 15  # Studio needs time to connect to backends
```

## Complete Startup Script

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
