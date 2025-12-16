"""Character repository for database operations."""

import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistence.models import Character


class CharacterRepository:
    """Repository for Character database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, character_id: uuid.UUID) -> Optional[Character]:
        """Get character by UUID."""
        result = await self.session.execute(
            select(Character).where(Character.id == character_id)
        )
        return result.scalar_one_or_none()

    async def get_by_owner(self, owner_id: uuid.UUID) -> List[Character]:
        """Get all characters owned by a player."""
        result = await self.session.execute(
            select(Character).where(Character.owner_id == owner_id)
        )
        return list(result.scalars().all())

    async def get_by_guild(self, guild_id: int) -> List[Character]:
        """Get all characters in a guild."""
        result = await self.session.execute(
            select(Character).where(Character.guild_id == guild_id)
        )
        return list(result.scalars().all())

    async def create(
        self,
        guild_id: int,
        owner_id: uuid.UUID,
        name: str,
        character_data: dict,
        is_template: bool = False
    ) -> Character:
        """Create a new character."""
        character = Character(
            guild_id=guild_id,
            owner_id=owner_id,
            name=name,
            character_data=character_data,
            is_template=is_template
        )
        self.session.add(character)
        await self.session.flush()
        return character

    async def update_data(
        self,
        character_id: uuid.UUID,
        character_data: dict
    ) -> Optional[Character]:
        """Update character data."""
        character = await self.get_by_id(character_id)
        if character:
            character.character_data = character_data
            await self.session.flush()
        return character

    async def delete(self, character_id: uuid.UUID) -> bool:
        """Delete a character."""
        character = await self.get_by_id(character_id)
        if character:
            await self.session.delete(character)
            await self.session.flush()
            return True
        return False
