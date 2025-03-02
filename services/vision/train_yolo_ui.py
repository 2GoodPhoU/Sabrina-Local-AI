#!/usr/bin/env python3
"""
YOLOv8 Training Helper for UI Elements
======================================
This script helps prepare and train a YOLOv8 model for UI element detection.
"""

import os
import sys
import logging
import argparse
import shutil
from pathlib import Path
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("yolo_trainer")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="YOLOv8 Training Helper for UI Elements"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directory containing training images",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/yolov8_ui",
        help="Directory to save the model",
    )
    parser.add_argument(
        "--epochs", type=int, default=50, help="Number of training epochs"
    )
    parser.add_argument(
        "--image-size", type=int, default=640, help="Image size for training"
    )
    parser.add_argument(
        "--batch-size", type=int, default=8, help="Batch size for training"
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Only prepare the dataset, don't train",
    )
    return parser.parse_args()


def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import ultralytics

        logger.info(f"Ultralytics version: {ultralytics.__version__}")
        return True
    except ImportError:
        logger.error(
            "Ultralytics not found. Please install it: pip install ultralytics"
        )
        return False


def prepare_dataset(data_dir, output_dir):
    """
    Prepare the dataset for YOLOv8 training

    Args:
        data_dir: Directory containing images and annotations
        output_dir: Directory to save the prepared dataset

    Returns:
        Path to the YAML config file for training
    """
    # Create dataset directory structure
    dataset_dir = os.path.join(output_dir, "dataset")
    images_dir = os.path.join(dataset_dir, "images")
    labels_dir = os.path.join(dataset_dir, "labels")

    # Create subdirectories
    for split in ["train", "val"]:
        os.makedirs(os.path.join(images_dir, split), exist_ok=True)
        os.makedirs(os.path.join(labels_dir, split), exist_ok=True)

    # UI element classes
    classes = [
        "button",
        "checkbox",
        "dropdown",
        "text_field",
        "link",
        "icon",
        "menu",
        "tab",
        "scrollbar",
        "slider",
        "toggle",
        "radio_button",
    ]

    # Create the YAML config file
    yaml_path = os.path.join(dataset_dir, "data.yaml")
    with open(yaml_path, "w") as f:
        f.write(f"path: {dataset_dir}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write("test: images/val\n\n")
        f.write(f"nc: {len(classes)}\n")
        f.write(f"names: {classes}\n")

    # Collect image and label files
    image_files = []
    for ext in ["*.jpg", "*.jpeg", "*.png"]:
        image_files.extend(list(Path(data_dir).glob(f"**/{ext}")))

    # If no images found, exit
    if not image_files:
        logger.error(f"No images found in {data_dir}")
        return None

    logger.info(f"Found {len(image_files)} images")

    # Randomly split into train and validation sets (80/20)
    random.shuffle(image_files)
    split_idx = int(len(image_files) * 0.8)
    train_images = image_files[:split_idx]
    val_images = image_files[split_idx:]

    # Copy images and labels to the dataset directory
    for split, images in [("train", train_images), ("val", val_images)]:
        for img_path in images:
            # Copy image
            shutil.copy(str(img_path), os.path.join(images_dir, split, img_path.name))

            # Look for corresponding label file
            label_path = img_path.with_suffix(".txt")
            if label_path.exists():
                shutil.copy(
                    str(label_path), os.path.join(labels_dir, split, label_path.name)
                )
            else:
                logger.warning(f"Label file not found for {img_path}")

    logger.info(
        f"Dataset prepared: {len(train_images)} training images, {len(val_images)} validation images"
    )
    return yaml_path


def train_model(yaml_path, output_dir, epochs, image_size, batch_size):
    """
    Train a YOLOv8 model for UI element detection

    Args:
        yaml_path: Path to the YAML config file
        output_dir: Directory to save the model
        epochs: Number of training epochs
        image_size: Image size for training
        batch_size: Batch size for training

    Returns:
        Path to the trained model
    """
    try:
        from ultralytics import YOLO

        # Create models directory
        os.makedirs(os.path.join(output_dir, "weights"), exist_ok=True)

        # Start with a pre-trained YOLOv8 model
        model = YOLO("yolov8n.pt")

        # Train the model
        logger.info(f"Starting training for {epochs} epochs...")
        results = model.train(
            data=yaml_path,
            epochs=epochs,
            imgsz=image_size,
            batch=batch_size,
            name="ui_elements_detector",
            project=output_dir,
        )
        print(results)

        # Get the path to the best model
        best_model_path = os.path.join(
            output_dir, "ui_elements_detector", "weights", "best.pt"
        )

        # Copy the model to the final location
        final_model_path = os.path.join(output_dir, "weights", "yolov8_ui.pt")
        shutil.copy(best_model_path, final_model_path)

        logger.info(f"Model trained and saved to {final_model_path}")
        return final_model_path

    except ImportError as e:
        logger.error(f"Error importing required modules: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error training model: {str(e)}")
        return None


def create_example_dataset(output_dir):
    """
    Create an example dataset structure to show the expected format

    Args:
        output_dir: Directory to create the example
    """
    example_dir = os.path.join(output_dir, "example_dataset")
    os.makedirs(example_dir, exist_ok=True)

    # Create example YAML file
    yaml_content = """path: /path/to/dataset
train: images/train
val: images/val
test: images/val

nc: 12
names: ["button", "checkbox", "dropdown", "text_field", "link", "icon", "menu", "tab", "scrollbar", "slider", "toggle", "radio_button"]
"""

    with open(os.path.join(example_dir, "data.yaml"), "w") as f:
        f.write(yaml_content)

    # Create example annotation file
    annotation_content = """0 0.716797 0.395833 0.216406 0.147222
1 0.687109 0.379167 0.196484 0.147222
2 0.585547 0.372396 0.155859 0.099479
"""

    with open(os.path.join(example_dir, "example_annotation.txt"), "w") as f:
        f.write(annotation_content)

    # Create README file with instructions
    readme_content = """# YOLOv8 UI Element Detection Dataset

## Dataset Structure
```
dataset/
├── images/
│   ├── train/
│   │   ├── image1.jpg
│   │   ├── image2.jpg
│   │   └── ...
│   └── val/
│       ├── image_val1.jpg
│       ├── image_val2.jpg
│       └── ...
├── labels/
│   ├── train/
│   │   ├── image1.txt
│   │   ├── image2.txt
│   │   └── ...
│   └── val/
│       ├── image_val1.txt
│       ├── image_val2.txt
│       └── ...
└── data.yaml
```

## Annotation Format
Each text file contains annotations in YOLO format:
```
class_id center_x center_y width height
```

Where:
- class_id: Integer ID of the UI element class (0-11)
- center_x, center_y: Normalized coordinates of the bounding box center (0-1)
- width, height: Normalized width and height of the bounding box (0-1)

## Classes
0: button
1: checkbox
2: dropdown
3: text_field
4: link
5: icon
6: menu
7: tab
8: scrollbar
9: slider
10: toggle
11: radio_button
```"""

    with open(os.path.join(example_dir, "README.md"), "w") as f:
        f.write(readme_content)

    logger.info(f"Example dataset created at {example_dir}")


def main():
    """Main function"""
    # Parse arguments
    args = parse_arguments()

    # Check dependencies
    if not check_dependencies():
        return 1

    print("\n===== YOLOv8 Training Helper for UI Elements =====\n")

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # If data directory exists, prepare the dataset
    if os.path.exists(args.data_dir):
        yaml_path = prepare_dataset(args.data_dir, args.output_dir)

        if not yaml_path:
            logger.error("Failed to prepare dataset. Exiting.")
            return 1

        logger.info(f"Dataset configuration saved to {yaml_path}")

        # Train the model if not in prepare-only mode
        if not args.prepare_only:
            model_path = train_model(
                yaml_path,
                args.output_dir,
                args.epochs,
                args.image_size,
                args.batch_size,
            )

            if model_path:
                print(f"\nModel trained successfully and saved to: {model_path}")
                print(
                    "\nYou can now use this model for UI element detection by setting:"
                )
                print(f"MODEL_PATH = '{model_path}'")
                print("in your services/vision/constants.py file")
            else:
                print("\nModel training failed. Please check the logs for errors.")
                return 1
        else:
            print("\nDataset preparation complete. Use the following to train:")
            print(
                f"python {sys.argv[0]} --data-dir {args.data_dir} --output-dir {args.output_dir}"
            )
    else:
        logger.error(f"Data directory not found: {args.data_dir}")

        # Create example dataset structure
        create_example_dataset(args.output_dir)

        print(
            "\nData directory not found. An example dataset structure has been created at:"
        )
        print(f"{os.path.join(args.output_dir, 'example_dataset')}")
        print("\nPrepare your dataset according to this structure and try again.")
        return 1

    print("\n===== YOLOv8 Training Helper Complete =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
