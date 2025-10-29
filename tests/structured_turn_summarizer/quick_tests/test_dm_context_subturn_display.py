"""
Test that subturn summaries appear in DM context builder output.

Verifies that completed subturn messages are properly displayed in the
DM context when building context for the parent turn.
"""

import sys
from pathlib import Path
import asyncio

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.memory.turn_manager import TurnManager, ActionDeclaration
from src.agents.structured_summarizer import create_turn_condensation_agent
from src.context.dm_context_builder import DMContextBuilder


async def test_subturn_in_dm_context():
    """
    Test that completed subturn summaries appear in DM context.
    """
    print("\n" + "="*80)
    print("TEST: Subturn Summaries in DM Context")
    print("="*80)

    # Setup
    condensation_agent = create_turn_condensation_agent()
    turn_manager = TurnManager(turn_condensation_agent=condensation_agent)
    dm_context_builder = DMContextBuilder()

    # Step 1: Create main turn
    print("\n[Step 1] Creating main turn with player action...")
    turn_manager.start_and_queue_turns([
        ActionDeclaration(speaker="Alice", content="I cast Fireball at the goblins!")
    ])
    turn_manager.add_messages([
        {"content": "DC 15 Dexterity save!", "speaker": "Alice"}
    ])

    # Step 2: Create reaction subturn
    print("\n[Step 2] Creating reaction subturn...")
    turn_manager.start_and_queue_turns([
        ActionDeclaration(speaker="Goblin Chief", content="I cast Shield!")
    ])
    turn_manager.add_messages([
        {"content": "Shield spell increases AC by 5", "speaker": "DM"},
        {"content": "The magical barrier glows around the goblin chief", "speaker": "DM"}
    ])

    # Step 3: End the subturn (should condense and add to parent)
    print("\n[Step 3] Ending subturn (should trigger condensation)...")
    end_result = await turn_manager.end_turn()

    print(f"Subturn ended: {end_result['turn_id']}")
    print(f"Condensation result exists: {end_result['condensation_result'] is not None}")
    print(f"Embedded in parent: {end_result['embedded_in_parent']}")

    if end_result['condensation_result']:
        print(f"\nCondensed summary:")
        print(end_result['condensation_result'].structured_summary)

    # Step 4: Check parent turn messages
    print("\n[Step 4] Checking parent turn messages...")
    parent_turn = turn_manager.get_current_turn_context()
    print(f"Parent turn ID: {parent_turn.turn_id}")
    print(f"Parent turn message count: {len(parent_turn.messages)}")

    from src.models.turn_message import MessageType
    completed_subturns = [
        msg for msg in parent_turn.messages
        if hasattr(msg, 'message_type') and msg.message_type == MessageType.COMPLETED_SUBTURN
    ]
    print(f"Completed subturn messages in parent: {len(completed_subturns)}")

    if completed_subturns:
        print(f"\nCompleted subturn content:")
        print(completed_subturns[0].content)

    # Step 5: Build DM context and verify subturn appears
    print("\n[Step 5] Building DM context...")
    snapshot = turn_manager.get_snapshot()

    # Use regular build_context method
    dm_context = dm_context_builder.build_demo_context(snapshot)

    print("\n" + "="*80)
    print("DM CONTEXT OUTPUT:")
    print("="*80)
    print(dm_context)
    print("="*80)

    # Step 6: Verify subturn appears in context
    print("\n[Step 6] Verifying subturn appears in DM context...")
    has_reaction_tag = "<reaction" in dm_context
    has_subturn_id = "1.1" in dm_context

    print(f"Has <reaction> tag: {has_reaction_tag}")
    print(f"Has subturn ID (1.1): {has_subturn_id}")

    if not has_reaction_tag:
        print("\n❌ PROBLEM: <reaction> tag not found in DM context!")
        print("This means completed subturn summaries are not appearing.")

        # Debug: Check what's in the parent turn XML
        print("\n[DEBUG] Parent turn XML:")
        parent_xml = parent_turn.to_xml_context(exclude_new_messages=True)
        print(parent_xml)

        return False

    if not has_subturn_id:
        print("\n⚠️  WARNING: Subturn ID '1.1' not found in context")
        print("The reaction tag exists but may not have the correct ID")
        return False

    print("\n✓ TEST PASSED: Subturn summaries appear in DM context!")
    return True


