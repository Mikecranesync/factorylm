FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY services/mes/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service source
COPY services/mes/ .

# Expose MES API port
EXPOSE 8300

# Run Alembic migrations then start the API
CMD alembic upgrade head && \
    uvicorn backend.main:app --host 0.0.0.0 --port 8300
