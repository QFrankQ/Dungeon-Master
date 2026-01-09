"""
Comprehensive tests for combat phase, turn, and round transitions.

Covers the complete combat lifecycle:
- Phase transitions (NOT_IN_COMBAT → COMBAT_START → COMBAT_ROUNDS → COMBAT_END)
- Initiative queuing (players and monsters)
- Turn transitions (step progression, subturn creation)
- Round transitions (all participants complete → new round)
- Combat end conditions
"""

import pytest
import asyncio
from typing import List

from src.memory.turn_manager import TurnManager, ActionDeclaration
from src.models.combat_state import CombatState, CombatPhase, InitiativeEntry, create_combat_state
from src.models.turn_context import TurnContext
from src.prompts.demo_combat_steps import (
    COMBAT_START_STEPS,
    COMBAT_TURN_STEPS,
    MONSTER_TURN_STEPS,
    DEMO_REACTION_STEPS,
    COMBAT_END_STEPS,
    EXPLORATION_STEPS,
    COMBAT_TURN_RESOLUTION_INDICES,
    MONSTER_TURN_RESOLUTION_INDICES,
    REACTION_RESOLUTION_INDICES,
    is_resolution_step_index,
    GamePhase,
)
from src.models.dm_response import MonsterReactionDecision


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def turn_manager():
    """Create TurnManager without condensation agent (mock-friendly)."""
    return TurnManager(turn_condensation_agent=None)


@pytest.fixture
def combat_state():
    """Create standalone CombatState for unit tests."""
    return create_combat_state()


@pytest.fixture
def sample_initiative_entries():
    """Create sample initiative entries for players and monsters."""
    return [
        InitiativeEntry(
            character_id="fighter",
            character_name="Tharion",
            roll=18,
            is_player=True,
            dex_modifier=2
        ),
        InitiativeEntry(
            character_id="wizard",
            character_name="Elara",
            roll=15,
            is_player=True,
            dex_modifier=3
        ),
        InitiativeEntry(
            character_id="goblin_1",
            character_name="Goblin Archer",
            roll=14,
            is_player=False,
            dex_modifier=2
        ),
        InitiativeEntry(
            character_id="goblin_2",
            character_name="Goblin Shaman",
            roll=12,
            is_player=False,
            dex_modifier=1
        ),
    ]


@pytest.fixture
def turn_manager_in_combat(turn_manager, sample_initiative_entries):
    """Create a TurnManager already in COMBAT_ROUNDS phase with 4 participants."""
    # Enter combat
    participants = ["fighter", "wizard", "goblin_1", "goblin_2"]
    turn_manager.enter_combat(participants, "Test Encounter")

    # Add initiative rolls
    for entry in sample_initiative_entries:
        turn_manager.add_initiative_roll(
            character_id=entry.character_id,
            character_name=entry.character_name,
            roll=entry.roll,
            is_player=entry.is_player,
            dex_modifier=entry.dex_modifier
        )

    # End the combat start turn - this automatically calls finalize_initiative()
    # and transitions to COMBAT_ROUNDS
    turn_manager.end_turn_sync()

    return turn_manager


# =============================================================================
# TestCombatPhaseTransitions
# =============================================================================

