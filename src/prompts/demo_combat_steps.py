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
    # Step 0: Select Monsters and Announce Combat Initiation
    "First, call get_available_monsters() to see available monster templates, then call select_encounter_monsters() to spawn monsters that fit the narrative context and desired difficulty. Example: select_encounter_monsters([{type: 'goblin', count: 2}]).\n"
    "IMMEDIATELY AFTER selecting monsters, announce combat initiation. CRITICAL REQUIREMENTS:\n"
    "1. You MUST describe ALL the monsters returned by select_encounter_monsters() - not just some of them.\n"
    "2. If the tool returned 2 goblins (goblin_1, goblin_2), your narrative MUST mention BOTH goblins. Count the monsters and ensure your description matches the exact count.\n"
    "3. DO NOT say 'a lone goblin' if you spawned 2 goblins. DO NOT invent different monster types.\n"
    "4. Make the transition from exploration to combat dramatic and clear.\n"
    "DO NOT call for initiative rolls in this step. Call complete_step() after processing - the tool will tell you whether to continue or return.",

    # Step 1: Determine Surprise and Initiative Modifiers
    "Determine surprise and initiative modifiers. Assess which sides were aware of each other before combat. Per 2024 PHB: Surprised creatures roll initiative with DISADVANTAGE (they do NOT skip their first turn). Determine if anyone gets advantage on initiative from initiating combat. Use query_character_ability with the EXACT monster IDs from select_encounter_monsters() (e.g., goblin_1 NOT bugbear_1). DO NOT call for rolls in this step - only determine modifiers. Call complete_step() after processing - the tool will tell you whether to continue or return.",

    # Step 2: Call for Initiative Rolls
    "Call for initiative rolls from ALL participants. CRITICAL REQUIREMENTS:\n"
    "1. You MUST roll initiative for EVERY monster spawned by select_encounter_monsters(). If you spawned 2 goblins (goblin_1, goblin_2), BOTH must have initiative rolls.\n"
    "2. Use the EXACT monster IDs returned by select_encounter_monsters() (e.g., goblin_1, goblin_2, NOT bugbear_1 or other made-up IDs).\n"
    "3. IMPORTANT: Use roll_dice() tool FIRST to get actual random rolls for monsters. Example: roll_dice([{character_id: 'goblin_1', die_type: 20, modifier: 2, label: 'initiative'}, {character_id: 'goblin_2', die_type: 20, modifier: 2, label: 'initiative'}]). DO NOT make up roll values.\n"
    "4. THEN call add_monster_initiative() with the actual roll results from roll_dice().\n"
    "5. After calling add_monster_initiative(), CHECK THE RESPONSE for any '🚨 ACTION REQUIRED' warnings - if monsters are missing, call add_monster_initiative() again for the missing ones.\n"
    "6. Combat CANNOT proceed until ALL monsters have initiative registered.\n"
    "7. CRITICAL: DO NOT announce the monster initiative roll results to players. Keep monster rolls secret - only use them internally for add_monster_initiative(). Players should only see their own initiative prompts, not what the monsters rolled.\n"
    "DO NOT announce initiative order in this step.\n"
    "TWO SCENARIOS: (1) If you are ASKING for initiative rolls, first use roll_dice() to roll for ALL monsters, then call add_monster_initiative() with those actual roll values (without announcing monster rolls to players), then set DO NOT call complete_step() yet and awaiting_response with response_type='initiative' and characters=[list of ALL player character IDs who need to roll]. (2) If you SEE 'Initiative Results' in the new messages showing all rolls have been collected, acknowledge receipt briefly and set call complete_step() to proceed to the next step.",

    # Step 3: Announce and Verify Initiative Order (reached only after initiative results are received)
    "You have received all initiative rolls. IMPORTANT: Refer to the <combat_state><initiative_order> section in your context for the ACTUAL initiative order stored by the system. DO NOT reconstruct the order from memory - use the EXACT order shown in the context.\n"
    "Announce the initiative order EXACTLY as shown in <initiative_order>, from highest to lowest. Provide a window for players to declare any abilities that modify initiative (e.g., Alert feat, class features). If contested, reference the exact rule text and adjust accordingly. DO NOT finalize the order in this step. Set awaiting_response with response_type='free_form' and characters=[all player character names] to allow objections.",

    # Step 4: Finalize Order and Begin Combat
    "Finalize the initiative order. Announce the final order clearly and state which participant acts first. DO NOT begin the first participant's turn in this step. Call complete_step() to signal that combat setup is complete - the turn will transition automatically."
]

