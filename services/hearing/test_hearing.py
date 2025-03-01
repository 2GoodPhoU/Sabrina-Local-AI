import time
import logging
from hearing import Hearing

# Configure logging for test script
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_hearing")

def test_hearing_module():
    """
    Test the functionality of the Hearing module.
    """
    logger.info("Initializing Hearing module...")
    hearing = Hearing(wake_word="hey sabrina", model_path="models/vosk-model")

    if not hearing.vosk_model:
        logger.error("Failed to load Vosk model. Check the model path and dependencies.")
        return

    logger.info("Testing wake word detection...")
    wake_word_detected = hearing.listen_for_wake_word()
    if wake_word_detected:
        logger.info("Wake word successfully detected!")
    else:
        logger.warning("Wake word not detected.")

    logger.info("Testing speech recognition...")
    recognized_text = hearing.listen(timeout=5)
    if recognized_text:
        logger.info(f"Recognized speech: {recognized_text}")
    else:
        logger.warning("No speech detected within timeout.")

    logger.info("Closing Hearing module...")
    hearing.close()

if __name__ == "__main__":
    test_hearing_module()