class TestCombatPhaseTransitions:
    """Test transitions between combat phases."""

    def test_enter_combat_from_exploration(self, turn_manager):
        """Verify phase transitions to COMBAT_START with correct setup."""
        # Initially not in combat
        assert turn_manager.combat_state.phase == CombatPhase.NOT_IN_COMBAT

        # Enter combat
        participants = ["fighter", "wizard", "goblin_1"]
        result = turn_manager.enter_combat(participants, "Goblin Ambush")

        # Verify phase transition
        assert turn_manager.combat_state.phase == CombatPhase.COMBAT_START
        assert result["phase"] == "combat_start"

        # Verify participants stored
        assert turn_manager.combat_state.participants == participants

        # Verify turn created with COMBAT_START_STEPS
        current_turn = turn_manager.get_next_pending_turn()
        assert current_turn is not None
        assert current_turn.game_step_list == COMBAT_START_STEPS
        assert current_turn.active_character == "SYSTEM"

    def test_finalize_initiative_transitions_to_combat_rounds(self, turn_manager, sample_initiative_entries):
        """Verify initiative finalization transitions to COMBAT_ROUNDS."""
        # Setup combat start phase
        participants = ["fighter", "wizard", "goblin_1", "goblin_2"]
        turn_manager.enter_combat(participants, "Test Encounter")

        # Add initiative rolls
        for entry in sample_initiative_entries:
            turn_manager.add_initiative_roll(
                character_id=entry.character_id,
                character_name=entry.character_name,
                roll=entry.roll,
                is_player=entry.is_player,
                dex_modifier=entry.dex_modifier
            )

        # Finalize initiative (this also ends the combat start turn)
        result = turn_manager.finalize_initiative(combat_start_turn_already_ended=False)

        # Verify phase transition
        assert turn_manager.combat_state.phase == CombatPhase.COMBAT_ROUNDS
        assert turn_manager.combat_state.round_number == 1

        # Verify initiative order sorted correctly (highest roll first)
        order = turn_manager.combat_state.initiative_order
        assert len(order) == 4
        assert order[0].character_id == "fighter"  # Roll 18
        assert order[1].character_id == "wizard"   # Roll 15
        assert order[2].character_id == "goblin_1" # Roll 14
        assert order[3].character_id == "goblin_2" # Roll 12

    def test_start_combat_end_transitions_phase(self, turn_manager_in_combat):
        """Verify combat end transition from COMBAT_ROUNDS."""
        tm = turn_manager_in_combat

        # Verify we're in combat rounds
        assert tm.combat_state.phase == CombatPhase.COMBAT_ROUNDS

        # Start combat end
        tm.combat_state.start_combat_end()

        # Verify phase transition
        assert tm.combat_state.phase == CombatPhase.COMBAT_END

    def test_finish_combat_returns_to_exploration(self, turn_manager_in_combat):
        """Verify finish_combat resets to NOT_IN_COMBAT."""
        tm = turn_manager_in_combat

        # Transition through combat end
        tm.combat_state.start_combat_end()
        tm.combat_state.finish_combat()

        # Verify complete reset
        assert tm.combat_state.phase == CombatPhase.NOT_IN_COMBAT
        assert tm.combat_state.round_number == 0
        assert tm.combat_state.initiative_order == []
        assert tm.combat_state.participants == []
        assert tm.combat_state.current_participant_index == 0
        assert tm.combat_state.encounter_name is None

    def test_invalid_phase_transitions_raise_errors(self, combat_state, sample_initiative_entries):
        """Verify invalid phase transitions raise ValueError."""
        # Cannot add initiative when not in COMBAT_START
        with pytest.raises(ValueError, match="Cannot add initiative"):
            combat_state.add_initiative_roll(sample_initiative_entries[0])

        # Start combat and finalize
        combat_state.start_combat(["fighter", "wizard"], "Test")
        combat_state.add_initiative_roll(sample_initiative_entries[0])
        combat_state.add_initiative_roll(sample_initiative_entries[1])
        combat_state.finalize_initiative()

        # Cannot add initiative in COMBAT_ROUNDS
        with pytest.raises(ValueError, match="Cannot add initiative"):
            combat_state.add_initiative_roll(sample_initiative_entries[2])

        # Cannot finalize initiative in COMBAT_ROUNDS
        with pytest.raises(ValueError, match="Cannot finalize initiative"):
            combat_state.finalize_initiative()

        # Cannot start combat end from COMBAT_START
        combat_state2 = create_combat_state()
        combat_state2.start_combat(["fighter"], "Test")
        with pytest.raises(ValueError, match="Cannot end combat"):
            combat_state2.start_combat_end()


# =============================================================================
# TestInitiativeQueueing
# =============================================================================

class TestInitiativeQueueing:
    """Test that all characters are correctly queued after initiative finalization."""

    def test_all_participants_queued_after_finalize(self, turn_manager_in_combat):
        """Verify all 4 participants (2 players + 2 monsters) are queued."""
        tm = turn_manager_in_combat

        # Get Level 0 queue
        assert len(tm.turn_stack) >= 1
        level_0_queue = tm.turn_stack[0]

        # Should have 4 turns (one for each participant)
        assert len(level_0_queue) == 4

        # Verify order matches initiative (fighter → wizard → goblin_1 → goblin_2)
        assert level_0_queue[0].active_character == "fighter"
        assert level_0_queue[1].active_character == "wizard"
        assert level_0_queue[2].active_character == "goblin_1"
        assert level_0_queue[3].active_character == "goblin_2"

    def test_players_get_combat_turn_steps(self, turn_manager_in_combat):
        """Verify player turns use COMBAT_TURN_STEPS (9 steps)."""
        tm = turn_manager_in_combat
        level_0_queue = tm.turn_stack[0]

        # Fighter (player) should have COMBAT_TURN_STEPS
        fighter_turn = level_0_queue[0]
        assert fighter_turn.active_character == "fighter"
        assert fighter_turn.game_step_list == COMBAT_TURN_STEPS
        assert len(fighter_turn.game_step_list) == 9

        # Wizard (player) should have COMBAT_TURN_STEPS
        wizard_turn = level_0_queue[1]
        assert wizard_turn.active_character == "wizard"
        assert wizard_turn.game_step_list == COMBAT_TURN_STEPS
        assert len(wizard_turn.game_step_list) == 9

    def test_monsters_get_monster_turn_steps(self, turn_manager_in_combat):
        """Verify monster turns use MONSTER_TURN_STEPS (9 steps)."""
        tm = turn_manager_in_combat
        level_0_queue = tm.turn_stack[0]

        # Goblin 1 (monster) should have MONSTER_TURN_STEPS
        goblin1_turn = level_0_queue[2]
        assert goblin1_turn.active_character == "goblin_1"
        assert goblin1_turn.game_step_list == MONSTER_TURN_STEPS
        assert len(goblin1_turn.game_step_list) == 9

        # Goblin 2 (monster) should have MONSTER_TURN_STEPS
        goblin2_turn = level_0_queue[3]
        assert goblin2_turn.active_character == "goblin_2"
        assert goblin2_turn.game_step_list == MONSTER_TURN_STEPS
        assert len(goblin2_turn.game_step_list) == 9

    def test_initiative_order_highest_first(self, turn_manager):
        """Verify initiative order is sorted highest roll first."""
        # Setup with specific rolls
        participants = ["low_roller", "high_roller", "mid_roller"]
        turn_manager.enter_combat(participants, "Test")

        turn_manager.add_initiative_roll("low_roller", "Low Roller", roll=5, is_player=True)
        turn_manager.add_initiative_roll("high_roller", "High Roller", roll=20, is_player=True)
        turn_manager.add_initiative_roll("mid_roller", "Mid Roller", roll=12, is_player=True)

        # Finalize initiative (ends combat start turn automatically)
        turn_manager.finalize_initiative(combat_start_turn_already_ended=False)

        # Verify order
        order = turn_manager.combat_state.initiative_order
        assert order[0].character_id == "high_roller"  # 20
        assert order[1].character_id == "mid_roller"   # 12
        assert order[2].character_id == "low_roller"   # 5

    def test_tie_breaking_by_dex_modifier(self, turn_manager):
        """Verify dexterity modifier breaks ties."""
        participants = ["char_a", "char_b"]
        turn_manager.enter_combat(participants, "Test")

        # Same roll, different dex modifiers
        turn_manager.add_initiative_roll("char_a", "Char A", roll=15, is_player=True, dex_modifier=1)
        turn_manager.add_initiative_roll("char_b", "Char B", roll=15, is_player=True, dex_modifier=3)

        # Finalize initiative (ends combat start turn automatically)
        turn_manager.finalize_initiative(combat_start_turn_already_ended=False)

        # Higher dex goes first
        order = turn_manager.combat_state.initiative_order
        assert order[0].character_id == "char_b"  # Higher dex
        assert order[1].character_id == "char_a"

    def test_active_character_set_correctly(self, turn_manager_in_combat):
        """Verify each queued turn has correct active_character (character_id)."""
        tm = turn_manager_in_combat
        level_0_queue = tm.turn_stack[0]

        expected_characters = ["fighter", "wizard", "goblin_1", "goblin_2"]
        for i, turn in enumerate(level_0_queue):
            assert turn.active_character == expected_characters[i]


