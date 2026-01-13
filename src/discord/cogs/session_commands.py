"""
Session Commands Cog

Handles game session management: /start and /end commands,
plus the on_message handler for player actions during active sessions.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
import logging

# Set up logger for this module
logger = logging.getLogger(__name__)

from src.discord.utils.session_pool import get_session_pool, SessionContext
from src.discord.utils.message_converter import discord_to_chat_message
from src.memory.message_coordinator import MessageValidationResult
from src.memory.response_collector import AddResult
from src.models.response_expectation import ResponseExpectation, ResponseType
from src.discord.views.reaction_view import ReactionView
from src.discord.views.initiative_modal import InitiativeView
from src.discord.views.save_modal import SaveView, parse_save_from_prompt
from src.prompts.demo_combat_steps import GamePhase


class SessionCommands(commands.Cog):
    """Commands for managing D&D game sessions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session_pool = get_session_pool()

    def _sync_combat_mode_with_phase(self, session_context: SessionContext) -> None:
        """
        Automatically sync combat_mode with the current game phase.

        - COMBAT_ROUNDS: Enable combat_mode (strict turn enforcement)
        - All other phases: Disable combat_mode (free chat)

        This ensures:
        - Players can chat freely during EXPLORATION, COMBAT_START, COMBAT_END
        - Only the active character can act during COMBAT_ROUNDS
        """
        coordinator = session_context.message_coordinator
        turn_manager = session_context.session_manager.turn_manager

        if not coordinator or not turn_manager:
            return

        current_phase = turn_manager.get_current_phase()

        # Only COMBAT_ROUNDS requires strict turn enforcement
        should_be_combat_mode = (current_phase == GamePhase.COMBAT_ROUNDS)

        if should_be_combat_mode and not coordinator.combat_mode:
            coordinator.enter_combat_mode()
        elif not should_be_combat_mode and coordinator.combat_mode:
            coordinator.exit_combat_mode()

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

        # Track for cleanup on error
        response_added_for_cleanup = None  # Will hold character_id if we need to clean up

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

                # Use character_id for system validation, character_name for DM narrative
                # character_id: canonical identifier for turn tracking, validation, initiative
                # character_name: display name for narrative flavor (e.g., "Tharion Stormwind")
                character = session_manager.state_manager.get_character(character_id)
                character_display_name = character.info.name if character else character_id

                # Milestone 5: Validate responder via MessageCoordinator
                # Use character_id for validation (matches turn tracking)
                coordinator = session_context.message_coordinator
                if coordinator:
                    validation = coordinator.validate_responder(character_id)
                    if validation.result != MessageValidationResult.VALID:
                        if coordinator.combat_mode:
                            # In combat mode, reject invalid responders with feedback
                            await self._send_validation_feedback(message, validation)
                            return
                        # In exploration mode, let message through (validation passes)

                # Convert Discord message to ChatMessage format
                # Use display name for narrative (DM sees "Tharion Stormwind said...")
                chat_message = discord_to_chat_message(message, character_display_name)

                # Milestone 5: Multi-response collection for combat mode
                # Only use collection logic when there's an active expectation with a collector
                if coordinator and coordinator.combat_mode and coordinator.current_expectation:
                    # Add response to collector (use character_id for tracking)
                    add_result = coordinator.add_response(character_id, chat_message)

                    # Track for cleanup if processing fails later
                    if add_result == AddResult.ACCEPTED:
                        response_added_for_cleanup = character_id

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
                        # Show progress (use display name for user-facing message)
                        missing = coordinator.get_missing_responders()
                        collected_count = len(coordinator.get_collected_responses())
                        total_count = collected_count + len(missing)
                        await message.add_reaction("✅")
                        await message.channel.send(
                            f"Got **{character_display_name}**'s response. "
                            f"({collected_count}/{total_count}) "
                            f"Waiting for: {', '.join(missing)}"
                        )
                        return

                    # Collection complete - gather all messages for batch processing
                    collected_messages = list(coordinator.get_collected_responses().values())
                else:
                    # Exploration mode, no coordinator, or no expectation set - single message processing
                    collected_messages = [chat_message]

                # Process through SessionManager
                result = await session_manager.demo_process_player_input(
                    new_messages=collected_messages
                )

                # Sync combat_mode with current game phase after DM processing
                # (phase may have changed during processing, e.g., entering COMBAT_ROUNDS)
                self._sync_combat_mode_with_phase(session_context)

                # Milestone 5: Update expectation after DM response and show UI
                if coordinator:
                    awaiting = result.get("awaiting_response")
                    coordinator.set_expectation(awaiting)
                    # Clear cleanup flag - old collector is replaced, response was processed successfully
                    response_added_for_cleanup = None

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
                # Show UI whenever there's a ResponseExpectation, regardless of combat_mode
                # combat_mode only controls validation (blocking wrong players), not UI display
                # This allows initiative modals during COMBAT_START even with combat_mode=False
                awaiting = result.get("awaiting_response")
                if coordinator and awaiting:
                    # Show warning if characters were filtered (Milestone 6)
                    filtered_warning = result.get("filtered_characters_warning")
                    if filtered_warning:
                        await message.channel.send(f"⚠️ *{filtered_warning}*")

                    await self._show_response_ui(
                        message.channel,
                        awaiting,
                        session_context
                    )

        except Exception as e:
            # Clean up: Remove response from collector so player can retry
            # This handles cases like API 503 errors where the message was collected
            # but processing failed before completing
            if response_added_for_cleanup and session_context.message_coordinator:
                try:
                    removed = session_context.message_coordinator.remove_response(response_added_for_cleanup)
                    if removed:
                        logger.info(f"Cleaned up response for {response_added_for_cleanup} after error - player can retry")
                except Exception as cleanup_error:
                    logger.warning(f"Error during cleanup: {cleanup_error}")

            await message.channel.send(
                f"❌ Error processing message: {str(e)}\n"
                f"Please try again or use `/end` to restart the session."
            )
            logger.exception(f"Error in on_message: {e}")

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

            # Add initiative rolls to turn manager (finalization happens after step 5 completes)
            turn_manager = session_manager.turn_manager
            registry = session_manager.player_character_registry
            id_to_name_map = registry.get_character_id_to_name_map() if registry else {}
            if turn_manager:
                for char_id, roll_info in rolls.items():
                    roll_value = roll_info.get("roll", 0)
                    dex_mod = roll_info.get("dex_modifier", 0)
                    # Get display name for narrative (fallback to ID if not found)
                    char_display_name = id_to_name_map.get(char_id, char_id)
                    try:
                        turn_manager.add_initiative_roll(
                            character_id=char_id,
                            character_name=char_display_name,
                            roll=roll_value,
                            dex_modifier=dex_mod,
                            is_player=True  # All Discord players are player characters
                        )
                        logger.info(f"Added initiative roll: {char_display_name} ({char_id}) = {roll_value}")
                    except Exception as e:
                        logger.warning(f"Could not add initiative roll for {char_id}: {e}")

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
                    summary_lines.append(f"- **{char}** wants to use a reaction!")

            if passed:
                summary_lines.append(f"- Passed: {', '.join(passed)}")

            if timed_out:
                summary_lines.append("\n*Window timed out - non-responders treated as passing.*")

            summary_text = "\n".join(summary_lines)

        else:
            summary_text = f"**{response_type} Results:** {results}"

        # Create a system message with the results
        system_message = ChatMessage.create_system_message(text=summary_text)

        try:
            # Show typing indicator while processing
            async with channel.typing():
                # Process through SessionManager
                result = await session_manager.demo_process_player_input(
                    new_messages=[system_message]
                )

                # Sync combat_mode with current game phase after DM processing
                self._sync_combat_mode_with_phase(session_context)

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
                # Show UI whenever there's a ResponseExpectation, regardless of combat_mode
                awaiting = result.get("awaiting_response")
                if coordinator and awaiting:
                    # Show warning if characters were filtered (Milestone 6)
                    filtered_warning = result.get("filtered_characters_warning")
                    if filtered_warning:
                        await channel.send(f"⚠️ *{filtered_warning}*")

                    await self._show_response_ui(channel, awaiting, session_context)

        except Exception as e:
            await channel.send(
                f"❌ Error processing {response_type} results: {str(e)}\n"
                f"Please try again or use `/end` to restart the session."
            )
            logger.exception(f"Error routing view results to DM: {e}")

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

        Character validation happens at parse time in ResponseExpectation's
        model_validator, so by the time we get here, the expectation is already
        validated and any unknown characters have been filtered out.
        """
        if expectation is None:
            return

        # Get helper to resolve user ID -> character ID
        registry = session_context.session_manager.player_character_registry

        def get_character_for_user(user_id: int) -> Optional[str]:
            return registry.get_character_id_by_player_id(str(user_id))

        # Get character ID to name mapping for display purposes
        id_to_name_map = registry.get_character_id_to_name_map()

        def get_display_names(character_ids: List[str]) -> List[str]:
            """Convert character IDs to display names for user-facing messages."""
            return [id_to_name_map.get(cid, cid) for cid in character_ids]

        # Get configurable timeouts (Milestone 6)
        timeouts = session_context.timeouts

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
            # Standard turn - just announce whose turn it is (use display name)
            active_id = expectation.characters[0] if expectation.characters else "Unknown"
            active_name = id_to_name_map.get(active_id, active_id)
            await channel.send(f"*⚔️ It's **{active_name}**'s turn. {active_name} may respond.*")

        elif expectation.response_type == ResponseType.INITIATIVE:
            # Show initiative view with roll button
            view = InitiativeView(
                expected_characters=expectation.characters,
                timeout=timeouts.initiative,  # Configurable (default 120s)
                get_character_for_user=get_character_for_user,
                get_dex_modifier=get_dex_modifier,
                on_complete=on_initiative_complete,
            )
            display_names = get_display_names(expectation.characters)
            await channel.send(
                "🎲 **Roll for Initiative!**\n"
                f"Waiting for: {', '.join(display_names)}",
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
                timeout=timeouts.saving_throw,  # Configurable (default 60s)
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
                timeout=timeouts.reaction,  # Configurable (default 30s)
                get_character_for_user=get_character_for_user,
                on_complete=on_reaction_complete,
            )
            await channel.send(f"⚡ {prompt}", view=view)

        elif expectation.response_type == ResponseType.FREE_FORM:
            # Exploration mode - anyone can respond (use display names)
            if expectation.characters:
                display_names = get_display_names(expectation.characters)
                chars = ', '.join(display_names)
            else:
                chars = "Anyone"
            await channel.send(f"*{chars} may respond.*")


async def setup(bot: commands.Bot):
    """Add this cog to the bot."""
    await bot.add_cog(SessionCommands(bot))
