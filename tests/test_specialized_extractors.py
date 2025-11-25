"""
Tests for Specialized State Extractors.

Tests the CombatStateExtractor and ResourceExtractor on the same 4 command types
that are tested in test_state_command_executor.py:
1. HPChangeCommand
2. SpellSlotCommand
3. HitDiceCommand
4. DeathSaveCommand
"""

import pytest
import asyncio

from src.agents.combat_state_extractor import create_combat_state_extractor
from src.agents.resource_extractor import create_resource_extractor
from src.models.state_updates import CombatStateResult, ResourceResult


# ==================== Test Fixtures ====================


@pytest.fixture
def combat_extractor():
    """Create a combat state extractor for testing."""
    return create_combat_state_extractor()


@pytest.fixture
def resource_extractor():
    """Create a resource extractor for testing."""
    return create_resource_extractor()


# ==================== Helper Functions ====================


def run_async(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.run(coro)


# ==================== HP Change Command Tests ====================


class TestHPChangeExtraction:
    """Test HP change extraction (damage, healing, temporary HP)."""

    def test_damage_extraction(self, combat_extractor):
        """Test extraction of damage from combat narrative."""
        narrative = """
<turn_context turn_id="turn_1" level="0">
  <turn_messages>
    <message type="dm_response">
      The orc swings his axe at Aragorn. It hits! Aragorn takes 8 slashing damage.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(combat_extractor.extract(narrative))
        assert isinstance(result, CombatStateResult)

        # Find Aragorn's update
        aragorn_update = next(
            (u for u in result.character_updates if "aragorn" in u.character_id.lower()),
            None
        )

        if aragorn_update and aragorn_update.hp_update:
            print(f"Extracted HP update: {aragorn_update.hp_update}")
            assert aragorn_update.hp_update.damage == 8, "Should extract 8 damage"
            assert aragorn_update.hp_update.damage_type.value == "slashing", \
                "Should extract slashing damage type"
        else:
            pytest.fail("Failed to extract HP damage for Aragorn")

    def test_healing_extraction(self, combat_extractor):
        """Test extraction of healing."""
        narrative = """
<turn_context turn_id="turn_2" level="0">
  <turn_messages>
    <message type="dm_response">
      The cleric casts Cure Wounds on Gimli. Gimli regains 12 hit points.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(combat_extractor.extract(narrative))
        assert isinstance(result, CombatStateResult)

        gimli_update = next(
            (u for u in result.character_updates if "gimli" in u.character_id.lower()),
            None
        )

        if gimli_update and gimli_update.hp_update:
            print(f"Extracted HP update: {gimli_update.hp_update}")
            assert gimli_update.hp_update.healing == 12, "Should extract 12 healing"
        else:
            pytest.fail("Failed to extract healing for Gimli")

    def test_temporary_hp_extraction(self, combat_extractor):
        """Test extraction of temporary HP."""
        narrative = """
<turn_context turn_id="turn_3" level="0">
  <turn_messages>
    <message type="dm_response">
      Legolas casts Aid on himself, gaining 5 temporary hit points.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(combat_extractor.extract(narrative))
        assert isinstance(result, CombatStateResult)

        legolas_update = next(
            (u for u in result.character_updates if "legolas" in u.character_id.lower()),
            None
        )

        if legolas_update and legolas_update.hp_update:
            print(f"Extracted HP update: {legolas_update.hp_update}")
            assert legolas_update.hp_update.temporary_hp == 5, "Should extract 5 temporary HP"
        else:
            pytest.fail("Failed to extract temporary HP for Legolas")

    def test_damage_with_unconsciousness(self, combat_extractor):
        """Test extraction of damage causing unconsciousness."""
        narrative = """
<turn_context turn_id="turn_4" level="0">
  <turn_messages>
    <message type="dm_response">
      The dragon's claw strikes Aragorn for 30 slashing damage! Aragorn falls unconscious.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(combat_extractor.extract(narrative))
        assert isinstance(result, CombatStateResult)

        aragorn_update = next(
            (u for u in result.character_updates if "aragorn" in u.character_id.lower()),
            None
        )

        if aragorn_update:
            print(f"Extracted update: {aragorn_update}")
            if aragorn_update.hp_update:
                assert aragorn_update.hp_update.damage == 30, "Should extract 30 damage"
            # Check if unconscious condition was added
            if aragorn_update.condition_update:
                conditions = [c.value for c in aragorn_update.condition_update.add_conditions]
                assert "unconscious" in conditions, "Should add unconscious condition"
        else:
            pytest.fail("Failed to extract damage and unconsciousness for Aragorn")


# ==================== Spell Slot Command Tests ====================


class TestSpellSlotExtraction:
    """Test spell slot extraction."""

    def test_spell_slot_usage(self, resource_extractor):
        """Test extraction of spell slot usage."""
        narrative = """
<turn_context turn_id="turn_5" level="0">
  <turn_messages>
    <message type="player_action">
      Gandalf casts Fireball using a 3rd level spell slot.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(resource_extractor.extract(narrative))
        assert isinstance(result, ResourceResult)

        gandalf_update = next(
            (u for u in result.character_updates if "gandalf" in u.character_id.lower()),
            None
        )

        if gandalf_update and gandalf_update.spell_slot_update:
            print(f"Extracted spell slot update: {gandalf_update.spell_slot_update}")
            assert gandalf_update.spell_slot_update.level.value == 3, \
                "Should use 3rd level spell slot"
            assert gandalf_update.spell_slot_update.change == -1, \
                "Should use 1 spell slot"
        else:
            pytest.fail("Failed to extract spell slot usage for Gandalf")

    def test_multiple_spell_slots(self, resource_extractor):
        """Test extraction of multiple spell slot usage."""
        narrative = """
<turn_context turn_id="turn_6" level="0">
  <turn_messages>
    <message type="dm_response">
      Gandalf casts Magic Missile at 2nd level, then later casts Shield using a 1st level slot.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(resource_extractor.extract(narrative))
        assert isinstance(result, ResourceResult)

        gandalf_update = next(
            (u for u in result.character_updates if "gandalf" in u.character_id.lower()),
            None
        )

        if gandalf_update:
            print(f"Extracted update: {gandalf_update}")
            # Should extract spell slot usage (may be combined or separate)
            assert gandalf_update.spell_slot_update is not None, \
                "Should extract spell slot usage"
        else:
            pytest.fail("Failed to extract spell slot usage for Gandalf")

    def test_spell_slot_restoration(self, resource_extractor):
        """Test extraction of spell slot restoration."""
        narrative = """
<turn_context turn_id="turn_7" level="0">
  <turn_messages>
    <message type="dm_response">
      After a long rest, Gandalf recovers all his spell slots.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(resource_extractor.extract(narrative))
        assert isinstance(result, ResourceResult)

        # Check if any restoration was detected
        assert len(result.character_updates) > 0 or result.notes, \
            "Should detect spell slot restoration"


# ==================== Hit Dice Command Tests ====================


class TestHitDiceExtraction:
    """Test hit dice extraction."""

    def test_hit_dice_usage(self, resource_extractor):
        """Test extraction of hit dice usage during short rest."""
        narrative = """
<turn_context turn_id="turn_8" level="0">
  <turn_messages>
    <message type="dm_response">
      During the short rest, Aragorn spends 2 hit dice to recover health.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(resource_extractor.extract(narrative))
        assert isinstance(result, ResourceResult)

        aragorn_update = next(
            (u for u in result.character_updates if "aragorn" in u.character_id.lower()),
            None
        )

        if aragorn_update and aragorn_update.hit_dice_update:
            print(f"Extracted hit dice update: {aragorn_update.hit_dice_update}")
            assert aragorn_update.hit_dice_update.change == -2, \
                "Should use 2 hit dice (negative change)"
        else:
            pytest.fail("Failed to extract hit dice usage for Aragorn")

    def test_hit_dice_restoration(self, resource_extractor):
        """Test extraction of hit dice restoration after long rest."""
        narrative = """
<turn_context turn_id="turn_9" level="0">
  <turn_messages>
    <message type="dm_response">
      After a long rest, Aragorn regains half of his spent hit dice (3 hit dice restored).
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(resource_extractor.extract(narrative))
        assert isinstance(result, ResourceResult)

        aragorn_update = next(
            (u for u in result.character_updates if "aragorn" in u.character_id.lower()),
            None
        )

        if aragorn_update and aragorn_update.hit_dice_update:
            print(f"Extracted hit dice update: {aragorn_update.hit_dice_update}")
            assert aragorn_update.hit_dice_update.change == 3, \
                "Should restore 3 hit dice (positive change)"
        else:
            pytest.fail("Failed to extract hit dice restoration for Aragorn")


# ==================== Death Save Command Tests ====================


class TestDeathSaveExtraction:
    """Test death saving throw extraction."""

    def test_death_save_success(self, combat_extractor):
        """Test extraction of successful death save."""
        narrative = """
<turn_context turn_id="turn_10" level="0">
  <turn_messages>
    <message type="dm_response">
      Legolas, unconscious on the ground, makes a death saving throw. He rolls a 15 - success!
      That's 1 successful death save.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(combat_extractor.extract(narrative))
        assert isinstance(result, CombatStateResult)

        legolas_update = next(
            (u for u in result.character_updates if "legolas" in u.character_id.lower()),
            None
        )

        if legolas_update and legolas_update.death_save_update:
            print(f"Extracted death save update: {legolas_update.death_save_update}")
            assert legolas_update.death_save_update.success_increment == 1, \
                "Should have 1 successful death save"
        else:
            pytest.fail("Failed to extract death save success for Legolas")

    def test_death_save_failure(self, combat_extractor):
        """Test extraction of failed death save."""
        narrative = """
<turn_context turn_id="turn_11" level="0">
  <turn_messages>
    <message type="dm_response">
      Gimli makes a death saving throw. He rolls a 7 - failure. That's 1 failed death save.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(combat_extractor.extract(narrative))
        assert isinstance(result, CombatStateResult)

        gimli_update = next(
            (u for u in result.character_updates if "gimli" in u.character_id.lower()),
            None
        )

        if gimli_update and gimli_update.death_save_update:
            print(f"Extracted death save update: {gimli_update.death_save_update}")
            assert gimli_update.death_save_update.failure_increment == 1, \
                "Should have 1 failed death save"
        else:
            pytest.fail("Failed to extract death save failure for Gimli")

    def test_death_save_critical(self, combat_extractor):
        """Test extraction of critical success (nat 20) on death save."""
        narrative = """
<turn_context turn_id="turn_12" level="0">
  <turn_messages>
    <message type="dm_response">
      Aragorn makes a death saving throw and rolls a natural 20! He regains 1 hit point
      and becomes conscious.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(combat_extractor.extract(narrative))
        assert isinstance(result, CombatStateResult)

        aragorn_update = next(
            (u for u in result.character_updates if "aragorn" in u.character_id.lower()),
            None
        )

        if aragorn_update:
            print(f"Extracted update: {aragorn_update}")
            # Should extract healing and/or death save reset
            if aragorn_update.hp_update:
                assert aragorn_update.hp_update.healing == 1, "Should regain 1 HP"
            if aragorn_update.death_save_update:
                assert aragorn_update.death_save_update.reset, \
                    "Death saves should be reset"
        else:
            pytest.fail("Failed to extract critical death save success for Aragorn")

    def test_death_save_stabilization(self, combat_extractor):
        """Test extraction of character stabilization (3 successful saves)."""
        narrative = """
<turn_context turn_id="turn_13" level="0">
  <turn_messages>
    <message type="dm_response">
      Gimli makes his third successful death saving throw. He is now stable but unconscious.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(combat_extractor.extract(narrative))
        assert isinstance(result, CombatStateResult)

        gimli_update = next(
            (u for u in result.character_updates if "gimli" in u.character_id.lower()),
            None
        )

        if gimli_update and gimli_update.death_save_update:
            print(f"Extracted death save update: {gimli_update.death_save_update}")
            # Should show success or stabilization
            assert gimli_update.death_save_update.success_increment is not None, \
                "Should extract death save success"
        else:
            pytest.fail("Failed to extract stabilization for Gimli")


# ==================== Integration Test ====================


class TestExtractorIntegration:
    """Test integration between extractors."""

    def test_complex_combat_scenario(self, combat_extractor, resource_extractor):
        """Test complex scenario requiring both extractors."""
        narrative = """
<turn_context turn_id="turn_14" level="0">
  <turn_messages>
    <message type="player_action">
      Gandalf casts Fireball (3rd level slot) at the group of orcs.
    </message>
    <message type="dm_response">
      The fireball explodes! Orc 1 takes 28 fire damage and dies. Orc 2 takes 28 fire damage
      and is badly wounded. Orc 3 takes 14 fire damage (saved).
    </message>
  </turn_messages>
</turn_context>
"""

        # Test combat extraction
        combat_result = run_async(combat_extractor.extract(narrative))
        assert isinstance(combat_result, CombatStateResult)
        print(f"Combat extraction: {len(combat_result.character_updates)} updates")

        # Test resource extraction
        resource_result = run_async(resource_extractor.extract(narrative))
        assert isinstance(resource_result, ResourceResult)
        print(f"Resource extraction: {len(resource_result.character_updates)} updates")

        # Verify both extractors found relevant information
        assert len(combat_result.character_updates) > 0, \
            "Combat extractor should find damage to orcs"
        assert len(resource_result.character_updates) > 0, \
            "Resource extractor should find spell slot usage"


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v", "-s"])
