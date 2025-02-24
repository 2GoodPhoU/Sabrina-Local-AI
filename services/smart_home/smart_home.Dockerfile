# Base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy required files
COPY smarthome_docker_requirements.txt requirements.txt
COPY smart_home.py smart_home.py

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose API port
EXPOSE 8500

# Start Smart Home API
CMD ["uvicorn", "smart_home:app", "--host", "0.0.0.0", "--port", "8500"]
