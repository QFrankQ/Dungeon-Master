"""
Test script to verify game_step_list initialization and advance_step() functionality.

This test verifies that:
1. TurnContext is properly initialized with game_step_list
2. The current_step_objective matches the first step in the list
3. advance_step() properly progresses through the step list
4. advance_step() returns False when all steps are complete
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.models.turn_context import TurnContext
from src.prompts.demo_combat_steps import DEMO_MAIN_ACTION_STEPS, DEMO_REACTION_STEPS


def test_step_initialization():
    """Test that TurnContext properly initializes with game_step_list."""
    print("=" * 70)
    print("TEST 1: Step List Initialization")
    print("=" * 70)

    # Create a TurnContext with game_step_list
    turn = TurnContext(
        turn_id="test_1",
        turn_level=0,
        current_step_objective=DEMO_MAIN_ACTION_STEPS[0],
        active_character="Test Hero",
        game_step_list=DEMO_MAIN_ACTION_STEPS,
        current_step_index=0
    )

    print(f"\n✓ TurnContext created with game_step_list")
    print(f"  - Turn ID: {turn.turn_id}")
    print(f"  - Active Character: {turn.active_character}")
    print(f"  - Game Step List Length: {len(turn.game_step_list)}")
    print(f"  - Current Step Index: {turn.current_step_index}")
    print(f"  - Current Step Objective: {turn.current_step_objective[:60]}...")

    # Verify the objective matches the first step
    assert turn.current_step_objective == DEMO_MAIN_ACTION_STEPS[0], \
        "Current step objective should match first step in list"
    print(f"\n✓ Current step objective matches first step in list")

    return turn


def test_advance_step(turn):
    """Test that advance_step() properly progresses through steps."""
    print("\n" + "=" * 70)
    print("TEST 2: Step Advancement")
    print("=" * 70)

    total_steps = len(turn.game_step_list)
    print(f"\nTotal steps in list: {total_steps}")

    for i in range(1, total_steps):
        print(f"\n--- Advancing to step {i + 1} ---")
        has_more = turn.advance_step()

        print(f"  advance_step() returned: {has_more}")
        print(f"  Current index: {turn.current_step_index}")
        print(f"  Current objective: {turn.current_step_objective[:60]}...")

        # Verify the objective was updated correctly
        expected_objective = turn.game_step_list[i]
        assert turn.current_step_objective == expected_objective, \
            f"Step {i}: Expected '{expected_objective}', got '{turn.current_step_objective}'"

        # Should return True if more steps remain
        if i < total_steps - 1:
            assert has_more is True, f"Should return True when steps remain (step {i})"
            print(f"  ✓ More steps available")
        else:
            # Last step - should still return True because we're on the last step
            assert has_more is True, f"Should return True on last step (step {i})"
            print(f"  ✓ On last step")

    # Try advancing past the last step
    print(f"\n--- Advancing past last step ---")
    has_more = turn.advance_step()
    print(f"  advance_step() returned: {has_more}")
    print(f"  Current index: {turn.current_step_index}")

    assert has_more is False, "Should return False when no more steps remain"
    print(f"  ✓ Correctly returns False when all steps complete")


def test_get_current_step_objective():
    """Test get_current_step_objective() method."""
    print("\n" + "=" * 70)
    print("TEST 3: Get Current Step Objective")
    print("=" * 70)

    # Create turn with step list
    turn = TurnContext(
        turn_id="test_2",
        turn_level=0,
        current_step_objective="Manual objective",
        active_character="Test Hero",
        game_step_list=DEMO_REACTION_STEPS,
        current_step_index=0
    )

    # Should return from game_step_list when available
    objective = turn.get_current_step_objective()
    assert objective == DEMO_REACTION_STEPS[0], \
        "Should return from game_step_list when available"
    print(f"\n✓ Returns step from game_step_list: {objective[:60]}...")

    # Advance to second step
    turn.advance_step()
    objective = turn.get_current_step_objective()
    assert objective == DEMO_REACTION_STEPS[1], \
        "Should return updated step after advance"
    print(f"✓ Returns updated step after advance: {objective[:60]}...")

    # Test fallback when no step list
    turn_no_list = TurnContext(
        turn_id="test_3",
        turn_level=0,
        current_step_objective="Manual fallback objective",
        active_character="Test Hero"
    )

    objective = turn_no_list.get_current_step_objective()
    assert objective == "Manual fallback objective", \
        "Should fallback to current_step_objective when no game_step_list"
    print(f"✓ Fallback to manual objective when no list: {objective}")


def test_without_step_list():
    """Test that advance_step() raises error when no game_step_list."""
    print("\n" + "=" * 70)
    print("TEST 4: Error Handling Without Step List")
    print("=" * 70)

    # Create turn without step list
    turn = TurnContext(
        turn_id="test_4",
        turn_level=0,
        current_step_objective="Manual objective",
        active_character="Test Hero"
    )

    print(f"\n✓ TurnContext created without game_step_list")

    # Should raise ValueError when trying to advance
    try:
        turn.advance_step()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"✓ Correctly raises ValueError: {str(e)}")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("GAME STEP INITIALIZATION & ADVANCEMENT TESTS")
    print("=" * 70)

    try:
        # Test 1: Initialization
        turn = test_step_initialization()

        # Test 2: Step advancement
        test_advance_step(turn)

        # Test 3: Get current step objective
        test_get_current_step_objective()

        # Test 4: Error handling
        test_without_step_list()

        # Summary
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED")
        print("=" * 70)
        print("\nVerified:")
        print("  • TurnContext properly initializes with game_step_list")
        print("  • Current step objective matches first step in list")
        print("  • advance_step() progresses through all steps correctly")
        print("  • advance_step() returns False when steps are complete")
        print("  • get_current_step_objective() works with and without step list")
        print("  • Proper error handling when no step list exists")
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
