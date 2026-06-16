FROM python:3.11-slim

# Install dependencies including Chromium + chromedriver from Debian repos
# chromedriver is provided by Debian matching the exact Chromium build
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

# Set to headless mode inside container; use system chromedriver (UC can't download
# matching chromedriver for Debian's arm64 Chromium from Google's CDN)
ENV CHROME_HEADLESS=true
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_VERSION_MAIN=149

WORKDIR /app

ENTRYPOINT ["python", "-m", "scrapper.docker_entry"]
