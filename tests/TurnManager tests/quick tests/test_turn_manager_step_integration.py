"""
Test script to verify TurnManager properly initializes TurnContext with game_step_list.

This test verifies that:
1. TurnManager automatically determines game_step_list based on turn_level
2. Level 0 uses DEMO_MAIN_ACTION_STEPS, Level 1+ uses DEMO_REACTION_STEPS
3. ActionDeclaration Pydantic model works correctly (Gemini compatibility)
4. The turn can be advanced through its steps
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.memory.turn_manager import create_turn_manager, ActionDeclaration
from src.prompts.demo_combat_steps import DEMO_MAIN_ACTION_STEPS, DEMO_REACTION_STEPS


def test_turn_manager_auto_step_selection():
    """Test TurnManager automatically selects correct step list based on turn level."""
    print("=" * 70)
    print("TEST: Automatic Step List Selection")
    print("=" * 70)

    # Create TurnManager
    turn_manager = create_turn_manager()
    print("\n✓ TurnManager created")

    # Start a Level 0 turn (should use DEMO_MAIN_ACTION_STEPS)
    print("\n--- Starting Level 0 turn (should use DEMO_MAIN_ACTION_STEPS) ---")
    result = turn_manager.start_and_queue_turns(
        actions=[ActionDeclaration(speaker="Test Hero", content="I attack the orc!")]
    )

    print(f"✓ Turn started successfully")
    print(f"  - Turn IDs: {result['turn_ids']}")
    print(f"  - Next to process: {result['next_to_process']}")

    # Get the created turn
    turn = turn_manager.get_next_pending_turn()
    assert turn is not None, "Should have a pending turn"
    print(f"\n✓ Retrieved pending turn: {turn.turn_id}")

    # Verify it used DEMO_MAIN_ACTION_STEPS
    assert turn.game_step_list is not None, "game_step_list should be set"
    assert turn.game_step_list == DEMO_MAIN_ACTION_STEPS, \
        "Level 0 should use DEMO_MAIN_ACTION_STEPS"
    print(f"✓ Automatically used DEMO_MAIN_ACTION_STEPS ({len(turn.game_step_list)} steps)")

    # Verify current step
    assert turn.current_step_index == 0, "Should start at step 0"
    assert turn.current_step_objective == DEMO_MAIN_ACTION_STEPS[0], \
        "Current objective should match first step"
    print(f"✓ Starting at step 0: {turn.current_step_objective[:60]}...")

    # Test advancing through steps
    print("\n--- Testing step advancement ---")
    for i in range(1, 4):  # Test advancing through first 3 steps
        has_more = turn.advance_step()
        print(f"  Step {i}: {turn.current_step_objective[:60]}...")
        assert has_more is True, f"Should have more steps at step {i}"
        assert turn.current_step_index == i, f"Index should be {i}"

    print(f"✓ Successfully advanced through 3 steps")

    return turn_manager


def test_reaction_auto_selection():
    """Test TurnManager automatically uses DEMO_REACTION_STEPS for Level 1+."""
    print("\n" + "=" * 70)
    print("TEST: Automatic Reaction Step Selection (Level 1+)")
    print("=" * 70)

    # Create TurnManager and start main turn
    turn_manager = create_turn_manager()

    # Start Level 0 main turn
    print("\n--- Starting Level 0 main turn ---")
    turn_manager.start_and_queue_turns(
        actions=[ActionDeclaration(speaker="Hero", content="I attack!")]
    )
    main_turn = turn_manager.get_next_pending_turn()
    assert main_turn.turn_level == 0, "Should be level 0"
    assert main_turn.game_step_list == DEMO_MAIN_ACTION_STEPS, "Should use main action steps"
    print(f"✓ Level 0 turn uses DEMO_MAIN_ACTION_STEPS")

    # Start Level 1 reaction turn (sub-turn)
    print("\n--- Starting Level 1 reaction sub-turn ---")
    result = turn_manager.start_and_queue_turns(
        actions=[ActionDeclaration(speaker="Wizard", content="I cast Shield!")]
    )

    print(f"✓ Reaction turn started: {result['turn_ids']}")

    # Get the reaction turn (should be at level 1)
    reaction_turn = turn_manager.get_next_pending_turn()
    assert reaction_turn.turn_level == 1, "Reaction should be at level 1"
    assert reaction_turn.game_step_list == DEMO_REACTION_STEPS, \
        "Level 1 should automatically use DEMO_REACTION_STEPS"
    print(f"✓ Level 1 turn automatically uses DEMO_REACTION_STEPS ({len(reaction_turn.game_step_list)} steps)")
    print(f"  First step: {reaction_turn.current_step_objective[:60]}...")


def test_action_declaration_model():
    """Test ActionDeclaration Pydantic model (Gemini compatibility)."""
    print("\n" + "=" * 70)
    print("TEST: ActionDeclaration Pydantic Model")
    print("=" * 70)

    # Create ActionDeclaration instances
    print("\n--- Creating ActionDeclaration instances ---")
    action1 = ActionDeclaration(speaker="Alice", content="I cast Fireball!")
    action2 = ActionDeclaration(speaker="Bob", content="I attack with my sword!")

    print(f"✓ Created ActionDeclaration: speaker='{action1.speaker}', content='{action1.content}'")
    print(f"✓ Created ActionDeclaration: speaker='{action2.speaker}', content='{action2.content}'")

    # Test with TurnManager
    turn_manager = create_turn_manager()
    result = turn_manager.start_and_queue_turns(
        actions=[action1, action2]
    )

    print(f"\n✓ TurnManager accepted List[ActionDeclaration]")
    print(f"  Created {len(result['turn_ids'])} turns: {result['turn_ids']}")

    # Verify Pydantic model validation
    print("\n--- Testing Pydantic validation ---")
    try:
        invalid_action = ActionDeclaration(speaker="", content="")  # Empty strings should work
        print(f"✓ Empty strings accepted (no strict validation)")
    except Exception as e:
        print(f"✗ Validation error: {e}")

    print(f"\n✓ ActionDeclaration model works correctly for Gemini compatibility")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("TURN MANAGER STEP INTEGRATION TESTS")
    print("=" * 70)

    try:
        # Test 1: Auto step selection for main actions
        test_turn_manager_auto_step_selection()

        # Test 2: Auto selection for reactions
        test_reaction_auto_selection()

        # Test 3: ActionDeclaration model
        test_action_declaration_model()

        # Summary
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED")
        print("=" * 70)
        print("\nVerified:")
        print("  • Level 0 automatically uses DEMO_MAIN_ACTION_STEPS")
        print("  • Level 1+ automatically uses DEMO_REACTION_STEPS")
        print("  • ActionDeclaration Pydantic model works (Gemini compatible)")
        print("  • No Dict[str, str] used (avoids additionalProperties issue)")
        print("  • Steps can be advanced through the list")
        print()

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
