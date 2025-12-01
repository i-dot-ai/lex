FROM python:3.12-slim

# Install curl for healthcheck and uv
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install uv

WORKDIR /app

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml uv.lock README.md ./

# Copy source code
COPY src/ ./src/

# Copy bulk export script for scheduled job
COPY scripts/bulk_export_parquet.py ./scripts/

# Install dependencies
RUN uv sync

EXPOSE 8000

# Use uv to run the application
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
