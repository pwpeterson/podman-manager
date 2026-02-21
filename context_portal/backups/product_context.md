# Product Context
## Deployment
{'container_systemd_dir': '/etc/containers/systemd', 'previous_container_systemd_dir': '~/.config/containers/systemd', 'change_date': '2026-02-19', 'reason': 'System-wide deployment for better systemd integration'}

## Paths
{'quadlet_source_dir': '/home/pwp/srv/local-ai-packaged/quadlets', 'systemd_containers_dir': '/etc/containers/systemd', 'env_file_path': '/etc/containers/systemd/.env', 'network_config_path': '/etc/containers/systemd/networks.config.json'}

## Affected Files
*   core/simple_fuzzy_matcher.py
*   core/validation_utils.py
*   core/service_discovery.py
*   managers/quadlet_manager.py
*   ai_analyzer/llama_cpp_troubleshooter.py
*   ai_analyzer/config.py
*   ai_analyzer/data_collectors.py
*   operations/installer.py
*   utils/supabase_fixer.py

## Supabase Configuration
{'database_port': '5433', 'pooler_startup': {'requires_sudo': True, 'readiness_checks': ['pg_isready on port 5433', 'psql connection test on port 5433'], 'max_attempts': 12, 'retry_interval': '5 seconds'}}

## Recent Fixes
{'supabase_pooler_startup': {'date': '2026-02-21', 'issue': "Pooler failing to start with 'container not found' errors", 'root_causes': ['Missing sudo for rootless podman containers', 'Incorrect port 5432 instead of 5433'], 'solution': 'Added sudo to podman exec commands and corrected port to 5433', 'file': 'managers/supabase_stack_manager.py', 'function': '_ensure_database_ready_for_pooler'}}
