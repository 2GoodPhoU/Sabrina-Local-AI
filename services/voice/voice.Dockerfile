# Base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy required files
COPY voice_docker_requirements.txt requirements.txt
COPY voice_api.py voice_api.py
COPY voice_api_client.py voice_api_client.py

# Create necessary directories
RUN mkdir -p logs data/audio_cache config

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose API port
EXPOSE 8100

# Set Python path
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Set environment variables
ENV VOICE_API_PORT=8100
ENV VOICE_API_KEY=sabrina-dev-key

# Start Voice API
CMD ["python", "voice_api.py"]
