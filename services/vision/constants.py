import os
from enum import Enum

### DIRECTORY & FILE PATHS ###
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # Correct base directory

# Vision module paths
VISION_DIR = os.path.join(BASE_DIR, "services", "vision")
CAPTURE_DIRECTORY = os.path.join(VISION_DIR, "captures")  # Directory for storing screenshots

# Correct Model & Dataset Paths
MODEL_DIR = os.path.join(BASE_DIR, "models", "yolov8")  # Now correctly points to /models/yolov8
MODEL_NAME = "custom_yolo.pt"
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_NAME)  # Full model path

DATASETS_DIR = os.path.join(BASE_DIR, "datasets")
DATASET_PATH = os.path.join(DATASETS_DIR, "dataset1", "data.yaml")
DATASET_EVAL_PATH = os.path.join(DATASETS_DIR, "dataset1", "eval.yaml")
DATASETS = [DATASET_PATH]  # List of dataset paths

### SCREEN CAPTURE MODES ###
class CaptureMode(Enum):
    """Modes for screen capture."""
    FULL_SCREEN = "full_screen"  # Captures the entire screen
    SPECIFIC_REGION = "specific_region"  # Captures a user-defined region
    ACTIVE_WINDOW = "active_window"  # Captures the currently active window

class ScreenRegion(Enum):
    """Predefined screen regions for capturing."""
    LEFT_HALF = "left_half"
    RIGHT_HALF = "right_half"
    TOP_HALF = "top_half"
    BOTTOM_HALF = "bottom_half"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CUSTOM = "custom"  # Allows manually defined coordinates

### IMAGE STORAGE SETTINGS ###
MAX_IMAGES = 5  # Maximum number of stored images before cleanup

### YOLO MODEL SETTINGS ###
TRAINING_EPOCHS = 50  # Number of training epochs (default: 50)
TRAINING_BATCH_SIZE = 8  # Batch size for training
TRAINING_LEARNING_RATE = 0.001  # Learning rate for model training
MIN_CONFIDENCE = 0.4  # Minimum confidence for object detection

### DETECTION PARAMETERS ###
DETECTION_CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence to consider a detection
NON_MAX_SUPPRESSION_THRESHOLD = 0.4  # Overlapping detection threshold

### VOICE API ###
VOICE_API_URL = "http://localhost:8100/get_file_audio"  # URL for TTS API

### LOGGING SETTINGS ###
LOGGING_LEVEL = "INFO"  # Logging level (DEBUG, INFO, WARNING, ERROR)