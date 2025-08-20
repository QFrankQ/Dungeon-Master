"""
MessageFormatter service for transforming messages between different formats.
Handles conversion from ChatMessage to FormattedGameMessage and creates structured agent input.
"""

from typing import List, Dict
from ..models.chat_message import ChatMessage
from ..models.formatted_game_message import FormattedGameMessage


class MessageFormatter:
    """
    Service for formatting messages for different purposes.
    
    Transforms ChatMessages to FormattedGameMessages and creates structured
    input text for the DM agent with character context.
    """
    
    def __init__(self, character_repository=None):
        """
        Initialize the message formatter.
        
        Args:
            character_repository: Repository for character data lookup (optional for now)
        """
        self.character_repository = character_repository
    
    def chat_to_formatted(self, chat_msg: ChatMessage) -> FormattedGameMessage:
        """
        Convert ChatMessage to FormattedGameMessage with character lookup.
        
        Args:
            chat_msg: ChatMessage from frontend
            
        Returns:
            FormattedGameMessage with character information
            
        Note:
            Currently uses placeholder character data. Will be enhanced when
            character repository is integrated.
        """
        # TODO: Replace with actual character repository lookup
        # For now, use placeholder data
        return FormattedGameMessage(
            character_name=f"Character_{chat_msg.character_id}",
            character_class="Unknown",
            character_level=1,
            message_text=chat_msg.text,
            current_hp=20,
            max_hp=20,
            armor_class=10,
            status_effects="None"
        )
    
    def format_agent_input(self, messages: List[FormattedGameMessage]) -> str:
        """
        Create structured input text for the DM agent.
        
        Uses "messages first" format:
        1. PLAYER ACTIONS section with all character messages
        2. CHARACTER STATUS section with character stats (deduplicated)
        
        Args:
            messages: List of FormattedGameMessage objects
            
        Returns:
            Structured text for agent consumption
        """
        if not messages:
            return ""
        
        # Collect actions and unique characters
        actions = []
        characters: Dict[str, FormattedGameMessage] = {}
        
        for msg in messages:
            # Add action to list
            actions.append(f"{msg.character_name}: {msg.message_text}")
            
            # Store character info (deduplicate by name)
            characters[msg.character_name] = msg
        
        # Build structured input
        input_parts = ["=== PLAYER ACTIONS ==="]
        input_parts.extend(actions)
        input_parts.append("")  # Add spacing
        input_parts.append("=== CHARACTER STATUS ===")
        
        # Add character status information
        for msg in characters.values():
            input_parts.append(msg.get_character_summary())
        
        return "\n".join(input_parts)
    
    def messages_to_history(self, messages: List[FormattedGameMessage]) -> List[str]:
        """
        Convert FormattedGameMessages to trimmed format for history storage.
        
        Args:
            messages: List of FormattedGameMessage objects
            
        Returns:
            List of trimmed message strings for history
        """
        return [msg.to_history_format() for msg in messages]
    
    def batch_chat_to_formatted(self, chat_messages: List[ChatMessage]) -> List[FormattedGameMessage]:
        """
        Convert multiple ChatMessages to FormattedGameMessages.
        
        Args:
            chat_messages: List of ChatMessage objects from frontend
            
        Returns:
            List of FormattedGameMessage objects
        """
        return [self.chat_to_formatted(msg) for msg in chat_messages]