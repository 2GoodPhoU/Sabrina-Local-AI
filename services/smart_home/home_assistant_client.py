"""
Home Assistant Client for Sabrina AI
===================================
Provides integration with Home Assistant smart home platform for device control
and state monitoring.
"""

import os
import logging
import requests
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("home_assistant_client")


class HomeAssistantClient:
    """Client for interacting with Home Assistant smart home platform"""

    def __init__(
        self, base_url: str = "http://homeassistant.local:8123", token: str = None
    ):
        """
        Initialize the Home Assistant client

        Args:
            base_url: Base URL for Home Assistant instance
            token: Long-lived access token for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.token = token or os.environ.get("HOME_ASSISTANT_TOKEN")
        self.devices = {}
        self.areas = {}
        self.connected = False

        # Setup session with authentication
        self.session = requests.Session()
        if self.token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                }
            )

        logger.info(f"Home Assistant client initialized with base URL: {self.base_url}")

    def test_connection(self) -> bool:
        """
        Test connection to Home Assistant

        Returns:
            bool: True if connected, False otherwise
        """
        if not self.token:
            logger.warning("No Home Assistant token provided")
            return False

        try:
            response = self.session.get(f"{self.base_url}/api/", timeout=5)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Connected to Home Assistant {data.get('version', '')}")
                self.connected = True
                return True
            else:
                logger.warning(
                    f"Failed to connect to Home Assistant: {response.status_code}"
                )
                return False

        except requests.RequestException as e:
            logger.error(f"Error connecting to Home Assistant: {str(e)}")
            return False

    def discover_devices(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover available devices from Home Assistant

        Returns:
            Dict of device IDs to device information
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Home Assistant")
            return {}

        try:
            # Get states
            response = self.session.get(f"{self.base_url}/api/states")

            if response.status_code == 200:
                states = response.json()

                # Process states into devices
                devices = {}

                for state in states:
                    entity_id = state.get("entity_id", "")

                    # Skip non-device entities
                    if not entity_id or not self._is_device_entity(entity_id):
                        continue

                    # Extract device information
                    domain, object_id = entity_id.split(".", 1)
                    friendly_name = state.get("attributes", {}).get(
                        "friendly_name", object_id
                    )

                    # Create device entry
                    devices[entity_id] = {
                        "entity_id": entity_id,
                        "name": friendly_name,
                        "type": domain,
                        "state": state.get("state", "unknown"),
                        "attributes": state.get("attributes", {}),
                        "last_updated": state.get("last_updated", ""),
                    }

                self.devices = devices
                logger.info(f"Discovered {len(devices)} devices from Home Assistant")
                return devices
            else:
                logger.warning(
                    f"Failed to get states from Home Assistant: {response.status_code}"
                )
                return {}

        except requests.RequestException as e:
            logger.error(f"Error discovering devices: {str(e)}")
            return {}

    def _is_device_entity(self, entity_id: str) -> bool:
        """
        Check if an entity ID represents a device

        Args:
            entity_id: Home Assistant entity ID

        Returns:
            bool: True if entity is a device, False otherwise
        """
        # Skip groups, scenes, automations, etc.
        non_device_domains = [
            "automation",
            "scene",
            "group",
            "script",
            "binary_sensor",
            "device_tracker",
            "zone",
            "input_boolean",
            "persistent_notification",
        ]

        if "." not in entity_id:
            return False

        domain = entity_id.split(".", 1)[0]
        return domain not in non_device_domains

    def get_device_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current state of a device

        Args:
            entity_id: Home Assistant entity ID

        Returns:
            Dict with device state or None if not found
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Home Assistant")
            return None

        try:
            response = self.session.get(f"{self.base_url}/api/states/{entity_id}")

            if response.status_code == 200:
                state = response.json()

                # Update devices cache
                if entity_id in self.devices:
                    self.devices[entity_id]["state"] = state.get("state", "unknown")
                    self.devices[entity_id]["attributes"] = state.get("attributes", {})
                    self.devices[entity_id]["last_updated"] = state.get(
                        "last_updated", ""
                    )

                # Return processed state
                return {
                    "entity_id": entity_id,
                    "state": state.get("state", "unknown"),
                    "attributes": state.get("attributes", {}),
                    "last_updated": state.get("last_updated", ""),
                }
            elif response.status_code == 404:
                logger.warning(f"Device not found: {entity_id}")
                return None
            else:
                logger.warning(f"Failed to get device state: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Error getting device state: {str(e)}")
            return None

    def set_device_state(self, entity_id: str, state: str) -> bool:
        """
        Set the state of a device

        Args:
            entity_id: Home Assistant entity ID
            state: State to set (e.g., "on", "off")

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Home Assistant")
            return False

        try:
            # Get domain for service determination
            if "." not in entity_id:
                logger.warning(f"Invalid entity ID: {entity_id}")
                return False

            domain, object_id = entity_id.split(".", 1)

            # Determine service
            service = state

            # Handle specific domains
            if domain in ["light", "switch", "automation"]:
                if state not in ["on", "off"]:
                    logger.warning(f"Invalid state for {domain}: {state}")
                    return False
            elif domain == "cover":
                if state not in ["open", "close", "stop"]:
                    logger.warning(f"Invalid state for cover: {state}")
                    return False
            elif domain == "climate":
                if state not in ["heat", "cool", "off", "auto"]:
                    if state not in ["on", "off"]:  # Fallback to on/off
                        logger.warning(f"Invalid state for climate: {state}")
                        return False
            elif domain == "media_player":
                if state not in ["play", "pause", "stop", "on", "off"]:
                    logger.warning(f"Invalid state for media_player: {state}")
                    return False
                # Map play/pause/stop to proper service
                if state == "play":
                    service = "media_play"
                elif state == "pause":
                    service = "media_pause"
                elif state == "stop":
                    service = "media_stop"

            # Call service
            response = self.session.post(
                f"{self.base_url}/api/services/{domain}/{service}",
                json={"entity_id": entity_id},
            )

            if response.status_code in [200, 201]:
                logger.info(f"Set {entity_id} to {state}")

                # Update device state in cache
                if entity_id in self.devices:
                    self.devices[entity_id]["state"] = state

                return True
            else:
                logger.warning(f"Failed to set device state: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Error setting device state: {str(e)}")
            return False

    def set_temperature(self, entity_id: str, temperature: float) -> bool:
        """
        Set temperature for a climate device

        Args:
            entity_id: Home Assistant entity ID (must be a climate device)
            temperature: Temperature to set

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Home Assistant")
            return False

        try:
            if "." not in entity_id:
                logger.warning(f"Invalid entity ID: {entity_id}")
                return False

            domain, object_id = entity_id.split(".", 1)

            if domain != "climate":
                logger.warning(f"Entity is not a climate device: {entity_id}")
                return False

            # Call service
            response = self.session.post(
                f"{self.base_url}/api/services/climate/set_temperature",
                json={"entity_id": entity_id, "temperature": float(temperature)},
            )

            if response.status_code in [200, 201]:
                logger.info(f"Set {entity_id} temperature to {temperature}")

                # Update device state in cache
                if entity_id in self.devices:
                    self.devices[entity_id]["attributes"]["temperature"] = temperature

                return True
            else:
                logger.warning(f"Failed to set temperature: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Error setting temperature: {str(e)}")
            return False

    def set_lock_state(self, entity_id: str, command: str) -> bool:
        """
        Set lock state (lock/unlock)

        Args:
            entity_id: Home Assistant entity ID (must be a lock)
            command: Either "lock" or "unlock"

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Home Assistant")
            return False

        try:
            if "." not in entity_id:
                logger.warning(f"Invalid entity ID: {entity_id}")
                return False

            domain, object_id = entity_id.split(".", 1)

            if domain != "lock":
                logger.warning(f"Entity is not a lock: {entity_id}")
                return False

            if command not in ["lock", "unlock"]:
                logger.warning(f"Invalid lock command: {command}")
                return False

            # Call service
            response = self.session.post(
                f"{self.base_url}/api/services/lock/{command}",
                json={"entity_id": entity_id},
            )

            if response.status_code in [200, 201]:
                logger.info(f"{command.capitalize()}ed {entity_id}")

                # Update device state in cache
                if entity_id in self.devices:
                    self.devices[entity_id]["state"] = (
                        "locked" if command == "lock" else "unlocked"
                    )

                return True
            else:
                logger.warning(
                    f"Failed to {command} {entity_id}: {response.status_code}"
                )
                return False

        except requests.RequestException as e:
            logger.error(f"Error setting lock state: {str(e)}")
            return False

    def execute_routine(self, routine_name: str) -> bool:
        """
        Execute a Home Assistant script or scene

        Args:
            routine_name: Name of script or scene to execute

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Home Assistant")
            return False

        try:
            # Try as script first
            script_entity = f"script.{routine_name}"
            script_response = self.session.post(
                f"{self.base_url}/api/services/script/turn_on",
                json={"entity_id": script_entity},
            )

            if script_response.status_code in [200, 201]:
                logger.info(f"Executed script: {routine_name}")
                return True

            # Try as scene
            scene_entity = f"scene.{routine_name}"
            scene_response = self.session.post(
                f"{self.base_url}/api/services/scene/turn_on",
                json={"entity_id": scene_entity},
            )

            if scene_response.status_code in [200, 201]:
                logger.info(f"Activated scene: {routine_name}")
                return True

            logger.warning(f"Routine not found: {routine_name}")
            return False

        except requests.RequestException as e:
            logger.error(f"Error executing routine: {str(e)}")
            return False

    def send_command(
        self, entity_id: str, command: str, parameters: Dict[str, Any] = None
    ) -> bool:
        """
        Send a generic command to a device

        Args:
            entity_id: Home Assistant entity ID
            command: Command to send
            parameters: Additional parameters

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Home Assistant")
            return False

        try:
            if "." not in entity_id:
                logger.warning(f"Invalid entity ID: {entity_id}")
                return False

            domain, object_id = entity_id.split(".", 1)

            # Prepare service call payload
            payload = {"entity_id": entity_id}
            if parameters:
                payload.update(parameters)

            # Call service
            response = self.session.post(
                f"{self.base_url}/api/services/{domain}/{command}", json=payload
            )

            if response.status_code in [200, 201]:
                logger.info(f"Sent command {command} to {entity_id}")
                return True
            else:
                logger.warning(f"Failed to send command: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Error sending command: {str(e)}")
            return False

    def get_areas(self) -> Dict[str, Dict[str, Any]]:
        """
        Get areas defined in Home Assistant

        Returns:
            Dict of area IDs to area information
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Home Assistant")
            return {}

        try:
            response = self.session.get(f"{self.base_url}/api/areas")

            if response.status_code == 200:
                areas_data = response.json()

                # Process areas
                areas = {}

                for area in areas_data:
                    area_id = area.get("area_id", "")
                    if area_id:
                        areas[area_id] = {
                            "area_id": area_id,
                            "name": area.get("name", ""),
                            "picture": area.get("picture", None),
                        }

                self.areas = areas
                logger.info(f"Retrieved {len(areas)} areas from Home Assistant")
                return areas
            else:
                logger.warning(f"Failed to get areas: {response.status_code}")
                return {}

        except requests.RequestException as e:
            logger.error(f"Error getting areas: {str(e)}")
            return {}

    def get_devices_by_area(self, area_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get devices in a specific area

        Args:
            area_name: Name of the area

        Returns:
            Dict of device IDs to device information for devices in the area
        """
        # Ensure we have devices
        if not self.devices:
            self.discover_devices()

        # Get areas if we don't have them
        if not self.areas:
            self.get_areas()

        # Find area ID by name
        area_id = None
        for id, area in self.areas.items():
            if area["name"].lower() == area_name.lower():
                area_id = id
                break

        if not area_id:
            logger.warning(f"Area not found: {area_name}")
            return {}

        # Find devices in area
        area_devices = {}
        for entity_id, device in self.devices.items():
            device_area = device.get("attributes", {}).get("area_id")
            if device_area == area_id:
                area_devices[entity_id] = device

        return area_devices
