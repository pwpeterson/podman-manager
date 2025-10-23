#!/usr/bin/env python3
"""Diagnose the AI analysis issue."""

import os
import sys
from pathlib import Path


def diagnose_issue():
    """Diagnose why the AI analysis method is not found."""
    print("🔍 Diagnosing AI analysis issue...\n")

    # Check current working directory
    print(f"Current directory: {os.getcwd()}")

    # Check if reinit_manager.py exists
    reinit_file = Path("reinit_manager.py")
    if reinit_file.exists():
        print(f"✅ reinit_manager.py exists: {reinit_file.absolute()}")
    else:
        print("❌ reinit_manager.py not found in current directory")
        return

    # Check Python path
    print(f"\nPython executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Python path: {sys.path[:3]}...")  # Show first 3 entries

    # Try to import and check the method
    try:
        # Add current directory to path if not already there
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
            print(f"\n✅ Added {os.getcwd()} to Python path")

        from reinit_manager import ReinitManager

        print("\n✅ Successfully imported ReinitManager")

        # Check if method exists
        if hasattr(ReinitManager, "_ai_analyze_reinit_failure"):
            print("✅ _ai_analyze_reinit_failure method exists")

            # Get method info
            method = getattr(ReinitManager, "_ai_analyze_reinit_failure")
            print(f"   Method: {method}")
            print(f"   Module: {method.__module__}")

            # Check file modification time
            mtime = reinit_file.stat().st_mtime
            import datetime

            mod_time = datetime.datetime.fromtimestamp(mtime)
            print(f"   File modified: {mod_time}")

        else:
            print("❌ _ai_analyze_reinit_failure method NOT found")

            # List all methods starting with _ai
            ai_methods = [attr for attr in dir(ReinitManager) if attr.startswith("_ai")]
            print(f"   Available _ai methods: {ai_methods}")

            # List all methods
            all_methods = [
                attr for attr in dir(ReinitManager) if not attr.startswith("__")
            ]
            print(f"   All methods: {len(all_methods)} total")

    except ImportError as e:
        print(f"❌ Failed to import ReinitManager: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    # Check for cache files
    cache_dir = Path("__pycache__")
    if cache_dir.exists():
        cache_files = list(cache_dir.glob("reinit_manager.cpython-*.pyc"))
        if cache_files:
            print(f"\n⚠️  Found cache files: {[f.name for f in cache_files]}")
            for cache_file in cache_files:
                mtime = cache_file.stat().st_mtime
                import datetime

                mod_time = datetime.datetime.fromtimestamp(mtime)
                print(f"   {cache_file.name}: {mod_time}")
        else:
            print("\n✅ No reinit_manager cache files found")
    else:
        print("\n✅ No __pycache__ directory found")

    # Check if pm command might be using a different Python
    print("\n🔍 Checking pm command location...")
    try:
        import subprocess

        result = subprocess.run(["which", "pm"], capture_output=True, text=True)
        if result.returncode == 0:
            pm_path = result.stdout.strip()
            print(f"pm command found at: {pm_path}")

            # Check if it's a script and what Python it uses
            if os.path.exists(pm_path):
                with open(pm_path, "r") as f:
                    first_line = f.readline().strip()
                    if first_line.startswith("#!"):
                        print(f"pm shebang: {first_line}")
        else:
            print("pm command not found in PATH")
    except Exception as e:
        print(f"Error checking pm command: {e}")


if __name__ == "__main__":
    diagnose_issue()
