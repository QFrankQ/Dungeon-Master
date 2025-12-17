"""
Session Commands Cog

Handles game session management: /start and /end commands,
plus the on_message handler for player actions during active sessions.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from src.discord.utils.session_pool import get_session_pool
from src.discord.utils.message_converter import discord_to_chat_message


class SessionCommands(commands.Cog):
    """Commands for managing D&D game sessions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session_pool = get_session_pool()

    @app_commands.command(name="start", description="Start a D&D game session in this channel")
    async def start_session(self, interaction: discord.Interaction):
        """Start a new game session in the current channel."""
        channel_id = interaction.channel_id
        guild_id = interaction.guild_id
        guild_name = interaction.guild.name if interaction.guild else "Unknown Guild"

        # Check if session already exists
        if self.session_pool.get(channel_id):
            await interaction.response.send_message(
                "⚠️ A game session is already active in this channel. Use `/end` to end it first.",
                ephemeral=True
            )
            return

        # Defer response (session creation may take a moment)
        await interaction.response.defer()

        try:
            # Create new session with database persistence + BYOK (Phase 2 + Phase 3)
            await self.session_pool.create_session(channel_id, guild_id, guild_name)

            await interaction.followup.send(
                "🎲 **D&D Game Session Started!**\n\n"
                "Welcome, adventurers! Your journey begins...\n\n"
                "**How to Play:**\n"
                "• Just type messages to interact with the DM\n"
                "• Use `/character` to view your character\n"
                "• Use `/register` to register or switch characters\n"
                "• Use `/help` for more commands\n"
                "• Use `/end` to end the session\n\n"
                "May the dice roll in your favor! 🎲"
            )

        except ValueError as e:
            # Phase 3: Specific handling for missing API key (strict BYOK)
            error_msg = str(e)
            if "API key" in error_msg:
                await interaction.followup.send(
                    f"⚠️ **{error_msg}**\n\n"
                    f"**To register an API key:**\n"
                    f"1. Get a Gemini API key at https://makersuite.google.com/app/apikey\n"
                    f"2. Use `/guild-key` to register it (admin only)\n\n"
                    f"**Note:** Both free and paid tier keys work. Free tier provides 15 requests/min.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to start session: {error_msg}",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to start session: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="end", description="End the current D&D game session")
    async def end_session(self, interaction: discord.Interaction):
        """End the game session in the current channel."""
        channel_id = interaction.channel_id

        # Check if session exists
        if not self.session_pool.get(channel_id):
            await interaction.response.send_message(
                "⚠️ No active game session in this channel.",
                ephemeral=True
            )
            return

        # End session
        await self.session_pool.end_session(channel_id)

        await interaction.response.send_message(
            "👋 **Game Session Ended**\n\n"
            "Thank you for playing! Your adventure has concluded.\n"
            "Use `/start` to begin a new session anytime."
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Handle player messages during active sessions.

        This is the core integration point - processes player actions
        through the SessionManager and sends DM responses.
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Check if message is in an active session channel
        session_context = self.session_pool.get(message.channel.id)
        if not session_context:
            return  # No active session in this channel

        # Ignore slash commands (they're handled by command handlers)
        if message.content.startswith('/'):
            return

        try:
            # Show typing indicator while processing
            async with message.channel.typing():
                # Get player's active character
                # For Phase 1, we'll use the character name from the player registry
                player_id = str(message.author.id)
                session_manager = session_context.session_manager

                # Get character for this player
                character_id = session_manager.player_character_registry.get_character_id_by_player_id(player_id)

                if not character_id:
                    # Player hasn't registered a character yet
                    await message.channel.send(
                        f"{message.author.mention} ⚠️ You haven't registered a character yet! "
                        f"Use `/register <character_id>` to register.\n"
                        f"Available characters: fighter, wizard, cleric"
                    )
                    return

                # Load character to get name
                character = session_manager.state_manager.get_character(character_id)
                character_name = character.info.name if character else character_id

                # Convert Discord message to ChatMessage format
                chat_message = discord_to_chat_message(message, character_name)

                # Process through SessionManager (mirrors demo_terminal.py:184-186)
                result = await session_manager.demo_process_player_input(
                    new_messages=[chat_message]
                )

                # Send DM responses (mirrors demo_terminal.py:201-202)
                for response_text in result["responses"]:
                    # Format response with DM prefix
                    formatted_response = f"**DM:** {response_text}"

                    # Split if too long (Discord has 2000 char limit)
                    if len(formatted_response) > 2000:
                        # Split into chunks
                        chunks = [formatted_response[i:i+1900] for i in range(0, len(formatted_response), 1900)]
                        for chunk in chunks:
                            await message.channel.send(chunk)
                    else:
                        await message.channel.send(formatted_response)

                # Display state change notification if any (mirrors demo_terminal.py:205-209)
                if result.get("state_results") and result["state_results"].get("success"):
                    state_info = result["state_results"]
                    if state_info.get("commands_executed", 0) > 0:
                        await message.channel.send(
                            f"💫 {state_info['commands_executed']} state changes applied\n"
                            f"Type `/character` to see updated character status"
                        )

        except Exception as e:
            await message.channel.send(
                f"❌ Error processing message: {str(e)}\n"
                f"Please try again or use `/end` to restart the session."
            )
            print(f"Error in on_message: {e}")
            import traceback
            traceback.print_exc()


async def setup(bot: commands.Bot):
    """Add this cog to the bot."""
    await bot.add_cog(SessionCommands(bot))
