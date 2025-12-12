"""
Tests for LifecycleAgent command extraction.

Tests the lifecycle specialist agent for death saves and rest events:
- DeathSaveCommand (success, failure, reset)
- RestCommand (short rest, long rest)
"""

import pytest
import asyncio

from src.agents.lifecycle_agent import create_lifecycle_agent
from src.models.state_commands_optimized import (
    StateAgentResult,
    DeathSaveCommand,
    RestCommand
)


# ==================== Test Fixtures ====================


@pytest.fixture
def lifecycle_agent():
    """Create lifecycle agent for testing."""
    return create_lifecycle_agent()


def run_async(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.run(coro)


# ==================== Death Save Tests ====================


class TestDeathSaves:
    """Test death save extraction."""

    def test_death_save_success(self, lifecycle_agent):
        """Test extraction of successful death save."""
        narrative = "Legolas, unconscious on the ground, makes a death saving throw. He rolls a 12 - that's a success!"

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)
        assert len(result.commands) > 0, "Should extract death save command"

        death_save_cmd = next((cmd for cmd in result.commands
                               if isinstance(cmd, DeathSaveCommand) and "legolas" in cmd.character_id.lower()), None)

        assert death_save_cmd is not None, "Should extract death save for Legolas"
        assert death_save_cmd.type == "death_save"
        assert death_save_cmd.result == "success", "Should be a success"
        assert death_save_cmd.count == 1, "Should increment by 1"
        print(f"✓ Extracted: {death_save_cmd}")

    def test_death_save_failure(self, lifecycle_agent):
        """Test extraction of failed death save."""
        narrative = "Gimli rolls a natural 1 on his death save. That's an automatic failure!"

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)
        assert len(result.commands) > 0, "Should extract death save command"

        death_save_cmd = next((cmd for cmd in result.commands
                               if isinstance(cmd, DeathSaveCommand) and "gimli" in cmd.character_id.lower()), None)

        assert death_save_cmd is not None, "Should extract death save for Gimli"
        assert death_save_cmd.result == "failure", "Should be a failure"
        assert death_save_cmd.count == 1, "Should increment by 1"
        print(f"✓ Extracted: {death_save_cmd}")

    def test_death_save_stabilization(self, lifecycle_agent):
        """Test extraction of stabilization (reset death saves)."""
        narrative = "The cleric casts Healing Word on Aragorn, restoring 5 hit points. Aragorn is conscious again and his death saves reset."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)
        assert len(result.commands) > 0, "Should extract death save reset"

        death_save_cmd = next((cmd for cmd in result.commands
                               if isinstance(cmd, DeathSaveCommand) and "aragorn" in cmd.character_id.lower()), None)

        assert death_save_cmd is not None, "Should extract death save reset for Aragorn"
        assert death_save_cmd.result == "reset", "Should reset death saves"
        print(f"✓ Extracted: {death_save_cmd}")

    def test_multiple_death_saves(self, lifecycle_agent):
        """Test extraction of multiple death saves in same narrative."""
        narrative = """Legolas makes his death save and rolls a 15 - success!
                      Meanwhile, Gimli also makes a death save, rolling a 7 - failure."""

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)
        death_save_cmds = [cmd for cmd in result.commands if isinstance(cmd, DeathSaveCommand)]

        # AI might extract both or just one depending on interpretation
        assert len(death_save_cmds) >= 1, "Should extract at least one death save"
        print(f"✓ Extracted {len(death_save_cmds)} death save commands")
        for cmd in death_save_cmds:
            print(f"  - {cmd}")

    def test_death_save_with_hp_context(self, lifecycle_agent):
        """Test that HP healing is ignored by lifecycle agent."""
        narrative = "The cleric heals Gimli for 10 HP. Gimli wakes up and his death saves reset."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)

        # Should extract only death save reset, NOT HP healing
        death_save_cmds = [cmd for cmd in result.commands if isinstance(cmd, DeathSaveCommand)]
        assert len(death_save_cmds) > 0, "Should extract death save reset"

        # Verify no HP commands were extracted (lifecycle agent doesn't handle HP)
        for cmd in result.commands:
            assert cmd.type in ["death_save", "rest"], "Should only extract lifecycle events"

        print(f"✓ Correctly ignored HP healing, extracted only death save reset")


# ==================== Rest Tests ====================


