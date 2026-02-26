"""Tests for the AgentRelay — Discord webhook message posting."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from factorylm.discord.relay import AgentRelay, RelayMessage


def test_configured_agents():
    """Only agents with non-empty webhook URLs are listed."""
    relay = AgentRelay(
        agent_webhooks={"tony": "https://discord.com/api/webhooks/1/abc", "ultron": "", "jarvis": ""},
    )
    assert relay.configured_agents == ["tony"]


def test_configured_agents_empty():
    """No agents when all webhooks are empty."""
    relay = AgentRelay(agent_webhooks={"tony": "", "ultron": ""})
    assert relay.configured_agents == []


def test_has_alerts():
    relay = AgentRelay(alerts_webhook="https://discord.com/api/webhooks/2/def")
    assert relay.has_alerts is True

    relay2 = AgentRelay(alerts_webhook="")
    assert relay2.has_alerts is False


def test_has_dispatch():
    relay = AgentRelay(dispatch_webhook="https://discord.com/api/webhooks/3/ghi")
    assert relay.has_dispatch is True

    relay2 = AgentRelay(dispatch_webhook="")
    assert relay2.has_dispatch is False


@pytest.mark.asyncio
async def test_post_no_webhook():
    """Posting to an unconfigured agent returns False."""
    relay = AgentRelay(agent_webhooks={})
    msg = RelayMessage(agent="tony", content="hello")
    result = await relay.post(msg)
    assert result is False
    await relay.close()


@pytest.mark.asyncio
async def test_post_alert_no_webhook():
    """Posting alert with no alerts webhook returns False."""
    relay = AgentRelay(alerts_webhook="")
    import discord
    embed = discord.Embed(title="test")
    result = await relay.post_alert(embed)
    assert result is False
    await relay.close()


@pytest.mark.asyncio
async def test_post_dispatch_no_webhook():
    """Posting dispatch with no dispatch webhook returns False."""
    relay = AgentRelay(dispatch_webhook="")
    import discord
    embed = discord.Embed(title="test")
    result = await relay.post_dispatch(embed)
    assert result is False
    await relay.close()


@pytest.mark.asyncio
async def test_post_sends_via_webhook():
    """Verify that post() calls Webhook.send with correct params."""
    relay = AgentRelay(
        agent_webhooks={"tony": "https://discord.com/api/webhooks/1/abc"},
    )

    mock_webhook_instance = MagicMock()
    mock_webhook_instance.send = AsyncMock()

    with patch("factorylm.discord.relay.discord.Webhook.from_url", return_value=mock_webhook_instance):
        msg = RelayMessage(agent="tony", content="test message")
        result = await relay.post(msg)

    assert result is True
    mock_webhook_instance.send.assert_called_once()
    call_kwargs = mock_webhook_instance.send.call_args[1]
    assert call_kwargs["content"] == "test message"
    assert call_kwargs["username"] == "Tony"
    await relay.close()


@pytest.mark.asyncio
async def test_relay_message_with_embed():
    """RelayMessage can carry an embed."""
    import discord
    embed = discord.Embed(title="Alert")
    msg = RelayMessage(agent="ultron", embed=embed)
    assert msg.agent == "ultron"
    assert msg.embed is not None
    assert msg.content == ""
