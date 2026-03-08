FROM python:3.12-slim

WORKDIR /app

# Install telegram bot dependencies
COPY services/telegram_bot/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy monorepo code needed by the bot
COPY core/ core/
COPY services/telegram_bot/ services/telegram_bot/

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.telegram_bot"]
