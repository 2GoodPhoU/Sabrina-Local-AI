"""
Voice Component Tests for Sabrina AI
===================================
Tests for the Voice API client and service integration.
"""

import os
import sys
import unittest
import tempfile
import json
import time
from unittest.mock import MagicMock, patch
import threading
import requests
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import voice components
from services.voice.voice_api_client import VoiceAPIClient
from utilities.config_manager import ConfigManager
from utilities.error_handler import ErrorHandler
from utilities.event_system import EventBus, EventType, Event, EventPriority

# Import base test class
from tests.test_framework import TestBase

class MockResponse:
    """Mock HTTP response for testing API clients"""
    
    def __init__(self, status_code=200, content=None, text="", json_data=None):
        self.status_code = status_code
        self.content = content if content is not None else b""
        self.text = text
        self._json = json_data
    
    def json(self):
        """Return JSON data"""
        return self._json


class VoiceClientTests(TestBase):
    """Tests for the Voice API client"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Create mock audio file for testing
        self.temp_audio_fd, self.temp_audio_path = tempfile.mkstemp(suffix='.wav')
        os.close(self.temp_audio_fd)
        
        # Write some dummy audio data
        with open(self.temp_audio_path, 'wb') as f:
            f.write(b'\x00' * 1000)  # Simple empty WAV data
    
    def tearDown(self):
        """Clean up test environment"""
        super().tearDown()
        
        # Clean up temp audio file
        if hasattr(self, 'temp_audio_path') and os.path.exists(self.temp_audio_path):
            os.unlink(self.temp_audio_path)
    
    @patch('requests.get')
    def test_test_connection(self, mock_get):
        """Test the connection test functionality"""
        # Mock a successful response
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data={"status": "ok", "service": "Sabrina Voice API"}
        )
        
        # Create client and test connection
        client = VoiceAPIClient()
        result = client.test_connection()
        
        # Verify
        self.assertTrue(result)
        self.assertTrue(client.connected)
        mock_get.assert_called_once_with(
            f"{client.api_url}/status", 
            timeout=client.timeout
        )
        
        # Mock a failed response
        mock_get.reset_mock()
        mock_get.return_value = MockResponse(status_code=404)
        
        # Test connection again
        client = VoiceAPIClient()
        result = client.test_connection()
        
        # Verify
        self.assertFalse(result)
        self.assertFalse(client.connected)
    
    @patch('requests.get')
    @patch.object(VoiceAPIClient, '_save_audio')
    @patch.object(VoiceAPIClient, '_play_audio')
    def test_speak(self, mock_play, mock_save, mock_get):
        """Test the speak functionality"""
        # Mock successful response
        mock_get.return_value = MockResponse(
            status_code=200,
            content=b'\x00' * 1000  # Simple empty WAV data
        )
        
        # Mock save_audio to return a path
        mock_save.return_value = self.temp_audio_path
        
        # Mock play_audio to return True
        mock_play.return_value = True
        
        # Create client and call speak
        client = VoiceAPIClient()
        client.connected = True  # Assume connection is successful
        result = client.speak("Hello, world!")
        
        # Verify
        self.assertEqual(result, self.temp_audio_path)
        mock_get.assert_called_once()
        mock_save.assert_called_once()
        mock_play.assert_called_once_with(self.temp_audio_path)
        
        # Test with empty text
        mock_get.reset_mock()
        mock_save.reset_mock()
        mock_play.reset_mock()
        
        result = client.speak("")
        
        # Verify
        self.assertIsNone(result)
        mock_get.assert_not_called()
        mock_save.assert_not_called()
        mock_play.assert_not_called()
    
    @patch('requests.get')
    def test_retries(self, mock_get):
        """Test retry mechanism"""
        # Mock a series of failures followed by success
        mock_get.side_effect = [
            requests.RequestException("Connection failed"),
            requests.RequestException("Connection failed again"),
            MockResponse(
                status_code=200,
                content=b'\x00' * 1000  # Simple empty WAV data
            )
        ]
        
        # Configure client with test settings
        client = VoiceAPIClient()
        client.connected = True  # Assume connection is successful
        client.retries = 3
        client.retry_delay = 0.1  # Fast retries for testing
        
        # Mock the internal methods we don't want to test
        client._save_audio = MagicMock(return_value=self.temp_audio_path)
        client._play_audio = MagicMock(return_value=True)
        
        # Call speak
        result = client.speak("Hello, world!")
        
        # Verify
        self.assertEqual(result, self.temp_audio_path)
        self.assertEqual(mock_get.call_count, 3)
    
    def test_update_settings(self):
        """Test updating voice settings"""
        client = VoiceAPIClient()
        
        # Test valid settings
        result = client.update_settings({
            "speed": 1.5,
            "pitch": 0.8,
            "emotion": "happy",
            "volume": 0.5
        })
        
        # Verify
        self.assertTrue(result)
        self.assertEqual(client.settings["speed"], 1.5)
        self.assertEqual(client.settings["pitch"], 0.8)
        self.assertEqual(client.settings["emotion"], "happy")
        self.assertEqual(client.settings["volume"], 0.5)
        
        # Test invalid settings
        result = client.update_settings({
            "speed": 3.0,  # Too high
            "pitch": -0.5,  # Too low
            "emotion": "invalid",  # Invalid emotion
            "unknown": "value"  # Unknown setting
        })
        
        # Verify - should update only valid settings
        self.assertTrue(result)
        self.assertEqual(client.settings["speed"], 1.5)  # Unchanged
        self.assertEqual(client.settings["pitch"], 0.8)  # Unchanged
        self.assertEqual(client.settings["emotion"], "happy")  # Unchanged
        self.assertNotIn("unknown", client.settings)  # Not added
    
    def test_convenience_methods(self):
        """Test convenience setter methods"""
        client = VoiceAPIClient()
        
        # Mock update_settings to track calls
        client.update_settings = MagicMock(return_value=True)
        
        # Test each setter
        client.set_speed(1.5)
        client.set_pitch(0.8)
        client.set_emotion("happy")
        client.set_volume(0.5)
        
        # Verify calls
        client.update_settings.assert_any_call({"speed": 1.5})
        client.update_settings.assert_any_call({"pitch": 0.8})
        client.update_settings.assert_any_call({"emotion": "happy"})
        client.update_settings.assert_any_call({"volume": 0.5})


class VoiceIntegrationTests(TestBase):
    """Integration tests for the Voice system"""
    
    @pytest.mark.integration
    def test_voice_api_client_event_integration(self):
        """Test integration between Voice client and event system"""
        # Skip if no voice service is running
        if not self._is_voice_service_running():
            self.skipTest("Voice service not running")
        
        # Create event handler to track voice events
        voice_events = []
        
        def voice_event_handler(event):
            voice_events.append(event)
        
        # Register handler
        handler = self.event_bus.create_event_handler(
            event_types=[EventType.VOICE],
            callback=voice_event_handler
        )
        self.event_bus.register_handler(handler)
        
        # Create client
        client = VoiceAPIClient()
        
        # Post voice event
        voice_text = "This is a test of voice synthesis"
        
        self.event_bus.post_event(Event(
            event_type=EventType.VOICE,
            data={"text": voice_text},
            source="test"
        ))
        
        # Wait for event to be processed
        self.wait_for_events(timeout=2.0)
        
        # Verify event was received
        self.assertGreaterEqual(len(voice_events), 1)
        self.assertEqual(voice_events[0].data.get("text"), voice_text)
    
    def _is_voice_service_running(self):
        """Check if the voice service is running"""
        try:
            response = requests.get("http://localhost:8100/status", timeout=1.0)
            return response.status_code == 200
        except:
            return False


if __name__ == "__main__":
    unittest.main()