# Use official Playwright Python image (pre-installed with browsers and deps)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium (Playwright needs the binaries even in the official image)
RUN playwright install chromium

# Copy your scripts (main.py, dashboard.py, etc.)
COPY . .

# Default command (overridden by docker-compose)
CMD ["python", "-m", "dashboard"]
