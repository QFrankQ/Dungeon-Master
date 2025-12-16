"""
SQLAlchemy models for D&D DM Bot database.

Defines all database tables for multi-guild support, character management,
session persistence, and BYOK API keys.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    String,
    Text,
    DateTime,
    Integer,
    ForeignKey,
    LargeBinary,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class Guild(Base):
    """Discord guild (server) registration."""
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Discord guild ID
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_api_key_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    players: Mapped[list["Player"]] = relationship("Player", back_populates="guild", cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="guild", cascade="all, delete-orphan")
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="guild", cascade="all, delete-orphan")


class APIKey(Base):
    """BYOK API keys (per-user OR per-guild)."""
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # NULL = guild-wide key
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'free' or 'paid'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    guild: Mapped["Guild"] = relationship("Guild", back_populates="api_keys")

    __table_args__ = (
        UniqueConstraint('guild_id', 'user_id', name='uix_guild_user_api_key'),
    )


class Player(Base):
    """Players per guild."""
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    active_character_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    guild: Mapped["Guild"] = relationship("Guild", back_populates="players")
    characters: Mapped[list["Character"]] = relationship("Character", back_populates="owner", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('discord_user_id', 'guild_id', name='uix_discord_user_guild'),
    )


class Character(Base):
    """Per-player characters (custom creation)."""
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    character_data: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Full Character model serialized
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    owner: Mapped["Player"] = relationship("Player", back_populates="characters")


class Session(Base):
    """Game sessions (per channel)."""
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    guild: Mapped["Guild"] = relationship("Guild", back_populates="sessions")
    session_players: Mapped[list["SessionPlayer"]] = relationship("SessionPlayer", back_populates="session", cascade="all, delete-orphan")
    turn_contexts: Mapped[list["TurnContext"]] = relationship("TurnContext", back_populates="session", cascade="all, delete-orphan")


class SessionPlayer(Base):
    """Session participants (many-to-many)."""
    __tablename__ = "session_players"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    player_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="session_players")


class TurnContext(Base):
    """Turn state persistence (for resume after restart)."""
    __tablename__ = "turn_contexts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    turn_id: Mapped[str] = mapped_column(String(20), nullable=False)  # "1", "1.1", etc.
    turn_level: Mapped[int] = mapped_column(Integer, nullable=False)
    active_character: Mapped[str] = mapped_column(String(100), nullable=False)
    messages: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Serialized TurnMessages
    turn_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Renamed from 'metadata' (reserved word)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="turn_contexts")
