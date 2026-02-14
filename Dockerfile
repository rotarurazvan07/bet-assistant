# Use official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Install GH CLI (Binary Method), Unzip, and Curl
RUN apt-get update && apt-get install -y curl unzip && \
    # Download the binary (detects architecture automatically)
    curl -fsSL https://github.com/cli/cli/releases/download/v2.42.1/gh_2.42.1_linux_$(dpkg --print-architecture).tar.gz -o gh.tar.gz && \
    # Extract and move to /usr/local/bin
    tar xzf gh.tar.gz --strip-components=1 -C /usr/local/ && \
    rm gh.tar.gz && \
    # Verify installation
    gh --version

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your scripts
COPY . .

CMD ["echo", "hello"]