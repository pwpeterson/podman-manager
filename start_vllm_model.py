import socket
import subprocess
import sys

import psutil
from loguru import logger
from rich.console import Console

# Setup rich logging
console = Console()
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="{time} {level} {message}",
    backtrace=True,
    diagnose=True,
    colorize=True,
    enqueue=True,
    catch=True,
)

# Function to check if port is in use


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


# Function to find and kill process using port


def kill_process_on_port(port):
    for proc in psutil.process_iter(["pid", "name", "connections"]):
        try:
            for conn in proc.info["connections"]:
                if conn.laddr.port == port:
                    logger.info(
                        f"Found process {proc.info['name']} (PID {proc.info['pid']}) using port {port}, terminating it..."
                    )
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                        logger.info(
                            f"Process {proc.info['pid']} terminated successfully."
                        )
                        return True
                    except psutil.TimeoutExpired:
                        logger.warning(
                            f"Process {proc.info['pid']} did not terminate in time, killing it..."
                        )
                        proc.kill()
                        proc.wait(timeout=5)
                        logger.info(f"Process {proc.info['pid']} killed.")
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    logger.info(f"No process found using port {port}.")
    return False


# Function to run a shell command and log output


def run_command(cmd):
    logger.info(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Command succeeded: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with error: {e.stderr.strip()}")
        return False


# Main orchestration function


def switch_vllm_backend(new_vllm_model_name: str):
    logger.info(f"Switching vLLM backend to container: {new_vllm_model_name}")

    # Step 1: Kill any process on port 8005
    if is_port_in_use(8005):
        killed = kill_process_on_port(8005)
        if not killed:
            logger.error("Failed to kill existing process on port 8005. Aborting.")
            return
    else:
        logger.info("No existing process on port 8005.")

    # Step 2: Start the new vLLM backend container
    # Here we assume podman is used and container is already created but stopped
    # Start the container
    start_cmd = ["podman", "start", new_vllm_model_name]
    if not run_command(start_cmd):
        logger.error(
            f"Failed to start backend container {new_vllm_model_name}. Aborting."
        )
        return

    # Step 3: Restart the proxy container with updated VLLM_URL
    proxy_container = "vllm-proxy"
    vllm_url = f"http://{new_vllm_model_name}:8005"

    # Stop proxy
    stop_cmd = ["podman", "stop", proxy_container]
    run_command(stop_cmd)

    # Remove proxy
    rm_cmd = ["podman", "rm", proxy_container]
    run_command(rm_cmd)

    # Run proxy with updated env
    # NOTE: You must customize this command with your actual proxy container options
    run_proxy_cmd = [
        "podman",
        "run",
        "-d",
        "--name",
        proxy_container,
        "--network",
        "local-ai-network",
        "-e",
        f"VLLM_URL={vllm_url}",
        # Add other env vars here as needed
        "-p",
        "8002:8002",
        "your-vllm-proxy-image",
    ]

    if not run_command(run_proxy_cmd):
        logger.error("Failed to start proxy container with updated VLLM_URL.")
        return

    logger.info("Switched vLLM backend and restarted proxy successfully.")


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        console.print("Usage: python switch_vllm_backend.py <new_vllm_model_name>")
        sys.exit(1)
    switch_vllm_backend(sys.argv[1])
