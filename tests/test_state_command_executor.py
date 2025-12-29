"""
Tests for StateCommandExecutor - applies state commands to character objects.

This test suite verifies that state commands (HPChangeCommand, SpellSlotCommand,
HitDiceCommand) are properly executed and correctly update character state.
"""

import pytest
from typing import Dict, Optional

from src.characters.charactersheet import Character
from src.characters.character_components import (
    CharacterInfo,
    CharacterClassEntry,
    AbilityScores,
    AbilityScoreEntry,
    HitPoints,
    HitDice,
    DeathSaves,
    CombatStats,
    SavingThrows,
    Skills,
    SpellcastingMeta,
    SpellSlotLevel,
    Speed,
    SpeedEntry,
    Senses,
)
from src.characters.dnd_enums import DamageType
from src.memory.state_command_executor import (
    StateCommandExecutor,
    CommandExecutionResult,
    BatchExecutionResult,
)
from src.models.state_commands_optimized import (
    HPChangeCommand,
    SpellSlotCommand,
    HitDiceCommand,
)


# ==================== Test Fixtures ====================


@pytest.fixture
def minimal_character():
    """Create a minimal valid character for basic testing."""
    return Character(
        character_id="test_warrior",
        info=CharacterInfo(
            name="Test Warrior",
            race="Human",
            classes=[CharacterClassEntry(class_name="Fighter", level=5)],
            total_level=5,
            proficiency_bonus=3,
        ),
        ability_scores=AbilityScores(
            strength=AbilityScoreEntry(score=16),
            dexterity=AbilityScoreEntry(score=14),
            constitution=AbilityScoreEntry(score=15),
            intelligence=AbilityScoreEntry(score=10),
            wisdom=AbilityScoreEntry(score=12),
            charisma=AbilityScoreEntry(score=8),
        ),
        saving_throws=SavingThrows(),
        skills=Skills(),
        combat_stats=CombatStats(
            armor_class=16,
            initiative_bonus=2,
            speed=Speed(walk=SpeedEntry(value=30)),
            senses=Senses(),
            hit_points=HitPoints(maximum=50, current=50, temporary=0),
            hit_dice=HitDice(total=5, used=0),
            death_saves=DeathSaves(),
        ),
    )


@pytest.fixture
def spellcaster_character():
    """Create a character with spellcasting abilities."""
    return Character(
        character_id="test_wizard",
        info=CharacterInfo(
            name="Test Wizard",
            race="Human",
            classes=[CharacterClassEntry(class_name="Wizard", level=5)],
            total_level=5,
            proficiency_bonus=3,
        ),
        ability_scores=AbilityScores(
            strength=AbilityScoreEntry(score=8),
            dexterity=AbilityScoreEntry(score=14),
            constitution=AbilityScoreEntry(score=12),
            intelligence=AbilityScoreEntry(score=18),
            wisdom=AbilityScoreEntry(score=12),
            charisma=AbilityScoreEntry(score=10),
        ),
        saving_throws=SavingThrows(),
        skills=Skills(),
        combat_stats=CombatStats(
            armor_class=12,
            initiative_bonus=2,
            speed=Speed(walk=SpeedEntry(value=30)),
            senses=Senses(),
            hit_points=HitPoints(maximum=30, current=30, temporary=0),
            hit_dice=HitDice(total=5, used=0, die_type="d6"),
            death_saves=DeathSaves(),
        ),
        spellcasting_meta=SpellcastingMeta(
            ability="intelligence",
            save_dc=15,
            attack_bonus=7,
            slots={
                "1st": SpellSlotLevel(total=4, used=0),
                "2nd": SpellSlotLevel(total=3, used=0),
                "3rd": SpellSlotLevel(total=2, used=0),
            },
        ),
    )


@pytest.fixture
def character_registry(minimal_character, spellcaster_character):
    """Create a character registry for lookup."""
    return {
        "warrior": minimal_character,
        "wizard": spellcaster_character,
    }


@pytest.fixture
def character_lookup(character_registry):
    """Create a character lookup function for the executor."""
    return lambda char_id: character_registry.get(char_id)


@pytest.fixture
def executor(character_lookup):
    """Create StateCommandExecutor instance."""
    return StateCommandExecutor(character_lookup)


# ==================== HPChangeCommand Tests ====================


