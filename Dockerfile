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

# Install dependencies (requirements-docker-full.txt has ALL deps)
COPY requirements-docker-full.txt /app/requirements-docker-full.txt
RUN pip install --no-cache-dir -r /app/requirements-docker-full.txt
RUN rm /app/requirements-docker-full.txt

# Copy entire application
COPY . /app/

# Remove files not needed in container
RUN rm -f /app/requirements-docker.txt /app/requirements-dev.txt /app/atlas-credentials.env /app/cred.txt /app/.dockerignore

# Chrome headless mode for container
ENV CHROME_HEADLESS=true
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_VERSION_MAIN=149
ENV PYTHONUNBUFFERED=1

# Default MongoDB connection (host.docker.internal reaches host from container)
ENV MONGO_URI=mongodb://host.docker.internal:27017
ENV DB_NAME=smartshop

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "admin_app.py", "--server.port=8501", "--server.headless=true", "--server.address=0.0.0.0"]
