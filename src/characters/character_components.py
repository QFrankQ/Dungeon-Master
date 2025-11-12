from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict
from enum import Enum
from .dnd_enums import (
    AbilityScore, Alignment, Race, CharacterClass, Language,
    WeaponType, ArmorType, HitDieType, DamageType, Condition
)

#TODO: Duration type may need further refinement for non-combat game play
class DurationType(str, Enum):
    """Duration types for lasting effects."""
    ROUNDS = "rounds"                      # Combat rounds (6 seconds each)
    MINUTES = "minutes"                    # Real-world minutes
    HOURS = "hours"                        # Real-world hours
    UNTIL_LONG_REST = "until_long_rest"    # Persists until long rest
    UNTIL_SHORT_REST = "until_short_rest"  # Persists until short rest
    PERMANENT = "permanent"                 # Until removed by effect
    CONCENTRATION = "concentration"         # Ends if concentration breaks


class Effect(BaseModel):
    """
    Represents a lasting effect on a character.
    Tracks duration, source, and stat modifiers.
    """
    name: str
    effect_type: str  # "condition", "buff", "debuff", "spell"
    duration_type: DurationType
    duration_remaining: int  # rounds/minutes/hours remaining
    source: str  # e.g., "Poison (Orc attack)", "Bless (Cleric)", "Rage (Barbarian)"
    modifiers: Dict[str, int] = {}  # stat modifications (e.g., {"attack_rolls": 1, "saving_throws": 1})
    created_at_turn: Optional[int] = None  # turn number when applied

    def tick(self, increment: int = 1) -> bool:
        """
        Decrement duration by increment.
        Returns True if effect is still active, False if expired.
        """
        if self.duration_type == DurationType.PERMANENT:
            return True

        self.duration_remaining -= increment
        return self.duration_remaining > 0

    def get_description(self) -> str:
        """Get human-readable description of effect and duration."""
        if self.duration_type == DurationType.PERMANENT:
            duration_str = "permanent"
        elif self.duration_type == DurationType.CONCENTRATION:
            duration_str = f"concentration ({self.duration_remaining} rounds remaining)"
        else:
            unit = self.duration_type.value
            duration_str = f"{self.duration_remaining} {unit} remaining"

        return f"{self.name} ({duration_str}, from {self.source})"

