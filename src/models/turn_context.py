"""
TurnContext data models for hierarchical turn tracking.

Contains TurnContext and related data structures for managing turn-based
conversation context with selective filtering capabilities.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from .turn_message import TurnMessage, MessageType, create_live_message, create_completed_subturn_message
from .formatted_game_message import FormattedGameMessage


@dataclass 
class TurnContext:
    """
    Context for a single turn or sub-turn in the turn stack.
    
    Contains messages with selective filtering capabilities to serve both
    DM (full chronological context) and StateExtractor (current turn only) needs.
    
    Uses TurnMessage system to distinguish between live conversation messages
    and condensed subturn results for proper context isolation.
    """
    turn_id: str
    turn_level: int  # Stack depth (0=main turn, 1=sub-turn, 2=sub-sub-turn, etc.)
    active_character: Optional[str] = None
    initiative_order: Optional[List[str]] = None
    
    # Enhanced message management with selective filtering
    messages: List[TurnMessage] = field(default_factory=list)
    
    # Legacy message storage for backward compatibility
    _formatted_messages: List[FormattedGameMessage] = field(default_factory=list)
    
    # Turn metadata
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_live_message(self, content: str) -> None:
        """Add a live conversation message to this turn's context."""
        message = create_live_message(content, self.turn_id, self.turn_level, self.turn_level)
        self.messages.append(message)
    
    def add_completed_subturn(self, condensed_content: str, subturn_id: str) -> None:
        """Add a condensed subturn result to this turn's context."""
        message = create_completed_subturn_message(condensed_content, subturn_id, self.turn_level, self.turn_level)
        self.messages.append(message)
    
    def get_live_messages_only(self) -> List[str]:
        """
        Get only live conversation messages from this specific turn.
        Used by StateExtractor to avoid processing condensed subturn results.
        """
        return [msg.content for msg in self.messages 
                if msg.message_type == MessageType.LIVE_MESSAGE and 
                   msg.turn_origin == self.turn_id]
    
    def get_all_messages_chronological(self) -> List[str]:
        """
        Get all messages (live + condensed subturns) in chronological order.
        Used by DM context builder for full turn context.
        """
        return [msg.content for msg in self.messages]
    
    # Legacy compatibility methods 
    def add_message(self, message: FormattedGameMessage) -> None:
        """Legacy method - add FormattedGameMessage and convert to live message."""
        self._formatted_messages.append(message)
        # Convert to live message for new system
        self.add_live_message(message.to_agent_input())
    
    def get_turn_context_messages(self) -> List[str]:
        """
        Legacy method - get messages for state extraction.
        Now returns only live messages from current turn.
        """
        return self.get_live_messages_only()
    
    def is_completed(self) -> bool:
        """Check if this turn has been completed."""
        return self.end_time is not None
    
    def to_xml_context(self) -> str:
        """
        Convert this TurnContext to XML format for agent consumption.
        
        Generates the XML structure used by agents with proper nesting and formatting:
        ```xml
        <turn_log>
          <message type="player/dm">content</message>
          <reaction id="..." level="...">
            <action>...</action>
            <resolution>...</resolution>
          </reaction>
        </turn_log>
        ```
        
        Returns:
            XML string wrapped in markdown code fences
        """
        xml_parts = ["```xml", "<turn_log>"]
        
        # Process messages chronologically
        for msg in self.messages:
            element = msg.to_xml_element()
            
            # Add proper indentation
            if msg.message_type == MessageType.LIVE_MESSAGE:
                xml_parts.append(f"  {element}")
            else:
                # For reactions, add with base indentation (element already has internal indentation)
                xml_parts.append(f"  {element}")
        
        xml_parts.extend(["</turn_log>", "```"])
        return "\n".join(xml_parts)


@dataclass
class TurnExtractionContext:
    """
    Context passed to StateExtractor containing isolated turn messages and metadata.
    """
    turn_id: str
    turn_level: int
    turn_messages: List[str]
    active_character: Optional[str] = None
    parent_modifications: List[str] = field(default_factory=list)  # From child turns
    metadata: Dict[str, Any] = field(default_factory=dict)