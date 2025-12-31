"""
Tests for Monster class and StateManager monster support.

This test suite verifies:
1. Monster class creation and validation
2. Monster combat methods (take_damage, heal, add_temporary_hp)
3. Monster effect methods (add_effect, remove_effect, has_condition)
4. StateCommandExecutor duck typing compatibility with Monster
5. StateManager monster management (add_monster, get_character_by_id, etc.)
"""

import pytest
from typing import Dict, Optional

from src.characters.monster import Monster
from src.characters.monster_components import (
    MonsterMeta,
    MonsterArmorClass,
    MonsterHitPoints,
    MonsterSpeed,
    MonsterSenses,
    ChallengeRating,
    DamageModifiers,
    MonsterAction,
    MonsterSpecialTrait,
    DamageRoll,
    AttackRange,
    SpeedEntry,
)
from src.characters.character_components import (
    AbilityScores,
    AbilityScoreEntry,
    Effect,
    DurationType,
)
from src.characters.dnd_enums import DamageType
from src.memory.state_command_executor import StateCommandExecutor
from src.memory.state_manager import StateManager
from src.models.state_commands_optimized import HPChangeCommand


# ==================== Test Fixtures ====================


@pytest.fixture
def goblin():
    """Create a basic goblin monster for testing."""
    return Monster(
        character_id="goblin_1",
        name="Goblin 1",
        meta=MonsterMeta(
            size="Small",
            type="humanoid",
            alignment="neutral evil"
        ),
        attributes=AbilityScores(
            strength=AbilityScoreEntry(score=8),
            dexterity=AbilityScoreEntry(score=14),
            constitution=AbilityScoreEntry(score=10),
            intelligence=AbilityScoreEntry(score=10),
            wisdom=AbilityScoreEntry(score=8),
            charisma=AbilityScoreEntry(score=8),
        ),
        armor_class=MonsterArmorClass(value=15, type="leather armor, shield"),
        hit_points=MonsterHitPoints(average=7, formula="2d6"),
        speed=MonsterSpeed(walk=SpeedEntry(value=30)),
        senses=MonsterSenses(darkvision=60, passive_perception=9),
        languages=["Common", "Goblin"],
        challenge=ChallengeRating(rating="1/4", xp=50),
        proficiency_bonus=2,
        skills={"stealth": 6},
        actions=[
            MonsterAction(
                name="Scimitar",
                description="Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.",
                attack_bonus=4,
                damage=DamageRoll(formula="1d6+2", type="slashing"),
                range=AttackRange(normal=5)
            ),
            MonsterAction(
                name="Shortbow",
                description="Ranged Weapon Attack: +4 to hit, range 80/320 ft., one target. Hit: 5 (1d6 + 2) piercing damage.",
                attack_bonus=4,
                damage=DamageRoll(formula="1d6+2", type="piercing"),
                range=AttackRange(normal=80, long=320)
            )
        ],
        special_traits=[
            MonsterSpecialTrait(
                name="Nimble Escape",
                description="The goblin can take the Disengage or Hide action as a bonus action on each of its turns."
            )
        ]
    )


@pytest.fixture
def orc_chief():
    """Create an orc chief monster with more HP for damage testing."""
    return Monster(
        character_id="orc_chief",
        name="Orc Chief",
        meta=MonsterMeta(
            size="Medium",
            type="humanoid",
            alignment="chaotic evil"
        ),
        attributes=AbilityScores(
            strength=AbilityScoreEntry(score=18),
            dexterity=AbilityScoreEntry(score=12),
            constitution=AbilityScoreEntry(score=16),
            intelligence=AbilityScoreEntry(score=10),
            wisdom=AbilityScoreEntry(score=11),
            charisma=AbilityScoreEntry(score=12),
        ),
        armor_class=MonsterArmorClass(value=16, type="chain mail"),
        hit_points=MonsterHitPoints(average=45, formula="6d8+18"),
        speed=MonsterSpeed(walk=SpeedEntry(value=30)),
        senses=MonsterSenses(darkvision=60, passive_perception=10),
        languages=["Common", "Orc"],
        challenge=ChallengeRating(rating="3", xp=700),
        proficiency_bonus=2,
        saving_throws={"strength": 6, "constitution": 5},
        actions=[
            MonsterAction(
                name="Greataxe",
                description="Melee Weapon Attack: +6 to hit, reach 5 ft., one target. Hit: 10 (1d12 + 4) slashing damage.",
                attack_bonus=6,
                damage=DamageRoll(formula="1d12+4", type="slashing"),
                range=AttackRange(normal=5)
            )
        ]
    )


