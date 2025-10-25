import configparser
import re
from typing import Dict, List, Optional, Tuple

DURATION_RE = re.compile(r"^\s*\d+\s*(ns|us|ms|s|m|h|d)?\s*$", re.IGNORECASE)
SIZE_RE = re.compile(r"^\s*\d+\s*([kmgt]i?b?|b)?\s*$", re.IGNORECASE)
CPU_LIST_RE = re.compile(r"^\s*\d+(-\d+)?(\s*,\s*\d+(-\d+)?)*\s*$")
PORT_RE = re.compile(
    r"^\s*(?:(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\:)?(?P<hp>\d+)\:(?P<cp>\d+)(?:/(?P<proto>tcp|udp|sctp))?\s*$",
    re.IGNORECASE,
)
EXPOSE_RE = re.compile(r"^\s*\d+(-\d+)?(?:/(tcp|udp|sctp))?\s*$", re.IGNORECASE)
HOSTS_RE = re.compile(
    r"^\s*(?P<host>[A-Za-z0-9][A-Za-z0-9\-\.]{0,251})\:(?P<ip>(\d{1,3}\.){3}\d{1,3})\s*$"
)
VOLUME_SIMPLE_RE = re.compile(r"^.+:.+")
MOUNT_KEYVAL_RE = re.compile(r"^\s*type=\w+(?:\s*,\s*\w+=[^,]+)*\s*$", re.IGNORECASE)
SYSCTL_RE = re.compile(r"^[a-z0-9_\.\-]+=[^\s]+$", re.IGNORECASE)
KEYVAL_RE = re.compile(r"^[^=\s]+=[^\s]+$")
ENV_RE = KEYVAL_RE
LABEL_RE = KEYVAL_RE
ANNOTATION_RE = KEYVAL_RE
DNS_RE = re.compile(r"^\s*(\d{1,3}\.){3}\d{1,3}\s*$")
DNS_SEARCH_RE = re.compile(r"^\s*[a-z0-9][a-z0-9\-\.]{0,251}\s*$", re.IGNORECASE)
DEVICE_RULE_RE = re.compile(r"^[cb]\s+\d+:\d+\s+[rwm]{1,3}$", re.IGNORECASE)
CAP_RE = re.compile(r"^[A-Z0-9_]+$")

ALLOWED = {
    "Pull": {"always", "missing", "never", "newer"},
    "RestartPolicy": {"no", "on-failure", "always", "unless-stopped"},
    "LogDriver": {"k8s-file", "journald", "json-file", "passthrough", "none"},
    "Network": {
        "bridge",
        "host",
        "none",
        "slirp4netns",
    },  # may also be custom network names
    "Ipc": {"shareable", "host", "private"},
    "Uts": {"host", "private"},
    "Pid": {"host", "private"},
    "Cgroup": {"host", "private"},
    "Timezone": {"container", "host"},  # or any tz database name
    "StopSignal": None,  # allow signal names/numbers; validated separately
    "KillSignal": None,
    "Privileged": {True, False},
    "TTY": {True, False},
    "Interactive": {True, False},
    "ReadOnly": {True, False},
    "ReadOnlyTmpfs": {True, False},
    "OomKillDisable": {True, False},
    "NoNewPrivileges": {True, False},
    "Rm": {True, False},
    "Init": {True, False},
    "IPv6": {True, False},
}

# Keys that can repeat; collect as lists
REPEATABLE_KEYS = {
    "Env",
    "EnvFile",
    "Label",
    "Annotation",
    "GroupAdd",
    "CapAdd",
    "CapDrop",
    "Devices",
    "DeviceCgroupRule",
    "Tmpfs",
    "Volume",
    "VolumeFrom",
    "Mount",
    "Network",
    "NetworkAlias",
    "PublishPort",
    "ExposePort",
    "Dns",
    "DnsSearch",
    "DnsOption",
    "Hosts",
    "Sysctl",
    "LogOpt",
    "Secrets",
    "ConfigMaps",
}

# Keys that accept duration syntax
DURATION_KEYS = {
    "HealthInterval",
    "HealthTimeout",
    "HealthStartPeriod",
    "StopTimeout",
}

# Keys that accept size syntax
SIZE_KEYS = {
    "Memory",
    "MemorySwap",
}

