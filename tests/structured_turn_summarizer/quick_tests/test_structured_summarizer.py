"""
Tests for the Structured Turn Summarizer agent.

Tests the agent's ability to condense turn contexts into structured summaries.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
import textwrap
from src.agents.structured_summarizer import (
    StructuredTurnSummarizer,
    create_turn_condensation_agent,
    StructuredTurnSummary
)
from src.models.turn_context import TurnContext


class TestStructuredTurnSummarizer:
    """Test suite for Structured Turn Summarizer."""

    def test_agent_initialization(self):
        """Test that the agent initializes correctly."""
        summarizer = create_turn_condensation_agent()
        assert summarizer is not None
        assert summarizer.agent is not None
        assert summarizer.context_builder is not None

    def test_simple_turn_condensation(self):
        """Test condensing a simple turn with only live messages."""
        summarizer = create_turn_condensation_agent()

        # Create a simple turn context
        turn_context = TurnContext(
            turn_id="1",
            turn_level=0,
            current_step_objective="Process player action",
            active_character="Aragorn"
        )

        turn_context.add_live_message("I attack the orc with my longsword", "player")
        turn_context.add_live_message("Roll for attack!", "dm")
        turn_context.add_live_message("I rolled 18 plus 5, that's 23 to hit", "player")
        turn_context.add_live_message("That hits! Roll damage", "dm")
        turn_context.add_live_message("12 slashing damage", "player")
        turn_context.add_live_message("Your blade cleaves through the orc's armor!", "dm")

        # Condense the turn synchronously
        result = summarizer.condense_turn_sync(turn_context)

        # Verify result structure
        assert isinstance(result, StructuredTurnSummary)
        assert result.structured_summary is not None
        assert len(result.structured_summary) > 0

        # Verify XML structure
        assert "<turn" in result.structured_summary
        assert 'id="1"' in result.structured_summary
        assert "<action>" in result.structured_summary
        assert "<resolution>" in result.structured_summary
        assert "</turn>" in result.structured_summary

        print("\n" + "=" * 80)
        print("SIMPLE TURN TEST RESULT:")
        print("=" * 80)
        print(result.structured_summary)

    def test_turn_with_nested_reactions(self):
        """Test condensing a turn with nested reaction subturns."""
        summarizer = create_turn_condensation_agent()

        # Create a turn with reactions
        turn_context = TurnContext(
            turn_id="2",
            turn_level=0,
            current_step_objective="Resolve spellcasting with reactions",
            active_character="Alice the Wizard"
        )

        # Main action
        turn_context.add_live_message("I cast Fireball at the goblin group", "player")
        turn_context.add_live_message("DC 15 Dexterity save", "player")
        turn_context.add_live_message("The goblin chief tries to counter your spell!", "dm")

        # Add completed subturn (enemy reaction)
        enemy_reaction = textwrap.dedent("""
            <action>Goblin chief snarls and weaves Counterspell magic desperately</action>
            <resolution>His crude magic fails against Alice's superior spellcasting</resolution>
        """).strip()
        turn_context.add_completed_subturn(enemy_reaction, "2.1")

        # Resolution
        turn_context.add_live_message("Yes! My Fireball explodes!", "player")
        turn_context.add_live_message("28 fire damage to all goblins. Most are incinerated!", "dm")

        # Condense the turn
        result = summarizer.condense_turn_sync(turn_context)

        # Verify result includes the reaction
        assert isinstance(result, StructuredTurnSummary)

        # Check if reaction tags are preserved
        has_reaction = "<reaction" in result.structured_summary
        has_id = 'id="2.1"' in result.structured_summary

        print(f"\nReaction tag present: {has_reaction}")
        print(f"ID attribute present: {has_id}")

        # The summarizer should preserve reactions from the input
        assert has_reaction, f"Expected <reaction tag in output, got: {result.structured_summary}"
        assert has_id, f"Expected id=\"2.1\" in output, got: {result.structured_summary}"

        print("\n" + "=" * 80)
        print("TURN WITH REACTIONS TEST RESULT:")
        print("=" * 80)
        print(result.structured_summary)

    def test_turn_with_deeply_nested_reactions(self):
        """Test condensing a turn with multiple levels of nested reactions."""
        summarizer = create_turn_condensation_agent()

        turn_context = TurnContext(
            turn_id="3",
            turn_level=0,
            current_step_objective="Resolve complex reaction chain",
            active_character="Gandalf"
        )

        # Main action
        turn_context.add_live_message("I cast Meteor Swarm at the dragon", "player")
        turn_context.add_live_message("The dragon roars in defiance!", "dm")

        # First reaction (dragon counters)
        dragon_reaction = textwrap.dedent("""
            <action>Dragon spreads wings and attempts Counterspell</action>
            <reaction id="3.1.1" level="2">
              <action>Gandalf recognizes the counter and fights back with his own Counterspell</action>
              <resolution>Gandalf's ancient power overwhelms the dragon's magic</resolution>
            </reaction>
            <resolution>Dragon's counterspell is neutralized by Gandalf's superior magic</resolution>
        """).strip()
        turn_context.add_completed_subturn(dragon_reaction, "3.1")

        # Final resolution
        turn_context.add_live_message("Meteors rain down on the dragon!", "dm")
        turn_context.add_live_message("84 bludgeoning and 84 fire damage!", "player")

        # Condense the turn
        result = summarizer.condense_turn_sync(turn_context)

        # Verify nested reactions are preserved
        assert isinstance(result, StructuredTurnSummary)
        assert result.structured_summary.count("<reaction") >= 2  # Should have nested reactions
        assert 'id="3.1"' in result.structured_summary
        assert 'id="3.1.1"' in result.structured_summary

        print("\n" + "=" * 80)
        print("DEEPLY NESTED REACTIONS TEST RESULT:")
        print("=" * 80)
        print(result.structured_summary)

    def test_empty_turn(self):
        """Test condensing an empty turn with no messages."""
        summarizer = create_turn_condensation_agent()

        turn_context = TurnContext(
            turn_id="4",
            turn_level=0,
            current_step_objective="Empty turn",
            active_character="TestCharacter"
        )

        # Condense empty turn
        result = summarizer.condense_turn_sync(turn_context)

        # Should still produce valid output
        assert isinstance(result, StructuredTurnSummary)
        assert result.structured_summary is not None

        print("\n" + "=" * 80)
        print("EMPTY TURN TEST RESULT:")
        print("=" * 80)
        print(result.structured_summary)

    def test_additional_context(self):
        """Test that additional context is properly formatted and used."""
        summarizer = create_turn_condensation_agent()

        turn_context = TurnContext(
            turn_id="5",
            turn_level=0,
            current_step_objective="Test with context",
            active_character="Legolas"
        )

        turn_context.add_live_message("I shoot two arrows at the orc", "player")
        turn_context.add_live_message("Both hit for 15 damage total!", "dm")

        # Add additional context
        additional_context = {
            "combat_round": 3,
            "current_initiative": 18,
            "location": "Helm's Deep"
        }

        result = summarizer.condense_turn_sync(turn_context, additional_context)

        assert isinstance(result, StructuredTurnSummary)
        assert result.structured_summary is not None

        print("\n" + "=" * 80)
        print("TURN WITH ADDITIONAL CONTEXT TEST RESULT:")
        print("=" * 80)
        print(result.structured_summary)

    @pytest.mark.asyncio
    async def test_async_condensation(self):
        """Test async version of turn condensation."""
        summarizer = create_turn_condensation_agent()

        turn_context = TurnContext(
            turn_id="6",
            turn_level=0,
            current_step_objective="Async test",
            active_character="Gimli"
        )

        turn_context.add_live_message("And my axe!", "player")
        turn_context.add_live_message("You strike true!", "dm")

        # Test async version
        result = await summarizer.condense_turn(turn_context)

        assert isinstance(result, StructuredTurnSummary)
        assert result.structured_summary is not None

        print("\n" + "=" * 80)
        print("ASYNC CONDENSATION TEST RESULT:")
        print("=" * 80)
        print(result.structured_summary)


class TestContextBuilderIntegration:
    """Test integration between Structured Summarizer and Context Builder."""

    def test_context_builder_creates_valid_input(self):
        """Verify context builder creates properly formatted input for the agent."""
        summarizer = create_turn_condensation_agent()

        turn_context = TurnContext(
            turn_id="7",
            turn_level=0,
            current_step_objective="Test context format",
            active_character="Frodo"
        )

        turn_context.add_live_message("I put on the Ring", "player")
        turn_context.add_live_message("You vanish from sight!", "dm")

        # Build context using the context builder
        context = summarizer.context_builder.build_context(turn_context, include_metadata=False)

        # Verify structure
        assert "<turn_log>" in context
        assert "</turn_log>" in context
        assert '<message speaker="player">' in context
        assert '<message speaker="dm">' in context

        print("\n" + "=" * 80)
        print("CONTEXT BUILDER OUTPUT:")
        print("=" * 80)
        print(context)

    def test_full_prompt_generation(self):
        """Test that the full prompt is properly generated."""
        summarizer = create_turn_condensation_agent()

        turn_context = TurnContext(
            turn_id="8",
            turn_level=0,
            current_step_objective="Test prompt",
            active_character="Sam"
        )

        turn_context.add_live_message("I won't leave you, Mr. Frodo!", "player")
        turn_context.add_live_message("Sam's loyalty gives you strength", "dm")

        # Generate full prompt
        prompt = summarizer.context_builder.build_prompt(turn_context)

        # Verify prompt structure
        assert "Condense the following turn" in prompt
        assert "INPUT:" in prompt
        assert "TURN METADATA:" in prompt
        assert "Turn ID: 8" in prompt
        assert "Active Character: Sam" in prompt

        print("\n" + "=" * 80)
        print("FULL PROMPT:")
        print("=" * 80)
        print(prompt)


def run_tests():
    """Run all tests manually (without pytest)."""
    print("\n" + "=" * 80)
    print("RUNNING STRUCTURED TURN SUMMARIZER TESTS")
    print("=" * 80)

    # Basic tests
    test_suite = TestStructuredTurnSummarizer()

    print("\n[TEST 1] Agent Initialization...")
    test_suite.test_agent_initialization()
    print("✓ PASSED")

    print("\n[TEST 2] Simple Turn Condensation...")
    test_suite.test_simple_turn_condensation()
    print("✓ PASSED")

    print("\n[TEST 3] Turn with Nested Reactions...")
    test_suite.test_turn_with_nested_reactions()
    print("✓ PASSED")

    print("\n[TEST 4] Deeply Nested Reactions...")
    test_suite.test_turn_with_deeply_nested_reactions()
    print("✓ PASSED")

    print("\n[TEST 5] Empty Turn...")
    test_suite.test_empty_turn()
    print("✓ PASSED")

    print("\n[TEST 6] Additional Context...")
    test_suite.test_additional_context()
    print("✓ PASSED")

    # Async test
    print("\n[TEST 7] Async Condensation...")
    asyncio.run(test_suite.test_async_condensation())
    print("✓ PASSED")

    # Context builder tests
    context_suite = TestContextBuilderIntegration()

    print("\n[TEST 8] Context Builder Creates Valid Input...")
    context_suite.test_context_builder_creates_valid_input()
    print("✓ PASSED")

    print("\n[TEST 9] Full Prompt Generation...")
    context_suite.test_full_prompt_generation()
    print("✓ PASSED")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
