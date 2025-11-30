FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if any needed for orjson/asyncpg build)
# usually slim is enough, but sometimes gcc is needed. 
# asyncpg and orjson usually have wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition
COPY pyproject.toml README.md ./

# Install dependencies
# We use pip to install directly from pyproject.toml
RUN pip install --no-cache-dir .

# Copy source code
COPY src ./src
COPY deploy ./deploy

# Set PYTHONPATH to include src
ENV PYTHONPATH=/app/src

# Create a non-root user and switch to it
RUN useradd -m -u 1000 gemini && \
    chown -R gemini:gemini /app

USER gemini

# Default command (can be overridden)
CMD ["python", "deploy/rotator.py"]
