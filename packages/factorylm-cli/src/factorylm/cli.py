"""FactoryLM CLI — Typer application with all commands."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

import factorylm
from factorylm.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    FactoryLMConfig,
    load_config,
    write_default_config,
)

console = Console()
app = typer.Typer(
    name="factorylm",
    help="Connect any PLC to Discord and the cloud. Industrial monitoring CLI.",
    no_args_is_help=True,
    pretty_exceptions_short=True,
)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _load(config_path: str | None = None) -> FactoryLMConfig:
    path = Path(config_path) if config_path else None
    return load_config(path)


# ── init ──────────────────────────────────────────────────────────────────

@app.command()
def init(
    config_path: str = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Interactive setup wizard — creates ~/.factorylm/config.toml."""
    path = Path(config_path) if config_path else CONFIG_FILE

    if path.exists():
        overwrite = typer.confirm(f"Config already exists at {path}. Overwrite?", default=False)
        if not overwrite:
            raise typer.Abort()

    console.print("\n[bold green]FactoryLM Setup Wizard[/bold green]\n")

    plc_type = typer.prompt("PLC protocol", default="modbus", type=str)
    plc_host = typer.prompt("PLC IP address", default="192.168.1.100")
    plc_port = typer.prompt("PLC port", default=502, type=int)
    poll_interval = typer.prompt("Poll interval (seconds)", default=2.0, type=float)
    api_port = typer.prompt("Web dashboard port", default=8001, type=int)
    discord_token = typer.prompt("Discord bot token (or leave blank)", default="")
    live_channel_id = typer.prompt("Discord live channel ID (0 to skip)", default=0, type=int)
    alerts_webhook = typer.prompt("Discord alerts webhook URL (or leave blank)", default="")

    config_text = f"""\
[plc]
type = "{plc_type}"
host = "{plc_host}"
port = {plc_port}
unit_id = 1
poll_interval = {poll_interval}

[db]
path = "~/.factorylm/tags.db"

[api]
host = "0.0.0.0"
port = {api_port}

[discord]
token = "{discord_token}"
bot_name = "FactoryLM"
mention_only = true
live_channel_id = {live_channel_id}
live_interval = 5.0
alerts_channel_id = 0
dispatch_channel_id = 0
alerts_webhook = "{alerts_webhook}"
dispatch_webhook = ""

[discord.agent_webhooks]
tony = ""
ultron = ""
jarvis = ""
hetzner = ""

[monitor]
enabled = true
poll_interval = 5.0

[cosmos]
api_key = ""
model = "nvidia/cosmos-reason2-8b"
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config_text)
    console.print(f"\n[green]Config written to {path}[/green]")
    console.print("Run [bold]factorylm connect[/bold] to test your PLC connection.")


# ── connect ───────────────────────────────────────────────────────────────

@app.command()
def connect(
    config_path: str = typer.Option(None, "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Test PLC connection — reads a few registers."""
    _setup_logging(verbose)
    cfg = _load(config_path)

    console.print(f"Connecting to [bold]{cfg.plc.type}[/bold] PLC at {cfg.plc.host}:{cfg.plc.port}...")

    from factorylm.plc.factory import create_client_from_config

    client = create_client_from_config(cfg.plc)
    if client.connect():
        console.print("[green]Connected![/green]")
        try:
            tags = client.read_tags()
            table = Table(title="PLC Tags")
            table.add_column("Tag", style="cyan")
            table.add_column("Value", style="green")
            for k, v in tags.items():
                table.add_row(k, str(v))
            console.print(table)
        except Exception as e:
            console.print(f"[yellow]Connected but read failed: {e}[/yellow]")
        finally:
            client.disconnect()
    else:
        console.print("[red]Connection failed.[/red]")
        raise typer.Exit(1)


# ── tags ──────────────────────────────────────────────────────────────────

