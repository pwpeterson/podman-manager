"""Service lifecycle operations for quadlet containers."""

import subprocess
from typing import Optional

from core.config import console, verbose_print
from core.simple_fuzzy_matcher import find_container
from utils.secure_subprocess import systemctl_user


class ServiceLifecycle:
    """Handles basic service lifecycle operations: start, stop, restart, enable, disable"""

    def __init__(self, manager):
        self.manager = manager
        self._model_manger = None

    @property
    def model_manger(self):
        """Lazy initialization of vLLM manager"""
        if self._model_manger is None:
            from managers.model_manager import ModelManger

            self._model_manger = ModelManger(self.manager)
        return self._model_manger

    def start(self, target: str, build: bool = False) -> bool:
        """Start a service or stack"""
        # Handle mcp-crawl4ai-rag service - prompt to disable roo code mcp service first
        if target == "mcp-crawl4ai-rag":
            console.print(f"\n[green]Starting {target}...[/green]")
            console.print()
            console.print(
                "[red]IMPORTANT[/red] [bright_yellow]Disable the roo code mcp-crawl4ai-rag service before starting[/bright_yellow]"
            )
            console.print(
                "[bright_yellow]Has the roo code mcp-crawl4ai-rag service been disabled? (y/n):[/bright_yellow] ",
                end="",
            )

            # Get user input
            try:
                response = input().strip().lower()
                if response != "y":
                    console.print(
                        "[yellow]Exiting start operation. Please disable the roo code mcp-crawl4ai-rag service first.[/yellow]"
                    )
                    return False
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                return False
            console.print()

        # Handle vLLM model services with enhanced startup monitoring (exclude model-proxy)
        is_vllm_service = (
            "vllm" in target.lower()
            and not target.endswith("-stack")
            and target != "model-proxy"
        )

        if is_vllm_service:
            console.print(
                "[yellow]Detected vLLM service, using enhanced startup monitoring...[/yellow]"
            )
            # Ensure any existing vLLM process is properly stopped first
            if not self.model_manger._cleanup_vllm_port():
                console.print(
                    "[yellow]Warning: Could not properly stop existing vLLM model[/yellow]"
                )
            console.print()

        # PRIORITY 1: Check for stack names first
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._start_stack(project_name)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            return self._start_stack(target)

        # PRIORITY 2.5: Handle special Supabase case
        if target == "supabase":
            return self._start_stack(target)

        # PRIORITY 3: Check if target is already a resolved container name (skip fuzzy matching)
        # This happens when command_router has already resolved the name
        if (
            hasattr(self.manager, "quadlet_services")
            and target in self.manager.quadlet_services
        ):
            return self._start_service_with_build(target, build=build)

        # PRIORITY 4: Try container resolution using fuzzy matching
        container = find_container(target)
        if container:
            return self._start_service_with_build(container["name"], build=build)

        # Fallback to old service name resolution for backward compatibility
        service_name = self.manager._find_service_name(target, "start")
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._start_stack(stack_name)

        return self._start_service_with_build(target, build=build)

    def stop(self, target: str) -> bool:
        """Stop a service or stack"""
        # PRIORITY 1: Check for stack names first
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._stop_stack(project_name)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            return self._stop_stack(target)

        # PRIORITY 3: Try container resolution using fuzzy matching
        container = find_container(target)
        if container:
            return self.manager.stop_service(container["name"])

        # Fallback to old service name resolution for backward compatibility
        service_name = self.manager._find_service_name(target, "stop")
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._stop_stack(stack_name)

        return self.manager.stop_service(target)

    def remove(self, target: str) -> bool:
        """Stop and remove a service or stack"""
        # PRIORITY 1: Check for stack names first
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._remove_stack(project_name)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            return self._remove_stack(target)

        # PRIORITY 3: Try service name resolution
        service_name = self.manager._find_service_name(target, "remove")

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._remove_stack(stack_name)

        return self._remove_service(target)

    def restart(
        self, target: str, build: bool = False, model_model: Optional[str] = None
    ) -> bool:
        """Restart a service or stack"""
        # Clear cache at the start of the operation
        self.manager._clear_auto_match_cache()

        # Handle mcp-crawl4ai-rag service - prompt to disable roo code mcp service first
        if target == "mcp-crawl4ai-rag":
            console.print(f"\n[green]Restarting {target}...[/green]")
            console.print()
            console.print(
                "[red]IMPORTANT[/red] [bright_yellow]Disable the roo code mcp-crawl4ai-rag service before restarting[/bright_yellow]"
            )
            console.print(
                "[bright_yellow]Has the roo code mcp-crawl4ai-rag service been disabled? (y/n):[/bright_yellow] ",
                end="",
            )

            # Get user input
            try:
                response = input().strip().lower()
                if response != "y":
                    console.print(
                        "[yellow]Exiting restart operation. Please disable the roo code mcp-crawl4ai-rag service first.[/yellow]"
                    )
                    return False
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                return False
            console.print()

        # Handle vLLM model switching if specified, or detect vLLM model services automatically (exclude model-proxy)
        is_vllm_service = "vllm" in target.lower() and target not in [
            "model-proxy",
            "vllm-stack",
        ]

        if model_model:
            console.print(
                f"[green]vLLM model switching requested: {model_model}[/green]"
            )
            if not self.model_manger.switch_model_model(model_model):
                console.print("[red]vLLM model switch failed, aborting restart[/red]")
                return False
            console.print()
        elif is_vllm_service:
            # For vLLM services without explicit model switch, ensure proper cleanup
            console.print(
                "[yellow]Detected vLLM service, ensuring proper shutdown...[/yellow]"
            )
            if not self.model_manger._cleanup_vllm_port():
                console.print(
                    "[yellow]Warning: Could not properly stop current vLLM model[/yellow]"
                )
            console.print()

        # PRIORITY 1: Check for stack names first
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._restart_stack(project_name)

        # PRIORITY 2: Check if target might be a stack name without -stack suffix
        stack_variant = f"{target}-stack"
        if (
            hasattr(self.manager, "stack_services")
            and stack_variant in self.manager.stack_services
        ):
            return self._restart_stack(target)

        # PRIORITY 3: Try container resolution using fuzzy matching
        container = find_container(target)
        if container:
            container_name = container["name"]
            service_name = f"{container_name}.service"
        else:
            # Fallback to old service name resolution for backward compatibility
            service_name = self.manager._find_service_name(target, "restart")

            # Handle stack operations (STACK: prefix)
            if service_name and service_name.startswith("STACK:"):
                stack_name = service_name[6:]  # Remove "STACK:" prefix
                return self._restart_stack(stack_name)

        # If we found a service, call manager.restart_service directly to avoid duplicate resolution
        if service_name:
            if build:
                # Stop first - use resolved container name if available
                stop_target = (
                    container_name.replace(".service", "") if container else target
                )
                self.manager.stop_service(stop_target, quiet=True)
                # Build - delegate to container_builder
                from operations.container_builder import ContainerBuilder

                builder = ContainerBuilder(self.manager)
                build_target = (
                    container_name.replace(".service", "") if container else target
                )
                if not builder.build_service(build_target):
                    return False
                # Reload daemon
                self.manager.reload_daemon()

            # Show restarting message and call systemctl restart directly since we already resolved the service name
            console.print()
            console.print(
                f"[green]Restarting {service_name.replace('.service', '')}...[/green]"
            )
            verbose_print(
                f"  [cyan]exec: systemctl --user restart {service_name}[/cyan]"
            )

            cmd = ["systemctl", "--user", "restart", service_name]
            result = self.manager._run_systemctl_command(
                cmd, f"restart_{target}", suppress_errors=True, quiet=True
            )

            if result.returncode == 0:
                console.print(f"  [green]Restarted {service_name}[/green]")

                # Handle mcp-crawl4ai-rag service - prompt to re-enable roo code mcp service
                if target == "mcp-crawl4ai-rag":
                    console.print("  ")
                    console.print(
                        "[red]IMPORTANT[/red] [bright_yellow]Enable the roo code mcp-crawl4ai-rag service[/bright_yellow]"
                    )
                    console.print(
                        "[bright_yellow]Has the roo code mcp-crawl4ai-rag service been enabled? (y/n):[/bright_yellow] ",
                        end="",
                    )

                    # Get user input
                    try:
                        response = input().strip().lower()
                        if response != "y":
                            console.print(
                                "[bright_red]mcp-crawl4ai-rag will not work until re-enabled[/bright_red]"
                            )
                    except (KeyboardInterrupt, EOFError):
                        console.print(
                            "\n[bright_red]mcp-crawl4ai-rag will not work until re-enabled[/bright_red]"
                        )
                    console.print()

                return True
            else:
                # Trigger automatic AI analysis for restart failures
                self._trigger_restart_failure_analysis(target, service_name, result)
                return False
        else:
            console.print(f"[red]Service '{target}' not found[/red]")
            return False

    def enable(self, target: str) -> bool:
        """Enable a service or stack to start at boot"""
        service_name = self.manager._find_service_name(target, "enable")

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._enable_stack(stack_name)

        # Handle legacy stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._enable_stack(project_name)

        return self.manager.enable_service(target)

    def disable(self, target: str) -> bool:
        """Disable a service or stack from starting at boot"""
        service_name = self.manager._find_service_name(target, "disable")

        # Handle stack operations (STACK: prefix)
        if service_name and service_name.startswith("STACK:"):
            stack_name = service_name[6:]  # Remove "STACK:" prefix
            return self._disable_stack(stack_name)

        # Handle legacy stack targets
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            return self._disable_stack(project_name)

        return self.manager.disable_service(target)

    def reset_failed(self, target: str) -> bool:
        """Reset failed service state"""
        self.manager._clear_auto_match_cache()

        # Try container resolution using fuzzy matching first
        container = find_container(target)
        if container:
            service_name = f"{container['name']}.service"
        else:
            # Check if container file exists first
            if not self.manager._check_container_file_exists(target):
                self.manager._show_install_suggestion(target)
                return False

            service_name = self.manager._find_service_name(target)

            if not service_name:
                console.print(f"[red]Service '{target}' not found[/red]")
                return False
            elif service_name == "CANCELLED":
                return False

        console.print(f"[yellow]Resetting failed state for {target}...[/yellow]")

        cmd = ["systemctl", "--user", "reset-failed", service_name]
        verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            result = systemctl_user(["reset-failed", service_name])
            if result.returncode == 0:
                console.print(
                    f"[green]Successfully reset failed state for {target}[/green]"
                )
                return True
            else:
                console.print(
                    f"[red]Failed to reset failed state: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
                )
                return False
        except Exception as e:
            console.print(f"[red]Error resetting failed state: {e}[/red]")
            return False

    def show_service_file(self, target: str) -> bool:
        """Show service file contents"""
        self.manager._clear_auto_match_cache()

        # Try container resolution using fuzzy matching first
        container = find_container(target)
        if container:
            service_name = f"{container['name']}.service"
        else:
            # Check if container file exists first
            if not self.manager._check_container_file_exists(target):
                self.manager._show_install_suggestion(target)
                return False

            service_name = self.manager._find_service_name(target)

            if not service_name:
                console.print(f"[red]Service '{target}' not found[/red]")
                return False
            elif service_name == "CANCELLED":
                return False

        console.print(f"[yellow]Showing service file for {target}...[/yellow]")

        cmd = ["systemctl", "--user", "cat", service_name]
        verbose_print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

        try:
            result = systemctl_user(["cat", service_name])
            if result.returncode == 0:
                console.print(f"\n[bold cyan]=== {service_name} ===[/bold cyan]")
                console.print(result.stdout)
                return True
            else:
                console.print(
                    f"[red]Failed to show service file: {result.stderr.strip() if result.stderr else 'Unknown error'}[/red]"
                )
                return False
        except Exception as e:
            console.print(f"[red]Error showing service file: {e}[/red]")
            return False

    def show_service_status(self, target: str) -> None:
        """Show detailed status for a specific service"""
        self.manager._clear_auto_match_cache()

        # Handle legacy stack targets first
        if target.endswith("-stack"):
            project_name = target[:-6]  # Remove "-stack" suffix
            self._show_stack_status(project_name)
            return

        # Try container resolution using fuzzy matching
        container = find_container(target)
        if container:
            service_name = f"{container['name']}.service"
        else:
            # Fallback to old service name resolution
            service_name = self.manager._find_service_name(target)

            # Handle stack operations (STACK: prefix)
            if service_name and service_name.startswith("STACK:"):
                stack_name = service_name[6:]  # Remove "STACK:" prefix
                self._show_stack_status(stack_name)
                return

            if not service_name:
                # When service_name is None, it could be due to user cancellation
                # The fuzzy matcher already showed "Selection cancelled" message
                # so we don't need to show an additional error message
                return

        # Use systemctl status for detailed output
        from core.config import _verbose_enabled

        cmd = ["systemctl", "--user", "status", service_name]
        if _verbose_enabled:
            console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")
        console.print("\n[green]Service Status:[/green]")

        try:
            result = systemctl_user(["status", service_name])
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[yellow]{result.stderr}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error getting service status: {e}[/red]")

    def reload_daemon(self) -> bool:
        """Reload systemd user daemon"""
        return self.manager.reload_daemon()

    def _get_stack_services(self, project: str) -> list[str]:
        """Get list of services for a project stack"""
        # Normalize project name to stack name format
        if not project.endswith("-stack"):
            stack_name = f"{project}-stack"
        else:
            stack_name = project

        # Look up in discovered stack services
        if (
            hasattr(self.manager, "stack_services")
            and stack_name in self.manager.stack_services
        ):
            return self.manager.stack_services[stack_name]

        # If not found, return empty list
        return []

    def _start_stack(self, project: str) -> bool:
        """Start all services in a project stack"""
        # Handle Supabase with special startup order
        if project == "supabase":
            from managers.supabase_stack_manager import SupabaseStackManager

            supabase_mgr = SupabaseStackManager(self.manager)
            return supabase_mgr.start_supabase_stack()

        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Starting {project} stack...[/yellow]")

        success = True
        for service in services:
            if not self.manager.start_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully started {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to start[/yellow]"
            )
        return success

    def _stop_stack(self, project: str) -> bool:
        """Stop all services in a project stack"""
        # Handle Supabase with special shutdown order
        if project == "supabase":
            from managers.supabase_stack_manager import SupabaseStackManager

            supabase_mgr = SupabaseStackManager(self.manager)
            return supabase_mgr.stop_supabase_stack()

        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        success = True
        stopped_services = []
        failed_services = []

        for service in services:
            console.print(f"[green]Stopping {service}...[/green]")
            if self.manager.stop_service(service, quiet=True):
                console.print(f"  [green]Stopped {service}[/green]")
                stopped_services.append(service)
            else:
                console.print(
                    f"  [yellow]{service} was not running or failed to stop[/yellow]"
                )
                failed_services.append(service)
                success = False
            console.print()

        if success:
            console.print(
                f"[green]Successfully stopped {project} stack ({len(stopped_services)} services)[/green]"
            )
        else:
            if stopped_services:
                console.print(
                    f"[yellow]Partially stopped {project} stack: {len(stopped_services)} succeeded, {len(failed_services)} failed[/yellow]"
                )
                console.print(f"[dim]  Stopped: {', '.join(stopped_services)}[/dim]")
                console.print(f"[dim]  Failed: {', '.join(failed_services)}[/dim]")
            else:
                console.print(
                    f"[yellow]No services in {project} stack were running or could be stopped[/yellow]"
                )
        return success

    def _restart_stack(self, project: str) -> bool:
        """Restart all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print()
        console.print(f"[green]Restarting {project} stack...[/green]")
        console.print()

        success = True
        failed_services = []

        for service in services:
            console.print(f"[green]Restarting {service}...[/green]")
            verbose_print(f"  [cyan]exec: systemctl --user restart {service}[/cyan]")

            # Get the service name for direct systemctl call to capture errors
            service_name = self.manager._find_service_name(service, "restart")
            if service_name and not service_name.startswith("STACK:"):
                cmd = ["systemctl", "--user", "restart", service_name]
                result = self.manager._run_systemctl_command(
                    cmd, f"restart_{service}", suppress_errors=True, quiet=True
                )

                if result.returncode == 0:
                    console.print(f"  [green]Restarted {service_name}[/green]")
                    console.print()
                else:
                    success = False
                    failed_services.append(service)
                    # Show concise error message with troubleshooting guidance
                    console.print(
                        f"  [red]Failed to restart {service}. Use [/red][white]pm restart {service}[/white][red] to troubleshoot.[/red]"
                    )
                    console.print()
            else:
                # Fallback to original method if service name resolution fails
                if not self.manager.restart_service(service):
                    success = False
                    failed_services.append(service)
                    console.print(
                        f"  [red]Failed to restart {service}. Use [/red][white]pm restart {service}[/white][red] to troubleshoot.[/red]"
                    )
                    console.print()

        if success:
            console.print(f"[green]Successfully restarted {project} stack[/green]")
            console.print()  # Add newline after successful stack restart
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to restart[/yellow]"
            )
            console.print()
            # No AI analysis for stack restarts - just show the troubleshooting messages above
        return success

    def _enable_stack(self, project: str) -> bool:
        """Enable all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Enabling {project} stack...[/yellow]")
        success = True
        for service in services:
            console.print(f"[dim]  Enabling {service}...[/dim]")
            if not self.manager.enable_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully enabled {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to enable[/yellow]"
            )
        return success

    def _disable_stack(self, project: str) -> bool:
        """Disable all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print(f"[yellow]Disabling {project} stack...[/yellow]")
        success = True
        for service in services:
            console.print(f"[dim]  Disabling {service}...[/dim]")
            if not self.manager.disable_service(service):
                success = False

        if success:
            console.print(f"[green]Successfully disabled {project} stack[/green]")
        else:
            console.print(
                f"[yellow]Some services in {project} stack failed to disable[/yellow]"
            )
        return success

    def _show_stack_status(self, project: str) -> None:
        """Show status for all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return

        console.print(f"[bold cyan]{project.title()} Stack Status[/bold cyan]")

        for service in services:
            console.print(f"\n[bold yellow]=== {service} ===[/bold yellow]")
            service_name = self.manager._find_service_name(service, "status")
            if service_name:
                cmd = [
                    "systemctl",
                    "--user",
                    "status",
                    service_name,
                    "--no-pager",
                    "-l",
                ]
                console.print(f"[cyan]exec: {' '.join(cmd)}[/cyan]")

                try:
                    result = systemctl_user(
                        ["status", service_name, "--no-pager", "-l"]
                    )
                    if result.stdout:
                        console.print(result.stdout)
                    if result.stderr:
                        console.print(f"[yellow]{result.stderr}[/yellow]")
                except Exception as e:
                    console.print(f"[red]Error getting status for {service}: {e}[/red]")
            else:
                console.print(f"[red]Service '{service}' not found[/red]")

    def _start_service_with_build(self, target: str, build: bool = False) -> bool:
        """Start a service with optional build"""
        if build:
            from operations.container_builder import ContainerBuilder

            builder = ContainerBuilder(self.manager)
            if not builder.build_service(target):
                return False

        result = self.manager.start_service(target)

        # Handle mcp-crawl4ai-rag service - prompt to re-enable roo code mcp service after successful start
        if result and target == "mcp-crawl4ai-rag":
            console.print("  ")
            console.print(
                "[red]IMPORTANT[/red] [bright_yellow]Enable the roo code mcp-crawl4ai-rag service[/bright_yellow]"
            )
            console.print(
                "[bright_yellow]Has the roo code mcp-crawl4ai-rag service been enabled? (y/n):[/bright_yellow] ",
                end="",
            )

            # Get user input
            try:
                response = input().strip().lower()
                if response != "y":
                    console.print(
                        "[bright_red]mcp-crawl4ai-rag will not work until re-enabled[/bright_red]"
                    )
            except (KeyboardInterrupt, EOFError):
                console.print(
                    "\n[bright_red]mcp-crawl4ai-rag will not work until re-enabled[/bright_red]"
                )
            console.print()

        return result

    def _trigger_restart_failure_analysis(
        self, target: str, service_name: str, result
    ) -> None:
        """Trigger automatic AI analysis when restart fails"""
        try:
            from ai_analyzer import ai_analyzer
            from core.config import _verbose_enabled

            # Initialize AI analyzer with manager if not already done
            if ai_analyzer.manager is None:
                ai_analyzer.manager = self.manager

            # Prepare context data for restart failure analysis
            context_data = {
                "operation": "restart",
                "service_name": service_name,
                "target": target,
                "restart_error": "Service failed to restart",
                "error_output": (
                    result.stderr if hasattr(result, "stderr") and result.stderr else ""
                ),
                "return_code": (
                    result.returncode if hasattr(result, "returncode") else 1
                ),
            }

            # Run AI analysis with verbose mode from global config
            ai_analyzer.ai_analyze(
                analysis_type="reinit_failure",
                target=target,
                context_data=context_data,
                ai_agent=None,  # Use default agent
                verbose=_verbose_enabled,
            )

        except Exception:
            # Silently handle AI analysis failures
            pass

    def _remove_stack(self, project: str) -> bool:
        """Stop and remove all services in a project stack"""
        services = self._get_stack_services(project)
        if not services:
            console.print(f"[red]No services found for {project} stack[/red]")
            return False

        console.print()
        console.print(f"[green]Stopping and removing {project}-stack...[/green]")

        success = True
        removed_services = []
        failed_services = []

        for service in services:
            console.print(f"  Stopping and removing {service}...")
            if self._remove_service(service, quiet=True):
                removed_services.append(service)
            else:
                failed_services.append(service)
                success = False

        if success:
            console.print(
                f"[green]Successfully removed {project} stack ({len(removed_services)} services)[/green]"
            )
        else:
            if removed_services:
                console.print(
                    f"[yellow]Partially removed {project} stack: {len(removed_services)} succeeded, {len(failed_services)} failed[/yellow]"
                )
                console.print(f"[dim]  Removed: {', '.join(removed_services)}[/dim]")
                console.print(f"[dim]  Failed: {', '.join(failed_services)}[/dim]")
            else:
                console.print(
                    f"[yellow]No services in {project} stack could be removed[/yellow]"
                )
        return success

    def _remove_service(self, target: str, quiet: bool = False) -> bool:
        """Stop and remove a single service"""
        if not quiet:
            console.print()
            console.print(f"[green]Stopping and removing {target}...[/green]")
            console.print()

        # First stop the service - show stopping phase
        if not quiet:
            console.print(f"[green]Stopping  {target}...[/green]")

        if not self.manager.stop_service(target, force=True, quiet=True):
            if not quiet:
                console.print(f"  [yellow]Warning: Could not stop {target}[/yellow]")
        else:
            if not quiet:
                console.print(f"  [green]Stopped {target}[/green]")
                console.print()

        # Try container resolution using fuzzy matching first
        container = find_container(target)
        if container:
            container_name = container["name"]
        else:
            # Fallback to old service name resolution
            service_name = self.manager._find_service_name(target, "remove")
            if not service_name or service_name.startswith("STACK:"):
                if not quiet:
                    console.print(
                        f"[red]Could not resolve service name for {target}[/red]"
                    )
                return False

            # Extract container name (remove .service suffix if present)
            container_name = (
                service_name.replace(".service", "")
                if service_name.endswith(".service")
                else service_name
            )

        # Use systemctl --user to stop the service (safer for Quadlet services)
        # Container removal is handled automatically by systemctl service lifecycle
        try:
            service_name = f"{container_name}.service"

            # Stop the service using systemctl --user
            stop_cmd = ["systemctl", "--user", "stop", service_name]
            verbose_print(f"[cyan]exec: {' '.join(stop_cmd)}[/cyan]")
            result = systemctl_user(["stop", service_name], timeout=30)

            if not quiet:
                console.print(f"[green]Removing {target}...[/green]")
                if result.returncode == 0:
                    console.print(
                        f"  [green]Removed {target} (systemctl handles container cleanup)[/green]"
                    )
                else:
                    console.print(
                        f"  [yellow]Service {service_name} was not running or already stopped[/yellow]"
                    )

            # Always return True since systemctl handles the lifecycle properly
            # Even if the service wasn't running, the "removal" is successful
            return True

        except subprocess.TimeoutExpired:
            if not quiet:
                console.print(f"[red]Timeout stopping service {service_name}[/red]")
            return False
        except Exception as e:
            if not quiet:
                console.print(f"[red]Error stopping service {service_name}: {e}[/red]")
            return False