# Integer keys
INT_KEYS = {
    "PidsLimit",
    "CpuShares",
    "CpuQuota",
    "CpuPeriod",
    "HealthRetries",
    "RestartTries",
}

# Special format keys
CPUSET_KEYS = {"CpusetCpus", "CpusetMems"}  # mems is looser; we reuse CPU_LIST_RE

SIGNALS = {
    # common signals; also allow numbers
    "SIGHUP",
    "SIGINT",
    "SIGQUIT",
    "SIGILL",
    "SIGTRAP",
    "SIGABRT",
    "SIGBUS",
    "SIGFPE",
    "SIGKILL",
    "SIGUSR1",
    "SIGSEGV",
    "SIGUSR2",
    "SIGPIPE",
    "SIGALRM",
    "SIGTERM",
    "SIGCHLD",
    "SIGCONT",
    "SIGSTOP",
    "SIGTSTP",
    "SIGTTIN",
    "SIGTTOU",
    "SIGURG",
    "SIGXCPU",
    "SIGXFSZ",
    "SIGVTALRM",
    "SIGPROF",
    "SIGWINCH",
    "SIGIO",
    "SIGPWR",
    "SIGSYS",
}

BOOLEAN_STRINGS = {"true", "false", "yes", "no", "on", "off", "1", "0"}


def _to_bool(v: str) -> Optional[bool]:
    s = v.strip().lower()
    if s in {"true", "yes", "on", "1"}:
        return True
    if s in {"false", "no", "off", "0"}:
        return False
    return None


def _validate_signal(v: str) -> bool:
    v = v.strip()
    if v.isdigit():
        return True
    if not v.startswith("SIG"):
        v = "SIG" + v
    return v.upper() in SIGNALS


def _validate_timezone(v: str) -> bool:
    v = v.strip()
    if v.lower() in {"container", "host"}:
        return True
    # heuristic for tz database names
    return "/" in v and all(
        part and re.match(r"^[A-Za-z0-9_\+\-]+$", part) for part in v.split("/")
    )


def _validate_network_value(v: str) -> Tuple[bool, Optional[str]]:
    base = v.strip().lower()
    if base in ALLOWED["Network"]:
        return True, None
    # allow ns:, container:, or custom network names
    if base.startswith("ns:") or base.startswith("container:"):
        return True, None
    if re.match(r"^[a-z0-9][a-z0-9_.\-]*$", v, re.IGNORECASE):
        return True, None
    return (
        False,
        "Network must be one of {bridge, host, none, slirp4netns}, a custom network name, or ns:/container: form",
    )


def _line_map(text: str) -> Dict[Tuple[str, str], int]:
    """
    Rough line mapping for [Container] keys: returns first occurrence line number for each key.
    """
    lines = text.splitlines()
    section = None
    mapping = {}
    for idx, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1]
            continue
        if section != "Container":
            continue
        if "=" in line and not s.startswith(";") and not s.startswith("#"):
            key = line.split("=", 1)[0].strip()
            mapping.setdefault(("Container", key), idx)
    return mapping


