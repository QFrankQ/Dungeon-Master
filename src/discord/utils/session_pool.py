"""
Session pool for managing SessionManager instances per Discord channel.

This module provides a simple in-memory session pool that creates and manages
SessionManager instances for each active game session in Discord channels.
"""

from typing import Dict, Optional
from dataclasses import dataclass
import shutil
import tempfile
from pathlib import Path


@dataclass
class SessionContext:
    """Context for an active game session in a Discord channel."""
    session_manager: 'SessionManager'  # Type: ignore
    guild_id: int
    channel_id: int
    temp_character_dir: Optional[str] = None


class SessionPool:
    """
    Manages SessionManager instances for Discord channels.

    Each Discord channel can have one active game session. This pool
    creates, manages, and cleans up SessionManager instances.
    """

    def __init__(self):
        self._sessions: Dict[int, SessionContext] = {}  # channel_id -> SessionContext

    def get(self, channel_id: int) -> Optional[SessionContext]:
        """
        Get an existing session for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            SessionContext if session exists, None otherwise
        """
        return self._sessions.get(channel_id)

    async def create_session(
        self,
        channel_id: int,
        guild_id: int
    ) -> SessionContext:
        """
        Create a new game session for a channel.

        Args:
            channel_id: Discord channel ID
            guild_id: Discord guild (server) ID

        Returns:
            New SessionContext

        Raises:
            ValueError: If session already exists for this channel
        """
        if channel_id in self._sessions:
            raise ValueError(f"Session already exists for channel {channel_id}")

        # Import here to avoid circular dependencies
        from demo_terminal import create_demo_session_manager
        from src.memory.turn_manager import ActionDeclaration

        # Create session manager with temp directory (like demo_terminal.py:607)
        session_manager, temp_dir = create_demo_session_manager(dm_model_name='gemini-2.5-flash')

        # Initialize first turn (like demo_terminal.py:150-158)
        # This ensures there's an active turn before first player message
        session_manager.turn_manager.start_and_queue_turns(
            actions=[ActionDeclaration(speaker="System", content="Discord session started")]
        )
        session_manager.turn_manager.update_processing_turn_to_current()
        session_manager.turn_manager.mark_new_messages_as_responded()

        context = SessionContext(
            session_manager=session_manager,
            guild_id=guild_id,
            channel_id=channel_id,
            temp_character_dir=temp_dir
        )

        self._sessions[channel_id] = context
        return context

    async def end_session(self, channel_id: int) -> bool:
        """
        End and cleanup a session.

        Args:
            channel_id: Discord channel ID

        Returns:
            True if session was ended, False if no session existed
        """
        context = self._sessions.pop(channel_id, None)
        if not context:
            return False

        # Cleanup temp character directory (like demo_terminal.py:503-509)
        if context.temp_character_dir and Path(context.temp_character_dir).exists():
            try:
                shutil.rmtree(context.temp_character_dir)
            except Exception as e:
                print(f"Warning: Could not clean up temp directory: {e}")

        return True

    def get_all_sessions(self) -> Dict[int, SessionContext]:
        """Get all active sessions."""
        return dict(self._sessions)

    def get_session_count(self) -> int:
        """Get number of active sessions."""
        return len(self._sessions)


# Global session pool instance
_session_pool: Optional[SessionPool] = None


def get_session_pool() -> SessionPool:
    """Get or create the global session pool instance."""
    global _session_pool
    if _session_pool is None:
        _session_pool = SessionPool()
    return _session_pool
