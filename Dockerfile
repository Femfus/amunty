# ───────────────────────────────────────────────
# Amunty — Self-hosted AI Workspace
# ───────────────────────────────────────────────

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install backend
COPY backend/pyproject.toml backend/
RUN pip install --no-cache-dir -e backend/

# Copy backend code
COPY backend/ backend/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist /app/static

# Data directory
RUN mkdir -p /app/data/workspace

EXPOSE 7000

CMD ["uvicorn", "amunty.main:app", "--host", "0.0.0.0", "--port", "7000", "--log-level", "info"]
