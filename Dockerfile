FROM python:3.10-slim-bookworm

# Global envs for smaller layers
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 1. Install system tools + clean up in ONE layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && pip install --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy requirement files first (better caching)
COPY setup/requirements-dashboard.txt .
COPY setup/requirements-scrape.txt .

# 3. Install Python deps AND purge build tools in the same layer as installs
# This ensures 'git' doesn't stay in the final image layers
RUN pip install -r requirements-dashboard.txt \
    && pip install -r requirements-scrape.txt \
    && apt-get purge -y --auto-remove git \
    && rm -rf /var/lib/apt/lists/*

# 4. Install EXACTLY what we need for Chromium and nothing else
RUN playwright install-deps chromium \
    && playwright install chromium \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy app code (relying on .dockerignore to skip .git and local venv)
COPY . .

# Default command
CMD ["python", "main.py", "--help"]