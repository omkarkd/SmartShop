FROM python:3.11-slim

# Install Chromium from Debian (works on both amd64 and arm64)
# undetected-chromedriver will auto-download matching chromedriver at runtime
# Debian's chromium-driver is kept as fallback
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    chromium-common \
    chromium-sandbox \
    && ln -sf /usr/bin/chromium /usr/bin/google-chrome \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (scraper only: selenium, uc, pymongo)
COPY requirements-docker.txt /app/requirements-docker.txt
RUN pip install --no-cache-dir --break-system-packages -r /app/requirements-docker.txt 2>/dev/null \
    || pip install --no-cache-dir -r /app/requirements-docker.txt

# Copy scraper code
COPY scrapper/ /app/scrapper/

# Set to headless mode inside container
ENV CHROME_HEADLESS=true

WORKDIR /app

ENTRYPOINT ["python", "-m", "scrapper.docker_entry"]
