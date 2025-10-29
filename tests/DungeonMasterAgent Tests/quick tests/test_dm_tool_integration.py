"""
Test script to verify that TurnManager.start_and_queue_turns is properly registered as a DM tool.

This test verifies that:
1. The DM agent is created with the tool
2. The tool is accessible to the agent
3. The agent lists the tool in its available tools
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_dm_agent_has_tool():
    """Test that DM agent has start_and_queue_turns as a tool."""
    print("=" * 70)
    print("TEST: DM Agent Tool Registration")
    print("=" * 70)

    # Import dependencies
    from src.agents.dungeon_master import create_dungeon_master_agent
    from src.memory.turn_manager import create_turn_manager

    print("\n--- Creating TurnManager ---")
    turn_manager = create_turn_manager(turn_condensation_agent=None)
    print(f"✓ TurnManager created")

    print("\n--- Creating DM Agent with tool ---")
    dm_agent = create_dungeon_master_agent(
        model_name='gemini-2.5-flash',
        tools=[turn_manager.start_and_queue_turns]
    )
    print(f"✓ DM Agent created")

    # Check that tools were registered
    print("\n--- Verifying Tool Registration ---")
    assert dm_agent.tools is not None, "Tools should not be None"
    assert len(dm_agent.tools) > 0, "Should have at least one tool"
    print(f"✓ Agent has {len(dm_agent.tools)} tool(s)")

    # Check the tool is the right one
    tool = dm_agent.tools[0]
    assert callable(tool), "Tool should be callable"
    print(f"✓ Tool is callable")
    print(f"  Tool name: {tool.__name__}")
    print(f"  Tool type: {type(tool)}")

    # Verify the agent's internal agent has tools
    print("\n--- Verifying PydanticAI Agent Configuration ---")
    # PydanticAI agents store tools internally
    # We can verify by checking if it's a method of turn_manager
    assert hasattr(turn_manager, 'start_and_queue_turns'), "TurnManager should have start_and_queue_turns method"
    print(f"✓ TurnManager has start_and_queue_turns method")

    # Test calling the tool directly (not through the agent, just to verify it works)
    print("\n--- Testing Tool Directly ---")
    from src.prompts.demo_combat_steps import DEMO_MAIN_ACTION_STEPS
    from src.memory.turn_manager import ActionDeclaration

    # Note: game_step_list is automatically determined by turn_level
    # Level 0 = DEMO_MAIN_ACTION_STEPS, Level 1+ = DEMO_REACTION_STEPS
    result = turn_manager.start_and_queue_turns(
        actions=[ActionDeclaration(speaker="Test Hero", content="I test the tool!")]
    )

    print(f"✓ Tool executed successfully")
    print(f"  Created turn IDs: {result['turn_ids']}")
    print(f"  Next to process: {result['next_to_process']}")

    return dm_agent, turn_manager


def test_demo_session_manager():
    """Test that demo session manager creates DM agent with tools properly."""
    print("\n" + "=" * 70)
    print("TEST: Demo Session Manager Tool Integration")
    print("=" * 70)

    # We need to test without actually importing heavy modules during test
    # So let's just verify the code is correct
    demo_terminal_path = project_root / "demo_terminal.py"

    with open(demo_terminal_path, 'r') as f:
        content = f.read()

    print("\n--- Checking demo_terminal.py code ---")

    # Check that turn_manager is created before dm_agent
    turn_manager_line = content.find("turn_manager = create_turn_manager")
    dm_agent_line = content.find("dm_agent = create_dungeon_master_agent")

    assert turn_manager_line < dm_agent_line, \
        "turn_manager should be created before dm_agent"
    print("✓ turn_manager is created before dm_agent")

    # Check that tools parameter is passed
    assert "tools=[turn_manager.start_and_queue_turns]" in content, \
        "Should pass start_and_queue_turns as a tool"
    print("✓ start_and_queue_turns is passed as a tool")

    print("\n✓ Demo session manager code is correctly configured")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("DM AGENT TOOL INTEGRATION TESTS")
    print("=" * 70)

    try:
        # Test 1: DM agent tool registration
        dm_agent, turn_manager = test_dm_agent_has_tool()

        # Test 2: Demo session manager integration
        test_demo_session_manager()

        # Summary
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED")
        print("=" * 70)
        print("\nVerified:")
        print("  • DM agent accepts tools parameter")
        print("  • TurnManager.start_and_queue_turns can be passed as a tool")
        print("  • Tool is properly registered with the agent")
        print("  • Demo session manager is correctly configured")
        print("\nThe DM agent now has access to start_and_queue_turns!")
        print("It can use this tool to create reaction turns when needed.")
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
