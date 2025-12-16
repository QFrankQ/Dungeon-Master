"""
D&D Dungeon Master Discord Bot

Main entry point for the Discord bot that integrates the DM AI
with Discord servers for multiplayer D&D sessions.
"""

import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()


def create_bot() -> commands.Bot:
    """
    Create and configure the Discord bot.

    Returns:
        Configured Discord bot instance
    """
    # Configure intents (required for message content and guild access)
    intents = discord.Intents.default()
    intents.message_content = True  # Required to read message content
    intents.guilds = True  # Required for guild information
    intents.members = False  # Not needed for now

    # Create bot instance
    bot = commands.Bot(
        command_prefix="/",  # Slash commands will be primary interface
        intents=intents,
        description="D&D Dungeon Master AI - Your personal DM for Discord"
    )

    @bot.event
    async def on_ready():
        """Called when the bot successfully connects to Discord."""
        print(f"✓ Bot connected as {bot.user} (ID: {bot.user.id})")
        print(f"✓ Connected to {len(bot.guilds)} guild(s)")
        print("✓ D&D Dungeon Master Bot is ready!")

        # Sync slash commands with Discord
        try:
            synced = await bot.tree.sync()
            print(f"✓ Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"✗ Failed to sync commands: {e}")

    @bot.event
    async def on_guild_join(guild: discord.Guild):
        """Called when the bot joins a new guild."""
        print(f"✓ Joined new guild: {guild.name} (ID: {guild.id})")

    @bot.event
    async def on_guild_remove(guild: discord.Guild):
        """Called when the bot is removed from a guild."""
        print(f"✗ Removed from guild: {guild.name} (ID: {guild.id})")

    return bot


async def load_cogs(bot: commands.Bot):
    """
    Load all command cogs.

    Args:
        bot: The Discord bot instance
    """
    cogs = [
        "src.discord.cogs.session_commands",
        "src.discord.cogs.game_commands",
        "src.discord.cogs.character_commands",
        # admin_commands will be added later for BYOK
    ]

    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✓ Loaded cog: {cog}")
        except Exception as e:
            print(f"✗ Failed to load cog {cog}: {e}")


async def main():
    """Main entry point for the bot."""
    # Get Discord token from environment
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("✗ Error: DISCORD_BOT_TOKEN not found in environment variables")
        print("  Please set DISCORD_BOT_TOKEN in your .env file")
        return

    # Create bot
    bot = create_bot()

    # Load cogs
    await load_cogs(bot)

    # Start bot
    try:
        print("Starting Discord bot...")
        await bot.start(token)
    except KeyboardInterrupt:
        print("\n✓ Shutting down gracefully...")
        await bot.close()
    except Exception as e:
        print(f"✗ Error running bot: {e}")
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
