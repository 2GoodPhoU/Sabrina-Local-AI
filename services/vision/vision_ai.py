import torch
import os
from ultralytics import YOLO

from services.vision.constants import MODEL_PATH, DATASETS, TRAINING_EPOCHS, TRAINING_BATCH_SIZE, TRAINING_LEARNING_RATE, MIN_CONFIDENCE

class VisionAI:
    def __init__(self):
        """Initialize the VisionAI module for YOLO-based object detection."""
        self.model_path = MODEL_PATH
        self.model = None
        self.load_model()
    
    def load_model(self):
        """Load or create a YOLO model."""
        print("[VisionAI] Loading YOLO model at:", self.model_path)
        if not os.path.exists(self.model_path):
            print("[VisionAI] Model not found. Training a new model...")
            self.create_model()
            self.train_model()
        else:
            print("[VisionAI] Model found. Loading existing model...")
            self.model = YOLO(self.model_path)
    
    def create_model(self):
        """Load a pre-trained YOLO model."""
        self.model = YOLO("yolov8n.pt").to('cuda' if torch.cuda.is_available() else 'cpu')

    def train_model(self):
        """Train the YOLO model using provided datasets."""
        print("[VisionAI] Training the YOLO model...")
        print("[VisionAI] Training has been commented out...")
        """
        for data_set in DATASETS:
            self.model.train(data=data_set, epochs=TRAINING_EPOCHS, batch=TRAINING_BATCH_SIZE, lr0=TRAINING_LEARNING_RATE, device='cuda')
            self.model.save(self.model_name)
        """

    def evaluate_model(self):
        """Evaluate the YOLO model on test datasets."""
        print("[VisionAI] Evaluating the YOLO model...")
        for data_set in DATASETS:
            results = self.model.evaluate(data=data_set)
            print(results)
    
    def detect_objects(self, image_path):
        """Detect objects in the given image using YOLO."""
        if not self.model:
            print("[VisionAI] Model not loaded. Ensure training is completed.")
            return []
        if not os.path.exists(image_path):
            print("[VisionAI] Image file does not exist.")
            return []
        results = self.model(image_path)
        detections = []
        for result in results:
            for i, box in enumerate(result.boxes.xyxy):
                confidence = float(result.boxes.conf[i])
                if confidence < MIN_CONFIDENCE:
                    continue  # Skip low-confidence detections
                label_index = int(result.boxes.cls[i])
                label = result.names[label_index] if label_index < len(result.names) else "Unknown"
                detections.append({
                    "type": label,
                    "coordinates": [int(box[0]), int(box[1]), int(box[2]), int(box[3])],
                    "confidence": confidence
                })
        return detections
