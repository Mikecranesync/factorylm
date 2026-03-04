FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir \
    "fastapi>=0.109.0" \
    "uvicorn[standard]>=0.27.0" \
    "pydantic-settings>=2.0.0" \
    "pymodbus>=3.6.0" \
    "python-dotenv>=1.0.0" \
    "httpx>=0.26.0" \
    && pip install --no-cache-dir -e .

EXPOSE 8001
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
