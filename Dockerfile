FROM python:3.11-slim

# Install system dependencies for OpenCV, video rendering, and spatial algorithms
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up non-root user matching Hugging Face Spaces specifications (UID 1000)
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR $HOME/app

# Install lightweight PyTorch CPU wheels first for quick building and startup
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy and install python dependencies
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Copy application source code, models, database, and frontend assets
COPY --chown=user:user . .

# Hugging Face Spaces requires listening on port 7860
EXPOSE 7860

# Launch FastAPI with WebSockets on port 7860
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "7860"]