# ==================== Monster Creation Tests ====================


class TestMonsterCreation:
    """Test suite for Monster class creation and validation."""

    def test_create_minimal_monster(self, goblin):
        """Test creating a monster with minimal required fields."""
        assert goblin.character_id == "goblin_1"
        assert goblin.name == "Goblin 1"
        assert goblin.meta.size == "Small"
        assert goblin.meta.type == "humanoid"

    def test_monster_hp_initialization(self, goblin):
        """Test that current HP is initialized to average."""
        assert goblin.hit_points.average == 7
        assert goblin.hit_points.current == 7
        assert goblin.hit_points.maximum == 7
        assert goblin.hit_points.temporary == 0

    def test_monster_has_character_id(self, goblin):
        """Test that Monster has character_id for duck typing."""
        assert hasattr(goblin, 'character_id')
        assert goblin.character_id == "goblin_1"

    def test_monster_actions_exist(self, goblin):
        """Test that monster has actions defined."""
        assert len(goblin.actions) == 2
        assert goblin.actions[0].name == "Scimitar"
        assert goblin.actions[1].name == "Shortbow"

    def test_monster_special_traits(self, goblin):
        """Test that monster has special traits defined."""
        assert len(goblin.special_traits) == 1
        assert goblin.special_traits[0].name == "Nimble Escape"


# ==================== Monster Combat Methods Tests ====================


class TestMonsterCombatMethods:
    """Test suite for Monster combat methods (duck typing interface)."""

    def test_take_damage_reduces_hp(self, orc_chief):
        """Test that take_damage reduces current HP."""
        initial_hp = orc_chief.hit_points.current
        result = orc_chief.take_damage(10)

        assert orc_chief.hit_points.current == initial_hp - 10
        assert result["actual_damage"] == 10
        assert result["temp_absorbed"] == 0
        assert result["current_hp"] == initial_hp - 10

    def test_take_damage_absorbs_temp_hp_first(self, orc_chief):
        """Test that temporary HP absorbs damage before regular HP."""
        orc_chief.add_temporary_hp(15)
        initial_hp = orc_chief.hit_points.current

        result = orc_chief.take_damage(10)

        assert orc_chief.hit_points.current == initial_hp  # HP unchanged
        assert orc_chief.hit_points.temporary == 5  # 15 - 10
        assert result["temp_absorbed"] == 10
        assert result["actual_damage"] == 0

    def test_take_damage_overflow_to_hp(self, orc_chief):
        """Test that damage overflows from temp HP to regular HP."""
        orc_chief.add_temporary_hp(5)
        initial_hp = orc_chief.hit_points.current

        result = orc_chief.take_damage(10)

        assert orc_chief.hit_points.temporary == 0
        assert orc_chief.hit_points.current == initial_hp - 5  # 10 - 5 temp
        assert result["temp_absorbed"] == 5
        assert result["actual_damage"] == 5

    def test_take_damage_cannot_go_below_zero(self, goblin):
        """Test that HP cannot go below 0."""
        result = goblin.take_damage(100)

        assert goblin.hit_points.current == 0
        assert result["current_hp"] == 0

    def test_heal_increases_hp(self, orc_chief):
        """Test that heal increases current HP."""
        orc_chief.take_damage(20)
        initial_hp = orc_chief.hit_points.current

        actual_healed = orc_chief.heal(10)

        assert orc_chief.hit_points.current == initial_hp + 10
        assert actual_healed == 10

    def test_heal_caps_at_maximum(self, orc_chief):
        """Test that healing cannot exceed maximum HP."""
        orc_chief.take_damage(10)
        max_hp = orc_chief.hit_points.maximum

        actual_healed = orc_chief.heal(50)

        assert orc_chief.hit_points.current == max_hp
        assert actual_healed == 10  # Only healed what was missing

    def test_add_temporary_hp(self, goblin):
        """Test adding temporary HP."""
        goblin.add_temporary_hp(10)
        assert goblin.hit_points.temporary == 10

    def test_temporary_hp_takes_higher(self, goblin):
        """Test that temporary HP takes the higher value, doesn't stack."""
        goblin.add_temporary_hp(5)
        goblin.add_temporary_hp(10)
        assert goblin.hit_points.temporary == 10

        goblin.add_temporary_hp(3)  # Lower, should not change
        assert goblin.hit_points.temporary == 10


# ==================== Monster Effect Methods Tests ====================


