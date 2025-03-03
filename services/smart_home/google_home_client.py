"""
Google Home Client for Sabrina AI
===============================
Provides integration with Google Home for smart device control
and status monitoring with OAuth2 authentication.
"""

import os
import logging
import json
import time
import requests
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("google_home_client")


class GoogleHomeClient:
    """Client for interacting with Google Home smart devices"""

    def __init__(self, credentials_path: str = None, token_path: str = None):
        """
        Initialize the Google Home client

        Args:
            credentials_path: Path to Google Home credentials JSON file
            token_path: Path to store/retrieve OAuth tokens
        """
        self.credentials_path = credentials_path or os.environ.get(
            "GOOGLE_HOME_CREDENTIALS"
        )
        self.token_path = token_path or "data/google_home_token.json"
        self.devices = {}
        self.rooms = {}
        self.connected = False
        self.api_endpoint = "https://homegraph.googleapis.com/v1"
        self.session = requests.Session()
        self.token = None

        # Try to load credentials
        self._load_credentials()

        logger.info("Google Home client initialized")

    def _load_credentials(self):
        """Load Google Home API credentials"""
        if not self.credentials_path:
            logger.warning("No Google Home credentials path provided")
            return

        try:
            if not os.path.exists(self.credentials_path):
                logger.warning(f"Credentials file not found: {self.credentials_path}")
                return

            with open(self.credentials_path, "r") as f:
                self.credentials = json.load(f)

            # Try to load existing token
            if os.path.exists(self.token_path):
                with open(self.token_path, "r") as f:
                    self.token = json.load(f)

                # Check if token is expired
                if self.token and "expiry" in self.token:
                    expires_at = self.token["expiry"]
                    if expires_at < time.time():
                        logger.info("Token expired, refreshing")
                        self._refresh_token()
                    else:
                        logger.info("Loaded valid token")

            logger.info("Loaded Google Home credentials")

        except Exception as e:
            logger.error(f"Error loading Google Home credentials: {str(e)}")
            self.credentials = None

    def _refresh_token(self) -> bool:
        """
        Refresh OAuth2 token

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.credentials:
            logger.warning("No credentials available to refresh token")
            return False

        if not self.token or "refresh_token" not in self.token:
            logger.warning("No refresh token available")
            return False

        try:
            refresh_token = self.token["refresh_token"]
            client_id = self.credentials["installed"]["client_id"]
            client_secret = self.credentials["installed"]["client_secret"]

            # Prepare token refresh request
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }

            response = requests.post(token_url, data=data)

            if response.status_code == 200:
                token_data = response.json()

                # Update token
                self.token.update(
                    {
                        "access_token": token_data["access_token"],
                        "token_type": token_data["token_type"],
                        "expiry": int(time.time()) + token_data["expires_in"],
                    }
                )

                # Save token
                self._save_token()

                # Update session headers
                self.session.headers.update(
                    {
                        "Authorization": f"Bearer {self.token['access_token']}",
                        "Content-Type": "application/json",
                    }
                )

                logger.info("Successfully refreshed token")
                return True
            else:
                logger.warning(f"Failed to refresh token: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return False

    def _save_token(self):
        """Save OAuth token to file"""
        if not self.token:
            return

        try:
            # Ensure directory exists
            token_dir = os.path.dirname(self.token_path)
            if token_dir:
                os.makedirs(token_dir, exist_ok=True)

            with open(self.token_path, "w") as f:
                json.dump(self.token, f)

            logger.debug("Saved token to file")

        except Exception as e:
            logger.error(f"Error saving token: {str(e)}")

    def authenticate(self) -> bool:
        """
        Perform OAuth2 authentication flow

        Returns:
            bool: True if authenticated, False otherwise
        """
        if not self.credentials:
            logger.warning("No credentials available for authentication")
            return False

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            # Define scopes
            scopes = [
                "https://www.googleapis.com/auth/homegraph",
                "https://www.googleapis.com/auth/home.devices.control",
            ]

            if self.token:
                # Create credentials from existing token
                creds = Credentials(
                    token=self.token.get("access_token"),
                    refresh_token=self.token.get("refresh_token"),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self.credentials["installed"]["client_id"],
                    client_secret=self.credentials["installed"]["client_secret"],
                    scopes=scopes,
                )

                # Refresh if needed
                if creds.expired:
                    creds.refresh(Request())
            else:
                # Start OAuth flow
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, scopes
                )
                creds = flow.run_local_server(port=0)

            # Save token
            self.token = {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_type": "Bearer",
                "expiry": int(time.time()) + 3600,  # Approximate expiry
            }
            self._save_token()

            # Update session headers
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.token['access_token']}",
                    "Content-Type": "application/json",
                }
            )

            logger.info("Successfully authenticated with Google Home")
            self.connected = True
            return True

        except Exception as e:
            logger.error(f"Error during authentication: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """
        Test connection to Google Home API

        Returns:
            bool: True if connected, False otherwise
        """
        if not self.token:
            if not self.authenticate():
                return False

        try:
            # Try to get devices
            url = f"{self.api_endpoint}/devices"
            response = self.session.get(url)

            if response.status_code == 200:
                logger.info("Successfully connected to Google Home API")
                self.connected = True
                return True
            elif response.status_code == 401:
                # Token expired, refresh and retry
                logger.info("Token expired, attempting to refresh")
                if self._refresh_token():
                    # Retry request
                    response = self.session.get(url)
                    if response.status_code == 200:
                        logger.info("Successfully connected to Google Home API")
                        self.connected = True
                        return True
                    else:
                        logger.warning(
                            f"Failed to connect after token refresh: {response.status_code}"
                        )
                        return False
                else:
                    logger.warning("Failed to refresh token")
                    return False
            else:
                logger.warning(
                    f"Failed to connect to Google Home API: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error testing connection: {str(e)}")
            return False

    def discover_devices(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover available Google Home devices

        Returns:
            Dict of device IDs to device information
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Google Home API")
            return {}

        try:
            # Get devices
            url = f"{self.api_endpoint}/devices"
            response = self.session.get(url)

            if response.status_code == 200:
                data = response.json()
                devices = {}

                for device in data.get("devices", []):
                    device_id = device.get("id")
                    if device_id:
                        devices[device_id] = {
                            "id": device_id,
                            "name": device.get("name", {}).get("name", "Unknown"),
                            "type": device.get("type", "unknown"),
                            "traits": device.get("traits", []),
                            "state": self._extract_device_state(device),
                            "room": device.get("room", {}).get("name", ""),
                            "structure": device.get("structure", {}),
                            "attributes": device.get("attributes", {}),
                        }

                self.devices = devices
                logger.info(f"Discovered {len(devices)} devices from Google Home")
                return devices
            else:
                logger.warning(f"Failed to discover devices: {response.status_code}")
                return {}

        except Exception as e:
            logger.error(f"Error discovering devices: {str(e)}")
            return {}

    def _extract_device_state(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract device state from device data

        Args:
            device_data: Device data from API

        Returns:
            Dict with device state
        """
        state = {}

        # Extract state from traits
        if "traits" in device_data:
            for trait in device_data["traits"]:
                if trait.get("state"):
                    state.update(trait["state"])

        # Check for common states
        if "action.devices.traits.OnOff" in device_data.get("traits", []):
            state["on"] = state.get("on", False)

        if "action.devices.traits.Brightness" in device_data.get("traits", []):
            state["brightness"] = state.get("brightness", 0)

        if "action.devices.traits.ColorSetting" in device_data.get("traits", []):
            if "color" in state:
                # Nothing to do, color already in state
                pass
            elif "spectrumRgb" in device_data.get("attributes", {}).get(
                "colorModel", []
            ):
                state["color"] = {"spectrumRgb": 16777215}  # Default white

        if "action.devices.traits.TemperatureSetting" in device_data.get("traits", []):
            state["thermostatMode"] = state.get("thermostatMode", "off")
            state["thermostatTemperatureSetpoint"] = state.get(
                "thermostatTemperatureSetpoint", 20
            )

        return state

    def get_device_state(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current state of a device

        Args:
            device_id: Device ID

        Returns:
            Dict with device state or None if not found
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Google Home API")
            return None

        try:
            # Get device state
            url = f"{self.api_endpoint}/devices/{device_id}"
            response = self.session.get(url)

            if response.status_code == 200:
                device_data = response.json()

                # Extract device state
                state = self._extract_device_state(device_data)

                # Update device in cache
                if device_id in self.devices:
                    self.devices[device_id]["state"] = state

                return state
            elif response.status_code == 404:
                logger.warning(f"Device not found: {device_id}")
                return None
            else:
                logger.warning(f"Failed to get device state: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting device state: {str(e)}")
            return None

    def set_device_state(self, device_id: str, state: str) -> bool:
        """
        Set the state of a device

        Args:
            device_id: Device ID
            state: State to set (typically "on" or "off")

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Google Home API")
            return False

        try:
            # Validate state
            if state not in ["on", "off"]:
                logger.warning(f"Invalid state: {state}")
                return False

            # Map state to bool
            on_state = state == "on"

            # Prepare request payload
            commands = {
                "commands": [
                    {
                        "devices": [{"id": device_id}],
                        "execution": [
                            {
                                "command": "action.devices.commands.OnOff",
                                "params": {"on": on_state},
                            }
                        ],
                    }
                ]
            }

            # Execute command
            url = f"{self.api_endpoint}/devices:execute"
            response = self.session.post(url, json=commands)

            if response.status_code in [200, 201]:
                logger.info(f"Set {device_id} to {state}")

                # Update device state in cache
                if device_id in self.devices:
                    if "state" not in self.devices[device_id]:
                        self.devices[device_id]["state"] = {}
                    self.devices[device_id]["state"]["on"] = on_state

                return True
            else:
                logger.warning(
                    f"Failed to set device state: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error setting device state: {str(e)}")
            return False

    def set_temperature(self, device_id: str, temperature: float) -> bool:
        """
        Set temperature for a thermostat device

        Args:
            device_id: Device ID
            temperature: Temperature to set

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Google Home API")
            return False

        try:
            # Check device type if available
            if device_id in self.devices:
                device_type = self.devices[device_id].get("type", "")
                if not device_type.endswith("Thermostat"):
                    logger.warning(f"Device is not a thermostat: {device_id}")
                    return False

            # Prepare request payload
            commands = {
                "commands": [
                    {
                        "devices": [{"id": device_id}],
                        "execution": [
                            {
                                "command": "action.devices.commands.ThermostatTemperatureSetpoint",
                                "params": {
                                    "thermostatTemperatureSetpoint": float(temperature)
                                },
                            }
                        ],
                    }
                ]
            }

            # Execute command
            url = f"{self.api_endpoint}/devices:execute"
            response = self.session.post(url, json=commands)

            if response.status_code in [200, 201]:
                logger.info(f"Set {device_id} temperature to {temperature}")

                # Update device state in cache
                if device_id in self.devices:
                    if "state" not in self.devices[device_id]:
                        self.devices[device_id]["state"] = {}
                    self.devices[device_id]["state"][
                        "thermostatTemperatureSetpoint"
                    ] = float(temperature)

                return True
            else:
                logger.warning(
                    f"Failed to set temperature: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error setting temperature: {str(e)}")
            return False

    def set_brightness(self, device_id: str, brightness: int) -> bool:
        """
        Set brightness for a light device

        Args:
            device_id: Device ID
            brightness: Brightness level (0-100)

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Google Home API")
            return False

        try:
            # Ensure brightness is in valid range
            brightness = max(0, min(100, int(brightness)))

            # Prepare request payload
            commands = {
                "commands": [
                    {
                        "devices": [{"id": device_id}],
                        "execution": [
                            {
                                "command": "action.devices.commands.BrightnessAbsolute",
                                "params": {"brightness": brightness},
                            }
                        ],
                    }
                ]
            }

            # Execute command
            url = f"{self.api_endpoint}/devices:execute"
            response = self.session.post(url, json=commands)

            if response.status_code in [200, 201]:
                logger.info(f"Set {device_id} brightness to {brightness}%")

                # Update device state in cache
                if device_id in self.devices:
                    if "state" not in self.devices[device_id]:
                        self.devices[device_id]["state"] = {}
                    self.devices[device_id]["state"]["brightness"] = brightness

                return True
            else:
                logger.warning(
                    f"Failed to set brightness: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error setting brightness: {str(e)}")
            return False

    def set_color(self, device_id: str, color: int) -> bool:
        """
        Set color for a light device (RGB value)

        Args:
            device_id: Device ID
            color: RGB color as integer (0xRRGGBB)

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Google Home API")
            return False

        try:
            # Prepare request payload
            commands = {
                "commands": [
                    {
                        "devices": [{"id": device_id}],
                        "execution": [
                            {
                                "command": "action.devices.commands.ColorAbsolute",
                                "params": {"color": {"spectrumRGB": color}},
                            }
                        ],
                    }
                ]
            }

            # Execute command
            url = f"{self.api_endpoint}/devices:execute"
            response = self.session.post(url, json=commands)

            if response.status_code in [200, 201]:
                logger.info(f"Set {device_id} color to {color}")

                # Update device state in cache
                if device_id in self.devices:
                    if "state" not in self.devices[device_id]:
                        self.devices[device_id]["state"] = {}
                    if "color" not in self.devices[device_id]["state"]:
                        self.devices[device_id]["state"]["color"] = {}
                    self.devices[device_id]["state"]["color"]["spectrumRgb"] = color

                return True
            else:
                logger.warning(
                    f"Failed to set color: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error setting color: {str(e)}")
            return False

    def execute_routine(self, routine_name: str) -> bool:
        """
        Execute a Google Home routine

        Args:
            routine_name: Name of routine to execute

        Returns:
            bool: True if successful, False otherwise
        """
        logger.warning(
            "Google Home API does not directly support executing named routines"
        )
        logger.info(
            "Consider using IFTTT or similar service to trigger Google Home routines"
        )
        return False

    def send_command(
        self, device_id: str, command: str, parameters: Dict[str, Any] = None
    ) -> bool:
        """
        Send a generic command to a device

        Args:
            device_id: Device ID
            command: Command name (e.g., "action.devices.commands.OnOff")
            parameters: Command parameters

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Google Home API")
            return False

        try:
            # Prepare request payload
            commands = {
                "commands": [
                    {
                        "devices": [{"id": device_id}],
                        "execution": [{"command": command, "params": parameters or {}}],
                    }
                ]
            }

            # Execute command
            url = f"{self.api_endpoint}/devices:execute"
            response = self.session.post(url, json=commands)

            if response.status_code in [200, 201]:
                logger.info(f"Sent command {command} to {device_id}")
                return True
            else:
                logger.warning(
                    f"Failed to send command: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error sending command: {str(e)}")
            return False

    def get_rooms(self) -> Dict[str, Dict[str, Any]]:
        """
        Get rooms defined in Google Home

        Returns:
            Dict of room IDs to room information
        """
        if not self.connected and not self.test_connection():
            logger.warning("Not connected to Google Home API")
            return {}

        try:
            # Get structures (includes rooms)
            url = f"{self.api_endpoint}/structures"
            response = self.session.get(url)

            if response.status_code == 200:
                data = response.json()
                rooms = {}

                for structure in data.get("structures", []):
                    for room in structure.get("rooms", []):
                        room_id = room.get("id")
                        if room_id:
                            rooms[room_id] = {
                                "id": room_id,
                                "name": room.get("name", "Unknown Room"),
                                "structure_id": structure.get("id"),
                                "structure_name": structure.get(
                                    "name", "Unknown Structure"
                                ),
                            }

                self.rooms = rooms
                logger.info(f"Retrieved {len(rooms)} rooms from Google Home")
                return rooms
            else:
                logger.warning(f"Failed to get rooms: {response.status_code}")
                return {}

        except Exception as e:
            logger.error(f"Error getting rooms: {str(e)}")
            return {}

    def get_devices_by_room(self, room_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get devices in a specific room

        Args:
            room_name: Name of the room

        Returns:
            Dict of device IDs to device information for devices in the room
        """
        # Ensure we have devices
        if not self.devices:
            self.discover_devices()

        # Get rooms if we don't have them
        if not self.rooms:
            self.get_rooms()

        # Find room ID by name
        room_id = None
        for id, room in self.rooms.items():
            if room["name"].lower() == room_name.lower():
                room_id = id
                break

        if not room_id:
            logger.warning(f"Room not found: {room_name}")
            return {}

        # Find devices in room
        room_devices = {}
        for device_id, device in self.devices.items():
            device_room_id = device.get("room", {}).get("id")
            if device_room_id == room_id:
                room_devices[device_id] = device

        return room_devices
