"""
Demo step objectives for mock Game Director.

Based on combat_flow.txt with three distinct phases:
- Phase 1: Combat Start (initiative collection, order finalization)
- Phase 2: Combat Rounds (main combat loop with turns)
- Phase 3: Combat End (conclusion and cleanup)

Plus exploration mode for non-combat interactions.

These objectives guide the DM through proper game flow without an actual GD agent.
"""

from enum import Enum


class GamePhase(str, Enum):
    """
    Game phases that determine which step list to use.

    Each phase has its own step progression appropriate for that context.
    """
    EXPLORATION = "exploration"
    """Free-form exploration and roleplay mode."""

    COMBAT_START = "combat_start"
    """Phase 1: Initiative collection and combat setup."""

    COMBAT_ROUNDS = "combat_rounds"
    """Phase 2: Main combat loop with turn-based actions."""

    COMBAT_END = "combat_end"
    """Phase 3: Combat conclusion and transition back to exploration."""

    REACTION = "reaction"
    """Sub-phase: Processing a declared reaction during combat."""


# =============================================================================
# EXPLORATION MODE STEPS
# =============================================================================
# Used for non-combat exploration, roleplay, and general interaction

EXPLORATION_STEPS = [
    # Step 1: Receive and Respond
    "Receive player input and respond appropriately as the Dungeon Master. Describe the environment, NPCs, or situation. Respond to player questions, actions, or roleplay. Maintain narrative flow and engagement. If players encounter danger or hostiles, you may transition to combat by describing the threat. Set awaiting_response with response_type='free_form' and characters=[all player character names] to allow any player to respond.",
]

# =============================================================================
# PHASE 1: COMBAT START
# =============================================================================
# Used when entering combat - describes encounter, collects initiative, establishes order

COMBAT_START_STEPS = [
    # Step 0: Select Monsters for Encounter
    "BEFORE describing the combat encounter: Call get_available_monsters() to see available monster templates, then call select_encounter_monsters() to spawn monsters that fit the narrative context and desired difficulty. Example: select_encounter_monsters([{type: 'goblin', count: 3}]). DO NOT describe the encounter until monsters are selected - you need their stat sheets for initiative and combat. Set awaiting_response with response_type='none' and game_step_completed=True after selecting monsters.",

    # Step 1: Announce Combat Initiation
    "Announce combat initiation. Describe the encounter using the monsters you selected, identify all hostile participants by the IDs returned (e.g., goblin_1, goblin_2), and set the stage for battle. Make the transition from exploration to combat dramatic and clear. The monsters are now in StateManager with full stat sheets. DO NOT call for initiative rolls in this step. Set awaiting_response with response_type='none' (you are narrating).",

    # Step 2: Determine Surprise and Initiative Modifiers
    "Determine surprise and initiative modifiers. Assess which sides were aware of each other before combat. Per 2024 PHB: Surprised creatures roll initiative with DISADVANTAGE (they do NOT skip their first turn). Determine if anyone gets advantage on initiative from initiating combat. Use query_character_ability to check monster DEX modifiers if needed. DO NOT call for rolls in this step - only determine modifiers. Set awaiting_response with response_type='none' (you are narrating).",

    # Step 3: Call for Initiative Rolls
    "Call for initiative rolls from ALL participants. Specify any advantage or disadvantage determined in the previous step (surprised = disadvantage). For monsters, roll their initiative (d20 + DEX modifier) and use add_monster_initiative() to register the rolls. DO NOT announce initiative order in this step. TWO SCENARIOS: (1) If you are ASKING for initiative rolls, first call add_monster_initiative() with monster rolls, then set game_step_completed=False and awaiting_response with response_type='initiative' and characters=[list of ALL player character IDs who need to roll]. (2) If you SEE 'Initiative Results' in the new messages showing all rolls have been collected, acknowledge receipt briefly and set game_step_completed=True to proceed to the next step.",

    # Step 4: Announce and Verify Initiative Order (reached only after initiative results are received)
    "You have received all initiative rolls. Announce the initial initiative order from highest to lowest. Provide a window for players to declare any abilities that modify initiative (e.g., Alert feat, class features). If contested, reference the exact rule text and adjust accordingly. DO NOT finalize the order in this step. Set awaiting_response with response_type='free_form' and characters=[all player character names] to allow objections.",

    # Step 5: Finalize Order and Begin Combat
    "Finalize the initiative order. Announce the final order clearly and state which participant acts first. DO NOT begin the first participant's turn in this step. Set game_step_completed=True to signal that combat setup is complete. Set awaiting_response with response_type='none' (you are concluding setup)."
]

