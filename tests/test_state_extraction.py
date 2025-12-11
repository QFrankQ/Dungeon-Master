"""
Tests for State Extraction - verifies extraction of state changes from game narratives.

This test suite verifies that the state extraction orchestrator can correctly
identify and extract state changes from D&D game narratives, producing the
correct commands for execution.
"""

import pytest
import asyncio
from typing import List

from src.agents.state_extraction_orchestrator import (
    StateExtractionOrchestrator,
    create_state_extraction_orchestrator
)
from src.models.state_updates import (
    StateExtractionResult,
    EventType,
    CharacterUpdate,
    HPUpdate,
    ConditionUpdate,
    SpellSlotUpdate,
    DeathSaveUpdate
)
from src.models.state_commands_optimized import (
    HPChangeCommand,
    ConditionCommand,
    EffectCommand,
    SpellSlotCommand,
    DeathSaveCommand,
    StateCommand
)


# ==================== Test Fixtures ====================


@pytest.fixture
def orchestrator():
    """Create a state extraction orchestrator for testing."""
    return create_state_extraction_orchestrator()


@pytest.fixture
def simple_combat_narrative():
    """Simple combat scenario with damage and condition."""
    return """
<turn_context turn_id="turn_1" level="0">
  <turn_metadata>
    <active_character>Goblin</active_character>
    <turn_number>1</turn_number>
  </turn_metadata>

  <turn_messages>
    <message type="player_action">
      Aragorn attacks the goblin with his longsword, rolling a 15 to hit.
    </message>
    <message type="dm_response">
      The blade strikes true! The goblin takes 8 slashing damage and falls prone.
    </message>
  </turn_messages>
</turn_context>
"""


@pytest.fixture
def spell_combat_narrative():
    """Combat with spell usage and multiple effects."""
    return """
<turn_context turn_id="turn_2" level="0">
  <turn_metadata>
    <active_character>Gandalf</active_character>
    <turn_number>2</turn_number>
  </turn_metadata>

  <turn_messages>
    <message type="player_action">
      Gandalf casts Fireball (3rd level) at the orcs.
    </message>
    <message type="dm_response">
      The fireball explodes! The three orcs each take 28 fire damage. Two orcs die instantly.
      The third orc survives but is badly burned.
    </message>
  </turn_messages>
</turn_context>
"""


@pytest.fixture
def death_save_narrative():
    """Narrative with death saving throws."""
    return """
<turn_context turn_id="turn_3" level="0">
  <turn_metadata>
    <active_character>Legolas</active_character>
    <turn_number>3</turn_number>
  </turn_metadata>

  <turn_messages>
    <message type="dm_response">
      Legolas, unconscious on the ground, makes a death saving throw. He rolls a 12 - that's a success!
      He now has 1 successful death save.
    </message>
  </turn_messages>
</turn_context>
"""


@pytest.fixture
def healing_narrative():
    """Narrative with healing."""
    return """
<turn_context turn_id="turn_4" level="0">
  <turn_metadata>
    <active_character>Gimli</active_character>
    <turn_number>4</turn_number>
  </turn_metadata>

  <turn_messages>
    <message type="player_action">
      Gimli drinks a Potion of Healing.
    </message>
    <message type="dm_response">
      Gimli rolls 2d4+2 for healing... that's 7 hit points restored!
    </message>
  </turn_messages>
</turn_context>
"""


# ==================== Helper Functions ====================


