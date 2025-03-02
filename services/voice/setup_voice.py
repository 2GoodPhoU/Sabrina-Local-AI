#!/usr/bin/env python3
"""
Installation Script for Sabrina Voice Service
============================================
Sets up the required dependencies for the voice service component.
"""

import os
import sys
import subprocess
import platform
import argparse


def print_section(title):
    """Print a section title"""
    print("\n" + "=" * 60)
    print(f" {title} ".center(60))
    print("=" * 60)


def print_status(message, status, success=True):
    """Print a status message"""
    status_symbol = "✓" if success else "✗"
    status_color = "\033[92m" if success else "\033[91m"  # Green or Red
    reset_color = "\033[0m"
    print(f"{status_color}{status_symbol}{reset_color} {message:<40} {status}")


def run_command(cmd, shell=False):
    """Run a command and return the result"""
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def check_python_version():
    """Check if Python version is adequate"""
    print_section("Checking Python Version")

    python_version = platform.python_version()
    version_parts = list(map(int, python_version.split(".")))

    if version_parts[0] >= 3 and version_parts[1] >= 8:
        print_status(
            f"Python version: {python_version}",
            "OK - Compatible with Voice Service",
            True,
        )
        return True
    else:
        print_status(
            f"Python version: {python_version}",
            "WARNING - Python 3.8+ recommended",
            False,
        )
        return False


def setup_virtual_env(env_dir="venv"):
    """Set up a virtual environment"""
    print_section("Setting Up Virtual Environment")

    # Check if venv exists
    if os.path.exists(env_dir):
        print_status(
            f"Virtual environment directory: {env_dir}", "Found (existing)", True
        )
        return True

    # Create new venv
    success, output = run_command([sys.executable, "-m", "venv", env_dir])

    if success:
        print_status(f"Virtual environment: {env_dir}", "Created successfully", True)
        return True
    else:
        print_status(f"Virtual environment: {env_dir}", "Failed to create", False)
        print(f"Error: {output}")
        return False


def install_dependencies(env_dir="venv", install_audio=True, install_gpu=False):
    """Install required dependencies"""
    print_section("Installing Dependencies")

    # Determine pip path based on platform
    if platform.system() == "Windows":
        pip_path = os.path.join(env_dir, "Scripts", "pip")
    else:
        pip_path = os.path.join(env_dir, "bin", "pip")

    # Install required packages
    requirements = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "requests",
        "python-dotenv",
        "aiofiles",
        "numpy",
        "scipy",
        "librosa",
    ]

    # Add TTS and audio playback packages if requested
    if install_audio:
        requirements.extend(["TTS", "playsound", "pygame", "sounddevice", "soundfile"])

    # Install base requirements
    print("Installing base requirements...")
    success, output = run_command([pip_path, "install", "--upgrade", "pip"])

    for package in requirements:
        success, output = run_command([pip_path, "install", package])
        print_status(
            f"Package: {package}", "Installed" if success else "Failed", success
        )

    # Install PyTorch with GPU support if requested
    if install_gpu:
        print("\nInstalling PyTorch with GPU support...")
        if platform.system() == "Windows":
            # For Windows
            success, output = run_command(
                [
                    pip_path,
                    "install",
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--index-url",
                    "https://download.pytorch.org/whl/cu118",
                ]
            )
        else:
            # For Linux/Mac
            success, output = run_command(
                [pip_path, "install", "torch", "torchvision", "torchaudio"]
            )

        print_status(
            "PyTorch with GPU support", "Installed" if success else "Failed", success
        )

    return True


