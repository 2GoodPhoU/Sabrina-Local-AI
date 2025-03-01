"""
Comprehensive Test Suite for Sabrina AI Voice Module
"""

import os
import pytest
import tempfile

# Import modules to test
from services.voice.voice_settings import VoiceSettingsManager
from services.voice.tts_engine import TTSEngine
from services.voice.voice_api_client import VoiceAPIClient

# Use httpx for async testing of FastAPI
import httpx


# Setup test configuration
class TestVoiceModule:
    """Comprehensive test class for Voice Module components"""

    @pytest.fixture
    def voice_settings_manager(self):
        """Fixture for VoiceSettingsManager"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "voice_settings.json")
            return VoiceSettingsManager(config_path)

    @pytest.fixture
    def tts_engine(self):
        """Fixture for TTS Engine with temporary directories"""
        with tempfile.TemporaryDirectory() as models_dir, tempfile.TemporaryDirectory() as cache_dir:
            return TTSEngine(models_dir, cache_dir)

    @pytest.fixture
    def voice_api_client(self):
        """Fixture for Voice API Client"""
        return VoiceAPIClient()

    def test_voice_settings_default(self, voice_settings_manager):
        """Test default voice settings"""
        settings = voice_settings_manager.get_settings()

        # Validate default settings
        assert settings.voice == "en_US-amy-medium"
        assert 0.0 <= settings.volume <= 1.0
        assert 0.5 <= settings.speed <= 2.0
        assert settings.emotion == "neutral"

    def test_voice_settings_update(self, voice_settings_manager):
        """Test updating voice settings"""
        # Update specific settings
        updated = voice_settings_manager.update_settings(
            {"volume": 0.7, "speed": 1.2, "emotion": "happy"}
        )

        assert updated.volume == 0.7
        assert updated.speed == 1.2
        assert updated.emotion == "happy"

    def test_tts_engine_initialization(self, tts_engine):
        """Test TTS Engine initialization"""
        assert tts_engine.current_model is not None
        assert tts_engine.synthesizer is not None

    def test_speech_generation(self, tts_engine):
        """Test generating speech from text"""
        test_text = "Hello, this is a test of Sabrina AI's voice module."

        # Generate speech
        audio_path = tts_engine.generate_speech(test_text)

        # Validate output
        assert os.path.exists(audio_path)
        assert audio_path.endswith(".wav")

        # Check file size (should not be empty)
        assert os.path.getsize(audio_path) > 0

    def test_voice_api_client_connection(self, voice_api_client):
        """Test Voice API Client connection"""
        # Test connection status
        assert voice_api_client.connected is True

    def test_voice_api_speak(self, voice_api_client):
        """Test speaking through API client"""
        test_text = "Testing Sabrina AI voice API client."

        # Speak with default settings
        audio_path = voice_api_client.speak(test_text)

        # Validate output
        assert os.path.exists(audio_path)
        assert audio_path.endswith(".wav")
        assert os.path.getsize(audio_path) > 0

    def test_voice_api_settings(self, voice_api_client):
        """Test retrieving and updating voice settings via API"""
        # Get current settings
        initial_settings = voice_api_client.get_settings()

        # Validate settings structure
        assert "voice" in initial_settings
        assert "volume" in initial_settings
        assert "speed" in initial_settings

        # Update settings
        updated_settings = voice_api_client.update_settings(
            volume=0.6, speed=1.1, emotion="excited"
        )

        # Validate updates
        assert updated_settings["volume"] == 0.6
        assert updated_settings["speed"] == 1.1
        assert updated_settings["emotion"] == "excited"

    def test_voice_cache_management(self, tts_engine):
        """Test speech generation cache functionality"""
        # Generate the same text multiple times
        test_text = "Testing speech caching mechanism."

        # First generation
        first_audio_path = tts_engine.generate_speech(test_text)
        first_modified_time = os.path.getmtime(first_audio_path)

        # Second generation (should use cache)
        second_audio_path = tts_engine.generate_speech(test_text)
        second_modified_time = os.path.getmtime(second_audio_path)

        # Paths should be the same due to caching
        assert first_audio_path == second_audio_path
        assert first_modified_time == second_modified_time

    def test_list_available_voices(self, tts_engine):
        """Test listing available TTS voices"""
        voices = tts_engine.list_available_voices()

        # Validate voice list
        assert isinstance(voices, list)
        assert len(voices) > 0

        # Ensure current model is in the list
        assert tts_engine.current_model in voices

    def test_emotion_settings(self, voice_api_client):
        """Test emotion settings"""
        valid_emotions = ["neutral", "happy", "sad", "angry", "excited"]

        for emotion in valid_emotions:
            # Update emotion
            updated_settings = voice_api_client.update_settings(emotion=emotion)

            # Validate update
            assert updated_settings["emotion"] == emotion

        # Test invalid emotion (should raise an error)
        with pytest.raises(Exception):
            voice_api_client.update_settings(emotion="invalid_emotion")


# Async tests for API endpoints
@pytest.mark.asyncio
class TestVoiceAPIEndpoints:
    """Async tests for Voice API endpoints"""

    @pytest.fixture
    async def async_client(self):
        """Create an async test client"""
        async with httpx.AsyncClient() as client:
            yield client

    async def test_api_status(self, async_client):
        """Test API status endpoint"""
        response = await async_client.get("http://localhost:8100/status")
        assert response.status_code == 200

        status_data = response.json()
        assert status_data["status"] == "healthy"
        assert "available_voices" in status_data

    async def test_api_speak_endpoint(self, async_client):
        """Test speak endpoint"""
        speak_payload = {
            "text": "Hello from Sabrina AI async test",
            "voice": "en_US-amy-medium",
            "volume": 0.7,
        }

        response = await async_client.post(
            "http://localhost:8100/speak", json=speak_payload
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"

    async def test_api_settings_endpoint(self, async_client):
        """Test settings endpoints"""
        # Get current settings
        get_response = await async_client.get("http://localhost:8100/settings")
        assert get_response.status_code == 200

        # Update settings
        update_payload = {"volume": 0.6, "speed": 1.1}
        update_response = await async_client.post(
            "http://localhost:8100/settings", json=update_payload
        )

        assert update_response.status_code == 200
        update_data = update_response.json()
        assert update_data["volume"] == 0.6
        assert update_data["speed"] == 1.1


# Additional configuration for running tests
def pytest_configure(config):
    """Custom pytest configuration"""
    config.addinivalue_line(
        "markers", "integration: marks tests that require external services"
    )
