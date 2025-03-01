def start_service_with_verification(
    service_name, service_script_path, verification_url, timeout=30, check_interval=1.0
):
    """
    Start a service and verify it's running properly before proceeding

    Args:
        service_name: Name of the service for logging
        service_script_path: Path to the service script to run
        verification_url: URL to check if service is running
        timeout: Maximum time to wait for service (seconds)
        check_interval: Time between status checks (seconds)

    Returns:
        bool: True if service started successfully, False otherwise
    """
    import subprocess
    import time
    import requests
    import sys
    import os
    from pathlib import Path
    import logging

    logger = logging.getLogger(f"{service_name}_starter")

    # Check if service is already running
    logger.info(f"Checking if {service_name} is already running...")
    try:
        response = requests.get(verification_url, timeout=3.0)
        if response.status_code == 200:
            logger.info(f"{service_name} is already running")
            return True
    except requests.RequestException:
        logger.info(f"{service_name} is not running, will start it")

    # Ensure path is a Path object
    if isinstance(service_script_path, str):
        service_script_path = Path(service_script_path)

    if not service_script_path.exists():
        logger.error(f"Service script not found at {service_script_path}")
        return False

    # Start the service
    logger.info(f"Starting {service_name}...")

    try:
        if sys.platform == "win32":
            # Windows
            process = subprocess.Popen(
                ["start", "python", str(service_script_path)], shell=True
            )
            print(process)
        else:
            # Linux/Mac
            # Run in background with nohup
            process = subprocess.Popen(
                ["python", str(service_script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setpgrp,  # Run in a new process group
            )

        # Wait for service to start with a progress indicator
        logger.info(f"Waiting for {service_name} to start (timeout: {timeout}s)...")
        start_time = time.time()

        print(f"Starting {service_name}", end="", flush=True)

        while time.time() - start_time < timeout:
            print(".", end="", flush=True)

            # Check if service is running
            try:
                response = requests.get(verification_url, timeout=2.0)
                if response.status_code == 200:
                    print()  # New line after dots
                    logger.info(f"{service_name} started successfully")
                    return True
            except requests.RequestException:
                # Service not ready yet, continue waiting
                pass

            time.sleep(check_interval)

        print()  # New line after dots
        logger.warning(
            f"{service_name} did not start within the timeout period ({timeout}s)"
        )
        return False

    except Exception as e:
        logger.error(f"Failed to start {service_name}: {str(e)}")
        return False


def start_voice_api(project_dir, timeout=30):
    """
    Start the Voice API service if it's not already running

    Args:
        project_dir: Project root directory
        timeout: Maximum time to wait for service (seconds)

    Returns:
        bool: True if service is running, False otherwise
    """
    from pathlib import Path

    voice_api_path = Path(project_dir) / "services" / "voice" / "voice_api.py"
    verification_url = "http://localhost:8100/status"

    return start_service_with_verification(
        service_name="Voice API",
        service_script_path=voice_api_path,
        verification_url=verification_url,
        timeout=timeout,
    )


def start_all_services(project_dir, timeout=30):
    """
    Start all required services for Sabrina AI

    Args:
        project_dir: Project root directory
        timeout: Maximum time to wait for each service (seconds)

    Returns:
        dict: Status of each service (True if running, False if failed)
    """
    service_status = {}

    # Start Voice API
    service_status["voice_api"] = start_voice_api(project_dir, timeout)

    # Add other services as needed
    # service_status["vision_api"] = start_vision_api(project_dir, timeout)
    # service_status["smart_home"] = start_smart_home_service(project_dir, timeout)

    return service_status