# =============================================================================
# TestTurnTransitions
# =============================================================================

class TestTurnTransitions:
    """Test transitions between turns when step list completes."""

    def test_advance_step_through_all_steps(self, turn_manager_in_combat):
        """Verify advance_step works through all steps."""
        tm = turn_manager_in_combat
        current_turn = tm.get_next_pending_turn()

        # COMBAT_TURN_STEPS has 9 steps (indices 0-8)
        assert current_turn.current_step_index == 0

        # Advance through 8 steps (0→1, 1→2, ..., 7→8)
        for i in range(8):
            result = current_turn.advance_step()
            assert result is True  # More steps remain
            assert current_turn.current_step_index == i + 1

        # Now at index 8 (last step), try to advance
        result = current_turn.advance_step()
        assert result is False  # No more steps

    def test_advance_step_returns_false_at_end(self, turn_manager_in_combat):
        """Verify advance_step returns False when no more steps."""
        tm = turn_manager_in_combat
        current_turn = tm.get_next_pending_turn()

        # Move to last step
        current_turn.current_step_index = len(current_turn.game_step_list) - 1

        # Try to advance past end
        result = current_turn.advance_step()
        assert result is False

    def test_end_turn_pops_from_queue(self, turn_manager_in_combat):
        """Verify ending a turn removes it from the queue."""
        tm = turn_manager_in_combat

        initial_queue_length = len(tm.turn_stack[0])
        assert initial_queue_length == 4

        # Get first turn info
        first_turn_id = tm.get_next_pending_turn().turn_id

        # End the turn
        tm.end_turn_sync()

        # Queue should be shorter
        assert len(tm.turn_stack[0]) == initial_queue_length - 1

        # Next turn should be different
        next_turn = tm.get_next_pending_turn()
        assert next_turn.turn_id != first_turn_id

    def test_end_turn_reveals_next_turn(self, turn_manager_in_combat):
        """Verify get_next_pending_turn returns correct turn after ending."""
        tm = turn_manager_in_combat

        # Get the second turn's character (should be wizard)
        second_turn_character = tm.turn_stack[0][1].active_character

        # End first turn
        tm.end_turn_sync()

        # Next pending should be the former second turn
        next_turn = tm.get_next_pending_turn()
        assert next_turn.active_character == second_turn_character
        assert next_turn.active_character == "wizard"

    def test_end_turn_and_get_next_returns_sibling_info(self, turn_manager_in_combat):
        """Verify end_turn_and_get_next provides next turn details."""
        tm = turn_manager_in_combat

        result = tm.end_turn_and_get_next()

        # Should have info about next turn
        assert "next_pending" in result
        next_info = result["next_pending"]
        assert next_info["speaker"] == "wizard"
        assert next_info["subturn_id"] is not None

    def test_processing_turn_preserved_during_subturn_creation(self, turn_manager_in_combat):
        """Verify _processing_turn maintained when creating subturns."""
        tm = turn_manager_in_combat

        # Get the first turn
        main_turn = tm.get_next_pending_turn()
        main_turn_id = main_turn.turn_id

        # Store as processing turn
        tm._processing_turn = main_turn

        # Create a subturn (reaction)
        actions = [ActionDeclaration(speaker="wizard", content="I cast Shield!")]
        tm.start_and_queue_turns(actions)

        # Processing turn should still be the main turn
        assert tm._processing_turn.turn_id == main_turn_id


# =============================================================================
# TestReactionSubturnTransitions
# =============================================================================

