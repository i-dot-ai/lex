FROM python:3.12-slim

# Install uv
RUN pip install uv

WORKDIR /app

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml uv.lock README.md ./

# Copy source code
COPY src/ ./src/

# Install dependencies
RUN uv sync

EXPOSE 8080

# Use uv to run the application
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
