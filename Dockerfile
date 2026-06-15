FROM python:3.11-slim

# Install Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (scraper only: selenium, uc, pymongo)
COPY requirements-docker.txt /app/requirements-docker.txt
RUN pip install --no-cache-dir -r /app/requirements-docker.txt

# Copy scraper code
COPY scrapper/ /app/scrapper/

# Set to headless mode inside container
ENV CHROME_HEADLESS=true

WORKDIR /app

ENTRYPOINT ["python", "-m", "scrapper.docker_entry"]
