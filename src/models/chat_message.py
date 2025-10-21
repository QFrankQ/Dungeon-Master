"""
ChatMessage model for frontend-backend communication.
Represents a message from a player character with full context.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ChatMessage:
    """
    Rich message format for frontend-backend communication.
    
    Contains all necessary information about who sent the message,
    which character they're playing, and metadata for routing.
    """
    player_id: str
    character_id: str
    text: str
    timestamp: datetime
    message_type: str = "player_message"
    
    # Optional fields for advanced messaging
    is_private: bool = False
    
    @classmethod
    def create_player_message(
        cls,
        player_id: str,
        character_id: str,
        text: str
    ) -> "ChatMessage":
        """Create a standard player action message."""
        return cls(
            player_id=player_id,
            character_id=character_id,
            text=text,
            timestamp=datetime.now(),
            message_type="player_message"
        )
    
    @classmethod
    def create_dm_message(
        cls,
        text: str,
        is_private: bool = False
    ) -> "ChatMessage":
        """Create a DM message."""
        return cls(
            player_id="dm",
            character_id="dm",
            text=text,
            timestamp=datetime.now(),
            message_type="dm_response",
            is_private=is_private
        )
    
    @classmethod
    def create_system_message(cls, text: str) -> "ChatMessage":
        """Create a system message (dice rolls, etc.)."""
        return cls(
            player_id="system",
            character_id="system",
            text=text,
            timestamp=datetime.now(),
            message_type="system"
        )
    
    def is_from_player(self) -> bool:
        """Check if this message is from a player character."""
        return self.message_type == "player_message"
    
    def is_from_dm(self) -> bool:
        """Check if this message is from the DM."""
        return self.message_type == "dm_response"
    
    # def is_targeted_message(self) -> bool:
    #     """Check if this message is targeted to specific players."""
    #     return self.target_player_ids is not None and len(self.target_player_ids) > 0