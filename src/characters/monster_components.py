"""
Monster component models for D&D 5e monster statblocks.

These Pydantic models define the structure for monster data matching the enemy_template.json format.
They are designed to work alongside character_components.py while providing monster-specific
structures for AC, HP, speed, senses, actions, and legendary/mythic abilities.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# === Identity ===

class MonsterMeta(BaseModel):
    """Monster type metadata (size, creature type, alignment)."""
    size: str  # "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"
    type: str  # "humanoid", "dragon", "undead", "fiend", etc.
    alignment: str  # "chaotic evil", "lawful good", "unaligned", etc.


# === Combat Stats ===

class MonsterArmorClass(BaseModel):
    """AC with optional armor type description."""
    value: int
    type: str = ""  # "natural armor", "plate armor", "mage armor", etc.


class MonsterHitPoints(BaseModel):
    """
    HP with formula and runtime state.

    The 'average' is the static HP from the template.
    'current' and 'temporary' track runtime combat state.

    Provides property aliases (current_hp, maximum_hp, temporary_hp) for
    duck typing compatibility with Character's HitPoints class.
    """
    average: int  # From template (e.g., 45)
    formula: str  # Dice formula (e.g., "6d10+12")
    current: int = 0  # Runtime - initialized to average via model_post_init
    temporary: int = 0  # Runtime temporary HP

    def model_post_init(self, __context) -> None:
        """Initialize current HP to average if not set."""
        if self.current == 0:
            self.current = self.average

    @property
    def maximum(self) -> int:
        """Maximum HP (alias for average for duck typing compatibility)."""
        return self.average

    # Duck typing aliases for StateCommandExecutor compatibility
    @property
    def current_hp(self) -> int:
        """Alias for current (duck typing with Character.hit_points)."""
        return self.current

    @property
    def maximum_hp(self) -> int:
        """Alias for maximum (duck typing with Character.hit_points)."""
        return self.average

    @property
    def temporary_hp(self) -> int:
        """Alias for temporary (duck typing with Character.hit_points)."""
        return self.temporary

    @property
    def is_bloodied(self) -> bool:
        """Check if monster is at or below half HP."""
        return self.current <= self.average // 2

    @property
    def is_unconscious(self) -> bool:
        """Check if monster is at 0 HP (typically dead for monsters)."""
        return self.current <= 0


class SpeedEntry(BaseModel):
    """Single speed type with value and unit."""
    value: int = 0
    unit: str = "ft"


class MonsterSpeed(BaseModel):
    """
    Multiple movement types for monsters.

    Supports walk, fly, swim, climb, and burrow speeds.
    """
    walk: SpeedEntry = Field(default_factory=SpeedEntry)
    fly: Optional[SpeedEntry] = None
    swim: Optional[SpeedEntry] = None
    climb: Optional[SpeedEntry] = None
    burrow: Optional[SpeedEntry] = None

    def to_string(self) -> str:
        """Format as '30 ft., fly 60 ft., swim 30 ft.'"""
        parts = []
        if self.walk.value > 0:
            parts.append(f"{self.walk.value} {self.walk.unit}")
        for name, entry in [("fly", self.fly), ("swim", self.swim),
                           ("climb", self.climb), ("burrow", self.burrow)]:
            if entry and entry.value > 0:
                parts.append(f"{name} {entry.value} {entry.unit}")
        return ", ".join(parts) if parts else "0 ft."


class MonsterSenses(BaseModel):
    """
    Monster sense ranges.

    All values in feet. passive_perception is always present.
    """
    darkvision: int = 0
    blindsight: int = 0
    truesight: int = 0
    tremorsense: int = 0
    passive_perception: int = 10

    def to_string(self) -> str:
        """Format as 'darkvision 60 ft., passive Perception 12'"""
        parts = []
        if self.darkvision > 0:
            parts.append(f"darkvision {self.darkvision} ft.")
        if self.blindsight > 0:
            parts.append(f"blindsight {self.blindsight} ft.")
        if self.truesight > 0:
            parts.append(f"truesight {self.truesight} ft.")
        if self.tremorsense > 0:
            parts.append(f"tremorsense {self.tremorsense} ft.")
        parts.append(f"passive Perception {self.passive_perception}")
        return ", ".join(parts)


class ChallengeRating(BaseModel):
    """Challenge rating and XP value."""
    rating: str  # "0", "1/8", "1/4", "1/2", "1", "5", "21", etc.
    xp: int


class DamageModifiers(BaseModel):
    """Damage and condition immunities, resistances, and vulnerabilities."""
    vulnerabilities: List[str] = Field(default_factory=list)  # e.g., ["fire", "radiant"]
    resistances: List[str] = Field(default_factory=list)  # e.g., ["cold", "lightning"]
    immunities: List[str] = Field(default_factory=list)  # e.g., ["poison", "psychic"]
    condition_immunities: List[str] = Field(default_factory=list)  # e.g., ["charmed", "frightened"]


# === Actions ===

class DamageRoll(BaseModel):
    """Damage formula and type for attacks."""
    formula: str  # "2d6+3", "1d8+4", etc.
    type: str  # "slashing", "piercing", "fire", etc.


class AttackRange(BaseModel):
    """Attack range values for melee or ranged attacks."""
    normal: int  # Normal range in feet
    long: int = 0  # Long range for ranged attacks (0 if melee)
    unit: str = "ft"


class MonsterAction(BaseModel):
    """
    Monster action (attack, special ability, etc.).

    Can represent melee attacks, ranged attacks, or special abilities.
    """
    name: str
    description: str
    attack_bonus: Optional[int] = None  # +X to hit
    damage: Optional[DamageRoll] = None
    range: Optional[AttackRange] = None


class MonsterReaction(BaseModel):
    """Monster reaction ability."""
    name: str
    description: str


class MonsterSpecialTrait(BaseModel):
    """
    Monster special trait with flexible extra fields.

    Special traits can have additional fields beyond name and description,
    such as spellcasting details, recharge mechanics, etc. These are captured
    in the extra_fields dictionary.

    Examples:
        - Simple trait: {"name": "Magic Resistance", "description": "..."}
        - Spellcasting: {"name": "Innate Spellcasting", "description": "...",
                         "spellcasting": {"at_will": [...], "per_day": {...}}}
    """
    name: str
    description: str
    extra_fields: Optional[dict] = Field(default=None, description="Additional trait-specific fields")

    @classmethod
    def from_dict(cls, data: dict) -> "MonsterSpecialTrait":
        """
        Create a MonsterSpecialTrait from a dictionary, capturing extra fields.

        Args:
            data: Dictionary with trait data (must have 'name' and 'description')

        Returns:
            MonsterSpecialTrait instance with extra fields stored
        """
        name = data.get("name", "")
        description = data.get("description", "")

        # Capture any extra fields beyond name and description
        extra = {k: v for k, v in data.items() if k not in ("name", "description")}
        extra_fields = extra if extra else None

        return cls(name=name, description=description, extra_fields=extra_fields)

    def to_display_string(self) -> str:
        """Format trait for display, including extra fields if present."""
        lines = [f"***{self.name}.*** {self.description}"]

        if self.extra_fields:
            # Format spellcasting specially
            if "spellcasting" in self.extra_fields:
                spells = self.extra_fields["spellcasting"]
                if "at_will" in spells:
                    lines.append(f"  At will: {', '.join(spells['at_will'])}")
                if "per_day" in spells:
                    for uses, spell_list in spells["per_day"].items():
                        lines.append(f"  {uses}/day each: {', '.join(spell_list)}")
            # Add other extra fields as key: value
            for key, value in self.extra_fields.items():
                if key != "spellcasting":
                    lines.append(f"  {key}: {value}")

        return "\n".join(lines)


class LegendaryAction(BaseModel):
    """Single legendary action option with cost."""
    name: str
    cost: int = 1  # Number of legendary actions consumed
    description: str


class LegendaryActions(BaseModel):
    """Legendary action pool and options."""
    uses: int = 3  # Actions per round
    actions: List[LegendaryAction] = Field(default_factory=list)


class MythicActions(BaseModel):
    """Mythic actions (triggered abilities for mythic monsters)."""
    trigger: str  # Condition that enables mythic actions
    actions: List[MonsterAction] = Field(default_factory=list)