# =============================================================================
# PHASE 2: COMBAT ROUNDS - Individual Turn Steps
# =============================================================================
# Used for each participant's turn during combat rounds
# Maps to Steps A-F from combat_flow.txt Phase 2

COMBAT_TURN_STEPS = [
    # Step 0: Announce Current Turn (Resolution step for turn-start effects)
    "Check the <combat_state><current_turn> element in your context to confirm whose turn it is according to the system. Announce that character's turn. Check for any effects that trigger at the start of this turn (ongoing damage, concentration checks, spell effects). If any turn-start effects apply, resolve them before requesting actions. DO NOT request actions in this step if there are turn-start effects to resolve.",

    # Step 1: Receive and Interpret Action
    "Receive and interpret the participant's declared action. Use action interpretation guidelines (Attack, Dash, Disengage, Dodge, Help, Hide, Influence, Magic, Ready, Search, Study, Utilize). VALIDATE character capability: check if character has the spell, ability, or equipment needed. If invalid, explain why and ask for a different action. If valid, confirm what action they are taking. DO NOT resolve the action in this step.",

    # Step 2: Pre-Resolution Reaction Window
    "Provide pre-resolution reaction window.\n"
    "TWO SCENARIOS:\n"
    "(1) If you are ASKING for reactions: Ask if any PLAYER wants to use a Reaction BEFORE the action resolves. Set DO NOT call complete_step() yet and awaiting_response with response_type='reaction' and characters=[all player character IDs]. For MONSTERS with reactions: Internally decide if each monster would use their reaction based on the trigger and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative).\n"
    "(2) If you SEE 'Reaction Window Results' in the new messages: The reaction window has completed. If any reactions were declared, use start_and_queue_turns to create reaction turn(s). Then set call complete_step() to proceed to the next step.\n"
    "DO NOT resolve the main action in this step.",

    # Step 3: Resolve Action (Resolution step)
    "Resolve the declared action: ASK THE PLAYER to make their roll (attack, damage, save, or check). CRITICAL: DO NOT use roll_dice() for player characters - this includes attack rolls AND damage rolls. Only monsters/NPCs roll with roll_dice(). Wait for the player to provide each result. Once you have ALL results needed, determine outcome and narrate it vividly. Apply damage and effects. DO NOT handle status changes or post-resolution reactions in this step.\n"
    "TWO SCENARIOS:\n"
    "(1) If you need a roll from the player (attack, damage, save, check): Set DO NOT call complete_step() yet and awaiting_response with response_type='action' asking for their roll.\n"
    "(2) If you SEE the roll result in new messages: Resolve the action, apply effects, call complete_step() to proceed.",

    # Step 4: Handle Critical Status Changes
    "Handle critical status changes: Check if anyone dropped to 0 HP (PCs fall unconscious, NPCs typically die). Apply consequences immediately. DO NOT provide post-resolution reaction window in this step.",

    # Step 5: Post-Resolution Reaction Window
    "Provide post-resolution reaction window.\n"
    "TWO SCENARIOS:\n"
    "(1) If you are ASKING for reactions: Ask if any PLAYER wants to use a Reaction in response to the outcome. Set DO NOT call complete_step() yet and awaiting_response with response_type='reaction' and characters=[all player character IDs]. For MONSTERS with reactions: Internally decide if each monster would use their reaction based on the outcome and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative).\n"
    "(2) If you SEE 'Reaction Window Results' in the new messages: The reaction window has completed. If any reactions were declared, use start_and_queue_turns to create reaction turn(s). Then set call complete_step() to proceed to the next step.\n"
    "DO NOT ask about additional actions in this step.",

    # Step 6: Confirm End of Turn
    "Ask the active participant: 'Would you like to do anything else on your turn?' Options include: bonus action, movement, free object interaction, or additional actions from features. If they declare another action, resolve it immediately within this step (interpret, validate, resolve, narrate). If they have nothing more to do, set call complete_step() to proceed. DO NOT check for turn-end effects in this step.",

    # Step 7: Turn-End Effects (Resolution step for turn-end effects)
    "Check for turn-end effects: Apply effects that trigger at the end of this turn (saving throws against conditions, concentration checks, Legendary Actions if facing a legendary creature). Resolve any triggered effects. DO NOT announce the next turn in this step.",

    # Step 8: Announce Next Turn
    "Announce the end of current participant's turn. Check the <combat_state><initiative_order> in your context to confirm who is next according to the system, then briefly state which participant is next in initiative order. CRITICAL RESTRICTIONS:\n"
    "1. DO NOT begin processing the next participant's actions, attacks, or decisions - only announce who is next.\n"
    "2. DO NOT narrate the next participant attacking, moving, or taking any action - the system will handle their turn separately.\n"
    "3. DO NOT use start_and_queue_turns() - the system automatically handles turn transitions.\n"
    "4. If this was the last turn in the round, also announce the start of the new round.\n"
    "Call complete_step() to signal the turn is complete - the system will automatically transition to the next turn and run it."
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
    "Check the <combat_state><current_turn> element in your context to confirm it is the monster's turn according to the system. Announce it is the monster's turn. Check for any effects that trigger at the start of this turn (ongoing damage, concentration checks, spell effects). Resolve turn-start effects before deciding actions. DO NOT decide monster action in this step.",

    # Step 1: Decide and Declare Action
    "Based on the monster's statblock, decide what action the monster takes. Consider: available actions, current HP, tactical situation, targets in range. Declare the monster's intended action clearly in the narrative. DO NOT resolve the action yet.",

    # Step 2: Pre-Resolution Reaction Window
    "Provide pre-resolution reaction window.\n"
    "TWO SCENARIOS:\n"
    "(1) If you are ASKING for reactions: Ask if any PLAYER wants to use a Reaction BEFORE the monster's action resolves. Set DO NOT call complete_step() yet and awaiting_response with response_type='reaction' and characters=[all player character IDs]. For OTHER MONSTERS with reactions (not the active monster): Internally decide if each would use their reaction based on the trigger and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative).\n"
    "(2) If you SEE 'Reaction Window Results' in the new messages: The reaction window has completed. If any reactions were declared, use start_and_queue_turns to create reaction turn(s). Then set call complete_step() to proceed to the next step.\n"
    "DO NOT resolve the monster's action in this step.",

    # Step 3: Resolve Monster Action (Resolution step)
    "Resolve the monster's declared action: Make attack rolls, call for saving throws from players if needed, determine outcome, apply damage and effects. Narrate the result vividly. DO NOT handle status changes or post-resolution reactions in this step.",

    # Step 4: Handle Critical Status Changes
    "Handle critical status changes: Check if anyone dropped to 0 HP (PCs fall unconscious, NPCs typically die). Apply consequences immediately. DO NOT provide post-resolution reaction window in this step.",

    # Step 5: Post-Resolution Reaction Window
    "Provide post-resolution reaction window.\n"
    "TWO SCENARIOS:\n"
    "(1) If you are ASKING for reactions: Ask if any PLAYER wants to use a Reaction in response to the outcome. Set DO NOT call complete_step() yet and awaiting_response with response_type='reaction' and characters=[all player character IDs]. For OTHER MONSTERS with reactions (not the active monster): Internally decide if each would use their reaction based on the outcome and record decisions in the monster_reactions field (hidden from players - DO NOT announce monster intent in narrative).\n"
    "(2) If you SEE 'Reaction Window Results' in the new messages: The reaction window has completed. If any reactions were declared, use start_and_queue_turns to create reaction turn(s). Then set call complete_step() to proceed to the next step.\n"
    "DO NOT ask about additional actions in this step.",

    # Step 6: Additional Actions (Bonus Action, Movement)
    "Decide if the monster uses a bonus action, additional movement, or free object interaction based on its statblock and the tactical situation. Resolve any additional actions. Call complete_step() after processing - the tool will tell you whether to continue or return.",

    # Step 7: Turn-End Effects (Resolution step for turn-end effects)
    "Check for turn-end effects: Apply effects that trigger at the end of this turn (saving throws against conditions, concentration checks). Resolve any triggered effects. DO NOT announce the next turn in this step.",

    # Step 8: Announce Next Turn
    "Announce the end of the monster's turn. Check the <combat_state><initiative_order> in your context to confirm who is next according to the system, then briefly state which participant is next in initiative order. CRITICAL RESTRICTIONS:\n"
    "1. DO NOT begin processing the next participant's actions, attacks, or decisions - only announce who is next.\n"
    "2. DO NOT narrate the next participant attacking, moving, or taking any action - the system will handle their turn separately.\n"
    "3. DO NOT use start_and_queue_turns() - the system automatically handles turn transitions.\n"
    "4. If this was the last turn in the round, also announce the start of the new round.\n"
    "Call complete_step() to signal the turn is complete - the system will automatically transition to the next turn and run it."
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
