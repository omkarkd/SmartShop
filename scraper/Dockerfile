FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    chromium-common \
    chromium-sandbox \
    && ln -sf /usr/bin/chromium /usr/bin/google-chrome \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN rm /app/requirements.txt

COPY shared/ /app/shared/
COPY scraper/ /app/scraper/

ENV CHROME_HEADLESS=true
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_VERSION_MAIN=149
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# MONGO_URI must be set at runtime via environment variable
# DB_NAME defaults to "smartshop"

CMD ["python", "-m", "scraper.main"]
