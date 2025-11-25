"""
Extended tests for state commands - simplified effect system and orchestrator.

Tests:
- ConditionCommand (add/remove conditions)
- EffectCommand (add/remove text-based effects)
- RestCommand (via StateCommandOrchestrator)
- DeathSaveCommand (success/failure/reset)
"""

import pytest
from typing import Dict, Optional

from src.characters.charactersheet import Character
from src.characters.character_components import (
    CharacterInfo,
    AbilityScores,
    HitPoints,
    HitDice,
    DeathSaves,
    CombatStats,
    SavingThrows,
    Skills,
    Spellcasting,
    DurationType,
    Effect,
)
from src.characters.dnd_enums import CharacterClass, Condition, AbilityScore
from src.memory.state_command_executor import (
    StateCommandExecutor,
    CommandExecutionResult,
    BatchExecutionResult,
)
from src.memory.state_command_orchestrator import StateCommandOrchestrator
from src.models.state_commands_optimized import (
    ConditionCommand,
    EffectCommand,
    RestCommand,
    DeathSaveCommand,
)


# ==================== Test Fixtures ====================


@pytest.fixture
def test_character():
    """Create a test character with various capabilities."""
    return Character(
        info=CharacterInfo(
            name="Test Hero",
            player_name=None,
            background=None,
            alignment=None,
            race=None,
            classes=[CharacterClass.FIGHTER],
            level=5,
            experience_points=6500,
            proficiency_bonus=3,
        ),
        ability_scores=AbilityScores(
            strength=16,
            dexterity=14,
            constitution=15,
            intelligence=10,
            wisdom=12,
            charisma=8,
        ),
        saving_throws=SavingThrows(),
        skills=Skills(),
        hit_points=HitPoints(maximum_hp=50, current_hp=30, temporary_hp=0),
        hit_dice=HitDice(total=5, used=2, faces=10),
        death_saves=DeathSaves(),
        combat_stats=CombatStats(armor_class=16, initiative_bonus=2, speed=30),
        spellcasting=Spellcasting(
            spellcasting_ability=AbilityScore.INTELLIGENCE,
            spell_save_dc=14,
            spell_attack_bonus=6,
            spell_slots={1: 4, 2: 3, 3: 2},
            spell_slots_expended={1: 2, 2: 1, 3: 1},
        ),
    )


@pytest.fixture
def character_registry(test_character):
    """Create a simple character registry for testing."""
    registry = {"hero": test_character}
    return lambda char_id: registry.get(char_id)


@pytest.fixture
def executor(character_registry):
    """Create a StateCommandExecutor for testing."""
    return StateCommandExecutor(character_lookup=character_registry)


@pytest.fixture
def orchestrator(executor):
    """Create a StateCommandOrchestrator for testing."""
    return StateCommandOrchestrator(executor)


# ==================== ConditionCommand Tests ====================


