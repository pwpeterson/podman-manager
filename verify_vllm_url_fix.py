#!/usr/bin/env python3
"""Verify that VLLM_URL is properly updated during vLLM model reinit."""

import subprocess
from pathlib import Path


def check_service_file_exists(service_name: str) -> bool:
    """Check if a systemd service file exists."""
    service_path = Path.home() / ".config/systemd/user" / f"{service_name}.service"
    return service_path.exists()


def get_vllm_url_from_service_file(service_name: str) -> str:
    """Extract VLLM_URL from systemd service file."""
    service_path = Path.home() / ".config/systemd/user" / f"{service_name}.service"

    if not service_path.exists():
        return "Service file not found"

    try:
        with open(service_path, "r") as f:
            content = f.read()

        # Look for VLLM_URL environment variable
        for line in content.split("\n"):
            if "VLLM_URL=" in line:
                # Extract the URL value
                if "=" in line:
                    return line.split("VLLM_URL=")[1].split()[0].strip("\"'")

        return "VLLM_URL not found in service file"
    except Exception as e:
        return f"Error reading service file: {e}"


def get_container_env_var(container_name: str, env_var: str) -> str:
    """Get environment variable from running container."""
    try:
        cmd = [
            "podman",
            "inspect",
            container_name,
            "--format",
            '{{range .Config.Env}}{{if eq (index (split . "=") 0) "'
            + env_var
            + '"}}{{.}}{{end}}{{end}}',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        if result.stdout.strip():
            return (
                result.stdout.strip().split("=", 1)[1]
                if "=" in result.stdout.strip()
                else "Not found"
            )
        else:
            return "Environment variable not found"
    except subprocess.CalledProcessError:
        return "Container not found or not running"
    except Exception as e:
        return f"Error: {e}"


def main():
    """Main verification function."""
    print("🔍 Verifying VLLM_URL Update Fix")
    print("=" * 50)

    # Check if sys-services-vllm-proxy service file exists
    proxy_service = "sys-services-vllm-proxy"

    print(f"\n1. Checking {proxy_service} service file...")
    if check_service_file_exists(proxy_service):
        print("   ✅ Service file exists")

        # Get VLLM_URL from service file
        vllm_url_from_file = get_vllm_url_from_service_file(proxy_service)
        print(f"   📄 VLLM_URL in service file: {vllm_url_from_file}")

        # Get VLLM_URL from running container
        vllm_url_from_container = get_container_env_var(proxy_service, "VLLM_URL")
        print(f"   🐳 VLLM_URL in container: {vllm_url_from_container}")

        # Compare them
        if (
            vllm_url_from_file == vllm_url_from_container
            and "localhost" not in vllm_url_from_file
        ):
            print("   ✅ VLLM_URL is properly configured (not using localhost)")
        elif "localhost" in vllm_url_from_file:
            print("   ❌ VLLM_URL still uses localhost - fix needed")
        else:
            print("   ⚠️  Service file and container VLLM_URL don't match")
    else:
        print("   ❌ Service file not found")

    # Check container logs for VLLM_URL
    print("\n2. Checking container logs for VLLM_URL...")
    try:
        cmd = ["podman", "logs", "--tail", "10", proxy_service]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        for line in result.stdout.split("\n"):
            if "vLLM Backend URL:" in line:
                print(f"   📋 Log shows: {line.strip()}")
                if "localhost" in line:
                    print("   ❌ Still using localhost in logs")
                else:
                    print("   ✅ Using proper container name in logs")
                break
        else:
            print("   ⚠️  No vLLM Backend URL found in recent logs")
    except subprocess.CalledProcessError:
        print("   ❌ Could not retrieve container logs")

    print("\n3. Fix Implementation Status:")

    # Check if the fix is in place
    vllm_reinit_flow_path = Path("managers/reinit/vllm_reinit_flow.py")
    if vllm_reinit_flow_path.exists():
        with open(vllm_reinit_flow_path, "r") as f:
            content = f.read()

        if 'remove_service_file("sys-services-vllm-proxy.service"' in content:
            print("   ✅ Fix is implemented: service file removal added")
        else:
            print("   ❌ Fix not implemented: service file removal missing")
    else:
        print("   ❌ vllm_reinit_flow.py not found")

    print("\n" + "=" * 50)
    print("\n💡 To test the fix:")
    print("   1. Run: python podman_manager.py reinit <vllm-model-name>")
    print("   2. Check logs: podman logs sys-services-vllm-proxy")
    print("   3. Verify VLLM_URL shows container name, not localhost")


if __name__ == "__main__":
    main()
