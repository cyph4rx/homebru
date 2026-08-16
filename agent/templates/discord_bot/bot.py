from __future__ import annotations

import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands


def load_local_environment() -> None:
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class DiscordBot(commands.Bot):
    async def setup_hook(self) -> None:
        commands_synced = await self.tree.sync()
        print(f"Synced {len(commands_synced)} Discord command(s).")


bot = DiscordBot(command_prefix="!", intents=discord.Intents.default())


@bot.event
async def on_ready() -> None:
    print(f"{{BOT_NAME}} is online as {bot.user}.")


@bot.tree.command(name="ping", description="Check whether the bot is online")
async def ping(interaction: discord.Interaction) -> None:
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! {latency_ms} ms")


@bot.tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(f"Hello, {interaction.user.mention}!")


if __name__ == "__main__":
    load_local_environment()
    discord_token = os.environ.get("DISCORD_TOKEN", "")
    if not discord_token or discord_token == "paste-your-discord-token-here":
        raise SystemExit("Add your Discord bot token to the .env file before starting the bot.")
    bot.run(discord_token, log_handler=None)
