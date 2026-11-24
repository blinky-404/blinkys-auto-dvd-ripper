# ============================================================================
# Blinky's Auto DVD Ripper v2.0 - Control Center Container Image
# Includes FastAPI, FFmpeg (audio/frame inspection), curl, and Docker CLI
# ============================================================================
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git curl docker.io docker.io usbutils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY webui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY webui/ .
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh /app/scripts/*.py
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
