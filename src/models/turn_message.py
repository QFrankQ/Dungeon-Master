"""
Message types and models for turn-based context management.

Defines message types and structures used in the unified turn context system
that supports selective filtering for different consumers (DM vs StateExtractor).
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Union

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
    processed_for_state_extraction: bool = False  # Track if StateExtractor has processed this
    is_new_message: bool = True  # Track if DM has responded to this message yet
    
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

    def mark_as_responded(self) -> None:
        """Mark this message as no longer new (DM has responded to it)."""
        self.is_new_message = False
    
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

def create_live_message(
    content: str,
    turn_origin: str,
    turn_level: str,
    speaker: str = "player",
    is_new_message: bool = True
) -> TurnMessage:
    """
    Factory function to create a live conversation message.

    Args:
        content: The message content
        turn_origin: ID of the turn this message belongs to
        turn_level: Level of the turn (0=main, 1+=subturn)
        speaker: Speaker type ("player" or "dm")
        is_new_message: Whether this message should be marked as new (default True)

    Returns:
        TurnMessage configured for live conversation
    """
    return TurnMessage(
        content=content,
        speaker=speaker,
        message_type=MessageType.LIVE_MESSAGE,
        turn_origin=turn_origin,
        turn_level=turn_level,
        is_new_message=is_new_message
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


@dataclass
class MessageGroup:
    """
    Groups multiple TurnMessages that were input simultaneously.

    Used for tracking batches of messages (e.g., multiple reactions declared at once)
    and highlighting them as "new" to the DM without duplication in context.

    This allows TurnContext.messages to be Union[TurnMessage, MessageGroup],
    where MessageGroup is treated like a single unit but contains multiple messages.
    """
    messages: List[TurnMessage]
    timestamp: datetime = field(default_factory=datetime.now)
    is_new_message: bool = True  # Track if DM has responded to this group yet
    message_type: MessageType = field(init=False)  # Inferred from contained messages

    def __post_init__(self):
        """Validate and infer message type from contained messages."""
        if not self.messages:
            raise ValueError("MessageGroup must contain at least one message")

        # Infer message_type from the first message (all messages in group should be same type)
        self.message_type = self.messages[0].message_type

    def mark_as_processed(self) -> None:
        """Mark this group and all contained messages as processed for state extraction."""
        for message in self.messages:
            message.mark_as_processed()

    def mark_as_responded(self) -> None:
        """Mark this group and all contained messages as no longer new (DM has responded)."""
        self.is_new_message = False
        for message in self.messages:
            message.mark_as_responded()

    def to_xml_element(self) -> str:
        """
        Convert this MessageGroup to an XML element string.

        Returns a simple wrapper containing all messages:
        <message_group>
          <message speaker="...">...</message>
          <message speaker="...">...</message>
        </message_group>

        Returns:
            XML string representation of this message group
        """
        xml_parts = ["<message_group>"]
        for message in self.messages:
            # Indent each message
            xml_parts.append(f"  {message.to_xml_element()}")
        xml_parts.append("</message_group>")
        return "\n".join(xml_parts)

    def __str__(self) -> str:
        """String representation showing all messages."""
        return f"MessageGroup({len(self.messages)} messages)"


def create_message_group(messages: List[TurnMessage]) -> MessageGroup:
    """
    Factory function to create a message group.

    Args:
        messages: List of TurnMessage objects to group together

    Returns:
        MessageGroup containing the messages
    """
    return MessageGroup(messages=messages)