@app.command()
def tags(
    config_path: str = typer.Option(None, "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    watch: bool = typer.Option(True, "--watch/--no-watch", help="Auto-refresh display"),
) -> None:
    """Live tag viewer — Rich table with auto-refresh."""
    _setup_logging(verbose)
    cfg = _load(config_path)

    from factorylm.plc.factory import create_client_from_config
    import time

    client = create_client_from_config(cfg.plc)
    if not client.connect():
        console.print("[red]Cannot connect to PLC.[/red]")
        raise typer.Exit(1)

    try:
        if not watch:
            tag_data = client.read_tags()
            table = Table(title="PLC Tags")
            table.add_column("Tag", style="cyan")
            table.add_column("Value", style="green")
            for k, v in tag_data.items():
                table.add_row(k, str(v))
            console.print(table)
            return

        console.print(f"[dim]Live tags from {cfg.plc.host} — Ctrl+C to stop[/dim]\n")
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                try:
                    tag_data = client.read_tags()
                    table = Table(title=f"PLC Tags — {cfg.plc.host}:{cfg.plc.port}")
                    table.add_column("Tag", style="cyan", min_width=20)
                    table.add_column("Value", style="green", min_width=15)
                    for k, v in sorted(tag_data.items()):
                        style = "bold red" if k in ("fault_alarm", "e_stop") and v else "green"
                        table.add_row(k, str(v), style=style)
                    live.update(table)
                except Exception as e:
                    live.update(f"[red]Read error: {e}[/red]")
                time.sleep(cfg.plc.poll_interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        console.print("\n[dim]Stopped.[/dim]")


# ── up ────────────────────────────────────────────────────────────────────

@app.command()
def up(
    config_path: str = typer.Option(None, "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start full pipeline: collector -> DB -> API -> Discord -> monitor."""
    _setup_logging(verbose)
    cfg = _load(config_path)

    console.print("[bold green]FactoryLM starting...[/bold green]")
    console.print(f"  PLC: {cfg.plc.type} @ {cfg.plc.host}:{cfg.plc.port}")
    console.print(f"  API: http://{cfg.api.host}:{cfg.api.port}")
    console.print(f"  Discord: {'configured' if cfg.discord.token else 'not configured'}")
    console.print(f"  Monitor: {'enabled' if cfg.monitor.enabled else 'disabled'}")
    console.print("")

    from factorylm.runner import run_all

    try:
        asyncio.run(run_all(cfg))
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


# ── down ──────────────────────────────────────────────────────────────────

@app.command()
def down() -> None:
    """Graceful shutdown (sends SIGTERM to running factorylm processes)."""
    import subprocess

    result = subprocess.run(
        ["pkill", "-f", "factorylm.cli"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print("[green]FactoryLM processes stopped.[/green]")
    else:
        console.print("[yellow]No running FactoryLM processes found.[/yellow]")


# ── status ────────────────────────────────────────────────────────────────

@app.command()
def status(
    config_path: str = typer.Option(None, "--config", "-c"),
) -> None:
    """Dashboard showing all subsystem status."""
    cfg = _load(config_path)

    from factorylm.db.store import TagStore

    store = TagStore(db_path=cfg.db.path)
    latest = store.get_latest(1)
    incidents = store.get_incidents(status="open", limit=5)

    table = Table(title="FactoryLM Status")
    table.add_column("Subsystem", style="cyan")
    table.add_column("Status", style="green")

    config_status = "[green]loaded[/green]" if CONFIG_FILE.exists() else "[red]missing[/red]"
    table.add_row("Config", config_status)
    table.add_row("PLC", f"{cfg.plc.type} @ {cfg.plc.host}:{cfg.plc.port}")
    table.add_row("Database", f"{store.db_path} ({len(latest)} latest)")
    table.add_row("Open Incidents", str(len(incidents)))
    table.add_row("API", f"http://{cfg.api.host}:{cfg.api.port}")
    table.add_row("Discord", "configured" if cfg.discord.token else "[dim]not configured[/dim]")
    agent_count = sum(1 for v in cfg.discord.agent_webhooks.values() if v)
    relay_status = f"{agent_count} agents" if agent_count else "[dim]none[/dim]"
    alerts_status = "[green]on[/green]" if cfg.discord.alerts_webhook else "[dim]off[/dim]"
    table.add_row("Agent Relay", f"{relay_status} | alerts: {alerts_status}")
    table.add_row("Monitor", "enabled" if cfg.monitor.enabled else "[dim]disabled[/dim]")
    table.add_row("Cosmos", "key set" if cfg.cosmos.api_key else "[dim]no key[/dim]")

    console.print(table)


# ── serve ─────────────────────────────────────────────────────────────────

@app.command()
def serve(
    config_path: str = typer.Option(None, "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start web dashboard only."""
    _setup_logging(verbose)
    cfg = _load(config_path)

    console.print(f"Starting API server on http://{cfg.api.host}:{cfg.api.port}")

    from factorylm.api.server import run_server
    from factorylm.db.store import TagStore

    store = TagStore(db_path=cfg.db.path)
    run_server(store, host=cfg.api.host, port=cfg.api.port)


# ── discord ───────────────────────────────────────────────────────────────

@app.command(name="discord")
def discord_cmd(
    config_path: str = typer.Option(None, "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start Discord bot only."""
    _setup_logging(verbose)
    cfg = _load(config_path)

    if not cfg.discord.token:
        console.print("[red]No Discord token configured. Set DISCORD_BOT_TOKEN or run `factorylm init`.[/red]")
        raise typer.Exit(1)

    try:
        from factorylm.discord.bot import FactoryLMBot
    except ImportError:
        console.print("[red]discord.py not installed. Run: pip install 'factorylm[discord]'[/red]")
        raise typer.Exit(1)

    from factorylm.db.store import TagStore

    store = TagStore(db_path=cfg.db.path)

    # Create relay if any webhooks are configured
    relay = None
    try:
        from factorylm.discord.relay import AgentRelay
        webhooks = cfg.discord.agent_webhooks
        if webhooks or cfg.discord.alerts_webhook or cfg.discord.dispatch_webhook:
            relay = AgentRelay(
                agent_webhooks=webhooks,
                alerts_webhook=cfg.discord.alerts_webhook,
                dispatch_webhook=cfg.discord.dispatch_webhook,
            )
            agent_count = len(relay.configured_agents)
            console.print(f"  Agent relay: {agent_count} agents configured")
    except ImportError:
        pass

    bot = FactoryLMBot(
        token=cfg.discord.token,
        store=store,
        bot_name=cfg.discord.bot_name,
        mention_only=cfg.discord.mention_only,
        live_channel_id=cfg.discord.live_channel_id,
        live_interval=cfg.discord.live_interval,
        relay=relay,
    )
    if cfg.discord.live_channel_id:
        console.print(f"  Live feed: channel {cfg.discord.live_channel_id} (every {cfg.discord.live_interval}s)")
    console.print(f"Starting Discord bot as '{cfg.discord.bot_name}'...")
    bot.run()


# ── collect ───────────────────────────────────────────────────────────────

@app.command()
def collect(
    config_path: str = typer.Option(None, "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start tag collector only (PLC -> SQLite)."""
    _setup_logging(verbose)
    cfg = _load(config_path)

    console.print(f"Starting collector: {cfg.plc.type} @ {cfg.plc.host}:{cfg.plc.port} -> SQLite")

    from factorylm.runner import collect_loop
    from factorylm.db.store import TagStore

    store = TagStore(db_path=cfg.db.path)
    try:
        asyncio.run(collect_loop(cfg, store))
    except KeyboardInterrupt:
        console.print("\n[dim]Collector stopped.[/dim]")


# ── relay ─────────────────────────────────────────────────────────────────

@app.command()
def relay(
    agent: str = typer.Argument(..., help="Agent name (tony, ultron, jarvis, hetzner)"),
    message: str = typer.Argument(..., help="Message to send"),
    config_path: str = typer.Option(None, "--config", "-c"),
) -> None:
    """Test relay — send a message to an agent's Discord channel via webhook."""
    cfg = _load(config_path)

    try:
        from factorylm.discord.relay import AgentRelay, RelayMessage
    except ImportError:
        console.print("[red]discord.py not installed. Run: pip install 'factorylm[discord]'[/red]")
        raise typer.Exit(1)

    webhooks = cfg.discord.agent_webhooks
    r = AgentRelay(
        agent_webhooks=webhooks,
        alerts_webhook=cfg.discord.alerts_webhook,
        dispatch_webhook=cfg.discord.dispatch_webhook,
    )

    if agent not in webhooks or not webhooks[agent]:
        console.print(f"[red]No webhook configured for agent '{agent}'.[/red]")
        configured = [k for k, v in webhooks.items() if v]
        if configured:
            console.print(f"Configured agents: {', '.join(configured)}")
        raise typer.Exit(1)

    async def _send():
        try:
            msg = RelayMessage(agent=agent, content=message)
            ok = await r.post(msg)
            if ok:
                console.print(f"[green]Message sent to #{agent}[/green]")
            else:
                console.print(f"[red]Failed to send message to #{agent}[/red]")
        finally:
            await r.close()

    asyncio.run(_send())


# ── version ───────────────────────────────────────────────────────────────

@app.command()
def version() -> None:
    """Show version."""
    console.print(f"factorylm {factorylm.__version__}")


# ── Main entry ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
