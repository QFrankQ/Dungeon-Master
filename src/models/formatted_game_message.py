"""
FormattedGameMessage model for agent processing and history storage.
Represents a game message with essential character information for DM agent consumption.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FormattedGameMessage:
    """
    Formatted message for agent processing and history storage.

    Contains essential character information along with the message text.
    Can be converted to rich format for agent input or trimmed format for history.

    Can work with either:
    1. Full Character object (recommended) - provides rich context
    2. Simple fields (backward compatibility) - basic info only
    """
    message_text: str
    character_name: str
    character_class: str = ""
    character_level: int = 1

    # Essential character stats for agent decision-making (backward compatibility)
    current_hp: int = 0
    max_hp: int = 0
    armor_class: int = 10
    status_effects: str = "None"

    # Optional: Full character object for rich context
    character: Optional[object] = None  # Type hint as object to avoid circular import

    def to_agent_input(self, detail_level: str = "combat") -> str:
        """
        Convert to rich text format for agent input processing.
        Provides full character context for current turn decision-making.

        Args:
            detail_level: "minimal", "combat", or "full" context depth

        Returns:
            Formatted string with character stats and action
        """
        if self.character:
            # Use full Character object for rich context
            if detail_level == "minimal":
                context = f"{self.character.info.name}: HP {self.character.hp}/{self.character.hit_points.maximum_hp}, AC {self.character.ac}"
            elif detail_level == "combat":
                context = self.character.get_combat_summary()
            elif detail_level == "full":
                context = self.character.get_full_sheet()
            else:
                context = self.character.get_combat_summary()

            return f"{context}\n\nAction: {self.message_text}"
        else:
            # Fallback to simple fields (backward compatibility)
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
        if self.character:
            return f"{self.character.info.name}: {self.message_text}"
        return f"{self.character_name}: {self.message_text}"

    def get_character_summary(self, detail_level: str = "combat") -> str:
        """
        Get character summary at specified detail level.

        Args:
            detail_level: "minimal", "combat", "abilities", "effects", "spellcasting", or "full"

        Returns:
            Formatted character status
        """
        if self.character:
            if detail_level == "minimal":
                conditions = ", ".join(self.character.conditions) if self.character.conditions else "None"
                return f"{self.character.info.name}: {self.character.hp}/{self.character.hit_points.maximum_hp} HP, AC {self.character.ac}, Status: {conditions}"
            elif detail_level == "combat":
                return self.character.get_combat_summary()
            elif detail_level == "abilities":
                return self.character.get_ability_summary()
            elif detail_level == "effects":
                return self.character.get_effects_summary()
            elif detail_level == "spellcasting":
                return self.character.get_spellcasting_summary()
            elif detail_level == "full":
                return self.character.get_full_sheet()
            else:
                return self.character.get_combat_summary()
        else:
            # Fallback to simple fields
            status_part = f", Status: {self.status_effects}" if self.status_effects != "None" else ""
            return (
                f"{self.character_name} (Level {self.character_level} {self.character_class}): "
                f"HP {self.current_hp}/{self.max_hp}, AC {self.armor_class}{status_part}"
            )

    def is_character_healthy(self) -> bool:
        """Check if character is at full health."""
        if self.character:
            return self.character.hp == self.character.hit_points.maximum_hp
        return self.current_hp == self.max_hp

    def is_character_critical(self) -> bool:
        """Check if character is at critically low health (25% or less)."""
        if self.character:
            return self.character.hit_points.hp_percentage <= 0.25
        return self.current_hp <= (self.max_hp * 0.25)

    def is_character_bloodied(self) -> bool:
        """Check if character is bloodied (below 50% HP)."""
        if self.character:
            return self.character.is_bloodied
        return self.current_hp < (self.max_hp / 2)

    def has_status_effects(self) -> bool:
        """Check if character has any active status effects."""
        if self.character:
            return len(self.character.conditions) > 0
        return self.status_effects != "None" and self.status_effects.strip() != ""