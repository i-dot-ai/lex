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

# Use a shell script to keep the container running
RUN echo '#!/bin/sh\nwhile true; do sleep 3600; done' > /app/keep_alive.sh \
    && chmod +x /app/keep_alive.sh

CMD ["/app/keep_alive.sh"]
