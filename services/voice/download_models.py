import os
import time
import requests

# Define model directory and URLs
MODEL_DIR = "../../models/piper"
MODEL_URLS = {
    "en_US-amy-medium": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US-amy-medium.onnx",
    "en_US-kathleen-medium": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US-kathleen-medium.onnx",
    "en_US-jenny-medium": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US-jenny-medium.onnx",
}

# Ensure model directory exists
os.makedirs(MODEL_DIR, exist_ok=True)


def download_model(model_name, url):
    """Download a model if it's missing, with retry logic."""
    model_path = os.path.join(MODEL_DIR, f"{model_name}.onnx")

    if (
        os.path.exists(model_path) and os.path.getsize(model_path) > 1024
    ):  # Ensure it's not empty
        print(f"✅ Model {model_name} already exists.")
        return

    print(f"⬇️ Downloading model: {model_name}...")
    for attempt in range(5):  # Retry up to 5 times
        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(model_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"✅ Model {model_name} downloaded successfully.")
                return
            else:
                print(f"⚠️ Failed to download {model_name}, retrying...")
        except Exception as e:
            print(f"❌ Error downloading {model_name}: {e}")
        time.sleep(2)  # Wait before retrying

    print(f"❌ Failed to download {model_name} after multiple attempts.")


def main():
    print("🔧 Ensuring all required models are present...")
    for model, url in MODEL_URLS.items():
        download_model(model, url)

    print("✅ All models are ready. You can now restart your Docker container.")


if __name__ == "__main__":
    main()