def setup_docker():
    """Set up Docker configuration"""
    print_section("Setting Up Docker")

    # Check if Docker is installed
    success, output = run_command(["docker", "--version"])

    if success:
        print_status("Docker", "Installed", True)
    else:
        print_status("Docker", "Not installed", False)
        print(
            "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
        )
        print("Then run this script again.")
        return False

    # Check if Docker Compose is available
    success, output = run_command(["docker", "compose", "version"])

    if not success:
        # Try older docker-compose command
        success, output = run_command(["docker-compose", "--version"])

    if success:
        print_status("Docker Compose", "Installed", True)
    else:
        print_status("Docker Compose", "Not installed", False)
        print("Please install Docker Compose: https://docs.docker.com/compose/install/")
        return False

    # Check if voice service Dockerfile exists
    if os.path.exists("voice.Dockerfile"):
        print_status("voice.Dockerfile", "Found", True)
    else:
        print_status("voice.Dockerfile", "Not found", False)
        print("Creating voice.Dockerfile...")

        with open("voice.Dockerfile", "w") as f:
            f.write(
                """# Voice Service Dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy required files
COPY voice_docker_requirements.txt requirements.txt
COPY voice_api.py voice_api.py
COPY voice_api_client.py voice_api_client.py
COPY tts_implementation.py tts_implementation.py
COPY voice_playback.py voice_playback.py

# Create necessary directories
RUN mkdir -p logs data/audio_cache config models

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose API port
EXPOSE 8100

# Set Python path
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Set environment variables
ENV VOICE_API_PORT=8100
ENV VOICE_API_KEY=sabrina-dev-key

# Start Voice API
CMD ["python", "voice_api.py"]
"""
            )
        print_status("voice.Dockerfile", "Created", True)

    # Check if docker-compose.yml exists
    if os.path.exists("docker-compose.yml"):
        print_status("docker-compose.yml", "Found", True)
    else:
        print_status("docker-compose.yml", "Not found", False)
        print("Creating docker-compose.yml...")

        with open("docker-compose.yml", "w") as f:
            f.write(
                """services:
  voice-api:
    build:
      context: .
      dockerfile: voice.Dockerfile
    container_name: sabrina-voice-api
    ports:
      - "8100:8100"
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./logs:/app/logs
      - ./models:/app/models  # Add models volume
    environment:
      - VOICE_API_PORT=8100
      - VOICE_API_KEY=${VOICE_API_KEY:-sabrina-dev-key}
      - DEBUG=${DEBUG:-false}
    restart: unless-stopped
"""
            )
        print_status("docker-compose.yml", "Created", True)

    # Check if voice_docker_requirements.txt exists
    if os.path.exists("voice_docker_requirements.txt"):
        print_status("voice_docker_requirements.txt", "Found", True)
    else:
        print_status("voice_docker_requirements.txt", "Not found", False)
        print("Creating voice_docker_requirements.txt...")

        with open("voice_docker_requirements.txt", "w") as f:
            f.write(
                """# TTS Core Dependencies
TTS>=0.13.0
torch
numpy
scipy
librosa
soundfile>=0.10.3

# Audio Playback Dependencies
playsound>=1.3.0
pygame>=2.1.0
sounddevice>=0.4.4

# API and Web Dependencies
fastapi>=0.89.0
uvicorn>=0.20.0
requests>=2.28.0
python-multipart>=0.0.5
aiofiles>=0.8.0
pydantic>=1.10.0
python-dotenv>=0.21.0

# Optional Dependencies
matplotlib>=3.6.0  # For visualizations
tensorboard>=2.11.0  # For training monitoring
"""
            )
        print_status("voice_docker_requirements.txt", "Created", True)

    return True


def create_directories():
    """Create required directories"""
    print_section("Creating Required Directories")

    directories = ["logs", "data", "data/audio_cache", "config", "models"]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print_status(
            f"Directory: {directory}",
            "Created" if os.path.exists(directory) else "Failed",
            os.path.exists(directory),
        )

    return True


def build_docker_image():
    """Build the Docker image"""
    print_section("Building Docker Image")

    print("Building the Docker image (this may take a while)...")
    success, output = run_command(["docker", "compose", "build"])

    if success:
        print_status("Docker image build", "Successful", True)
    else:
        print_status("Docker image build", "Failed", False)
        print(f"Error: {output}")
        return False

    return True


def start_docker_container():
    """Start the Docker container"""
    print_section("Starting Docker Container")

    print("Starting the Docker container...")
    success, output = run_command(["docker", "compose", "up", "-d"])

    if success:
        print_status("Docker container", "Started successfully", True)
    else:
        print_status("Docker container", "Failed to start", False)
        print(f"Error: {output}")
        return False

    return True


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Setup Sabrina Voice Service")
    parser.add_argument(
        "--skip-venv", action="store_true", help="Skip virtual environment creation"
    )
    parser.add_argument(
        "--skip-deps", action="store_true", help="Skip dependency installation"
    )
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker setup")
    parser.add_argument(
        "--with-gpu", action="store_true", help="Install with GPU support"
    )
    args = parser.parse_args()

    print_section("Sabrina Voice Service Setup")

    # Check Python version
    check_python_version()

    # Create directories
    create_directories()

    # Set up virtual environment
    if not args.skip_venv:
        setup_virtual_env()

    # Install dependencies
    if not args.skip_deps:
        install_dependencies(install_gpu=args.with_gpu)

    # Set up Docker
    if not args.skip_docker:
        docker_ok = setup_docker()

        if docker_ok:
            # Build Docker image
            build_docker_image()

            # Start Docker container
            start_docker_container()

    # Print success message
    print_section("Setup Complete")
    print("\nSabrina Voice Service has been set up successfully!")
    print("\nTo start the voice service:")
    print("1. With Docker (recommended): ")
    print("   docker compose up -d")
    print("\n2. Without Docker:")
    print("   python voice_api.py")
    print("\nTo test the voice service:")
    print("   python voice_module_test.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
