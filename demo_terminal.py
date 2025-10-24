"""
Demo Terminal Script for D&D Session Manager

This script provides a terminal interface to interact with the DM through the Session Manager.
Uses simplified demo methods that bypass GD agent and state management for demo purposes.
"""

import asyncio
from datetime import datetime
from typing import Optional, TYPE_CHECKING

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

    def __init__(self, session_manager: 'SessionManager'):
        self.session_manager = session_manager
        self.session_active = True

        # Usage tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

        # Multi-character support
        self.characters = {
            "hero": {"player_id": "player1", "character_name": "Hero"},
            "wizard": {"player_id": "player2", "character_name": "Gandalf"},
            "rogue": {"player_id": "player3", "character_name": "Shadowblade"},
            "cleric": {"player_id": "player4", "character_name": "Healix"}
        }
        self.current_character_key = "hero"  # Default character

    @property
    def current_player_id(self):
        """Get current player ID."""
        return self.characters[self.current_character_key]["player_id"]

    @property
    def current_character_name(self):
        """Get current character name."""
        return self.characters[self.current_character_key]["character_name"]

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

        print("\n[SYSTEM] Demo session ended. Farewell!")

    def print_header(self):
        """Print demo header."""
        print("=" * 70)
        print(" " * 20 + "D&D SESSION MANAGER DEMO")
        print("=" * 70)
        print("\nThis demo uses simplified methods without GD and state management.")
        print("Perfect for testing DM interactions and turn management.\n")

    def print_instructions(self):
        """Print available commands."""
        print("-" * 70)
        print("COMMANDS:")
        print("  /help          - Show this help message")
        print("  /turn          - Show current turn information")
        print("  /history       - Show completed turns history")
        print("  /stats         - Show turn manager statistics")
        print("  /usage         - Show token usage statistics")
        print("  /context       - Show DM context as built by context builder")
        print("  /switch <char> - Switch to a different character (hero, wizard, rogue, cleric)")
        print("  /who           - Show current character and all available characters")
        print("  /quit          - Exit the demo")
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

        # Start first turn with default objective
        initial_objective = "Greet the player and set the initial enemy scene for combat"
        self.session_manager.turn_manager.start_and_queue_turns(
            actions=[{"speaker": self.current_character_name, "content": "I'm ready to begin the adventure!"}],
            new_step_objective=initial_objective
        )

        print(f"[SYSTEM] Session initialized. Current objective: {initial_objective}")
        print(f"[SYSTEM] Playing as: {self.current_character_name}")
        print("\n[DM] Welcome, brave adventurer! Your journey begins...")

    async def process_player_action(self, action_text: str):
        """
        Process player action through the demo session manager.

        Args:
            action_text: The player's action text
        """
        # Create ChatMessage (import locally to avoid heavy imports at module import)
        from src.models.chat_message import ChatMessage

        message = ChatMessage.create_player_message(
            player_id=self.current_player_id,
            character_id=self.current_character_name,
            text=action_text
        )

        # Process through demo method
        print("\n[SYSTEM] Processing...", end="", flush=True)

        # Use demo method - returns dict with responses and usage
        result = await self.session_manager.demo_process_player_input(
            new_messages=[message]
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

        elif cmd == '/who':
            self.show_characters()

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
            new_message_entries=None  # Don't include new messages, just show current state
        )

        # Display the context
        print(context)
        print("=" * 70)

    def switch_character(self, character_key: str):
        """
        Switch to a different character.

        Args:
            character_key: Key for the character to switch to (hero, wizard, rogue, cleric)
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


def create_demo_session_manager(dm_model_name=None) -> 'SessionManager':
    """
    Create a session manager configured for demo purposes.

    Returns:
        SessionManager with DM agent and turn manager
    """
    # Local imports to avoid heavy SDK/module import at module load time
    print("Starting imports for demo session manager...")
    from src.agents.dungeon_master import create_dungeon_master_agent
    from src.memory.session_manager import SessionManager
    from src.memory.turn_manager import create_turn_manager
    from src.memory.player_character_registry import create_player_character_registry
    print("Finished imports for demo session manager.")
    # Create DM agent
    dm_agent = create_dungeon_master_agent(model_name=dm_model_name)

    # Create turn manager (without condensation for demo)
    turn_manager = create_turn_manager(turn_condensation_agent=None)

    # Create player character registry
    player_registry = create_player_character_registry()

    # Register demo player and character
    player_registry.register_player_character("demo_player", "Hero")

    # Create session manager with all components
    session_manager = SessionManager(
        gameflow_director_agent=None,  # No GD for demo
        dungeon_master_agent=dm_agent,
        state_extraction_orchestrator=None,  # No state extraction for demo
        state_manager=None,  # No state management for demo
        enable_state_management=False,
        # tool_registry=None,
        turn_manager=turn_manager,
        enable_turn_management=True,
        player_character_registry=player_registry
    )

    return session_manager


async def main():
    """Main entry point for demo terminal."""
    print("\n[SYSTEM] Creating demo session...")

    # Create session manager
    session_manager = create_demo_session_manager(dm_model_name='gemini-2.5-flash')
    print("[SYSTEM] Demo session manager created.")
    # # Create and run terminal
    terminal = DemoTerminal(session_manager)
    print("[SYSTEM] Starting demo terminal...")
    await terminal.run()


if __name__ == "__main__":
    print("Starting D&D Session Manager Demo Terminal...\n")
    asyncio.run(main())
