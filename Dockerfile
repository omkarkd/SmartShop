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

# Install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN rm /app/requirements.txt

# Copy entire application
COPY . /app/

# Remove files not needed in container
RUN rm -f /app/requirements-docker-full.txt /app/requirements-docker.txt /app/requirements-dev.txt /app/atlas-credentials.env /app/cred.txt /app/.dockerignore /app/.streamlit/secrets.toml

# Chrome headless mode for container
ENV CHROME_HEADLESS=true
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_VERSION_MAIN=149
ENV PYTHONUNBUFFERED=1

# Default MongoDB connection — MUST override via env var or Streamlit secrets
# ⚠ NEVER hardcode real credentials here; they end up in the image.
ENV MONGO_URI=""
ENV DB_NAME=smartshop

EXPOSE 8501

# Use $PORT if set (Render/Streamlit Cloud), otherwise 8501
ENTRYPOINT ["sh", "-c", "streamlit run admin_app.py --server.port=${PORT:-8501} --server.headless=true --server.address=0.0.0.0"]