# =============================================================================
# PHASE 2: COMBAT ROUNDS - Individual Turn Steps
# =============================================================================
# Used for each participant's turn during combat rounds
# Maps to Steps A-F from combat_flow.txt Phase 2

COMBAT_TURN_STEPS = [
    # Step 0: Announce Current Turn (Resolution step for turn-start effects)
    "Announce whose turn it is. Check for any effects that trigger at the start of this turn (ongoing damage, concentration checks, spell effects). If any turn-start effects apply, resolve them before requesting actions. DO NOT request actions in this step if there are turn-start effects to resolve.",

    # Step 1: Receive and Interpret Action
    "Receive and interpret the participant's declared action. Use action interpretation guidelines (Attack, Dash, Disengage, Dodge, Help, Hide, Influence, Magic, Ready, Search, Study, Utilize). VALIDATE character capability: check if character has the spell, ability, or equipment needed. If invalid, explain why and ask for a different action. If valid, confirm what action they are taking. DO NOT resolve the action in this step.",

    # Step 2: Pre-Resolution Reaction Window
    "Provide pre-resolution reaction window: Ask if any PLAYER wants to use a Reaction BEFORE the action resolves. Set awaiting_response with response_type='reaction' and characters=[all player character IDs]. For MONSTERS with reactions: Internally decide if each monster would use their reaction based on the trigger and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative). Wait for player response. If a reaction is declared, use start_and_queue_turns to create reaction turn(s). DO NOT resolve the main action in this step.",

    # Step 3: Resolve Action (Resolution step)
    "Resolve the declared action: Validate the action, call for necessary rolls (attack rolls, saving throws, ability checks), determine outcome based on the rolls, and narrate the result vividly. Apply damage and effects. DO NOT handle status changes or post-resolution reactions in this step.",

    # Step 4: Handle Critical Status Changes
    "Handle critical status changes: Check if anyone dropped to 0 HP (PCs fall unconscious, NPCs typically die). Apply consequences immediately. DO NOT provide post-resolution reaction window in this step.",

    # Step 5: Post-Resolution Reaction Window
    "Provide post-resolution reaction window: Ask if any PLAYER wants to use a Reaction in response to the outcome. Set awaiting_response with response_type='reaction' and characters=[all player character IDs]. For MONSTERS with reactions: Internally decide if each monster would use their reaction based on the outcome and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative). Wait for player response. If a reaction is declared, use start_and_queue_turns to create reaction turn(s). DO NOT ask about additional actions in this step.",

    # Step 6: Confirm End of Turn
    "Ask the active participant: 'Would you like to do anything else on your turn?' Options include: bonus action, movement, free object interaction, or additional actions from features. If they declare another action, resolve it immediately within this step (interpret, validate, resolve, narrate). If they have nothing more to do, set game_step_completed=True to proceed. DO NOT check for turn-end effects in this step.",

    # Step 7: Turn-End Effects (Resolution step for turn-end effects)
    "Check for turn-end effects: Apply effects that trigger at the end of this turn (saving throws against conditions, concentration checks, Legendary Actions if facing a legendary creature). Resolve any triggered effects. DO NOT announce the next turn in this step.",

    # Step 8: Announce Next Turn
    "Announce the end of current participant's turn. State which participant is next in initiative order and prompt them for their intended action. If this was the last turn in the round, also announce the start of the new round. DO NOT begin processing the next participant's actions in this step."
]

