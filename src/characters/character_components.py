from pydantic import BaseModel, Field, field_validator, computed_field
from typing import List, Optional, Dict, Union
from enum import Enum
from .dnd_enums import (
    AbilityScore, Alignment, Race, CharacterClass, Language,
    WeaponType, ArmorType, HitDieType, DamageType, Condition
)


# ==================== Duration & Effect Types (UNCHANGED) ====================

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
    Simple text-based effect tracking for display and reference.

    Effects are tracked to show what's active on characters. DM/agents
    manually apply bonuses when needed. System handles duration tracking
    and expiration.

    Examples:
        - Bless: "Grants +1d4 to attack rolls and saving throws" (10 rounds)
        - Haste: "+2 AC, advantage on Dex saves, doubled speed" (concentration)
        - Fire Resistance: "Resistant to fire damage" (1 hour)
    """
    name: str
    effect_type: str  # "buff", "debuff", "condition", "spell"
    duration_type: DurationType
    duration_remaining: int  # rounds/minutes/hours remaining
    source: str  # e.g., "Bless (Cleric)", "Poison (Orc attack)"
    description: str = ""  # Full text description of the effect
    summary: Optional[str] = None  # Brief summary for compact display
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

    def get_compact_display(self) -> str:
        """Get compact summary for display."""
        duration_part = ""
        if self.duration_type == DurationType.CONCENTRATION:
            duration_part = f" [{self.duration_remaining}r conc]"
        elif self.duration_type != DurationType.PERMANENT:
            duration_part = f" [{self.duration_remaining}{self.duration_type.value[0]}]"

        display_text = self.summary if self.summary else self.description
        return f"{self.name}: {display_text}{duration_part}"


# ==================== Character Class Entry (Multiclassing Support) ====================

class CharacterClassEntry(BaseModel):
    """Represents a single class for multiclass support."""
    class_name: str  # e.g., "Rogue", "Fighter"
    subclass: Optional[str] = None  # e.g., "Soulknife", "Echo Knight"
    level: int = 1


# ==================== Ability Score Components ====================

class AbilityScoreEntry(BaseModel):
    """Single ability score with auto-calculated modifier."""
    score: int

    @computed_field
    @property
    def modifier(self) -> int:
        """Auto-calculate modifier using 5e formula: (score - 10) // 2"""
        return (self.score - 10) // 2


class AbilityScores(BaseModel):
    """All six ability scores with computed modifiers."""
    strength: AbilityScoreEntry
    dexterity: AbilityScoreEntry
    constitution: AbilityScoreEntry
    intelligence: AbilityScoreEntry
    wisdom: AbilityScoreEntry
    charisma: AbilityScoreEntry

    @property
    def modifiers(self) -> Dict[str, int]:
        """Get all modifiers as a dictionary for backward compatibility."""
        return {
            "strength": self.strength.modifier,
            "dexterity": self.dexterity.modifier,
            "constitution": self.constitution.modifier,
            "intelligence": self.intelligence.modifier,
            "wisdom": self.wisdom.modifier,
            "charisma": self.charisma.modifier,
        }

    def get_score(self, ability: str) -> int:
        """Get score by ability name."""
        entry = getattr(self, ability.lower(), None)
        if entry:
            return entry.score
        return 10  # Default

    def get_modifier(self, ability: str) -> int:
        """Get modifier by ability name."""
        entry = getattr(self, ability.lower(), None)
        if entry:
            return entry.modifier
        return 0  # Default


# ==================== Skill & Saving Throw Components ====================

class SkillEntry(BaseModel):
    """Single skill with proficiency, expertise, and bonus tracking."""
    proficient: bool = False
    expertise: bool = False
    additional_bonuses: int = 0

    def get_total_bonus(self, ability_modifier: int, proficiency_bonus: int) -> int:
        """
        Calculate total skill bonus.
        Total = ability_modifier + (proficiency_bonus if proficient) + (proficiency_bonus if expertise) + additional_bonuses
        """
        bonus = ability_modifier + self.additional_bonuses
        if self.proficient:
            bonus += proficiency_bonus
        if self.expertise:
            bonus += proficiency_bonus  # Expertise doubles proficiency
        return bonus


