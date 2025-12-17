"""
BYOK (Bring Your Own Key) Service

Handles guild-level API key resolution (strict BYOK - no fallback).
"""

from typing import Optional

from src.persistence.database import get_session
from src.persistence.repositories.api_key_repo import APIKeyRepository


async def get_api_key_for_guild(guild_id: int) -> Optional[str]:
    """
    Get API key for a guild (strict BYOK - no fallback).

    Args:
        guild_id: Discord guild ID

    Returns:
        API key string, or None if guild has no key registered
    """
    try:
        async with get_session() as db_session:
            api_key_repo = APIKeyRepository(db_session)
            guild_key = await api_key_repo.get_guild_key(guild_id)
            return guild_key
    except Exception as e:
        print(f"Warning: Failed to fetch guild API key from database: {e}")
        return None
