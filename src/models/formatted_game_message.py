"""
FormattedGameMessage model for agent processing and history storage.
Represents a game message with essential character information for DM agent consumption.
"""

from dataclasses import dataclass


@dataclass
class FormattedGameMessage:
    """
    Formatted message for agent processing and history storage.
    
    Contains essential character information along with the message text.
    Can be converted to rich format for agent input or trimmed format for history.
    """
    character_name: str
    character_class: str
    character_level: int
    message_text: str
    
    # Essential character stats for agent decision-making
    current_hp: int
    max_hp: int
    armor_class: int
    status_effects: str = "None"
    
    def to_agent_input(self) -> str:
        """
        Convert to rich text format for agent input processing.
        Provides full character context for current turn decision-making.
        
        Returns:
            Formatted string with character stats and action
        """
        return (
            f"Character: {self.character_name} (Level {self.character_level} {self.character_class})\n"
            f"HP: {self.current_hp}/{self.max_hp} | AC: {self.armor_class} | Status: {self.status_effects}\n"
            f"Action: {self.message_text}"
        )
    
    def to_history_format(self) -> str:
        """
        Convert to trimmed format for message history storage.
        Keeps only essential information for conversation continuity.
        
        Returns:
            Simple character: message format
        """
        return f"{self.character_name}: {self.message_text}"
    
    def get_character_summary(self) -> str:
        """
        Get a one-line character summary for status displays.
        
        Returns:
            Formatted character status line
        """
        status_part = f", Status: {self.status_effects}" if self.status_effects != "None" else ""
        return (
            f"{self.character_name} (Level {self.character_level} {self.character_class}): "
            f"HP {self.current_hp}/{self.max_hp}, AC {self.armor_class}{status_part}"
        )
    
    def is_character_healthy(self) -> bool:
        """Check if character is at full health."""
        return self.current_hp == self.max_hp
    
    def is_character_critical(self) -> bool:
        """Check if character is at critically low health (25% or less)."""
        return self.current_hp <= (self.max_hp * 0.25)
    
    def has_status_effects(self) -> bool:
        """Check if character has any active status effects."""
        return self.status_effects != "None" and self.status_effects.strip() != ""