class SavingThrowEntry(BaseModel):
    """Single saving throw with proficiency, expertise, and bonus tracking."""
    proficient: bool = False
    expertise: bool = False  # Rare but some features grant this
    additional_bonuses: int = 0

    def get_total_bonus(self, ability_modifier: int, proficiency_bonus: int) -> int:
        """
        Calculate total saving throw bonus.
        Total = ability_modifier + (proficiency_bonus if proficient) + (proficiency_bonus if expertise) + additional_bonuses
        """
        bonus = ability_modifier + self.additional_bonuses
        if self.proficient:
            bonus += proficiency_bonus
        if self.expertise:
            bonus += proficiency_bonus
        return bonus


class SavingThrows(BaseModel):
    """All six saving throws."""
    strength: SavingThrowEntry = Field(default_factory=SavingThrowEntry)
    dexterity: SavingThrowEntry = Field(default_factory=SavingThrowEntry)
    constitution: SavingThrowEntry = Field(default_factory=SavingThrowEntry)
    intelligence: SavingThrowEntry = Field(default_factory=SavingThrowEntry)
    wisdom: SavingThrowEntry = Field(default_factory=SavingThrowEntry)
    charisma: SavingThrowEntry = Field(default_factory=SavingThrowEntry)

    def get_entry(self, ability: str) -> SavingThrowEntry:
        """Get saving throw entry by ability name."""
        return getattr(self, ability.lower(), SavingThrowEntry())

    def is_proficient(self, ability: str) -> bool:
        """Check if proficient in a saving throw (backward compatibility)."""
        entry = getattr(self, ability.lower(), None)
        return entry.proficient if entry else False


class Skills(BaseModel):
    """All 18 D&D 5e skills."""
    acrobatics: SkillEntry = Field(default_factory=SkillEntry)
    animal_handling: SkillEntry = Field(default_factory=SkillEntry)
    arcana: SkillEntry = Field(default_factory=SkillEntry)
    athletics: SkillEntry = Field(default_factory=SkillEntry)
    deception: SkillEntry = Field(default_factory=SkillEntry)
    history: SkillEntry = Field(default_factory=SkillEntry)
    insight: SkillEntry = Field(default_factory=SkillEntry)
    intimidation: SkillEntry = Field(default_factory=SkillEntry)
    investigation: SkillEntry = Field(default_factory=SkillEntry)
    medicine: SkillEntry = Field(default_factory=SkillEntry)
    nature: SkillEntry = Field(default_factory=SkillEntry)
    perception: SkillEntry = Field(default_factory=SkillEntry)
    performance: SkillEntry = Field(default_factory=SkillEntry)
    persuasion: SkillEntry = Field(default_factory=SkillEntry)
    religion: SkillEntry = Field(default_factory=SkillEntry)
    sleight_of_hand: SkillEntry = Field(default_factory=SkillEntry)
    stealth: SkillEntry = Field(default_factory=SkillEntry)
    survival: SkillEntry = Field(default_factory=SkillEntry)

    def get_entry(self, skill: str) -> SkillEntry:
        """Get skill entry by skill name."""
        return getattr(self, skill.lower().replace(" ", "_"), SkillEntry())

    def is_proficient(self, skill: str) -> bool:
        """Check if proficient in a skill (backward compatibility)."""
        entry = getattr(self, skill.lower().replace(" ", "_"), None)
        return entry.proficient if entry else False


# ==================== Movement & Senses ====================

class SpeedEntry(BaseModel):
    """Speed value with unit."""
    value: int
    unit: str = "ft"


class Speed(BaseModel):
    """All movement types."""
    walk: Optional[SpeedEntry] = None
    fly: Optional[SpeedEntry] = None
    swim: Optional[SpeedEntry] = None
    climb: Optional[SpeedEntry] = None
    burrow: Optional[SpeedEntry] = None

    @property
    def primary_speed(self) -> int:
        """Get walking speed for backward compatibility."""
        return self.walk.value if self.walk else 30


