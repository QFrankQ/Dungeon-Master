"""
Game Commands Cog

Handles game information commands: /turn, /history, /stats, /context, /usage, /help, /combat
"""

import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path
from typing import Optional

from src.discord.utils.session_pool import get_session_pool
from src.models.combat_state import CombatPhase


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

    @app_commands.command(name="combat", description="Manage combat mode")
    @app_commands.describe(
        action="Combat action: start, end, status, or toggle (default)",
        force="Force end combat from any phase (use with 'end' action)"
    )
    async def combat(
        self,
        interaction: discord.Interaction,
        action: Optional[str] = None,
        force: Optional[bool] = False
    ):
        """Toggle or manage combat mode for multiplayer coordination."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        coordinator = session_context.message_coordinator
        turn_manager = session_context.session_manager.turn_manager

        if not coordinator:
            await interaction.response.send_message(
                "⚠️ Message coordinator not available.",
                ephemeral=True
            )
            return

        if action is None:
            # Toggle combat mode
            if coordinator.combat_mode:
                coordinator.exit_combat_mode()
                await interaction.response.send_message(
                    "⚔️ **Combat Mode: OFF**\n"
                    "Free exploration - all players can send messages."
                )
            else:
                coordinator.enter_combat_mode()
                await interaction.response.send_message(
                    "⚔️ **Combat Mode: ON**\n"
                    "Strict turn enforcement enabled.\n"
                    "Use `/combat start` to begin a combat encounter."
                )

        elif action.lower() == "start":
            # Start a combat encounter
            if turn_manager.is_in_combat():
                phase = turn_manager.get_combat_phase()
                await interaction.response.send_message(
                    f"⚠️ Already in combat! Phase: {phase.value}\n"
                    f"Use `/combat end` to end current combat first.",
                    ephemeral=True
                )
                return

            # Get all registered characters for this session
            registry = session_context.session_manager.player_character_registry
            player_chars = list(registry._character_by_player.values())

            if not player_chars:
                await interaction.response.send_message(
                    "⚠️ No registered characters! Players must use `/register` first.",
                    ephemeral=True
                )
                return

            # For now, add some placeholder enemies
            # In future, DM narrative or explicit command would specify enemies
            enemies = ["Goblin 1", "Goblin 2"]
            all_participants = player_chars + enemies

            # Enter combat via TurnManager
            turn_manager.enter_combat(all_participants, "Combat Encounter")
            coordinator.enter_combat_mode()

            # Build combat announcement
            player_list = ", ".join(player_chars) if player_chars else "No players"
            enemy_list = ", ".join(enemies) if enemies else "No enemies"

            await interaction.response.send_message(
                "⚔️ **COMBAT INITIATED!**\n\n"
                f"**Players:** {player_list}\n"
                f"**Enemies:** {enemy_list}\n\n"
                "🎲 **Roll for Initiative!**\n"
                "Use `/initiative <roll>` to submit your initiative roll.\n"
                "Example: `/initiative 15`"
            )

        elif action.lower() == "end":
            # End combat
            if not turn_manager.is_in_combat():
                await interaction.response.send_message(
                    "⚠️ Not currently in combat.",
                    ephemeral=True
                )
                return

            current_phase = turn_manager.get_combat_phase()

            # Check if we need force flag for non-COMBAT_END phases
            if current_phase != CombatPhase.COMBAT_END and not force:
                await interaction.response.send_message(
                    f"⚠️ Cannot end combat from phase `{current_phase.value}`.\n\n"
                    f"Combat should naturally progress to the COMBAT_END phase.\n"
                    f"To force end combat immediately, use:\n"
                    f"`/combat end force:True`",
                    ephemeral=True
                )
                return

            # Force end: directly reset combat state without finish_combat()
            if force and current_phase != CombatPhase.COMBAT_END:
                # Capture summary before clearing
                combat_state = turn_manager.combat_state
                summary = {
                    "encounter_name": combat_state.encounter_name,
                    "rounds_fought": combat_state.round_number,
                    "forced": True,
                    "previous_phase": current_phase.value
                }

                # End any active turns
                while turn_manager.turn_stack:
                    level_turns = turn_manager.turn_stack[-1]
                    if level_turns:
                        turn = level_turns[0]
                        from datetime import datetime
                        turn.end_time = datetime.now()
                        turn_manager.completed_turns.append(turn)
                    turn_manager.turn_stack.pop()

                # Reset combat state
                combat_state.finish_combat()

                coordinator.exit_combat_mode()

                await interaction.response.send_message(
                    "⚔️ **Combat FORCE ENDED.**\n\n"
                    f"Previous phase: `{current_phase.value}`\n"
                    f"Rounds fought: {summary['rounds_fought']}\n\n"
                    "⚠️ Combat was ended early - some cleanup may be incomplete.\n"
                    "Returning to exploration mode."
                )
            else:
                # Normal end from COMBAT_END phase
                turn_manager.finish_combat()
                coordinator.exit_combat_mode()

                await interaction.response.send_message(
                    "⚔️ **Combat has ended.**\n\n"
                    "Returning to exploration mode.\n"
                    "All players can now send messages freely."
                )

        elif action.lower() == "status":
            # Show combat status
            phase = turn_manager.get_combat_phase()

            if phase == CombatPhase.NOT_IN_COMBAT:
                mode = "ON (strict)" if coordinator.combat_mode else "OFF (exploration)"
                await interaction.response.send_message(
                    f"⚔️ **Combat Status**\n\n"
                    f"**Mode:** {mode}\n"
                    f"**Combat Phase:** Not in combat\n\n"
                    f"Use `/combat start` to begin an encounter."
                )
            else:
                combat_state = turn_manager.combat_state
                summary = combat_state.get_initiative_summary()

                await interaction.response.send_message(
                    f"⚔️ **Combat Status**\n\n"
                    f"**Phase:** {phase.value}\n"
                    f"**Round:** {combat_state.round_number}\n"
                    f"**Current Participant:** {combat_state.get_current_participant() or 'N/A'}\n\n"
                    f"```\n{summary}\n```"
                )

        else:
            await interaction.response.send_message(
                f"⚠️ Unknown combat action: `{action}`\n"
                f"Valid actions: `start`, `end`, `status`, or omit for toggle.",
                ephemeral=True
            )

    # NOTE: /initiative command is commented out to reduce complexity.
    # Initiative rolls are collected via the InitiativeView modal (system-driven UI)
    # triggered automatically when ResponseType.INITIATIVE is set.
    # This command can be re-enabled later if manual slash command input is desired.
    #
    # @app_commands.command(name="initiative", description="Submit your initiative roll")
    # @app_commands.describe(roll="Your initiative roll result (d20 + modifier)")
    # async def initiative(self, interaction: discord.Interaction, roll: int):
    #     """Submit an initiative roll during combat start phase."""
    #     session_context, error = self._get_session_or_error(interaction)
    #     if error:
    #         await interaction.response.send_message(error, ephemeral=True)
    #         return
    #
    #     turn_manager = session_context.session_manager.turn_manager
    #     coordinator = session_context.message_coordinator
    #
    #     # Verify combat phase
    #     if turn_manager.get_combat_phase() != CombatPhase.COMBAT_START:
    #         await interaction.response.send_message(
    #             "⚠️ Initiative can only be rolled during combat start phase!",
    #             ephemeral=True
    #         )
    #         return
    #
    #     # Get character for this user
    #     player_id = str(interaction.user.id)
    #     registry = session_context.session_manager.player_character_registry
    #     character_id = registry.get_character_id_by_player_id(player_id)
    #
    #     if not character_id:
    #         await interaction.response.send_message(
    #             "⚠️ You need to register a character first! Use `/register`",
    #             ephemeral=True
    #         )
    #         return
    #
    #     # Add the initiative roll
    #     result = turn_manager.add_initiative_roll(
    #         character_name=character_id,
    #         roll=roll,
    #         is_player=True
    #     )
    #
    #     if result.get("error"):
    #         await interaction.response.send_message(
    #             f"⚠️ {result['error']}",
    #             ephemeral=True
    #         )
    #         return
    #
    #     # Acknowledge the roll
    #     await interaction.response.send_message(
    #         f"🎲 **{character_id}** rolled **{roll}** for initiative!\n"
    #         f"({result['collected']}/{result['total_participants']} collected)"
    #     )
    #
    #     # Check if all initiative collected
    #     if result.get("all_collected"):
    #         # Finalize initiative order
    #         finalize_result = turn_manager.finalize_initiative()
    #         order = finalize_result.get("initiative_order", [])
    #
    #         # Build initiative order display
    #         order_text = ""
    #         for i, entry in enumerate(order):
    #             player_marker = "🎮" if entry["is_player"] else "🐉"
    #             order_text += f"{i+1}. {player_marker} **{entry['character_name']}** - {entry['roll']}\n"
    #
    #         first_char = order[0]["character_name"] if order else "Unknown"
    #
    #         await interaction.channel.send(
    #             "📋 **Initiative Order Finalized!**\n\n"
    #             f"{order_text}\n"
    #             f"**{first_char}** goes first!"
    #         )

    @app_commands.command(name="config", description="Configure session settings")
    @app_commands.describe(
        setting="Setting to configure: timeouts",
        value="New value for the setting"
    )
    async def config(
        self,
        interaction: discord.Interaction,
        setting: Optional[str] = None,
        value: Optional[str] = None
    ):
        """Configure session settings like timeouts."""
        session_context, error = self._get_session_or_error(interaction)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        timeouts = session_context.timeouts

        # No setting specified - show current config
        if setting is None:
            config_text = (
                "**Session Configuration**\n\n"
                "**Timeouts (seconds):**\n"
                f"• Initiative: {timeouts.initiative}s\n"
                f"• Saving Throw: {timeouts.saving_throw}s\n"
                f"• Reaction: {timeouts.reaction}s\n"
                f"• Action: {timeouts.action}s\n\n"
                "**To change a timeout:**\n"
                "`/config timeouts initiative=60`\n"
                "`/config timeouts saving_throw=30`\n"
                "`/config timeouts reaction=15`\n"
                "`/config timeouts action=180`"
            )
            await interaction.response.send_message(config_text, ephemeral=True)
            return

        # Handle timeout configuration
        if setting.lower() == "timeouts":
            if not value:
                await interaction.response.send_message(
                    "**Current Timeouts:**\n"
                    f"• initiative={timeouts.initiative}\n"
                    f"• saving_throw={timeouts.saving_throw}\n"
                    f"• reaction={timeouts.reaction}\n"
                    f"• action={timeouts.action}\n\n"
                    "Usage: `/config timeouts <type>=<seconds>`",
                    ephemeral=True
                )
                return

            # Parse value (e.g., "initiative=60" or "reaction=15")
            if "=" not in value:
                await interaction.response.send_message(
                    f"Invalid format. Use: `/config timeouts <type>=<seconds>`\n"
                    f"Example: `/config timeouts initiative=60`",
                    ephemeral=True
                )
                return

            timeout_type, timeout_value = value.split("=", 1)
            timeout_type = timeout_type.strip().lower()

            try:
                new_timeout = float(timeout_value.strip())
                if new_timeout < 5:
                    await interaction.response.send_message(
                        "Timeout must be at least 5 seconds.",
                        ephemeral=True
                    )
                    return
                if new_timeout > 600:
                    await interaction.response.send_message(
                        "Timeout cannot exceed 600 seconds (10 minutes).",
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    f"Invalid timeout value: `{timeout_value}`. Must be a number.",
                    ephemeral=True
                )
                return

            # Update the appropriate timeout
            valid_types = ["initiative", "saving_throw", "reaction", "action"]
            if timeout_type not in valid_types:
                await interaction.response.send_message(
                    f"Invalid timeout type: `{timeout_type}`\n"
                    f"Valid types: {', '.join(valid_types)}",
                    ephemeral=True
                )
                return

            setattr(timeouts, timeout_type, new_timeout)
            await interaction.response.send_message(
                f"Updated **{timeout_type}** timeout to **{new_timeout}s**",
                ephemeral=True
            )

        else:
            await interaction.response.send_message(
                f"Unknown setting: `{setting}`\n"
                f"Available settings: `timeouts`",
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
            "**Combat:**\n"
            "• `/combat` - Toggle combat mode on/off\n"
            "• `/combat start` - Start a combat encounter\n"
            "• `/combat end` - End the current combat (use `force:True` to force end)\n"
            "• `/combat status` - Show combat status and initiative\n\n"
            "**Game Information:**\n"
            "• `/turn` - Show current turn information\n"
            "• `/history` - Show completed turns\n"
            "• `/stats` - Show turn manager statistics\n"
            "• `/context` - View DM context (debug)\n"
            "• `/usage` - Show token usage\n"
            "• `/config` - Configure session settings (timeouts)\n"
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
