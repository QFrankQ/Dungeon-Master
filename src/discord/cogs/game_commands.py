"""
Game Commands Cog

Handles game information commands: /turn, /history, /stats, /context, /usage, /help
"""

import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path

from src.discord.utils.session_pool import get_session_pool


class GameCommands(commands.Cog):
    """Commands for viewing game state and information."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session_pool = get_session_pool()

    def _get_session_or_error(self, interaction: discord.Interaction):
        """Helper to get session or return error message."""
        session_context = self.session_pool.get(interaction.channel_id)
        if not session_context:
            return None, "⚠️ No active game session in this channel. Use `/start` to begin."
        return session_context, None

    @app_commands.command(name="turn", description="Show current turn information")
    async def show_turn(self, interaction: discord.Interaction):
        """Show current turn info (mirrors demo_terminal.py:269-287)."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        turn_manager = session_context.session_manager.turn_manager

        if not turn_manager.is_in_turn():
            await interaction.response.send_message(
                "📭 No active turn",
                ephemeral=True
            )
            return

        current_turn = turn_manager.get_current_turn_context()

        # Build turn info message
        turn_info = (
            f"**📋 Current Turn Info**\n\n"
            f"**Turn ID:** {current_turn.turn_id}\n"
            f"**Turn Level:** {current_turn.turn_level}\n"
            f"**Active Character:** {current_turn.active_character}\n"
            f"**Step Objective:** {current_turn.current_step_objective}\n"
            f"**Message Count:** {len(current_turn.messages)}\n"
        )

        # Show recent messages
        if current_turn.messages:
            turn_info += f"\n**Recent messages:**\n"
            for msg in current_turn.messages[-3:]:
                content_preview = msg.content[:60] + "..." if len(msg.content) > 60 else msg.content
                turn_info += f"• [{msg.speaker}]: {content_preview}\n"

        await interaction.response.send_message(turn_info)

    @app_commands.command(name="history", description="Show completed turns history")
    async def show_history(self, interaction: discord.Interaction):
        """Show completed turns (mirrors demo_terminal.py:289-302)."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        turn_manager = session_context.session_manager.turn_manager
        completed = turn_manager.completed_turns

        if not completed:
            await interaction.response.send_message(
                "📭 No completed turns yet",
                ephemeral=True
            )
            return

        history_text = f"**📜 Completed Turns ({len(completed)})**\n\n"

        for turn in completed[-5:]:  # Show last 5
            duration = (turn.end_time - turn.start_time).total_seconds() if turn.end_time and turn.start_time else 0
            summary = turn.get_turn_summary()[:100] + "..." if len(turn.get_turn_summary()) > 100 else turn.get_turn_summary()
            history_text += (
                f"**Turn {turn.turn_id}** ({turn.active_character}):\n"
                f"• Duration: {duration:.1f}s\n"
                f"• Messages: {len(turn.messages)}\n"
                f"• Summary: {summary}\n\n"
            )

        await interaction.response.send_message(history_text)

    @app_commands.command(name="stats", description="Show turn manager statistics")
    async def show_stats(self, interaction: discord.Interaction):
        """Show turn manager stats (mirrors demo_terminal.py:304-321)."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        turn_manager = session_context.session_manager.turn_manager
        stats = turn_manager.get_turn_stats()

        stats_text = (
            f"**📊 Turn Manager Statistics**\n\n"
            f"**Active Turns:** {stats['active_turns']}\n"
            f"**Current Turn Level:** {stats['current_turn_level']}\n"
            f"**Completed Turns:** {stats['completed_turns']}\n"
            f"**Total Turns Started:** {stats['total_turns_started']}\n"
            f"**Current Turn ID:** {stats['current_turn_id']}\n"
            f"**Turn Stack Depth:** {stats['turn_stack_depth']}\n"
        )

        # Show turn stack summary
        stack_summary = turn_manager.get_turn_stack_summary()
        if stack_summary:
            stats_text += f"\n**Turn Stack:**\n"
            for summary in stack_summary:
                stats_text += f"• {summary}\n"

        await interaction.response.send_message(stats_text)

    @app_commands.command(name="context", description="Show DM context (for debugging)")
    async def show_context(self, interaction: discord.Interaction):
        """Show DM context (mirrors demo_terminal.py:238-372)."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        # Defer response as this may take a moment
        await interaction.response.defer(ephemeral=True)

        turn_manager = session_context.session_manager.turn_manager
        dm_context_builder = session_context.session_manager.dm_context_builder

        # Get turn manager snapshot
        turn_manager_snapshot = turn_manager.get_snapshot()

        # Build context using the demo context builder
        context = dm_context_builder.build_demo_context(
            turn_manager_snapshots=turn_manager_snapshot
        )

        # Estimate token counts (rough approximation: 1 token ≈ 4 chars)
        context_tokens = len(context) // 4

        # Read system prompt and estimate its tokens
        try:
            prompt_path = Path("src/prompts/dungeon_master_system_prompt.txt")
            with open(prompt_path, 'r') as f:
                system_prompt = f.read()
            system_prompt_tokens = len(system_prompt) // 4
            total_tokens = context_tokens + system_prompt_tokens
        except:
            system_prompt_tokens = 0
            total_tokens = context_tokens

        # Format context for Discord (truncate if too long)
        context_preview = context[:1800] + "\n...(truncated)" if len(context) > 1800 else context

        context_msg = (
            f"**🔍 DM Context (Debug View)**\n\n"
            f"```\n{context_preview}\n```\n\n"
            f"**Token Estimates:**\n"
            f"• Context: ~{context_tokens:,} tokens ({len(context):,} chars)\n"
        )

        if system_prompt_tokens:
            context_msg += (
                f"• System Prompt: ~{system_prompt_tokens:,} tokens\n"
                f"• **Total: ~{total_tokens:,} tokens**"
            )

        await interaction.followup.send(context_msg, ephemeral=True)

    @app_commands.command(name="usage", description="Show token usage statistics")
    async def show_usage(self, interaction: discord.Interaction):
        """Show token usage stats."""
        await interaction.response.send_message(
            "📊 **Token Usage Statistics**\n\n"
            "Token tracking will be implemented in a future update.\n"
            "For now, check your Gemini API dashboard for usage.",
            ephemeral=True
        )

    @app_commands.command(name="help", description="Show available commands and how to play")
    async def show_help(self, interaction: discord.Interaction):
        """Show help information."""
        help_text = (
            "🎲 **D&D Dungeon Master Bot - Command Guide**\n\n"
            "**Session Management:**\n"
            "• `/start` - Start a new game session in this channel\n"
            "• `/end` - End the current session\n\n"
            "**Character Management:**\n"
            "• `/register <character_id>` - Register/switch character\n"
            "• `/character` - View your character's stats and status\n"
            "• `/switch <character_id>` - Switch to a different character\n"
            "• `/who` - Show all available characters\n"
            "• `/upload-character` - Upload your own custom character JSON file\n\n"
            "**Game Information:**\n"
            "• `/turn` - Show current turn information\n"
            "• `/history` - Show completed turns\n"
            "• `/stats` - Show turn manager statistics\n"
            "• `/context` - View DM context (debug)\n"
            "• `/usage` - Show token usage\n"
            "• `/help` - Show this help message\n\n"
            "**How to Play:**\n"
            "1. Start a session with `/start`\n"
            "2. Register a character with `/register <character_id>` or upload your own\n"
            "3. Just type messages to interact with the DM!\n"
            "4. The DM will respond to your actions and roll dice as needed\n\n"
            "Have fun adventuring! 🗡️🛡️"
        )
        await interaction.response.send_message(help_text, ephemeral=True)


async def setup(bot: commands.Bot):
    """Add this cog to the bot."""
    await bot.add_cog(GameCommands(bot))
