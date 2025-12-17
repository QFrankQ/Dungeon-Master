"""
Session pool for managing SessionManager instances per Discord channel.

This module provides session management with database persistence for
multi-guild support and session recovery.
"""

from typing import Dict, Optional
from dataclasses import dataclass
import uuid
import shutil
import tempfile
from pathlib import Path


@dataclass
class SessionContext:
    """Context for an active game session in a Discord channel."""
    session_manager: 'SessionManager'  # Type: ignore
    guild_id: int
    channel_id: int
    session_db_id: uuid.UUID  # Database session ID (Phase 2)
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
        guild_id: int,
        guild_name: str
    ) -> SessionContext:
        """
        Create a new game session for a channel with database persistence.

        Args:
            channel_id: Discord channel ID
            guild_id: Discord guild (server) ID
            guild_name: Discord guild name

        Returns:
            New SessionContext

        Raises:
            ValueError: If session already exists for this channel
            ValueError: If guild has no API key registered (strict BYOK)
        """
        if channel_id in self._sessions:
            raise ValueError(f"Session already exists for channel {channel_id}")

        # Import here to avoid circular dependencies
        from demo_terminal import create_demo_session_manager
        from src.memory.turn_manager import ActionDeclaration
        from src.persistence.database import get_session
        from src.persistence.repositories.guild_repo import GuildRepository
        from src.persistence.repositories.session_repo import SessionRepository
        from src.services.byok_service import get_api_key_for_guild

        # Phase 3: Get guild's API key (strict BYOK - no fallback)
        guild_api_key = await get_api_key_for_guild(guild_id)
        if not guild_api_key:
            raise ValueError(
                f"This server needs an API key before you can start a game. "
                f"Server admins: use `/guild-key` to register a Gemini API key."
            )

        # Create session manager with guild's API key
        session_manager, temp_dir = create_demo_session_manager(
            dm_model_name='gemini-2.5-flash',
            api_key=guild_api_key  # Pass guild's API key for BYOK
        )

        # Initialize first turn (like demo_terminal.py:150-158)
        # This ensures there's an active turn before first player message
        session_manager.turn_manager.start_and_queue_turns(
            actions=[ActionDeclaration(speaker="System", content="Discord session started")]
        )
        session_manager.turn_manager.update_processing_turn_to_current()
        session_manager.turn_manager.mark_new_messages_as_responded()

        # Phase 2: Persist to database
        session_db_id = None
        try:
            async with get_session() as db_session:
                # Ensure guild exists
                guild_repo = GuildRepository(db_session)
                await guild_repo.get_or_create(guild_id, guild_name)

                # Create session record
                session_repo = SessionRepository(db_session)
                db_game_session = await session_repo.create(guild_id, channel_id)
                session_db_id = db_game_session.id
                await db_session.commit()
        except Exception as e:
            print(f"Warning: Failed to persist session to database: {e}")
            # Continue anyway - Phase 1 compatibility (in-memory only)
            session_db_id = uuid.uuid4()

        context = SessionContext(
            session_manager=session_manager,
            guild_id=guild_id,
            channel_id=channel_id,
            session_db_id=session_db_id,
            temp_character_dir=temp_dir
        )

        self._sessions[channel_id] = context
        return context

    async def end_session(self, channel_id: int) -> bool:
        """
        End and cleanup a session with database cleanup.

        Args:
            channel_id: Discord channel ID

        Returns:
            True if session was ended, False if no session existed
        """
        context = self._sessions.pop(channel_id, None)
        if not context:
            return False

        # Phase 2: Cleanup database record
        try:
            from src.persistence.database import get_session
            from src.persistence.repositories.session_repo import SessionRepository

            async with get_session() as db_session:
                session_repo = SessionRepository(db_session)
                await session_repo.delete(context.session_db_id)
                await db_session.commit()
        except Exception as e:
            print(f"Warning: Failed to cleanup session from database: {e}")

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