async def test_multiple_subturns_in_context():
    """
    Test that multiple subturn summaries all appear in DM context.
    """
    print("\n" + "="*80)
    print("TEST: Multiple Subturn Summaries in DM Context")
    print("="*80)

    # Setup
    condensation_agent = create_turn_condensation_agent()
    turn_manager = TurnManager(turn_condensation_agent=condensation_agent)
    dm_context_builder = DMContextBuilder()

    # Create main turn
    print("\n[Step 1] Creating main turn...")
    turn_manager.start_and_queue_turns([
        ActionDeclaration(speaker="Alice", content="I cast Chain Lightning!")
    ])

    # Create and end first subturn
    print("\n[Step 2] Creating first reaction...")
    turn_manager.start_and_queue_turns([
        ActionDeclaration(speaker="Enemy Wizard", content="I Counterspell!")
    ])
    first_subturn = turn_manager.get_current_turn_context()
    print(f"First subturn ID: {first_subturn.turn_id}")
    turn_manager.add_messages([
        {"content": "Enemy wizard attempts to counter", "speaker": "DM"}
    ])
    end1 = await turn_manager.end_turn()
    print(f"First subturn ended with ID: {end1['turn_id']}")

    # Create and end second subturn
    print("\n[Step 3] Creating second reaction...")
    turn_manager.start_and_queue_turns([
        ActionDeclaration(speaker="Bob", content="I Counterspell the enemy's Counterspell!")
    ])
    second_subturn = turn_manager.get_current_turn_context()
    print(f"Second subturn ID: {second_subturn.turn_id}")
    turn_manager.add_messages([
        {"content": "Bob counters the counter!", "speaker": "DM"}
    ])
    end2 = await turn_manager.end_turn()
    print(f"Second subturn ended with ID: {end2['turn_id']}")

    # Build DM context
    print("\n[Step 4] Building DM context...")
    snapshot = turn_manager.get_snapshot()
    dm_context = dm_context_builder.build_demo_context(snapshot)

    print("\n" + "="*80)
    print("DM CONTEXT OUTPUT:")
    print("="*80)
    print(dm_context)
    print("="*80)

    # Verify both subturns appear
    print("\n[Step 5] Verifying both subturns appear...")
    reaction_count = dm_context.count("<reaction")
    print(f"Number of <reaction> tags: {reaction_count}")

    has_first_subturn = "1.1" in dm_context
    has_second_subturn = "1.2" in dm_context

    print(f"Has first subturn (1.1): {has_first_subturn}")
    print(f"Has second subturn (1.2): {has_second_subturn}")

    if reaction_count >= 2 and has_first_subturn and has_second_subturn:
        print("\n✓ TEST PASSED: Multiple subturn summaries appear in DM context!")
        return True
    else:
        print("\n❌ PROBLEM: Not all subturn summaries are appearing!")
        return False


async def run_all_tests():
    """Run all test cases."""
    print("\n" + "="*80)
    print("DM CONTEXT SUBTURN DISPLAY TEST SUITE")
    print("="*80)

    try:
        # Test 1: Single subturn in context
        result1 = await test_subturn_in_dm_context()

        # Test 2: Multiple subturns in context
        result2 = await test_multiple_subturns_in_context()

        if result1 and result2:
            print("\n" + "="*80)
            print("ALL TESTS PASSED!")
            print("="*80)
            print("\nKey Findings:")
            print("✓ Completed subturn summaries appear in DM context")
            print("✓ Multiple subturn summaries are all displayed")
            print("✓ Subturn summaries are wrapped in <reaction> tags with IDs")
        else:
            print("\n" + "="*80)
            print("SOME TESTS FAILED")
            print("="*80)

    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
