"""
Session Commands Cog

Handles game session management: /start and /end commands,
plus the on_message handler for player actions during active sessions.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List

from src.discord.utils.session_pool import get_session_pool, SessionContext
from src.discord.utils.message_converter import discord_to_chat_message
from src.memory.message_coordinator import MessageValidationResult
from src.memory.response_collector import AddResult
from src.models.response_expectation import ResponseExpectation, ResponseType
from src.discord.views.reaction_view import ReactionView
from src.discord.views.initiative_modal import InitiativeView
from src.discord.views.save_modal import SaveView, parse_save_from_prompt


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

        # Verify guild still has a valid API key (safety check)
        from src.services.byok_service import get_api_key_for_guild
        guild_api_key = await get_api_key_for_guild(session_context.guild_id)
        if not guild_api_key:
            # API key was removed - end this session
            await self.session_pool.end_session(message.channel.id)
            await message.channel.send(
                "⚠️ **Session Ended - API Key Removed**\n\n"
                "The server's API key was removed by an admin.\n"
                "This session has been automatically ended.\n\n"
                "To play again, an admin must register a new API key with `/guild-key`."
            )
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

                # Milestone 5: Validate responder via MessageCoordinator
                coordinator = session_context.message_coordinator
                if coordinator:
                    validation = coordinator.validate_responder(character_name)
                    if validation.result != MessageValidationResult.VALID:
                        if coordinator.combat_mode:
                            # In combat mode, reject invalid responders with feedback
                            await self._send_validation_feedback(message, validation)
                            return
                        # In exploration mode, let message through (validation passes)

                # Convert Discord message to ChatMessage format
                chat_message = discord_to_chat_message(message, character_name)

                # Milestone 5: Multi-response collection for combat mode
                if coordinator and coordinator.combat_mode:
                    # Add response to collector
                    add_result = coordinator.add_response(character_name, chat_message)

                    if add_result == AddResult.DUPLICATE:
                        await message.reply(
                            "You've already responded! Waiting for others...",
                            delete_after=10
                        )
                        return
                    elif add_result == AddResult.UNEXPECTED:
                        await message.reply(
                            "Your response wasn't expected at this time.",
                            delete_after=10
                        )
                        return

                    # Check if collection is complete
                    if not coordinator.is_collection_complete():
                        # Show progress
                        missing = coordinator.get_missing_responders()
                        collected_count = len(coordinator.get_collected_responses())
                        total_count = collected_count + len(missing)
                        await message.add_reaction("✅")
                        await message.channel.send(
                            f"Got **{character_name}**'s response. "
                            f"({collected_count}/{total_count}) "
                            f"Waiting for: {', '.join(missing)}"
                        )
                        return

                    # Collection complete - gather all messages for batch processing
                    collected_messages = list(coordinator.get_collected_responses().values())
                else:
                    # Exploration mode or no coordinator - single message processing
                    collected_messages = [chat_message]

                # Process through SessionManager
                result = await session_manager.demo_process_player_input(
                    new_messages=collected_messages
                )

                # Milestone 5: Update expectation after DM response and show UI
                if coordinator:
                    awaiting = result.get("awaiting_response")
                    coordinator.set_expectation(awaiting)

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

                # Milestone 5: System-driven UI selection based on ResponseType
                if coordinator and coordinator.combat_mode:
                    awaiting = result.get("awaiting_response")
                    if awaiting:
                        await self._show_response_ui(
                            message.channel,
                            awaiting,
                            session_context
                        )

        except Exception as e:
            await message.channel.send(
                f"❌ Error processing message: {str(e)}\n"
                f"Please try again or use `/end` to restart the session."
            )
            print(f"Error in on_message: {e}")
            import traceback
            traceback.print_exc()

    async def _send_validation_feedback(
        self,
        message: discord.Message,
        validation
    ) -> None:
        """
        Send feedback when a player tries to act out of turn in combat mode.

        Uses reactions and ephemeral-like messages to minimize channel clutter.
        """
        if validation.result == MessageValidationResult.INVALID_NOT_YOUR_TURN:
            # Add hourglass reaction to indicate waiting
            await message.add_reaction("⏳")
            # Send feedback (auto-delete to reduce clutter)
            expected = validation.expected_characters
            if expected:
                await message.reply(
                    f"⏳ It's not your turn! Waiting for: **{', '.join(expected)}**",
                    delete_after=10
                )
            else:
                await message.reply(
                    "⏳ It's not your turn!",
                    delete_after=10
                )

        elif validation.result == MessageValidationResult.INVALID_ALREADY_RESPONDED:
            await message.add_reaction("✅")
            await message.reply(
                "You've already responded. Waiting for others...",
                delete_after=10
            )

        elif validation.result == MessageValidationResult.INVALID_NO_RESPONSE_EXPECTED:
            await message.add_reaction("🤫")
            await message.reply(
                "The DM is narrating - no response expected right now.",
                delete_after=10
            )

    async def _route_view_results_to_dm(
        self,
        channel: discord.TextChannel,
        session_context: SessionContext,
        response_type: str,
        results: dict
    ) -> None:
        """
        Route collected view results to the DM for processing.

        This is the integration point between Discord UI views and the DM agent.
        Collected responses (initiative rolls, saves, reactions) are formatted
        as a system message and sent to the DM for narrative continuation.

        Args:
            channel: Discord channel to send DM response to
            session_context: Current session context
            response_type: Type of response (initiative, save, reaction)
            results: Collected results from the view
        """
        from src.models.chat_message import ChatMessage

        session_manager = session_context.session_manager
        coordinator = session_context.message_coordinator

        # Format results as a system summary message for the DM
        if response_type == "initiative":
            # Format initiative results
            order = results.get("order", [])
            rolls = results.get("rolls", {})
            timed_out = results.get("timed_out", False)

            summary_lines = ["**Initiative Results:**"]
            for i, char in enumerate(order):
                roll_info = rolls.get(char, {})
                roll = roll_info.get("roll", "?")
                source = roll_info.get("source", "")
                flavor = roll_info.get("flavor", "")
                summary_lines.append(f"{i+1}. **{char}**: {roll}")
                if flavor:
                    summary_lines.append(f"   *{flavor}*")

            if timed_out:
                summary_lines.append("\n*Some rolls were auto-generated due to timeout.*")

            summary_text = "\n".join(summary_lines)

        elif response_type == "save":
            # Format saving throw results
            rolls = results.get("rolls", {})
            successes = results.get("successes", [])
            failures = results.get("failures", [])
            save_type = results.get("save_type", "?")
            dc = results.get("dc")
            timed_out = results.get("timed_out", False)

            summary_lines = [f"**{save_type} Saving Throw Results:**"]
            if dc:
                summary_lines[0] += f" (DC {dc})"

            for char, info in rolls.items():
                roll = info.get("roll", "?")
                success = info.get("success")
                result_text = ""
                if success is True:
                    result_text = " ✅ SUCCESS"
                elif success is False:
                    result_text = " ❌ FAILURE"
                summary_lines.append(f"• **{char}**: {roll}{result_text}")

            if successes:
                summary_lines.append(f"\n**Successes:** {', '.join(successes)}")
            if failures:
                summary_lines.append(f"**Failures:** {', '.join(failures)}")

            if timed_out:
                summary_lines.append("\n*Some rolls were auto-generated due to timeout.*")

            summary_text = "\n".join(summary_lines)

        elif response_type == "reaction":
            # Format reaction results
            passed = results.get("passed", [])
            reactions = results.get("reactions", {})
            timed_out = results.get("timed_out", False)

            summary_lines = ["**Reaction Window Results:**"]

            if reactions:
                for char, info in reactions.items():
                    summary_lines.append(f"• **{char}** wants to use a reaction!")

            if passed:
                summary_lines.append(f"• Passed: {', '.join(passed)}")

            if timed_out:
                summary_lines.append("\n*Window timed out - non-responders treated as passing.*")

            summary_text = "\n".join(summary_lines)

        else:
            summary_text = f"**{response_type} Results:** {results}"

        # Create a system message with the results
        system_message = ChatMessage.create_system_message(
            text=summary_text,
            metadata={"response_type": response_type, "results": results}
        )

        try:
            # Show typing indicator while processing
            async with channel.typing():
                # Process through SessionManager
                result = await session_manager.demo_process_player_input(
                    new_messages=[system_message]
                )

                # Update expectation after DM response
                if coordinator:
                    awaiting = result.get("awaiting_response")
                    coordinator.set_expectation(awaiting)

                # Send DM responses
                for response_text in result["responses"]:
                    formatted_response = f"**DM:** {response_text}"

                    if len(formatted_response) > 2000:
                        chunks = [formatted_response[i:i+1900] for i in range(0, len(formatted_response), 1900)]
                        for chunk in chunks:
                            await channel.send(chunk)
                    else:
                        await channel.send(formatted_response)

                # Display state change notification if any
                if result.get("state_results") and result["state_results"].get("success"):
                    state_info = result["state_results"]
                    if state_info.get("commands_executed", 0) > 0:
                        await channel.send(
                            f"💫 {state_info['commands_executed']} state changes applied\n"
                            f"Type `/character` to see updated character status"
                        )

                # Show next UI if needed
                if coordinator and coordinator.combat_mode:
                    awaiting = result.get("awaiting_response")
                    if awaiting:
                        await self._show_response_ui(channel, awaiting, session_context)

        except Exception as e:
            await channel.send(
                f"❌ Error processing {response_type} results: {str(e)}\n"
                f"Please try again or use `/end` to restart the session."
            )
            print(f"Error routing view results to DM: {e}")
            import traceback
            traceback.print_exc()

    async def _show_response_ui(
        self,
        channel: discord.TextChannel,
        expectation: ResponseExpectation,
        session_context: SessionContext
    ) -> None:
        """
        Show appropriate UI based on ResponseType (system-driven UI selection).

        This is a key principle from the multiplayer coordination design:
        The system selects UI based on ResponseType, NOT text parsing.
        """
        if expectation is None:
            return

        # Get helper to resolve user ID -> character name
        registry = session_context.session_manager.player_character_registry

        def get_character_for_user(user_id: int) -> Optional[str]:
            return registry.get_character_id_by_player_id(str(user_id))

        # Get helper to get character stats
        state_manager = session_context.session_manager.state_manager

        def get_dex_modifier(character_name: str) -> int:
            try:
                char = state_manager.get_character(character_name)
                if char and char.abilities:
                    dex = char.abilities.dexterity
                    return (dex - 10) // 2  # D&D modifier formula
            except:
                pass
            return 0

        def get_save_modifier(character_name: str, save_type: str) -> int:
            try:
                char = state_manager.get_character(character_name)
                if char and char.abilities:
                    # Get base ability modifier
                    ability_map = {
                        "STR": char.abilities.strength,
                        "DEX": char.abilities.dexterity,
                        "CON": char.abilities.constitution,
                        "INT": char.abilities.intelligence,
                        "WIS": char.abilities.wisdom,
                        "CHA": char.abilities.charisma,
                    }
                    ability_score = ability_map.get(save_type.upper(), 10)
                    modifier = (ability_score - 10) // 2

                    # Check for proficiency in save
                    if hasattr(char, 'saving_throws') and char.saving_throws:
                        prof_bonus = char.proficiency_bonus if hasattr(char, 'proficiency_bonus') else 2
                        if save_type.upper() in [s.upper() for s in char.saving_throws]:
                            modifier += prof_bonus

                    return modifier
            except:
                pass
            return 0

        # Create on_complete callbacks that route results to the DM
        # These closures capture channel and session_context for async routing
        async def on_initiative_complete(results: dict):
            await self._route_view_results_to_dm(
                channel, session_context, "initiative", results
            )

        async def on_save_complete(results: dict):
            await self._route_view_results_to_dm(
                channel, session_context, "save", results
            )

        async def on_reaction_complete(results: dict):
            await self._route_view_results_to_dm(
                channel, session_context, "reaction", results
            )

        # Select and show UI based on response type
        if expectation.response_type == ResponseType.NONE:
            # DM narrating - no UI needed
            return

        elif expectation.response_type == ResponseType.ACTION:
            # Standard turn - just announce whose turn it is
            active = expectation.characters[0] if expectation.characters else "Unknown"
            await channel.send(f"⚔️ **{active}'s turn.** What do you do?")

        elif expectation.response_type == ResponseType.INITIATIVE:
            # Show initiative view with roll button
            view = InitiativeView(
                expected_characters=expectation.characters,
                timeout=120.0,
                get_character_for_user=get_character_for_user,
                get_dex_modifier=get_dex_modifier,
                on_complete=on_initiative_complete,
            )
            await channel.send(
                "🎲 **Roll for Initiative!**\n"
                f"Waiting for: {', '.join(expectation.characters)}",
                view=view
            )

        elif expectation.response_type == ResponseType.SAVING_THROW:
            # Parse save type and DC from prompt
            prompt = expectation.prompt or "Make a saving throw"
            save_type, dc = parse_save_from_prompt(prompt)

            view = SaveView(
                expected_characters=expectation.characters,
                prompt=prompt,
                save_type=save_type,
                dc=dc,
                timeout=60.0,
                get_character_for_user=get_character_for_user,
                get_save_modifier=get_save_modifier,
                on_complete=on_save_complete,
            )
            await channel.send(f"🎲 **{prompt}**", view=view)

        elif expectation.response_type == ResponseType.REACTION:
            # Show reaction view with Pass/Use Reaction buttons
            prompt = expectation.prompt or "Does anyone want to use a reaction?"
            view = ReactionView(
                expected_characters=expectation.characters,
                prompt=prompt,
                timeout=30.0,
                get_character_for_user=get_character_for_user,
                on_complete=on_reaction_complete,
            )
            await channel.send(f"⚡ {prompt}", view=view)

        elif expectation.response_type == ResponseType.FREE_FORM:
            # Exploration mode - anyone can respond
            chars = ', '.join(expectation.characters) if expectation.characters else "Anyone"
            await channel.send(f"*{chars} may respond.*")


async def setup(bot: commands.Bot):
    """Add this cog to the bot."""
    await bot.add_cog(SessionCommands(bot))
