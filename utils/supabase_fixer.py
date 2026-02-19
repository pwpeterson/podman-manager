#!/usr/bin/env python3
"""
Supabase environment variable fix utility
"""

import re
from pathlib import Path

from core.config import console
from utils.secure_subprocess import systemctl_user


def fix_supabase_environment_variables():
    """Fix Supabase environment variable issues in container files"""

    # Common Supabase environment variable defaults
    SUPABASE_ENV_DEFAULTS = {
        "POSTGRES_PASSWORD": "your-super-secret-and-long-postgres-password",
        "POSTGRES_DB": "postgres",
        "POSTGRES_USER": "postgres",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "JWT_SECRET": "your-super-secret-jwt-token-with-at-least-32-characters-long",
        "ANON_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0",
        "SERVICE_ROLE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU",
        "DASHBOARD_USERNAME": "supabase",
        "DASHBOARD_PASSWORD": "this_password_is_insecure_and_should_be_updated",
        "SECRET_KEY_BASE": "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890",
        "SITE_URL": "http://localhost:3000",
        "API_EXTERNAL_URL": "http://localhost:8000",
        "SUPABASE_PUBLIC_URL": "http://localhost:8000",
        "SUPABASE_URL": "http://localhost:8000",
        "SUPABASE_ANON_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0",
        "IMGPROXY_ENABLE_WEBP_DETECTION": "true",
        "IMGPROXY_USE_ETAG": "true",
        "IMGPROXY_KEY": "your-imgproxy-key-here",
        "IMGPROXY_SALT": "your-imgproxy-salt-here",
        "GOTRUE_EXTERNAL_EMAIL_ENABLED": "true",
        "GOTRUE_MAILER_AUTOCONFIRM": "false",
        "GOTRUE_SMTP_ADMIN_EMAIL": "admin@example.com",
        "GOTRUE_SMTP_HOST": "localhost",
        "GOTRUE_SMTP_PORT": "587",
        "GOTRUE_SMTP_USER": "your-smtp-user",
        "GOTRUE_SMTP_PASS": "your-smtp-password",
        "GOTRUE_SMTP_SENDER_NAME": "Supabase",
        "STUDIO_DEFAULT_ORGANIZATION": "Default Organization",
        "STUDIO_DEFAULT_PROJECT": "Default Project",
        "SUPABASE_AUTH_ADMIN_EMAIL": "admin@example.com",
        "SUPABASE_AUTH_ADMIN_PASSWORD": "password",
        "FUNCTIONS_VERIFY_JWT": "false",
        "LOGFLARE_API_KEY": "your-logflare-api-key",
        "LOGFLARE_SOURCE_TOKEN": "your-logflare-source-token",
        "VECTOR_API_KEY": "your-vector-api-key",
    }

    console.print("[bold green]Supabase Environment Variable Fix[/bold green]")
    console.print("=" * 50)

    # Find Supabase container files
    systemd_dir = Path("/etc/containers/systemd")

    if not systemd_dir.exists():
        console.print(f"[red]Systemd directory not found: {systemd_dir}[/red]")
        return False

    supabase_files = list(systemd_dir.glob("supabase*.container"))
    console.print(f"[cyan]Found {len(supabase_files)} Supabase container files[/cyan]")

    if not supabase_files:
        console.print("[red]No Supabase container files found to fix[/red]")
        return False

    # Fix each file
    fixed_count = 0

    for file_path in supabase_files:
        console.print(f"[cyan]Processing {file_path.name}...[/cyan]")

        # Create backup
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        if not backup_path.exists():
            backup_path.write_text(file_path.read_text())
            console.print(f"[dim]Created backup: {backup_path}[/dim]")

        # Read file content
        content = file_path.read_text()
        lines = content.split("\n")

        modified = False
        fixed_lines = []

        for line in lines:
            # Process Environment= lines
            if line.strip().startswith("Environment="):
                # Find unset variables (${VAR} without default)
                var_refs = re.findall(r"\$\{([^}:]+)\}", line)

                for var_name in var_refs:
                    if var_name in SUPABASE_ENV_DEFAULTS:
                        # Replace ${VAR} with ${VAR:-default}
                        old_pattern = f"${{{var_name}}}"
                        new_pattern = (
                            f"${{{var_name}:-{SUPABASE_ENV_DEFAULTS[var_name]}}}"
                        )
                        line = line.replace(old_pattern, new_pattern)
                        modified = True
                        console.print(
                            f"[green]  Fixed: {var_name} -> default value[/green]"
                        )
                    else:
                        console.print(
                            f"[yellow]  Warning: No default for {var_name}[/yellow]"
                        )

            fixed_lines.append(line)

        if modified:
            # Write the fixed content
            file_path.write_text("\n".join(fixed_lines))
            console.print(f"[green]✓ Fixed {file_path.name}[/green]")
            fixed_count += 1
        else:
            console.print(f"[dim]  No changes needed for {file_path.name}[/dim]")

    console.print(
        f"\n[cyan]Fixed {fixed_count} out of {len(supabase_files)} files[/cyan]"
    )

    if fixed_count > 0:
        # Reload systemd daemon
        console.print("[yellow]Reloading systemd daemon...[/yellow]")
        try:
            result = systemctl_user(["daemon-reload"])

            if result.returncode == 0:
                console.print("[green]✓ Systemd daemon reloaded[/green]")

                # Reset failed services
                console.print("[yellow]Resetting failed services...[/yellow]")
                systemctl_user(["reset-failed", "supabase*"])
                console.print("[green]✓ Failed services reset[/green]")

                console.print("\n[bold green]Fix completed successfully![/bold green]")
                console.print("[cyan]Next steps:[/cyan]")
                console.print("1. [white]Run: pm reinit supabase[/white]")
                console.print("2. [white]Check status: pm status supabase[/white]")
                console.print(
                    "3. [white]View logs if needed: pm logs supabase-imgproxy[/white]"
                )
                return True
            else:
                console.print(f"[red]Failed to reload daemon: {result.stderr}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]Error reloading daemon: {e}[/red]")
            return False
    else:
        console.print("[yellow]No files needed fixing[/yellow]")
        return True
