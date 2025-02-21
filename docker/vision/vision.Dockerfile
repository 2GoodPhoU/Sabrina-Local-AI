# Base Image (Python + FFmpeg)
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies for vision processing
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    x11-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirement file and install dependencies
COPY docker/vision/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy API and scripts
COPY api/vision_api.py /app/api/vision_api.py
COPY scripts/vision.py /app/scripts/vision.py

# Command to start the API
CMD ["python", "/app/api/vision_api.py"]

