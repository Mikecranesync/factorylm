FROM python:3.12-slim

WORKDIR /app

# Install whatsapp adapter dependencies
COPY services/whatsapp/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy monorepo code needed by the adapter
COPY core/ core/
COPY services/whatsapp/ services/whatsapp/

ENV PYTHONPATH=/app
EXPOSE 8200

CMD ["uvicorn", "services.whatsapp.main:app", "--host", "0.0.0.0", "--port", "8200"]
