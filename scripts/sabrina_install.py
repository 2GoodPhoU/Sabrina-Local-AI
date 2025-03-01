#!/usr/bin/env python3
"""
Installation Script for Sabrina AI
=================================
Sets up the Sabrina AI environment and installs required dependencies.
"""

import os
import sys
import subprocess
import platform
import argparse
import shutil


def print_step(message):
    """Print a step message"""
    print(f"\n\033[1;34m==>\033[0m \033[1m{message}\033[0m")


def print_substep(message):
    """Print a substep message"""
    print(f"  \033[1;32m->\033[0m {message}")


def print_error(message):
    """Print an error message"""
    print(f"\033[1;31mERROR: {message}\033[0m")


def print_warning(message):
    """Print a warning message"""
    print(f"\033[1;33mWARNING: {message}\033[0m")


def print_success(message):
    """Print a success message"""
    print(f"\033[1;32mSUCCESS: {message}\033[0m")


def run_command(command, shell=False, check=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {e}")
        print(e.stderr)
        if check:
            raise
        return e


def check_python_version():
    """Check if Python version is 3.10+"""
    print_step("Checking Python version")

    python_version = platform.python_version()
    major, minor, _ = map(int, python_version.split("."))

    if major < 3 or (major == 3 and minor < 10):
        print_error(f"Python 3.10+ is required, but you have {python_version}")
        print_warning("Please install Python 3.10 or higher")
        return False

    print_substep(f"Found Python {python_version} - OK")
    return True


def check_system_dependencies():
    """Check system dependencies"""
    print_step("Checking system dependencies")

    system = platform.system()
    missing_deps = []

    if system == "Linux":
        # Check Linux dependencies
        dependencies = {
            "tesseract": "Tesseract OCR",
            "ffmpeg": "FFmpeg",
            "pulseaudio": "PulseAudio",
        }

        for command, name in dependencies.items():
            result = run_command(["which", command], check=False)
            if result.returncode != 0:
                missing_deps.append(name)
            else:
                print_substep(f"Found {name} - OK")

    elif system == "Darwin":  # macOS
        # Check macOS dependencies
        dependencies = {"tesseract": "Tesseract OCR", "ffmpeg": "FFmpeg"}

        for command, name in dependencies.items():
            result = run_command(["which", command], check=False)
            if result.returncode != 0:
                missing_deps.append(name)
            else:
                print_substep(f"Found {name} - OK")

    elif system == "Windows":
        # Check Windows dependencies
        print_warning("On Windows, please ensure you have installed:")
        print_warning(
            "1. Tesseract OCR (https://github.com/UB-Mannheim/tesseract/wiki)"
        )
        print_warning("2. FFmpeg (https://ffmpeg.org/download.html)")
        print_warning("3. Add them to your PATH environment variable")

        # Try to check anyway
        try:
            result = run_command(["where", "tesseract"], check=False)
            if result.returncode == 0:
                print_substep("Found Tesseract OCR - OK")
            else:
                missing_deps.append("Tesseract OCR")

            result = run_command(["where", "ffmpeg"], check=False)
            if result.returncode == 0:
                print_substep("Found FFmpeg - OK")
            else:
                missing_deps.append("FFmpeg")
        except Exception:
            print_warning("Could not check Windows dependencies automatically")

    if missing_deps:
        print_warning(f"Missing dependencies: {', '.join(missing_deps)}")

        if system == "Linux":
            print_warning("Install them with your package manager, e.g.:")
            print_warning("sudo apt-get install tesseract-ocr ffmpeg pulseaudio")
        elif system == "Darwin":
            print_warning("Install them with Homebrew:")
            print_warning("brew install tesseract ffmpeg")

        return False

    return True


def create_virtual_environment(args):
    """Create a virtual environment"""
    print_step("Setting up virtual environment")

    venv_dir = args.venv_dir or "venv"

    # Check if virtual environment already exists
    if os.path.exists(venv_dir):
        if args.force:
            print_warning(f"Removing existing virtual environment: {venv_dir}")
            shutil.rmtree(venv_dir)
        else:
            print_warning(f"Virtual environment already exists: {venv_dir}")
            print_warning("Use --force to overwrite it")
            return False

    # Create virtual environment
    print_substep(f"Creating virtual environment in: {venv_dir}")
    result = run_command([sys.executable, "-m", "venv", venv_dir], check=False)

    if result.returncode != 0:
        print_error("Failed to create virtual environment")
        return False

    print_substep("Virtual environment created successfully")

    # Get path to Python and pip in the virtual environment
    if platform.system() == "Windows":
        python_path = os.path.join(venv_dir, "Scripts", "python.exe")
        pip_path = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        python_path = os.path.join(venv_dir, "bin", "python")
        pip_path = os.path.join(venv_dir, "bin", "pip")

    # Upgrade pip
    print_substep("Upgrading pip")
    run_command([python_path, "-m", "pip", "install", "--upgrade", "pip"])

    return python_path, pip_path


def install_python_dependencies(pip_path, args):
    """Install Python dependencies"""
    print_step("Installing Python dependencies")

    # Install Python dependencies
    requirements_file = os.path.join(os.path.dirname(__file__), "requirements.txt")

    if not os.path.exists(requirements_file):
        print_error(f"Requirements file not found: {requirements_file}")
        return False

    print_substep("Installing dependencies from requirements.txt")
    result = run_command([pip_path, "install", "-r", requirements_file])

    if result.returncode != 0:
        print_error("Failed to install dependencies")
        return False

    print_substep("Dependencies installed successfully")

    # Install optional dependencies based on flags
    optional_packages = []

    if args.gpu:
        print_substep("Installing GPU support")
        optional_packages.extend(
            [
                "torch==2.0.0+cu118",
                "torchvision==0.15.1+cu118",
                "-f",
                "https://download.pytorch.org/whl/torch_stable.html",
            ]
        )

    if args.full:
        print_substep("Installing full package set")
        optional_packages.extend(["paddlepaddle", "paddleocr", "TTS"])

    if optional_packages:
        print_substep("Installing optional packages")
        result = run_command([pip_path, "install"] + optional_packages)

        if result.returncode != 0:
            print_warning("Failed to install some optional dependencies")
            print_warning("You may need to install them manually")

    return True


def create_project_structure():
    """Create the project directory structure"""
    print_step("Creating project directory structure")

    directories = [
        "core",
        "utilities",
        "services/voice",
        "services/vision",
        "services/hearing",
        "services/automation",
        "services/smart_home",
        "services/presence",
        "scripts",
        "config",
        "logs",
        "data",
        "data/captures",
        "models",
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print_substep(f"Created directory: {directory}")

    return True


def setup_configuration():
    """Set up configuration files"""
    print_step("Setting up configuration files")

    # Create settings.yaml if it doesn't exist
    config_file = "config/settings.yaml"
    if not os.path.exists(config_file):
        print_substep(f"Creating default configuration: {config_file}")

        with open(config_file, "w") as f:
            f.write(
                """# Sabrina AI Configuration

core:
  debug_mode: false
  log_level: INFO
  console_mode: false

voice:
  enabled: true
  api_url: http://localhost:8100
  volume: 0.8
  speed: 1.0
  pitch: 1.0
  emotion: normal

vision:
  enabled: true
  capture_method: auto
  use_ocr: true
  use_object_detection: true
  max_images: 5

hearing:
  enabled: true
  wake_word: hey sabrina
  silence_threshold: 0.03
  model_path: models/vosk-model
  use_hotkey: true
  hotkey: ctrl+shift+s

automation:
  mouse_move_duration: 0.2
  typing_interval: 0.1
  failsafe: true

memory:
  max_entries: 20
  use_vector_db: false
  vector_db_path: data/vectordb

smart_home:
  enable: false
  home_assistant_url: http://homeassistant.local:8123
  use_google_home: false

presence:
  enable: false
  theme: default
  transparency: 0.85
  click_through: false
"""
            )
    else:
        print_substep(f"Configuration file already exists: {config_file}")

    return True


def download_models(python_path):
    """Download required models"""
    print_step("Downloading required models")

    # Check if we can download the Vosk model
    vosk_model_dir = "models/vosk-model"
    if not os.path.exists(vosk_model_dir) or len(os.listdir(vosk_model_dir)) == 0:
        print_substep("Downloading Vosk model for speech recognition")

        # Create a small Python script to download the model
        download_script = """
import os
import wget
import zipfile

model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
model_zip_path = "models/vosk-model.zip"

# Create directory if it doesn't exist
os.makedirs("models", exist_ok=True)

# Download model
print("Downloading Vosk model...")
wget.download(model_url, model_zip_path)

# Extract model
print("\\nExtracting Vosk model...")
with zipfile.ZipFile(model_zip_path, 'r') as zip_ref:
    zip_ref.extractall("models/")

# Remove zip file
os.remove(model_zip_path)

# Rename directory if needed
extracted_dir = None
for item in os.listdir("models/"):
    if os.path.isdir(os.path.join("models/", item)) and "vosk-model" in item:
        extracted_dir = item
        break

if extracted_dir and extracted_dir != "vosk-model":
    os.rename(os.path.join("models/", extracted_dir), "models/vosk-model")

print("Vosk model downloaded and extracted successfully")
"""

        # Write the script to a temporary file
        with open("download_vosk.py", "w") as f:
            f.write(download_script)

        # Run the script
        result = run_command([python_path, "download_vosk.py"], check=False)

        # Remove the temporary script
        os.remove("download_vosk.py")

        if result.returncode != 0:
            print_warning("Failed to download Vosk model")
            print_warning("You may need to download it manually from:")
            print_warning("https://alphacephei.com/vosk/models")
    else:
        print_substep("Vosk model already exists")

    return True


def setup_docker():
    """Set up Docker configuration"""
    print_step("Setting up Docker configuration")

    # Check if Docker is installed
    result = run_command(["docker", "--version"], check=False)

    if result.returncode != 0:
        print_warning("Docker not found")
        print_warning("To use Docker, please install Docker Desktop:")
        print_warning("https://www.docker.com/products/docker-desktop")
        return False

    print_substep("Docker is installed")

    # Check if Docker Compose is installed
    result = run_command(["docker-compose", "--version"], check=False)

    if result.returncode != 0:
        print_warning("Docker Compose not found")
        print_warning("To use Docker Compose, please install it:")
        print_warning("https://docs.docker.com/compose/install/")
        return False

    print_substep("Docker Compose is installed")

    # Create Docker-related files
    if not os.path.exists("Dockerfile"):
        print_substep("Creating Dockerfile")
        with open("Dockerfile", "w") as f:
            f.write(
                """# Base Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=off \\
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    python3-dev \\
    python3-pip \\
    python3-setuptools \\
    python3-wheel \\
    python3-venv \\
    pulseaudio \\
    ffmpeg \\
    libsm6 \\
    libxext6 \\
    libxrender-dev \\
    libgl1-mesa-glx \\
    tesseract-ocr \\
    libtesseract-dev \\
    wget \\
    curl \\
    git \\
    && apt-get clean \\
    && rm -rf /var/lib/apt/lists/*

# Create directory structure
RUN mkdir -p /app/logs /app/data /app/config /app/models

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user to run the application
RUN useradd -m sabrina
RUN chown -R sabrina:sabrina /app
USER sabrina

# Set up entrypoint
ENTRYPOINT ["python", "scripts/start_sabrina.py"]

# Default command (can be overridden)
CMD ["--config", "config/settings.yaml"]
"""
            )
    else:
        print_substep("Dockerfile already exists")

    if not os.path.exists("docker-compose.yml"):
        print_substep("Creating docker-compose.yml")
        with open("docker-compose.yml", "w") as f:
            f.write(
                """version: '3.8'

services:
  # Main Sabrina AI Core
  sabrina-core:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: sabrina-core
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./logs:/app/logs
      - ./models:/app/models
    environment:
      - SABRINA_CORE_DEBUG_MODE=false
      - PYTHONUNBUFFERED=1
    depends_on:
      - voice-service
    networks:
      - sabrina-network
    command: ["--config", "config/settings.yaml"]

  # Voice Service
  voice-service:
    build:
      context: ./services/voice
      dockerfile: voice.Dockerfile
    container_name: sabrina-voice
    ports:
      - "8100:8100"
    volumes:
      - ./config:/app/config
      - ./models:/app/models
    networks:
      - sabrina-network

networks:
  sabrina-network:
    driver: bridge
"""
            )
    else:
        print_substep("docker-compose.yml already exists")

    return True


def create_startup_scripts():
    """Create startup scripts"""
    print_step("Creating startup scripts")

    # Create run.sh/run.bat script
    if platform.system() == "Windows":
        script_name = "run.bat"
        script_content = """@echo off
REM Activate virtual environment
call venv\\Scripts\\activate.bat

REM Start the voice service
start cmd /k "python services/voice/voice_api.py"

REM Wait for voice service to start
timeout /t 5

REM Start the main Sabrina AI system
python scripts/start_sabrina.py

REM Deactivate virtual environment
call venv\\Scripts\\deactivate.bat
"""
    else:
        script_name = "run.sh"
        script_content = """#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Start the voice service
python services/voice/voice_api.py &
VOICE_PID=$!

# Wait for voice service to start
sleep 5

# Start the main Sabrina AI system
python scripts/start_sabrina.py

# Kill the voice service when done
kill $VOICE_PID

# Deactivate virtual environment
deactivate
"""

    if not os.path.exists(script_name):
        print_substep(f"Creating startup script: {script_name}")
        with open(script_name, "w") as f:
            f.write(script_content)

        # Make the script executable on Unix systems
        if platform.system() != "Windows":
            os.chmod(script_name, 0o755)
    else:
        print_substep(f"Startup script already exists: {script_name}")

    return True


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Sabrina AI Installation Script")

    parser.add_argument(
        "--venv-dir",
        type=str,
        default="venv",
        help="Virtual environment directory (default: venv)",
    )

    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing files and directories"
    )

    parser.add_argument(
        "--skip-checks", action="store_true", help="Skip dependency checks"
    )

    parser.add_argument("--gpu", action="store_true", help="Install GPU support")

    parser.add_argument(
        "--full", action="store_true", help="Install all optional dependencies"
    )

    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker setup")

    return parser.parse_args()


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("  SABRINA AI - Installation Script  ".center(60))
    print("=" * 60 + "\n")

    args = parse_arguments()

    # 1. Check Python version
    if not args.skip_checks:
        if not check_python_version():
            return 1

    # 2. Check system dependencies
    if not args.skip_checks:
        if not check_system_dependencies():
            print_warning("Some dependencies are missing, but we'll continue anyway")

    # 3. Create virtual environment
    venv_result = create_virtual_environment(args)
    if not venv_result:
        return 1

    python_path, pip_path = venv_result

    # 4. Install Python dependencies
    if not install_python_dependencies(pip_path, args):
        return 1

    # 5. Create project structure
    if not create_project_structure():
        return 1

    # 6. Set up configuration
    if not setup_configuration():
        return 1

    # 7. Download models
    if not download_models(python_path):
        print_warning("Failed to download some models, but we'll continue anyway")

    # 8. Set up Docker
    if not args.skip_docker:
        if not setup_docker():
            print_warning("Docker setup failed, but we'll continue anyway")

    # 9. Create startup scripts
    if not create_startup_scripts():
        print_warning("Failed to create startup scripts, but we'll continue anyway")

    print("\n" + "=" * 60)
    print("  SABRINA AI - Installation Complete!  ".center(60))
    print("=" * 60 + "\n")

    print("You can now start Sabrina AI by running:")
    if platform.system() == "Windows":
        print("  run.bat")
    else:
        print("  ./run.sh")

    print("\nOr manually start the components:")
    print("1. Start the voice service:")
    if platform.system() == "Windows":
        print("   venv\\Scripts\\python.exe services/voice/voice_api.py")
    else:
        print("   venv/bin/python services/voice/voice_api.py")

    print("2. Start the main Sabrina AI system:")
    if platform.system() == "Windows":
        print("   venv\\Scripts\\python.exe scripts/start_sabrina.py")
    else:
        print("   venv/bin/python scripts/start_sabrina.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
