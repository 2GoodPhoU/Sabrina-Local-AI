import os
import subprocess
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def start_home_assistant():
    """Start Home Assistant in Docker with explicit port binding."""
    print("[INFO] Starting Home Assistant...")

    # Ensure Docker is running
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("[ERROR] Docker is not running! Please start Docker and retry.")
        return

    # Check if Home Assistant is already running
    result = subprocess.run(["docker", "ps", "-q", "-f", "name=homeassistant"], capture_output=True, text=True)
    if result.stdout.strip():
        print("[INFO] Home Assistant is already running.")
    else:
        print("[INFO] Starting Home Assistant with explicit port binding...")
        home_dir = os.path.expanduser("~")
        docker_command = [
            "docker", "run", "-d",
            "--name", "homeassistant",
            "--restart", "unless-stopped",
            "-p", "8123:8123",  # ✅ Explicitly binding port 8123
            "-v", f"{home_dir}/homeassistant/config:/config",
            "ghcr.io/home-assistant/home-assistant:stable"
        ]
        subprocess.run(docker_command)
        print("[INFO] Home Assistant started successfully.")

if __name__ == "__main__":
    start_home_assistant()
