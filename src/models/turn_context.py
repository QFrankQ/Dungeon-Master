"""
TurnContext data models for hierarchical turn tracking.

Contains TurnContext and related data structures for managing turn-based
conversation context with selective filtering capabilities.
"""

from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

from .turn_message import TurnMessage, MessageType, MessageGroup, create_live_message, create_completed_subturn_message, create_message_group
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
    current_step_objective: str
    active_character: Optional[str] = None
    initiative_order: Optional[List[str]] = None
    # Enhanced message management with selective filtering
    # Supports both individual messages and grouped messages
    messages: List[Union[TurnMessage, MessageGroup]] = field(default_factory=list)
    
    # Legacy message storage for backward compatibility
    _formatted_messages: List[FormattedGameMessage] = field(default_factory=list)
    
    # Turn metadata
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_live_message(self, content: str, speaker: str) -> None:
        """Add a live conversation message to this turn's context."""
        message = create_live_message(content, self.turn_id, str(self.turn_level), speaker)
        self.messages.append(message)

    def add_message_group(self, messages: List[TurnMessage]) -> None:
        """
        Add a group of messages as a single unit.

        Used for batching simultaneous messages (e.g., multiple reactions).
        The group will be treated as one item in the messages list.

        Args:
            messages: List of TurnMessage objects to group together
        """
        group = create_message_group(messages)
        self.messages.append(group)

    def add_completed_subturn(self, condensed_content: str, subturn_id: str) -> None:
        """Add a condensed subturn result to this turn's context."""
        message = create_completed_subturn_message(condensed_content, subturn_id, str(self.turn_level))
        self.messages.append(message)
    
    def get_live_messages_only(self) -> List[str]:
        """
        Get only live conversation messages from this specific turn.
        Used by DM to get full chronological context regardless of processing status.
        Handles both individual TurnMessages and MessageGroups.
        """
        result = []
        for item in self.messages:
            if isinstance(item, MessageGroup):
                # Extract messages from group
                result.extend([msg.content for msg in item.messages
                              if msg.message_type == MessageType.LIVE_MESSAGE and
                                 msg.turn_origin == self.turn_id])
            elif isinstance(item, TurnMessage):
                if item.message_type == MessageType.LIVE_MESSAGE and item.turn_origin == self.turn_id:
                    result.append(item.content)
        return result

    def get_unprocessed_live_messages(self) -> List[str]:
        """
        Get only unprocessed live conversation messages from this specific turn.
        Used by StateExtractor to avoid duplicate extractions.
        Handles both individual TurnMessages and MessageGroups.
        """
        result = []
        for item in self.messages:
            if isinstance(item, MessageGroup):
                # Extract unprocessed messages from group
                result.extend([msg.content for msg in item.messages
                              if msg.message_type == MessageType.LIVE_MESSAGE and
                                 msg.turn_origin == self.turn_id and
                                 not msg.processed_for_state_extraction])
            elif isinstance(item, TurnMessage):
                if (item.message_type == MessageType.LIVE_MESSAGE and
                    item.turn_origin == self.turn_id and
                    not item.processed_for_state_extraction):
                    result.append(item.content)
        return result

    def mark_all_messages_as_processed(self) -> int:
        """
        Mark all current messages as processed for state extraction.
        Handles both individual TurnMessages and MessageGroups.

        Returns:
            Number of messages that were marked as processed
        """
        marked_count = 0
        for item in self.messages:
            if isinstance(item, MessageGroup):
                # Mark group and all its messages as processed for state extraction
                item.mark_as_processed()
                # Count how many messages were actually marked
                marked_count += sum(1 for msg in item.messages
                                   if msg.message_type == MessageType.LIVE_MESSAGE)
            elif isinstance(item, TurnMessage):
                if item.message_type == MessageType.LIVE_MESSAGE and not item.processed_for_state_extraction:
                    item.mark_as_processed()
                    marked_count += 1
        return marked_count

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

    def to_xml_context(self, exclude_new_messages: bool = False, cause: Optional[str] = None) -> str:
        """
        Convert this TurnContext to XML format for agent consumption.

        Generates dynamic XML structure based on turn level:
        - Level 0: <turn_log>
        - Level 1+: <subturn_log id="..." cause="...">

        Args:
            exclude_last: Whether to exclude the last message
            exclude_unprocessed: Whether to exclude new/unresponded MessageGroups (is_new_message=True)
                This prevents duplication when new groups are shown in <new_messages>
            cause: Optional cause for subturn (e.g., "trap_sprung")

        Returns:
            XML string wrapped in markdown code fences
        """
        # Determine tag name and attributes based on turn level
        if self.turn_level == 0:
            opening_tag = "<turn_log>"
            closing_tag = "</turn_log>"
        else:
            # For subturns, include ID and optional cause
            if cause:
                opening_tag = f'<subturn_log id="{self.turn_id}" cause="{cause}">'
            else:
                opening_tag = f'<subturn_log id="{self.turn_id}">'
            closing_tag = f'</subturn_log>'

        xml_parts = [opening_tag]

        # Process messages chronologically
        messages = self.messages

        # Filter out new MessageGroups if requested
        if exclude_new_messages:
            messages = [msg for msg in messages
                       if not (isinstance(msg, MessageGroup) and msg.is_new_message)]

        for msg in messages:
            element = msg.to_xml_element()

            # Add proper indentation
            if msg.message_type == MessageType.LIVE_MESSAGE:
                xml_parts.append(f"  {element}")
            else:
                # For reactions, add with base indentation (element already has internal indentation)
                xml_parts.append(f"  {element}")

        xml_parts.extend([closing_tag])
        return "\n".join(xml_parts)

    def get_last_message_xml(self):
        if not self.messages:
            return Exception("No message in current (sub)turn")
        return self.messages[-1].to_xml_element()


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