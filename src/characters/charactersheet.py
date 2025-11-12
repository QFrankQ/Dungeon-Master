from pydantic import BaseModel, model_validator
from typing import List, Optional, Dict
from .character_components import (
    DurationType, Effect, AbilityScores, HitPoints, HitDice, DeathSaves,
    CombatStats, SavingThrows, Skills, CharacterInfo, ProficienciesAndLanguages,
    FeaturesAndTraits, Spellcasting
)

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