class QuadletContainerValidator:
    """
    Validate fields of a Quadlet .container file.
    Usage:
        v = QuadletContainerValidator()
        ok, errors, warnings = v.validate_file("/etc/containers/systemd/foo.container")
    """

    def __init__(self):
        # keys we know and will validate
        self.known_container_keys = {
            # basic
            "Image",
            "ContainerName",
            "Pull",
            "KillSignal",
            "StopSignal",
            "StopTimeout",
            "RestartPolicy",
            "RestartTries",
            "Exec",
            "Entrypoint",
            "Env",
            "EnvFile",
            "Label",
            "Annotation",
            "User",
            "GroupAdd",
            "UMask",
            "WorkingDir",
            "Privileged",
            "CapAdd",
            "CapDrop",
            "SecurityOpt",
            "Devices",
            "DeviceCgroupRule",
            "PidsLimit",
            "Memory",
            "MemorySwap",
            "CpuShares",
            "CpuQuota",
            "CpuPeriod",
            "CpusetCpus",
            "CpusetMems",
            "OomScoreAdj",
            "OomKillDisable",
            "LogDriver",
            "LogOpt",
            "TTY",
            "Interactive",
            "ReadOnly",
            "ReadOnlyTmpfs",
            "Tmpfs",
            "Volume",
            "VolumeFrom",
            "Mount",
            "Network",
            "NetworkAlias",
            "PublishPort",
            "ExposePort",
            "Dns",
            "DnsSearch",
            "DnsOption",
            "Hosts",
            "Hostname",
            "Ipc",
            "Uts",
            "Pid",
            "Cgroup",
            "Sysctl",
            "HealthCmd",
            "HealthInterval",
            "HealthTimeout",
            "HealthStartPeriod",
            "HealthRetries",
            "Secrets",
            "ConfigMaps",
            "NoNewPrivileges",
            "Rm",
            "Init",
            "Timezone",
            "WorkDir",
        }

    def validate_file(self, path: str) -> Tuple[bool, List[str], List[str]]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.validate_text(content, source=path)

    def validate_text(
        self, text: str, source: str = "<string>"
    ) -> Tuple[bool, List[str], List[str]]:
        cfg = configparser.ConfigParser(strict=False, interpolation=None)
        # Preserve case
        cfg.optionxform = str  # type: ignore

        errors: List[str] = []
        warnings: List[str] = []

        try:
            cfg.read_string(text)
        except configparser.Error as e:
            return False, [f"{source}: INI parse error: {e}"], warnings

        line_map = _line_map(text)

        if "Container" not in cfg:
            errors.append(f"{source}: missing [Container] section")
            return False, errors, warnings

        c = cfg["Container"]

        # Unknown keys warning
        for key in c.keys():
            if key not in self.known_container_keys:
                warnings.append(
                    f"{source}:{line_map.get(('Container', key), '?')}: unknown key '{key}' (may be valid in newer Podman; ensure spelling)"
                )

        # Validate required keys
        if "Image" not in c:
            errors.append(f"{source}:1: missing required key 'Image' in [Container]")

        # Field-by-field validation
        for key, value in c.items():
            ln = line_map.get(("Container", key), "?")
            v = value.strip()

            # Repeatable keys are allowed to be present multiple times in file; configparser flattens them.
            # We treat them as comma/newline separated list heuristically.
            if key in REPEATABLE_KEYS:
                values = self._split_repeatable(v)
                for i, item in enumerate(values, 1):
                    e = self._validate_repeatable_item(key, item)
                    if e:
                        errors.append(f"{source}:{ln}: {key}[{i}] invalid: {e}")
                continue

            if key in ALLOWED and ALLOWED[key] is not None:
                # boolean sets or enumerations
                allowed = ALLOWED[key]
                if allowed in ({True, False},):
                    b = _to_bool(v)
                    if b is None:
                        errors.append(
                            f"{source}:{ln}: {key} must be boolean (true/false/yes/no/on/off/1/0)"
                        )
                else:
                    if v.lower() not in {
                        str(x).lower() for x in allowed
                    }:  # case-insensitive match
                        errors.append(
                            f"{source}:{ln}: {key} invalid. Allowed: {sorted(allowed)}"
                        )
                continue

            if key in DURATION_KEYS:
                if not DURATION_RE.match(v):
                    errors.append(
                        f"{source}:{ln}: {key} must be a duration like 30s, 5m, 1h, or plain seconds"
                    )
                continue

            if key in SIZE_KEYS:
                if v != "" and v != "-1" and not SIZE_RE.match(v):
                    errors.append(
                        f"{source}:{ln}: {key} must be a size like 512m, 2g, -1, or empty"
                    )
                continue

            if key in INT_KEYS:
                if not v.isdigit() and not (v.startswith("-") and v[1:].isdigit()):
                    errors.append(f"{source}:{ln}: {key} must be an integer")
                continue

            if key in CPUSET_KEYS:
                if not CPU_LIST_RE.match(v):
                    errors.append(f"{source}:{ln}: {key} must be like '0-3,6'")
                continue

            if key in {"KillSignal", "StopSignal"}:
                if not _validate_signal(v):
                    errors.append(
                        f"{source}:{ln}: {key} must be a valid signal name (SIGTERM) or number"
                    )
                continue

            if key == "Timezone":
                if not _validate_timezone(v):
                    errors.append(
                        f"{source}:{ln}: Timezone must be 'container', 'host', or a valid tz like 'UTC' or 'America/Chicago'"
                    )
                continue

            if key == "User":
                # allow uid, name, uid:gid, name:group
                if not re.match(
                    r"^[A-Za-z0-9_][A-Za-z0-9_\-]*(:[A-Za-z0-9_][A-Za-z0-9_\-]*)?$", v
                ) and not re.match(r"^\d+(:\d+)?$", v):
                    errors.append(
                        f"{source}:{ln}: User must be uid, username, or uid:gid/user:group"
                    )
                continue

            if key == "UMask":
                if not re.match(r"^[0-7]{3,4}$", v):
                    errors.append(
                        f"{source}:{ln}: UMask must be octal like 0022 or 022"
                    )
                continue

            if key == "WorkingDir" or key == "WorkDir":
                if not v.startswith("/"):
                    warnings.append(
                        f"{source}:{ln}: {key} is not absolute; container may fail if relative path isn't present"
                    )
                continue

            if key == "SecurityOpt":
                # free-form but commonly key=value or known toggles
                # Accept common patterns, warn otherwise
                if not (re.match(r"^[a-z0-9_\-]+(=.+)?$", v, re.IGNORECASE)):
                    warnings.append(
                        f"{source}:{ln}: SecurityOpt has unusual format; expected like 'label=disable' or 'apparmor=unconfined'"
                    )
                continue

            if key == "Hostname":
                if not re.match(r"^[a-z0-9][a-z0-9\-\.]{0,251}$", v, re.IGNORECASE):
                    errors.append(f"{source}:{ln}: Hostname invalid")
                continue

            if key == "Network":
                ok, msg = _validate_network_value(v)
                if not ok:
                    errors.append(f"{source}:{ln}: Network invalid: {msg}")
                continue

            # Known but largely free-form keys: Exec, Entrypoint, Image, ContainerName, Annotation, Label handled above
            # No specific validation for other known keys

        return len(errors) == 0, errors, warnings

    def _split_repeatable(self, value: str) -> List[str]:
        """Split repeatable values by comma or newline."""
        # Handle both comma-separated and newline-separated values
        if "\n" in value:
            items = [item.strip() for item in value.split("\n") if item.strip()]
        else:
            items = [item.strip() for item in value.split(",") if item.strip()]
        return items

    def _validate_repeatable_item(self, key: str, item: str) -> Optional[str]:
        """Validate a single item from a repeatable key."""
        item = item.strip()

        if key == "Env":
            if not ENV_RE.match(item):
                return "must be KEY=VALUE format"
        elif key == "Label":
            if not LABEL_RE.match(item):
                return "must be KEY=VALUE format"
        elif key == "Annotation":
            if not ANNOTATION_RE.match(item):
                return "must be KEY=VALUE format"
        elif key == "PublishPort":
            if not PORT_RE.match(item):
                return "must be [IP:]HOST_PORT:CONTAINER_PORT[/PROTOCOL] format"
        elif key == "ExposePort":
            if not EXPOSE_RE.match(item):
                return "must be PORT[-PORT][/PROTOCOL] format"
        elif key == "Dns":
            if not DNS_RE.match(item):
                return "must be valid IP address"
        elif key == "DnsSearch":
            if not DNS_SEARCH_RE.match(item):
                return "must be valid domain name"
        elif key == "Hosts":
            if not HOSTS_RE.match(item):
                return "must be HOSTNAME:IP format"
        elif key == "Sysctl":
            if not SYSCTL_RE.match(item):
                return "must be KEY=VALUE format"
        elif key == "Volume":
            if not VOLUME_SIMPLE_RE.match(item):
                return "must contain source:destination mapping"
        elif key == "Mount":
            if not MOUNT_KEYVAL_RE.match(item):
                return "must be type=TYPE,key=value format"
        elif key == "DeviceCgroupRule":
            if not DEVICE_RULE_RE.match(item):
                return "must be 'c|b MAJOR:MINOR PERMISSIONS' format"
        elif key in {"CapAdd", "CapDrop"}:
            cap = item.upper()
            if not cap.startswith("CAP_"):
                cap = "CAP_" + cap
            if not CAP_RE.match(cap.replace("CAP_", "")):
                return "must be valid capability name"
        elif key == "Network":
            ok, msg = _validate_network_value(item)
            if not ok:
                return msg
        # For other repeatable keys, accept any non-empty value
        elif not item:
            return "cannot be empty"

        return None
