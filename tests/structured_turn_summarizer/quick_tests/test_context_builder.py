"""
Test script for the Structured Summarizer Context Builder.

Demonstrates how the context builder formats turn context into XML for the summarizer.
"""

import textwrap

from src.models.turn_context import TurnContext
from src.models.turn_message import create_live_message, create_completed_subturn_message
from src.context.structured_summarizer_context_builder import create_structured_summarizer_context_builder


def test_context_builder():
    """Test the context builder with a sample turn."""

    # Create a sample turn context
    turn_context = TurnContext(
        turn_id="2",
        turn_level=0,
        current_step_objective="Resolve player action",
        active_character="Alice the Wizard"
    )

    # Add some live messages
    turn_context.add_live_message("I want to cast Fireball at the goblin group", "player")
    turn_context.add_live_message("What's your spell save DC?", "dm")
    turn_context.add_live_message("DC 15 Dexterity save, using 3rd level slot", "player")
    turn_context.add_live_message("Goblins roll saves... Chief got 18, others failed", "dm")
    turn_context.add_live_message("The chief tries to counter your spell!", "dm")

    # Add a completed subturn (reaction)
    subturn_summary = textwrap.dedent("""
        <action>"Not today, witch!" the chief snarls, weaving desperate Counterspell magic</action>
        <reaction id="2.1.1" level="2">
          <action>Alice recognizes the counter-magic and fights back with her own Counterspell (rolled 15)</action>
          <resolution>Alice's superior magical training overcomes the crude attempt</resolution>
        </reaction>
        <resolution>The goblin's spell fizzles as Alice's magic dominates the weave</resolution>
    """).strip()

    turn_context.add_completed_subturn(subturn_summary, "2.1")

    # Add more live messages after the reaction
    turn_context.add_live_message("Yes! Does my Fireball go off?", "player")
    turn_context.add_live_message("Your counter succeeds! Fireball explodes for 28 fire damage", "dm")
    turn_context.add_live_message("The blast terrifies the survivors - they're fleeing!", "dm")

    # Add another completed subturn
    fleeing_summary = textwrap.dedent("""
        <action>Witnessing their chief's magical failure and comrades' immolation, remaining goblins flee in terror</action>
        <resolution>Three goblins break formation and sprint for the cave entrance</resolution>
    """).strip()

    turn_context.add_completed_subturn(fleeing_summary, "2.2")

    # Build the context
    context_builder = create_structured_summarizer_context_builder()

    print("=" * 80)
    print("CONTEXT (with metadata):")
    print("=" * 80)
    xml_context = context_builder.build_context(turn_context, include_metadata=True)
    print(xml_context)

    print("\n" + "=" * 80)
    print("FULL PROMPT:")
    print("=" * 80)
    prompt = context_builder.build_prompt(turn_context)
    print(prompt)


if __name__ == "__main__":
    test_context_builder()