class TestMonsterEffectMethods:
    """Test suite for Monster effect methods."""

    def test_add_effect(self, goblin):
        """Test adding an effect to monster."""
        effect = Effect(
            name="Bless",
            description="+1d4 to attack rolls and saving throws",
            duration_type=DurationType.CONCENTRATION,
            duration_remaining=10,
            effect_type="buff",
            source="Cleric"
        )
        goblin.add_effect(effect)

        assert len(goblin.active_effects) == 1
        assert goblin.active_effects[0].name == "Bless"

    def test_add_effect_replaces_same_name(self, goblin):
        """Test that adding effect with same name replaces it."""
        effect1 = Effect(
            name="Hex",
            duration_type=DurationType.CONCENTRATION,
            duration_remaining=10,
            effect_type="debuff",
            source="Warlock"
        )
        effect2 = Effect(
            name="Hex",
            duration_type=DurationType.CONCENTRATION,
            duration_remaining=20,
            effect_type="debuff",
            source="Warlock"
        )

        goblin.add_effect(effect1)
        goblin.add_effect(effect2)

        assert len(goblin.active_effects) == 1
        assert goblin.active_effects[0].duration_remaining == 20

    def test_remove_effect(self, goblin):
        """Test removing an effect from monster."""
        effect = Effect(
            name="Poisoned",
            effect_type="condition",
            duration_type=DurationType.ROUNDS,
            duration_remaining=10,
            source="Orc attack"
        )
        goblin.add_effect(effect)
        assert len(goblin.active_effects) == 1

        removed = goblin.remove_effect("Poisoned")
        assert removed is True
        assert len(goblin.active_effects) == 0

    def test_remove_effect_case_insensitive(self, goblin):
        """Test that remove_effect is case-insensitive."""
        effect = Effect(
            name="Stunned",
            effect_type="condition",
            duration_type=DurationType.ROUNDS,
            duration_remaining=1,
            source="Mind Flayer"
        )
        goblin.add_effect(effect)

        removed = goblin.remove_effect("STUNNED")
        assert removed is True
        assert len(goblin.active_effects) == 0

    def test_remove_nonexistent_effect(self, goblin):
        """Test removing effect that doesn't exist returns False."""
        removed = goblin.remove_effect("Nonexistent")
        assert removed is False

    def test_has_condition(self, goblin):
        """Test checking if monster has a condition."""
        effect = Effect(
            name="Poisoned",
            effect_type="condition",
            duration_type=DurationType.ROUNDS,
            duration_remaining=10,
            source="Poison attack"
        )
        goblin.add_effect(effect)

        assert goblin.has_condition("Poisoned") is True
        assert goblin.has_condition("poisoned") is True  # Case insensitive
        assert goblin.has_condition("Stunned") is False

    def test_conditions_property(self, goblin):
        """Test conditions property returns condition names."""
        goblin.add_effect(Effect(
            name="Poisoned",
            effect_type="condition",
            duration_type=DurationType.ROUNDS,
            duration_remaining=10,
            source="Poison"
        ))
        goblin.add_effect(Effect(
            name="Bless",
            effect_type="buff",
            duration_type=DurationType.CONCENTRATION,
            duration_remaining=10,
            source="Cleric"
        ))  # Not a condition

        conditions = goblin.conditions
        assert "Poisoned" in conditions
        assert "Bless" not in conditions

    def test_bloodied_condition_derived(self, orc_chief):
        """Test that Bloodied is a derived condition at half HP."""
        assert "Bloodied" not in orc_chief.conditions

        orc_chief.take_damage(23)  # Exactly half of 45
        assert "Bloodied" in orc_chief.conditions

    def test_unconscious_condition_derived(self, goblin):
        """Test that Unconscious is a derived condition at 0 HP."""
        assert "Unconscious" not in goblin.conditions

        goblin.take_damage(10)  # More than 7 HP
        assert "Unconscious" in goblin.conditions


# ==================== Monster Summary Methods Tests ====================


