"""WhatsApp webhook server — FastAPI app for Twilio WhatsApp integration.

Run: uvicorn services.whatsapp.main:app --host 0.0.0.0 --port 8200
Or:  make whatsapp
"""

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request, Response

# Ensure monorepo root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.whatsapp.adapter import handle_webhook, validate_twilio_signature

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("factorylm.whatsapp")

app = FastAPI(title="FactoryLM WhatsApp Adapter", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "whatsapp-adapter"}


@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """Receive Twilio WhatsApp webhooks."""
    form = await request.form()
    form_dict = dict(form)

    # Validate signature if auth token is configured
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if not validate_twilio_signature(url, form_dict, signature):
        logger.warning("Invalid Twilio signature — rejecting webhook")
        return Response(content="Forbidden", status_code=403)

    # Process message through pipeline
    twiml = await handle_webhook(form_dict)

    return Response(content=twiml, media_type="application/xml")


@app.post("/whatsapp/status")
async def whatsapp_status(request: Request):
    """Receive Twilio delivery status callbacks (optional)."""
    form = await request.form()
    sid = form.get("MessageSid", "?")
    status = form.get("MessageStatus", "?")
    logger.debug("WhatsApp status: %s → %s", sid, status)
    return Response(content="OK", status_code=200)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WHATSAPP_PORT", "8200"))
    uvicorn.run(app, host="0.0.0.0", port=port)