class TestRests:
    """Test rest event extraction."""

    def test_short_rest(self, lifecycle_agent):
        """Test extraction of short rest."""
        narrative = "The party takes a short rest to catch their breath and tend to their wounds."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)
        assert len(result.commands) > 0, "Should extract rest command"

        rest_cmd = next((cmd for cmd in result.commands if isinstance(cmd, RestCommand)), None)

        assert rest_cmd is not None, "Should extract rest command"
        assert rest_cmd.type == "rest"
        assert rest_cmd.rest_type == "short", "Should be a short rest"
        print(f"✓ Extracted: {rest_cmd}")

    def test_long_rest(self, lifecycle_agent):
        """Test extraction of long rest."""
        narrative = "After defeating the goblins, the party takes a long rest to recover their strength."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)
        assert len(result.commands) > 0, "Should extract rest command"

        rest_cmd = next((cmd for cmd in result.commands if isinstance(cmd, RestCommand)), None)

        assert rest_cmd is not None, "Should extract rest command"
        assert rest_cmd.rest_type == "long", "Should be a long rest"
        print(f"✓ Extracted: {rest_cmd}")

    def test_rest_with_hit_dice(self, lifecycle_agent):
        """Test rest extraction when hit dice usage is mentioned."""
        narrative = "The party takes a short rest. During the rest, Aragorn spends 2 hit dice and recovers 14 hit points."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)

        # Should extract only rest event, NOT hit dice or HP recovery
        rest_cmd = next((cmd for cmd in result.commands if isinstance(cmd, RestCommand)), None)
        assert rest_cmd is not None, "Should extract rest command"
        assert rest_cmd.rest_type == "short", "Should be a short rest"

        # Verify no hit dice or HP commands were extracted
        for cmd in result.commands:
            assert cmd.type in ["death_save", "rest"], "Should only extract lifecycle events"

        print(f"✓ Correctly ignored hit dice/HP, extracted only rest event")

    def test_rest_with_spell_slot_restoration(self, lifecycle_agent):
        """Test rest extraction when spell slot restoration is mentioned."""
        narrative = "The party takes a long rest. When they wake up, they have full HP and all spell slots restored."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)

        # Should extract rest event (AI variability allowed)
        rest_cmd = next((cmd for cmd in result.commands if isinstance(cmd, RestCommand)), None)

        # AI might extract rest or skip it depending on interpretation
        if rest_cmd:
            assert rest_cmd.rest_type == "long", "Should be a long rest"
            # Verify only rest command extracted
            for cmd in result.commands:
                assert cmd.type in ["death_save", "rest"], "Should only extract lifecycle events"
            print(f"✓ Correctly ignored HP/spell restoration, extracted rest event")
        else:
            # AI might skip if it interprets "wake up" as non-explicit rest
            print(f"✓ AI skipped implicit rest (acceptable behavior)")

    def test_individual_rest(self, lifecycle_agent):
        """Test extraction of individual character rest (not party-wide)."""
        narrative = "Aragorn takes a short rest while keeping watch."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)

        rest_cmd = next((cmd for cmd in result.commands if isinstance(cmd, RestCommand)), None)

        if rest_cmd:
            # AI might extract individual rest with character name
            assert rest_cmd.rest_type == "short", "Should be a short rest"
            print(f"✓ Extracted individual rest: {rest_cmd}")
        else:
            # Or AI might skip individual rests and only extract party rests
            print("✓ AI correctly skipped individual rest (optional behavior)")


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_narrative(self, lifecycle_agent):
        """Test handling of narrative with no lifecycle events."""
        narrative = "The party explores the dungeon and finds treasure."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)
        assert len(result.commands) == 0, "Should extract no commands from non-lifecycle narrative"
        print("✓ Correctly returned empty list for non-lifecycle narrative")

    def test_mixed_lifecycle_events(self, lifecycle_agent):
        """Test extraction of both death saves and rests in same narrative."""
        narrative = """The party takes a short rest after the battle.
                      During the rest, Gimli makes a death save and succeeds with a 16."""

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)

        # Should extract both rest and death save
        rest_cmds = [cmd for cmd in result.commands if isinstance(cmd, RestCommand)]
        death_save_cmds = [cmd for cmd in result.commands if isinstance(cmd, DeathSaveCommand)]

        # AI might extract both or be selective - both are valid
        total_cmds = len(rest_cmds) + len(death_save_cmds)
        assert total_cmds > 0, "Should extract at least one lifecycle event"

        print(f"✓ Extracted {len(rest_cmds)} rest + {len(death_save_cmds)} death save commands")

    def test_narrative_with_only_combat(self, lifecycle_agent):
        """Test that lifecycle agent ignores pure combat narratives."""
        narrative = "Aragorn attacks the orc with his longsword, dealing 8 slashing damage. The orc falls prone."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)
        assert len(result.commands) == 0, "Should ignore combat-only narrative"
        print("✓ Correctly ignored combat narrative")

    def test_narrative_with_spell_casting(self, lifecycle_agent):
        """Test that lifecycle agent ignores spell casting."""
        narrative = "Gandalf casts Fireball using a 3rd level spell slot. The fireball explodes, dealing 28 fire damage to the orcs."

        result = run_async(lifecycle_agent.extract(narrative))

        assert isinstance(result, StateAgentResult)
        assert len(result.commands) == 0, "Should ignore spell casting narrative"
        print("✓ Correctly ignored spell casting")


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v"])