class Senses(BaseModel):
    """Character senses including passive checks."""
    darkvision: Optional[int] = None
    blindsight: Optional[int] = None
    tremorsense: Optional[int] = None
    truesight: Optional[int] = None
    passive_perception: int = 10
    passive_insight: int = 10
    passive_investigation: int = 10


# ==================== Hit Points, Hit Dice, Death Saves ====================

class HitPoints(BaseModel):
    """Character hit points with validation."""
    maximum: int
    current: int
    temporary: int = 0

    @field_validator('current')
    @classmethod
    def validate_current(cls, v, info):
        """Ensure current HP doesn't exceed maximum and is non-negative."""
        max_hp = info.data.get('maximum', 0)
        return max(0, min(v, max_hp))

    # Backward compatibility properties
    @property
    def maximum_hp(self) -> int:
        return self.maximum

    @property
    def current_hp(self) -> int:
        return self.current

    @property
    def temporary_hp(self) -> int:
        return self.temporary

    @property
    def effective_hp(self) -> int:
        """Total HP including temporary HP."""
        return self.current + self.temporary

    @property
    def is_bloodied(self) -> bool:
        """D&D bloodied condition (below 50% HP)."""
        return self.current < self.maximum / 2

    @property
    def is_unconscious(self) -> bool:
        """Character at 0 HP."""
        return self.current <= 0

    @property
    def hp_percentage(self) -> float:
        """Percentage of HP remaining (0.0 to 1.0)."""
        if self.maximum == 0:
            return 0.0
        return self.current / self.maximum


class HitDice(BaseModel):
    """Hit dice tracking."""
    total: int  # total number available (e.g., levels)
    used: int = 0
    die_type: str = "d8"  # Now a string, e.g., "d10" or "4d8, 3d10"

    @property
    def remaining(self) -> int:
        """Number of hit dice remaining."""
        return self.total - self.used


class DeathSaves(BaseModel):
    """Death saving throw tracking."""
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


# ==================== Combat Stats (Consolidated) ====================

class CombatStats(BaseModel):
    """Consolidated combat statistics including HP, hit dice, death saves, and senses."""
    armor_class: int
    initiative_bonus: int
    speed: Speed
    hit_points: HitPoints
    hit_dice: HitDice
    death_saves: DeathSaves
    senses: Senses

    @property
    def initiative(self) -> int:
        """Alias for initiative_bonus for backward compatibility."""
        return self.initiative_bonus


# ==================== Attacks ====================

class Attack(BaseModel):
    """Weapon or spell attack entry."""
    name: str
    attack_bonus: int
    damage: str  # e.g., "1d6 + 4"
    damage_type: str
    notes: Optional[str] = None


# ==================== Equipment & Coins ====================

class EquipmentItem(BaseModel):
    """Single equipment item."""
    name: str
    quantity: int = 1
    weight_lbs: float = 0.0
    description: Optional[str] = None


class Coins(BaseModel):
    """Currency tracking."""
    cp: int = 0  # Copper pieces
    sp: int = 0  # Silver pieces
    ep: int = 0  # Electrum pieces
    gp: int = 0  # Gold pieces
    pp: int = 0  # Platinum pieces

    @property
    def total_gp_value(self) -> float:
        """Total value in gold pieces."""
        return self.cp / 100 + self.sp / 10 + self.ep / 2 + self.gp + self.pp * 10


# ==================== Spellcasting ====================

class SpellSlotLevel(BaseModel):
    """Spell slot tracking for a single level."""
    total: int = 0
    used: int = 0

    @property
    def remaining(self) -> int:
        """Remaining spell slots at this level."""
        return self.total - self.used


class SpellEntry(BaseModel):
    """Full spell entry with all details."""
    name: str
    casting_time: Optional[str] = None
    range: Optional[str] = None
    target: Optional[str] = None
    components: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None
    at_higher_levels: Optional[str] = None


