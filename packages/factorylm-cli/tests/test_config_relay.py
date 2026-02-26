"""Tests for config loading with agent relay fields."""

from factorylm.config import load_config, write_default_config


def test_default_config_has_agent_webhooks(tmp_path):
    """Default config TOML includes [discord.agent_webhooks] section."""
    path = tmp_path / "config.toml"
    write_default_config(path)
    content = path.read_text()
    assert "[discord.agent_webhooks]" in content
    assert 'tony = ""' in content
    assert 'ultron = ""' in content
    assert 'alerts_webhook' in content
    assert 'dispatch_webhook' in content


def test_load_config_with_agent_webhooks(tmp_path):
    """Config loader correctly parses agent_webhooks dict."""
    config_text = """\
[discord]
token = "test-token"
alerts_webhook = "https://discord.com/api/webhooks/alerts/abc"
dispatch_webhook = "https://discord.com/api/webhooks/dispatch/def"

[discord.agent_webhooks]
tony = "https://discord.com/api/webhooks/tony/123"
ultron = "https://discord.com/api/webhooks/ultron/456"
jarvis = ""
"""
    path = tmp_path / "config.toml"
    path.write_text(config_text)
    cfg = load_config(path)

    assert cfg.discord.token == "test-token"
    assert cfg.discord.alerts_webhook == "https://discord.com/api/webhooks/alerts/abc"
    assert cfg.discord.dispatch_webhook == "https://discord.com/api/webhooks/dispatch/def"
    assert cfg.discord.agent_webhooks["tony"] == "https://discord.com/api/webhooks/tony/123"
    assert cfg.discord.agent_webhooks["ultron"] == "https://discord.com/api/webhooks/ultron/456"
    assert cfg.discord.agent_webhooks["jarvis"] == ""


def test_load_config_no_webhooks(tmp_path):
    """Config without agent_webhooks section defaults to empty dict."""
    config_text = """\
[discord]
token = "test"
"""
    path = tmp_path / "config.toml"
    path.write_text(config_text)
    cfg = load_config(path)

    assert cfg.discord.agent_webhooks == {}
    assert cfg.discord.alerts_webhook == ""
    assert cfg.discord.dispatch_webhook == ""


def test_env_override_alerts_webhook(tmp_path, monkeypatch):
    """DISCORD_ALERTS_WEBHOOK env var overrides config."""
    config_text = '[discord]\nalerts_webhook = ""\n'
    path = tmp_path / "config.toml"
    path.write_text(config_text)

    monkeypatch.setenv("DISCORD_ALERTS_WEBHOOK", "https://override.webhook/abc")
    cfg = load_config(path)
    assert cfg.discord.alerts_webhook == "https://override.webhook/abc"


def test_env_override_dispatch_webhook(tmp_path, monkeypatch):
    """DISCORD_DISPATCH_WEBHOOK env var overrides config."""
    config_text = '[discord]\ndispatch_webhook = ""\n'
    path = tmp_path / "config.toml"
    path.write_text(config_text)

    monkeypatch.setenv("DISCORD_DISPATCH_WEBHOOK", "https://override.webhook/def")
    cfg = load_config(path)
    assert cfg.discord.dispatch_webhook == "https://override.webhook/def"
