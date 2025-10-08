"""
Message types and models for turn-based context management.

Defines message types and structures used in the unified turn context system
that supports selective filtering for different consumers (DM vs StateExtractor).
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from .chat_message import ChatMessage


#TODO: processed or not
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
    speaker: str #Change to players and DM later
    message_type: MessageType
    turn_origin: str  # Which turn this message originated from
    turn_level: str
    timestamp: datetime = field(default_factory=datetime.now)
    processed_for_state_extraction: bool = False  # Track if message has been processed
    
    def __str__(self) -> str:
        """String representation of the message content."""
        return self.content
    
    def is_live_message(self) -> bool:
        """Check if this is a live conversation message."""
        return self.message_type == MessageType.LIVE_MESSAGE
    
    def is_completed_subturn(self) -> bool:
        """Check if this is a condensed subturn result."""
        return self.message_type == MessageType.COMPLETED_SUBTURN

    def mark_as_processed(self) -> None:
        """Mark this message as processed for state extraction."""
        self.processed_for_state_extraction = True
    
    def to_xml_element(self) -> str:
        """
        Convert this TurnMessage to an XML element string.
        
        For LIVE_MESSAGE: Creates <message type="player/dm">content</message>
        For COMPLETED_SUBTURN: Creates <reaction id="..." level="...">content</reaction>
        
        Returns:
            XML string representation of this message
        """
        if self.message_type == MessageType.LIVE_MESSAGE:
            # Use the speaker field directly
            return f'<message speaker="{self.speaker}">{self.content}</message>'
            
        elif self.message_type == MessageType.COMPLETED_SUBTURN:
            # Calculate nesting level from turn_origin (count dots)
            #TODO: Not necessary reaction, could be other types of action.
            
            return f'<reaction id="{self.turn_origin}" level="{self.turn_level}">\n    {self.content}\n  </reaction>'
            
        else:
            # Fallback for unknown message types
            return f'<unknown>{self.content}</unknown>'

def create_live_message(content: str, turn_origin: str, turn_level: str, speaker: str = "player") -> TurnMessage:
    """
    Factory function to create a live conversation message.
    
    Args:
        content: The message content
        turn_origin: ID of the turn this message belongs to
        speaker: Speaker type ("player" or "dm")
        
    Returns:
        TurnMessage configured for live conversation
    """
    return TurnMessage(
        content=content,
        speaker=speaker,
        message_type=MessageType.LIVE_MESSAGE,
        turn_origin=turn_origin,
        turn_level = turn_level
    )


def create_completed_subturn_message(condensed_content: str, subturn_id: str, subturn_level: str) -> TurnMessage:
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
        speaker="system",  # Completed subturns are system-generated
        message_type=MessageType.COMPLETED_SUBTURN,
        turn_origin=subturn_id,
        turn_level = subturn_level
    )