class TestHPChangeCommand:
    """Test suite for HPChangeCommand execution."""

    def test_damage_reduces_current_hp(self, executor, minimal_character):
        """Test that damage correctly reduces current HP."""
        initial_hp = minimal_character.hit_points.current_hp

        command = HPChangeCommand(
            character_id="warrior",
            change=-10,
            damage_type=DamageType.SLASHING,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_points.current_hp == initial_hp - 10
        assert "10" in result.message
        assert "slashing" in result.message.lower()
        assert result.details["damage_amount"] == 10
        assert result.details["actual_damage"] == 10

    def test_damage_with_temporary_hp_absorption(self, executor, minimal_character):
        """Test that temporary HP absorbs damage before regular HP."""
        # Grant temporary HP first
        minimal_character.add_temporary_hp(15)
        initial_hp = minimal_character.hit_points.current_hp
        initial_temp_hp = minimal_character.hit_points.temporary_hp

        command = HPChangeCommand(
            character_id="warrior",
            change=-10,
            damage_type=DamageType.PIERCING,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_points.current_hp == initial_hp  # HP unchanged
        assert minimal_character.hit_points.temporary_hp == initial_temp_hp - 10
        assert result.details["temp_hp_absorbed"] == 10
        assert result.details["actual_damage"] == 0

    def test_healing_increases_current_hp(self, executor, minimal_character):
        """Test that healing increases current HP up to maximum."""
        # Damage first
        minimal_character.take_damage(20)
        initial_hp = minimal_character.hit_points.current_hp

        command = HPChangeCommand(
            character_id="warrior",
            change=15,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_points.current_hp == initial_hp + 15
        assert result.details["actual_healing"] == 15
        assert "15" in result.message

    def test_healing_caps_at_maximum_hp(self, executor, minimal_character):
        """Test that healing cannot exceed maximum HP."""
        # Damage first
        minimal_character.take_damage(10)
        max_hp = minimal_character.hit_points.maximum_hp

        command = HPChangeCommand(
            character_id="warrior",
            change=50,  # More than needed to reach max
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_points.current_hp == max_hp
        assert result.details["at_max_hp"] is True

    def test_temporary_hp_grant(self, executor, minimal_character):
        """Test granting temporary HP."""
        command = HPChangeCommand(
            character_id="warrior",
            change=10,
            is_temporary=True,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_points.temporary_hp == 10
        assert result.details["new_temp_hp"] == 10
        assert "temporary HP" in result.message

    def test_temporary_hp_replacement(self, executor, minimal_character):
        """Test that new temporary HP replaces old if higher."""
        # Grant initial temp HP
        minimal_character.add_temporary_hp(5)

        command = HPChangeCommand(
            character_id="warrior",
            change=10,
            is_temporary=True,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_points.temporary_hp == 10  # Replaced, not added

    def test_damage_causing_unconsciousness(self, executor, minimal_character):
        """Test that damage reducing HP to 0 causes unconsciousness."""
        initial_hp = minimal_character.hit_points.current_hp

        command = HPChangeCommand(
            character_id="warrior",
            change=-(initial_hp + 5),  # More than current HP
            damage_type=DamageType.BLUDGEONING,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_points.current_hp == 0
        assert minimal_character.is_unconscious is True
        assert "unconscious" in result.message.lower()
        assert result.details["is_unconscious"] is True

    def test_zero_change_is_noop(self, executor, minimal_character):
        """Test that zero change is a valid no-op."""
        initial_hp = minimal_character.hit_points.current_hp

        command = HPChangeCommand(
            character_id="warrior",
            change=0,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_points.current_hp == initial_hp
        assert "No HP change" in result.message

    def test_character_not_found(self, executor):
        """Test error handling when character doesn't exist."""
        command = HPChangeCommand(
            character_id="nonexistent",
            change=-10,
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "not found" in result.message.lower()


# ==================== SpellSlotCommand Tests ====================


class TestSpellSlotCommand:
    """Test suite for SpellSlotCommand execution."""

    def test_use_spell_slot(self, executor, spellcaster_character):
        """Test using a spell slot."""
        initial_remaining = spellcaster_character.spellcasting_meta.get_remaining_slots(3)

        command = SpellSlotCommand(
            character_id="wizard",
            action="use",
            level=3,
            spell_name="Fireball",
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert spellcaster_character.spellcasting_meta.get_remaining_slots(3) == initial_remaining - 1
        assert "Fireball" in result.message
        assert result.details["spell_name"] == "Fireball"
        assert result.details["level"] == 3

    def test_use_spell_slot_when_none_available(self, executor, spellcaster_character):
        """Test using spell slot when none are available."""
        # Expend all level 3 slots (use the new SpellSlotLevel format)
        spellcaster_character.spellcasting_meta.slots["3rd"].used = 2

        command = SpellSlotCommand(
            character_id="wizard",
            action="use",
            level=3,
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "No level 3 spell slots available" in result.message

    def test_use_spell_slot_non_spellcaster(self, executor, minimal_character):
        """Test using spell slot on non-spellcaster fails."""
        command = SpellSlotCommand(
            character_id="warrior",
            action="use",
            level=1,
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "does not have spellcasting" in result.message

    def test_restore_spell_slot(self, executor, spellcaster_character):
        """Test restoring a spell slot."""
        # Use some slots first
        spellcaster_character.spellcasting_meta.use_spell_slot(2)
        spellcaster_character.spellcasting_meta.use_spell_slot(2)
        initial_remaining = spellcaster_character.spellcasting_meta.get_remaining_slots(2)

        command = SpellSlotCommand(
            character_id="wizard",
            action="restore",
            level=2,
            count=1,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert spellcaster_character.spellcasting_meta.get_remaining_slots(2) == initial_remaining + 1
        assert result.details["actual_restored"] == 1

    def test_restore_when_all_slots_available(self, executor, spellcaster_character):
        """Test restoring slots when all are available fails."""
        command = SpellSlotCommand(
            character_id="wizard",
            action="restore",
            level=1,
            count=1,
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "No level 1 spell slots to restore" in result.message

    def test_restore_more_than_expended(self, executor, spellcaster_character):
        """Test restoring more slots than expended only restores what was used."""
        # Use 1 slot
        spellcaster_character.spellcasting_meta.use_spell_slot(2)
        initial_remaining = spellcaster_character.spellcasting_meta.get_remaining_slots(2)

        command = SpellSlotCommand(
            character_id="wizard",
            action="restore",
            level=2,
            count=5,  # More than expended
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert result.details["requested_count"] == 5
        assert result.details["actual_restored"] == 1
        assert spellcaster_character.spellcasting_meta.get_remaining_slots(2) == initial_remaining + 1

    def test_invalid_spell_level(self, executor, spellcaster_character):
        """Test using spell slot at level character doesn't have."""
        command = SpellSlotCommand(
            character_id="wizard",
            action="use",
            level=9,  # Character only has slots up to level 3
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "no level 9 spell slots" in result.message.lower()

    def test_multiple_slot_usage(self, executor, spellcaster_character):
        """Test using multiple spell slots in sequence."""
        initial_slots = spellcaster_character.spellcasting_meta.get_remaining_slots(1)

        commands = [
            SpellSlotCommand(character_id="wizard", action="use", level=1, spell_name="Magic Missile"),
            SpellSlotCommand(character_id="wizard", action="use", level=1, spell_name="Shield"),
        ]

        batch_result = executor.execute_batch(commands)

        assert batch_result.all_successful is True
        assert spellcaster_character.spellcasting_meta.get_remaining_slots(1) == initial_slots - 2


# ==================== HitDiceCommand Tests ====================


class TestHitDiceCommand:
    """Test suite for HitDiceCommand execution."""

    def test_use_hit_dice(self, executor, minimal_character):
        """Test using hit dice."""
        initial_used = minimal_character.hit_dice.used

        command = HitDiceCommand(
            character_id="warrior",
            action="use",
            count=2,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_dice.used == initial_used + 2
        assert result.details["actual_used"] == 2
        assert "2 hit dice" in result.message

    def test_use_when_none_available(self, executor, minimal_character):
        """Test using hit dice when none are available."""
        # Use all hit dice
        minimal_character.hit_dice.used = minimal_character.hit_dice.total

        command = HitDiceCommand(
            character_id="warrior",
            action="use",
            count=1,
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "No hit dice available" in result.message

    def test_use_more_than_available(self, executor, minimal_character):
        """Test using more hit dice than available only uses what's available."""
        total = minimal_character.hit_dice.total
        minimal_character.hit_dice.used = total - 2  # Only 2 available

        command = HitDiceCommand(
            character_id="warrior",
            action="use",
            count=5,  # More than available
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert result.details["requested_count"] == 5
        assert result.details["actual_used"] == 2
        assert minimal_character.hit_dice.used == total

    def test_restore_hit_dice(self, executor, minimal_character):
        """Test restoring hit dice."""
        # Use some hit dice first
        minimal_character.hit_dice.used = 3
        initial_used = minimal_character.hit_dice.used

        command = HitDiceCommand(
            character_id="warrior",
            action="restore",
            count=2,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert minimal_character.hit_dice.used == initial_used - 2
        assert result.details["actual_restored"] == 2

    def test_restore_when_all_available(self, executor, minimal_character):
        """Test restoring hit dice when all are available fails."""
        command = HitDiceCommand(
            character_id="warrior",
            action="restore",
            count=1,
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "No hit dice to restore" in result.message

    def test_restore_more_than_used(self, executor, minimal_character):
        """Test restoring more hit dice than used only restores what was used."""
        minimal_character.hit_dice.used = 2

        command = HitDiceCommand(
            character_id="warrior",
            action="restore",
            count=5,  # More than used
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert result.details["requested_count"] == 5
        assert result.details["actual_restored"] == 2
        assert minimal_character.hit_dice.used == 0

    def test_use_and_restore_sequence(self, executor, minimal_character):
        """Test using and then restoring hit dice."""
        initial_used = minimal_character.hit_dice.used

        commands = [
            HitDiceCommand(character_id="warrior", action="use", count=3),
            HitDiceCommand(character_id="warrior", action="restore", count=1),
        ]

        batch_result = executor.execute_batch(commands)

        assert batch_result.all_successful is True
        assert minimal_character.hit_dice.used == initial_used + 2  # Used 3, restored 1


# ==================== Batch Execution Tests ====================


class TestBatchExecution:
    """Test suite for batch command execution."""

    def test_execute_multiple_commands(self, executor, minimal_character):
        """Test executing multiple commands in sequence."""
        commands = [
            HPChangeCommand(character_id="warrior", change=-10),
            HitDiceCommand(character_id="warrior", action="use", count=1),
            HPChangeCommand(character_id="warrior", change=5),
        ]

        batch_result = executor.execute_batch(commands)

        assert batch_result.total_commands == 3
        assert batch_result.successful == 3
        assert batch_result.failed == 0
        assert batch_result.all_successful is True

    def test_batch_with_mixed_success_failure(self, executor, minimal_character):
        """Test batch execution with some successes and some failures."""
        commands = [
            HPChangeCommand(character_id="warrior", change=-10),  # Success
            SpellSlotCommand(character_id="warrior", action="use", level=1),  # Fail (no spellcasting)
            HitDiceCommand(character_id="warrior", action="use", count=1),  # Success
        ]

        batch_result = executor.execute_batch(commands)

        assert batch_result.total_commands == 3
        assert batch_result.successful == 2
        assert batch_result.failed == 1
        assert batch_result.all_successful is False

    def test_get_failures(self, executor, minimal_character):
        """Test getting only failed command results."""
        commands = [
            HPChangeCommand(character_id="warrior", change=-10),  # Success
            HPChangeCommand(character_id="nonexistent", change=-10),  # Fail
            HitDiceCommand(character_id="warrior", action="use", count=1),  # Success
        ]

        batch_result = executor.execute_batch(commands)
        failures = batch_result.get_failures()

        assert len(failures) == 1
        assert failures[0].success is False
        assert "not found" in failures[0].message.lower()

    def test_get_successes(self, executor, minimal_character):
        """Test getting only successful command results."""
        commands = [
            HPChangeCommand(character_id="warrior", change=-10),  # Success
            HPChangeCommand(character_id="nonexistent", change=-10),  # Fail
            HitDiceCommand(character_id="warrior", action="use", count=1),  # Success
        ]

        batch_result = executor.execute_batch(commands)
        successes = batch_result.get_successes()

        assert len(successes) == 2
        assert all(r.success for r in successes)

    def test_complex_combat_scenario(self, executor, minimal_character, spellcaster_character):
        """Test a complex combat scenario with multiple characters and commands."""
        commands = [
            # Wizard casts spell
            SpellSlotCommand(character_id="wizard", action="use", level=3, spell_name="Fireball"),
            # Warrior takes damage
            HPChangeCommand(character_id="warrior", change=-15, damage_type=DamageType.FIRE),
            # Wizard takes damage
            HPChangeCommand(character_id="wizard", change=-8, damage_type=DamageType.FIRE),
            # Warrior uses hit dice to heal during short rest
            HitDiceCommand(character_id="warrior", action="use", count=1),
        ]

        batch_result = executor.execute_batch(commands)

        assert batch_result.all_successful is True
        assert spellcaster_character.spellcasting_meta.get_remaining_slots(3) == 1  # Used 1 of 2
        assert minimal_character.combat_stats.hit_points.current == 35  # 50 - 15 damage
        assert spellcaster_character.combat_stats.hit_points.current == 22  # 30 - 8 damage
        assert minimal_character.combat_stats.hit_dice.used == 1
