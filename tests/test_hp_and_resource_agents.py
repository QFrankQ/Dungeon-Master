"""
Tests for HPAgent and ResourceAgent command extraction.

Tests the two specialist agents on the command types from test_state_command_executor.py:
- HPAgent: HPChangeCommand
- ResourceAgent: SpellSlotCommand, HitDiceCommand, ItemCommand
"""

import pytest
import asyncio

from src.agents.hp_agent import create_hp_agent
from src.agents.resource_agent import create_resource_agent
from src.models.state_commands_optimized import (
    HPAgentResult,
    ResourceAgentResult,
    HPChangeCommand,
    SpellSlotCommand,
    HitDiceCommand,
    ItemCommand
)


# ==================== Test Fixtures ====================


@pytest.fixture
def hp_agent():
    """Create HP agent for testing."""
    return create_hp_agent()


@pytest.fixture
def resource_agent():
    """Create resource agent for testing."""
    return create_resource_agent()


def run_async(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.run(coro)


# ==================== HP Agent Tests ====================


class TestHPAgent:
    """Test HP agent extraction of HPChangeCommand."""

    def test_damage_extraction(self, hp_agent):
        """Test extraction of damage (negative HP change)."""
        narrative = "The orc swings his axe at Aragorn. It hits! Aragorn takes 8 slashing damage."

        result = run_async(hp_agent.extract(narrative))

        assert isinstance(result, HPAgentResult)
        assert len(result.commands) > 0, "Should extract at least one HP command"

        # Find Aragorn's damage
        aragorn_cmd = next((cmd for cmd in result.commands
                           if "aragorn" in cmd.character_id.lower()), None)

        assert aragorn_cmd is not None, "Should extract damage for Aragorn"
        assert aragorn_cmd.type == "hp_change"
        assert aragorn_cmd.change == -8, "Should be -8 (negative for damage)"
        assert aragorn_cmd.damage_type.value == "slashing", "Should extract slashing damage type"
        print(f"✓ Extracted: {aragorn_cmd}")

    def test_healing_extraction(self, hp_agent):
        """Test extraction of healing (positive HP change)."""
        narrative = "The cleric casts Cure Wounds on Gimli. Gimli regains 12 hit points."

        result = run_async(hp_agent.extract(narrative))

        assert isinstance(result, HPAgentResult)
        assert len(result.commands) > 0, "Should extract healing command"

        gimli_cmd = next((cmd for cmd in result.commands
                         if "gimli" in cmd.character_id.lower()), None)

        assert gimli_cmd is not None, "Should extract healing for Gimli"
        assert gimli_cmd.change == 12, "Should be +12 (positive for healing)"
        assert gimli_cmd.damage_type is None, "Healing should not have damage type"
        print(f"✓ Extracted: {gimli_cmd}")

    def test_temporary_hp_extraction(self, hp_agent):
        """Test extraction of temporary HP."""
        narrative = "The wizard grants Legolas 5 temporary hit points."

        result = run_async(hp_agent.extract(narrative))

        assert isinstance(result, HPAgentResult)
        assert len(result.commands) > 0, "Should extract temporary HP command"

        legolas_cmd = next((cmd for cmd in result.commands
                           if "legolas" in cmd.character_id.lower()), None)

        assert legolas_cmd is not None, "Should extract temp HP for Legolas"
        assert legolas_cmd.change == 5, "Should be +5"
        assert legolas_cmd.is_temporary == True, "Should mark as temporary HP"
        print(f"✓ Extracted: {legolas_cmd}")

    def test_multiple_targets_damage(self, hp_agent):
        """Test extraction of damage to multiple characters."""
        narrative = """The fireball explodes! Orc 1 takes 28 fire damage and dies.
                      Orc 2 takes 28 fire damage. Orc 3 takes 14 fire damage."""

        result = run_async(hp_agent.extract(narrative))

        assert isinstance(result, HPAgentResult)
        assert len(result.commands) >= 3, "Should extract damage for all 3 orcs"

        # Verify all damages are fire type
        for cmd in result.commands:
            assert cmd.change < 0, "All should be damage (negative)"
            if cmd.damage_type:
                assert cmd.damage_type.value == "fire", "All damage should be fire type"

        print(f"✓ Extracted {len(result.commands)} damage commands")
        for cmd in result.commands:
            print(f"  - {cmd}")

    def test_damage_caps_at_zero(self, hp_agent):
        """Test that HP doesn't go below 0 (implicit in damage command)."""
        narrative = "The dragon breathes fire on Aragorn for 30 damage, dropping him to 0 HP."

        result = run_async(hp_agent.extract(narrative))

        assert isinstance(result, HPAgentResult)
        aragorn_cmd = next((cmd for cmd in result.commands
                           if "aragorn" in cmd.character_id.lower()), None)

        assert aragorn_cmd is not None
        assert aragorn_cmd.change == -30, "Should extract the 30 damage"
        print(f"✓ Extracted: {aragorn_cmd}")

    def test_healing_caps_at_max(self, hp_agent):
        """Test healing extraction (capping happens in executor, not extractor)."""
        narrative = "Gandalf heals Aragorn for 20 HP, bringing him to full health."

        result = run_async(hp_agent.extract(narrative))

        assert isinstance(result, HPAgentResult)
        aragorn_cmd = next((cmd for cmd in result.commands
                           if "aragorn" in cmd.character_id.lower()), None)

        assert aragorn_cmd is not None
        assert aragorn_cmd.change == 20, "Should extract the 20 healing"
        print(f"✓ Extracted: {aragorn_cmd}")

    def test_no_hp_changes(self, hp_agent):
        """Test narrative with no HP changes."""
        narrative = "Aragorn searches the room carefully but finds nothing."

        result = run_async(hp_agent.extract(narrative))

        assert isinstance(result, HPAgentResult)
        assert len(result.commands) == 0, "Should extract no commands when no HP changes"
        print("✓ Correctly extracted 0 commands for narrative with no HP changes")


# ==================== Resource Agent Tests ====================


class TestResourceAgent:
    """Test resource agent extraction of spell slots, hit dice, and items."""

    # ---------- Spell Slot Tests ----------

    def test_spell_slot_usage(self, resource_agent):
        """Test extraction of spell slot usage."""
        narrative = "Gandalf casts Fireball using a 3rd level spell slot."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        assert len(result.commands) > 0, "Should extract spell slot usage"

        # Find spell slot command
        spell_cmd = next((cmd for cmd in result.commands
                         if cmd.type == "spell_slot"), None)

        assert spell_cmd is not None, "Should extract spell slot command"
        assert "gandalf" in spell_cmd.character_id.lower(), "Should be Gandalf"
        assert spell_cmd.action == "use", "Should be using a slot"
        assert spell_cmd.level == 3, "Should be 3rd level"
        assert spell_cmd.spell_name == "Fireball", "Should extract spell name"
        print(f"✓ Extracted: {spell_cmd}")

    def test_multiple_spell_casts(self, resource_agent):
        """Test extraction of multiple spell slot usage."""
        narrative = "Gandalf casts Magic Missile (1st level), then Shield (1st level)."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        spell_cmds = [cmd for cmd in result.commands if cmd.type == "spell_slot"]

        assert len(spell_cmds) >= 2, "Should extract both spell slot uses"
        print(f"✓ Extracted {len(spell_cmds)} spell slot commands")

    def test_spell_slot_restoration(self, resource_agent):
        """Test extraction of spell slot restoration."""
        narrative = "Gandalf uses Arcane Recovery to regain 2 first-level spell slots."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        spell_cmd = next((cmd for cmd in result.commands
                         if cmd.type == "spell_slot"), None)

        if spell_cmd:  # Agent might extract this
            assert spell_cmd.action == "restore", "Should be restoring slots"
            assert spell_cmd.level == 1, "Should be 1st level"
            assert spell_cmd.count == 2, "Should restore 2 slots"
            print(f"✓ Extracted: {spell_cmd}")
        else:
            print("⚠ Agent did not extract spell slot restoration (acceptable)")

    # ---------- Hit Dice Tests ----------

    def test_hit_dice_usage(self, resource_agent):
        """Test extraction of hit dice usage during short rest."""
        narrative = "During the short rest, Aragorn spends 2 hit dice to recover health."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        hit_dice_cmd = next((cmd for cmd in result.commands
                            if cmd.type == "hit_dice"), None)

        assert hit_dice_cmd is not None, "Should extract hit dice usage"
        assert "aragorn" in hit_dice_cmd.character_id.lower(), "Should be Aragorn"
        assert hit_dice_cmd.action == "use", "Should be using hit dice"
        assert hit_dice_cmd.count == 2, "Should use 2 hit dice"
        print(f"✓ Extracted: {hit_dice_cmd}")

    def test_hit_dice_restoration(self, resource_agent):
        """Test extraction of hit dice restoration after long rest."""
        narrative = "After a long rest, Aragorn regains half of his spent hit dice (3 hit dice restored)."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        hit_dice_cmd = next((cmd for cmd in result.commands
                            if cmd.type == "hit_dice"), None)

        assert hit_dice_cmd is not None, "Should extract hit dice restoration"
        assert hit_dice_cmd.action == "restore", "Should be restoring hit dice"
        assert hit_dice_cmd.count == 3, "Should restore 3 hit dice"
        print(f"✓ Extracted: {hit_dice_cmd}")

    def test_hit_dice_when_none_available(self, resource_agent):
        """Test narrative mentioning hit dice but none available."""
        narrative = "Aragorn wants to use hit dice but has none remaining."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        # Agent might or might not extract this - it's edge case
        print(f"✓ Agent handled edge case (extracted {len(result.commands)} commands)")

    # ---------- Item Tests ----------

    def test_item_usage(self, resource_agent):
        """Test extraction of item usage."""
        narrative = "Gimli drinks a Potion of Healing and feels much better."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        item_cmd = next((cmd for cmd in result.commands
                        if cmd.type == "item"), None)

        assert item_cmd is not None, "Should extract item usage"
        assert "gimli" in item_cmd.character_id.lower(), "Should be Gimli"
        assert item_cmd.action == "use", "Should be using item"
        assert "potion" in item_cmd.item_name.lower(), "Should be Potion of Healing"
        print(f"✓ Extracted: {item_cmd}")

    def test_item_acquisition(self, resource_agent):
        """Test extraction of items gained."""
        narrative = "The party finds 50 gold coins in the treasure chest."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        item_cmd = next((cmd for cmd in result.commands
                        if cmd.type == "item"), None)

        if item_cmd:  # Agent might extract this
            assert item_cmd.action == "add", "Should be adding items"
            assert "gold" in item_cmd.item_name.lower(), "Should be gold coins"
            assert item_cmd.quantity == 50, "Should be 50 coins"
            print(f"✓ Extracted: {item_cmd}")
        else:
            print("⚠ Agent did not extract item acquisition (might need party as character)")

    def test_item_removal(self, resource_agent):
        """Test extraction of items lost or removed."""
        narrative = "Aragorn drops his rope to lighten his load."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        item_cmd = next((cmd for cmd in result.commands
                        if cmd.type == "item"), None)

        if item_cmd:  # Agent might extract this
            assert item_cmd.action == "remove", "Should be removing item"
            assert "rope" in item_cmd.item_name.lower(), "Should be rope"
            print(f"✓ Extracted: {item_cmd}")
        else:
            print("⚠ Agent did not extract item removal (acceptable)")

    def test_no_resource_changes(self, resource_agent):
        """Test narrative with no resource usage."""
        narrative = "Aragorn carefully searches the room but finds nothing of interest."

        result = run_async(resource_agent.extract(narrative))

        assert isinstance(result, ResourceAgentResult)
        assert len(result.commands) == 0, "Should extract no commands"
        print("✓ Correctly extracted 0 commands for narrative with no resources")


# ==================== Integration Tests ====================


class TestAgentIntegration:
    """Test both agents working together on complex scenarios."""

    def test_combat_with_spellcasting(self, hp_agent, resource_agent):
        """Test complex combat scenario requiring both agents."""
        narrative = """Gandalf casts Fireball using a 3rd level spell slot.
                      The fireball explodes! Orc 1 takes 28 fire damage and dies.
                      Orc 2 takes 28 fire damage. Orc 3 takes 14 fire damage."""

        # Extract with HP agent
        hp_result = run_async(hp_agent.extract(narrative))
        assert len(hp_result.commands) >= 3, "HP agent should find damage to orcs"

        # Extract with Resource agent
        resource_result = run_async(resource_agent.extract(narrative))
        assert len(resource_result.commands) >= 1, "Resource agent should find spell slot usage"

        print(f"✓ HP Agent extracted {len(hp_result.commands)} commands")
        print(f"✓ Resource Agent extracted {len(resource_result.commands)} commands")

    def test_short_rest_scenario(self, hp_agent, resource_agent):
        """Test short rest with healing and hit dice."""
        narrative = """During the short rest, Aragorn spends 2 hit dice.
                      He rolls and recovers 14 hit points."""

        # Extract with HP agent
        hp_result = run_async(hp_agent.extract(narrative))
        healing_cmd = next((cmd for cmd in hp_result.commands
                           if cmd.change > 0), None)
        assert healing_cmd is not None, "Should extract healing"

        # Extract with Resource agent
        resource_result = run_async(resource_agent.extract(narrative))
        hit_dice_cmd = next((cmd for cmd in resource_result.commands
                            if cmd.type == "hit_dice"), None)
        assert hit_dice_cmd is not None, "Should extract hit dice usage"

        print(f"✓ HP Agent: {healing_cmd}")
        print(f"✓ Resource Agent: {hit_dice_cmd}")

    def test_potion_usage_scenario(self, hp_agent, resource_agent):
        """Test potion usage affecting both HP and items."""
        narrative = "Gimli drinks a Potion of Healing, recovering 7 hit points."

        # Extract with HP agent
        hp_result = run_async(hp_agent.extract(narrative))
        healing_cmd = next((cmd for cmd in hp_result.commands
                           if cmd.change > 0), None)
        assert healing_cmd is not None, "Should extract healing"
        assert healing_cmd.change == 7

        # Extract with Resource agent
        resource_result = run_async(resource_agent.extract(narrative))
        item_cmd = next((cmd for cmd in resource_result.commands
                        if cmd.type == "item"), None)
        assert item_cmd is not None, "Should extract potion usage"

        print(f"✓ HP Agent: {healing_cmd}")
        print(f"✓ Resource Agent: {item_cmd}")


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v", "-s"])
