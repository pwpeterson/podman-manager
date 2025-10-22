#!/usr/bin/env python3
"""Fix RestartPolicy in quadlet files - move from [Container] to [Service] section as Restart."""

import re
from pathlib import Path


def fix_quadlet_file(file_path):
    """Fix a single quadlet file by moving RestartPolicy from [Container] to [Service] section."""
    print(f"Fixing {file_path}...")

    with open(file_path, "r") as f:
        content = f.read()

    # Remove RestartPolicy from [Container] section
    content = re.sub(r"^RestartPolicy=.*\n", "", content, flags=re.MULTILINE)

    # Add Restart=always to [Service] section
    if "[Service]" in content:
        content = re.sub(r"(\[Service\]\n)", r"\1Restart=always\n", content)
    else:
        # If no [Service] section exists, add it before [Install]
        content = re.sub(r"(\[Install\])", r"[Service]\nRestart=always\n\n\1", content)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"✓ Fixed {file_path}")


def main():
    """Fix all quadlet files with RestartPolicy issues."""
    systemd_dir = Path.home() / ".config" / "containers" / "systemd"

    if not systemd_dir.exists():
        print(f"Systemd directory not found: {systemd_dir}")
        return

    # Find all .container files that contain RestartPolicy
    files_to_fix = []
    for container_file in systemd_dir.glob("*.container"):
        try:
            with open(container_file, "r") as f:
                content = f.read()
                if "RestartPolicy=" in content:
                    files_to_fix.append(container_file)
        except Exception as e:
            print(f"Error reading {container_file}: {e}")

    if not files_to_fix:
        print("No files need fixing.")
        return

    print(f"Found {len(files_to_fix)} files to fix:")
    for file_path in files_to_fix:
        print(f"  - {file_path.name}")

    print("\nFixing files...")
    for file_path in files_to_fix:
        try:
            fix_quadlet_file(file_path)
        except Exception as e:
            print(f"Error fixing {file_path}: {e}")

    print(f"\n✓ Fixed {len(files_to_fix)} quadlet files")
    print("\nNext steps:")
    print("1. Run: systemctl --user daemon-reload")
    print("2. Run: pm start sys-roo-token-tracker")


if __name__ == "__main__":
    main()
