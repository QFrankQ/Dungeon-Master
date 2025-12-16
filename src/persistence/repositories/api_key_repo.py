"""API Key repository for BYOK system (Phase 3)."""

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet

from src.persistence.models import APIKey
from src.config.settings import get_settings


class APIKeyRepository:
    """Repository for APIKey database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        settings = get_settings()
        self.encryption_key = settings.get_encryption_key()
        self.cipher = Fernet(self.encryption_key) if self.encryption_key else None

    async def get_user_key(self, guild_id: int, user_id: int) -> Optional[str]:
        """Get decrypted API key for a specific user in a guild."""
        result = await self.session.execute(
            select(APIKey).where(
                APIKey.guild_id == guild_id,
                APIKey.user_id == user_id
            )
        )
        api_key = result.scalar_one_or_none()
        if api_key and self.cipher:
            decrypted = self.cipher.decrypt(api_key.encrypted_key)
            return decrypted.decode()
        return None

    async def get_guild_key(self, guild_id: int) -> Optional[str]:
        """Get decrypted guild-wide API key."""
        result = await self.session.execute(
            select(APIKey).where(
                APIKey.guild_id == guild_id,
                APIKey.user_id.is_(None)  # NULL = guild-wide
            )
        )
        api_key = result.scalar_one_or_none()
        if api_key and self.cipher:
            decrypted = self.cipher.decrypt(api_key.encrypted_key)
            return decrypted.decode()
        return None

    async def set_user_key(
        self,
        guild_id: int,
        user_id: int,
        api_key: str,
        key_type: str = "free"
    ) -> APIKey:
        """Set API key for a specific user."""
        if not self.cipher:
            raise ValueError("Encryption key not configured")

        # Check if key already exists
        result = await self.session.execute(
            select(APIKey).where(
                APIKey.guild_id == guild_id,
                APIKey.user_id == user_id
            )
        )
        existing = result.scalar_one_or_none()

        encrypted = self.cipher.encrypt(api_key.encode())

        if existing:
            # Update existing key
            existing.encrypted_key = encrypted
            existing.key_type = key_type
            await self.session.flush()
            return existing
        else:
            # Create new key
            new_key = APIKey(
                guild_id=guild_id,
                user_id=user_id,
                encrypted_key=encrypted,
                key_type=key_type
            )
            self.session.add(new_key)
            await self.session.flush()
            return new_key

    async def set_guild_key(
        self,
        guild_id: int,
        api_key: str,
        key_type: str = "free"
    ) -> APIKey:
        """Set guild-wide API key."""
        if not self.cipher:
            raise ValueError("Encryption key not configured")

        # Check if key already exists
        result = await self.session.execute(
            select(APIKey).where(
                APIKey.guild_id == guild_id,
                APIKey.user_id.is_(None)
            )
        )
        existing = result.scalar_one_or_none()

        encrypted = self.cipher.encrypt(api_key.encode())

        if existing:
            # Update existing key
            existing.encrypted_key = encrypted
            existing.key_type = key_type
            await self.session.flush()
            return existing
        else:
            # Create new key
            new_key = APIKey(
                guild_id=guild_id,
                user_id=None,
                encrypted_key=encrypted,
                key_type=key_type
            )
            self.session.add(new_key)
            await self.session.flush()
            return new_key

    async def delete_user_key(self, guild_id: int, user_id: int) -> bool:
        """Delete user's API key."""
        result = await self.session.execute(
            select(APIKey).where(
                APIKey.guild_id == guild_id,
                APIKey.user_id == user_id
            )
        )
        api_key = result.scalar_one_or_none()
        if api_key:
            await self.session.delete(api_key)
            await self.session.flush()
            return True
        return False

    async def delete_guild_key(self, guild_id: int) -> bool:
        """Delete guild-wide API key."""
        result = await self.session.execute(
            select(APIKey).where(
                APIKey.guild_id == guild_id,
                APIKey.user_id.is_(None)
            )
        )
        api_key = result.scalar_one_or_none()
        if api_key:
            await self.session.delete(api_key)
            await self.session.flush()
            return True
        return False

    async def get_api_key(self, guild_id: int, user_id: int) -> Optional[str]:
        """
        Get API key with fallback logic: user key → guild key → None.

        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID

        Returns:
            Decrypted API key or None
        """
        # Try user's personal key first
        user_key = await self.get_user_key(guild_id, user_id)
        if user_key:
            return user_key

        # Fall back to guild-wide key
        guild_key = await self.get_guild_key(guild_id)
        if guild_key:
            return guild_key

        # No key available
        return None
