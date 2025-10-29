"""Quick test to see what the summarizer outputs for reactions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import textwrap
from src.agents.structured_summarizer import create_turn_condensation_agent
from src.models.turn_context import TurnContext


def test_reactions():
    """Test turn with reactions to see actual output."""
    summarizer = create_turn_condensation_agent()

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

    print("=" * 80)
    print("INPUT TO SUMMARIZER:")
    print("=" * 80)
    prompt = summarizer.context_builder.build_prompt(turn_context)
    print(prompt)

    print("\n" + "=" * 80)
    print("OUTPUT FROM SUMMARIZER:")
    print("=" * 80)
    result = summarizer.condense_turn_sync(turn_context)
    print(result.structured_summary)
    print("\n" + "=" * 80)

    # Check what we got
    print("\nCHECKS:")
    print(f"  Contains '<reaction': {('<reaction' in result.structured_summary)}")
    check_id = 'id="2.1"' in result.structured_summary
    print(f"  Contains 'id=\"2.1\"': {check_id}")
    has_counter = 'Counterspell' in result.structured_summary or 'counter' in result.structured_summary.lower()
    print(f"  Contains 'Counterspell' or 'counter': {has_counter}")


if __name__ == "__main__":
    test_reactions()