class TestMonsterSummaryMethods:
    """Test suite for Monster summary methods."""

    def test_get_combat_summary(self, goblin):
        """Test combat summary format."""
        summary = goblin.get_combat_summary()

        assert "Goblin 1" in summary
        assert "Small humanoid" in summary
        assert "AC 15" in summary
        assert "HP 7/7" in summary
        assert "CR 1/4" in summary

    def test_get_full_statblock(self, goblin):
        """Test full statblock format."""
        statblock = goblin.get_full_statblock()

        assert "# Goblin 1" in statblock
        assert "Small humanoid" in statblock
        assert "Armor Class" in statblock
        assert "Hit Points" in statblock
        assert "Speed" in statblock
        assert "STR" in statblock
        assert "Actions" in statblock
        assert "Scimitar" in statblock
        assert "Nimble Escape" in statblock

    def test_get_actions_detailed(self, goblin):
        """Test detailed action format."""
        actions = goblin.get_actions_detailed()

        assert "Scimitar" in actions
        assert "Shortbow" in actions
        assert "Attack Bonus" in actions
        assert "Damage" in actions


# ==================== StateCommandExecutor Duck Typing Tests ====================


class TestMonsterStateCommandExecutor:
    """Test that StateCommandExecutor works with Monster via duck typing."""

    @pytest.fixture
    def monster_registry(self, goblin, orc_chief):
        """Create a registry with both monsters."""
        return {
            "goblin_1": goblin,
            "orc_chief": orc_chief,
        }

    @pytest.fixture
    def executor(self, monster_registry):
        """Create executor with monster lookup."""
        return StateCommandExecutor(lambda char_id: monster_registry.get(char_id))

    def test_hp_damage_command_on_monster(self, executor, orc_chief):
        """Test HPChangeCommand works on Monster."""
        initial_hp = orc_chief.hit_points.current

        command = HPChangeCommand(
            character_id="orc_chief",
            change=-15,
            damage_type=DamageType.SLASHING
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert orc_chief.hit_points.current == initial_hp - 15
        assert "15" in result.message

    def test_hp_healing_command_on_monster(self, executor, orc_chief):
        """Test healing command works on Monster."""
        orc_chief.take_damage(20)
        initial_hp = orc_chief.hit_points.current

        command = HPChangeCommand(
            character_id="orc_chief",
            change=10
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert orc_chief.hit_points.current == initial_hp + 10

    def test_temporary_hp_command_on_monster(self, executor, goblin):
        """Test temporary HP command works on Monster."""
        command = HPChangeCommand(
            character_id="goblin_1",
            change=5,
            is_temporary=True
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert goblin.hit_points.temporary == 5

    def test_condition_add_command_on_monster(self, executor, goblin):
        """Test adding a condition to a monster."""
        from src.models.state_commands_optimized import ConditionCommand
        from src.characters.dnd_enums import Condition

        command = ConditionCommand(
            character_id="goblin_1",
            condition=Condition.POISONED,
            action="add",
            duration_type=DurationType.ROUNDS,
            duration=3
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert "Poisoned" in goblin.conditions
        assert "Added condition" in result.message

    def test_condition_remove_command_on_monster(self, executor, goblin):
        """Test removing a condition from a monster."""
        from src.models.state_commands_optimized import ConditionCommand
        from src.characters.dnd_enums import Condition

        # First add the condition
        goblin.add_effect(Effect(
            name="Poisoned",
            effect_type="condition",
            duration_type=DurationType.ROUNDS,
            duration_remaining=3,
            source="Test"
        ))

        command = ConditionCommand(
            character_id="goblin_1",
            condition=Condition.POISONED,
            action="remove"
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert "Poisoned" not in goblin.conditions
        assert "Removed condition" in result.message

    def test_effect_add_command_on_monster(self, executor, orc_chief):
        """Test adding a spell effect to a monster."""
        from src.models.state_commands_optimized import EffectCommand

        command = EffectCommand(
            character_id="orc_chief",
            effect_name="Bless",
            action="add",
            duration_type=DurationType.CONCENTRATION,
            duration=10,
            effect_type="buff",
            description="+1d4 to attack rolls and saving throws",
            summary="+1d4 attacks/saves"
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert any(e.name == "Bless" for e in orc_chief.active_effects)
        assert "Added buff" in result.message

    def test_effect_remove_command_on_monster(self, executor, orc_chief):
        """Test removing an effect from a monster."""
        from src.models.state_commands_optimized import EffectCommand

        # First add the effect
        orc_chief.add_effect(Effect(
            name="Hex",
            effect_type="debuff",
            duration_type=DurationType.CONCENTRATION,
            duration_remaining=10,
            source="Warlock"
        ))

        command = EffectCommand(
            character_id="orc_chief",
            effect_name="Hex",
            action="remove"
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert not any(e.name == "Hex" for e in orc_chief.active_effects)
        assert "Removed effect" in result.message

    def test_batch_execution_on_monsters(self, executor, goblin, orc_chief):
        """Test executing multiple commands on different monsters."""
        commands = [
            HPChangeCommand(character_id="goblin_1", change=-3),
            HPChangeCommand(character_id="orc_chief", change=-10),
            HPChangeCommand(character_id="goblin_1", change=2),
        ]

        batch_result = executor.execute_batch(commands)

        assert batch_result.total_commands == 3
        assert batch_result.successful == 3
        assert batch_result.failed == 0
        assert batch_result.all_successful is True
        assert goblin.hit_points.current == 7 - 3 + 2  # 6
        assert orc_chief.hit_points.current == 45 - 10  # 35

    def test_command_on_nonexistent_monster(self, executor):
        """Test command on nonexistent monster fails gracefully."""
        command = HPChangeCommand(
            character_id="nonexistent_monster",
            change=-10
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "not found" in result.message

    def test_batch_with_mixed_success_failure(self, executor, goblin):
        """Test batch execution with some failures."""
        commands = [
            HPChangeCommand(character_id="goblin_1", change=-3),  # Success
            HPChangeCommand(character_id="nonexistent", change=-5),  # Fail
            HPChangeCommand(character_id="goblin_1", change=1),  # Success
        ]

        batch_result = executor.execute_batch(commands)

        assert batch_result.total_commands == 3
        assert batch_result.successful == 2
        assert batch_result.failed == 1
        assert batch_result.all_successful is False
        assert len(batch_result.get_failures()) == 1
        assert len(batch_result.get_successes()) == 2

    def test_damage_with_temp_hp_on_monster(self, executor, orc_chief):
        """Test damage absorbed by temp HP on monster."""
        # Give temp HP first
        orc_chief.add_temporary_hp(10)
        initial_hp = orc_chief.hit_points.current

        command = HPChangeCommand(
            character_id="orc_chief",
            change=-15,
            damage_type=DamageType.FIRE
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert orc_chief.hit_points.temporary == 0  # Temp HP consumed
        assert orc_chief.hit_points.current == initial_hp - 5  # 15 - 10 temp = 5 actual
        assert "temp HP" in result.message

    def test_healing_caps_at_max_on_monster(self, executor, goblin):
        """Test healing doesn't exceed max HP on monster."""
        goblin.take_damage(3)  # 7 -> 4
        assert goblin.hit_points.current == 4

        command = HPChangeCommand(
            character_id="goblin_1",
            change=10  # More than missing HP
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert goblin.hit_points.current == 7  # Capped at max
        assert result.details["actual_healing"] == 3

    def test_lethal_damage_on_monster(self, executor, goblin):
        """Test damage that reduces monster to 0 HP."""
        command = HPChangeCommand(
            character_id="goblin_1",
            change=-100,
            damage_type=DamageType.BLUDGEONING
        )

        result = executor.execute_command(command)

        assert result.success is True
        assert goblin.hit_points.current == 0
        assert goblin.hit_points.is_unconscious is True
        assert "Unconscious" in goblin.conditions

    def test_multiple_conditions_on_monster(self, executor, orc_chief):
        """Test adding multiple conditions to a monster."""
        from src.models.state_commands_optimized import ConditionCommand
        from src.characters.dnd_enums import Condition

        commands = [
            ConditionCommand(
                character_id="orc_chief",
                condition=Condition.POISONED,
                action="add",
                duration_type=DurationType.ROUNDS,
                duration=5
            ),
            ConditionCommand(
                character_id="orc_chief",
                condition=Condition.FRIGHTENED,
                action="add",
                duration_type=DurationType.ROUNDS,
                duration=3
            ),
        ]

        batch_result = executor.execute_batch(commands)

        assert batch_result.all_successful is True
        assert "Poisoned" in orc_chief.conditions
        assert "Frightened" in orc_chief.conditions

    def test_condition_already_exists_fails(self, executor, goblin):
        """Test adding condition that already exists fails."""
        from src.models.state_commands_optimized import ConditionCommand
        from src.characters.dnd_enums import Condition

        # Add condition first
        goblin.add_effect(Effect(
            name="Stunned",
            effect_type="condition",
            duration_type=DurationType.ROUNDS,
            duration_remaining=1,
            source="Test"
        ))

        command = ConditionCommand(
            character_id="goblin_1",
            condition=Condition.STUNNED,
            action="add",
            duration_type=DurationType.ROUNDS,
            duration=2
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "already active" in result.message

    def test_remove_nonexistent_condition_fails(self, executor, goblin):
        """Test removing condition that doesn't exist fails."""
        from src.models.state_commands_optimized import ConditionCommand
        from src.characters.dnd_enums import Condition

        command = ConditionCommand(
            character_id="goblin_1",
            condition=Condition.PARALYZED,
            action="remove"
        )

        result = executor.execute_command(command)

        assert result.success is False
        assert "not found" in result.message


# ==================== StateManager Monster Support Tests ====================


class TestStateManagerMonsterSupport:
    """Test StateManager monster management methods."""

    @pytest.fixture
    def state_manager(self, tmp_path):
        """Create a StateManager instance for testing."""
        return StateManager(character_data_path=str(tmp_path), enable_logging=False)

    def test_add_monster(self, state_manager, goblin):
        """Test adding a monster to state manager."""
        state_manager.add_monster(goblin)

        assert "goblin_1" in state_manager.monsters
        assert state_manager.monsters["goblin_1"] is goblin

    def test_get_monster(self, state_manager, goblin):
        """Test getting a monster by ID."""
        state_manager.add_monster(goblin)

        retrieved = state_manager.get_monster("goblin_1")
        assert retrieved is goblin

    def test_get_monster_not_found(self, state_manager):
        """Test getting nonexistent monster returns None."""
        retrieved = state_manager.get_monster("nonexistent")
        assert retrieved is None

    def test_remove_monster(self, state_manager, goblin):
        """Test removing a monster."""
        state_manager.add_monster(goblin)
        removed = state_manager.remove_monster("goblin_1")

        assert removed is True
        assert "goblin_1" not in state_manager.monsters

    def test_remove_nonexistent_monster(self, state_manager):
        """Test removing nonexistent monster returns False."""
        removed = state_manager.remove_monster("nonexistent")
        assert removed is False

    def test_get_all_monsters(self, state_manager, goblin, orc_chief):
        """Test getting all monsters."""
        state_manager.add_monster(goblin)
        state_manager.add_monster(orc_chief)

        all_monsters = state_manager.get_all_monsters()
        assert len(all_monsters) == 2
        assert goblin in all_monsters
        assert orc_chief in all_monsters

    def test_clear_monsters(self, state_manager, goblin, orc_chief):
        """Test clearing all monsters."""
        state_manager.add_monster(goblin)
        state_manager.add_monster(orc_chief)

        state_manager.clear_monsters()

        assert len(state_manager.monsters) == 0

    def test_get_character_by_id_finds_monster(self, state_manager, goblin):
        """Test get_character_by_id finds monsters."""
        state_manager.add_monster(goblin)

        character = state_manager.get_character_by_id("goblin_1")
        assert character is goblin

    def test_get_character_by_id_prioritizes_monster(self, state_manager, goblin):
        """Test that get_character_by_id checks monsters before player characters."""
        state_manager.add_monster(goblin)
        # Character with same ID would be loaded from storage
        # Monster should be found first

        character = state_manager.get_character_by_id("goblin_1")
        assert character is goblin

    def test_get_character_name_to_id_map(self, state_manager, goblin, orc_chief):
        """Test getting name to ID mapping for all characters."""
        state_manager.add_monster(goblin)
        state_manager.add_monster(orc_chief)

        mapping = state_manager.get_character_name_to_id_map()

        assert mapping["Goblin 1"] == "goblin_1"
        assert mapping["Orc Chief"] == "orc_chief"


# ==================== Monster HP Properties Tests ====================


class TestMonsterHPProperties:
    """Test MonsterHitPoints properties for duck typing."""

    def test_maximum_property(self, goblin):
        """Test that maximum property returns average."""
        assert goblin.hit_points.maximum == goblin.hit_points.average

    def test_is_bloodied_at_half(self, orc_chief):
        """Test is_bloodied at exactly half HP."""
        orc_chief.hit_points.current = 22  # Less than half of 45
        assert orc_chief.hit_points.is_bloodied is True

    def test_is_bloodied_above_half(self, orc_chief):
        """Test is_bloodied above half HP."""
        orc_chief.hit_points.current = 30
        assert orc_chief.hit_points.is_bloodied is False

    def test_is_unconscious_at_zero(self, goblin):
        """Test is_unconscious at 0 HP."""
        goblin.hit_points.current = 0
        assert goblin.hit_points.is_unconscious is True

    def test_is_unconscious_above_zero(self, goblin):
        """Test is_unconscious above 0 HP."""
        assert goblin.hit_points.is_unconscious is False
