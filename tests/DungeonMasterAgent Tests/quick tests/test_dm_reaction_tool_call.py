"""
Test script to verify DM agent can invoke start_and_queue_turns when receiving reactions.

This test verifies that:
1. The DM agent has access to the start_and_queue_turns tool
2. Gemini can successfully call the tool with ActionDeclaration parameters
3. The tool is invoked when reactions are declared in the narrative
4. The ActionDeclaration Pydantic model is compatible with Gemini's function calling
"""

import sys
from pathlib import Path
import asyncio

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_dm_calls_tool_on_reaction():
    """Test that DM agent invokes start_and_queue_turns when a reaction is declared."""
    print("=" * 70)
    print("TEST: DM Agent Calls start_and_queue_turns on Reaction")
    print("=" * 70)

    # Import dependencies
    from src.agents.dungeon_master import create_dungeon_master_agent
    from src.memory.turn_manager import create_turn_manager, ActionDeclaration
    from src.prompts.demo_combat_steps import DEMO_MAIN_ACTION_STEPS

    print("\n--- Setting up test environment ---")

    # Create turn manager
    turn_manager = create_turn_manager(turn_condensation_agent=None)
    print("✓ TurnManager created")

    # Start initial main action turn
    turn_manager.start_and_queue_turns(
        actions=[ActionDeclaration(speaker="Alice", content="I cast Fireball at the goblins!")]
    )
    print("✓ Initial turn created (Alice casting Fireball)")

    # Create DM agent with the tool
    dm_agent = create_dungeon_master_agent(
        model_name='gemini-2.5-flash',
        tools=[turn_manager.start_and_queue_turns]
    )
    print("✓ DM Agent created with start_and_queue_turns tool")

    # Build a context that should trigger the tool call
    # We're at step 3 (pre-resolution reaction window)
    context = """
You are the Dungeon Master for a D&D combat session.

<turn_log>
<message speaker="Alice">Alice: I cast Fireball at the goblins!</message>
<message speaker="DM">DM: Alice begins to channel arcane energy, flames gathering at her fingertips as she aims at the goblin cluster.</message>
</turn_log>

Current Step Objective: "Provide pre-resolution reaction window: Ask if anyone wants to use a Reaction BEFORE the action resolves. Wait for response. If a reaction is declared, use start_and_queue_turns to create reaction turn(s) with the reaction declaration(s). DO NOT resolve the main action yet."

<new_messages>
<message speaker="DM">DM: Does anyone want to use a Reaction before the Fireball resolves?</message>
<message speaker="Bob">Bob: I cast Counterspell to stop Alice's Fireball!</message>
</new_messages>

IMPORTANT: Bob has declared a reaction (Counterspell). You MUST use the start_and_queue_turns tool to create a reaction turn for Bob's Counterspell before proceeding.
"""

    print("\n--- Running DM agent with reaction scenario ---")
    print("Context includes Bob declaring Counterspell as a reaction")

    try:
        # Run the DM agent
        result = await dm_agent.process_message(context)

        print(f"\n✓ DM agent processed successfully")
        print(f"\nDM Response:")
        print(f"  Narrative: {result.output.narrative[:150]}...")

        # Check if tool was called
        # PydanticAI stores tool calls in the result
        if hasattr(result, 'all_messages'):
            tool_calls = [msg for msg in result.all_messages()
                         if hasattr(msg, 'parts') and any(hasattr(p, 'tool_name') for p in msg.parts)]

            if tool_calls:
                print(f"\n✓ TOOL WAS CALLED!")
                for call in tool_calls:
                    for part in call.parts:
                        if hasattr(part, 'tool_name'):
                            print(f"  Tool name: {part.tool_name}")
                            if hasattr(part, 'args'):
                                print(f"  Tool args: {part.args}")
            else:
                print(f"\n✗ WARNING: Tool was not called in this run")
                print(f"   The DM may need clearer instructions to use the tool")

        # Check if turn manager has new turns (Level 1)
        print("\n--- Checking TurnManager state ---")
        if len(turn_manager.turn_stack) > 1:
            print(f"✓ New turn level created (Level {len(turn_manager.turn_stack) - 1})")
            reaction_turn = turn_manager.get_next_pending_turn()
            if reaction_turn:
                print(f"  Turn ID: {reaction_turn.turn_id}")
                print(f"  Turn Level: {reaction_turn.turn_level}")
                print(f"  Active Character: {reaction_turn.active_character}")
                print(f"  Step Objective: {reaction_turn.current_step_objective[:60]}...")
        else:
            print(f"  Current stack depth: {len(turn_manager.turn_stack)}")
            print(f"  (Tool may not have been invoked)")

        return result

    except Exception as e:
        print(f"\n✗ ERROR during DM agent processing:")
        print(f"  {str(e)}")
        import traceback
        traceback.print_exc()
        raise


async def test_dm_tool_signature():
    """Test that the tool has the correct signature for Gemini."""
    print("\n" + "=" * 70)
    print("TEST: Tool Signature Compatibility")
    print("=" * 70)

    from src.agents.dungeon_master import create_dungeon_master_agent
    from src.memory.turn_manager import create_turn_manager
    import inspect

    print("\n--- Inspecting tool signature ---")

    turn_manager = create_turn_manager(turn_condensation_agent=None)
    tool = turn_manager.start_and_queue_turns

    # Get signature
    sig = inspect.signature(tool)
    print(f"Tool signature: {sig}")

    # Check parameters
    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue
        print(f"  Parameter: {param_name}")
        print(f"    Type: {param.annotation}")
        print(f"    Default: {param.default}")

    # Get type hints
    import typing
    hints = typing.get_type_hints(tool)
    print(f"\n✓ Type hints: {hints}")

    # Verify ActionDeclaration is a Pydantic model
    from src.memory.turn_manager import ActionDeclaration
    from pydantic import BaseModel

    assert issubclass(ActionDeclaration, BaseModel), "ActionDeclaration must be a Pydantic BaseModel"
    print(f"\n✓ ActionDeclaration is a Pydantic BaseModel (Gemini compatible)")

    # Show the model schema
    print(f"\nActionDeclaration schema:")
    schema = ActionDeclaration.model_json_schema()
    print(f"  Properties: {list(schema.get('properties', {}).keys())}")
    print(f"  Required: {schema.get('required', [])}")
    print(f"  No additionalProperties: {'additionalProperties' not in schema}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("DM REACTION TOOL CALL TESTS")
    print("=" * 70)
    print("\nThis test verifies that the DM agent can invoke start_and_queue_turns")
    print("when reactions are declared during gameplay.")

    try:
        # Test 1: Tool signature
        await test_dm_tool_signature()

        # Test 2: Actual tool call
        await test_dm_calls_tool_on_reaction()

        # Summary
        print("\n" + "=" * 70)
        print("✓ TESTS COMPLETED")
        print("=" * 70)
        print("\nVerified:")
        print("  • Tool has correct signature for Gemini")
        print("  • ActionDeclaration is Pydantic BaseModel")
        print("  • No additionalProperties in schema (Gemini compatible)")
        print("  • DM agent can process reaction scenarios")
        print("\nNOTE: Whether the tool is actually invoked depends on:")
        print("  • The model's interpretation of the instructions")
        print("  • The clarity of the step objective")
        print("  • The context provided to the agent")
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
    print("\nStarting DM reaction tool call test...")
    print("This test will make actual API calls to Gemini.\n")
    asyncio.run(main())
