from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict
from .character_components import (
    DurationType, Effect, CharacterClassEntry, AbilityScores, AbilityScoreEntry,
    SavingThrows, SavingThrowEntry, Skills, SkillEntry, Speed, SpeedEntry, Senses,
    HitPoints, HitDice, DeathSaves, CombatStats, Attack, EquipmentItem, Coins,
    SpellcastingMeta, SpellSlotLevel, Spells, SpellEntry, CharacterInfo,
    FeatureEntry, ProficienciesAndLanguages
)


# Skill to ability mapping for bonus calculations
SKILL_TO_ABILITY = {
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


class Character(BaseModel):
    """
    D&D 5e Character Sheet model with full multiclassing, expertise, and inventory support.

    New structure matches the charactersheet_template.json format with:
    - Multiclass support via CharacterClassEntry objects
    - Ability scores with auto-calculated modifiers
    - Skills/saves with proficiency, expertise, and additional bonuses
    - Consolidated combat_stats with hit_points, hit_dice, death_saves, senses
    - Attacks, equipment, and coins tracking
    - Enhanced spellcasting with full spell entries
    """
    character_id: str  # Unique identifier for state management
    info: CharacterInfo
    ability_scores: AbilityScores
    saving_throws: SavingThrows
    skills: Skills
    combat_stats: CombatStats  # Contains hit_points, hit_dice, death_saves, senses
    attacks_and_spellcasting: List[Attack] = Field(default_factory=list)
    features_and_traits: List[FeatureEntry] = Field(default_factory=list)
    equipment: List[EquipmentItem] = Field(default_factory=list)
    coins: Coins = Field(default_factory=Coins)

    # Spellcasting (new format)
    spellcasting_meta: Optional[SpellcastingMeta] = None
    spells: Optional[Spells] = None

    languages_and_proficiencies: Optional[ProficienciesAndLanguages] = None

    # Runtime state - KEEP
    active_effects: List[Effect] = Field(default_factory=list)

    # ==================== Backward Compatibility Properties ====================

    @property
    def hit_points(self) -> HitPoints:
        """Access hit points from combat_stats for backward compatibility."""
        return self.combat_stats.hit_points

    @property
    def hit_dice(self) -> HitDice:
        """Access hit dice from combat_stats for backward compatibility."""
        return self.combat_stats.hit_dice

    @property
    def death_saves(self) -> DeathSaves:
        """Access death saves from combat_stats for backward compatibility."""
        return self.combat_stats.death_saves

    # ==================== Computed Properties ====================

    @property
    def conditions(self) -> List[str]:
        """Extract condition names from active effects."""
        condition_names = [e.name for e in self.active_effects if e.effect_type == "condition"]

        # Add derived conditions
        if self.combat_stats.hit_points.is_bloodied:
            condition_names.append("Bloodied")
        if self.combat_stats.hit_points.is_unconscious:
            condition_names.append("Unconscious")
        if self.combat_stats.death_saves.is_dead:
            condition_names.append("Dead")
        elif self.combat_stats.death_saves.is_stable:
            condition_names.append("Stable")

        return condition_names

    @property
    def is_bloodied(self) -> bool:
        """Computed from HP - NOT stored as condition."""
        return self.combat_stats.hit_points.is_bloodied

    @property
    def is_unconscious(self) -> bool:
        """Computed from HP - NOT stored as condition."""
        return self.combat_stats.hit_points.is_unconscious

    @property
    def is_dead(self) -> bool:
        """Computed from death saves - NOT stored as condition."""
        return self.combat_stats.death_saves.is_dead

    @property
    def is_stable(self) -> bool:
        """Character has succeeded 3 death saves."""
        return self.combat_stats.death_saves.is_stable

    @property
    def hp(self) -> int:
        """Shortcut to current HP."""
        return self.combat_stats.hit_points.current

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

    def has_condition(self, condition_name: str) -> bool:
        """Check if character has a specific condition (applied or derived)."""
        return condition_name in self.conditions

    # ==================== Ability & Skill Methods ====================

    def get_ability_modifier(self, ability: str) -> int:
        """Get modifier for any ability score."""
        return self.ability_scores.get_modifier(ability)

    def get_skill_bonus(self, skill: str) -> int:
        """
        Calculate skill check bonus including ability modifier and proficiency.
        Auto-calculates total_bonus from ability modifier, proficiency, expertise, and additional bonuses.
        """
        ability = SKILL_TO_ABILITY.get(skill.lower().replace(" ", "_"), 'strength')
        ability_modifier = self.get_ability_modifier(ability)
        proficiency_bonus = self.info.proficiency_bonus

        skill_entry = self.skills.get_entry(skill)
        return skill_entry.get_total_bonus(ability_modifier, proficiency_bonus)

    def get_saving_throw_bonus(self, ability: str) -> int:
        """Calculate saving throw bonus including proficiency."""
        ability_modifier = self.get_ability_modifier(ability)
        proficiency_bonus = self.info.proficiency_bonus

        save_entry = self.saving_throws.get_entry(ability)
        return save_entry.get_total_bonus(ability_modifier, proficiency_bonus)

    # ==================== Combat & HP Management ====================

    def take_damage(self, damage: int) -> Dict[str, int]:
        """
        Apply damage to character, handling temporary HP first.
        Returns dict with temp_absorbed and actual_damage.
        """
        if damage <= 0:
            return {"temp_absorbed": 0, "actual_damage": 0}

        hp = self.combat_stats.hit_points

        # Apply to temp HP first
        if hp.temporary > 0:
            if damage <= hp.temporary:
                hp.temporary -= damage
                return {"temp_absorbed": damage, "actual_damage": 0}
            else:
                temp_absorbed = hp.temporary
                remaining = damage - temp_absorbed
                hp.temporary = 0
                hp.current = max(0, hp.current - remaining)
                return {"temp_absorbed": temp_absorbed, "actual_damage": remaining}
        else:
            hp.current = max(0, hp.current - damage)
            return {"temp_absorbed": 0, "actual_damage": damage}

    def heal(self, amount: int):
        """Restore HP, capped at maximum."""
        if amount > 0:
            hp = self.combat_stats.hit_points
            hp.current = min(hp.maximum, hp.current + amount)

    def add_temporary_hp(self, amount: int):
        """
        Add temporary HP. Temporary HP doesn't stack - take the higher value.
        """
        hp = self.combat_stats.hit_points
        hp.temporary = max(hp.temporary, amount)

    # ==================== Rest Management ====================

    def short_rest(self, hit_dice_to_spend: int = 0) -> int:
        """
        Take a short rest. Optionally spend hit dice to heal.
        Returns HP healed.
        """
        hp_healed = 0
        hit_dice = self.combat_stats.hit_dice

        # Spend hit dice for healing
        if hit_dice_to_spend > 0:
            available = hit_dice.total - hit_dice.used
            dice_spent = min(hit_dice_to_spend, available)

            for _ in range(dice_spent):
                # Simplified: assume average roll + CON modifier
                con_mod = self.get_ability_modifier('constitution')
                heal_amount = max(1, con_mod)  # Minimum 1 HP per die
                self.heal(heal_amount)
                hp_healed += heal_amount
                hit_dice.used += 1

        # Remove short rest duration effects
        self.tick_effects(DurationType.UNTIL_SHORT_REST)

        return hp_healed

    def long_rest(self):
        """
        Take a long rest. Restore HP, half of hit dice, and spell slots.
        """
        hp = self.combat_stats.hit_points
        hit_dice = self.combat_stats.hit_dice
        death_saves = self.combat_stats.death_saves

        # Restore all HP
        hp.current = hp.maximum

        # Reset death saves
        death_saves.successes = 0
        death_saves.failures = 0

        # Restore half of spent hit dice (minimum 1)
        if hit_dice.used > 0:
            restored = max(1, hit_dice.used // 2)
            hit_dice.used = max(0, hit_dice.used - restored)

        # Restore spell slots
        if self.spellcasting_meta:
            self.spellcasting_meta.restore_spell_slots()

        # Remove long rest duration effects
        self.tick_effects(DurationType.UNTIL_LONG_REST)

    # ==================== Selective Summary Methods ====================

    def get_combat_summary(self) -> str:
        """Essential combat info - used most frequently."""
        classes_str = ", ".join([
            f"{c.class_name}" + (f" ({c.subclass})" if c.subclass else "")
            for c in self.info.classes
        ]) if self.info.classes else "Unknown"
        conditions_str = ", ".join(self.conditions) if self.conditions else "None"

        hp = self.combat_stats.hit_points
        speed_str = f"{self.combat_stats.speed.primary_speed}ft"

        return f"""{self.info.name} (Level {self.info.total_level} {classes_str})
HP: {hp.current}/{hp.maximum} (Temp: {hp.temporary})
AC: {self.combat_stats.armor_class} | Initiative: +{self.combat_stats.initiative_bonus} | Speed: {speed_str}
Active Conditions: {conditions_str}"""

    def get_ability_summary(self) -> str:
        """Ability scores and modifiers."""
        lines = []
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            entry = getattr(self.ability_scores, ability)
            lines.append(f"{ability.upper()[:3]} {entry.score} ({entry.modifier:+d})")

        return " | ".join(lines[:3]) + "\n" + " | ".join(lines[3:])

    def get_effects_summary(self) -> str:
        """Active effects with durations."""
        if not self.active_effects:
            return "No active effects"

        effects_list = [e.get_description() for e in self.active_effects]
        return "Active Effects:\n" + "\n".join([f"- {e}" for e in effects_list])

    def get_spellcasting_summary(self) -> str:
        """Current spell slots and prepared spells."""
        if not self.spellcasting_meta:
            return "No spellcasting"

        slots = []
        for level in range(1, 10):
            remaining = self.spellcasting_meta.get_remaining_slots(level)
            slot_key = self.spellcasting_meta._level_to_key(level)
            slot = self.spellcasting_meta.slots.get(slot_key)
            total = slot.total if slot else 0
            if total > 0:
                slots.append(f"L{level}: {remaining}/{total}")

        slots_str = " | ".join(slots) if slots else "No spell slots"

        # Count prepared spells from spells object
        prepared_count = 0
        if self.spells:
            for level in range(0, 10):
                prepared_count += len(self.spells.get_spells_at_level(level))

        return f"""Spellcasting Ability: {self.spellcasting_meta.ability or 'None'}
Spell Save DC: {self.spellcasting_meta.save_dc} | Spell Attack: +{self.spellcasting_meta.attack_bonus}
Spell Slots: {slots_str}
Prepared Spells: {prepared_count}"""

    def get_attacks_summary(self) -> str:
        """List of attacks with bonuses and damage."""
        if not self.attacks_and_spellcasting:
            return "No attacks"

        lines = ["Attacks:"]
        for attack in self.attacks_and_spellcasting:
            line = f"  {attack.name}: +{attack.attack_bonus} to hit, {attack.damage} {attack.damage_type}"
            if attack.notes:
                line += f" ({attack.notes})"
            lines.append(line)
        return "\n".join(lines)

    def get_equipment_summary(self) -> str:
        """Equipment and coins summary."""
        lines = []

        if self.equipment:
            lines.append("Equipment:")
            for item in self.equipment:
                qty = f" x{item.quantity}" if item.quantity > 1 else ""
                lines.append(f"  {item.name}{qty}")

        coin_parts = []
        coin_parts.append(f"{self.coins.pp} pp")
        coin_parts.append(f"{self.coins.gp} gp")
        coin_parts.append(f"{self.coins.sp} sp")    
        coin_parts.append(f"{self.coins.cp} cp")

        if coin_parts:
            lines.append(f"Coins: {', '.join(coin_parts)}")

        return "\n".join(lines) if lines else "No equipment"

    def get_saving_throws_summary(self) -> str:
        """Saving throw bonuses with proficiency markers."""
        lines = ["Saving Throws:"]
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            entry = self.saving_throws.get_entry(ability)
            ability_mod = self.get_ability_modifier(ability)
            total = entry.get_total_bonus(ability_mod, self.info.proficiency_bonus)
            prof_marker = "●" if entry.proficient else "○"
            lines.append(f"  {prof_marker} {ability.upper()[:3]}: {total:+d}")
        return "\n".join(lines)

    def get_skills_summary(self) -> str:
        """Skills with proficiency and expertise markers."""
        lines = ["Skills:"]
        for skill_name in SKILL_TO_ABILITY.keys():
            entry = self.skills.get_entry(skill_name)
            ability = SKILL_TO_ABILITY[skill_name]
            ability_mod = self.get_ability_modifier(ability)
            total = entry.get_total_bonus(ability_mod, self.info.proficiency_bonus)

            # Marker: ◆ for expertise, ● for proficient, ○ for neither
            if entry.expertise:
                marker = "◆"
            elif entry.proficient:
                marker = "●"
            else:
                marker = "○"

            # Format skill name nicely
            display_name = skill_name.replace("_", " ").title()
            lines.append(f"  {marker} {display_name}: {total:+d}")
        return "\n".join(lines)

    def get_hit_dice_summary(self) -> str:
        """Hit dice availability."""
        hd = self.combat_stats.hit_dice
        available = hd.total - hd.used
        return f"Hit Dice: {available}/{hd.total} {hd.die_type}"

    def get_death_saves_summary(self) -> str:
        """Death save status."""
        ds = self.combat_stats.death_saves
        if ds.is_dead:
            return "Death Saves: DEAD (3 failures)"
        if ds.is_stable:
            return "Death Saves: STABLE (3 successes)"
        if ds.successes == 0 and ds.failures == 0:
            return "Death Saves: None"

        success_display = "●" * ds.successes + "○" * (3 - ds.successes)
        failure_display = "●" * ds.failures + "○" * (3 - ds.failures)
        return f"Death Saves: Successes [{success_display}] Failures [{failure_display}]"

    def get_senses_summary(self) -> str:
        """Senses including darkvision and passive scores."""
        senses = self.combat_stats.senses
        parts = []

        if senses.darkvision and senses.darkvision > 0:
            parts.append(f"Darkvision {senses.darkvision} ft")
        if senses.blindsight and senses.blindsight > 0:
            parts.append(f"Blindsight {senses.blindsight} ft")
        if senses.tremorsense and senses.tremorsense > 0:
            parts.append(f"Tremorsense {senses.tremorsense} ft")
        if senses.truesight and senses.truesight > 0:
            parts.append(f"Truesight {senses.truesight} ft")

        parts.append(f"Passive Perception {senses.passive_perception}")
        parts.append(f"Passive Insight {senses.passive_insight}")
        parts.append(f"Passive Investigation {senses.passive_investigation}")

        return "Senses: " + ", ".join(parts)

    def get_features_summary(self) -> str:
        """Features and traits list."""
        if not self.features_and_traits:
            return "No features or traits"

        lines = ["Features & Traits:"]
        for feature in self.features_and_traits:
            source_str = f" ({feature.source})" if feature.source else ""
            lines.append(f"  • {feature.name}{source_str}")
        return "\n".join(lines)

    def get_spells_summary(self) -> str:
        """List of known/prepared spells by level."""
        if not self.spells:
            return "No spells"

        lines = ["Spells:"]

        # Cantrips
        cantrips = self.spells.get_spells_at_level(0)
        if cantrips:
            spell_names = ", ".join(s.name for s in cantrips)
            lines.append(f"  Cantrips: {spell_names}")

        # Leveled spells
        for level in range(1, 10):
            spells_at_level = self.spells.get_spells_at_level(level)
            if spells_at_level:
                spell_names = ", ".join(s.name for s in spells_at_level)
                lines.append(f"  Level {level}: {spell_names}")

        return "\n".join(lines) if len(lines) > 1 else "No spells prepared"

    def get_languages_summary(self) -> str:
        """Languages and proficiencies."""
        if not self.languages_and_proficiencies:
            return "No languages or proficiencies recorded"

        lines = []
        lp = self.languages_and_proficiencies

        if lp.languages:
            lines.append(f"Languages: {', '.join(lp.languages)}")
        if lp.armor:
            lines.append(f"Armor: {', '.join(lp.armor)}")
        if lp.weapons:
            lines.append(f"Weapons: {', '.join(lp.weapons)}")
        if lp.tools:
            lines.append(f"Tools: {', '.join(lp.tools)}")

        return "\n".join(lines) if lines else "No proficiencies recorded"

    # ==================== Detailed Summary Methods (with descriptions) ====================

    def get_attacks_detailed(self) -> str:
        """Detailed attacks with full notes and descriptions for DM reference."""
        if not self.attacks_and_spellcasting:
            return "No attacks"

        lines = ["═══ ATTACKS & SPELLCASTING ═══"]
        for attack in self.attacks_and_spellcasting:
            lines.append(f"\n▸ {attack.name}")
            lines.append(f"  Attack Bonus: +{attack.attack_bonus}")
            lines.append(f"  Damage: {attack.damage} {attack.damage_type}")
            if attack.notes:
                lines.append(f"  Notes: {attack.notes}")
        return "\n".join(lines)

    def get_features_detailed(self) -> str:
        """Detailed features and traits with full descriptions for DM reference."""
        if not self.features_and_traits:
            return "No features or traits"

        lines = ["═══ FEATURES & TRAITS ═══"]
        for feature in self.features_and_traits:
            lines.append(f"\n▸ {feature.name}")
            if feature.source:
                lines.append(f"  Source: {feature.source}")
            if feature.description:
                # Wrap description text for readability
                desc_lines = feature.description.split('\n')
                for desc_line in desc_lines:
                    lines.append(f"  {desc_line}")
        return "\n".join(lines)

    def get_spells_detailed(self) -> str:
        """Detailed spell list with casting time, range, components, duration, and description."""
        if not self.spells:
            return "No spells"

        lines = ["═══ SPELLBOOK ═══"]

        # Helper to format a single spell
        def format_spell(spell: 'SpellEntry', level_label: str) -> list:
            spell_lines = [f"\n▸ {spell.name} ({level_label})"]
            if spell.casting_time:
                spell_lines.append(f"  Casting Time: {spell.casting_time}")
            if spell.range:
                spell_lines.append(f"  Range: {spell.range}")
            if spell.target:
                spell_lines.append(f"  Target: {spell.target}")
            if spell.components:
                spell_lines.append(f"  Components: {spell.components}")
            if spell.duration:
                spell_lines.append(f"  Duration: {spell.duration}")
            if spell.description:
                spell_lines.append(f"  Description: {spell.description}")
            if spell.at_higher_levels:
                spell_lines.append(f"  At Higher Levels: {spell.at_higher_levels}")
            return spell_lines

        # Cantrips
        cantrips = self.spells.get_spells_at_level(0)
        if cantrips:
            lines.append("\n── Cantrips ──")
            for spell in cantrips:
                lines.extend(format_spell(spell, "Cantrip"))

        # Leveled spells
        level_names = {
            1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th",
            6: "6th", 7: "7th", 8: "8th", 9: "9th"
        }
        for level in range(1, 10):
            spells_at_level = self.spells.get_spells_at_level(level)
            if spells_at_level:
                lines.append(f"\n── {level_names[level]} Level ──")
                for spell in spells_at_level:
                    lines.extend(format_spell(spell, f"{level_names[level]} level"))

        return "\n".join(lines) if len(lines) > 1 else "No spells prepared"

    def get_equipment_detailed(self) -> str:
        """Detailed equipment list with descriptions and weights."""
        lines = ["═══ EQUIPMENT & INVENTORY ═══"]

        if self.equipment:
            for item in self.equipment:
                qty = f" (×{item.quantity})" if item.quantity > 1 else ""
                weight = f" [{item.weight_lbs} lb]" if item.weight_lbs > 0 else ""
                lines.append(f"\n▸ {item.name}{qty}{weight}")
                if item.description:
                    desc_lines = item.description.split('\n')
                    for desc_line in desc_lines:
                        lines.append(f"  {desc_line}")

            # Total weight calculation
            total_weight = sum(item.weight_lbs * item.quantity for item in self.equipment)
            if total_weight > 0:
                lines.append(f"\nTotal Weight: {total_weight:.1f} lb")

        # Coins
        lines.append("\n── Coins ──")
        lines.append(f"  Platinum (pp): {self.coins.pp}")
        lines.append(f"  Gold (gp): {self.coins.gp}")
        lines.append(f"  Silver (sp): {self.coins.sp}")
        lines.append(f"  Copper (cp): {self.coins.cp}")
        lines.append(f"  Total Value: {self.coins.total_gp_value:.2f} gp")

        return "\n".join(lines) if len(lines) > 1 else "No equipment"

    def get_full_sheet_detailed(self) -> str:
        """Complete character sheet with full descriptions for DM reference."""
        sections = [
            self.get_combat_summary(),
            self.get_ability_summary(),
            self.get_saving_throws_summary(),
            self.get_skills_summary(),
            self.get_effects_summary(),
        ]

        if self.attacks_and_spellcasting:
            sections.append(self.get_attacks_detailed())

        if self.spellcasting_meta:
            sections.append(self.get_spellcasting_summary())

        if self.spells:
            sections.append(self.get_spells_detailed())

        if self.features_and_traits:
            sections.append(self.get_features_detailed())

        if self.equipment or self.coins.total_gp_value > 0:
            sections.append(self.get_equipment_detailed())

        # Additional info sections
        sections.append(self.get_hit_dice_summary())
        sections.append(self.get_death_saves_summary())
        sections.append(self.get_senses_summary())

        if self.languages_and_proficiencies:
            sections.append(self.get_languages_summary())

        return "\n\n".join(sections)

    def get_full_sheet(self) -> str:
        """Complete character sheet."""
        sections = [
            self.get_combat_summary(),
            self.get_ability_summary(),
            self.get_saving_throws_summary(),
            self.get_skills_summary(),
            self.get_effects_summary(),
        ]

        if self.attacks_and_spellcasting:
            sections.append(self.get_attacks_summary())

        if self.spellcasting_meta:
            sections.append(self.get_spellcasting_summary())

        if self.spells:
            sections.append(self.get_spells_summary())

        if self.features_and_traits:
            sections.append(self.get_features_summary())

        if self.equipment or self.coins.total_gp_value > 0:
            sections.append(self.get_equipment_summary())

        # Additional info sections
        sections.append(self.get_hit_dice_summary())
        sections.append(self.get_death_saves_summary())
        sections.append(self.get_senses_summary())

        if self.languages_and_proficiencies:
            sections.append(self.get_languages_summary())

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
