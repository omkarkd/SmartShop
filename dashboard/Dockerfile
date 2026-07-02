FROM python:3.11-slim

RUN pip install --no-cache-dir --upgrade pip

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN rm /app/requirements.txt

COPY shared/ /app/shared/
COPY dashboard/ /app/dashboard/
COPY .streamlit/config.toml /app/.streamlit/config.toml

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# MONGO_URI must be set at runtime via environment variable or Streamlit secrets
# DB_NAME defaults to "smartshop"
# ADMIN_SEED_USER and ADMIN_SEED_PASS for first-user bootstrap

EXPOSE 8501

CMD ["sh", "-c", "streamlit run dashboard/app.py --server.port=${PORT:-8501} --server.headless=true --server.address=0.0.0.0"]