# Legacy alias for backward compatibility
DEMO_MAIN_ACTION_STEPS = COMBAT_TURN_STEPS

# =============================================================================
# PHASE 2: COMBAT ROUNDS - Monster Turn Steps
# =============================================================================
# Used for monster/NPC turns during combat rounds
# DM decides and executes monster actions internally

MONSTER_TURN_STEPS = [
    # Step 0: Announce Turn + Turn-Start Effects (Resolution step for turn-start effects)
    "Announce it is the monster's turn. Check for any effects that trigger at the start of this turn (ongoing damage, concentration checks, spell effects). Resolve turn-start effects before deciding actions. DO NOT decide monster action in this step.",

    # Step 1: Decide and Declare Action
    "Based on the monster's statblock, decide what action the monster takes. Consider: available actions, current HP, tactical situation, targets in range. Declare the monster's intended action clearly in the narrative. DO NOT resolve the action yet.",

    # Step 2: Pre-Resolution Reaction Window
    "Provide pre-resolution reaction window: Ask if any PLAYER wants to use a Reaction BEFORE the monster's action resolves. Set awaiting_response with response_type='reaction' and characters=[all player character IDs]. For OTHER MONSTERS with reactions (not the active monster): Internally decide if each would use their reaction based on the trigger and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative). Wait for player responses. If any reactions are declared, use start_and_queue_turns to create reaction turn(s). DO NOT resolve the monster's action in this step.",

    # Step 3: Resolve Monster Action (Resolution step)
    "Resolve the monster's declared action: Make attack rolls, call for saving throws from players if needed, determine outcome, apply damage and effects. Narrate the result vividly. DO NOT handle status changes or post-resolution reactions in this step.",

    # Step 4: Handle Critical Status Changes
    "Handle critical status changes: Check if anyone dropped to 0 HP (PCs fall unconscious, NPCs typically die). Apply consequences immediately. DO NOT provide post-resolution reaction window in this step.",

    # Step 5: Post-Resolution Reaction Window
    "Provide post-resolution reaction window: Ask if any PLAYER wants to use a Reaction in response to the outcome. Set awaiting_response with response_type='reaction' and characters=[all player character IDs]. For OTHER MONSTERS with reactions (not the active monster): Internally decide if each would use their reaction based on the outcome and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative). Wait for player responses. If any reactions are declared, use start_and_queue_turns to create reaction turn(s). DO NOT ask about additional actions in this step.",

    # Step 6: Additional Actions (Bonus Action, Movement)
    "Decide if the monster uses a bonus action, additional movement, or free object interaction based on its statblock and the tactical situation. Resolve any additional actions. Set awaiting_response with response_type='none'.",

    # Step 7: Turn-End Effects (Resolution step for turn-end effects)
    "Check for turn-end effects: Apply effects that trigger at the end of this turn (saving throws against conditions, concentration checks). Resolve any triggered effects. DO NOT announce the next turn in this step.",

    # Step 8: Announce Next Turn
    "Announce the end of the monster's turn. State which participant is next in initiative order. If this was the last turn in the round, also announce the start of the new round. DO NOT begin processing the next participant's actions in this step."
]

# Legacy alias for backward compatibility
ENEMY_TURN_STEPS = MONSTER_TURN_STEPS

# =============================================================================
# PHASE 2: REACTION STEPS (Adjudication Sub-Routine)
# =============================================================================
# Used when reactions are declared during pre-resolution or post-resolution windows
# This is a recursive routine - reactions can trigger other reactions