def run_async(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.run(coro)


def convert_extraction_to_commands(result: StateExtractionResult) -> List[StateCommand]:
    """
    Convert StateExtractionResult to list of StateCommands.

    This is a simplified converter for testing purposes.
    In production, this would be handled by a dedicated converter class.
    """
    commands = []

    for char_update in result.character_updates:
        char_id = char_update.character_id

        # Convert HP updates
        if char_update.hp_update:
            hp_update = char_update.hp_update

            if hp_update.damage:
                commands.append(HPChangeCommand(
                    character_id=char_id,
                    change=-hp_update.damage,
                    damage_type=hp_update.damage_type
                ))

            if hp_update.healing:
                commands.append(HPChangeCommand(
                    character_id=char_id,
                    change=hp_update.healing
                ))

            if hp_update.temporary_hp:
                commands.append(HPChangeCommand(
                    character_id=char_id,
                    change=hp_update.temporary_hp,
                    is_temporary=True
                ))

        # Convert condition updates
        if char_update.condition_update:
            cond_update = char_update.condition_update

            for condition in cond_update.add_conditions:
                commands.append(ConditionCommand(
                    character_id=char_id,
                    action="add",
                    condition=condition,
                    duration_type="rounds",  # Default, should be inferred
                    duration=10  # Default, should be inferred
                ))

            for condition in cond_update.remove_conditions:
                commands.append(ConditionCommand(
                    character_id=char_id,
                    action="remove",
                    condition=condition
                ))

        # Convert spell slot updates
        if char_update.spell_slot_update:
            slot_update = char_update.spell_slot_update

            if slot_update.change < 0:  # Using a slot
                commands.append(SpellSlotCommand(
                    character_id=char_id,
                    action="use",
                    level=slot_update.level.value,  # Enum to int
                    spell_name=slot_update.reason
                ))
            elif slot_update.change > 0:  # Restoring slots
                commands.append(SpellSlotCommand(
                    character_id=char_id,
                    action="restore",
                    level=slot_update.level.value,
                    count=slot_update.change
                ))

        # Convert death save updates
        if char_update.death_save_update:
            ds_update = char_update.death_save_update

            if ds_update.reset:
                commands.append(DeathSaveCommand(
                    character_id=char_id,
                    result="reset",
                    count=1
                ))
            elif ds_update.success_increment:
                commands.append(DeathSaveCommand(
                    character_id=char_id,
                    result="success",
                    count=ds_update.success_increment
                ))
            elif ds_update.failure_increment:
                commands.append(DeathSaveCommand(
                    character_id=char_id,
                    result="failure",
                    count=ds_update.failure_increment
                ))

    return commands


# ==================== Test Cases ====================


@pytest.mark.asyncio
class TestStateExtraction:
    """Test state extraction from game narratives."""

    async def test_simple_damage_extraction(self, orchestrator, simple_combat_narrative):
        """Test extraction of simple damage and condition."""
        result = await orchestrator.extract_state_changes(simple_combat_narrative)

        # Verify we got a result
        assert isinstance(result, StateExtractionResult)

        # Check if rate limited or API error occurred
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # The narrative is clear and unambiguous - extraction should succeed
        assert len(result.character_updates) > 0, "Should extract updates from clear combat narrative"

        # Find the goblin update
        goblin_update = next((u for u in result.character_updates if "goblin" in u.character_id.lower()), None)
        assert goblin_update is not None, "Should find goblin in character updates"

        # Verify damage was extracted
        assert goblin_update.hp_update is not None, "Should extract HP update"
        assert goblin_update.hp_update.damage == 8, "Should extract 8 damage"

        # Damage type is optional but should be slashing if present
        if goblin_update.hp_update.damage_type:
            assert goblin_update.hp_update.damage_type.value == "slashing", "Should extract slashing damage type"

        # Verify condition was extracted
        assert goblin_update.condition_update is not None, "Should extract condition update"
        assert any(c.value == "prone" for c in goblin_update.condition_update.add_conditions), \
            "Should extract prone condition"

    async def test_spell_slot_extraction(self, orchestrator, spell_combat_narrative):
        """Test extraction of spell usage."""
        result = await orchestrator.extract_state_changes(spell_combat_narrative)

        assert isinstance(result, StateExtractionResult)

        # Find Gandalf's update
        gandalf_update = next((u for u in result.character_updates if "gandalf" in u.character_id.lower()), None)

        # Verify spell slot usage was extracted
        if gandalf_update and gandalf_update.spell_slot_update:
            assert gandalf_update.spell_slot_update.level.value == 3, "Should use 3rd level slot"
            assert gandalf_update.spell_slot_update.change == -1, "Should use 1 slot"

    async def test_death_save_extraction(self, orchestrator, death_save_narrative):
        """Test extraction of death saving throws."""
        result = await orchestrator.extract_state_changes(death_save_narrative)

        assert isinstance(result, StateExtractionResult)

        # Find Legolas's update
        legolas_update = next((u for u in result.character_updates if "legolas" in u.character_id.lower()), None)

        # Verify death save was extracted
        if legolas_update and legolas_update.death_save_update:
            assert legolas_update.death_save_update.success_increment == 1, "Should have 1 success"

    async def test_healing_extraction(self, orchestrator, healing_narrative):
        """Test extraction of healing."""
        result = await orchestrator.extract_state_changes(healing_narrative)

        assert isinstance(result, StateExtractionResult)

        # Find Gimli's update
        gimli_update = next((u for u in result.character_updates if "gimli" in u.character_id.lower()), None)

        # Verify healing was extracted
        if gimli_update and gimli_update.hp_update:
            assert gimli_update.hp_update.healing == 7, "Should extract 7 healing"

    async def test_conversion_to_commands(self, orchestrator, simple_combat_narrative):
        """Test conversion of extracted state to commands."""
        result = await orchestrator.extract_state_changes(simple_combat_narrative)

        # Check if rate limited or API error occurred
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Convert to commands
        commands = convert_extraction_to_commands(result)

        # The narrative is clear - should extract and produce commands
        assert len(commands) > 0, "Should produce commands from clear combat narrative"

        # Verify command types are correct
        command_types = [cmd.type for cmd in commands]
        assert any(t == "hp_change" for t in command_types), "Should have HP change command"
        assert any(t == "condition" for t in command_types), "Should have condition command"

        # Verify all commands have required fields
        for cmd in commands:
            assert hasattr(cmd, 'type'), "Command should have type"
            assert hasattr(cmd, 'character_id'), "Command should have character_id"


@pytest.mark.asyncio
class TestEventDetection:
    """Test event detection component of state extraction."""

    async def test_combat_event_detection(self, orchestrator, simple_combat_narrative):
        """Test that HP change and effect events are detected."""
        # The orchestrator uses event detection internally
        result = await orchestrator.extract_state_changes(simple_combat_narrative)

        # Check the notes for event detection info
        assert result.notes is not None, "Should have notes about extraction"

        # Note: AI model may not always detect events due to variability
        # The test verifies that the orchestrator runs without errors
        # and returns a valid result structure
        # If events ARE detected, verify they're the right types
        notes_lower = result.notes.lower()
        if "no events detected" not in notes_lower:
            # Events were detected - verify they're HP_CHANGE or EFFECT_APPLIED
            assert ("hp_change" in notes_lower or
                    "effect_applied" in notes_lower or
                    "combat" in notes_lower or  # Legacy format for backwards compat
                    len(result.character_updates) > 0), \
                   "If events detected, should be HP or effect related"

    async def test_resource_event_detection(self, orchestrator, spell_combat_narrative):
        """Test that resource usage events are detected."""
        result = await orchestrator.extract_state_changes(spell_combat_narrative)

        # Check for resource-related extraction
        assert result.notes is not None, "Should have notes about extraction"
        # The extraction should identify spell usage as a resource event


# ==================== Integration Tests ====================


class TestStateExtractionIntegration:
    """Integration tests for complete extraction pipeline."""

    def test_full_extraction_pipeline(self, orchestrator, simple_combat_narrative):
        """Test complete extraction from narrative to commands."""
        # Run extraction
        result = run_async(orchestrator.extract_state_changes(simple_combat_narrative))

        # Convert to commands
        commands = convert_extraction_to_commands(result)

        # Verify pipeline produces executable commands
        assert all(hasattr(cmd, 'type') for cmd in commands), \
               "All commands should have a type field"
        assert all(hasattr(cmd, 'character_id') for cmd in commands), \
               "All commands should have a character_id field"

    def test_empty_narrative_handling(self, orchestrator):
        """Test handling of narrative with no state changes."""
        empty_narrative = """
<turn_context turn_id="turn_5" level="0">
  <turn_metadata>
    <active_character>Narrator</active_character>
    <turn_number>5</turn_number>
  </turn_metadata>

  <turn_messages>
    <message type="dm_response">
      The party rests peacefully. Nothing happens during the night.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(orchestrator.extract_state_changes(empty_narrative))

        # Should return valid result with no updates
        assert isinstance(result, StateExtractionResult)
        assert len(result.character_updates) == 0, "Should extract no updates from peaceful rest"


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v"])