class AbilityScores(BaseModel):
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    @property
    def modifiers(self) -> dict[str, int]:
        # Using 5e formula: (score - 10) // 2
        return {ab: (score - 10) // 2 for ab, score in self.model_dump().items()}

class HitPoints(BaseModel):
    maximum_hp: int
    current_hp: int
    temporary_hp: int = 0

    @field_validator('current_hp')
    @classmethod
    def validate_current_hp(cls, v, info):
        """Ensure current HP doesn't exceed maximum and is non-negative."""
        max_hp = info.data.get('maximum_hp', 0)
        return max(0, min(v, max_hp))

    @property
    def effective_hp(self) -> int:
        """Total HP including temporary HP."""
        return self.current_hp + self.temporary_hp

    @property
    def is_bloodied(self) -> bool:
        """D&D bloodied condition (below 50% HP)."""
        return self.current_hp < self.maximum_hp / 2

    @property
    def is_unconscious(self) -> bool:
        """Character at 0 HP."""
        return self.current_hp <= 0

    @property
    def hp_percentage(self) -> float:
        """Percentage of HP remaining (0.0 to 1.0)."""
        if self.maximum_hp == 0:
            return 0.0
        return self.current_hp / self.maximum_hp

class HitDice(BaseModel):
    total: int  # total number available (e.g., levels)
    used: int = 0
    die_type: Optional[HitDieType] = None  # Type of hit die for this character

#TODO: may need to be reset upon stabilization or regain HP
#TODO: may need to be tied to hit points model
class DeathSaves(BaseModel):
    successes: int = 0
    failures: int = 0

    @field_validator('successes', 'failures')
    @classmethod
    def validate_saves(cls, v):
        """Death saves capped at 3 and non-negative."""
        return max(0, min(3, v))

    @property
    def is_stable(self) -> bool:
        """Character has succeeded 3 death saves."""
        return self.successes >= 3

    @property
    def is_dead(self) -> bool:
        """Character has failed 3 death saves."""
        return self.failures >= 3

class CombatStats(BaseModel):
    armor_class: int
    initiative_bonus: int  # Dexterity modifier + other bonuses
    speed: int  # in feet

    @property
    def initiative(self) -> int:
        """Alias for initiative_bonus for backward compatibility."""
        return self.initiative_bonus

class SavingThrows(BaseModel):
    strength: bool = False
    dexterity: bool = False
    constitution: bool = False
    intelligence: bool = False
    wisdom: bool = False
    charisma: bool = False

class Skills(BaseModel):
    acrobatics: bool = False
    animal_handling: bool = False
    arcana: bool = False
    athletics: bool = False
    deception: bool = False
    history: bool = False
    insight: bool = False
    intimidation: bool = False
    investigation: bool = False
    medicine: bool = False
    nature: bool = False
    perception: bool = False
    performance: bool = False
    persuasion: bool = False
    religion: bool = False
    sleight_of_hand: bool = False
    stealth: bool = False
    survival: bool = False

class CharacterInfo(BaseModel):
    name: str
    player_name: Optional[str]
    background: Optional[str]
    alignment: Optional[Alignment]
    race: Optional[Race]
    classes: List[CharacterClass]  # e.g., ["Fighter", "Rogue"]
    level: int
    experience_points: int
    proficiency_bonus: int
    inspiration: bool = False
    passive_perception: Optional[int] = None

#TODO
class ProficienciesAndLanguages(BaseModel):
    armor: List[ArmorType] = []
    weapons: List[WeaponType] = []
    tools: List[str] = []
    languages: List[Language] = []

class Feature(BaseModel):
    name: str
    description: str

class FeaturesAndTraits(BaseModel):
    features: List[Feature] = []

class Spellcasting(BaseModel):
    spellcasting_ability: Optional[AbilityScore]
    spell_save_dc: Optional[int]
    spell_attack_bonus: Optional[int]
    cantrips_known: int = 0
    spells_known: int = 0
    spell_slots: dict[int, int] = {}  # e.g. {1: 4, 2: 3} - available slots by level
    spell_slots_expended: dict[int, int] = {}  # e.g. {1: 1, 2: 0} - used slots
    spells_prepared: List[str] = []  # List of prepared spell names

    def has_spell_slot(self, level: int) -> bool:
        """Check if spell slot is available at given level."""
        if level == 0:  # Cantrips don't use slots
            return True
        available = self.spell_slots.get(level, 0)
        used = self.spell_slots_expended.get(level, 0)
        return used < available
    #TODO: if mistakenly used (returning False), may need a way to un-do and re-run the DM
    def use_spell_slot(self, level: int) -> bool:
        """
        Expend a spell slot at given level.
        Returns True if successful, False if no slots available.
        """
        if level == 0:  # Cantrips don't use slots
            return True
        if not self.has_spell_slot(level):
            return False
        self.spell_slots_expended[level] = self.spell_slots_expended.get(level, 0) + 1
        return True

    def restore_spell_slots(self, levels: Optional[List[int]] = None):
        """
        Restore spell slots. If levels specified, restore only those levels.
        Otherwise, restore all slots (long rest).
        """
        if levels is None:
            # Long rest - restore all slots
            self.spell_slots_expended.clear()
        else:
            # Restore specific levels (e.g., Arcane Recovery)
            for level in levels:
                if level in self.spell_slots_expended:
                    del self.spell_slots_expended[level]

    def get_remaining_slots(self, level: int) -> int:
        """Get number of remaining spell slots at given level."""
        available = self.spell_slots.get(level, 0)
        used = self.spell_slots_expended.get(level, 0)
        return max(0, available - used)
