# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY pdf_translator/web/frontend/package*.json ./
RUN npm ci
COPY pdf_translator/web/frontend/ ./
RUN npm run build

# Stage 2: Runtime
FROM eclipse-temurin:21-jre-jammy

# Install Python 3.12
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    tesseract-ocr tesseract-ocr-kor tesseract-ocr-jpn tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY pyproject.toml README.md ./
COPY pdf_translator/ pdf_translator/
RUN python3 -m pip install --no-cache-dir -e ".[all]"

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist pdf_translator/web/frontend/dist/

# Copy tests (optional, for CI)
COPY tests/ tests/

EXPOSE 8000

ENV PDF_TRANSLATOR_DATA_DIR=/data

CMD ["python3", "-m", "pdf_translator.cli.main", "serve", "--host", "0.0.0.0", "--port", "8000", "--data-dir", "/data"]