class SpellcastingMeta(BaseModel):
    """Spellcasting statistics and slot tracking."""
    ability: Optional[str] = None  # e.g., "Charisma", "Intelligence"
    save_dc: int = 0
    attack_bonus: int = 0
    slots: Dict[str, SpellSlotLevel] = Field(default_factory=dict)  # "1st", "2nd", etc.

    def has_spell_slot(self, level: int) -> bool:
        """Check if spell slot is available at given level."""
        if level == 0:  # Cantrips don't use slots
            return True
        slot_key = self._level_to_key(level)
        slot = self.slots.get(slot_key)
        if not slot:
            return False
        return slot.remaining > 0

    def use_spell_slot(self, level: int) -> bool:
        """
        Expend a spell slot at given level.
        Returns True if successful, False if no slots available.
        """
        if level == 0:  # Cantrips don't use slots
            return True
        if not self.has_spell_slot(level):
            return False
        slot_key = self._level_to_key(level)
        self.slots[slot_key].used += 1
        return True

    def restore_spell_slots(self, levels: Optional[List[int]] = None):
        """
        Restore spell slots. If levels specified, restore only those levels.
        Otherwise, restore all slots (long rest).
        """
        if levels is None:
            # Long rest - restore all slots
            for slot in self.slots.values():
                slot.used = 0
        else:
            # Restore specific levels
            for level in levels:
                slot_key = self._level_to_key(level)
                if slot_key in self.slots:
                    self.slots[slot_key].used = 0

    def get_remaining_slots(self, level: int) -> int:
        """Get number of remaining spell slots at given level."""
        slot_key = self._level_to_key(level)
        slot = self.slots.get(slot_key)
        return slot.remaining if slot else 0

    @staticmethod
    def _level_to_key(level: int) -> str:
        """Convert spell level to dictionary key."""
        if level == 1:
            return "1st"
        elif level == 2:
            return "2nd"
        elif level == 3:
            return "3rd"
        else:
            return f"{level}th"

    @staticmethod
    def _key_to_level(key: str) -> int:
        """Convert dictionary key to spell level."""
        mapping = {
            "1st": 1, "2nd": 2, "3rd": 3,
            "4th": 4, "5th": 5, "6th": 6,
            "7th": 7, "8th": 8, "9th": 9
        }
        return mapping.get(key, 0)


class Spells(BaseModel):
    """All known/prepared spells organized by level."""
    cantrips: List[SpellEntry] = Field(default_factory=list)
    level_1: List[SpellEntry] = Field(default_factory=list)
    level_2: List[SpellEntry] = Field(default_factory=list)
    level_3: List[SpellEntry] = Field(default_factory=list)
    level_4: List[SpellEntry] = Field(default_factory=list)
    level_5: List[SpellEntry] = Field(default_factory=list)
    level_6: List[SpellEntry] = Field(default_factory=list)
    level_7: List[SpellEntry] = Field(default_factory=list)
    level_8: List[SpellEntry] = Field(default_factory=list)
    level_9: List[SpellEntry] = Field(default_factory=list)

    def get_spells_at_level(self, level: int) -> List[SpellEntry]:
        """Get all spells at a given level."""
        if level == 0:
            return self.cantrips
        attr_name = f"level_{level}"
        return getattr(self, attr_name, [])


# ==================== Character Info ====================

class CharacterInfo(BaseModel):
    """Basic character information."""
    name: str
    alignment: Optional[str] = None  # Now string, not enum
    race: Optional[str] = None  # Now string, not enum
    background: Optional[str] = None
    classes: List[CharacterClassEntry]
    total_level: int
    proficiency_bonus: int
    experience_points: int = 0
    inspiration: bool = False

    @property
    def level(self) -> int:
        """Alias for total_level for backward compatibility."""
        return self.total_level


# ==================== Features & Proficiencies ====================

class FeatureEntry(BaseModel):
    """Character feature or trait."""
    name: str
    source: Optional[str] = None  # e.g., "Rogue Lvl 1", "Half-Elf"
    description: str


class ProficienciesAndLanguages(BaseModel):
    """Proficiencies and languages - now uses strings for flexibility."""
    languages: List[str] = Field(default_factory=list)
    armor: List[str] = Field(default_factory=list)
    weapons: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)