class TestReactionSubturnTransitions:
    """Test reaction subturn creation and completion."""

    def test_start_and_queue_turns_creates_subturns(self, turn_manager_in_combat):
        """Verify start_and_queue_turns creates subturns at Level 1."""
        tm = turn_manager_in_combat

        # Start with Level 0 turn
        assert len(tm.turn_stack) == 1

        # Create reaction subturns
        actions = [
            ActionDeclaration(speaker="wizard", content="I use Shield!"),
            ActionDeclaration(speaker="fighter", content="I use my reaction to attack!")
        ]
        result = tm.start_and_queue_turns(actions)

        # Should have Level 1 queue now
        assert len(tm.turn_stack) == 2

        # Level 1 should have 2 turns
        level_1_queue = tm.turn_stack[1]
        assert len(level_1_queue) == 2

    def test_reaction_turns_get_reaction_steps(self, turn_manager_in_combat):
        """Verify reaction subturns use DEMO_REACTION_STEPS (6 steps)."""
        tm = turn_manager_in_combat

        # Create reaction subturn
        actions = [ActionDeclaration(speaker="wizard", content="Shield!")]
        tm.start_and_queue_turns(actions)

        # Get the subturn
        subturn = tm.turn_stack[1][0]

        assert subturn.game_step_list == DEMO_REACTION_STEPS
        assert len(subturn.game_step_list) == 6

    def test_hierarchical_turn_ids(self, turn_manager_in_combat):
        """Verify hierarchical turn ID structure (1, 1.1, 1.1.1)."""
        tm = turn_manager_in_combat

        # Get main turn
        main_turn = tm.get_next_pending_turn()
        main_turn_id = main_turn.turn_id

        # Create reaction subturn
        actions = [ActionDeclaration(speaker="wizard", content="Shield!")]
        tm.start_and_queue_turns(actions)

        # Get subturn
        subturn = tm.turn_stack[1][0]

        # Subturn ID should include parent ID
        assert subturn.turn_id.startswith(main_turn_id + ".")

    def test_monster_reactions_merged_with_player_actions(self, turn_manager_in_combat):
        """Verify monster reactions are queued alongside player actions."""
        tm = turn_manager_in_combat

        # Set pending monster reactions using the proper method
        tm.set_pending_monster_reactions([
            MonsterReactionDecision(
                monster_id="goblin_1",
                reaction_name="Opportunity Attack",
                trigger_condition="When fighter moves away",
                will_use=True
            )
        ])

        # Create player reaction
        player_actions = [ActionDeclaration(speaker="wizard", content="Shield!")]
        tm.start_and_queue_turns(player_actions)

        # Should have both player and monster reactions in Level 1
        level_1_queue = tm.turn_stack[1]

        # Should have 2 reactions (1 player + 1 monster)
        assert len(level_1_queue) == 2

        # Monster reactions should be cleared
        assert len(tm.get_pending_monster_reactions()) == 0

    def test_return_to_parent_after_all_reactions_complete(self, turn_manager_in_combat):
        """Verify return_to_parent=True when all subturns complete."""
        tm = turn_manager_in_combat

        # Create reaction subturns
        actions = [ActionDeclaration(speaker="wizard", content="Shield!")]
        tm.start_and_queue_turns(actions)

        # End the reaction subturn
        result = tm.end_turn_and_get_next()

        # Should indicate return to parent
        assert result["return_to_parent"] is True

        # Should be back at Level 0
        assert len(tm.turn_stack) == 1

    def test_nested_reaction_creates_deeper_level(self, turn_manager_in_combat):
        """Verify nested reactions create Level 2+ queues."""
        tm = turn_manager_in_combat

        # Create Level 1 reaction
        actions_level_1 = [ActionDeclaration(speaker="wizard", content="Shield!")]
        tm.start_and_queue_turns(actions_level_1)

        assert len(tm.turn_stack) == 2

        # Create Level 2 nested reaction
        actions_level_2 = [ActionDeclaration(speaker="fighter", content="I counterspell the counterspell!")]
        tm.start_and_queue_turns(actions_level_2)

        # Should have 3 levels now
        assert len(tm.turn_stack) == 3

        # Level 2 turn should have turn_level = 2
        level_2_turn = tm.turn_stack[2][0]
        assert level_2_turn.turn_level == 2

    def test_completed_subturn_returns_to_parent_level(self, turn_manager_in_combat):
        """Verify completed subturn properly returns to parent level."""
        tm = turn_manager_in_combat

        # Get main turn
        main_turn = tm.get_next_pending_turn()
        main_turn_id = main_turn.turn_id

        # Create and complete a reaction subturn
        actions = [ActionDeclaration(speaker="wizard", content="Shield!")]
        tm.start_and_queue_turns(actions)

        # Verify we're at Level 1
        assert len(tm.turn_stack) == 2

        # Add a message to the subturn
        subturn = tm.get_next_pending_turn()
        assert subturn.turn_level == 1
        subturn.add_live_message("Wizard casts Shield, AC increases by 5!", "DM")

        # End the subturn
        result = tm.end_turn_and_get_next()

        # Should have returned to parent level
        assert result["return_to_parent"] is True
        assert len(tm.turn_stack) == 1

        # Main turn should still be there
        current_turn = tm.get_next_pending_turn()
        assert current_turn.turn_id == main_turn_id


