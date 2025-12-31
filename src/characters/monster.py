"""
Monster class for D&D 5e monster statblocks with combat state tracking.

Implements the same combat interface as Character for duck typing compatibility
with StateCommandExecutor, while using monster-specific components for statblock data.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict

from .character_components import AbilityScores, Effect
from .monster_components import (
    MonsterMeta, MonsterArmorClass, MonsterHitPoints, MonsterSpeed, MonsterSenses,
    ChallengeRating, DamageModifiers, MonsterAction, MonsterReaction,
    MonsterSpecialTrait, LegendaryActions, MythicActions
)


class Monster(BaseModel):
    """
    D&D 5e Monster statblock with combat state tracking.

    Implements the same combat interface as Character (take_damage, heal, add_effect, etc.)
    for duck typing compatibility with StateCommandExecutor.
    """

    # Identity - unified with Character
    character_id: str  # Unique ID: "goblin_1", "orc_chief", "ancient_red_dragon"
    name: str  # Display name: "Goblin 1", "Orc Chief", "Ancient Red Dragon"
    meta: MonsterMeta

    # Ability scores - reuse from character_components
    attributes: AbilityScores

    # Combat stats - monster-specific structures
    armor_class: MonsterArmorClass
    hit_points: MonsterHitPoints  # Has .current, .maximum, .temporary for duck typing
    speed: MonsterSpeed
    saving_throws: Dict[str, int] = Field(default_factory=dict)  # ability → total modifier
    skills: Dict[str, int] = Field(default_factory=dict)  # skill → total modifier
    senses: MonsterSenses = Field(default_factory=MonsterSenses)
    languages: List[str] = Field(default_factory=list)
    challenge: ChallengeRating
    proficiency_bonus: int = 2

    # Damage modifiers - monster only
    damage_modifiers: DamageModifiers = Field(default_factory=DamageModifiers)

    # Abilities
    special_traits: List[MonsterSpecialTrait] = Field(default_factory=list)
    actions: List[MonsterAction] = Field(default_factory=list)
    reactions: List[MonsterReaction] = Field(default_factory=list)
    legendary_actions: Optional[LegendaryActions] = None
    mythic_actions: Optional[MythicActions] = None

    # Runtime state (same interface as Character for duck typing)
    active_effects: List[Effect] = Field(default_factory=list)
    legendary_actions_remaining: int = 0

    # ==================== Combat Methods (Duck Typing Interface) ====================

    def take_damage(self, damage: int) -> Dict[str, int]:
        """
        Apply damage to the monster, consuming temporary HP first.

        Args:
            damage: Amount of damage to apply (positive integer)

        Returns:
            Dictionary with damage breakdown (duck typing with Character):
            - temp_absorbed: Damage absorbed by temporary HP
            - actual_damage: Actual HP lost (for StateCommandExecutor compatibility)
            - current_hp: Current HP after damage
        """
        temp_absorbed = min(damage, self.hit_points.temporary)
        self.hit_points.temporary -= temp_absorbed
        remaining = damage - temp_absorbed
        self.hit_points.current = max(0, self.hit_points.current - remaining)
        return {
            "temp_absorbed": temp_absorbed,
            "actual_damage": remaining,
            "current_hp": self.hit_points.current
        }

    def heal(self, amount: int) -> int:
        """
        Heal the monster up to maximum HP.

        Args:
            amount: Amount to heal (positive integer)

        Returns:
            Actual amount healed (may be less if near max HP)
        """
        old_hp = self.hit_points.current
        self.hit_points.current = min(self.hit_points.maximum, self.hit_points.current + amount)
        return self.hit_points.current - old_hp

    def add_temporary_hp(self, amount: int) -> None:
        """
        Add temporary HP (doesn't stack - takes higher value).

        Args:
            amount: Temporary HP to add
        """
        self.hit_points.temporary = max(self.hit_points.temporary, amount)

    # ==================== Effect Methods (Duck Typing Interface) ====================

    def add_effect(self, effect: Effect) -> None:
        """
        Add an effect, replacing existing effect with same name.

        Args:
            effect: Effect to add
        """
        self.remove_effect(effect.name)
        self.active_effects.append(effect)

    def remove_effect(self, effect_name: str) -> bool:
        """
        Remove effect by name (case-insensitive).

        Args:
            effect_name: Name of effect to remove

        Returns:
            True if effect was found and removed, False otherwise
        """
        for i, e in enumerate(self.active_effects):
            if e.name.lower() == effect_name.lower():
                self.active_effects.pop(i)
                return True
        return False

    def has_condition(self, condition_name: str) -> bool:
        """
        Check if monster has a condition (case-insensitive).

        Args:
            condition_name: Name of condition to check

        Returns:
            True if monster has the condition
        """
        return condition_name.lower() in [c.lower() for c in self.conditions]

    @property
    def conditions(self) -> List[str]:
        """
        Get list of active condition names.

        Includes both explicit conditions from active_effects and
        derived conditions (Bloodied, Unconscious).
        """
        conditions = [e.name for e in self.active_effects if e.effect_type == "condition"]
        # Add derived conditions
        if self.hit_points.is_bloodied:
            conditions.append("Bloodied")
        if self.hit_points.is_unconscious:
            conditions.append("Unconscious")
        return conditions

    @property
    def is_unconscious(self) -> bool:
        """Check if monster is unconscious (0 HP). Duck typing with Character."""
        return self.hit_points.is_unconscious

    @property
    def is_bloodied(self) -> bool:
        """Check if monster is bloodied (at or below half HP). Duck typing with Character."""
        return self.hit_points.is_bloodied

    # ==================== Legendary Action Methods ====================

    def use_legendary_action(self, cost: int = 1) -> bool:
        """
        Use legendary action(s).

        Args:
            cost: Number of legendary actions to use

        Returns:
            True if successful, False if not enough actions remaining
        """
        if self.legendary_actions_remaining >= cost:
            self.legendary_actions_remaining -= cost
            return True
        return False

    def reset_legendary_actions(self) -> None:
        """Reset legendary actions to full at start of monster's turn."""
        if self.legendary_actions:
            self.legendary_actions_remaining = self.legendary_actions.uses

    # ==================== Summary Methods ====================

    def get_combat_summary(self) -> str:
        """
        Compact combat summary for DM context.

        Returns a brief overview suitable for combat tracking.
        """
        lines = [
            f"## {self.name} ({self.meta.size} {self.meta.type})",
            f"AC {self.armor_class.value} | HP {self.hit_points.current}/{self.hit_points.maximum}",
            f"CR {self.challenge.rating} ({self.challenge.xp} XP)"
        ]
        if self.hit_points.temporary > 0:
            lines[1] += f" (+{self.hit_points.temporary} temp)"
        if self.conditions:
            lines.append(f"Conditions: {', '.join(self.conditions)}")
        if self.legendary_actions and self.legendary_actions_remaining > 0:
            lines.append(f"Legendary Actions: {self.legendary_actions_remaining}/{self.legendary_actions.uses}")
        return "\n".join(lines)

    def get_full_statblock(self) -> str:
        """
        Full monster statblock in standard format.

        Returns complete statblock suitable for detailed reference.
        """
        lines = []

        # Header
        lines.append(f"# {self.name}")
        lines.append(f"*{self.meta.size} {self.meta.type}, {self.meta.alignment}*")
        lines.append("")

        # Basic stats
        ac_str = f"{self.armor_class.value}"
        if self.armor_class.type:
            ac_str += f" ({self.armor_class.type})"
        lines.append(f"**Armor Class** {ac_str}")
        lines.append(f"**Hit Points** {self.hit_points.current}/{self.hit_points.maximum} ({self.hit_points.formula})")
        lines.append(f"**Speed** {self.speed.to_string()}")
        lines.append("")

        # Ability scores
        lines.append("| STR | DEX | CON | INT | WIS | CHA |")
        lines.append("|:---:|:---:|:---:|:---:|:---:|:---:|")
        scores = self.attributes
        lines.append(
            f"| {scores.strength.score} ({scores.strength.modifier:+d}) "
            f"| {scores.dexterity.score} ({scores.dexterity.modifier:+d}) "
            f"| {scores.constitution.score} ({scores.constitution.modifier:+d}) "
            f"| {scores.intelligence.score} ({scores.intelligence.modifier:+d}) "
            f"| {scores.wisdom.score} ({scores.wisdom.modifier:+d}) "
            f"| {scores.charisma.score} ({scores.charisma.modifier:+d}) |"
        )
        lines.append("")

        # Saving throws
        if self.saving_throws:
            saves = ", ".join(f"{ability.capitalize()} {mod:+d}" for ability, mod in self.saving_throws.items())
            lines.append(f"**Saving Throws** {saves}")

        # Skills
        if self.skills:
            skills = ", ".join(f"{skill.replace('_', ' ').title()} {mod:+d}" for skill, mod in self.skills.items())
            lines.append(f"**Skills** {skills}")

        # Damage modifiers
        if self.damage_modifiers.vulnerabilities:
            lines.append(f"**Damage Vulnerabilities** {', '.join(self.damage_modifiers.vulnerabilities)}")
        if self.damage_modifiers.resistances:
            lines.append(f"**Damage Resistances** {', '.join(self.damage_modifiers.resistances)}")
        if self.damage_modifiers.immunities:
            lines.append(f"**Damage Immunities** {', '.join(self.damage_modifiers.immunities)}")
        if self.damage_modifiers.condition_immunities:
            lines.append(f"**Condition Immunities** {', '.join(self.damage_modifiers.condition_immunities)}")

        # Senses and languages
        lines.append(f"**Senses** {self.senses.to_string()}")
        if self.languages:
            lines.append(f"**Languages** {', '.join(self.languages)}")
        else:
            lines.append("**Languages** —")
        lines.append(f"**Challenge** {self.challenge.rating} ({self.challenge.xp} XP)")
        lines.append(f"**Proficiency Bonus** +{self.proficiency_bonus}")
        lines.append("")

        # Special traits
        if self.special_traits:
            for trait in self.special_traits:
                lines.append(trait.to_display_string())
            lines.append("")

        # Actions
        if self.actions:
            lines.append("## Actions")
            for action in self.actions:
                action_str = f"***{action.name}.*** {action.description}"
                lines.append(action_str)
            lines.append("")

        # Reactions
        if self.reactions:
            lines.append("## Reactions")
            for reaction in self.reactions:
                lines.append(f"***{reaction.name}.*** {reaction.description}")
            lines.append("")

        # Legendary actions
        if self.legendary_actions:
            lines.append("## Legendary Actions")
            lines.append(f"The {self.name.lower()} can take {self.legendary_actions.uses} legendary actions, "
                        "choosing from the options below. Only one legendary action option can be used at a time "
                        "and only at the end of another creature's turn. The creature regains spent legendary "
                        "actions at the start of its turn.")
            lines.append("")
            for la in self.legendary_actions.actions:
                cost_str = f" (Costs {la.cost} Actions)" if la.cost > 1 else ""
                lines.append(f"**{la.name}{cost_str}.** {la.description}")
            lines.append("")

        # Mythic actions
        if self.mythic_actions:
            lines.append("## Mythic Actions")
            lines.append(f"*{self.mythic_actions.trigger}*")
            lines.append("")
            for ma in self.mythic_actions.actions:
                lines.append(f"**{ma.name}.** {ma.description}")

        # Current status
        if self.conditions:
            lines.append("")
            lines.append(f"**Current Conditions:** {', '.join(self.conditions)}")

        return "\n".join(lines)

    def get_actions_detailed(self) -> str:
        """
        Detailed action descriptions for DM reference.

        Returns formatted list of all actions with full details.
        """
        lines = [f"## {self.name} - Actions"]
        lines.append("")

        if self.actions:
            for action in self.actions:
                lines.append(f"### {action.name}")
                if action.attack_bonus is not None:
                    lines.append(f"- **Attack Bonus:** +{action.attack_bonus}")
                if action.damage:
                    lines.append(f"- **Damage:** {action.damage.formula} {action.damage.type}")
                if action.range:
                    range_str = f"{action.range.normal} {action.range.unit}"
                    if action.range.long > 0:
                        range_str += f"/{action.range.long} {action.range.unit}"
                    lines.append(f"- **Range:** {range_str}")
                lines.append(f"- **Description:** {action.description}")
                lines.append("")
        else:
            lines.append("No actions defined.")

        return "\n".join(lines)

    def get_traits_detailed(self) -> str:
        """
        Detailed special trait descriptions.

        Returns formatted list of all special traits.
        """
        lines = [f"## {self.name} - Special Traits"]
        lines.append("")

        if self.special_traits:
            for trait in self.special_traits:
                lines.append(f"### {trait.name}")
                lines.append(trait.description)
                # Include extra fields if present
                if trait.extra_fields:
                    for key, value in trait.extra_fields.items():
                        if key == "spellcasting":
                            lines.append("**Spellcasting:**")
                            if "at_will" in value:
                                lines.append(f"  At will: {', '.join(value['at_will'])}")
                            if "per_day" in value:
                                for uses, spell_list in value["per_day"].items():
                                    lines.append(f"  {uses}/day each: {', '.join(spell_list)}")
                        else:
                            lines.append(f"**{key}:** {value}")
                lines.append("")
        else:
            lines.append("No special traits.")

        return "\n".join(lines)
