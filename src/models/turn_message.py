"""
Message types and models for turn-based context management.

Defines message types and structures used in the unified turn context system
that supports selective filtering for different consumers (DM vs StateExtractor).
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


class MessageType(Enum):
    """Types of messages stored in turn context."""
    LIVE_MESSAGE = "live_message"        # Active conversation messages
    COMPLETED_SUBTURN = "completed_subturn"  # Condensed subturn results


@dataclass
class TurnMessage:
    """
    Individual message in a turn context with metadata for selective filtering.
    
    Supports both live conversation messages and condensed subturn results,
    allowing the same turn context to serve both DM (full context) and 
    StateExtractor (current turn only) needs.
    """
    content: str
    message_type: MessageType
    turn_origin: str  # Which turn this message originated from
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        """String representation of the message content."""
        return self.content
    
    def is_live_message(self) -> bool:
        """Check if this is a live conversation message."""
        return self.message_type == MessageType.LIVE_MESSAGE
    
    def is_completed_subturn(self) -> bool:
        """Check if this is a condensed subturn result."""
        return self.message_type == MessageType.COMPLETED_SUBTURN


def create_live_message(content: str, turn_origin: str) -> TurnMessage:
    """
    Factory function to create a live conversation message.
    
    Args:
        content: The message content
        turn_origin: ID of the turn this message belongs to
        
    Returns:
        TurnMessage configured for live conversation
    """
    return TurnMessage(
        content=content,
        message_type=MessageType.LIVE_MESSAGE,
        turn_origin=turn_origin
    )


def create_completed_subturn_message(condensed_content: str, subturn_id: str) -> TurnMessage:
    """
    Factory function to create a condensed subturn result message.
    
    Args:
        condensed_content: The condensed subturn action-resolution structure
        subturn_id: ID of the completed subturn
        
    Returns:
        TurnMessage configured for condensed subturn result
    """
    return TurnMessage(
        content=condensed_content,
        message_type=MessageType.COMPLETED_SUBTURN,
        turn_origin=subturn_id
    )