# =============================================================================
# TestRoundTransitions
# =============================================================================

class TestRoundTransitions:
    """Test transitions between combat rounds."""

    def test_round_increments_after_last_participant(self, turn_manager_in_combat):
        """Verify round_number increments after all participants via advance_combat_turn."""
        tm = turn_manager_in_combat

        # Start at round 1
        assert tm.combat_state.round_number == 1

        # Complete all 4 turns using advance_combat_turn for round progression
        for _ in range(4):
            tm.end_turn_sync()
            if tm.combat_state.phase == CombatPhase.COMBAT_ROUNDS:
                tm.advance_combat_turn()

        # Round should increment
        assert tm.combat_state.round_number == 2

    def test_new_round_queues_all_participants_again(self, turn_manager_in_combat):
        """Verify new round can be queued after all participants complete."""
        tm = turn_manager_in_combat

        # Complete all 4 turns of round 1
        for _ in range(4):
            tm.end_turn_sync()
            if tm.combat_state.phase == CombatPhase.COMBAT_ROUNDS:
                result = tm.advance_combat_turn()

        # Round 2 should have started
        assert tm.combat_state.round_number == 2

        # Queue the next round explicitly
        tm._queue_combat_round()

        # Should have new turns queued for round 2
        level_0_queue = tm.turn_stack[0]
        assert len(level_0_queue) == 4

        # Same order as before
        assert level_0_queue[0].active_character == "fighter"
        assert level_0_queue[1].active_character == "wizard"
        assert level_0_queue[2].active_character == "goblin_1"
        assert level_0_queue[3].active_character == "goblin_2"

    def test_advance_combat_turn_detects_new_round(self, turn_manager_in_combat):
        """Verify advance_turn detects when new round starts."""
        tm = turn_manager_in_combat

        # Move to last participant
        for _ in range(3):
            tm.combat_state.advance_turn()

        # Advance from last participant
        next_id, is_new_round = tm.combat_state.advance_turn()

        assert is_new_round is True
        assert next_id == "fighter"  # Back to first in order

    def test_turn_order_preserved_across_rounds(self, turn_manager_in_combat):
        """Verify initiative order stays same in round 2."""
        tm = turn_manager_in_combat

        # Get initiative order (this is persistent)
        initiative_order = [e.character_id for e in tm.combat_state.initiative_order]

        # Complete round 1
        for _ in range(4):
            tm.end_turn_sync()
            if tm.combat_state.phase == CombatPhase.COMBAT_ROUNDS:
                tm.advance_combat_turn()

        # Queue round 2
        tm._queue_combat_round()

        round_2_order = [t.active_character for t in tm.turn_stack[0]]

        assert initiative_order == round_2_order

    def test_empty_level_removed_from_stack(self, turn_manager_in_combat):
        """Verify empty level is removed from turn_stack."""
        tm = turn_manager_in_combat

        # Create subturns
        actions = [ActionDeclaration(speaker="wizard", content="Shield!")]
        tm.start_and_queue_turns(actions)

        assert len(tm.turn_stack) == 2

        # Complete subturn
        tm.end_turn_sync()

        # Level 1 should be removed
        assert len(tm.turn_stack) == 1


# =============================================================================
# TestCombatEndConditions
# =============================================================================

class TestCombatEndConditions:
    """Test combat ending conditions and transitions."""

    def test_is_combat_over_all_players_eliminated(self, combat_state, sample_initiative_entries):
        """Verify is_combat_over when all players removed."""
        combat_state.start_combat(["fighter", "wizard", "goblin_1", "goblin_2"])
        for entry in sample_initiative_entries:
            combat_state.add_initiative_roll(entry)
        combat_state.finalize_initiative()

        # Remove all players
        combat_state.remove_participant("fighter")
        combat_state.remove_participant("wizard")

        assert combat_state.is_combat_over() is True

    def test_is_combat_over_all_monsters_eliminated(self, combat_state, sample_initiative_entries):
        """Verify is_combat_over when all monsters removed."""
        combat_state.start_combat(["fighter", "wizard", "goblin_1", "goblin_2"])
        for entry in sample_initiative_entries:
            combat_state.add_initiative_roll(entry)
        combat_state.finalize_initiative()

        # Remove all monsters
        combat_state.remove_participant("goblin_1")
        combat_state.remove_participant("goblin_2")

        assert combat_state.is_combat_over() is True

    def test_is_combat_over_false_while_both_sides_remain(self, combat_state, sample_initiative_entries):
        """Verify is_combat_over is False with both sides present."""
        combat_state.start_combat(["fighter", "wizard", "goblin_1", "goblin_2"])
        for entry in sample_initiative_entries:
            combat_state.add_initiative_roll(entry)
        combat_state.finalize_initiative()

        # Remove one from each side
        combat_state.remove_participant("fighter")
        combat_state.remove_participant("goblin_1")

        # Still have one player and one monster
        assert combat_state.is_combat_over() is False

    def test_remove_participant_updates_combat_over(self, combat_state, sample_initiative_entries):
        """Verify combat_over triggers progressively."""
        combat_state.start_combat(["fighter", "wizard", "goblin_1", "goblin_2"])
        for entry in sample_initiative_entries:
            combat_state.add_initiative_roll(entry)
        combat_state.finalize_initiative()

        # Remove monsters one by one
        combat_state.remove_participant("goblin_1")
        assert combat_state.is_combat_over() is False

        combat_state.remove_participant("goblin_2")
        assert combat_state.is_combat_over() is True

    def test_remove_participant_adjusts_current_index(self, combat_state, sample_initiative_entries):
        """Verify current_participant_index adjusts when removing earlier participant."""
        combat_state.start_combat(["fighter", "wizard", "goblin_1", "goblin_2"])
        for entry in sample_initiative_entries:
            combat_state.add_initiative_roll(entry)
        combat_state.finalize_initiative()

        # Move to goblin_1's turn (index 2)
        combat_state.advance_turn()  # 0→1
        combat_state.advance_turn()  # 1→2
        assert combat_state.current_participant_index == 2

        # Remove fighter (index 0 in order, before current)
        combat_state.remove_participant("fighter")

        # Index should adjust
        assert combat_state.current_participant_index == 1  # Was 2, now 1

    def test_get_remaining_player_and_monster_ids(self, combat_state, sample_initiative_entries):
        """Verify helper methods return correct IDs."""
        combat_state.start_combat(["fighter", "wizard", "goblin_1", "goblin_2"])
        for entry in sample_initiative_entries:
            combat_state.add_initiative_roll(entry)
        combat_state.finalize_initiative()

        players = combat_state.get_remaining_player_ids()
        monsters = combat_state.get_remaining_monster_ids()

        assert set(players) == {"fighter", "wizard"}
        assert set(monsters) == {"goblin_1", "goblin_2"}