DEMO_REACTION_STEPS = [
    # Adjudication Step 0: Receive and Interpret
    "Receive and interpret the declared reaction. VALIDATE character capability: check if character has this reaction ability based on their character sheet (class features, spells like Shield or Counterspell, opportunity attacks, etc.). If invalid, explain why and ask for a different choice. If valid, confirm what reaction they are using, its trigger, and verify it's valid for the current situation. DO NOT confirm reaction cost in this step.",

    # Adjudication Step 1: Confirm Reaction Cost
    "Confirm this uses their Reaction for this round. Verify they have a Reaction available (haven't used it this round). If valid, mark their reaction as used. If not, inform them and ask for a different choice. DO NOT check for nested reactions in this step.",

    # Adjudication Step 2: Pre-Resolution Reaction Window (Recursive)
    "Provide pre-resolution reaction window: Ask if any PLAYER wants to use a Reaction in response to this reaction before it resolves. Set awaiting_response with response_type='reaction' and characters=[all player character IDs]. For OTHER MONSTERS with reactions (not the reacting character if it's a monster): Internally decide if each would use their reaction based on the trigger and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative). Wait for player responses. If any reactions are declared, use start_and_queue_turns to create nested reaction turn(s). DO NOT resolve this reaction in this step.",

    # Adjudication Step 3: Resolve Reaction (Resolution step)
    "Resolve the declared reaction: Validate, call for necessary rolls, determine outcome, and narrate how the reaction affects the triggering action or its outcome. DO NOT handle status changes in this step.",

    # Adjudication Step 4: Handle Critical Status Changes
    "Handle critical status changes from the reaction: Check if the reaction caused anyone to drop to 0 HP. Apply consequences immediately (unconscious for PCs, death for most NPCs). DO NOT provide post-resolution reaction window in this step.",

    # Adjudication Step 5: Post-Resolution Reaction Window (Recursive)
    "Provide post-resolution reaction window: Ask if any PLAYER wants to use a Reaction in response to this reaction's outcome. Set awaiting_response with response_type='reaction' and characters=[all player character IDs]. For OTHER MONSTERS with reactions (not the reacting character if it's a monster): Internally decide if each would use their reaction based on the outcome and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative). Wait for player responses. If any reactions are declared, use start_and_queue_turns to create nested reaction turn(s)."
]

# =============================================================================
# PHASE 3: COMBAT END
# =============================================================================
# Used when combat concludes

COMBAT_END_STEPS = [
    # Step 0: Determine Conclusion
    "Determine if combat conclusion conditions are met: One side is entirely neutralized (incapacitated, killed, or fled), OR a pre-determined objective has been achieved, OR both sides agree to cease hostilities. DO NOT announce combat has ended in this step.",

    # Step 1: Announce End
    "Formally announce that the structured combat encounter has concluded. Make the transition clear and dramatic. DO NOT summarize the outcome in this step.",

    # Step 2: Summarize Outcome
    "Provide a concise summary of the combat outcome: Who won/lost, casualties on both sides, any significant events that occurred, and the immediate aftermath. DO NOT report lasting effects in this step.",

    # Step 3: Report Lasting Effects
    "Identify and announce any ongoing effects that will persist beyond combat: Lingering spell effects with remaining duration, conditions that don't end with combat (exhaustion, curses), concentration spells still maintained, and any time-sensitive effects. DO NOT clean up effects in this step.",

    # Step 4: Clean Up Combat-Only Effects (RESOLUTION STEP - triggers state extraction)
    "Remove all combat-only effects that end when combat concludes: End Barbarian Rage, drop concentration spells no longer needed, clear 'until end of combat' conditions (like temporary frightened or charmed effects), and remove any combat-specific buffs. Announce what effects are ending. State extraction will capture these changes."
]

# =============================================================================
# RESOLUTION STEP INDICES
# =============================================================================
# State extraction triggers after these steps (where game state changes occur)

