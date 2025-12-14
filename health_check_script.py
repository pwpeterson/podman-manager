#!/usr/bin/env python3
"""Simple health check script for model services"""

import socket
import sys
from typing import Tuple


def check_port(host: str, port: int, timeout: int = 5) -> Tuple[bool, str]:
    """Check if a port is accessible"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            return True, "Open"
        else:
            return False, "Closed/Filtered"
    except socket.gaierror:
        return False, "Hostname resolution failed"
    except Exception as e:
        return False, f"Error: {e}"


def check_http_endpoint(
    host: str, port: int, path: str = "/health"
) -> Tuple[bool, str]:
    """Check HTTP endpoint"""
    try:
        import urllib.error
        import urllib.request

        url = f"http://{host}:{port}{path}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "HealthChecker/1.0")

        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.getcode()
            content = response.read().decode("utf-8")[:200]  # First 200 chars
            return True, f"HTTP {status} - {content}"

    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} - {e.reason}"
    except urllib.error.URLError as e:
        return False, f"URL Error: {e.reason}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Main health check function"""
    print("🏥 Model Services Health Check")
    print("=" * 50)

    # Define endpoints to check
    endpoints = [
        ("Model Service Port", "127.0.0.1", 8005, True),  # Model services
        ("Proxy Service Port", "127.0.0.1", 8002, True),  # Proxy service
        ("Alternative Health Port", "127.0.0.1", 8001, False),  # Sometimes used
    ]

    results = []

    for name, host, port, check_http in endpoints:
        print(f"\n🔍 Checking {name} ({host}:{port})...")

        # Check port accessibility
        port_open, port_msg = check_port(host, port)
        print(f"  Port Status: {'✅' if port_open else '❌'} {port_msg}")

        if port_open and check_http:
            # Check HTTP endpoint
            http_ok, http_msg = check_http_endpoint(host, port)
            print(f"  HTTP Status: {'✅' if http_ok else '❌'} {http_msg}")
            results.append((name, port, port_open, http_ok if check_http else None))
        else:
            results.append((name, port, port_open, None))

    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)

    all_good = True
    for name, port, port_open, http_ok in results:
        status = (
            "🟢 HEALTHY"
            if (port_open and (http_ok is None or http_ok))
            else "🔴 UNHEALTHY"
        )
        print(f"  {name}: {status}")
        if not port_open or (http_ok is not None and not http_ok):
            all_good = False

    if all_good:
        print("\n✅ All services appear healthy!")
        return 0
    else:
        print("\n❌ Some services have issues. Check the details above.")
        print("\n🔧 TROUBLESHOOTING SUGGESTIONS:")
        print("   1. Check if vllm-glm4-9b-chat service is running:")
        print("      systemctl --user status vllm-glm4-9b-chat")
        print("   2. Check service logs:")
        print("      journalctl --user -u vllm-glm4-9b-chat -f")
        print("   3. Try restarting the service:")
        print("      systemctl --user restart vllm-glm4-9b-chat")
        print("   4. Check if proxy service is running:")
        print("      systemctl --user status sys-services-model-proxy")
        return 1


if __name__ == "__main__":
    sys.exit(main())
