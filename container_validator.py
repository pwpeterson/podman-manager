"""Container file validation module for quadlet .container files."""

import re
from pathlib import Path
from typing import Dict, List, Tuple

from rich.console import Console
from rich.table import Table

console = Console()


class ContainerValidator:
    """Validates quadlet .container files for missing environment variables and invalid parameters."""

    def __init__(self):
        """Initialize the validator with known valid parameters and common environment variables."""
        # Valid quadlet .container file parameters
        # Based on podman-systemd.unit(5) documentation
        self.valid_parameters = {
            # Container section parameters
            "Image",
            "ContainerName",
            "PublishPort",
            "Volume",
            "Environment",
            "EnvironmentFile",
            "EnvironmentHost",
            "Network",
            "NetworkAlias",
            "User",
            "Group",
            "WorkingDir",
            "Entrypoint",
            "Exec",
            "RunInit",
            "Timezone",
            "PodmanArgs",
            "Label",
            "Annotation",
            "AddCapability",
            "DropCapability",
            "NoNewPrivileges",
            "ReadOnly",
            "ReadOnlyTmpfs",
            "Rootfs",
            "Tmpfs",
            "Mount",
            "SecurityLabelDisable",
            "SecurityLabelFileType",
            "SecurityLabelLevel",
            "SecurityLabelNested",
            "SecurityLabelType",
            "Mask",
            "Unmask",
            "Notify",
            "ExposeHostPort",
            "HostName",
            "IP",
            "IP6",
            "DNS",
            "DNSSearch",
            "DNSOption",
            "LogDriver",
            "LogOpt",
            "SyslogIdentifier",
            "SyslogFacility",
            "SyslogLevel",
            "SyslogTag",
            "AutoUpdate",
            "GlobalArgs",
            "Pull",
            "Pod",
            "PodName",
            "Ulimit",
            "PidsLimit",
            "Memory",
            "HealthCmd",
            "HealthInterval",
            "HealthOnFailure",
            "HealthRetries",
            "HealthStartPeriod",
            "HealthStartupCmd",
            "HealthStartupInterval",
            "HealthStartupRetries",
            "HealthStartupSuccess",
            "HealthStartupTimeout",
            "HealthTimeout",
            "StopSignal",
            "StopTimeout",
            "Secret",
            "Secrets",
            "DecryptionKey",
            "Device",
            "HostDevice",
            "AddDevice",
            "Sysctl",
            "UserNS",
            "GroupAdd",
            "HostUser",
            "IDMap",
            "SubUIDName",
            "SubGIDName",
            "VolumesFrom",
            "UsernsMode",
            "CgroupsMode",
            "CgroupParent",
            "CgroupConf",
            "OOMScoreAdj",
            "Privileged",
            "SecurityOpt",
            "SeccompProfile",
            "ShmSize",
            "SystemdDropin",
            "Userns",
            "UtsMode",
            "IpcMode",
            "PidMode",
            "CgroupMode",
            "NetworkMode",
            "RestartPolicy",
            "RestartSec",
            # Additional Container section parameters from documentation
            "Arch",
            "OS",
            "Variant",
            "AuthFile",
            "CertDir",
            "Creds",
            "Policy",
            "Retry",
            "RetryDelay",
            "TLSVerify",
            "ImageTag",
            "ContainersConfModule",
            "SetWorkingDirectory",
            # Unit section parameters (systemd)
            "Description",
            "Documentation",
            "Requires",
            "Requisite",
            "Wants",
            "BindsTo",
            "PartOf",
            "Conflicts",
            "Before",
            "After",
            "OnFailure",
            "PropagatesReloadTo",
            "ReloadPropagatedFrom",
            "JoinsNamespaceOf",
            "RequiresMountsFor",
            "OnFailureJobMode",
            "IgnoreOnIsolate",
            "StopWhenUnneeded",
            "RefuseManualStart",
            "RefuseManualStop",
            "AllowIsolate",
            "DefaultDependencies",
            "JobTimeoutSec",
            "JobRunningTimeoutSec",
            "JobTimeoutAction",
            "StartLimitIntervalSec",
            "StartLimitBurst",
            "StartLimitAction",
            "FailureAction",
            "SuccessAction",
            "FailureActionExitStatus",
            "SuccessActionExitStatus",
            "RebootArgument",
            "SourcePath",
            "ConditionArchitecture",
            "ConditionVirtualization",
            "ConditionHost",
            "ConditionKernelCommandLine",
            "ConditionKernelVersion",
            "ConditionSecurity",
            "ConditionCapability",
            "ConditionACPower",
            "ConditionNeedsUpdate",
            "ConditionFirstBoot",
            "ConditionPathExists",
            "ConditionPathExistsGlob",
            "ConditionPathIsDirectory",
            "ConditionPathIsSymbolicLink",
            "ConditionPathIsMountPoint",
            "ConditionPathIsReadWrite",
            "ConditionDirectoryNotEmpty",
            "ConditionFileNotEmpty",
            "ConditionFileIsExecutable",
            "ConditionUser",
            "ConditionGroup",
            "ConditionControlGroupController",
            "ConditionMemory",
            "ConditionCPUs",
            "ConditionEnvironment",
            "AssertArchitecture",
            "AssertVirtualization",
            "AssertHost",
            "AssertKernelCommandLine",
            "AssertKernelVersion",
            "AssertSecurity",
            "AssertCapability",
            "AssertACPower",
            "AssertNeedsUpdate",
            "AssertFirstBoot",
            "AssertPathExists",
            "AssertPathExistsGlob",
            "AssertPathIsDirectory",
            "AssertPathIsSymbolicLink",
            "AssertPathIsMountPoint",
            "AssertPathIsReadWrite",
            "AssertDirectoryNotEmpty",
            "AssertFileNotEmpty",
            "AssertFileIsExecutable",
            "AssertUser",
            "AssertGroup",
            "AssertControlGroupController",
            "AssertMemory",
            "AssertCPUs",
            "AssertEnvironment",
            # Service section parameters (systemd)
            "Type",
            "RemainAfterExit",
            "GuessMainPID",
            "PIDFile",
            "BusName",
            "ExecStart",
            "ExecStartPre",
            "ExecStartPost",
            "ExecCondition",
            "ExecReload",
            "ExecStop",
            "ExecStopPost",
            "RestartSec",
            "TimeoutStartSec",
            "TimeoutStopSec",
            "TimeoutAbortSec",
            "TimeoutSec",
            "TimeoutStartFailureMode",
            "TimeoutStopFailureMode",
            "RuntimeMaxSec",
            "WatchdogSec",
            "Restart",
            "SuccessExitStatus",
            "RestartPreventExitStatus",
            "RestartForceExitStatus",
            "RootDirectoryStartOnly",
            "NonBlocking",
            "NotifyAccess",
            "Sockets",
            "FileDescriptorStoreMax",
            "USBFunctionDescriptors",
            "USBFunctionStrings",
            "OOMPolicy",
            "OpenFile",
            # Install section parameters (systemd)
            "WantedBy",
            "RequiredBy",
            "Alias",
            "Also",
            "DefaultInstance",
        }

        # Invalid/deprecated parameters that should be flagged
        self.invalid_parameters = {
            "Expose",  # Should be ExposeHostPort or PublishPort
            "Port",  # Should be PublishPort
            "Ports",  # Should be PublishPort
            "Env",  # Should be Environment
            "EnvFile",  # Should be EnvironmentFile
            "Volumes",  # Should be Volume
            "Networks",  # Should be Network
            # Docker-style parameters that don't exist in Podman quadlet
            "Dockerfile",  # Not applicable to .container files
            "Build",  # Should use .build files instead
            "Command",  # Should be Exec
            "Args",  # Should be Exec
            "Cmd",  # Should be Exec
        }

        # Parameters that are only invalid in specific sections
        self.section_specific_invalid = {
            "Container": {
                "Restart",  # Should be in Service section (use RestartPolicy instead)
                # Note: RestartPolicy is valid in Container section
            }
        }

        # Common restart policy values (systemd format)
        self.valid_restart_policies = {
            "no",
            "always",
            "on-success",
            "on-failure",
            "on-abnormal",
            "on-abort",
            "on-watchdog",
        }

        # Docker-style to systemd restart policy mapping
        self.docker_to_systemd_restart_policies = {
            "unless-stopped": "always",  # Docker unless-stopped -> systemd always
            "on-reboot": "always",  # Docker on-reboot -> systemd always
        }

        # Invalid Docker-style restart policies (for reference)
        self.invalid_restart_policies = set(
            self.docker_to_systemd_restart_policies.keys()
        )

    def validate_container_file(
        self, file_path: Path
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate a .container file for issues.

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []

        if not file_path.exists():
            errors.append(f"Container file does not exist: {file_path}")
            return False, errors, warnings

        try:
            with open(file_path, "r") as f:
                content = f.read()
        except Exception as e:
            errors.append(f"Failed to read container file: {e}")
            return False, errors, warnings

        # Parse the file content
        sections = self._parse_container_file(content)

        # Validate sections and parameters
        section_errors, section_warnings = self._validate_sections(sections)
        errors.extend(section_errors)
        warnings.extend(section_warnings)

        # Check for environment variable references
        env_errors, env_warnings = self._validate_environment_variables(content)
        errors.extend(env_errors)
        warnings.extend(env_warnings)

        # Check for common configuration issues
        config_errors, config_warnings = self._validate_configuration(sections)
        errors.extend(config_errors)
        warnings.extend(config_warnings)

        is_valid = len(errors) == 0
        return is_valid, errors, warnings

    def _parse_container_file(self, content: str) -> Dict[str, Dict[str, str]]:
        """Parse .container file content into sections and key-value pairs."""
        sections = {}
        current_section = None

        for line_num, line in enumerate(content.split("\n"), 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Section headers
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                sections[current_section] = {}
                continue

            # Key-value pairs
            if "=" in line and current_section:
                key, value = line.split("=", 1)
                sections[current_section][key.strip()] = value.strip()

        return sections

    def _validate_sections(
        self, sections: Dict[str, Dict[str, str]]
    ) -> Tuple[List[str], List[str]]:
        """Validate section parameters."""
        errors = []
        warnings = []

        for section_name, section_params in sections.items():
            for param_name, param_value in section_params.items():
                # Check for section-specific invalid parameters first
                if (
                    section_name in self.section_specific_invalid
                    and param_name in self.section_specific_invalid[section_name]
                ):
                    if param_name == "Restart" and section_name == "Container":
                        errors.append(
                            f"Invalid parameter '{param_name}' in [{section_name}] section. Use 'RestartPolicy' instead."
                        )
                    else:
                        errors.append(
                            f"Invalid parameter '{param_name}' in [{section_name}] section."
                        )

                # Check for globally invalid parameters
                elif param_name in self.invalid_parameters:
                    if param_name == "Expose":
                        errors.append(
                            f"Invalid parameter '{param_name}' in [{section_name}] section. Use 'PublishPort' instead."
                        )
                    elif param_name in ["Port", "Ports"]:
                        errors.append(
                            f"Invalid parameter '{param_name}' in [{section_name}] section. Use 'PublishPort' instead."
                        )
                    elif param_name == "Env":
                        errors.append(
                            f"Invalid parameter '{param_name}' in [{section_name}] section. Use 'Environment' instead."
                        )
                    elif param_name == "EnvFile":
                        errors.append(
                            f"Invalid parameter '{param_name}' in [{section_name}] section. Use 'EnvironmentFile' instead."
                        )
                    elif (
                        param_name in ["Volumes", "Volume"]
                        and section_name == "Container"
                    ):
                        # Volume is valid, but Volumes is not
                        if param_name == "Volumes":
                            errors.append(
                                f"Invalid parameter '{param_name}' in [{section_name}] section. Use 'Volume' instead."
                            )
                    elif param_name == "Networks":
                        errors.append(
                            f"Invalid parameter '{param_name}' in [{section_name}] section. Use 'Network' instead."
                        )
                    else:
                        errors.append(
                            f"Invalid/deprecated parameter '{param_name}' in [{section_name}] section."
                        )

                # Check for unknown parameters (not in valid list)
                elif param_name not in self.valid_parameters:
                    warnings.append(
                        f"Unknown parameter '{param_name}' in [{section_name}] section. Please verify this is correct."
                    )

                # Validate specific parameter values
                if param_name == "Restart" and section_name == "Service":
                    if param_value in self.docker_to_systemd_restart_policies:
                        suggested_value = self.docker_to_systemd_restart_policies[
                            param_value
                        ]
                        errors.append(
                            f"Docker-style Restart value '{param_value}' not supported by systemd. Use 'Restart={suggested_value}' instead."
                        )
                    elif param_value not in self.valid_restart_policies:
                        errors.append(
                            f"Invalid Restart value '{param_value}'. Valid values: {', '.join(self.valid_restart_policies)}"
                        )

                if param_name == "RestartPolicy" and section_name == "Container":
                    if param_value in self.docker_to_systemd_restart_policies:
                        suggested_value = self.docker_to_systemd_restart_policies[
                            param_value
                        ]
                        errors.append(
                            f"Docker-style RestartPolicy value '{param_value}' not supported by systemd. Use 'RestartPolicy={suggested_value}' instead."
                        )
                    elif param_value not in self.valid_restart_policies:
                        errors.append(
                            f"Invalid RestartPolicy value '{param_value}'. Valid values: {', '.join(self.valid_restart_policies)}"
                        )

        return errors, warnings

    def _validate_environment_variables(
        self, content: str
    ) -> Tuple[List[str], List[str]]:
        """Check for unresolved environment variable references against /etc/environment.d/ files."""
        errors = []
        warnings = []

        # Load environment variables from /etc/environment.d/ files
        env_d_vars = self._load_environment_d_variables()

        # Find all environment variable references
        env_var_pattern = r"\$\{([^}]+)\}"
        env_vars = re.findall(env_var_pattern, content)

        for env_var in env_vars:
            # Handle default values: ${VAR:-default}
            var_name = env_var.split(":-")[0].split(":=")[0]

            # Check if environment variable is set in /etc/environment.d/ files
            if var_name not in env_d_vars:
                # Check if it has a default value
                if ":-" in env_var or ":=" in env_var:
                    warnings.append(
                        f"Environment variable '{var_name}' not found in /etc/environment.d/, will use default value"
                    )
                else:
                    errors.append(
                        f"'{var_name}' is missing in /etc/environment.d/10-app.conf:"
                    )

        return errors, warnings

    def _load_environment_d_variables(self) -> Dict[str, str]:
        """Load environment variables from /etc/environment.d/ and ~/.config/environment.d/ files."""
        env_vars = {}

        # Check both system and user environment.d directories
        env_dirs = [Path("/etc/environment.d"), Path.home() / ".config/environment.d"]

        for env_dir in env_dirs:
            if not env_dir.exists():
                continue

            # Process .conf files in alphabetical order
            conf_files = sorted(env_dir.glob("*.conf"))
            for conf_file in conf_files:
                try:
                    with open(conf_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            # Skip empty lines and comments
                            if not line or line.startswith("#"):
                                continue
                            # Parse KEY=VALUE format
                            if "=" in line:
                                key, value = line.split("=", 1)
                                env_vars[key.strip()] = value.strip()
                except Exception:
                    # Ignore files that can't be read
                    continue

        return env_vars

    def _validate_configuration(
        self, sections: Dict[str, Dict[str, str]]
    ) -> Tuple[List[str], List[str]]:
        """Validate common configuration patterns and requirements."""
        errors = []
        warnings = []

        # Check for required sections
        if "Container" not in sections:
            errors.append("Missing required [Container] section")
            return errors, warnings

        container_section = sections["Container"]

        # Check for required parameters
        if "Image" not in container_section:
            errors.append("Missing required 'Image' parameter in [Container] section")

        # Check PublishPort format
        if "PublishPort" in container_section:
            port_value = container_section["PublishPort"]
            # Basic port format validation: should be like "8080:8080" or "8080"
            if not re.match(r"^\d+(?::\d+)?(?:/[a-z]+)?$", port_value):
                warnings.append(
                    f"PublishPort format may be incorrect: '{port_value}'. Expected format: 'host_port:container_port' or 'port'"
                )

        # Check for common misconfigurations
        if "EnvironmentFile" in container_section:
            env_file = container_section["EnvironmentFile"]
            if not Path(env_file).exists():
                warnings.append(f"EnvironmentFile '{env_file}' does not exist")

        # Check restart policy location
        if "Restart" in container_section:
            errors.append(
                "'Restart' parameter should be 'RestartPolicy' in [Service] section, not [Container] section"
            )

        return errors, warnings

    def validate_multiple_files(
        self, file_paths: List[Path]
    ) -> Dict[str, Tuple[bool, List[str], List[str]]]:
        """Validate multiple container files and return results."""
        results = {}

        for file_path in file_paths:
            is_valid, errors, warnings = self.validate_container_file(file_path)
            results[str(file_path)] = (is_valid, errors, warnings)

        return results

    def print_validation_results(
        self, file_path: Path, is_valid: bool, errors: List[str], warnings: List[str]
    ) -> None:
        """Print validation results in a formatted way."""
        console.print(f"\n[bold]Validating: {file_path.name}[/bold]")

        if is_valid and not warnings:
            console.print("[green]✓ Container file is valid[/green]")
            return

        if errors:
            console.print(f"[red]✗ {len(errors)} error(s) found:[/red]")
            for error in errors:
                console.print(f"  [red]• {error}[/red]")

        if warnings:
            console.print(f"[yellow]⚠ {len(warnings)} warning(s):[/yellow]")
            for warning in warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")

        if not errors:
            console.print("[green]✓ No critical errors (warnings only)[/green]")

    def print_summary_table(
        self, results: Dict[str, Tuple[bool, List[str], List[str]]]
    ) -> None:
        """Print a summary table of validation results."""
        table = Table(title="Container File Validation Summary")
        table.add_column("File", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Errors", style="red")
        table.add_column("Warnings", style="yellow")

        for file_path, (is_valid, errors, warnings) in results.items():
            file_name = Path(file_path).name
            status = "[green]✓ Valid[/green]" if is_valid else "[red]✗ Invalid[/red]"
            error_count = str(len(errors)) if errors else "-"
            warning_count = str(len(warnings)) if warnings else "-"

            table.add_row(file_name, status, error_count, warning_count)

        console.print(table)
