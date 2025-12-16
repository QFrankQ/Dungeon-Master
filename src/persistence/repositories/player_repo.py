"""Player repository for database operations."""

import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistence.models import Player


class PlayerRepository:
    """Repository for Player database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, player_id: uuid.UUID) -> Optional[Player]:
        """Get player by UUID."""
        result = await self.session.execute(
            select(Player).where(Player.id == player_id)
        )
        return result.scalar_one_or_none()

    async def get_by_discord_user(self, discord_user_id: int, guild_id: int) -> Optional[Player]:
        """Get player by Discord user ID and guild ID."""
        result = await self.session.execute(
            select(Player).where(
                Player.discord_user_id == discord_user_id,
                Player.guild_id == guild_id
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        discord_user_id: int,
        guild_id: int,
        display_name: str
    ) -> Player:
        """Create a new player."""
        player = Player(
            discord_user_id=discord_user_id,
            guild_id=guild_id,
            display_name=display_name
        )
        self.session.add(player)
        await self.session.flush()
        return player

    async def get_or_create(
        self,
        discord_user_id: int,
        guild_id: int,
        display_name: str
    ) -> Player:
        """Get player or create if they don't exist."""
        player = await self.get_by_discord_user(discord_user_id, guild_id)
        if not player:
            player = await self.create(discord_user_id, guild_id, display_name)
        return player

    async def set_active_character(
        self,
        player_id: uuid.UUID,
        character_id: uuid.UUID
    ) -> Optional[Player]:
        """Set player's active character."""
        player = await self.get_by_id(player_id)
        if player:
            player.active_character_id = character_id
            await self.session.flush()
        return player

    async def get_by_guild(self, guild_id: int) -> List[Player]:
        """Get all players in a guild."""
        result = await self.session.execute(
            select(Player).where(Player.guild_id == guild_id)
        )
        return list(result.scalars().all())
