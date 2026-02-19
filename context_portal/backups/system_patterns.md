# System Patterns

---
## STDIO Service Configuration Pattern
*   [2025-12-14 01:10:55]
STDIO services are defined in stdio_services_config.json with service metadata (description, container_name, image, stack, run_command). ServiceDiscovery loads this config at initialization and marks services with stdio:true flag. Display logic checks for STDIO services first before checking systemd status. Config file path uses script directory (Path(__file__).parent.parent) not cwd for location independence.
