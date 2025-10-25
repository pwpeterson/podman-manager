#!/usr/bin/env python3
"""
Command routing and execution logic
"""

import subprocess

from rich.table import Table

from ai_analyzer import ai_analyzer
from core.config import console, set_verbose
from utils.supabase_fixer import fix_supabase_environment_variables


class CommandRouter:
    """Routes commands to appropriate handlers"""

    def __init__(
        self, manager, container_ops, display, selected_mode=None, detector=None
    ):
        self.manager = manager
        self.container_ops = container_ops
        self.display = display
        self.selected_mode = "quadlet"  # Always quadlet mode
        self.detector = detector  # Keep for compatibility but not used
        self.ai_agent = None  # Store AI agent selection

    def handle_command_verbose(self, args):
        """Handle command-specific verbose flags"""
        if hasattr(args, "verbose") and args.verbose:
            set_verbose(True)

    def _resolve_ai_agent_name(self, short_name):
        """Convert short AI agent names to full names"""
        if not short_name or short_name is True:
            return None

        # Mapping of short names to full agent names
        agent_mapping = {
            "qwen25": "vllm-qwen25",
            "glm46": "vllm-glm46",
            "claude": "claude-sonnet",
            "gpt4": "gpt-4",
            "gpt-4": "gpt-4",  # Allow both formats
            "claude-sonnet": "claude-sonnet",  # Allow full names too
            "vllm-qwen25": "vllm-qwen25",
            "vllm-glm46": "vllm-glm46",
        }

        return agent_mapping.get(short_name.lower(), short_name)

    def _detect_podman_error(
        self, result, command_type: str, target: str | None = None
    ) -> bool:
        """Detect if a command result indicates a Podman-related error that should trigger AI analysis"""
        if not result or result is True:
            return False

        # Check for common Podman error patterns
        error_patterns = [
            "error",
            "failed",
            "cannot",
            "unable to",
            "connection refused",
            "timeout",
            "permission denied",
            "no such container",
            "no such image",
            "port already in use",
            "network not found",
            "volume not found",
            "image pull failed",
            "container creation failed",
            "service failed",
            "unit failed",
            "systemd",
            "quadlet",
        ]

        # If result is False (operation failed), that's an error
        if result is False:
            return True

        # If result is a subprocess result with non-zero return code
        if hasattr(result, "returncode") and result.returncode != 0:
            return True

        # Check stderr/stdout for error patterns if available
        if hasattr(result, "stderr") and result.stderr:
            error_text = result.stderr.lower()
            if any(pattern in error_text for pattern in error_patterns):
                return True

        if hasattr(result, "stdout") and result.stdout:
            output_text = result.stdout.lower()
            if any(pattern in output_text for pattern in error_patterns):
                return True

        return False

    def _trigger_automatic_ai_analysis(
        self,
        command_type: str,
        target: str,
        error_context: dict | None = None,
        ai_agent: str | None = None,
    ):
        """Automatically trigger AI analysis when Podman errors are detected"""
        from core.config import _verbose_enabled

        try:
            # Show error detection message
            console.print(f"\n[red]Error found in {command_type} command[/red]\n")
            console.print("[green]Starting AI analysis and diagnostics...[/green]")

            # Initialize AI analyzer with manager if not already done
            if ai_analyzer.manager is None:
                ai_analyzer.manager = self.manager

            # Determine analysis type based on command
            analysis_type_mapping = {
                "reinit": "reinit_failure",
                "start": "reinit_failure",
                "restart": "reinit_failure",
                "build": "build_failure",
                "logs": "logs",
                "status": "status",
            }

            analysis_type = analysis_type_mapping.get(command_type, "logs")

            # Prepare context data
            context_data = error_context or {}
            if command_type in ["reinit", "start", "restart"]:
                context_data["start_error"] = "Service failed to start/restart"

            # Resolve AI agent name if provided
            resolved_ai_agent = (
                self._resolve_ai_agent_name(ai_agent) if ai_agent else None
            )

            # Run AI analysis with verbose mode from global config
            result = ai_analyzer.ai_analyze(
                analysis_type=analysis_type,
                target=target or "unknown",
                context_data=context_data,
                ai_agent=resolved_ai_agent,
                verbose=_verbose_enabled,  # Use global verbose setting
            )

            if result:
                console.print("[green]AI analysis completed.[/green]")
                console.print()
            else:
                console.print()
                console.print(
                    "[yellow]⚠ AI analysis was unable to provide insights[/yellow]"
                )

        except Exception as e:
            console.print(f"[red]AI analysis failed: {e}[/red]")

    def try_with_fallback(self, operation_func, *operation_args, **operation_kwargs):
        """Execute operation in quadlet mode with AI analysis on Podman errors"""
        target = operation_kwargs.get(
            "target", operation_args[0] if operation_args else ""
        )

        # Determine command type from function name
        command_type = (
            operation_func.__name__.replace("_", "")
            .replace("container", "")
            .replace("ops", "")
        )
        if hasattr(operation_func, "__self__"):
            # Extract method name for better command type detection
            method_name = operation_func.__name__
            if "reinit" in method_name:
                command_type = "reinit"
            elif "start" in method_name:
                command_type = "start"
            elif "restart" in method_name:
                command_type = "restart"
            elif "build" in method_name or "rebuild" in method_name:
                command_type = "build"
            elif "stop" in method_name:
                command_type = "stop"

        try:
            result = operation_func(*operation_args, **operation_kwargs)

            # Check if this is a Podman-related error that should trigger AI analysis
            if self._detect_podman_error(result, command_type, target):
                self._trigger_automatic_ai_analysis(
                    command_type,
                    target,
                    {
                        "operation": operation_func.__name__,
                        "args": operation_args,
                        "kwargs": operation_kwargs,
                    },
                    ai_agent=self.ai_agent,
                )

            return result
        except Exception as e:
            console.print(f"[red]Operation failed: {e}[/red]")

            # Trigger AI analysis for exceptions as well
            self._trigger_automatic_ai_analysis(
                command_type,
                target,
                {
                    "operation": operation_func.__name__,
                    "exception": str(e),
                    "args": operation_args,
                    "kwargs": operation_kwargs,
                },
                ai_agent=self.ai_agent,
            )

            return False

    def route_command(self, args):
        """Route command to appropriate handler"""
        command = args.command

        # Store AI agent selection for use in error analysis
        self.ai_agent = getattr(args, "ai_agent", None)

        # Status and information commands
        if command == "list":
            return self._handle_list(args)
        elif command == "ps":
            return self._handle_ps(args)
        elif command == "help":
            return self._handle_help(args)
        elif command == "help-podman":
            return self._handle_help_podman(args)
        elif command == "images":
            return self._handle_images(args)
        elif command == "stats":
            return self._handle_stats(args)
        elif command == "targets":
            return self._handle_targets(args)
        elif command == "ai-agents":
            return self._handle_ai_agents(args)
        elif command == "set-default-ai":
            return self._handle_set_default_ai(args)
        elif command == "colors":
            return self._handle_colors(args)

        # Resource commands
        elif command == "logs":
            return self._handle_logs(args)
        elif command == "diagnose":
            return self._handle_diagnose(args)
        elif command == "exec":
            return self._handle_exec(args)
        elif command == "volumes":
            return self._handle_volumes(args)
        elif command == "networks":
            return self._handle_networks(args)
        elif command == "prune":
            return self._handle_prune(args)
        elif command == "system-df":
            return self._handle_system_df(args)

        # Service lifecycle commands
        elif command == "reinit":
            return self._handle_reinit(args)
        elif command == "build":
            return self._handle_build(args)
        elif command == "start":
            return self._handle_start(args)
        elif command == "stop":
            return self._handle_stop(args)
        elif command == "down":
            return self._handle_down(args)
        elif command == "restart":
            return self._handle_restart(args)
        elif command == "enable":
            return self._handle_enable(args)
        elif command == "disable":
            return self._handle_disable(args)
        elif command == "reset-failed":
            return self._handle_reset_failed(args)
        elif command == "show-service-file":
            return self._handle_show_service_file(args)

        # Image and update commands
        elif command == "install":
            return self._handle_install(args)
        elif command == "uninstall":
            return self._handle_uninstall(args)
        elif command == "update":
            return self._handle_update(args)
        elif command == "auto-update":
            return self._handle_auto_update(args)
        elif command == "reload":
            return self._handle_reload(args)
        elif command == "refresh":
            return self._handle_refresh(args)
        elif command == "fix-supabase-env":
            return self._handle_fix_supabase_env(args)

        else:
            console.print(f"[red]Unknown command: {command}[/red]")
            console.print("[dim]Use --help to see available commands[/dim]")
            return False

    # Status and information command handlers
    def _handle_list(self, args):
        if args.target:
            self.display.show_status(args.target)
        else:
            self.display.show_status()
        return True

    def _handle_ps(self, args):
        try:
            result = subprocess.run(
                [
                    "podman",
                    "ps",
                    "-a",
                    "--format",
                    "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Create table without borders
                table = Table(show_header=True, box=None, padding=(0, 1))
                table.add_column("ID", style="cyan", no_wrap=True)
                table.add_column("Names", style="green")
                table.add_column("Status", style="yellow")
                table.add_column("Ports", style="blue")

                # Parse the output and add rows
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if line.strip():  # Skip empty lines
                        parts = line.split("\t")
                        if len(parts) >= 4:
                            table.add_row(parts[0], parts[1], parts[2], parts[3])
                        elif len(parts) == 3:
                            table.add_row(parts[0], parts[1], parts[2], "")
                        elif len(parts) == 2:
                            table.add_row(parts[0], parts[1], "", "")
                        elif len(parts) == 1:
                            table.add_row(parts[0], "", "", "")

                console.print(table)
                return True
            else:
                console.print(f"[red]Error running podman ps: {result.stderr}[/red]")

                # Trigger automatic AI analysis for podman ps errors
                self._trigger_automatic_ai_analysis(
                    "ps",
                    "system",
                    {
                        "operation": "podman_ps",
                        "error": result.stderr,
                        "returncode": result.returncode,
                    },
                    ai_agent=self.ai_agent,
                )

                return False
        except subprocess.TimeoutExpired:
            console.print("[red]Timeout running podman ps[/red]")

            # Trigger automatic AI analysis for timeout
            self._trigger_automatic_ai_analysis(
                "ps",
                "system",
                {"operation": "podman_ps", "error": "Command timeout", "timeout": 10},
                ai_agent=self.ai_agent,
            )

            return False
        except FileNotFoundError:
            console.print("[red]Podman command not found. Please install podman.[/red]")

            # Trigger automatic AI analysis for missing podman
            self._trigger_automatic_ai_analysis(
                "ps",
                "system",
                {
                    "operation": "podman_ps",
                    "error": "Podman command not found - installation issue",
                },
                ai_agent=self.ai_agent,
            )

            return False
        except Exception as e:
            console.print(f"[red]Error running podman ps: {e}[/red]")

            # Trigger automatic AI analysis for general errors
            self._trigger_automatic_ai_analysis(
                "ps",
                "system",
                {"operation": "podman_ps", "exception": str(e)},
                ai_agent=self.ai_agent,
            )

            return False

    def _handle_help(self, args):
        from cli.help_formatter import show_rich_help

        show_rich_help()
        return True

    def _handle_help_podman(self, args):
        try:
            result = subprocess.run(
                ["podman", "--help"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                console.print("[bold blue]Podman Help Documentation[/bold blue]")
                console.print("=" * 50)
                # Print without markup parsing to avoid Rich markup conflicts
                console.print(result.stdout, markup=False)
                return True
            else:
                console.print(
                    f"[red]Error running podman --help: {result.stderr}[/red]"
                )
                return False
        except subprocess.TimeoutExpired:
            console.print("[red]Timeout running podman --help[/red]")
            return False
        except FileNotFoundError:
            console.print("[red]Podman command not found. Please install podman.[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error running podman --help: {e}[/red]")
            return False

    def _handle_images(self, args):
        self.display.show_images(show_all=args.all)
        return True

    def _handle_stats(self, args):
        self.display.show_stats(follow=args.follow)
        return True

    def _handle_targets(self, args):
        if self.detector:
            available_targets = self.detector.list_available_targets()
        else:
            available_targets = {"quadlet": []}

        table = Table(
            show_header=True, header_style="bold magenta", title="Available Targets"
        )
        table.add_column("Type", style="cyan", no_wrap=True)
        table.add_column("Targets", style="white")

        if available_targets["quadlet"]:
            table.add_row("Quadlet Services", ", ".join(available_targets["quadlet"]))
        else:
            table.add_row("Quadlet Services", "No targets found")

        console.print(table)

        # Show current mode
        console.print(f"\n[dim]Current mode: {self.selected_mode}[/dim]")
        return True

    # Resource command handlers
    def _handle_logs(self, args):
        try:
            # Store AI agent from command-specific argument if provided, otherwise use global
            ai_agent = getattr(args, "ai_agent", None) or self.ai_agent

            # If AI agent is specified, trigger AI analysis directly
            if ai_agent:
                console.print(
                    f"[green]Performing AI log analysis with {ai_agent}...[/green]"
                )

                # Initialize AI analyzer with manager if not already done
                if ai_analyzer.manager is None:
                    ai_analyzer.manager = self.manager

                # Resolve AI agent name
                resolved_ai_agent = self._resolve_ai_agent_name(ai_agent)

                # Trigger AI analysis directly for logs
                from core.config import _verbose_enabled

                result = ai_analyzer.ai_analyze(
                    analysis_type="logs",
                    target=args.target,
                    context_data={"lines": 100},  # Use 100 lines as requested
                    ai_agent=resolved_ai_agent,
                    verbose=_verbose_enabled or getattr(args, "verbose", False),
                )

                if result:
                    console.print("[green]AI log analysis completed.[/green]")
                    console.print()
                else:
                    console.print(
                        "[yellow]⚠ AI analysis was unable to provide insights[/yellow]"
                    )
            else:
                # Show logs normally without AI analysis
                self.container_ops.show_logs(args.target, follow=args.follow)

            return True
        except Exception as e:
            console.print(f"[red]Error showing logs: {e}[/red]")

            # Use command-specific AI agent if provided, otherwise fall back to global
            ai_agent = getattr(args, "ai_agent", None) or self.ai_agent

            # Trigger automatic AI analysis for log viewing errors
            self._trigger_automatic_ai_analysis(
                "logs",
                args.target,
                {
                    "operation": "show_logs",
                    "exception": str(e),
                    "follow": args.follow,
                },
                ai_agent=ai_agent,
            )

            return False

    def _handle_diagnose(self, args):
        self.container_ops.diagnose_container_failure(args.target)
        return True

    def _handle_exec(self, args):
        self.container_ops.exec_command(args.target, args.cmd)
        return True

    def _handle_volumes(self, args):
        self.display.show_volumes()
        return True

    def _handle_networks(self, args):
        self.display.show_networks()
        return True

    def _handle_prune(self, args):
        enhanced = not getattr(args, "basic", False)
        quick = getattr(args, "quick", False)
        self.container_ops.prune(enhanced=enhanced, quick=quick)
        return True

    def _handle_system_df(self, args):
        self.container_ops.show_system_df()
        return True

    # Service lifecycle command handlers
    def _handle_reinit(self, args):
        self.handle_command_verbose(args)

        # Determine build type
        build_type = None
        if getattr(args, "build", False):
            build_type = "legacy"  # -b flag (backward compatibility)
        elif getattr(args, "podman_build", False):
            build_type = "podman"
        elif getattr(args, "quadlet_build", False):
            build_type = "quadlet"

        return self.try_with_fallback(
            self.container_ops.reinit, args.target, build_type=build_type
        )

    def _handle_build(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.rebuild, args.target)

    def _handle_start(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(
            self.container_ops.start, args.target, build=getattr(args, "build", False)
        )

    def _handle_stop(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.stop, args.target)

    def _handle_down(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.down, args.target)

    def _handle_restart(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(
            self.container_ops.restart, args.target, build=getattr(args, "build", False)
        )

    def _handle_enable(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.enable, args.target)

    def _handle_disable(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.disable, args.target)

    def _handle_reset_failed(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.reset_failed, args.target)

    def _handle_show_service_file(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.show_service_file, args.target)

    # Image and update command handlers
    def _handle_install(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.install_stack, args.target)

    def _handle_uninstall(self, args):
        return self.try_with_fallback(self.container_ops.uninstall_stack, args.target)

    def _handle_update(self, args):
        return self.try_with_fallback(
            self.container_ops.update_images_and_restart, args.target
        )

    def _handle_auto_update(self, args):
        self.container_ops.check_auto_update_status()
        return True

    def _handle_reload(self, args):
        return self.container_ops.reload_daemon()

    def _handle_refresh(self, args):
        # Hidden refresh command used internally by universal script
        if hasattr(self.manager, "refresh_service_discovery"):
            self.manager.refresh_service_discovery()
        # Also clear any display caches
        if hasattr(self.display, "clear_cache"):
            self.display.clear_cache()
        console.print("[green]Service discovery refreshed[/green]")
        return True

    def _handle_fix_supabase_env(self, args):
        # Fix Supabase environment variable issues
        return fix_supabase_environment_variables()

    def _handle_ai_agents(self, args):
        """Show available AI agents for log analysis"""
        self.handle_command_verbose(args)
        try:
            from ai_system.ai_agents import ai_agent_manager

            ai_agent_manager.show_agents_status()
            return True
        except ImportError:
            console.print("[red]AI agents system not available[/red]")
            return False

    def _handle_set_default_ai(self, args):
        """Set the default AI agent"""
        self.handle_command_verbose(args)
        try:
            from ai_analyzer.config import config
            from ai_system.ai_agents import ai_agent_manager

            # Resolve the agent name
            resolved_agent = self._resolve_ai_agent_name(args.agent_name)

            if not resolved_agent:
                console.print(f"[red]✗ Invalid agent name: {args.agent_name}[/red]")
                console.print("[dim]Run 'pm ai-agents' to see available agents[/dim]")
                return False

            # Set default in both places
            success = ai_agent_manager.set_default_agent(resolved_agent, persist=True)
            if success:
                config.set_default_agent(resolved_agent)
                console.print(
                    f"[green]✓ Default AI agent set to: {resolved_agent}[/green]"
                )
                console.print(
                    f"[dim]Config saved to: {ai_agent_manager.get_config_file_path()}[/dim]"
                )
                return True
            else:
                console.print(
                    f"[red]✗ Failed to set default agent: {resolved_agent} not found[/red]"
                )
                console.print("[dim]Run 'pm ai-agents' to see available agents[/dim]")
                return False
        except ImportError:
            console.print("[red]AI agents system not available[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error setting default AI agent: {e}[/red]")
            return False

    def _handle_colors(self, args):
        """Show available Rich text colors and styles"""
        self.handle_command_verbose(args)
        try:
            from modules.rich_colors_styles import (
                print_colors_and_styles,
                print_compact_color_examples,
            )

            if getattr(args, "compact", False):
                print_compact_color_examples(console)
            else:
                print_colors_and_styles(console)
            return True
        except ImportError as e:
            console.print(f"[red]Error importing color module: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error displaying colors: {e}[/red]")
            return False
