#!/usr/bin/env python3
"""
Command routing and execution logic
"""

import re
import subprocess  # nosec B404 - using secure_subprocess wrapper
from typing import Optional

from rich.table import Table

from ai_analyzer import get_ai_analyzer
from core.config import console, set_verbose
from operations.common_actions import CommonActionsFormatter
from utils.secure_subprocess import SecureSubprocessError, secure_run
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
        self.ai_model = (
            None  # Store AI model selection (abacus-proxy model id override)
        )
        self.common_actions = (
            CommonActionsFormatter()
        )  # Initialize common actions formatter

    def handle_command_verbose(self, args):
        """Handle command-specific verbose flags"""
        if hasattr(args, "verbose") and args.verbose:
            set_verbose(True)

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
        ai_model: str | None = None,
    ):
        """Automatically trigger AI analysis when Podman errors are detected"""
        from core.config import _verbose_enabled

        try:
            # Show error detection message
            console.print(f"\n[red]Error found in {command_type} command[/red]\n")
            console.print("[green]Starting AI analysis and diagnostics...[/green]")

            analyzer = get_ai_analyzer(self.manager)

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

            # Optional model override (interpreted as an abacus-proxy model id)
            resolved_ai_model = ai_model

            # Run AI analysis with verbose mode from global config
            result = analyzer.ai_analyze(
                analysis_type=analysis_type,
                target=target or "unknown",
                context_data=context_data,
                ai_model=resolved_ai_model,
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
            console.print(f"[red]AI analysis failed: {e}[/red]", markup=False)

    def _resolve_container_name_once(self, target: str) -> str:
        """Resolve container name once using fuzzy matching to avoid duplicate prompts"""
        try:
            from core.simple_fuzzy_matcher import find_container

            # Check if this is a stack target to avoid fuzzy matching
            is_stack_target = target.endswith(
                "-stack"
            ) or self._has_corresponding_stack_directory(target)

            if not is_stack_target:
                container = find_container(target)
                if container:
                    return container["name"]

            # Return original target if no container found or is stack target
            return target
        except Exception:
            # If fuzzy matching fails, return original target
            return target

    def _has_corresponding_stack_directory(self, target: str) -> bool:
        """Check if a target has a corresponding -stack directory in the quadlets source."""
        try:
            from pathlib import Path

            quadlets_source_dir = Path("/home/pwp/srv/local-ai-packaged/quadlets")
            if not quadlets_source_dir.exists():
                return False

            # Check if target-stack directory exists
            stack_dir = quadlets_source_dir / f"{target}-stack"
            return stack_dir.exists() and stack_dir.is_dir()
        except Exception:
            return False

    def _show_common_actions_for_command(
        self,
        command_type: str,
        target: str,
        resolved_container_name: Optional[str] = None,
    ):
        """Show common actions after successful command completion"""
        try:
            # Use resolved container name to avoid duplicate fuzzy matching
            container_name = resolved_container_name or target

            # Show comprehensive actions for all commands using detailed format
            if command_type in ["reinit", "restart"]:
                # Show comprehensive actions for reinit and restart with all categories
                self.common_actions.show_common_actions(
                    target=target,
                    container_name=container_name,
                    categories=[
                        "pm_shortcuts",
                        "service_status",
                        "logs_diagnostics",
                        "troubleshooting",
                    ],
                )
            elif command_type in [
                "install",
                "start",
                "enable",
                "build",
            ]:
                self.common_actions.show_common_actions(
                    target=target,
                    container_name=container_name,
                    categories=["pm_shortcuts", "service_status", "logs_diagnostics"],
                )
            elif command_type in ["stop", "disable", "reset", "uninstall"]:
                # For stop/disable commands, show different essential actions
                self.common_actions.show_common_actions(
                    target=target,
                    container_name=container_name,
                    categories=[
                        "service_status",
                        "logs_diagnostics",
                        "troubleshooting",
                    ],
                )
            else:
                # Default essential actions for other commands
                self.common_actions.show_common_actions(
                    target=target,
                    container_name=container_name,
                    categories=["pm_shortcuts", "service_status", "logs_diagnostics"],
                )
        except Exception as e:
            # Don't let common actions display errors break the main command
            console.print(
                f"[dim]Note: Could not display additional actions ({e})[/dim]"
            )

    def try_with_fallback(self, operation_func, *operation_args, **operation_kwargs):
        """Execute operation in quadlet mode with AI analysis on Podman errors"""
        target = operation_kwargs.get(
            "target", operation_args[0] if operation_args else ""
        )

        # Resolve container name once to avoid duplicate fuzzy matching prompts
        resolved_container_name = self._resolve_container_name_once(target)

        # Pass resolved container name to avoid duplicate fuzzy matching
        if resolved_container_name != target:
            # Update the target in args/kwargs to use resolved name
            if operation_args:
                operation_args = list(operation_args)
                operation_args[0] = resolved_container_name
                operation_args = tuple(operation_args)
            if "target" in operation_kwargs:
                operation_kwargs["target"] = resolved_container_name

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
            elif "install" in method_name:
                command_type = "install"
            elif "uninstall" in method_name:
                command_type = "uninstall"
            elif "enable" in method_name:
                command_type = "enable"
            elif "disable" in method_name:
                command_type = "disable"
            elif "reset" in method_name:
                command_type = "reset"
            elif "update" in method_name:
                command_type = "update"

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
                    ai_model=self.ai_model,
                )
            elif result is True or (
                hasattr(result, "returncode") and result.returncode == 0
            ):
                # Operation was successful, show common actions (except for install, uninstall, and diag)
                if command_type not in ["install", "uninstall", "diag"]:
                    self._show_common_actions_for_command(
                        command_type, target, resolved_container_name
                    )

            return result
        except Exception as e:
            console.print(f"[red]Operation failed: {e}[/red]", markup=False)

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
                ai_model=self.ai_model,
            )

            return False

    def route_command(self, args):
        """Route command to appropriate handler"""
        command = args.command

        # Store AI model selection for use in error analysis
        # Back-compat: accept legacy args.ai_agent until cli/parser.py is updated.
        self.ai_model = getattr(args, "ai_model", None) or getattr(
            args, "ai_agent", None
        )

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
        elif command == "colors":
            return self._handle_colors(args)

        # Resource commands
        elif command == "logs":
            return self._handle_logs(args)
        elif command == "diag":
            return self._handle_diag(args)
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
        elif command == "enhanced-reinit":
            return self._handle_enhanced_reinit(args)
        elif command == "build":
            return self._handle_build(args)
        elif command == "start":
            return self._handle_start(args)
        elif command == "stop":
            return self._handle_stop(args)
        elif command == "remove":
            return self._handle_remove(args)
        elif command == "restart":
            return self._handle_restart(args)

        # vLLM model management commands
        elif command == "vllm-switch":
            return self._handle_vllm_switch(args)
        elif command == "vllm-status":
            return self._handle_vllm_status(args)
        elif command == "vllm-models":
            return self._handle_model_models(args)
        elif command == "vllm-current":
            return self._handle_vllm_current(args)
        elif command == "enable":
            return self._handle_enable(args)
        elif command == "disable":
            return self._handle_disable(args)
        elif command == "reset-failed":
            return self._handle_reset_failed(args)
        elif command == "show-service-file":
            return self._handle_show_service_file(args)

        # Image and update commands
        elif command == "deploy":
            return self._handle_install(args)
        elif command == "dep":
            return self._handle_install(args)
        elif command == "uninstall":
            return self._handle_uninstall(args)
        elif command == "update":
            return self._handle_update(args)
        elif command == "auto-update":
            return self._handle_auto_update(args)
        elif command == "reload":
            return self._handle_reload(args)

        elif command == "fix-supabase-env":
            return self._handle_fix_supabase_env(args)
        elif command == "copy-volumes":
            return self._handle_copy_volumes(args)
        elif command == "list-volumes":
            return self._handle_list_volumes(args)
        elif command == "cleanup-volumes":
            return self._handle_cleanup_volumes(args)

        else:
            console.print(f"[red]Unknown command: {command}[/red]")
            console.print("[dim]Use --help to see available commands[/dim]")
            return False

    # Status and information command handlers
    def _handle_list(self, args):
        self.handle_command_verbose(args)
        if args.target:
            self.display.show_status(args.target)
        else:
            self.display.show_status()
        return True

    def _handle_ps(self, args):
        self.handle_command_verbose(args)

        try:
            cmd = [
                "podman",
                "ps",
                "-a",
                "--format",
                "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}",
            ]

            # Show command in verbose mode with cyan color
            from core.config import _verbose_enabled

            if _verbose_enabled:
                console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

            result = secure_run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                verbose=_verbose_enabled,
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
                    ai_model=self.ai_model,
                )

                return False
        except subprocess.TimeoutExpired:
            console.print("[red]Timeout running podman ps[/red]")

            # Trigger automatic AI analysis for timeout
            self._trigger_automatic_ai_analysis(
                "ps",
                "system",
                {"operation": "podman_ps", "error": "Command timeout", "timeout": 10},
                ai_model=self.ai_model,
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
                ai_model=self.ai_model,
            )

            return False
        except Exception as e:
            console.print(f"[red]Error running podman ps: {e}[/red]")

            # Trigger automatic AI analysis for general errors
            self._trigger_automatic_ai_analysis(
                "ps",
                "system",
                {"operation": "podman_ps", "exception": str(e)},
                ai_model=self.ai_model,
            )

            return False

    def _handle_help(self, args):
        from cli.help_formatter import show_rich_help

        show_rich_help()
        return True

    def _handle_help_podman(self, args):
        try:
            result = secure_run(
                ["podman", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
                verbose=False,
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
    def _strip_ansi_colors(self, text: str) -> str:
        """Remove ANSI color codes from text using multiple patterns"""
        # Remove all ANSI escape sequences
        # Pattern 1: Standard ANSI escape sequences
        text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
        # Pattern 2: More specific color codes
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        # Pattern 3: Cursor and other control sequences
        text = re.sub(r"\x1b\[[0-9;]*[ABCDEFGHIJKLMNOPQRSTUVWXYZ]", "", text)
        # Pattern 4: Alternative format
        text = re.sub(r"\033\[[0-9;]*[a-zA-Z]", "", text)
        # Pattern 5: Remove any remaining escape sequences
        text = re.sub(r"\x1b\[.*?[a-zA-Z]", "", text)
        return text

    def _handle_logs(self, args):
        # Display comprehensive logs using multiple commands
        target = args.target

        # Use fuzzy matching to find container
        from core.simple_fuzzy_matcher import find_container

        container = find_container(target)

        if not container:
            console.print(f"[red]Container '{target}' not found[/red]")
            return False

        container_name = container["name"]

        # Commands to run with their descriptions - using secure subprocess calls
        commands = [
            {
                "name": "Podman Container Logs",
                "cmd": ["podman", "logs", container_name],
                "description": f"podman logs {container_name}",
            },
            {
                "name": "Systemd Service Status",
                "cmd": [
                    "systemctl",
                    "--user",
                    "status",
                    container_name,
                    "--no-pager",
                    "-l",
                    "--plain",
                    "--no-legend",
                ],
                "description": f"sudo systemctl status {container_name} --no-pager -l --plain --no-legend",
            },
            {
                "name": "Systemd Service Logs",
                "cmd": [
                    "journalctl",
                    "--user",
                    "-u",
                    container_name,
                    "-n",
                    "100",
                    "--no-pager",
                    "--no-hostname",
                    "--output=short-precise",
                ],
                "description": f"journalctl --user -u {container_name} -n 100 --no-pager --no-hostname --output=short-precise",
            },
        ]

        # Execute each command and display results
        for cmd_info in commands:
            console.print(f"\n[bold green]{cmd_info['name']}[/bold green]")
            console.print(f"[cyan]Command: {cmd_info['description']}[/cyan]")
            console.print("─" * 80)

            try:
                # Set environment to disable colors
                import os

                env = os.environ.copy()
                env["NO_COLOR"] = "1"
                env["SYSTEMD_COLORS"] = "0"
                env["TERM"] = "dumb"  # Force non-interactive terminal
                env["COLORTERM"] = ""  # Disable color terminal detection

                # Use secure subprocess wrapper
                result = secure_run(
                    cmd_info["cmd"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                    verbose=False,
                )

                if result.returncode == 0:
                    if result.stdout.strip():
                        # Strip ANSI color codes before displaying
                        clean_output = self._strip_ansi_colors(result.stdout)
                        console.print(clean_output, markup=False)
                    else:
                        console.print("[dim]No output[/dim]")
                else:
                    console.print(
                        f"[red]Command failed (exit code {result.returncode})[/red]"
                    )
                    if result.stderr:
                        clean_error = self._strip_ansi_colors(result.stderr.strip())
                        console.print(f"[red]Error: {clean_error}[/red]")

            except SecureSubprocessError as e:
                console.print(f"[red]Security error: {e}[/red]")
            except subprocess.TimeoutExpired:
                console.print("[red]Command timed out after 30 seconds[/red]")
            except FileNotFoundError:
                console.print("[red]Command not found[/red]")
            except Exception as e:
                console.print(f"[red]Error running command: {e}[/red]")

        # Show common actions after successful logs display
        self._show_common_actions_for_command("logs", args.target, container_name)
        return True

    def _handle_diag(self, args):
        # Perform comprehensive diagnostic analysis with optional AI assistance
        try:
            # Store AI model from command-specific argument if provided, otherwise use global
            ai_model = (
                getattr(args, "ai_model", None)
                or getattr(args, "ai_agent", None)
                or self.ai_model
            )

            # Use fuzzy matching to find container
            from core.simple_fuzzy_matcher import find_container

            container = find_container(args.target)

            if not container:
                console.print(f"[red]Container '{args.target}' not found[/red]")
                return False

            container_name = container["name"]

            # Always show troubleshooting message first with container name
            console.print(f"\n[green]Troubleshooting {container_name}...[/green]")
            console.print()

            # Always trigger AI analysis for diagnostics (with optional model override)
            if ai_model:
                console.print(
                    f"[green]Performing AI diagnostic analysis with model {ai_model}...[/green]"
                )
            else:
                console.print("[green]Performing AI diagnostic analysis...[/green]")
            console.print()

            analyzer = get_ai_analyzer(self.manager)

            # Optional model override (interpreted as an abacus-proxy model id)
            resolved_ai_model = ai_model

            # Trigger AI analysis for diagnostics
            from core.config import _verbose_enabled

            result = analyzer.ai_analyze(
                analysis_type="logs",
                target=args.target,
                context_data={"lines": 100},  # Use 100 lines for analysis
                ai_model=resolved_ai_model,
                verbose=_verbose_enabled or getattr(args, "verbose", False),
            )

            if result:
                console.print("[green]AI diagnostic analysis completed.[/green]")
                console.print()
            else:
                console.print(
                    "[yellow]⚠ AI analysis was unable to provide insights[/yellow]"
                )
                # Fallback to basic container diagnosis if AI analysis fails
                console.print(
                    "[cyan]Falling back to basic container diagnosis...[/cyan]"
                )
                self.container_ops.diagnose_container_failure(args.target)

            return True
        except Exception as e:
            console.print(f"[red]Error in diagnostic command: {e}[/red]")

            # Use command-specific AI model if provided, otherwise fall back to global
            ai_model = (
                getattr(args, "ai_model", None)
                or getattr(args, "ai_agent", None)
                or self.ai_model
            )

            # Trigger automatic AI analysis for diagnostic errors
            self._trigger_automatic_ai_analysis(
                "diag",
                args.target,
                {
                    "operation": "diagnose_container_failure",
                    "exception": str(e),
                    "follow": getattr(args, "follow", False),
                },
                ai_model=ai_model,
            )

            return False

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
        result = self.container_ops.prune(enhanced=enhanced, quick=quick)

        # Show common actions after successful prune
        if result is not False:
            self._show_common_actions_for_command("prune", "system")

        return True

    def _handle_system_df(self, args):
        self.container_ops.show_system_df()
        return True

    # Service lifecycle command handlers
    def _handle_reinit(self, args):
        """Handle both standard and enhanced reinit commands."""
        # Make verbose mode the default for reinit unless --quiet is specified
        if not getattr(args, "quiet", False):
            set_verbose(True)
        else:
            self.handle_command_verbose(args)

        # Determine build type
        build_type = None
        if getattr(args, "build", False):
            build_type = "legacy"  # -b flag (backward compatibility)
        elif getattr(args, "podman_build", False):
            build_type = "podman"
        elif getattr(args, "quadlet_build", False):
            build_type = "quadlet"

        # Get vLLM model if specified
        model_model = getattr(args, "model_model", None)

        # Check if this is enhanced reinit (command name is 'enhanced-reinit')
        is_enhanced = args.command == "enhanced-reinit"

        if is_enhanced:
            return self._handle_enhanced_reinit_logic(args, build_type, model_model)
        else:
            # Standard reinit
            dry_run = getattr(args, "dry_run", False)
            return self.try_with_fallback(
                self.container_ops.reinit,
                args.target,
                build_type=build_type,
                model_model=model_model,
                dry_run=dry_run,
            )

    def _handle_enhanced_reinit(self, args):
        """Handle enhanced reinit - delegates to unified handler."""
        return self._handle_reinit(args)

    def _handle_enhanced_reinit_logic(self, args, build_type, model_model):
        """Handle enhanced reinit logic with proactive AI troubleshooting."""
        try:
            from managers.reinit_manager import ReinitManager

            enhanced_manager = ReinitManager(self.manager)

            # Get enhanced options
            enable_ai_guidance = getattr(args, "enable_ai_guidance", True)
            enable_retry = getattr(args, "enable_retry", True)

            # Try enhanced reinit first
            success = enhanced_manager.enhanced_reinit(
                target=args.target,
                build=build_type is not None,
                build_type=build_type,
                model_model=model_model,
                enable_ai_guidance=enable_ai_guidance,
            )

            # If enhanced reinit fails and retry is enabled, use intelligent retry
            if not success and enable_retry:
                from managers.intelligent_retry_manager import IntelligentRetryManager

                retry_manager = IntelligentRetryManager(self.manager)

                console.print(
                    "\n[yellow]Enhanced reinit failed. Attempting intelligent retry...[/yellow]"
                )

                success = retry_manager.retry_with_ai_guidance(
                    target=args.target,
                    original_operation=enhanced_manager.enhanced_reinit,
                    operation_kwargs={
                        "target": args.target,
                        "build": build_type is not None,
                        "build_type": build_type,
                        "model_model": model_model,
                        "enable_ai_guidance": enable_ai_guidance,
                    },
                    enable_auto_fixes=getattr(args, "enable_auto_fixes", True),
                )

                if success:
                    # Show retry statistics
                    stats = retry_manager.get_retry_statistics()
                    console.print(
                        f"\n[green]✅ Succeeded after {stats.get('total_attempts', 0)} retry attempts[/green]"
                    )

            if success:
                # Show common actions after successful enhanced reinit
                resolved_container_name = self._resolve_container_name_once(args.target)
                self._show_common_actions_for_command(
                    "enhanced-reinit", args.target, resolved_container_name
                )

            return success

        except ImportError as e:
            console.print(f"[red]Enhanced reinit not available: {e}[/red]")
            console.print("[dim]Falling back to standard reinit...[/dim]")
            # Fall back to standard reinit
            dry_run = getattr(args, "dry_run", False)
            return self.try_with_fallback(
                self.container_ops.reinit,
                args.target,
                build_type=build_type,
                model_model=model_model,
                dry_run=dry_run,
            )
        except Exception as e:
            console.print(f"[red]Enhanced reinit failed: {e}[/red]")
            return False

    def _handle_build(self, args):
        # Handle verbose/quiet flags for build command
        # Build command defaults to verbose unless --quiet is specified
        if hasattr(args, "quiet") and args.quiet:
            # Override default verbose behavior with quiet flag
            set_verbose(False)
        else:
            # Default to verbose for build command
            set_verbose(True)
        return self.try_with_fallback(self.container_ops.build_only, args.target)

    def _handle_start(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(
            self.container_ops.start, args.target, build=getattr(args, "build", False)
        )

    def _handle_stop(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.stop, args.target)

    def _handle_remove(self, args):
        self.handle_command_verbose(args)
        return self.try_with_fallback(self.container_ops.remove, args.target)

    def _handle_restart(self, args):
        self.handle_command_verbose(args)
        # Get vLLM model if specified
        model_model = getattr(args, "model_model", None)
        return self.try_with_fallback(
            self.container_ops.restart,
            args.target,
            build=getattr(args, "build", False),
            model_model=model_model,
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

    def _handle_fix_supabase_env(self, args):
        # Fix Supabase environment variable issues
        return fix_supabase_environment_variables()

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

    def _handle_copy_volumes(self, args):
        """Copy volumes from source stack to target stack, including share networks"""
        self.handle_command_verbose(args)
        return self.try_with_fallback(
            self.container_ops.copy_stack_volumes, args.source_stack, args.target_stack
        )

    def _handle_list_volumes(self, args):
        """List volumes and networks for a stack"""
        self.handle_command_verbose(args)
        self.container_ops.list_stack_volumes_and_networks(args.target)
        return True

    def _handle_cleanup_volumes(self, args):
        """Clean up orphaned volumes for a stack"""
        self.handle_command_verbose(args)
        return self.try_with_fallback(
            self.container_ops.cleanup_orphaned_volumes, args.target
        )

    # vLLM model management command handlers
    def _handle_vllm_switch(self, args):
        """Switch vLLM backend to a different model container"""
        self.handle_command_verbose(args)
        try:
            from managers.model_manager import ModelManger

            vllm_mgr = ModelManger(self.manager)

            proxy_image = getattr(args, "proxy_image", None)
            result = vllm_mgr.switch_model_model(args.model_container, proxy_image)

            if result:
                console.print(
                    f"[green]Successfully switched to vLLM model: {args.model_container}[/green]"
                )
                # Show common actions after successful switch
                self._show_common_actions_for_command(
                    "vllm-switch", args.model_container
                )
            else:
                console.print(
                    f"[red]Failed to switch to vLLM model: {args.model_container}[/red]"
                )

            return result
        except ImportError:
            console.print("[red]vLLM model manager not available[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error switching vLLM model: {e}[/red]")
            return False

    def _handle_vllm_status(self, args):
        """Show current vLLM configuration and status"""
        self.handle_command_verbose(args)
        try:
            from managers.model_manager import ModelManger

            vllm_mgr = ModelManger(self.manager)
            vllm_mgr.show_vllm_status()
            return True
        except ImportError:
            console.print("[red]vLLM model manager not available[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error showing vLLM status: {e}[/red]")
            return False

    def _handle_model_models(self, args):
        """List available vLLM model containers"""
        self.handle_command_verbose(args)
        try:
            from managers.model_manager import ModelManger

            vllm_mgr = ModelManger(self.manager)

            available_models = vllm_mgr.get_available_model_models()
            current_backend = vllm_mgr.get_current_vllm_backend()

            console.print("[bold cyan]Available vLLM Model Containers[/bold cyan]")
            console.print()

            if available_models:
                for model in available_models:
                    status = vllm_mgr._get_container_status(model)
                    marker = "→" if model == current_backend else " "
                    console.print(f"  {marker} [cyan]{model}[/cyan] - {status}")

                if current_backend:
                    console.print(
                        f"\n[green]Current Backend:[/green] {current_backend}"
                    )
                else:
                    console.print(
                        "\n[yellow]Current Backend:[/yellow] Unknown or proxy not running"
                    )
            else:
                console.print("  [yellow]No vLLM model containers found[/yellow]")
                console.print(
                    "  [dim]Use 'podman ps -a --filter name=vllm' to check for containers[/dim]"
                )

            console.print()
            return True
        except ImportError:
            console.print("[red]vLLM model manager not available[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error listing vLLM models: {e}[/red]")
            return False

    def _handle_vllm_current(self, args):
        """Show which vLLM model is currently using port 8005"""
        self.handle_command_verbose(args)
        try:
            from managers.model_manager import ModelManger

            vllm_mgr = ModelManger(self.manager)
            vllm_mgr.show_current_model_model()
            return True
        except ImportError:
            console.print("[red]vLLM model manager not available[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error detecting current vLLM model: {e}[/red]")
            return False
