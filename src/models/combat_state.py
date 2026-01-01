"""
Combat state tracking for D&D combat phase progression.

Manages the three phases of combat:
- Phase 1: Combat Start (initiative collection, order finalization)
- Phase 2: Combat Rounds (main loop with turns)
- Phase 3: Combat End (conclusion and cleanup)

Based on combat_flow.txt specification.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class CombatPhase(str, Enum):
    """Current phase of combat progression."""
    NOT_IN_COMBAT = "not_in_combat"   # Exploration mode
    COMBAT_START = "combat_start"      # Phase 1: Initiative collection
    COMBAT_ROUNDS = "combat_rounds"    # Phase 2: Main combat loop
    COMBAT_END = "combat_end"          # Phase 3: Conclusion


class InitiativeEntry(BaseModel):
    """
    Single initiative roll result for a combatant.

    Note on 2024 PHB Surprise Rules:
    - Surprise gives DISADVANTAGE on initiative roll (not "skip first turn")
    - The disadvantage is applied BEFORE rolling, so is_surprised is not stored here
    - Once the roll is made with disadvantage factored in, no additional tracking needed

    Fields:
    - character_id: Unique identifier used for system lookups (e.g., "fighter", "goblin_1")
    - character_name: Display name for UI/narrative (e.g., "Tharion Stormwind", "Goblin Archer")
    - is_player: True for player characters, False for monsters/NPCs
    """
    character_id: str = Field(..., description="Unique identifier for the character (e.g., 'fighter', 'goblin_1')")
    character_name: str = Field(..., description="Display name of the character/creature for narrative")
    roll: int = Field(..., description="Total initiative roll result (with any modifiers/advantage/disadvantage already applied)")
    is_player: bool = Field(default=True, description="Whether this is a player character")
    dex_modifier: int = Field(default=0, description="Dexterity modifier for tie-breaking")

    def __lt__(self, other: "InitiativeEntry") -> bool:
        """Compare for sorting (higher initiative first, then higher dex mod)."""
        if self.roll != other.roll:
            return self.roll > other.roll  # Higher roll goes first
        return self.dex_modifier > other.dex_modifier  # Higher dex breaks ties


class CombatState(BaseModel):
    """
    Tracks overall combat state across all phases.

    This is the single source of truth for combat progression,
    stored in TurnManager and referenced for phase transitions.
    """
    phase: CombatPhase = Field(default=CombatPhase.NOT_IN_COMBAT)
    round_number: int = Field(default=0, description="Current combat round (0 = not started)")
    initiative_order: List[InitiativeEntry] = Field(default_factory=list, description="Sorted initiative order")
    participants: List[str] = Field(default_factory=list, description="All combatant names")
    current_participant_index: int = Field(default=0, description="Index in initiative_order")

    # Combat metadata
    encounter_name: Optional[str] = Field(default=None, description="Optional name for the encounter")
    combat_start_narrative: Optional[str] = Field(default=None, description="How combat started")

    model_config = {"arbitrary_types_allowed": True}

    def start_combat(self, participants: List[str], encounter_name: Optional[str] = None) -> None:
        """
        Transition to COMBAT_START phase (Phase 1).

        Args:
            participants: List of all combatant names (players + enemies)
            encounter_name: Optional descriptive name for the encounter
        """
        self.phase = CombatPhase.COMBAT_START
        self.participants = participants
        self.round_number = 0
        self.initiative_order = []
        self.current_participant_index = 0
        self.encounter_name = encounter_name

    def add_initiative_roll(self, entry: InitiativeEntry) -> None:
        """
        Add an initiative roll during Phase 1.

        Args:
            entry: The initiative entry to add
        """
        if self.phase != CombatPhase.COMBAT_START:
            raise ValueError(f"Cannot add initiative roll in phase {self.phase}")

        # Check if character already has an entry (by character_id)
        existing = next((e for e in self.initiative_order if e.character_id == entry.character_id), None)
        if existing:
            # Replace existing entry (in case of re-roll)
            self.initiative_order.remove(existing)

        self.initiative_order.append(entry)

    def finalize_initiative(self) -> None:
        """
        Finalize initiative order and transition to COMBAT_ROUNDS phase (Phase 2).

        Sorts the initiative order and prepares for the first round.
        """
        if self.phase != CombatPhase.COMBAT_START:
            raise ValueError(f"Cannot finalize initiative in phase {self.phase}")

        # Sort by roll (descending), then by dex modifier (descending) for ties
        self.initiative_order = sorted(self.initiative_order)
        self.phase = CombatPhase.COMBAT_ROUNDS
        self.round_number = 1
        self.current_participant_index = 0

    def get_current_participant_id(self) -> Optional[str]:
        """Get the character_id of the current participant in initiative order."""
        if not self.initiative_order or self.phase != CombatPhase.COMBAT_ROUNDS:
            return None
        if self.current_participant_index >= len(self.initiative_order):
            return None
        return self.initiative_order[self.current_participant_index].character_id

    def get_current_entry(self) -> Optional[InitiativeEntry]:
        """Get the full initiative entry for the current participant."""
        if not self.initiative_order or self.phase != CombatPhase.COMBAT_ROUNDS:
            return None
        if self.current_participant_index >= len(self.initiative_order):
            return None
        return self.initiative_order[self.current_participant_index]

    def advance_turn(self) -> tuple[Optional[str], bool]:
        """
        Move to next participant in initiative order.

        Returns:
            Tuple of (next_participant_id, is_new_round)
            - next_participant_id: character_id of next participant, or None if combat ended
            - is_new_round: True if we wrapped to a new round
        """
        if self.phase != CombatPhase.COMBAT_ROUNDS:
            return None, False

        self.current_participant_index += 1
        is_new_round = False

        # Check if we've completed the round
        if self.current_participant_index >= len(self.initiative_order):
            self.current_participant_index = 0
            self.round_number += 1
            is_new_round = True

        return self.get_current_participant_id(), is_new_round

    def remove_participant(self, character_id: str) -> bool:
        """
        Remove a participant from combat (died, fled, etc.).

        Args:
            character_id: The character_id of the participant to remove

        Returns:
            True if removed, False if not found
        """
        # Find and remove from initiative order (by character_id)
        entry = next((e for e in self.initiative_order if e.character_id == character_id), None)
        if entry:
            removed_index = self.initiative_order.index(entry)
            self.initiative_order.remove(entry)

            # Adjust current index if needed
            if removed_index < self.current_participant_index:
                self.current_participant_index -= 1
            elif removed_index == self.current_participant_index:
                # Current participant was removed, don't advance index
                # (next call to advance_turn will get the new participant at this index)
                if self.current_participant_index >= len(self.initiative_order):
                    self.current_participant_index = 0

            # Remove from participants list
            if character_id in self.participants:
                self.participants.remove(character_id)

            return True
        return False

    def add_new_combatant(self, entry: InitiativeEntry, immediate_turn: bool = True) -> None:
        """
        Add a new combatant mid-combat (per combat_flow.txt Phase 2 section 3).

        Args:
            entry: The initiative entry for the new combatant
            immediate_turn: If True, they act immediately then join order
        """
        if self.phase != CombatPhase.COMBAT_ROUNDS:
            raise ValueError("Can only add combatants during combat rounds")

        # Add to participants (using character_id)
        if entry.character_id not in self.participants:
            self.participants.append(entry.character_id)

        # If immediate turn, they'll be handled separately
        # Then add to initiative order at appropriate position
        self.initiative_order.append(entry)
        self.initiative_order = sorted(self.initiative_order)

    def start_combat_end(self) -> None:
        """Transition to COMBAT_END phase (Phase 3)."""
        if self.phase != CombatPhase.COMBAT_ROUNDS:
            raise ValueError(f"Cannot end combat from phase {self.phase}")
        self.phase = CombatPhase.COMBAT_END

    def finish_combat(self) -> None:
        """Complete combat and return to exploration mode."""
        self.phase = CombatPhase.NOT_IN_COMBAT
        self.round_number = 0
        self.initiative_order = []
        self.participants = []
        self.current_participant_index = 0
        self.encounter_name = None
        self.combat_start_narrative = None

    def get_initiative_summary(self) -> str:
        """Get a formatted summary of the current initiative order."""
        if not self.initiative_order:
            return "No initiative order established."

        lines = [f"=== Initiative Order (Round {self.round_number}) ==="]
        for i, entry in enumerate(self.initiative_order):
            marker = "→ " if i == self.current_participant_index else "  "
            player_marker = "PC" if entry.is_player else "NPC"
            lines.append(f"{marker}{i+1}. {entry.character_name} [{player_marker}]: {entry.roll}")

        return "\n".join(lines)

    def get_remaining_player_ids(self) -> List[str]:
        """Get list of player character IDs still in combat."""
        return [e.character_id for e in self.initiative_order if e.is_player]

    def get_remaining_monster_ids(self) -> List[str]:
        """Get list of monster/NPC character IDs still in combat."""
        return [e.character_id for e in self.initiative_order if not e.is_player]

    def is_combat_over(self) -> bool:
        """
        Check if combat should end (one side eliminated).

        Returns:
            True if all players or all monsters are gone
        """
        players = self.get_remaining_player_ids()
        monsters = self.get_remaining_monster_ids()
        return len(players) == 0 or len(monsters) == 0


def create_combat_state() -> CombatState:
    """Factory function to create a new CombatState instance."""
    return CombatState()