# =============================================================================
# TestStepListSelection
# =============================================================================

class TestStepListSelection:
    """Test correct step list selection based on phase and turn level."""

    def test_combat_start_uses_combat_start_steps(self, turn_manager):
        """Verify combat start turn uses COMBAT_START_STEPS."""
        turn_manager.enter_combat(["fighter"], "Test")

        current_turn = turn_manager.get_next_pending_turn()
        assert current_turn.game_step_list == COMBAT_START_STEPS
        # 5 steps: Step 0 (monster selection + announce) + Steps 1-4 (surprise, initiative, order, finalize)
        assert len(current_turn.game_step_list) == 5

    def test_player_main_turn_uses_combat_turn_steps(self, turn_manager_in_combat):
        """Verify player Level 0 turns use COMBAT_TURN_STEPS."""
        tm = turn_manager_in_combat

        # Fighter is a player
        fighter_turn = tm.turn_stack[0][0]
        assert fighter_turn.active_character == "fighter"
        assert fighter_turn.game_step_list == COMBAT_TURN_STEPS

    def test_monster_main_turn_uses_monster_turn_steps(self, turn_manager_in_combat):
        """Verify monster Level 0 turns use MONSTER_TURN_STEPS."""
        tm = turn_manager_in_combat

        # Goblin is a monster
        goblin_turn = tm.turn_stack[0][2]
        assert goblin_turn.active_character == "goblin_1"
        assert goblin_turn.game_step_list == MONSTER_TURN_STEPS

    def test_subturn_always_uses_reaction_steps(self, turn_manager_in_combat):
        """Verify subturns (Level 1+) use DEMO_REACTION_STEPS regardless of character."""
        tm = turn_manager_in_combat

        # Create reaction for player
        actions = [ActionDeclaration(speaker="fighter", content="Shield!")]
        tm.start_and_queue_turns(actions)

        # Even player reactions use DEMO_REACTION_STEPS
        subturn = tm.turn_stack[1][0]
        assert subturn.turn_level == 1
        assert subturn.game_step_list == DEMO_REACTION_STEPS

    def test_combat_end_uses_combat_end_steps(self, turn_manager):
        """Verify combat end phase would use COMBAT_END_STEPS."""
        # This tests the step list directly since TurnManager doesn't auto-create combat end turns
        from src.prompts.demo_combat_steps import get_steps_for_phase

        steps = get_steps_for_phase(GamePhase.COMBAT_END)
        assert steps == COMBAT_END_STEPS
        assert len(steps) == 5  # 5 steps including cleanup step

    def test_exploration_uses_exploration_steps(self, turn_manager):
        """Verify exploration phase uses EXPLORATION_STEPS."""
        from src.prompts.demo_combat_steps import get_steps_for_phase

        steps = get_steps_for_phase(GamePhase.EXPLORATION)
        assert steps == EXPLORATION_STEPS
        assert len(steps) == 1


# =============================================================================
# TestResolutionStepIndices
# =============================================================================