# For combat turns: Resolution happens at multiple steps
# - Index 0: Turn-start effects (ongoing damage, spell effects, concentration)
# - Index 3: Main action resolution (attacks, spells, abilities)
# - Index 7: Turn-end effects (saving throws, Legendary Actions)
COMBAT_TURN_RESOLUTION_INDICES = {0, 3, 7}
MAIN_ACTION_RESOLUTION_INDICES = COMBAT_TURN_RESOLUTION_INDICES  # Legacy alias

# For monster turns: Same resolution indices as player turns
# - Index 0: Turn-start effects
# - Index 3: Monster action resolution
# - Index 7: Turn-end effects
MONSTER_TURN_RESOLUTION_INDICES = {0, 3, 7}
ENEMY_TURN_RESOLUTION_INDICES = MONSTER_TURN_RESOLUTION_INDICES  # Legacy alias

# For reactions: Resolution happens at step index 3 (Resolve Reaction)
REACTION_RESOLUTION_INDICES = {3}

# Combat start doesn't have resolution steps (no game state changes)
COMBAT_START_RESOLUTION_INDICES = set()

# Combat end: Resolution happens at step index 4 (Clean Up Combat-Only Effects)
# - Index 4: Remove combat-only effects (rage, concentration, temporary conditions)
COMBAT_END_RESOLUTION_INDICES = {4}


def is_resolution_step_index(step_index: int, step_list: list[str]) -> bool:
    """
    Check if a step index is a resolution step that should trigger state extraction.

    Args:
        step_index: The current step index
        step_list: The step list being used

    Returns:
        True if this step index is a resolution step
    """
    if step_list is COMBAT_TURN_STEPS or step_list is DEMO_MAIN_ACTION_STEPS:
        return step_index in COMBAT_TURN_RESOLUTION_INDICES
    elif step_list is MONSTER_TURN_STEPS:
        return step_index in MONSTER_TURN_RESOLUTION_INDICES
    elif step_list is DEMO_REACTION_STEPS:
        return step_index in REACTION_RESOLUTION_INDICES
    elif step_list is COMBAT_START_STEPS:
        return step_index in COMBAT_START_RESOLUTION_INDICES
    elif step_list is COMBAT_END_STEPS:
        return step_index in COMBAT_END_RESOLUTION_INDICES
    elif step_list is EXPLORATION_STEPS:
        return step_index in EXPLORATION_RESOLUTION_INDICES
    return False


def get_step_list_name(step_list: list[str]) -> str:
    """Get a human-readable name for a step list."""
    if step_list is EXPLORATION_STEPS:
        return "Exploration"
    elif step_list is COMBAT_START_STEPS:
        return "Combat Start"
    elif step_list is COMBAT_TURN_STEPS or step_list is DEMO_MAIN_ACTION_STEPS:
        return "Combat Turn"
    elif step_list is MONSTER_TURN_STEPS:
        return "Monster Turn"
    elif step_list is DEMO_REACTION_STEPS:
        return "Reaction"
    elif step_list is COMBAT_END_STEPS:
        return "Combat End"
    return "Unknown"


# Legacy alias for backward compatibility
DEMO_SETUP_STEPS = COMBAT_START_STEPS[:2]  # Just the intro steps

# Exploration doesn't have resolution steps (no game state changes from DM narration)
EXPLORATION_RESOLUTION_INDICES = set()


def get_steps_for_phase(phase: GamePhase) -> list[str]:
    """
    Get the appropriate step list for a game phase.

    Args:
        phase: The current game phase

    Returns:
        The step list appropriate for that phase
    """
    if phase == GamePhase.EXPLORATION:
        return EXPLORATION_STEPS
    elif phase == GamePhase.COMBAT_START:
        return COMBAT_START_STEPS
    elif phase == GamePhase.COMBAT_ROUNDS:
        return COMBAT_TURN_STEPS
    elif phase == GamePhase.COMBAT_END:
        return COMBAT_END_STEPS
    elif phase == GamePhase.REACTION:
        return DEMO_REACTION_STEPS
    else:
        return EXPLORATION_STEPS  # Default to exploration
