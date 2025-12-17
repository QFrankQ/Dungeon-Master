"""
Admin Commands Cog

Handles guild-level API key management (strict BYOK):
- /guild-key - Set guild-wide API key (admin only)
- /guild-key-status - Check if guild has a key registered (admin only)
- /remove-guild-key - Remove guild's API key (admin only)
"""

import discord
from discord import app_commands
from discord.ext import commands

from src.persistence.database import get_session
from src.persistence.repositories.api_key_repo import APIKeyRepository
from src.discord.utils.session_pool import get_session_pool


class AdminCommands(commands.Cog):
    """Commands for guild-level API key management (strict BYOK)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session_pool = get_session_pool()

    @app_commands.command(name="guild-key", description="Set server-wide API key (Admin only)")
    @app_commands.describe(
        api_key="Gemini API key for the entire server"
    )
    @app_commands.default_permissions(administrator=True)
    async def guild_key(
        self,
        interaction: discord.Interaction,
        api_key: str
    ):
        """Set guild-wide API key (admin only)."""
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild_id

        try:
            async with get_session() as db_session:
                api_key_repo = APIKeyRepository(db_session)
                await api_key_repo.set_guild_key(guild_id, api_key)
                await db_session.commit()

            await interaction.followup.send(
                f"✅ **Server API Key Set!**\n\n"
                f"• **Scope**: All users in this server\n"
                f"• **Security**: Encrypted in database\n\n"
                f"All users can now play D&D games using this key.\n"
                f"Use `/remove-guild-key` to remove it or `/guild-key` again to update it.",
                ephemeral=True
            )

        except ValueError as e:
            await interaction.followup.send(
                f"❌ **Failed to set key**: {str(e)}\n\n"
                f"Make sure the bot owner has configured an encryption key.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ **Error**: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="guild-key-status", description="Check if server has an API key (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def guild_key_status(self, interaction: discord.Interaction):
        """Check if guild has a registered API key (admin only)."""
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild_id

        try:
            async with get_session() as db_session:
                api_key_repo = APIKeyRepository(db_session)
                guild_key = await api_key_repo.get_guild_key(guild_id)

            if guild_key:
                await interaction.followup.send(
                    "✅ **Server has an API key registered**\n\n"
                    "All users in this server can play D&D games.\n"
                    "Use `/remove-guild-key` to remove it or `/guild-key` to update it.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "⚠️ **No API key registered**\n\n"
                    "This server needs an API key before users can play.\n"
                    "Use `/guild-key` to register a Gemini API key.\n\n"
                    "Get your free key at: https://makersuite.google.com/app/apikey",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ **Error**: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="remove-guild-key", description="Remove server's API key (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def remove_guild_key(self, interaction: discord.Interaction):
        """Remove guild's API key (admin only)."""
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild_id

        try:
            async with get_session() as db_session:
                api_key_repo = APIKeyRepository(db_session)
                deleted = await api_key_repo.delete_guild_key(guild_id)
                await db_session.commit()

            if deleted:
                # End all active sessions for this guild
                ended_sessions = await self.session_pool.end_all_guild_sessions(guild_id)

                response_msg = "✅ **Server API Key Removed**\n\n"
                response_msg += "The server's API key has been deleted from the database.\n"

                if ended_sessions > 0:
                    response_msg += f"\n🛑 **{ended_sessions} active session(s) were automatically ended**\n"
                    response_msg += "Players in those channels will need to start new sessions with a new API key.\n"

                response_msg += "\nUsers will no longer be able to start games until a new key is registered."

                await interaction.followup.send(response_msg, ephemeral=True)
            else:
                await interaction.followup.send(
                    "ℹ️ **No key to remove**\n\n"
                    "This server doesn't have an API key registered.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ **Error**: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Add this cog to the bot."""
    await bot.add_cog(AdminCommands(bot))
