# ==============================================================================
# Production Multi-Stage Dockerfile for Render, Railway & Cloud Deployments
# Builds the Vite React Frontend, pre-seeds the analytical DuckDB engine,
# and serves full-stack via Python FastAPI in a single container.
# ==============================================================================

# Stage 1: Build Frontend SPA
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Python FastAPI Backend with Pre-Built Analytical Database & Embedded UI
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY db/ /app/db/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Pre-build embedded analytical database (ey_bi.duckdb) at image build time for instant 0ms cold start
RUN python3 -c "\
import duckdb; \
con = duckdb.connect('/app/ey_bi.duckdb'); \
con.execute(open('/app/db/01_schema.sql').read().replace('NUMERIC(14, 2)', 'DOUBLE').replace('ON DELETE CASCADE', '')); \
con.execute(open('/app/db/seed/seed_data.sql').read()); \
con.execute(open('/app/db/02_views.sql').read().replace('::numeric', '::DOUBLE')); \
con.close(); \
print('Pre-seeded ey_bi.duckdb successfully!')"

ENV PYTHONPATH=/app
ENV DUCKDB_PATH=/app/ey_bi.duckdb
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
