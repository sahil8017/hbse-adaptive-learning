# Dockerfile for Hugging Face Spaces (Next.js + FastAPI)

# --- Stage 1: Build Frontend ---
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Stage 2: Runtime Stage ---
FROM python:3.12-slim AS runtime

# Install system dependencies (Node.js and build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    build-essential \
    gcc \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy python dependencies
COPY requirements.txt ./requirements.txt

# Install python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend /app/frontend

# Copy backend codebase
COPY backend ./backend
COPY data ./data

# Expose Hugging Face Space port
EXPOSE 7860

# Copy start script
COPY start.sh ./start.sh
RUN chmod +x ./start.sh

# Run startup script
CMD ["./start.sh"]
