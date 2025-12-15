"""
Demo combat step objectives for mock Game Director.

Based on combat_flow.txt Phase 2 (Combat Rounds), specifically:
- Steps A-F for main action processing
- Adjudication Sub-Routine for reactions

These objectives guide the DM through proper combat flow without an actual GD agent.
"""

# Main action steps (Steps A-F from combat_flow.txt)
# Used for processing a participant's full turn
DEMO_MAIN_ACTION_STEPS = [
    
    "Greet the player and describe the initial combat scene. Set the stage for combat.",
    
    # Step A: Announce Current Turn
    # "Announce whose turn it is and check for any turn-start effects. If no turn-start effects apply, simply announce the turn. DO NOT ask for action yet.",
    "Call for initiative rolls from all participants. Wait for the player to provide their initiative roll. DO NOT proceed until you have the roll. Once you have all the rolls, announce the initiative order then PROCEED to the next step.",

    # Step C: Process Main Turn Actions - Adjudication Step 1
    "Receive and interpret the participant's declared action. Use action interpretation guidelines (Attack, Dash, Disengage, Dodge, Help, Hide, Influence, Magic, Ready, Search, Study, Utilize). Confirm what action they are taking. DO NOT confirm action cost yet. DO NOT resolve the action yet.",

    # Step C: Process Main Turn Actions - Adjudication Step 2
    # "If the action is Influence, Search, Study, or Utilize, confirm the action cost (using their Action). Ask: 'This will use your Action for the turn. Do you still want to do this?' Otherwise, acknowledge and proceed. DO NOT provide reaction window yet.",

    # Step C: Process Main Turn Actions - Adjudication Step 3
    "Provide pre-resolution reaction window: Ask if anyone wants to use a Reaction BEFORE the action resolves. Wait for response. If a reaction is declared, use start_and_queue_turns to create reaction turn(s) with the reaction declaration(s). DO NOT resolve the main action yet.",

    # Step C: Process Main Turn Actions - Adjudication Step 4
    "Resolve the declared action: Validate the action, call for necessary rolls, determine outcome, and narrate the result. DO NOT check for status changes yet.",

    # Step C: Process Main Turn Actions - Adjudication Step 5
    # "Handle critical status changes and zero hit points: Check if anyone dropped to 0 HP. For PCs, they fall unconscious and begin death saves. For NPCs, they are dead. Narrate the consequences. DO NOT provide reaction window yet.",

    # Step C: Process Main Turn Actions - Adjudication Step 6
    "Provide post-resolution reaction window: Ask if anyone wants to use a Reaction AFTER the action's outcome. Wait for response. If a reaction is declared, use start_and_queue_turns to create reaction turn(s) with the reaction declaration(s). DO NOT ask about other actions yet.",

    # Step D: Confirm End of Turn
    "Ask the active participant: 'Would you like to do anything else on your turn?' (bonus action, movement, item interaction). Wait for response. If they declare another action, process it. Otherwise proceed. DO NOT check turn-end effects yet.",

    # Step E: Check for Turn-End Effects
    # "Check for turn-end effects: Apply ongoing damage, conditions, or trigger Legendary Actions if applicable. If none apply, acknowledge and proceed. DO NOT announce next turn yet.",

    # Step F: Announce Next Turn
    "Announce the end of current participant's turn and state which participant is next in initiative order. Prompt them for their intended action."
]

# Reaction steps (Adjudication sub-routine only)
# Used when reactions are declared during pre-resolution or post-resolution windows
DEMO_REACTION_STEPS = [
    # Adjudication Step 1: Receive and Interpret
    "Receive and interpret the declared reaction. Confirm what reaction they are using, its trigger, and verify it's valid for the current situation. DO NOT confirm reaction cost yet.",

    # Adjudication Step 2: Confirm Reaction Cost
    "Confirm this uses their Reaction for this round. Verify they have a Reaction available (haven't used it this round). If valid, proceed. If not, inform them and ask for a different choice. DO NOT provide reaction window yet.",

    # Adjudication Step 3: Pre-Resolution Reaction Window (Recursive)
    "Provide pre-resolution reaction window: Ask if anyone ELSE wants to use a Reaction in response to this reaction before it resolves. Wait for response. If a reaction is declared, use start_and_queue_turns to create nested reaction turn(s). DO NOT resolve the reaction yet.",

    # Adjudication Step 4: Resolve Reaction
    "Resolve the declared reaction: Validate, call for necessary rolls, determine outcome, and narrate how the reaction affects the triggering action or its outcome. DO NOT check for status changes yet.",

    # Adjudication Step 5: Handle Critical Status Changes
    "Handle critical status changes from the reaction: Check if the reaction caused anyone to drop to 0 HP. Apply consequences immediately (unconscious/death). DO NOT provide reaction window yet.",

    # Adjudication Step 6: Post-Resolution Reaction Window (Recursive)
    "Provide post-resolution reaction window: Ask if anyone wants to use a Reaction in response to this reaction's outcome. Wait for response. If a reaction is declared, use start_and_queue_turns to create nested reaction turn(s)."
]

# Initial setup steps (before main combat loop)
DEMO_SETUP_STEPS = [
    "Greet the players and describe the initial combat scene. Set the stage for combat.",

    # "Call for initiative rolls from all participants. Wait for players to provide their initiative rolls. DO NOT proceed until all rolls are received.",

    # "Announce the complete initiative order from highest to lowest. Then announce whose turn is first and prompt them for their action."
]

# Resolution step indices - state extraction triggers after these steps
MAIN_ACTION_RESOLUTION_INDICES = {3}  # Index 3: "Resolve the declared action..."
REACTION_RESOLUTION_INDICES = {3}     # Index 3: "Resolve the declared reaction..."

def is_resolution_step_index(step_index: int, step_list: list[str]) -> bool:
    """
    Check if a step index is a resolution step that should trigger state extraction.

    Args:
        step_index: The current step index
        step_list: The step list being used (DEMO_MAIN_ACTION_STEPS or DEMO_REACTION_STEPS)

    Returns:
        True if this step index is a resolution step
    """
    if step_list is DEMO_MAIN_ACTION_STEPS:
        return step_index in MAIN_ACTION_RESOLUTION_INDICES
    elif step_list is DEMO_REACTION_STEPS:
        return step_index in REACTION_RESOLUTION_INDICES
    return False
