# Base: PyTorch with CUDA 12.1 — provides torch pre-installed on GPU-capable base
FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

WORKDIR /app

# System dependencies for pillow-heif (HEIC support) and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libheif-dev \
    libde265-dev \
    libx265-dev \
    cmake \
    build-essential \
    libopenblas-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (torch is already in base image, others installed here)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download CLIP ViT-L-14 weights at build time (baked into image layer, ~890 MB)
# This avoids a long download on first container start.
RUN python3 -c "\
import open_clip; \
open_clip.create_model_and_transforms('ViT-L-14', pretrained='laion2b_s32b_b82k'); \
print('CLIP model weights cached successfully')"

# Copy application code
COPY app/ ./app/

# Copy frontend (served as static files from FastAPI)
COPY ../frontend/ ./frontend/

# Data directory for SQLite DB and thumbnail cache
RUN mkdir -p /data /models

EXPOSE 8000

# Single worker: the GPU model is a module-level singleton — multiple workers
# would each load their own copy into VRAM.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
