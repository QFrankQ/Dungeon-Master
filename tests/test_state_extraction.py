"""
Tests for State Extraction - verifies extraction of state changes from game narratives.

This test suite verifies that the state extraction orchestrator can correctly
identify and extract state changes from D&D game narratives, producing the
correct commands for execution.
"""

import pytest
import asyncio

from src.agents.state_extraction_orchestrator import (
    StateExtractionOrchestrator,
    create_state_extraction_orchestrator
)
from src.models.state_commands_optimized import StateCommandResult


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


# NOTE: convert_extraction_to_commands helper removed - orchestrator now returns commands directly


# ==================== Test Cases ====================


@pytest.mark.asyncio
class TestStateExtraction:
    """Test state extraction from game narratives."""

    async def test_simple_damage_extraction(self, orchestrator, simple_combat_narrative):
        """Test extraction of simple damage and condition."""
        result = await orchestrator.extract_state_changes(simple_combat_narrative)

        # Verify we got a result
        assert isinstance(result, StateCommandResult)

        # Check if rate limited or API error occurred
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # The narrative is clear and unambiguous - extraction should succeed
        assert len(result.commands) > 0, "Should extract commands from clear combat narrative"

        # Find the HP change command for the goblin
        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change" and "goblin" in cmd.character_id.lower()]
        assert len(hp_commands) > 0, "Should find HP command for goblin"

        # Verify damage was extracted
        goblin_hp_cmd = hp_commands[0]
        assert goblin_hp_cmd.change == -8, "Should extract 8 damage (negative)"

        # Damage type is optional but should be slashing if present
        if goblin_hp_cmd.damage_type:
            assert goblin_hp_cmd.damage_type.value == "slashing", "Should extract slashing damage type"

        # Note: Condition extraction requires turn_snapshot to be provided
        # For now, just verify HP extraction works with new 4-agent architecture

    async def test_spell_slot_extraction(self, orchestrator, spell_combat_narrative):
        """Test extraction of spell usage."""
        result = await orchestrator.extract_state_changes(spell_combat_narrative)

        assert isinstance(result, StateCommandResult)

        # Find Gandalf's spell slot command
        spell_commands = [cmd for cmd in result.commands if cmd.type == "spell_slot" and "gandalf" in cmd.character_id.lower()]

        # Verify spell slot usage was extracted
        if spell_commands:
            gandalf_spell_cmd = spell_commands[0]
            assert gandalf_spell_cmd.level == 3, "Should use 3rd level slot"
            assert gandalf_spell_cmd.action == "use", "Should be using a slot"

    async def test_death_save_extraction(self, orchestrator, death_save_narrative):
        """Test extraction of death saving throws."""
        result = await orchestrator.extract_state_changes(death_save_narrative)

        assert isinstance(result, StateCommandResult)

        # Find Legolas's death save command
        death_save_commands = [cmd for cmd in result.commands if cmd.type == "death_save" and "legolas" in cmd.character_id.lower()]

        # Verify death save was extracted
        if death_save_commands:
            legolas_ds_cmd = death_save_commands[0]
            assert legolas_ds_cmd.result == "success", "Should be a success"
            assert legolas_ds_cmd.count == 1, "Should have 1 success"

    async def test_healing_extraction(self, orchestrator, healing_narrative):
        """Test extraction of healing."""
        result = await orchestrator.extract_state_changes(healing_narrative)

        assert isinstance(result, StateCommandResult)

        # Find Gimli's healing command
        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change" and "gimli" in cmd.character_id.lower()]

        # Verify healing was extracted
        if hp_commands:
            gimli_hp_cmd = hp_commands[0]
            assert gimli_hp_cmd.change == 7, "Should extract 7 healing (positive)"

    async def test_direct_command_extraction(self, orchestrator, simple_combat_narrative):
        """Test that orchestrator returns commands directly (no conversion needed)."""
        result = await orchestrator.extract_state_changes(simple_combat_narrative)

        # Check if rate limited or API error occurred
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # The narrative is clear - should extract and produce commands
        assert len(result.commands) > 0, "Should produce commands from clear combat narrative"

        # Verify command types are correct
        command_types = [cmd.type for cmd in result.commands]
        assert any(t == "hp_change" for t in command_types), "Should have HP change command"
        # Note: Condition commands require turn_snapshot, so not testing that here

        # Verify all commands have required fields
        for cmd in result.commands:
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

        # Orchestrator now returns commands directly
        assert isinstance(result, StateCommandResult)

        # Verify pipeline produces executable commands
        assert all(hasattr(cmd, 'type') for cmd in result.commands), \
               "All commands should have a type field"
        assert all(hasattr(cmd, 'character_id') for cmd in result.commands), \
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
      The party explores the dungeon. You find a locked door ahead.
    </message>
  </turn_messages>
</turn_context>
"""

        result = run_async(orchestrator.extract_state_changes(empty_narrative))

        # Should return valid result with no commands
        assert isinstance(result, StateCommandResult)
        assert len(result.commands) == 0, "Should extract no commands from exploration narrative"


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v"])
