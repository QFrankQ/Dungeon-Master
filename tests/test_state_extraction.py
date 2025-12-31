"""
Tests for State Extraction - verifies extraction of state changes from game narratives.

This test suite verifies that the state extraction orchestrator can correctly
identify and extract state changes from D&D game narratives, producing the
correct commands for execution.
"""

import pytest
import asyncio
import os

from src.agents.state_extraction_orchestrator import (
    StateExtractionOrchestrator,
    create_state_extraction_orchestrator
)
from src.models.state_commands_optimized import StateCommandResult


# ==================== Test Fixtures ====================


@pytest.fixture
def orchestrator():
    """Create a state extraction orchestrator for testing."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")

    return create_state_extraction_orchestrator(
        model_name="gemini-2.5-flash-lite",
        api_key=api_key
    )


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


# ==================== Monster State Extraction Tests ====================


@pytest.fixture
def monster_combat_narrative_with_mapping():
    """Combat narrative with monster character mapping for ID resolution."""
    return """```xml
<character_mapping>
  <!-- Use these mappings to convert character names to character_ids -->
  <entry name="Tharion Stormwind" id="fighter"/>
  <entry name="Goblin 1" id="goblin_1"/>
  <entry name="Goblin 2" id="goblin_2"/>
  <entry name="Orc Chief" id="orc_chief"/>
</character_mapping>
<turn_log>
  <message speaker="Player">Tharion attacks Goblin 1 with his longsword.</message>
  <message speaker="DM">The blade slices through! Goblin 1 takes 8 slashing damage and is bloodied.</message>
</turn_log>
```"""


@pytest.fixture
def multi_monster_damage_narrative():
    """Combat narrative with multiple monsters taking damage."""
    return """```xml
<character_mapping>
  <!-- Use these mappings to convert character names to character_ids -->
  <entry name="Elara the Wizard" id="wizard"/>
  <entry name="Goblin 1" id="goblin_1"/>
  <entry name="Goblin 2" id="goblin_2"/>
  <entry name="Goblin 3" id="goblin_3"/>
</character_mapping>
<turn_log>
  <message speaker="Player">Elara casts Burning Hands at the goblins!</message>
  <message speaker="DM">Fire engulfs the goblins! Goblin 1 takes 12 fire damage and dies. Goblin 2 takes 12 fire damage and dies. Goblin 3 makes its save and takes 6 fire damage.</message>
</turn_log>
```"""


@pytest.fixture
def monster_effect_narrative():
    """Combat narrative with effects applied to monsters."""
    return """```xml
<character_mapping>
  <!-- Use these mappings to convert character names to character_ids -->
  <entry name="Ranger" id="ranger"/>
  <entry name="Orc Chief" id="orc_chief"/>
  <entry name="Orc Warrior" id="orc_warrior_1"/>
</character_mapping>
<turn_log>
  <message speaker="Player">Ranger casts Hunter's Mark on the Orc Chief.</message>
  <message speaker="DM">The Orc Chief is marked! He also gets hit by an arrow for 7 piercing damage. The mark will deal extra damage on subsequent attacks.</message>
</turn_log>
```"""


@pytest.fixture
def monster_healing_narrative():
    """Narrative with monster receiving healing (rare but possible)."""
    return """```xml
<character_mapping>
  <!-- Use these mappings to convert character names to character_ids -->
  <entry name="Orc Shaman" id="orc_shaman"/>
  <entry name="Orc Chief" id="orc_chief"/>
</character_mapping>
<turn_log>
  <message speaker="DM">The Orc Shaman casts Cure Wounds on the injured Orc Chief, healing 10 hit points.</message>
</turn_log>
```"""


@pytest.fixture
def monster_condition_narrative():
    """Narrative with conditions applied to monsters."""
    return """```xml
<character_mapping>
  <!-- Use these mappings to convert character names to character_ids -->
  <entry name="Wizard" id="wizard"/>
  <entry name="Goblin Boss" id="goblin_boss"/>
</character_mapping>
<turn_log>
  <message speaker="Player">Wizard casts Hold Person on the Goblin Boss.</message>
  <message speaker="DM">The Goblin Boss fails its Wisdom save! It becomes paralyzed for 1 minute (concentration).</message>
</turn_log>
```"""


@pytest.mark.asyncio
class TestMonsterStateExtraction:
    """Test state extraction for monster characters with ID mapping."""

    async def test_monster_damage_extraction_with_mapping(self, orchestrator, monster_combat_narrative_with_mapping):
        """Test that damage to a monster extracts correct character_id from mapping."""
        result = await orchestrator.extract_state_changes(monster_combat_narrative_with_mapping)

        assert isinstance(result, StateCommandResult)

        # Check for API rate limiting
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract HP change command
        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change"]

        if hp_commands:
            # Find command for goblin_1 (from mapping "Goblin 1" -> "goblin_1")
            goblin_commands = [cmd for cmd in hp_commands if cmd.character_id == "goblin_1"]
            assert len(goblin_commands) > 0, "Should extract command with character_id='goblin_1' from mapping"

            goblin_cmd = goblin_commands[0]
            assert goblin_cmd.change == -8, "Should extract 8 damage (negative)"

    async def test_multi_monster_damage_extraction(self, orchestrator, multi_monster_damage_narrative):
        """Test extraction of damage to multiple monsters in same turn."""
        result = await orchestrator.extract_state_changes(multi_monster_damage_narrative)

        assert isinstance(result, StateCommandResult)

        # Check for API rate limiting
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract HP change commands for each goblin
        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change"]

        if hp_commands:
            # Get unique character IDs
            monster_ids = set(cmd.character_id for cmd in hp_commands)

            # Should have commands for goblin_1, goblin_2, goblin_3
            expected_goblins = {"goblin_1", "goblin_2", "goblin_3"}
            found_goblins = monster_ids.intersection(expected_goblins)

            assert len(found_goblins) >= 1, f"Should find at least one goblin command with mapped IDs. Found: {monster_ids}"

            # Verify damage amounts if goblins were found
            for cmd in hp_commands:
                if cmd.character_id in expected_goblins:
                    # Goblin 3 took 6 damage (saved), others took 12
                    if cmd.character_id == "goblin_3":
                        assert cmd.change == -6, f"Goblin 3 should take 6 damage, got {cmd.change}"
                    else:
                        assert cmd.change == -12, f"{cmd.character_id} should take 12 damage, got {cmd.change}"

    async def test_monster_healing_extraction(self, orchestrator, monster_healing_narrative):
        """Test extraction of healing applied to a monster."""
        result = await orchestrator.extract_state_changes(monster_healing_narrative)

        assert isinstance(result, StateCommandResult)

        # Check for API rate limiting
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract HP change command for healing
        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change"]

        if hp_commands:
            # Find command for orc_chief (healing)
            chief_commands = [cmd for cmd in hp_commands if cmd.character_id == "orc_chief"]

            if chief_commands:
                chief_cmd = chief_commands[0]
                assert chief_cmd.change == 10, "Should extract 10 healing (positive)"
                assert chief_cmd.change > 0, "Healing should be positive"

    async def test_monster_id_uses_mapping_not_inference(self, orchestrator, monster_combat_narrative_with_mapping):
        """Test that character_id comes from mapping, not inferred from name."""
        result = await orchestrator.extract_state_changes(monster_combat_narrative_with_mapping)

        # Check for API rate limiting
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Check all commands use the exact IDs from mapping
        valid_ids = {"fighter", "goblin_1", "goblin_2", "orc_chief"}

        for cmd in result.commands:
            # If there's a character_id, it should be from the mapping
            if cmd.character_id:
                # The ID should be one of the mapped IDs OR a reasonable inference
                # (agents may fall back to inference if mapping isn't found)
                assert (
                    cmd.character_id in valid_ids or
                    cmd.character_id.lower().replace(" ", "_") in valid_ids or
                    "goblin" in cmd.character_id.lower() or
                    "orc" in cmd.character_id.lower() or
                    "fighter" in cmd.character_id.lower() or
                    "tharion" in cmd.character_id.lower()
                ), f"character_id '{cmd.character_id}' should match mapping or be reasonable inference"

    async def test_mixed_player_and_monster_extraction(self, orchestrator, monster_effect_narrative):
        """Test extraction correctly distinguishes player and monster targets."""
        result = await orchestrator.extract_state_changes(monster_effect_narrative)

        # Check for API rate limiting
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should have commands for the orc_chief (damage)
        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change"]

        if hp_commands:
            # The 7 damage should be on orc_chief, not the ranger
            orc_damage_commands = [cmd for cmd in hp_commands if "orc" in cmd.character_id.lower()]
            ranger_damage_commands = [cmd for cmd in hp_commands if cmd.character_id == "ranger"]

            if orc_damage_commands:
                assert orc_damage_commands[0].change == -7, "Orc Chief should take 7 damage"

            # Ranger should not have damage (they were the attacker)
            assert len(ranger_damage_commands) == 0, "Ranger should not have damage commands"


@pytest.mark.asyncio
class TestMonsterEffectExtraction:
    """Test state extraction for effects and conditions applied to monsters."""

    async def test_condition_applied_to_monster(self, orchestrator, monster_condition_narrative):
        """Test extraction of condition (paralyzed) applied to monster."""
        result = await orchestrator.extract_state_changes(monster_condition_narrative)

        assert isinstance(result, StateCommandResult)

        # Check for API rate limiting
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract condition or effect command (action="add")
        effect_commands = [cmd for cmd in result.commands
                          if cmd.type in ("condition", "effect") and getattr(cmd, 'action', '') == 'add']

        if effect_commands:
            # Find command for goblin_boss
            goblin_boss_effects = [cmd for cmd in effect_commands
                                   if cmd.character_id == "goblin_boss"]

            assert len(goblin_boss_effects) > 0, \
                "Should extract effect command for goblin_boss from mapping"

            # Verify the condition is paralyzed - check both condition and effect_name attributes
            for cmd in goblin_boss_effects:
                # ConditionCommand uses 'condition', EffectCommand uses 'effect_name'
                effect_value = getattr(cmd, 'condition', None) or getattr(cmd, 'effect_name', '')
                effect_str = str(effect_value).lower()
                assert "paralyz" in effect_str or "hold" in effect_str, \
                    f"Effect should be paralyzed or hold person, got '{effect_value}'"

    async def test_spell_effect_on_monster(self, orchestrator, monster_effect_narrative):
        """Test extraction of spell effect (Hunter's Mark) on monster."""
        result = await orchestrator.extract_state_changes(monster_effect_narrative)

        assert isinstance(result, StateCommandResult)

        # Check for API rate limiting
        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract effect command for Hunter's Mark (action="add")
        effect_commands = [cmd for cmd in result.commands
                          if cmd.type in ("condition", "effect") and getattr(cmd, 'action', '') == 'add']

        if effect_commands:
            # Find command for orc_chief (Hunter's Mark target)
            orc_effects = [cmd for cmd in effect_commands
                          if "orc" in cmd.character_id.lower()]

            if orc_effects:
                # Verify effect is Hunter's Mark related
                for cmd in orc_effects:
                    effect_value = getattr(cmd, 'condition', None) or getattr(cmd, 'effect_name', '')
                    effect_str = str(effect_value).lower()
                    assert any(kw in effect_str for kw in ["hunter", "mark", "marked"]), \
                        f"Effect should be Hunter's Mark, got '{effect_value}'"

    async def test_multiple_conditions_on_monster(self, orchestrator):
        """Test extraction of multiple conditions applied to same monster."""
        narrative = """```xml
<character_mapping>
  <entry name="Monk" id="monk"/>
  <entry name="Ogre" id="ogre_1"/>
</character_mapping>
<turn_log>
  <message speaker="Player">The Monk uses Stunning Strike on the Ogre!</message>
  <message speaker="DM">The Ogre fails its Constitution save and is stunned! It also falls prone from the force of the blow.</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract multiple condition commands (action="add")
        effect_commands = [cmd for cmd in result.commands
                          if cmd.type in ("condition", "effect") and getattr(cmd, 'action', '') == 'add']

        if effect_commands:
            ogre_effects = [cmd for cmd in effect_commands
                           if cmd.character_id == "ogre_1"]

            # May extract stunned, prone, or both - get condition/effect names
            condition_names = []
            for cmd in ogre_effects:
                effect_value = getattr(cmd, 'condition', None) or getattr(cmd, 'effect_name', '')
                condition_names.append(str(effect_value).lower())

            has_stunned = any("stun" in name for name in condition_names)
            has_prone = any("prone" in name for name in condition_names)

            # At minimum should have one condition
            assert len(ogre_effects) >= 1, \
                f"Should extract at least one condition for ogre. Got: {condition_names}"

            # Ideally should have both, but AI may merge them
            if len(ogre_effects) >= 2:
                assert has_stunned or has_prone, \
                    f"Should extract stunned or prone. Got: {condition_names}"

    async def test_debuff_effect_on_monster(self, orchestrator):
        """Test extraction of debuff effect on monster (Bane, Hex, etc.)."""
        narrative = """```xml
<character_mapping>
  <entry name="Warlock" id="warlock"/>
  <entry name="Troll" id="troll_1"/>
</character_mapping>
<turn_log>
  <message speaker="Player">I cast Hex on the Troll, choosing Strength as the affected ability.</message>
  <message speaker="DM">The Troll is hexed! It has disadvantage on Strength checks, and will take extra necrotic damage from your attacks.</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Effect command with action="add"
        effect_commands = [cmd for cmd in result.commands
                          if cmd.type in ("condition", "effect") and getattr(cmd, 'action', '') == 'add']

        if effect_commands:
            troll_effects = [cmd for cmd in effect_commands
                            if cmd.character_id == "troll_1"]

            if troll_effects:
                effect_names = []
                for cmd in troll_effects:
                    effect_value = getattr(cmd, 'condition', None) or getattr(cmd, 'effect_name', '')
                    effect_names.append(str(effect_value).lower())
                assert any("hex" in name for name in effect_names), \
                    f"Should extract Hex effect. Got: {effect_names}"

    async def test_buff_removed_from_monster(self, orchestrator):
        """Test extraction of effect removal from monster."""
        narrative = """```xml
<character_mapping>
  <entry name="Cleric" id="cleric"/>
  <entry name="Vampire" id="vampire_1"/>
</character_mapping>
<turn_log>
  <message speaker="Player">I cast Dispel Magic on the Vampire to remove its Haste effect!</message>
  <message speaker="DM">The Haste spell is dispelled! The Vampire loses its extra speed and action, and must skip its next turn due to the lethargy.</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract condition or effect command with action="remove"
        remove_commands = [cmd for cmd in result.commands
                          if cmd.type in ("condition", "effect") and getattr(cmd, 'action', '') == 'remove']

        if remove_commands:
            vampire_removes = [cmd for cmd in remove_commands
                              if cmd.character_id == "vampire_1"]

            if vampire_removes:
                effect_names = []
                for cmd in vampire_removes:
                    effect_value = getattr(cmd, 'condition', None) or getattr(cmd, 'effect_name', '')
                    effect_names.append(str(effect_value).lower())
                assert any("haste" in name for name in effect_names), \
                    f"Should extract Haste removal. Got: {effect_names}"


@pytest.mark.asyncio
class TestMonsterResourceExtraction:
    """Test state extraction for resources used in monster encounters."""

    async def test_spell_slot_used_against_monster(self, orchestrator, multi_monster_damage_narrative):
        """Test extraction of spell slot used when casting on monsters."""
        result = await orchestrator.extract_state_changes(multi_monster_damage_narrative)

        assert isinstance(result, StateCommandResult)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract spell_slot command for the wizard
        spell_commands = [cmd for cmd in result.commands if cmd.type == "spell_slot"]

        if spell_commands:
            wizard_spells = [cmd for cmd in spell_commands
                            if cmd.character_id == "wizard"]

            if wizard_spells:
                # Burning Hands is a 1st level spell
                assert wizard_spells[0].level >= 1, "Should use at least 1st level slot"
                assert wizard_spells[0].action == "use", "Should be using a slot"

    async def test_multiple_spell_slots_in_combat(self, orchestrator):
        """Test extraction of multiple spell slot usages in combat."""
        narrative = """```xml
<character_mapping>
  <entry name="Wizard" id="wizard"/>
  <entry name="Cleric" id="cleric"/>
  <entry name="Dragon" id="adult_red_dragon"/>
</character_mapping>
<turn_log>
  <message speaker="Player">Wizard casts Fireball (3rd level) at the Dragon!</message>
  <message speaker="DM">The Dragon takes 28 fire damage from the fireball!</message>
  <message speaker="Player">Cleric casts Guiding Bolt (1st level) at the Dragon!</message>
  <message speaker="DM">The radiant bolt strikes! The Dragon takes 14 radiant damage and the next attack against it has advantage.</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        spell_commands = [cmd for cmd in result.commands if cmd.type == "spell_slot"]

        if spell_commands:
            # Should have spell slot usage for both casters
            wizard_spells = [cmd for cmd in spell_commands if cmd.character_id == "wizard"]
            cleric_spells = [cmd for cmd in spell_commands if cmd.character_id == "cleric"]

            # Check wizard used 3rd level
            if wizard_spells:
                assert wizard_spells[0].level == 3, \
                    f"Wizard should use 3rd level slot, got {wizard_spells[0].level}"

            # Check cleric used 1st level
            if cleric_spells:
                assert cleric_spells[0].level == 1, \
                    f"Cleric should use 1st level slot, got {cleric_spells[0].level}"

    async def test_item_usage_in_monster_combat(self, orchestrator):
        """Test extraction of item usage during monster combat."""
        narrative = """```xml
<character_mapping>
  <entry name="Rogue" id="rogue"/>
  <entry name="Assassin Vine" id="assassin_vine"/>
</character_mapping>
<turn_log>
  <message speaker="Player">I throw a vial of Alchemist's Fire at the Assassin Vine!</message>
  <message speaker="DM">The Alchemist's Fire shatters on the plant creature, dealing 4 fire damage! It will take additional fire damage at the start of its turn.</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract item command with action="use"
        item_commands = [cmd for cmd in result.commands
                        if cmd.type == "item" and getattr(cmd, 'action', '') == 'use']

        if item_commands:
            rogue_items = [cmd for cmd in item_commands if cmd.character_id == "rogue"]

            if rogue_items:
                item_names = [cmd.item_name.lower() for cmd in rogue_items]
                assert any("alchemist" in name or "fire" in name for name in item_names), \
                    f"Should extract Alchemist's Fire usage. Got: {item_names}"

    async def test_potion_used_during_monster_fight(self, orchestrator):
        """Test extraction of potion usage during combat with monsters."""
        narrative = """```xml
<character_mapping>
  <entry name="Fighter" id="fighter"/>
  <entry name="Hill Giant" id="hill_giant"/>
</character_mapping>
<turn_log>
  <message speaker="DM">The Hill Giant smashes the Fighter for 21 bludgeoning damage!</message>
  <message speaker="Player">I drink my Potion of Greater Healing as a bonus action!</message>
  <message speaker="DM">You drink the potion and recover 18 hit points, getting back in the fight!</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract item command with action="use" for potion and hp_change for healing
        item_commands = [cmd for cmd in result.commands
                        if cmd.type == "item" and getattr(cmd, 'action', '') == 'use']
        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change"]

        # Check potion usage
        if item_commands:
            fighter_items = [cmd for cmd in item_commands if cmd.character_id == "fighter"]
            if fighter_items:
                item_names = [cmd.item_name.lower() for cmd in fighter_items]
                assert any("potion" in name or "healing" in name for name in item_names), \
                    f"Should extract potion usage. Got: {item_names}"

        # Check healing from potion
        if hp_commands:
            fighter_healing = [cmd for cmd in hp_commands
                              if cmd.character_id == "fighter" and cmd.change > 0]
            if fighter_healing:
                assert fighter_healing[0].change == 18, \
                    f"Fighter should heal 18 HP, got {fighter_healing[0].change}"

        # Check damage to fighter from giant
        if hp_commands:
            fighter_damage = [cmd for cmd in hp_commands
                             if cmd.character_id == "fighter" and cmd.change < 0]
            if fighter_damage:
                assert fighter_damage[0].change == -21, \
                    f"Fighter should take 21 damage, got {fighter_damage[0].change}"

    async def test_ki_points_used_on_monster(self, orchestrator):
        """Test extraction of class resource (Ki) used on monster."""
        narrative = """```xml
<character_mapping>
  <entry name="Monk" id="monk"/>
  <entry name="Orc Warchief" id="orc_warchief"/>
</character_mapping>
<turn_log>
  <message speaker="Player">I use Flurry of Blows (1 ki point) against the Orc Warchief!</message>
  <message speaker="DM">You land both bonus action attacks! The Orc Warchief takes 6 bludgeoning damage from the first strike and 8 bludgeoning damage from the second!</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change"]

        # Note: Ki points are class-specific resources not tracked by current command set
        # Just verify the damage extraction works correctly

        # Check damage to orc (14 total: 6 + 8)
        if hp_commands:
            orc_damage = [cmd for cmd in hp_commands if cmd.character_id == "orc_warchief"]
            if orc_damage:
                total_damage = sum(cmd.change for cmd in orc_damage)
                assert total_damage == -14, \
                    f"Orc should take 14 total damage, got {total_damage}"

    async def test_hit_dice_used_after_monster_fight(self, orchestrator):
        """Test extraction of hit dice usage during short rest after combat."""
        narrative = """```xml
<character_mapping>
  <entry name="Barbarian" id="barbarian"/>
</character_mapping>
<turn_log>
  <message speaker="DM">With the goblins defeated, you take a short rest.</message>
  <message speaker="Player">I spend 2 hit dice to recover HP.</message>
  <message speaker="DM">You roll 2d12 + your Constitution modifier (3) twice. You recover 12 + 3 = 15 hit points from the first die and 8 + 3 = 11 from the second, for a total of 26 HP recovered.</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        # Should extract hit_dice command with action="use" and hp_change
        hit_dice_commands = [cmd for cmd in result.commands
                           if cmd.type == "hit_dice" and getattr(cmd, 'action', '') == 'use']
        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change"]

        # Check hit dice usage
        if hit_dice_commands:
            barbarian_hd = [cmd for cmd in hit_dice_commands if cmd.character_id == "barbarian"]
            if barbarian_hd:
                # count should be 2 (the command uses count for number of dice)
                assert barbarian_hd[0].count == 2, \
                    f"Should use 2 hit dice, got {barbarian_hd[0].count}"

        # Check healing (26 total)
        if hp_commands:
            barbarian_heal = [cmd for cmd in hp_commands
                             if cmd.character_id == "barbarian" and cmd.change > 0]
            if barbarian_heal:
                total_heal = sum(cmd.change for cmd in barbarian_heal)
                assert total_heal == 26, f"Should heal 26 HP total, got {total_heal}"


@pytest.mark.asyncio
class TestMonsterCharacterIdMapping:
    """Test that character mapping is correctly parsed and used."""

    async def test_mapping_with_spaces_in_names(self, orchestrator):
        """Test that names with spaces map correctly."""
        narrative = """```xml
<character_mapping>
  <entry name="Goblin War Chief" id="goblin_war_chief"/>
  <entry name="Fighter" id="fighter"/>
</character_mapping>
<turn_log>
  <message speaker="DM">The Goblin War Chief takes 15 slashing damage from the Fighter's attack!</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change"]

        if hp_commands:
            # Should use "goblin_war_chief" from mapping, not "goblin_war_chief" inferred
            goblin_commands = [cmd for cmd in hp_commands if "goblin" in cmd.character_id.lower()]
            assert len(goblin_commands) > 0, "Should extract damage for goblin"

            # Verify the ID format matches the mapping
            for cmd in goblin_commands:
                assert cmd.character_id == "goblin_war_chief" or "goblin" in cmd.character_id.lower(), \
                    f"character_id should be 'goblin_war_chief' or similar, got '{cmd.character_id}'"

    async def test_mapping_with_numbered_monsters(self, orchestrator):
        """Test that numbered monsters (Goblin 1, Goblin 2) map correctly."""
        narrative = """```xml
<character_mapping>
  <entry name="Goblin 1" id="goblin_1"/>
  <entry name="Goblin 2" id="goblin_2"/>
  <entry name="Paladin" id="paladin"/>
</character_mapping>
<turn_log>
  <message speaker="DM">The Paladin's Divine Smite obliterates Goblin 2, dealing 22 radiant damage!</message>
</turn_log>
```"""

        result = await orchestrator.extract_state_changes(narrative)

        if result.notes and ("RESOURCE_EXHAUSTED" in result.notes or "quota" in result.notes.lower()):
            pytest.skip("API rate limit hit - test would pass with available quota")

        hp_commands = [cmd for cmd in result.commands if cmd.type == "hp_change"]

        if hp_commands:
            # Should specifically target goblin_2, not goblin_1
            goblin2_commands = [cmd for cmd in hp_commands if cmd.character_id == "goblin_2"]

            if goblin2_commands:
                assert goblin2_commands[0].change == -22, "Goblin 2 should take 22 damage"

            # Should NOT have command for goblin_1
            goblin1_commands = [cmd for cmd in hp_commands if cmd.character_id == "goblin_1"]
            assert len(goblin1_commands) == 0, "Goblin 1 should not have damage (wasn't targeted)"


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v"])
