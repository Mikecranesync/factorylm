"""Telegram Bot API alerter — sends fault and divergence alerts to Mike."""

import logging

import httpx

from cosmos.models import CosmosInsight

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramAlerter:
    """Sends formatted alerts to Telegram via Bot API (raw httpx, no SDK)."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=10.0)

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send_incident_alert(
        self,
        incident: dict,
        insight: CosmosInsight,
    ) -> bool:
        """Send a PLC fault alert with Cosmos analysis."""
        if not self.enabled:
            logger.warning("Telegram alerter not configured, skipping incident alert")
            return False

        checks = ""
        for check in insight.suggested_checks[:5]:
            checks += f"  \u2192 {_escape_html(check)}\n"

        text = (
            "\U0001f534 <b>PLC FAULT ALERT</b>\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"Incident: <b>#{_escape_html(str(incident.get('id', '?')))}</b>\n"
            f"Error: {_escape_html(str(incident.get('error_message', incident.get('description', '?'))))}\n"
            f"Node: {_escape_html(str(incident.get('node_id', '?')))}\n"
            "\n"
            f"<b>AI Analysis</b> ({_escape_html(insight.cosmos_model)})\n"
            f"Summary: {_escape_html(insight.summary)}\n"
            f"Root Cause: {_escape_html(insight.root_cause)}\n"
            f"Confidence: {int(insight.confidence * 100)}%\n"
            "\n"
            "<b>Suggested Checks:</b>\n"
            f"{checks}"
        )

        return await self._send(text)

    async def send_divergence_alert(
        self,
        drift_score: float,
        mismatches: list[dict],
        insight: CosmosInsight | None = None,
    ) -> bool:
        """Send a digital twin divergence alert."""
        if not self.enabled:
            logger.warning("Telegram alerter not configured, skipping divergence alert")
            return False

        mismatch_lines = ""
        for m in mismatches[:6]:
            tag = m["tag"]
            real = m["real"]
            sim = m["sim"]
            if m["type"] == "numeric":
                pct = int(m["drift"] * 100)
                mismatch_lines += f"  {_escape_html(tag)}: real={real}, sim={sim} (+{pct}%)\n"
            elif m["type"] == "bool":
                status = "MISMATCH"
                mismatch_lines += f"  {_escape_html(tag)}: real={real}, sim={sim} ({status})\n"
            else:
                mismatch_lines += f"  {_escape_html(tag)}: real={real}, sim={sim}\n"

        text = (
            "\U0001f7e1 <b>DIGITAL TWIN DIVERGENCE</b>\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"Drift Score: <b>{drift_score:.2f} ({int(drift_score * 100)}%)</b>\n"
            "\n"
            "<b>Mismatches:</b>\n"
            f"{mismatch_lines}"
        )

        if insight:
            text += (
                "\n"
                "<b>AI Analysis:</b>\n"
                f"Summary: {_escape_html(insight.summary)}\n"
                f"Root Cause: {_escape_html(insight.root_cause)}\n"
            )

        return await self._send(text)

    async def _send(self, text: str) -> bool:
        """POST a message to Telegram Bot API."""
        url = f"{TELEGRAM_API}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            resp = await self._client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram alert sent to chat %s", self.chat_id)
                return True
            logger.warning("Telegram API error %d: %s", resp.status_code, resp.text)
            return False
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            return False

    async def close(self) -> None:
        await self._client.aclose()


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
