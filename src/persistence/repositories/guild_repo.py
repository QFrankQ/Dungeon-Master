"""Guild repository for database operations."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistence.models import Guild


class GuildRepository:
    """Repository for Guild database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, guild_id: int) -> Optional[Guild]:
        """Get guild by Discord guild ID."""
        result = await self.session.execute(
            select(Guild).where(Guild.id == guild_id)
        )
        return result.scalar_one_or_none()

    async def create(self, guild_id: int, name: str) -> Guild:
        """Create a new guild."""
        guild = Guild(id=guild_id, name=name)
        self.session.add(guild)
        await self.session.flush()
        return guild

    async def get_or_create(self, guild_id: int, name: str) -> Guild:
        """Get guild or create if it doesn't exist."""
        guild = await self.get_by_id(guild_id)
        if not guild:
            guild = await self.create(guild_id, name)
        return guild

    async def update_name(self, guild_id: int, name: str) -> Optional[Guild]:
        """Update guild name."""
        guild = await self.get_by_id(guild_id)
        if guild:
            guild.name = name
            await self.session.flush()
        return guild

    async def delete(self, guild_id: int) -> bool:
        """Delete a guild and all related data."""
        guild = await self.get_by_id(guild_id)
        if guild:
            await self.session.delete(guild)
            await self.session.flush()
            return True
        return False
