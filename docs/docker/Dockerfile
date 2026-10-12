# CANDIDATE Docker image (not active; Render still uses the Python runtime in render.yaml).
# Adds the two tools the free Python runtime lacks: DWG->DXF (LibreDWG dwg2dxf) and OCR (tesseract).
# NOT BUILT OR TESTED YET: build locally with `docker build -f docs/docker/Dockerfile -t mars .` before switching Render.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libredwg-tools tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-supabase.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-supabase.txt
COPY . .
ENV ENGINEERING_ENV=production PYTHONUNBUFFERED=1
CMD ["sh", "-c", "uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-10000}"]