class TestResolutionStepIndices:
    """Test resolution step detection for state extraction."""

    def test_combat_turn_resolution_indices(self):
        """Verify indices {0, 3, 7} trigger extraction for COMBAT_TURN_STEPS."""
        assert COMBAT_TURN_RESOLUTION_INDICES == {0, 3, 7}

        # Test is_resolution_step_index function
        assert is_resolution_step_index(0, COMBAT_TURN_STEPS) is True
        assert is_resolution_step_index(3, COMBAT_TURN_STEPS) is True
        assert is_resolution_step_index(7, COMBAT_TURN_STEPS) is True

    def test_monster_turn_resolution_indices(self):
        """Verify indices {0, 3, 7} trigger extraction for MONSTER_TURN_STEPS."""
        assert MONSTER_TURN_RESOLUTION_INDICES == {0, 3, 7}

        assert is_resolution_step_index(0, MONSTER_TURN_STEPS) is True
        assert is_resolution_step_index(3, MONSTER_TURN_STEPS) is True
        assert is_resolution_step_index(7, MONSTER_TURN_STEPS) is True

    def test_reaction_resolution_indices(self):
        """Verify index {3} triggers extraction for DEMO_REACTION_STEPS."""
        assert REACTION_RESOLUTION_INDICES == {3}

        assert is_resolution_step_index(3, DEMO_REACTION_STEPS) is True

    def test_non_resolution_steps_return_false(self):
        """Verify non-resolution steps return False."""
        # For COMBAT_TURN_STEPS, indices 1, 2, 4, 5, 6, 8 are not resolution steps
        non_resolution = [1, 2, 4, 5, 6, 8]
        for idx in non_resolution:
            assert is_resolution_step_index(idx, COMBAT_TURN_STEPS) is False

        # For DEMO_REACTION_STEPS, indices 0, 1, 2, 4, 5 are not resolution steps
        non_resolution_reaction = [0, 1, 2, 4, 5]
        for idx in non_resolution_reaction:
            assert is_resolution_step_index(idx, DEMO_REACTION_STEPS) is False


# =============================================================================
# TestFullCombatFlow (Integration Tests)
# =============================================================================

class TestFullCombatFlow:
    """End-to-end tests of complete combat lifecycle."""

    def test_complete_combat_lifecycle(self, turn_manager, sample_initiative_entries):
        """Test complete combat lifecycle from start to finish."""
        tm = turn_manager

        # 1. Enter combat (NOT_IN_COMBAT → COMBAT_START)
        participants = ["fighter", "wizard", "goblin_1", "goblin_2"]
        tm.enter_combat(participants, "Goblin Ambush")
        assert tm.combat_state.phase == CombatPhase.COMBAT_START

        # 2. Add initiative entries
        for entry in sample_initiative_entries:
            tm.add_initiative_roll(
                character_id=entry.character_id,
                character_name=entry.character_name,
                roll=entry.roll,
                is_player=entry.is_player,
                dex_modifier=entry.dex_modifier
            )

        # 3. Finalize initiative (ends combat start turn automatically)
        tm.finalize_initiative(combat_start_turn_already_ended=False)
        assert tm.combat_state.phase == CombatPhase.COMBAT_ROUNDS
        assert tm.combat_state.round_number == 1

        # 4. Process Turn 1 (fighter) - advance all steps
        fighter_turn = tm.get_next_pending_turn()
        assert fighter_turn.active_character == "fighter"
        while fighter_turn.advance_step():
            pass

        # 5. End Turn 1 and advance combat
        tm.end_turn_sync()
        tm.advance_combat_turn()

        # 6. Process Turn 2 (wizard) with reaction
        wizard_turn = tm.get_next_pending_turn()
        assert wizard_turn.active_character == "wizard"

        # Create a reaction subturn during wizard's turn
        actions = [ActionDeclaration(speaker="goblin_1", content="Opportunity attack!")]
        tm.start_and_queue_turns(actions)

        # Complete reaction
        reaction_turn = tm.get_next_pending_turn()
        assert reaction_turn.turn_level == 1
        tm.end_turn_sync()

        # Return to wizard turn and complete it
        while wizard_turn.advance_step():
            pass
        tm.end_turn_sync()
        tm.advance_combat_turn()

        # 7. Process Turn 3 (goblin_1)
        goblin1_turn = tm.get_next_pending_turn()
        assert goblin1_turn.active_character == "goblin_1"
        while goblin1_turn.advance_step():
            pass
        tm.end_turn_sync()
        tm.advance_combat_turn()

        # 8. Process Turn 4 (goblin_2)
        goblin2_turn = tm.get_next_pending_turn()
        assert goblin2_turn.active_character == "goblin_2"
        while goblin2_turn.advance_step():
            pass
        tm.end_turn_sync()
        result = tm.advance_combat_turn()

        # 9. Verify Round 2 starts
        assert result.get("is_new_round") is True
        assert tm.combat_state.round_number == 2

        # 10. Remove all monsters (combat over)
        tm.combat_state.remove_participant("goblin_1")
        tm.combat_state.remove_participant("goblin_2")
        assert tm.combat_state.is_combat_over() is True

        # 11. Start combat end (COMBAT_ROUNDS → COMBAT_END)
        tm.combat_state.start_combat_end()
        assert tm.combat_state.phase == CombatPhase.COMBAT_END

        # 12. Finish combat (COMBAT_END → NOT_IN_COMBAT)
        tm.combat_state.finish_combat()
        assert tm.combat_state.phase == CombatPhase.NOT_IN_COMBAT

        # 13. Verify all state reset
        assert tm.combat_state.round_number == 0
        assert tm.combat_state.initiative_order == []
        assert tm.combat_state.participants == []

    def test_combat_with_participant_removal(self, turn_manager, sample_initiative_entries):
        """Test that removing a participant updates the initiative order."""
        tm = turn_manager

        # Setup combat
        participants = ["fighter", "wizard", "goblin_1", "goblin_2"]
        tm.enter_combat(participants, "Test")

        for entry in sample_initiative_entries:
            tm.add_initiative_roll(
                character_id=entry.character_id,
                character_name=entry.character_name,
                roll=entry.roll,
                is_player=entry.is_player,
                dex_modifier=entry.dex_modifier
            )

        # Finalize initiative
        tm.finalize_initiative(combat_start_turn_already_ended=False)

        # Verify initial state
        assert len(tm.combat_state.initiative_order) == 4
        assert tm.combat_state.round_number == 1

        # Remove a participant
        tm.combat_state.remove_participant("goblin_1")

        # Verify participant was removed from initiative order
        assert len(tm.combat_state.initiative_order) == 3
        assert "goblin_1" not in [e.character_id for e in tm.combat_state.initiative_order]

        # Verify remaining participants are correct
        remaining_ids = [e.character_id for e in tm.combat_state.initiative_order]
        assert remaining_ids == ["fighter", "wizard", "goblin_2"]

        # Remove all monsters to trigger combat over
        tm.combat_state.remove_participant("goblin_2")
        assert tm.combat_state.is_combat_over() is True

    def test_remove_queued_turns_for_defeated_character(self, turn_manager, sample_initiative_entries):
        """Test that removing a participant also removes their queued turns."""
        tm = turn_manager

        # Setup combat with 4 participants
        participants = ["fighter", "wizard", "goblin_1", "goblin_2"]
        tm.enter_combat(participants, "Test")

        for entry in sample_initiative_entries:
            tm.add_initiative_roll(
                character_id=entry.character_id,
                character_name=entry.character_name,
                roll=entry.roll,
                is_player=entry.is_player,
                dex_modifier=entry.dex_modifier
            )

        # Finalize initiative - this queues turns for all 4 participants
        tm.finalize_initiative(combat_start_turn_already_ended=False)

        # Verify 4 turns are queued (initiative order: fighter=20, wizard=15, goblin_2=12, goblin_1=10)
        # All 4 participants have their turns queued at level 0
        assert len(tm.turn_stack) == 1  # One level
        assert len(tm.turn_stack[0]) == 4  # 4 turns queued

        # Get the characters in the queue
        queued_characters = [turn.active_character for turn in tm.turn_stack[0]]
        assert "goblin_2" in queued_characters

        # Now remove goblin_2's queued turns (simulating what happens when they're defeated)
        removed_count = tm.remove_queued_turns_for_character("goblin_2")

        # Should have removed 1 turn (goblin_2's turn)
        # Note: The first turn (fighter) is the active turn and is not removed
        # goblin_2 is at position 2 (0-indexed), so it should be removed
        assert removed_count == 1

        # Verify goblin_2's turn is no longer in the queue
        remaining_characters = [turn.active_character for turn in tm.turn_stack[0]]
        assert "goblin_2" not in remaining_characters
        assert len(remaining_characters) == 3  # fighter, wizard, goblin_1

    def test_remove_queued_turns_preserves_active_turn(self, turn_manager, sample_initiative_entries):
        """Test that removing queued turns does NOT remove the currently active turn."""
        tm = turn_manager

        # Setup combat
        participants = ["fighter", "wizard", "goblin_1"]
        tm.enter_combat(participants, "Test")

        # Add initiative: fighter=20, wizard=15, goblin_1=10
        tm.add_initiative_roll("fighter", "Fighter", 20, True, 2)
        tm.add_initiative_roll("wizard", "Wizard", 15, True, 1)
        tm.add_initiative_roll("goblin_1", "Goblin 1", 10, False, 2)

        tm.finalize_initiative(combat_start_turn_already_ended=False)

        # fighter's turn is active (first in queue)
        active_turn = tm.get_next_pending_turn()
        assert active_turn.active_character == "fighter"

        # Try to remove fighter's turns (should not remove the active turn)
        removed_count = tm.remove_queued_turns_for_character("fighter")
        assert removed_count == 0  # Active turn is not removed

        # Active turn should still be fighter
        assert tm.get_next_pending_turn().active_character == "fighter"


