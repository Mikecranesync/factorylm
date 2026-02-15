#!/usr/bin/env python3
"""Long polling -> webhook forwarder for @JarvisMIO_bot"""
import requests
import time
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = '8387943893:AAEynugW3SP1sWs6An4aNgZParSSRBlWSJk'
WEBHOOK_URL = 'http://localhost:8100/telegram/webhook'
last_update_id = 0

logger.info('Starting long polling for @JarvisMIO_bot...')

while True:
    try:
        resp = requests.get(
            f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
            params={'offset': last_update_id + 1, 'timeout': 30},
            timeout=35
        )
        data = resp.json()
        
        if not data.get('ok'):
            logger.error(f'Telegram API error: {data}')
            time.sleep(5)
            continue
        
        for update in data.get('result', []):
            last_update_id = update['update_id']
            msg = update.get('message', {})
            text = msg.get('text', '[no text]')
            user = msg.get('from', {}).get('first_name', 'Unknown')
            chat_id = msg.get('chat', {}).get('id', 0)
            
            logger.info(f'[{user}] ({chat_id}): {text[:50]}')
            
            try:
                r = requests.post(WEBHOOK_URL, json=update, timeout=60)
                logger.info(f'  -> Forwarded ({r.status_code})')
            except Exception as e:
                logger.error(f'  -> Forward failed: {e}')
            
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        sys.exit(0)
    except requests.exceptions.Timeout:
        # Normal timeout from long polling, just retry
        continue
    except Exception as e:
        logger.error(f'Error: {e}')
        time.sleep(5)
