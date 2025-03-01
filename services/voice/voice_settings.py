"""
Voice Settings Management for Sabrina AI Voice Module
Manages voice configuration, persistence, and dynamic updates
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator

# Configure logging
logger = logging.getLogger(__name__)


class VoiceSettings(BaseModel):
    """Structured voice configuration model"""

    # Voice Selection
    voice: str = Field(
        default="en_US-amy-medium", description="Selected TTS voice model"
    )

    # Audio Parameters
    volume: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Volume level (0.0-1.0)"
    )
    speed: float = Field(
        default=1.0, ge=0.5, le=2.0, description="Speech speed (0.5-2.0)"
    )
    pitch: float = Field(
        default=1.0, ge=0.5, le=2.0, description="Voice pitch (0.5-2.0)"
    )

    # Emotion & Style
    emotion: str = Field(default="neutral", description="Speech emotion/style")
    language: str = Field(default="en-US", description="Primary language")

    # Advanced Settings
    cache_enabled: bool = Field(default=True, description="Enable speech caching")
    max_cache_size: int = Field(
        default=100, description="Maximum number of cached audio files"
    )

    @validator("emotion")
    def validate_emotion(cls, v):
        """Validate emotion is within allowed set"""
        valid_emotions = ["neutral", "happy", "sad", "angry", "excited"]
        if v.lower() not in valid_emotions:
            raise ValueError(f"Invalid emotion. Must be one of {valid_emotions}")
        return v.lower()


class VoiceSettingsManager:
    """Manages voice settings persistence and retrieval"""

    def __init__(self, config_path: str = "config/voice_settings.json"):
        """
        Initialize voice settings manager

        Args:
            config_path: Path to save/load voice configuration
        """
        self.config_path = config_path
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Default settings if no config exists
        self.settings = self._load_or_create_config()

    def _load_or_create_config(self) -> VoiceSettings:
        """
        Load existing configuration or create default

        Returns:
            VoiceSettings instance
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config_data = json.load(f)
                    return VoiceSettings(**config_data)
            else:
                # Create default configuration
                default_settings = VoiceSettings()
                self.save_config(default_settings)
                return default_settings
        except Exception as e:
            logger.error(f"Error loading voice settings: {e}")
            return VoiceSettings()

    def save_config(self, settings: Optional[VoiceSettings] = None):
        """
        Save configuration to file

        Args:
            settings: Optional settings to save, uses current if None
        """
        try:
            settings = settings or self.settings
            with open(self.config_path, "w") as f:
                json.dump(settings.dict(), f, indent=4)
            logger.info(f"Voice settings saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving voice settings: {e}")

    def update_settings(self, updates: Dict[str, Any]) -> VoiceSettings:
        """
        Update specific voice settings

        Args:
            updates: Dictionary of settings to update

        Returns:
            Updated VoiceSettings instance
        """
        try:
            current_dict = self.settings.dict()
            current_dict.update(updates)
            self.settings = VoiceSettings(**current_dict)
            self.save_config()
            return self.settings
        except Exception as e:
            logger.error(f"Error updating voice settings: {e}")
            return self.settings

    def get_settings(self) -> VoiceSettings:
        """
        Retrieve current voice settings

        Returns:
            Current VoiceSettings
        """
        return self.settings

    def reset_to_default(self) -> VoiceSettings:
        """
        Reset settings to default configuration

        Returns:
            Default VoiceSettings
        """
        self.settings = VoiceSettings()
        self.save_config()
        return self.settings


# Global settings manager for easy import
voice_settings_manager = VoiceSettingsManager()