# =============================================================================
# MONSTER INITIATIVE TESTS
# =============================================================================

class TestMonsterInitiativeInTurnManager:
    """Test that monster initiative rolls work in TurnManager.

    Note: Monster validation (ensuring monsters exist before adding initiative)
    is now handled in dm_tools.py's add_monster_initiative() function, not in
    TurnManager. This keeps TurnManager focused on turn management without
    coupling it to StateManager.
    """

    def test_monster_initiative_allowed(self, turn_manager):
        """Monster initiative rolls work in TurnManager without validation."""
        # Enter combat
        turn_manager.enter_combat(["fighter", "goblin_1"], "Test")

        # Add monster initiative - TurnManager accepts it directly
        # (validation happens at dm_tools layer)
        result = turn_manager.add_initiative_roll(
            character_id="goblin_1",
            character_name="Goblin",
            roll=12,
            is_player=False,
            dex_modifier=2
        )

        assert result["character_id"] == "goblin_1"
        assert len(turn_manager.combat_state.initiative_order) == 1

    def test_player_initiative_allowed(self, turn_manager):
        """Player initiative rolls work in TurnManager."""
        turn_manager.enter_combat(["fighter", "goblin_1"], "Test")

        # Add player initiative
        result = turn_manager.add_initiative_roll(
            character_id="fighter",
            character_name="Tharion",
            roll=18,
            is_player=True,
            dex_modifier=2
        )

        assert result["character_id"] == "fighter"
        assert len(turn_manager.combat_state.initiative_order) == 1
