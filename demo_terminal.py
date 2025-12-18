"""
Demo Terminal Script for D&D Session Manager

This script provides a terminal interface to interact with the DM through the Session Manager.
Uses simplified demo methods that bypass GD agent and state management for demo purposes.
"""

import asyncio
import shutil
import tempfile
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from pathlib import Path
from src.prompts.demo_combat_steps import DEMO_MAIN_ACTION_STEPS, DEMO_REACTION_STEPS
from src.memory.turn_manager import ActionDeclaration
from src.models.response_expectation import ResponseExpectation, ResponseType
from src.memory.response_collector import ResponseCollector, AddResult, create_response_collector
from src.memory.message_coordinator import (
    MessageCoordinator,
    create_message_coordinator,
    MessageValidationResult
)
# Defer heavy imports (agents, vector services, cloud SDKs) until runtime so
# importing this module doesn't trigger long SDK initializations.
if TYPE_CHECKING:
    # Only imported for type checking / annotations
    from src.memory.session_manager import SessionManager
    from src.models.chat_message import ChatMessage


class DemoTerminal:
    """
    Terminal interface for demo D&D session.

    Provides simple command-line interaction with the DM using demo methods.
    """

    def __init__(self, session_manager: 'SessionManager', temp_character_dir: Optional[str] = None):
        self.session_manager = session_manager
        self.session_active = True
        self.temp_character_dir = temp_character_dir  # For cleanup on exit

        # Usage tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

        # Multi-character support (updated to match new character files)
        self.characters = {
            "fighter": {"player_id": "player1", "character_name": "Tharion Stormwind"},
            "wizard": {"player_id": "player2", "character_name": "Lyralei Moonwhisper"},
            "cleric": {"player_id": "player3", "character_name": "Grimjaw Ironforge"}
        }
        self.current_character_key = "fighter"  # Default character

        # Multiplayer coordination - use MessageCoordinator as central gatekeeper
        self.message_coordinator = create_message_coordinator()

    @property
    def current_player_id(self):
        """Get current player ID."""
        return self.characters[self.current_character_key]["player_id"]

    @property
    def current_character_name(self):
        """Get current character name."""
        return self.characters[self.current_character_key]["character_name"]

    # Property accessors for MessageCoordinator state
    @property
    def combat_mode(self) -> bool:
        """Get combat mode from coordinator."""
        return self.message_coordinator.combat_mode

    @property
    def current_expectation(self) -> Optional[ResponseExpectation]:
        """Get current expectation from coordinator."""
        return self.message_coordinator.current_expectation

    @property
    def response_collector(self) -> Optional[ResponseCollector]:
        """Get response collector from coordinator."""
        return self.message_coordinator.response_collector

    def is_valid_responder(self, character_name: str) -> bool:
        """Check if a character is expected to respond."""
        return self.message_coordinator.is_valid_responder(character_name)

    def update_expectation(self, expectation: Optional[ResponseExpectation]):
        """Update the current expectation and display status."""
        # Use MessageCoordinator to set expectation (also creates response collector)
        self.message_coordinator.set_expectation(expectation)

        if expectation is None:
            return

        # Display expectation status
        mode = expectation.get_collection_mode()
        chars = expectation.characters

        if mode == "none":
            print("[WAITING] DM narrating - no response expected")
        elif mode == "single" and chars:
            print(f"[WAITING] {chars[0]}'s turn")
            if expectation.prompt:
                print(f"[PROMPT] {expectation.prompt}")
        elif mode == "all" and chars:
            print(f"[WAITING] All must respond: {', '.join(chars)}")
            if expectation.prompt:
                print(f"[PROMPT] {expectation.prompt}")
        elif mode == "any" and chars:
            print(f"[WAITING] Any of: {', '.join(chars)}")
        elif mode == "optional" and chars:
            print(f"[WAITING] Optional - {', '.join(chars)} may respond or pass")
            if expectation.prompt:
                print(f"[PROMPT] {expectation.prompt}")

    async def run(self):
        """Main demo loop."""
        self.print_header()
        self.print_instructions()

        # Initialize first turn with welcome message
        await self.initialize_session()

        # Main interaction loop
        while self.session_active:
            try:
                user_input = input(f"\n[{self.current_character_name}] ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith('/'):
                    await self.handle_command(user_input)
                    continue

                # Process player message
                await self.process_player_action(user_input)

            except KeyboardInterrupt:
                print("\n\n[SYSTEM] Session interrupted by user.")
                break
            except Exception as e:
                print(f"\n[ERROR] {str(e)}")
                import traceback
                traceback.print_exc()

        # Cleanup temp character directory
        self.cleanup()

        print("\n[SYSTEM] Demo session ended. Farewell!")

    def print_header(self):
        """Print demo header."""
        print("=" * 70)
        print(" " * 20 + "D&D SESSION MANAGER DEMO")
        print("=" * 70)
        print("\nThis demo showcases DM interactions, turn management, and character state tracking.")
        print("State extraction automatically tracks HP, effects, spell slots, and more.\n")

    def print_instructions(self):
        """Print available commands."""
        print("-" * 70)
        print("COMMANDS:")
        print("  /help          - Show this help message")
        print("  /turn          - Show current turn information")
        print("  /history       - Show completed turns history")
        print("  /stats         - Show turn manager statistics")
        print("  /character     - Show current character status and stats")
        print("  /register <id> - Link a character file to current player (fighter, wizard, cleric)")
        print("  /usage         - Show token usage statistics")
        print("  /context       - Show DM context as built by context builder")
        print("  /switch <char> - Switch to a different player/character (fighter, wizard, cleric)")
        print("  /who           - Show current character and all available characters")
        print("  /combat        - Toggle combat mode (strict turn enforcement)")
        print("  /expectation   - Show current response expectation")
        print("  /collected     - Show collected responses (for multi-response modes)")
        print("  /quit          - Exit the demo")
        print("-" * 70)
        print("\nNOTE: In this demo, each character has a separate player_id to simulate")
        print("      multiplayer. Use /switch to change characters for multi-response tests.")
        print("-" * 70)

    async def initialize_session(self):
        """Initialize the session with first turn."""
        print("\n[SYSTEM] Initializing session...")

        # Register all characters in the player character registry
        for char_key, char_info in self.characters.items():
            self.session_manager.player_character_registry.register_player_character(
                char_info["player_id"],
                char_info["character_name"]
            )

        # Auto-register default character if state management is enabled
        if self.session_manager.state_manager:
            default_char_id = "fighter"
            character = self.session_manager.state_manager.load_character(default_char_id)
            if character:
                self.session_manager.player_character_registry.register_player_character(
                    self.current_player_id,
                    default_char_id
                )
                classes_str = "/".join([c.value.title() for c in character.info.classes])
                print(f"[SYSTEM] ✓ Auto-registered '{character.info.name}' ({classes_str} Level {character.info.level})")
                print("[SYSTEM] Use /character to view stats, /register to switch characters")
            else:
                print(f"[SYSTEM] ⚠ Could not auto-register default character. Use /register <character_id> to register.")

        # Start first turn with default objective
        # Use the first step from DEMO_MAIN_ACTION_STEPS as the initial objective
        # Note: game_step_list is automatically determined by turn_level (0 = main action, 1+ = reaction)
        self.session_manager.turn_manager.start_and_queue_turns(
            actions=[ActionDeclaration(speaker=self.current_character_name, content="I'm ready to begin the adventure!")]
        )
        initial_objective = DEMO_MAIN_ACTION_STEPS[0]

        # Mark the initialization message as responded so it doesn't appear as "new"
        # Set processing turn reference first, then mark as responded
        self.session_manager.turn_manager.update_processing_turn_to_current()
        self.session_manager.turn_manager.mark_new_messages_as_responded()
        
        print(f"[SYSTEM] Session initialized. Current objective: {initial_objective}")
        print(f"[SYSTEM] Playing as: {self.current_character_name}")
        print("\n[DM] Welcome, brave adventurer! Your journey begins...")

    async def process_player_action(self, action_text: str):
        """
        Process player action through the demo session manager.

        For multi-response modes (initiative, saving_throw), responses are collected
        until all expected characters have responded. Only then is the DM called.

        Uses MessageCoordinator for validation and response collection.

        Args:
            action_text: The player's action text
        """
        # Validate responder using MessageCoordinator
        validation = self.message_coordinator.validate_responder(self.current_character_name)

        if validation.result != MessageValidationResult.VALID:
            # Handle different invalid cases with appropriate messages
            if validation.result == MessageValidationResult.INVALID_NOT_YOUR_TURN:
                print(f"\n[SYSTEM] {validation.message}")
                print(f"[SYSTEM] Use /switch to change to an expected character.")
            elif validation.result == MessageValidationResult.INVALID_NO_RESPONSE_EXPECTED:
                print(f"\n[SYSTEM] {validation.message}")
            elif validation.result == MessageValidationResult.INVALID_ALREADY_RESPONDED:
                print(f"\n[SYSTEM] {validation.message}")
                print(f"[SYSTEM] {self.message_coordinator.get_status_message()}")
            return

        # Create ChatMessage (import locally to avoid heavy imports at module import)
        from src.models.chat_message import ChatMessage

        message = ChatMessage.create_player_message(
            player_id=self.current_player_id,
            character_id=self.current_character_name,
            text=action_text
        )

        # Check if we're in multi-response collection mode
        collection_mode = self.message_coordinator.get_collection_mode()

        if collection_mode == "all":
            # Multi-response mode: collect responses before sending to DM
            result = self.message_coordinator.add_response(
                self.current_character_name,
                message
            )

            if result == AddResult.DUPLICATE:
                print(f"\n[SYSTEM] {self.current_character_name} has already responded.")
                print(f"[SYSTEM] {self.message_coordinator.get_status_message()}")
                return
            elif result == AddResult.UNEXPECTED:
                print(f"\n[SYSTEM] {self.current_character_name} is not expected to respond.")
                return
            else:
                # Response accepted
                print(f"\n[SYSTEM] Response from {self.current_character_name} collected.")

                # Check if collection is complete
                if not self.message_coordinator.is_collection_complete():
                    # Still waiting for more responses
                    missing = self.message_coordinator.get_missing_responders()
                    print(f"[SYSTEM] Still waiting for: {', '.join(missing)}")
                    print(f"[SYSTEM] Use /switch to respond as another character.")
                    return

                # Collection complete - gather all messages and send to DM
                print(f"\n[SYSTEM] All responses collected! Sending to DM...")
                all_messages = list(self.message_coordinator.get_collected_responses().values())
                await self._send_messages_to_dm(all_messages)
                return

        # For single/any/none modes, send immediately
        await self._send_messages_to_dm([message])

    async def _send_messages_to_dm(self, messages: list):
        """
        Send collected messages to the DM and handle the response.

        Args:
            messages: List of ChatMessage objects to send
        """
        # Process through demo method
        print("\n[SYSTEM] Processing...", end="", flush=True)

        # Use demo method - returns dict with responses and usage
        result = await self.session_manager.demo_process_player_input(
            new_messages=messages
        )

        # Clear processing message
        print("\r" + " " * 30 + "\r", end="")

        # Extract responses and usage
        responses = result["responses"]
        usage = result["usage"]

        # Update session totals
        self.total_input_tokens += usage["input_tokens"]
        self.total_output_tokens += usage["output_tokens"]
        self.total_requests += usage["requests"]

        # Display DM responses
        for response in responses:
            print(f"[DM] {response}\n")

        # Display state change notifications if any
        if result.get("state_results") and result["state_results"].get("success"):
            state_info = result["state_results"]
            if state_info.get("commands_executed", 0) > 0:
                print(f"\n[STATE] {state_info['commands_executed']} state changes applied")
                print("Type /character to see updated character status\n")

        # Update and display awaiting_response
        awaiting = result.get("awaiting_response")
        self.update_expectation(awaiting)

        # Display usage for this run
        print(f"[USAGE] This run: {usage['input_tokens']} in / {usage['output_tokens']} out / {usage['total_tokens']} total / {usage['requests']} requests")

    async def handle_command(self, command: str):
        """
        Handle special commands.

        Args:
            command: The command string (starting with /)
        """
        cmd = command.lower().strip()

        if cmd == '/help':
            self.print_instructions()

        elif cmd == '/turn':
            self.show_turn_info()

        elif cmd == '/history':
            self.show_history()

        elif cmd == '/stats':
            self.show_stats()

        elif cmd == '/usage':
            self.show_usage()

        elif cmd == '/context':
            self.show_context()

        elif cmd.startswith('/switch'):
            parts = command.split()
            if len(parts) < 2:
                print("[SYSTEM] Usage: /switch <character>")
                print(f"[SYSTEM] Available characters: {', '.join(self.characters.keys())}")
            else:
                self.switch_character(parts[1].lower())

        elif cmd == '/character':
            self.show_character_status()

        elif cmd.startswith('/register'):
            parts = command.split()
            if len(parts) < 2:
                print("[SYSTEM] Usage: /register <character_id>")
                print("[SYSTEM] Available characters: fighter, wizard, cleric")
            else:
                await self.register_character(parts[1].lower())

        elif cmd == '/who':
            self.show_characters()

        elif cmd == '/combat':
            self.toggle_combat_mode()

        elif cmd == '/expectation':
            self.show_expectation()

        elif cmd == '/collected':
            self.show_collected()

        elif cmd == '/quit':
            self.session_active = False

        else:
            print(f"[SYSTEM] Unknown command: {command}. Type /help for available commands.")

    def show_turn_info(self):
        """Show current turn information."""
        if not self.session_manager.turn_manager.is_in_turn():
            print("\n[SYSTEM] No active turn")
            return

        current_turn = self.session_manager.turn_manager.get_current_turn_context()
        print(f"\n--- CURRENT TURN INFO ---")
        print(f"Turn ID: {current_turn.turn_id}")
        print(f"Turn Level: {current_turn.turn_level}")
        print(f"Active Character: {current_turn.active_character}")
        print(f"Step Objective: {current_turn.current_step_objective}")
        print(f"Message Count: {len(current_turn.messages)}")

        # Show recent messages
        if current_turn.messages:
            print(f"\nRecent messages:")
            for msg in current_turn.messages[-3:]:  # Last 3 messages
                print(f"  [{msg.speaker}]: {msg.content[:60]}...")

    def show_history(self):
        """Show completed turns history."""
        completed = self.session_manager.turn_manager.completed_turns

        if not completed:
            print("\n[SYSTEM] No completed turns yet")
            return

        print(f"\n--- COMPLETED TURNS ({len(completed)}) ---")
        for turn in completed:
            print(f"\nTurn {turn.turn_id} ({turn.active_character}):")
            print(f"  Duration: {(turn.end_time - turn.start_time).total_seconds():.1f}s")
            print(f"  Messages: {len(turn.messages)}")
            print(f"  Summary: {turn.get_turn_summary()[:100]}...")

    def show_stats(self):
        """Show turn manager statistics."""
        stats = self.session_manager.turn_manager.get_turn_stats()

        print(f"\n--- TURN MANAGER STATISTICS ---")
        print(f"Active Turns: {stats['active_turns']}")
        print(f"Current Turn Level: {stats['current_turn_level']}")
        print(f"Completed Turns: {stats['completed_turns']}")
        print(f"Total Turns Started: {stats['total_turns_started']}")
        print(f"Current Turn ID: {stats['current_turn_id']}")
        print(f"Turn Stack Depth: {stats['turn_stack_depth']}")

        # Show turn stack summary
        stack_summary = self.session_manager.turn_manager.get_turn_stack_summary()
        if stack_summary:
            print(f"\nTurn Stack:")
            for summary in stack_summary:
                print(f"  {summary}")

    def show_usage(self):
        """Show token usage statistics."""
        print(f"\n--- TOKEN USAGE STATISTICS ---")
        print(f"Total Input Tokens: {self.total_input_tokens:,}")
        print(f"Total Output Tokens: {self.total_output_tokens:,}")
        print(f"Total Tokens: {self.total_input_tokens + self.total_output_tokens:,}")
        print(f"Total Requests: {self.total_requests}")

        # Calculate average if we have requests
        if self.total_requests > 0:
            avg_input = self.total_input_tokens / self.total_requests
            avg_output = self.total_output_tokens / self.total_requests
            print(f"\nAverage per Request:")
            print(f"  Input: {avg_input:.1f} tokens")
            print(f"  Output: {avg_output:.1f} tokens")
            print(f"  Total: {(avg_input + avg_output):.1f} tokens")

    def show_context(self):
        """Show the DM context as it would be built by the context builder."""
        print(f"\n--- DM CONTEXT (as built by DMContextBuilder) ---")
        print("=" * 70)

        # Get turn manager snapshot
        turn_manager_snapshot = self.session_manager.turn_manager.get_snapshot()

        # Build context using the demo context builder
        context = self.session_manager.dm_context_builder.build_demo_context(
            turn_manager_snapshots=turn_manager_snapshot,
            # new_message_entries=None  # Don't include new messages, just show current state
        )

        # Estimate token counts (rough approximation: 1 token ≈ 4 chars)
        context_tokens = len(context) // 4

        # Read system prompt and estimate its tokens
        prompt_path = Path(__file__).parent / "src" / "prompts" / "dungeon_master_system_prompt.txt"
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
        system_prompt_tokens = len(system_prompt) // 4

        total_tokens = context_tokens + system_prompt_tokens

        # Display the context
        print(context)
        print("=" * 70)
        print(f"\nToken Estimates (rough: 1 token ≈ 4 chars):")
        print(f"  Context: ~{context_tokens:,} tokens ({len(context):,} chars)")
        print(f"  System Prompt: ~{system_prompt_tokens:,} tokens ({len(system_prompt):,} chars)")
        print(f"  Total: ~{total_tokens:,} tokens")
        print("=" * 70)

    def switch_character(self, character_key: str):
        """
        Switch to a different character.

        Args:
            character_key: Key for the character to switch to (fighter, wizard, cleric)
        """
        if character_key not in self.characters:
            print(f"[SYSTEM] Unknown character: {character_key}")
            print(f"[SYSTEM] Available characters: {', '.join(self.characters.keys())}")
            return

        old_char = self.current_character_name
        self.current_character_key = character_key
        new_char = self.current_character_name

        print(f"\n[SYSTEM] Switched from {old_char} to {new_char}")
        print(f"[SYSTEM] You are now playing as {new_char} (player_id: {self.current_player_id})")

    def show_characters(self):
        """Show current character and all available characters."""
        print(f"\n--- CHARACTER INFORMATION ---")
        print(f"Current Character: {self.current_character_name} (player_id: {self.current_player_id})")
        print("\nAvailable Characters:")
        for key, info in self.characters.items():
            marker = " <-- ACTIVE" if key == self.current_character_key else ""
            print(f"  {key:10} - {info['character_name']:15} (player_id: {info['player_id']}){marker}")

    def toggle_combat_mode(self):
        """Toggle combat mode on/off using MessageCoordinator."""
        if self.message_coordinator.combat_mode:
            self.message_coordinator.exit_combat_mode()
            print(f"\n[SYSTEM] Combat mode: OFF (free exploration)")
        else:
            self.message_coordinator.enter_combat_mode()
            print(f"\n[SYSTEM] Combat mode: ON (strict turn enforcement)")
            if self.current_expectation:
                # Show current expectation when entering combat mode
                self.show_expectation()

    def show_expectation(self):
        """Show current response expectation."""
        print(f"\n--- RESPONSE EXPECTATION ---")
        print(f"Combat Mode: {'ON' if self.combat_mode else 'OFF'}")

        if self.current_expectation is None:
            print("No expectation set (DM hasn't responded yet or awaiting_response was empty)")
            return

        exp = self.current_expectation
        mode = exp.get_collection_mode()

        print(f"Response Type: {exp.response_type.value}")
        print(f"Collection Mode: {mode}")
        print(f"Expected Characters: {', '.join(exp.characters) if exp.characters else '(none)'}")
        if exp.prompt:
            print(f"Prompt: {exp.prompt}")

        # Show validation status
        is_valid = self.is_valid_responder(self.current_character_name)
        print(f"\nCurrent Character: {self.current_character_name}")
        print(f"Can Respond: {'YES' if is_valid else 'NO'}")

        # Show collection progress for multi-response modes
        if self.response_collector and mode == "all":
            collected_count = len(self.response_collector.collected)
            total_count = len(exp.characters)
            print(f"\nCollection Progress: {collected_count}/{total_count}")
            if self.response_collector.collected:
                print(f"Collected from: {', '.join(self.response_collector.collected.keys())}")

    def show_collected(self):
        """Show collected responses for multi-response modes."""
        print(f"\n--- COLLECTED RESPONSES ---")

        if self.response_collector is None:
            print("No response collector active.")
            return

        if not self.current_expectation:
            print("No expectation set.")
            return

        mode = self.current_expectation.get_collection_mode()
        print(f"Collection Mode: {mode}")

        if mode != "all":
            print("(Multi-response collection only applies to 'all' mode - initiative/saving_throw)")
            return

        # Show collected responses
        collected = self.response_collector.collected
        expected = self.current_expectation.characters

        print(f"\nExpected Characters: {', '.join(expected)}")
        print(f"Collection Progress: {len(collected)}/{len(expected)}")

        if collected:
            print(f"\nCollected Responses:")
            for char_name, message in collected.items():
                # message is a ChatMessage object
                text_preview = message.text[:50] + "..." if len(message.text) > 50 else message.text
                print(f"  ✓ {char_name}: \"{text_preview}\"")

        missing = self.response_collector.get_missing_responders()
        if missing:
            print(f"\nStill Waiting For:")
            for char_name in missing:
                print(f"  ○ {char_name}")

        if self.response_collector.is_complete():
            print(f"\n[READY] All responses collected! Next message will send to DM.")
        else:
            print(f"\n[TIP] Use /switch <character> to respond as another character.")

    def show_character_status(self):
        """Show current character's game stats and status."""
        if not self.session_manager.state_manager:
            print("\n[SYSTEM] State management is disabled in this demo.")
            print("[SYSTEM] Enable state management to view character stats.")
            return

        # Get character ID from registry
        character_id = self.session_manager.player_character_registry.get_character_id_by_player_id(self.current_player_id)

        if not character_id:
            print(f"\n[SYSTEM] No character registered for player '{self.current_player_id}'")
            print("[SYSTEM] Use /register <character_id> to link a character")
            print("[SYSTEM] Available characters: fighter, wizard, cleric")
            return

        # Load character from state manager
        character = self.session_manager.state_manager.get_character(character_id)

        if not character:
            print(f"\n[SYSTEM] Character '{character_id}' not found")
            return

        # Display character stats (comprehensive format)
        print(f"\n{'='*70}")
        classes_str = "/".join([c.value.title() for c in character.info.classes])
        print(f"CHARACTER: {character.info.name} ({classes_str} Level {character.info.level})")
        print(f"{'='*70}")

        # HP Status with visual bar
        hp_percent = (character.hit_points.current_hp / character.hit_points.maximum_hp) * 100
        hp_bar_filled = int(hp_percent / 5)  # 20 char bar (5% per char)
        hp_bar = "█" * hp_bar_filled + "░" * (20 - hp_bar_filled)
        print(f"\nHP: [{hp_bar}] {character.hit_points.current_hp}/{character.hit_points.maximum_hp} ({hp_percent:.0f}%)")
        if character.hit_points.temporary_hp > 0:
            print(f"Temp HP: +{character.hit_points.temporary_hp}")

        # Combat Stats
        print(f"\nAC: {character.combat_stats.armor_class} | Initiative: +{character.combat_stats.initiative_bonus} | Speed: {character.combat_stats.speed} ft")

        # Ability Scores
        print(f"\nAbility Scores:")
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            score = getattr(character.ability_scores, ability)
            modifier = (score - 10) // 2
            mod_str = f"+{modifier}" if modifier >= 0 else str(modifier)
            print(f"  {ability.title()[:3].upper()}: {score} ({mod_str})")

        # Active Effects
        if character.active_effects:
            print(f"\nActive Effects:")
            for effect in character.active_effects:
                duration_str = f"{effect.duration} rounds" if effect.duration else "Permanent"
                conc_str = " [Concentration]" if hasattr(effect, 'requires_concentration') and effect.requires_concentration else ""
                print(f"  • {effect.name}: {effect.summary}{conc_str} ({duration_str})")

        # Spell Slots (if spellcaster)
        if hasattr(character, 'spellcasting') and character.spellcasting and character.spellcasting.spell_slots:
            print(f"\nSpell Slots:")
            for level in range(1, 10):
                total_slots = character.spellcasting.spell_slots.get(str(level), 0)
                expended = character.spellcasting.spell_slots_expended.get(str(level), 0)
                current = total_slots - expended
                if total_slots > 0:
                    slot_display = "●" * current + "○" * expended
                    print(f"  Level {level}: {slot_display} ({current}/{total_slots})")

        # Hit Dice
        print(f"\nHit Dice: {character.hit_dice.total - character.hit_dice.used}/{character.hit_dice.total} {character.hit_dice.die_type}")

        # Death Saves (if any recorded)
        if character.death_saves.successes > 0 or character.death_saves.failures > 0:
            success_display = "●" * character.death_saves.successes + "○" * (3 - character.death_saves.successes)
            failure_display = "●" * character.death_saves.failures + "○" * (3 - character.death_saves.failures)
            print(f"\nDeath Saves:")
            print(f"  Successes: {success_display}")
            print(f"  Failures:  {failure_display}")

        print(f"{'='*70}\n")

    async def register_character(self, character_id: str):
        """
        Register a character file to the current player and switch to that character.

        This is useful if you want to use a different character file than the default
        mapping (e.g., use 'wizard' file for player1 instead of 'fighter').

        For simply switching between the 3 pre-configured characters, use /switch instead.
        """
        if not self.session_manager.state_manager:
            print("\n[SYSTEM] State management is disabled in this demo.")
            print("[SYSTEM] Enable state management to use character registration.")
            return

        # Verify character exists by attempting to load it
        character = self.session_manager.state_manager.load_character(character_id)
        if not character:
            print(f"\n[SYSTEM] Character '{character_id}' not found")
            print("[SYSTEM] Available characters: fighter, wizard, cleric")
            return

        # Also switch to that character if it's one of the pre-configured ones
        if character_id in self.characters:
            old_char = self.current_character_name
            self.current_character_key = character_id
            print(f"\n[SYSTEM] Switched from {old_char} to {self.current_character_name}")

        # Register mapping for the current player
        self.session_manager.player_character_registry.register_player_character(self.current_player_id, character_id)
        classes_str = "/".join([c.value.title() for c in character.info.classes])
        print(f"[SYSTEM] ✓ Registered '{character.info.name}' ({classes_str} Level {character.info.level}) to player '{self.current_player_id}'")
        print("[SYSTEM] Use /character to view character status")

    def cleanup(self):
        """Clean up temporary character directory on exit."""
        if self.temp_character_dir and Path(self.temp_character_dir).exists():
            try:
                shutil.rmtree(self.temp_character_dir)
                print(f"[SYSTEM] Cleaned up temporary character data")
            except Exception as e:
                print(f"[SYSTEM] Warning: Could not clean up temp directory: {e}")


def create_demo_session_manager(dm_model_name=None, api_key=None) -> tuple['SessionManager', str]:
    """
    Create a session manager configured for demo purposes.

    Args:
        dm_model_name: Optional model name override
        api_key: Optional API key for guild-level BYOK (required)

    Returns:
        Tuple of (SessionManager with DM agent and turn manager, temp character directory path)
    """
    # Local imports to avoid heavy SDK/module import at module load time
    print("Starting imports for demo session manager...")
    from src.agents.dungeon_master import create_dungeon_master_agent
    from src.memory.session_manager import SessionManager
    from src.memory.turn_manager import create_turn_manager
    from src.memory.player_character_registry import create_player_character_registry
    from src.agents.structured_summarizer import create_turn_condensation_agent
    print("Finished imports for demo session manager.")

    # API key is required
    if not api_key:
        raise ValueError("API key is required for demo session manager")

    # Create turn condensation agent for automatic reaction summarization
    turn_condensation_agent = create_turn_condensation_agent()

    # Create turn manager with condensation agent
    turn_manager = create_turn_manager(turn_condensation_agent=turn_condensation_agent)

    # NEW: Create services for DM tools
    from src.db.lance_rules_service import create_lance_rules_service
    from src.services.rules_cache_service import create_rules_cache_service
    from src.agents.dm_tools import create_dm_tools

    lance_service = create_lance_rules_service()
    rules_cache_service = create_rules_cache_service()

    # Create DM tools and dependencies
    dm_tools, dm_deps = create_dm_tools(
        lance_service=lance_service,
        turn_manager=turn_manager,
        rules_cache_service=rules_cache_service
    )

    # Create DM agent with all tools (turn management + rules database)
    # Pass guild-level API key for BYOK
    dm_agent = create_dungeon_master_agent(
        model_name=dm_model_name,
        tools=[turn_manager.start_and_queue_turns] + dm_tools,
        api_key=api_key  # NEW: Pass guild's API key
    )

    # Store dm_deps for passing to process_message()
    dm_agent.dm_deps = dm_deps

    # Create temporary directory for character state (prevents modifying source files)
    temp_dir = tempfile.mkdtemp(prefix="dnd_demo_")
    print(f"[SYSTEM] Created temporary character directory: {temp_dir}")

    # Copy character JSON files from source to temp directory
    source_char_dir = Path("src/characters")
    temp_char_dir = Path(temp_dir)
    character_files = ["fighter.json", "wizard.json", "cleric.json"]

    for char_file in character_files:
        source_file = source_char_dir / char_file
        if source_file.exists():
            shutil.copy2(source_file, temp_char_dir / char_file)
            print(f"[SYSTEM] Copied {char_file} to temp directory")

    # Create player character registry in temp directory (per-session, not global)
    registry_path = str(temp_char_dir / "player_character_registry.json")
    player_registry = create_player_character_registry(registry_file_path=registry_path)
    print(f"[SYSTEM] Created per-session player registry: {registry_path}")

    # Create state management components with temp directory
    from src.memory.state_manager import create_state_manager
    from src.agents.state_extraction_orchestrator import create_state_extraction_orchestrator

    state_manager = create_state_manager(character_data_path=str(temp_char_dir) + "/")
    state_extraction_orchestrator = create_state_extraction_orchestrator(
        model_name="gemini-2.5-flash-lite",
        api_key=api_key,
        rules_cache_service=rules_cache_service  # Share with DM tools
    )

    # Create session manager with all components
    session_manager = SessionManager(
        gameflow_director_agent=None,  # No GD for demo
        dungeon_master_agent=dm_agent,
        state_extraction_orchestrator=state_extraction_orchestrator,
        state_manager=state_manager,
        enable_state_management=True,  # ENABLED for character tracking
        turn_manager=turn_manager,
        enable_turn_management=True,
        player_character_registry=player_registry,
        rules_cache_service=rules_cache_service  # For DM context with cached rules
    )

    return session_manager, temp_dir


async def main():
    """Main entry point for demo terminal."""
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Get API key from environment
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[ERROR] API key not found in environment variables.")
        print("[ERROR] Please set GEMINI_API_KEY or GOOGLE_API_KEY in your .env file")
        return

    print("\n[SYSTEM] Creating demo session...")

    # Create session manager with temp directory and API key
    session_manager, temp_dir = create_demo_session_manager(
        dm_model_name='gemini-2.5-flash',
        api_key=api_key
    )
    print("[SYSTEM] Demo session manager created.")

    # Create and run terminal with temp directory for cleanup
    terminal = DemoTerminal(session_manager, temp_character_dir=temp_dir)
    print("[SYSTEM] Starting demo terminal...")
    await terminal.run()


if __name__ == "__main__":
    print("Starting D&D Session Manager Demo Terminal...\n")
    asyncio.run(main())
