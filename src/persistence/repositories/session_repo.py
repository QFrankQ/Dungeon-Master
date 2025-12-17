"""Session repository for database operations."""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistence.models import Session, SessionPlayer


class SessionRepository:
    """Repository for Session database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, session_id: uuid.UUID) -> Optional[Session]:
        """Get session by UUID."""
        result = await self.session.execute(
            select(Session).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_channel(self, channel_id: int) -> Optional[Session]:
        """Get session by Discord channel ID."""
        result = await self.session.execute(
            select(Session).where(Session.channel_id == channel_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_guild(self, guild_id: int) -> List[Session]:
        """Get all active sessions in a guild."""
        result = await self.session.execute(
            select(Session).where(
                Session.guild_id == guild_id,
                Session.status == "active"
            )
        )
        return list(result.scalars().all())

    async def create(
        self,
        guild_id: int,
        channel_id: int
    ) -> Session:
        """Create a new session."""
        game_session = Session(
            guild_id=guild_id,
            channel_id=channel_id,
            status="active"
        )
        self.session.add(game_session)
        await self.session.flush()
        return game_session

    async def update_activity(self, session_id: uuid.UUID) -> Optional[Session]:
        """Update session's last activity timestamp."""
        game_session = await self.get_by_id(session_id)
        if game_session:
            game_session.last_activity = datetime.utcnow()
            await self.session.flush()
        return game_session

    async def set_status(
        self,
        session_id: uuid.UUID,
        status: str
    ) -> Optional[Session]:
        """Set session status (active, paused, ended)."""
        game_session = await self.get_by_id(session_id)
        if game_session:
            game_session.status = status
            await self.session.flush()
        return game_session

    async def delete(self, session_id: uuid.UUID) -> bool:
        """Delete a session and all related data."""
        game_session = await self.get_by_id(session_id)
        if game_session:
            await self.session.delete(game_session)
            await self.session.flush()
            return True
        return False

    async def delete_all_active(self) -> int:
        """
        Delete all active sessions (cleanup orphaned sessions on bot restart).

        Returns:
            Number of sessions deleted
        """
        result = await self.session.execute(
            select(Session).where(Session.status == "active")
        )
        sessions = list(result.scalars().all())

        for game_session in sessions:
            await self.session.delete(game_session)

        await self.session.flush()
        return len(sessions)

    async def add_player(
        self,
        session_id: uuid.UUID,
        player_id: uuid.UUID,
        character_id: uuid.UUID
    ) -> SessionPlayer:
        """Add a player to a session."""
        session_player = SessionPlayer(
            session_id=session_id,
            player_id=player_id,
            character_id=character_id
        )
        self.session.add(session_player)
        await self.session.flush()
        return session_player

    async def remove_player(
        self,
        session_id: uuid.UUID,
        player_id: uuid.UUID
    ) -> bool:
        """Remove a player from a session."""
        result = await self.session.execute(
            select(SessionPlayer).where(
                SessionPlayer.session_id == session_id,
                SessionPlayer.player_id == player_id
            )
        )
        session_player = result.scalar_one_or_none()
        if session_player:
            await self.session.delete(session_player)
            await self.session.flush()
            return True
        return False
