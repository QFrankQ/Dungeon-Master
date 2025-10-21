from pydantic import BaseModel, field_validator, model_validator
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

class Character(BaseModel):
    info: CharacterInfo
    ability_scores: AbilityScores
    saving_throws: SavingThrows
    skills: Skills
    hit_points: HitPoints
    hit_dice: HitDice
    death_saves: DeathSaves
    combat_stats: CombatStats
    proficiencies: Optional[ProficienciesAndLanguages] = None
    features: Optional[FeaturesAndTraits] = None
    spellcasting: Optional[Spellcasting] = None
    active_effects: List[Effect] = []  # Replaces simple conditions list

    # ==================== Computed Properties ====================

    @property
    def conditions(self) -> List[str]:
        """Extract condition names from active effects."""
        condition_names = [e.name for e in self.active_effects if e.effect_type == "condition"]

        # Add derived conditions
        if self.hit_points.is_bloodied:
            condition_names.append("Bloodied")
        if self.hit_points.is_unconscious:
            condition_names.append("Unconscious")
        if self.death_saves.is_dead:
            condition_names.append("Dead")
        elif self.death_saves.is_stable:
            condition_names.append("Stable")

        return condition_names

    @property
    def is_bloodied(self) -> bool:
        """Computed from HP - NOT stored as condition."""
        return self.hit_points.is_bloodied

    @property
    def is_unconscious(self) -> bool:
        """Computed from HP - NOT stored as condition."""
        return self.hit_points.is_unconscious

    @property
    def is_dead(self) -> bool:
        """Computed from death saves - NOT stored as condition."""
        return self.death_saves.is_dead

    @property
    def is_stable(self) -> bool:
        """Character has succeeded 3 death saves."""
        return self.death_saves.is_stable

    @property
    def hp(self) -> int:
        """Shortcut to current HP."""
        return self.hit_points.current_hp

    @property
    def ac(self) -> int:
        """Shortcut to armor class."""
        return self.combat_stats.armor_class

    # ==================== Effect Management ====================

    def add_effect(self, effect: Effect):
        """Add a new effect to the character."""
        self.active_effects.append(effect)

    def remove_effect(self, effect_name: str):
        """Remove effect by name."""
        self.active_effects = [e for e in self.active_effects if e.name != effect_name]

    def tick_effects(self, duration_type: DurationType = DurationType.ROUNDS):
        """
        Progress all effects of a certain duration type.
        Removes expired effects automatically.
        """
        self.active_effects = [
            e for e in self.active_effects
            if e.duration_type != duration_type or e.tick()
        ]

    def get_modifier_total(self, stat: str) -> int:
        """Calculate total modifier from all active effects."""
        return sum(e.modifiers.get(stat, 0) for e in self.active_effects)

    def has_condition(self, condition_name: str) -> bool:
        """Check if character has a specific condition (applied or derived)."""
        return condition_name in self.conditions

    # ==================== Ability & Skill Methods ====================

    def get_ability_modifier(self, ability: str) -> int:
        """Get modifier for any ability score."""
        return self.ability_scores.modifiers.get(ability, 0)

    def get_skill_bonus(self, skill: str) -> int:
        """
        Calculate skill check bonus including ability modifier and proficiency.
        """
        # Map skills to abilities
        skill_to_ability = {
            'acrobatics': 'dexterity',
            'animal_handling': 'wisdom',
            'arcana': 'intelligence',
            'athletics': 'strength',
            'deception': 'charisma',
            'history': 'intelligence',
            'insight': 'wisdom',
            'intimidation': 'charisma',
            'investigation': 'intelligence',
            'medicine': 'wisdom',
            'nature': 'intelligence',
            'perception': 'wisdom',
            'performance': 'charisma',
            'persuasion': 'charisma',
            'religion': 'intelligence',
            'sleight_of_hand': 'dexterity',
            'stealth': 'dexterity',
            'survival': 'wisdom',
        }

        ability = skill_to_ability.get(skill, 'strength')
        modifier = self.get_ability_modifier(ability)
        is_proficient = getattr(self.skills, skill, False)

        bonus = modifier
        if is_proficient:
            bonus += self.info.proficiency_bonus

        # Add effect modifiers
        bonus += self.get_modifier_total(f"{skill}_checks")

        return bonus

    def get_saving_throw_bonus(self, ability: str) -> int:
        """Calculate saving throw bonus including proficiency."""
        modifier = self.get_ability_modifier(ability)
        is_proficient = getattr(self.saving_throws, ability, False)

        bonus = modifier
        if is_proficient:
            bonus += self.info.proficiency_bonus

        # Add effect modifiers
        bonus += self.get_modifier_total("saving_throws")
        bonus += self.get_modifier_total(f"{ability}_saves")

        return bonus

    # ==================== Combat & HP Management ====================

    def take_damage(self, damage: int) -> Dict[str, int]:
        """
        Apply damage to character, handling temporary HP first.
        Returns dict with temp_absorbed and actual_damage.
        """
        if damage <= 0:
            return {"temp_absorbed": 0, "actual_damage": 0}

        # Apply to temp HP first
        if self.hit_points.temporary_hp > 0:
            if damage <= self.hit_points.temporary_hp:
                self.hit_points.temporary_hp -= damage
                return {"temp_absorbed": damage, "actual_damage": 0}
            else:
                temp_absorbed = self.hit_points.temporary_hp
                remaining = damage - temp_absorbed
                self.hit_points.temporary_hp = 0
                self.hit_points.current_hp = max(0, self.hit_points.current_hp - remaining)
                return {"temp_absorbed": temp_absorbed, "actual_damage": remaining}
        else:
            self.hit_points.current_hp = max(0, self.hit_points.current_hp - damage)
            return {"temp_absorbed": 0, "actual_damage": damage}

    def heal(self, amount: int):
        """Restore HP, capped at maximum."""
        if amount > 0:
            self.hit_points.current_hp = min(
                self.hit_points.maximum_hp,
                self.hit_points.current_hp + amount
            )

    def add_temporary_hp(self, amount: int):
        """
        Add temporary HP. Temporary HP doesn't stack - take the higher value.
        """
        if amount > self.hit_points.temporary_hp:
            self.hit_points.temporary_hp = amount

    # ==================== Rest Management ====================

    def short_rest(self, hit_dice_to_spend: int = 0) -> int:
        """
        Take a short rest. Optionally spend hit dice to heal.
        Returns HP healed.
        """
        hp_healed = 0

        # Spend hit dice for healing
        if hit_dice_to_spend > 0:
            available = self.hit_dice.total - self.hit_dice.used
            dice_spent = min(hit_dice_to_spend, available)

            for _ in range(dice_spent):
                # Simplified: assume average roll + CON modifier
                con_mod = self.get_ability_modifier('constitution')
                heal_amount = max(1, con_mod)  # Minimum 1 HP per die
                self.heal(heal_amount)
                hp_healed += heal_amount
                self.hit_dice.used += 1

        # Remove short rest duration effects
        self.tick_effects(DurationType.UNTIL_SHORT_REST)

        return hp_healed

    def long_rest(self):
        """
        Take a long rest. Restore HP, half of hit dice, and spell slots.
        """
        # Restore all HP
        self.hit_points.current_hp = self.hit_points.maximum_hp

        # Reset death saves
        self.death_saves.successes = 0
        self.death_saves.failures = 0

        # Restore half of spent hit dice (minimum 1)
        if self.hit_dice.used > 0:
            restored = max(1, self.hit_dice.used // 2)
            self.hit_dice.used = max(0, self.hit_dice.used - restored)

        # Restore spell slots
        if self.spellcasting:
            self.spellcasting.restore_spell_slots()

        # Remove long rest duration effects
        self.tick_effects(DurationType.UNTIL_LONG_REST)

    # ==================== Selective Summary Methods ====================

    def get_combat_summary(self) -> str:
        """Essential combat info - used most frequently."""
        class_names = ", ".join([c.value for c in self.info.classes]) if self.info.classes else "Unknown"
        conditions_str = ", ".join(self.conditions) if self.conditions else "None"

        return f"""{self.info.name} (Level {self.info.level} {class_names})
HP: {self.hit_points.current_hp}/{self.hit_points.maximum_hp} (Temp: {self.hit_points.temporary_hp})
AC: {self.combat_stats.armor_class} | Initiative: +{self.combat_stats.initiative_bonus} | Speed: {self.combat_stats.speed}ft
Active Conditions: {conditions_str}"""

    def get_ability_summary(self) -> str:
        """Ability scores and modifiers."""
        scores = self.ability_scores.model_dump()
        mods = self.ability_scores.modifiers

        return f"""STR {scores['strength']} ({mods['strength']:+d}) | DEX {scores['dexterity']} ({mods['dexterity']:+d}) | CON {scores['constitution']} ({mods['constitution']:+d})
INT {scores['intelligence']} ({mods['intelligence']:+d}) | WIS {scores['wisdom']} ({mods['wisdom']:+d}) | CHA {scores['charisma']} ({mods['charisma']:+d})"""

    def get_effects_summary(self) -> str:
        """Active effects with durations."""
        if not self.active_effects:
            return "No active effects"

        effects_list = [e.get_description() for e in self.active_effects]
        return "Active Effects:\n" + "\n".join([f"- {e}" for e in effects_list])

    def get_spellcasting_summary(self) -> str:
        """Current spell slots and prepared spells."""
        if not self.spellcasting:
            return "No spellcasting"

        slots = []
        for level in range(1, 10):
            remaining = self.spellcasting.get_remaining_slots(level)
            total = self.spellcasting.spell_slots.get(level, 0)
            if total > 0:
                slots.append(f"L{level}: {remaining}/{total}")

        slots_str = " | ".join(slots) if slots else "No spell slots"
        prepared_count = len(self.spellcasting.spells_prepared)

        return f"""Spellcasting Ability: {self.spellcasting.spellcasting_ability.value if self.spellcasting.spellcasting_ability else 'None'}
Spell Save DC: {self.spellcasting.spell_save_dc} | Spell Attack: +{self.spellcasting.spell_attack_bonus}
Spell Slots: {slots_str}
Prepared Spells: {prepared_count}"""

    def get_full_sheet(self) -> str:
        """Complete character sheet."""
        sections = [
            self.get_combat_summary(),
            self.get_ability_summary(),
            self.get_effects_summary(),
        ]

        if self.spellcasting:
            sections.append(self.get_spellcasting_summary())

        return "\n\n".join(sections)

    # ==================== Validator for Automatic Condition Interactions ====================

    @model_validator(mode='after')
    def apply_condition_rules(self):
        """Handle automatic condition interactions per D&D rules."""
        # If unconscious, automatically apply prone (if not already present)
        if self.is_unconscious:
            prone_effect = next((e for e in self.active_effects if e.name == "Prone"), None)
            if not prone_effect:
                self.add_effect(Effect(
                    name="Prone",
                    effect_type="condition",
                    duration_type=DurationType.PERMANENT,
                    duration_remaining=0,
                    source="Unconscious (automatic)"
                ))

        # Remove prone if character is no longer unconscious and prone was auto-applied
        if not self.is_unconscious:
            auto_prone = next(
                (e for e in self.active_effects
                 if e.name == "Prone" and e.source == "Unconscious (automatic)"),
                None
            )
            if auto_prone:
                self.remove_effect("Prone")

        return self
