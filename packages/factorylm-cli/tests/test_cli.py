"""Tests for CLI entry points."""

from typer.testing import CliRunner

from factorylm.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "factorylm" in result.stdout


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Connect any PLC" in result.stdout


def test_status_no_config(tmp_path):
    """Status should work even without a config file."""
    result = runner.invoke(app, ["status", "--config", str(tmp_path / "nonexistent.toml")])
    assert result.exit_code == 0
    assert "FactoryLM Status" in result.stdout


def test_init_creates_config(tmp_path):
    cfg = tmp_path / "test_config.toml"
    result = runner.invoke(app, ["init", "--config", str(cfg)], input="modbus\n192.168.1.100\n502\n2.0\n8001\n\n0\n")
    assert result.exit_code == 0
    assert cfg.exists()
    content = cfg.read_text()
    assert "[plc]" in content
    assert "modbus" in content