class TestConditionCommand:
    """Tests for ConditionCommand (D&D conditions)."""

    def test_add_condition(self, executor, test_character):
        """Test adding a condition to a character."""
        command = ConditionCommand(
            character_id="hero",
            action="add",
            condition=Condition.POISONED,
            duration_type=DurationType.ROUNDS,
            duration=10,
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert "Poisoned" in result.message
        assert len(test_character.active_effects) == 1
        assert test_character.active_effects[0].name == "Poisoned"
        assert test_character.active_effects[0].effect_type == "condition"
        assert test_character.active_effects[0].duration_remaining == 10

    def test_add_duplicate_condition_fails(self, executor, test_character):
        """Test that adding a duplicate condition fails."""
        # Add condition first time
        command = ConditionCommand(
            character_id="hero",
            action="add",
            condition=Condition.STUNNED,
            duration_type=DurationType.ROUNDS,
            duration=3,
        )
        executor.execute_command(command)

        # Try to add same condition again
        result = executor.execute_command(command)

        assert result.success is False
        assert "already active" in result.message
        assert len(test_character.active_effects) == 1  # Still only one

    def test_remove_condition(self, executor, test_character):
        """Test removing a condition from a character."""
        # Add condition
        test_character.add_effect(
            Effect(
                name="Blinded",
                effect_type="condition",
                duration_type=DurationType.ROUNDS,
                duration_remaining=5,
                source="Blinded condition",
                description="Affected by Blinded condition",
                summary="Blinded",
            )
        )

        # Remove condition
        command = ConditionCommand(
            character_id="hero", action="remove", condition=Condition.BLINDED
        )
        result = executor.execute_command(command)

        assert result.success is True
        assert "Removed" in result.message
        assert len(test_character.active_effects) == 0

    def test_remove_nonexistent_condition_fails(self, executor, test_character):
        """Test that removing a non-existent condition fails."""
        command = ConditionCommand(
            character_id="hero", action="remove", condition=Condition.PARALYZED
        )
        result = executor.execute_command(command)

        assert result.success is False
        assert "not found" in result.message

    def test_condition_with_concentration(self, executor, test_character):
        """Test adding a condition with concentration duration."""
        command = ConditionCommand(
            character_id="hero",
            action="add",
            condition=Condition.RESTRAINED,
            duration_type=DurationType.CONCENTRATION,
            duration=10,
        )

        result = executor.execute_command(command)

        assert result.success is True
        effect = test_character.active_effects[0]
        assert effect.duration_type == DurationType.CONCENTRATION
        assert "concentration" in effect.get_description().lower()


# ==================== EffectCommand Tests ====================


class TestEffectCommand:
    """Tests for EffectCommand (text-based effects)."""

    def test_add_effect(self, executor, test_character):
        """Test adding a text-based effect."""
        command = EffectCommand(
            character_id="hero",
            action="add",
            effect_name="Bless",
            duration_type=DurationType.CONCENTRATION,
            duration=10,
            description="Grants +1d4 to attack rolls and saving throws",
            summary="+1d4 attacks/saves",
            effect_type="buff",
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert "Bless" in result.message
        assert len(test_character.active_effects) == 1
        effect = test_character.active_effects[0]
        assert effect.name == "Bless"
        assert effect.description == "Grants +1d4 to attack rolls and saving throws"
        assert effect.summary == "+1d4 attacks/saves"
        assert effect.effect_type == "buff"

    def test_add_effect_without_summary(self, executor, test_character):
        """Test adding an effect without optional summary."""
        command = EffectCommand(
            character_id="hero",
            action="add",
            effect_name="Hunter's Mark",
            duration_type=DurationType.CONCENTRATION,
            duration=60,
            description="Deal an extra 1d6 damage to the marked target",
            effect_type="buff",
        )

        result = executor.execute_command(command)

        assert result.success is True
        effect = test_character.active_effects[0]
        assert effect.summary is None

    def test_add_effect_without_description_fails(self, executor, test_character):
        """Test that adding an effect without description fails."""
        command = EffectCommand(
            character_id="hero",
            action="add",
            effect_name="Mystery Effect",
            duration_type=DurationType.ROUNDS,
            duration=5,
            description=None,  # Missing required field
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "description is required" in result.message

    def test_add_duplicate_effect_fails(self, executor, test_character):
        """Test that adding a duplicate effect fails."""
        command = EffectCommand(
            character_id="hero",
            action="add",
            effect_name="Haste",
            duration_type=DurationType.CONCENTRATION,
            duration=10,
            description="+2 AC, advantage on Dex saves, doubled speed",
            summary="+2 AC, adv Dex, 2x speed",
        )

        executor.execute_command(command)
        result = executor.execute_command(command)  # Try again

        assert result.success is False
        assert "already active" in result.message

    def test_remove_effect(self, executor, test_character):
        """Test removing an effect."""
        # Add effect
        test_character.add_effect(
            Effect(
                name="Fire Resistance",
                effect_type="buff",
                duration_type=DurationType.HOURS,
                duration_remaining=1,
                source="Fire Resistance (buff)",
                description="Resistant to fire damage",
                summary="Resist fire",
            )
        )

        # Remove effect
        command = EffectCommand(
            character_id="hero", action="remove", effect_name="Fire Resistance"
        )
        result = executor.execute_command(command)

        assert result.success is True
        assert "Removed" in result.message
        assert len(test_character.active_effects) == 0

    def test_remove_nonexistent_effect_fails(self, executor, test_character):
        """Test that removing a non-existent effect fails."""
        command = EffectCommand(
            character_id="hero", action="remove", effect_name="Nonexistent Effect"
        )
        result = executor.execute_command(command)

        assert result.success is False
        assert "not found" in result.message

    def test_effect_with_permanent_duration(self, executor, test_character):
        """Test adding an effect with permanent duration."""
        command = EffectCommand(
            character_id="hero",
            action="add",
            effect_name="Darkvision",
            duration_type=DurationType.PERMANENT,
            duration=0,
            description="Can see in dim light and darkness",
            summary="Darkvision 60 ft",
        )

        result = executor.execute_command(command)

        assert result.success is True
        effect = test_character.active_effects[0]
        assert effect.duration_type == DurationType.PERMANENT


# ==================== RestCommand via Orchestrator Tests ====================


class TestRestCommandOrchestrator:
    """Tests for RestCommand expansion via StateCommandOrchestrator."""

    def test_short_rest_with_hit_dice(self, orchestrator, test_character, character_registry):
        """Test short rest with hit dice spending."""
        initial_hp = test_character.hit_points.current_hp
        initial_hit_dice_used = test_character.hit_dice.used

        command = RestCommand(
            character_id="hero", rest_type="short", hit_dice_spent=2
        )

        result = orchestrator.process_and_execute([command], character_registry)

        assert result.all_successful is True
        # HP should have increased (healing)
        assert test_character.hit_points.current_hp > initial_hp
        # Hit dice used should have increased
        assert test_character.hit_dice.used == initial_hit_dice_used + 2

    def test_short_rest_without_hit_dice(self, orchestrator, test_character, character_registry):
        """Test short rest without spending hit dice."""
        initial_hp = test_character.hit_points.current_hp
        initial_hit_dice_used = test_character.hit_dice.used

        command = RestCommand(
            character_id="hero", rest_type="short", hit_dice_spent=0
        )

        result = orchestrator.process_and_execute([command], character_registry)

        assert result.all_successful is True
        # HP should be unchanged (no healing)
        assert test_character.hit_points.current_hp == initial_hp
        # Hit dice should be unchanged
        assert test_character.hit_dice.used == initial_hit_dice_used

    def test_long_rest_full_heal(self, orchestrator, test_character, character_registry):
        """Test long rest heals to full HP."""
        # Character starts at 30/50 HP
        assert test_character.hit_points.current_hp == 30

        command = RestCommand(character_id="hero", rest_type="long")

        result = orchestrator.process_and_execute([command], character_registry)

        assert result.all_successful is True
        # Should be at max HP
        assert test_character.hit_points.current_hp == test_character.hit_points.maximum_hp

    def test_long_rest_restores_hit_dice(self, orchestrator, test_character, character_registry):
        """Test long rest restores half of spent hit dice."""
        # Character has used 2 out of 5 hit dice
        assert test_character.hit_dice.used == 2

        command = RestCommand(character_id="hero", rest_type="long")

        result = orchestrator.process_and_execute([command], character_registry)

        assert result.all_successful is True
        # Should restore 1 hit die (half of 2, minimum 1)
        assert test_character.hit_dice.used == 1

    def test_long_rest_restores_spell_slots(self, orchestrator, test_character, character_registry):
        """Test long rest restores all spell slots."""
        # Character has used spell slots
        initial_used_slots = test_character.spellcasting.spell_slots_expended.copy()
        assert sum(initial_used_slots.values()) > 0

        command = RestCommand(character_id="hero", rest_type="long")

        result = orchestrator.process_and_execute([command], character_registry)

        assert result.all_successful is True
        # All spell slots should be restored
        for level in initial_used_slots:
            assert test_character.spellcasting.spell_slots_expended.get(level, 0) == 0

    def test_long_rest_removes_temporary_effects(
        self, orchestrator, test_character, character_registry
    ):
        """Test long rest removes all temporary effects."""
        # Add temporary effects
        test_character.add_effect(
            Effect(
                name="Bless",
                effect_type="buff",
                duration_type=DurationType.CONCENTRATION,
                duration_remaining=10,
                source="Bless (buff)",
                description="Grants +1d4 to attack rolls",
                summary="+1d4 attacks",
            )
        )
        test_character.add_effect(
            Effect(
                name="Haste",
                effect_type="buff",
                duration_type=DurationType.MINUTES,
                duration_remaining=10,
                source="Haste (buff)",
                description="Doubled speed",
                summary="2x speed",
            )
        )
        # Add permanent effect (should NOT be removed)
        test_character.add_effect(
            Effect(
                name="Darkvision",
                effect_type="buff",
                duration_type=DurationType.PERMANENT,
                duration_remaining=0,
                source="Darkvision (buff)",
                description="Can see in darkness",
                summary="Darkvision",
            )
        )

        assert len(test_character.active_effects) == 3

        command = RestCommand(character_id="hero", rest_type="long")

        result = orchestrator.process_and_execute([command], character_registry)

        assert result.all_successful is True
        # Only permanent effect should remain
        assert len(test_character.active_effects) == 1
        assert test_character.active_effects[0].name == "Darkvision"

    def test_rest_command_reaches_executor_fails(self, executor, test_character):
        """Test that RestCommand reaching executor directly fails with clear message."""
        command = RestCommand(character_id="hero", rest_type="long")

        result = executor.execute_command(command)

        assert result.success is False
        assert "StateCommandOrchestrator" in result.message
        assert "orchestrator.process_and_execute()" in result.message

    def test_rest_command_invalid_character(self, orchestrator, character_registry):
        """Test RestCommand with non-existent character."""
        command = RestCommand(character_id="nonexistent", rest_type="long")

        result = orchestrator.process_and_execute([command], character_registry)

        assert result.failed == 1
        assert "not found" in result.results[0].message

    def test_mixed_commands_with_rest(
        self, orchestrator, test_character, character_registry
    ):
        """Test orchestrator handles mix of RestCommand and atomic commands."""
        from src.models.state_commands_optimized import HPChangeCommand

        commands = [
            HPChangeCommand(character_id="hero", change=-10, change_type="damage"),
            RestCommand(character_id="hero", rest_type="long"),
            EffectCommand(
                character_id="hero",
                action="add",
                effect_name="Bless",
                duration_type=DurationType.CONCENTRATION,
                duration=10,
                description="Grants +1d4",
                summary="+1d4",
            ),
        ]

        result = orchestrator.process_and_execute(commands, character_registry)

        # All should succeed (damage, rest, then add effect)
        assert result.all_successful is True
        # Character should be at full HP after rest
        assert test_character.hit_points.current_hp == test_character.hit_points.maximum_hp
        # Bless should be active
        assert any(e.name == "Bless" for e in test_character.active_effects)


# ==================== DeathSaveCommand Tests ====================


class TestDeathSaveCommand:
    """Tests for DeathSaveCommand (death saving throws)."""

    def test_death_save_success(self, executor, test_character):
        """Test recording a successful death save."""
        command = DeathSaveCommand(
            character_id="hero", result="success", count=1
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert test_character.death_saves.successes == 1
        assert test_character.death_saves.failures == 0

    def test_death_save_failure(self, executor, test_character):
        """Test recording a failed death save."""
        command = DeathSaveCommand(
            character_id="hero", result="failure", count=1
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert test_character.death_saves.failures == 1
        assert test_character.death_saves.successes == 0

    def test_death_save_critical_success(self, executor, test_character):
        """Test recording a critical success (counts as 2)."""
        command = DeathSaveCommand(
            character_id="hero", result="success", count=2
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert test_character.death_saves.successes == 2

    def test_death_save_critical_failure(self, executor, test_character):
        """Test recording a critical failure (counts as 2)."""
        command = DeathSaveCommand(
            character_id="hero", result="failure", count=2
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert test_character.death_saves.failures == 2

    def test_death_save_reset(self, executor, test_character):
        """Test resetting death saves."""
        # Add some saves first
        test_character.death_saves.successes = 2
        test_character.death_saves.failures = 1

        command = DeathSaveCommand(
            character_id="hero", result="reset", count=1
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert test_character.death_saves.successes == 0
        assert test_character.death_saves.failures == 0

    def test_death_save_three_successes(self, executor, test_character):
        """Test reaching 3 successful death saves."""
        commands = [
            DeathSaveCommand(character_id="hero", result="success", count=1),
            DeathSaveCommand(character_id="hero", result="success", count=1),
            DeathSaveCommand(character_id="hero", result="success", count=1),
        ]

        for cmd in commands:
            result = executor.execute_command(cmd)
            assert result.success is True

        assert test_character.death_saves.successes == 3
        # Character is now stable (implementation dependent)

    def test_death_save_three_failures(self, executor, test_character):
        """Test reaching 3 failed death saves."""
        commands = [
            DeathSaveCommand(character_id="hero", result="failure", count=1),
            DeathSaveCommand(character_id="hero", result="failure", count=1),
            DeathSaveCommand(character_id="hero", result="failure", count=1),
        ]

        for cmd in commands:
            result = executor.execute_command(cmd)
            assert result.success is True

        assert test_character.death_saves.failures == 3
        # Character is dead (implementation dependent)
