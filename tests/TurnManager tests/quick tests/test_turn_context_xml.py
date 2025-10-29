"""
Test script for TurnContext.to_xml_context() method.

Verifies that the dataclass methods handle indentation properly.
"""

import textwrap
from src.models.turn_context import TurnContext


def test_turn_context_xml():
    """Test TurnContext.to_xml_context() with proper indentation."""

    # Create a sample turn context
    turn_context = TurnContext(
        turn_id="2",
        turn_level=0,
        current_step_objective="Resolve player action",
        active_character="Alice the Wizard"
    )

    # Add some live messages
    turn_context.add_live_message("I cast Fireball at the goblins", "player")
    turn_context.add_live_message("Roll for damage!", "dm")

    # Add a completed subturn (reaction)
    subturn_summary = textwrap.dedent("""
        <action>Goblin chief attempts Counterspell</action>
        <resolution>Fails due to low spellcasting ability</resolution>
    """).strip()

    turn_context.add_completed_subturn(subturn_summary, "2.1")

    # Add more messages
    turn_context.add_live_message("28 fire damage!", "player")
    turn_context.add_live_message("The goblins are incinerated!", "dm")

    # Test to_xml_context() method
    print("=" * 80)
    print("TurnContext.to_xml_context() OUTPUT:")
    print("=" * 80)
    xml_output = turn_context.to_xml_context()
    print(xml_output)

    # Test with exclude_new_messages=True
    print("\n" + "=" * 80)
    print("With exclude_new_messages=True (should exclude MessageGroups with is_new_message=True):")
    print("=" * 80)
    xml_output_filtered = turn_context.to_xml_context(exclude_new_messages=True)
    print(xml_output_filtered)


if __name__ == "__main__":
    test_turn_context_xml()
