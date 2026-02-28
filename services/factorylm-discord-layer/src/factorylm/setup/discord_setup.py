"""Discord server setup — channel and webhook provisioning.

Creates categories, channels, and webhooks for the FactoryLM agent swarm.
Idempotent — skips resources that already exist.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import aiohttp

logger = logging.getLogger(__name__)

DISCORD_API = "https://discord.com/api/v10"

# Channel layout spec
CATEGORIES = {
    "FACTORY FLOOR": ["plc-live", "alerts"],
    "AGENTS": ["tony", "ultron", "jarvis", "hetzner", "dispatch-log"],
}


@dataclass
class SetupResult:
    """Collects IDs and webhook URLs created during setup."""

    guild_id: int
    categories: dict[str, int] = field(default_factory=dict)
    channels: dict[str, int] = field(default_factory=dict)
    webhooks: dict[str, str] = field(default_factory=dict)


class DiscordSetup:
    """Provisions Discord categories, channels, and webhooks via REST API."""

    def __init__(self, bot_token: str, guild_id: int) -> None:
        self.bot_token = bot_token
        self.guild_id = guild_id
        self._session: aiohttp.ClientSession | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def _api_get(self, path: str) -> list | dict:
        session = await self._get_session()
        async with session.get(f"{DISCORD_API}{path}") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _api_post(self, path: str, json: dict) -> dict:
        session = await self._get_session()
        async with session.post(f"{DISCORD_API}{path}", json=json) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _get_existing_channels(self) -> list[dict]:
        return await self._api_get(f"/guilds/{self.guild_id}/channels")

    async def _get_existing_webhooks(self, channel_id: int) -> list[dict]:
        return await self._api_get(f"/channels/{channel_id}/webhooks")

    async def create_categories(self, existing: list[dict]) -> dict[str, int]:
        """Create category channels, skipping those that already exist."""
        categories: dict[str, int] = {}
        existing_names = {
            ch["name"]: ch["id"]
            for ch in existing
            if ch["type"] == 4  # GUILD_CATEGORY
        }

        for name in CATEGORIES:
            if name in existing_names:
                logger.info("Category '%s' already exists (id=%s)", name, existing_names[name])
                categories[name] = existing_names[name]
            else:
                data = await self._api_post(
                    f"/guilds/{self.guild_id}/channels",
                    {"name": name, "type": 4},
                )
                categories[name] = data["id"]
                logger.info("Created category '%s' (id=%s)", name, data["id"])

        return categories

    async def create_channels(
        self, categories: dict[str, int], existing: list[dict]
    ) -> dict[str, int]:
        """Create text channels under their categories, skipping existing."""
        channels: dict[str, int] = {}
        existing_names = {
            ch["name"]: ch["id"]
            for ch in existing
            if ch["type"] == 0  # GUILD_TEXT
        }

        for category_name, channel_names in CATEGORIES.items():
            parent_id = categories.get(category_name)
            for ch_name in channel_names:
                if ch_name in existing_names:
                    logger.info(
                        "Channel '#%s' already exists (id=%s)", ch_name, existing_names[ch_name]
                    )
                    channels[ch_name] = existing_names[ch_name]
                else:
                    payload: dict = {"name": ch_name, "type": 0}
                    if parent_id:
                        payload["parent_id"] = parent_id
                    data = await self._api_post(
                        f"/guilds/{self.guild_id}/channels",
                        payload,
                    )
                    channels[ch_name] = data["id"]
                    logger.info("Created channel '#%s' (id=%s)", ch_name, data["id"])

        return channels

    async def create_webhooks(self, channels: dict[str, int]) -> dict[str, str]:
        """Create one webhook per channel, skipping channels that already have one."""
        webhooks: dict[str, str] = {}

        for ch_name, ch_id in channels.items():
            existing = await self._get_existing_webhooks(ch_id)
            factorylm_hooks = [w for w in existing if w.get("name") == "FactoryLM"]
            if factorylm_hooks:
                url = _webhook_url(factorylm_hooks[0])
                logger.info("Webhook for '#%s' already exists", ch_name)
                webhooks[ch_name] = url
            else:
                data = await self._api_post(
                    f"/channels/{ch_id}/webhooks",
                    {"name": "FactoryLM"},
                )
                webhooks[ch_name] = _webhook_url(data)
                logger.info("Created webhook for '#%s'", ch_name)

        return webhooks

    async def run_setup(self) -> SetupResult:
        """Run full setup: categories → channels → webhooks. Idempotent."""
        existing = await self._get_existing_channels()
        categories = await self.create_categories(existing)
        channels = await self.create_channels(categories, existing)
        webhooks = await self.create_webhooks(channels)

        return SetupResult(
            guild_id=self.guild_id,
            categories=categories,
            channels=channels,
            webhooks=webhooks,
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


def _webhook_url(webhook_data: dict) -> str:
    """Build full webhook URL from API response."""
    wid = webhook_data["id"]
    token = webhook_data["token"]
    return f"https://discord.com/api/webhooks/{wid}/{token}"


def cli_main() -> None:
    """Entry point for factorylm-setup command.

    Flags:
        --instance <name>  Instance key (e.g. "ultron"). Enables merge mode.
        --merge            Merge into existing config instead of overwriting.
        --bot-token-env <var>  Env var name for this instance's bot token.
    """
    import argparse
    import os
    import sys

    parser = argparse.ArgumentParser(description="Set up Discord server for FactoryLM")
    parser.add_argument("--instance", type=str, default="", help="Instance name (enables merge)")
    parser.add_argument("--merge", action="store_true", help="Merge into existing config.toml")
    parser.add_argument(
        "--bot-token-env", type=str, default="DISCORD_BOT_TOKEN",
        help="Env var name for bot token (default: DISCORD_BOT_TOKEN)",
    )
    args = parser.parse_args()

    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    guild_id_str = os.environ.get("DISCORD_GUILD_ID", "")

    if not token:
        print("Error: DISCORD_BOT_TOKEN not set")
        sys.exit(1)
    if not guild_id_str:
        print("Error: DISCORD_GUILD_ID not set")
        sys.exit(1)

    from factorylm.setup.config_writer import write_config, write_instance_config

    use_merge = args.merge or bool(args.instance)

    async def _run() -> None:
        setup = DiscordSetup(token, int(guild_id_str))
        try:
            result = await setup.run_setup()
            if use_merge and args.instance:
                output_path = write_instance_config(
                    result,
                    instance_name=args.instance,
                    bot_token_env_var=args.bot_token_env,
                )
                print(f"Setup complete. Instance '{args.instance}' merged into {output_path}")
            else:
                output_path = write_config(result)
                print(f"Setup complete. Config written to {output_path}")
        finally:
            await setup.close()

    asyncio.run(_run())
