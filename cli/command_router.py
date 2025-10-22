#!/usr/bin/env python3
"""
Command routing and execution logic
"""

import subprocess
import sys

from rich.table import Table

from config import console, set_verbose
from utils.supabase_fixer import fix_supabase_environment_variables


class CommandRouter:
    """Routes commands to appropriate handlers"""

    def __init__(self, manager, container_ops, display, selected_mode, detector):
        self.manager = manager
        self.container_ops = container_ops
        self.display = display
        self.selected_mode = selected_mode
        self.detector = detector

    def handle_command_verbose(self, args):
        """Handle command-specific verbose flags"""
        if hasattr(args, "verbose") and args.verbose:
            set_verbose(True)

    def try_with_fallback(self, operation_func, *operation_args, **operation_kwargs):
        """Try operation with current mode, fallback to alternative if it fails"""
        target = operation_kwargs.get(
            "target", operation_args[0] if operation_args else ""
        )

        try:
            result = operation_func(*operation_args, **operation_kwargs)
            # If operation returns False (failure), try fallback
            if result is False:
                alternative_mode = self.detector.suggest_alternative_mode(
                    target, self.selected_mode
                )
                if alternative_mode:
                    console.print(
                        f"[yellow]Trying alternative mode: {alternative_mode}[/yellow]"
                    )
                    console.print(
                        f"[dim]Try: pm --mode {alternative_mode} {' '.join(sys.argv[1:])}[/dim]"
                    )
            return result
        except Exception as e:
            console.print(f"[red]Operation failed: {e}[/red]")
            alternative_mode = self.detector.suggest_alternative_mode(
                target, self.selected_mode
            )
            if alternative_mode:
                console.print(
                    f"[dim]Try: pm --mode {alternative_mode} {' '.join(sys.argv[1:])}[/dim]"
                )
            return False

    def route_command(self, args):
        """Route command to appropriate handler"""
        command = args.command

        # Status and information commands
        if command == "list":
            return self._handle_list(args)
        elif command == "status":
            return self._handle_status(args)
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
        elif command == "events":
            return self._handle_events(args)
        elif command == "targets":
            return self._handle_targets(args)

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

    def _handle_status(self, args):
        verbose = getattr(args, "verbose", False)
        if args.target:
            self.display.show_status(args.target, verbose=verbose)
        else:
            self.display.show_status(verbose=verbose)
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
                return False
        except subprocess.TimeoutExpired:
            console.print("[red]Timeout running podman ps[/red]")
            return False
        except FileNotFoundError:
            console.print("[red]Podman command not found. Please install podman.[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error running podman ps: {e}[/red]")
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

    def _handle_events(self, args):
        self.display.show_events(since=args.since)
        return True

    def _handle_targets(self, args):
        available_targets = self.detector.list_available_targets()

        table = Table(
            show_header=True, header_style="bold magenta", title="Available Targets"
        )
        table.add_column("Type", style="cyan", no_wrap=True)
        table.add_column("Targets", style="white")

        if available_targets["quadlet"]:
            table.add_row("Quadlet Services", ", ".join(available_targets["quadlet"]))

        if available_targets["compose"]:
            table.add_row("Compose Services", ", ".join(available_targets["compose"]))

        if not available_targets["quadlet"] and not available_targets["compose"]:
            table.add_row("None", "No targets found")

        console.print(table)

        # Show current mode
        console.print(f"\n[dim]Current mode: {self.selected_mode}[/dim]")
        return True

    # Resource command handlers
    def _handle_logs(self, args):
        if getattr(args, "ai_diagnose", False):
            self.container_ops.ai_analyze_logs(
                args.target,
                lines=args.tail,
                vllm_url=args.vllm_url,
                verbose=args.verbose,
            )
        else:
            self.container_ops.show_logs(
                args.target, follow=args.follow, tail=args.tail
            )
        return True

    def _handle_diagnose(self, args):
        if self.selected_mode == "quadlet":
            self.container_ops.diagnose_container_failure(args.target)
            return True
        else:
            console.print("[red]Diagnose command only available in quadlet mode[/red]")
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
        self.container_ops.prune(enhanced=enhanced, quick=quick)
        return True

    def _handle_system_df(self, args):
        if self.selected_mode == "quadlet":
            self.container_ops.show_system_df()
        else:
            self.display.show_system_df()
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
        if self.selected_mode == "quadlet":
            return self.try_with_fallback(self.container_ops.reset_failed, args.target)
        else:
            console.print(
                "[red]Reset-failed command only available in quadlet mode[/red]"
            )
            return False

    def _handle_show_service_file(self, args):
        self.handle_command_verbose(args)
        if self.selected_mode == "quadlet":
            return self.try_with_fallback(
                self.container_ops.show_service_file, args.target
            )
        else:
            console.print(
                "[red]Show-service-file command only available in quadlet mode[/red]"
            )
            return False

    # Image and update command handlers
    def _handle_install(self, args):
        self.handle_command_verbose(args)
        if self.selected_mode == "quadlet":
            return self.try_with_fallback(self.container_ops.install_stack, args.target)
        else:
            console.print("[red]Install command only available in quadlet mode[/red]")
            return False

    def _handle_uninstall(self, args):
        if self.selected_mode == "quadlet":
            return self.try_with_fallback(
                self.container_ops.uninstall_stack, args.target
            )
        else:
            console.print("[red]Uninstall command only available in quadlet mode[/red]")
            return False

    def _handle_update(self, args):
        if self.selected_mode == "quadlet":
            return self.try_with_fallback(
                self.container_ops.update_images_and_restart, args.target
            )
        else:
            console.print("[red]Update command only available in quadlet mode[/red]")
            return False

    def _handle_auto_update(self, args):
        if self.selected_mode == "quadlet":
            self.container_ops.check_auto_update_status()
            return True
        else:
            console.print(
                "[red]Auto-update command only available in quadlet mode[/red]"
            )
            return False

    def _handle_reload(self, args):
        if self.selected_mode == "quadlet":
            return self.container_ops.reload_daemon()
        else:
            console.print("[red]Reload command only available in quadlet mode[/red]")
            return False

    def _handle_refresh(self, args):
        # Hidden refresh command used internally by universal script
        if self.selected_mode == "quadlet":
            if hasattr(self.manager, "refresh_service_discovery"):
                self.manager.refresh_service_discovery()
            # Also clear any display caches
            if hasattr(self.display, "clear_cache"):
                self.display.clear_cache()
            console.print("[green]Service discovery refreshed[/green]")
            return True
        else:
            return False

    def _handle_fix_supabase_env(self, args):
        # Fix Supabase environment variable issues
        if self.selected_mode == "quadlet":
            return fix_supabase_environment_variables()
        else:
            console.print(
                "[red]Fix Supabase environment command only available in quadlet mode[/red]"
            )
            return False
