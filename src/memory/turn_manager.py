"""
Turn management system for D&D combat with hierarchical turn/sub-turn tracking and reaction queues.

## Architecture Overview

The TurnManager implements a **queue-based turn stack** architecture that supports both single
turn processing and complex reaction queues. It separates action resolution (immediate state
updates) from turn conclusion (cleanup only) while providing hierarchical turn tracking with
context isolation to prevent duplicate state extractions.

### Core Data Structure: Stack of Queues

**Turn Stack Structure**: `List[List[TurnContext]]` where each level contains a queue of turns
- **Level 0**: `[[Turn_1], [Turn_2], ...]` - Main character turns in initiative order
- **Level 1**: `[[Turn_2.1, Turn_2.2, Turn_2.3]]` - Sibling reactions/sub-turns
- **Level 2+**: `[[Turn_2.1.1, Turn_2.1.2]]` - Nested reactions to reactions

**Queue Behavior**:
- Completed turns are **immediately popped** from their level queue
- Empty level queues are removed from the stack
- All remaining turns in a queue are either processing or pending
- First turn in each queue is always the next to process

### Key Design Principles

1. **Sibling Subturn Reaction Architecture**
   - Multiple reactions create sibling subturns at the same level (e.g., 2.1, 2.2, 2.3)
   - Turn stack itself serves as the natural queue structure
   - Sequential processing through GD orchestration with `end_turn_and_get_next()`

2. **Action Resolution vs Turn Conclusion Separation**
   - `resolve_action()`: Extracts and applies state changes during action resolution
   - `end_turn()`: Handles cleanup, condensation, and turn removal only
   - State extraction occurs at resolution time for proper D&D reaction timing

3. **Context Isolation for State Extraction**
   - Each turn maintains its own message context and extraction scope
   - StateExtractor focuses on current turn's resolution/narrative
   - Child turn messages serve as supplemental context, not primary extraction sources
   - Prevents duplicate state extractions across turn hierarchy

### Turn Creation and Queue Management

**Unified Turn Creation**: `start_and_queue_turns(actions, step_objective)`
```python
# Single action
start_and_queue_turns([{"speaker": "Alice", "content": "I attack the orc"}], "Receive action")

# Reaction queue (creates 2.1, 2.2, 2.3)
start_and_queue_turns([
    {"speaker": "Bob", "content": "I cast Counterspell!"},
    {"speaker": "Carol", "content": "I use Shield!"},
    {"speaker": "Dave", "content": "I dodge!"}
], "Process reactions")
```

**Queue Management Methods**:
- `get_next_pending_turn()`: Always returns first turn in current level queue
- `end_turn_and_get_next()`: End turn and provide transition information

### Hierarchical Turn ID Generation

- **Level 0**: Simple counter (`"1"`, `"2"`, `"3"`)
- **Subturns**: Parent.Number format (`"2.1"`, `"2.2"`, `"2.3"`)
- **Nested**: Dot notation (`"2.1.1"`, `"2.1.2"`)

### Message Flow and Agent Integration

#### DM Agent Integration:
- Reads full message history across all turns for complete context
- Incorporates subturn modifications into parent turn narrative
- Generates final resolved narrative reflecting all modification effects

#### StateExtractor Integration:
- Processes current turn's resolution/narrative as primary source
- Uses child turn messages as supplemental context for understanding
- Each extractor focuses on its own turn scope to avoid duplicate extractions

#### GD Agent Integration:
- Orchestrates reaction queue creation and processing
- Uses `end_turn_and_get_next()` for seamless transition management
- Determines processing order and sets step objectives

### Reaction Queue Processing Flow

1. **Reaction Collection**: GD collects positive reactions from players
2. **Queue Creation**: `start_and_queue_turns()` creates sibling subturns
3. **Sequential Processing**: GD processes each reaction through adjudication
4. **Queue Transitions**: `end_turn_and_get_next()` manages flow between reactions
5. **Parent Return**: Automatic return to parent turn when queue is empty

### Effect Types and Handling

**Modifications**: Immediate resolution adjustments that affect current action
- Example: "B's Shield spell reduces A's damage by 5"
- Flow: Sub-turn → Parent turn context → DM narrative → Final state extraction
- Lifespan: Applied during resolution, then discarded

**Effects**: Persistent state changes with duration
- Example: "Shield spell active for 1 minute"
- Handled by: StateManager as character-bound conditions/modifiers
- Tracked until: Duration expires or actively dispelled

### Integration with Session Architecture

The TurnManager integrates with the broader session architecture:
- **SessionManager**: Orchestrates overall session flow, owns TurnManager instance
- **MessageFormatter**: Processes messages between formats for turn context
- **HistoryManager**: Manages message history separate from turn-specific context
- **StateManager**: Applies extracted state changes to character models

### Design Benefits

**Natural Queue Structure**:
- Turn stack IS the queue - no separate queue metadata needed
- Visual representation of pending work via incomplete subturns
- Leverages existing turn management infrastructure

**Clean Queue Management**:
- Immediate turn removal prevents stale data
- Simple "first in queue" processing model
- Elegant completion tracking through stack depth

**GD Orchestration**:
- Clear separation: GD handles flow, DM handles content
- Consistent tool interface for reaction management
- Flexible processing order (initiative, timing rules, context)

This design supports complex D&D reaction scenarios while maintaining clean architectural
boundaries and providing efficient queue processing for combat mechanics.
"""

from typing import List, Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
import asyncio
from pydantic import BaseModel, Field

from ..models.formatted_game_message import FormattedGameMessage
from ..services.game_logger import GameLogger, LogLevel
from ..models.turn_context import TurnContext, TurnExtractionContext
from ..models.turn_message import create_live_message, create_message_group
from ..models.combat_state import CombatState, CombatPhase, InitiativeEntry, create_combat_state
from ..models.dm_response import MonsterReactionDecision
from ..context.state_extractor_context_builder import StateExtractorContextBuilder
from ..prompts.demo_combat_steps import (
    DEMO_MAIN_ACTION_STEPS, DEMO_REACTION_STEPS,
    COMBAT_START_STEPS, COMBAT_TURN_STEPS, COMBAT_END_STEPS,
    EXPLORATION_STEPS, MONSTER_TURN_STEPS, GamePhase, get_steps_for_phase
)


class ActionDeclaration(BaseModel):
    """
    Pydantic model for action declarations in turn management.

    Used as input parameter for start_and_queue_turns tool.
    Must be a Pydantic model (not Dict) for Gemini tool compatibility,
    as Gemini doesn't support additionalProperties in function schemas.
    """
    speaker: str = Field(..., description="Name of the character performing the action")
    content: str = Field(..., description="The action declaration text (e.g., 'I cast Counterspell!')")

# Optional imports for state extraction and message formatting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..services.message_formatter import MessageFormatter
    from ..agents.state_extractor import StateExtractorAgent
    from ..agents.structured_summarizer import StructuredTurnSummarizer, StructuredTurnSummary

@dataclass(frozen=True)
class TurnManagerSnapshot:
    """Immutable snapshot of TurnManager state."""
    turn_stack: List[List[TurnContext]]  # Stack of turn queues
    completed_turns: List[TurnContext]
    current_step_objective: str
    turn_counter: int
    active_turns_by_level: List[TurnContext]  # First TurnContext from each level for context building


class TurnManager:
    """
    Manages hierarchical turn tracking with queue-based reaction processing and context isolation.

    Implements a stack of queues architecture where each level contains a queue of turns.
    Supports both single turn processing and complex reaction queues with sibling subturns.
    Separates action resolution (immediate state updates) from turn conclusion (cleanup).

    Core Data Structure:
    - turn_stack: List[List[TurnContext]] - Stack of turn queues
    - Each level represents turn depth (0=main, 1=reactions, 2=nested reactions)
    - Completed turns are immediately popped; remaining turns are pending

    Key Methods:
    - start_and_queue_turns(): Create single turn or reaction queue with hierarchical IDs
    - resolve_action(): Extract and apply state changes during action resolution
    - end_turn(): Clean turn conclusion with condensation and removal
    - end_turn_and_get_next(): End turn and provide queue transition information
    - get_next_pending_turn(): Get first pending turn in current level queue

    Queue Processing Flow:
    1. GD creates reaction queue via start_and_queue_turns()
    2. DM processes each reaction through resolve_action()
    3. GD uses end_turn_and_get_next() for seamless queue transitions
    4. Automatic return to parent when queue is empty

    Turn nesting level determined by stack depth.
    Applies HistoryManager pattern for message management and filtering.
    Supports GD orchestration of complex D&D reaction scenarios.
    """
    
    def __init__(
        self,
        turn_condensation_agent: Optional["StructuredTurnSummarizer"] = None,
        logger: Optional[GameLogger] = None
    ):
        """
        Initialize the turn manager.

        Args:
            turn_condensation_agent: Optional agent for turn condensation
            logger: Optional GameLogger for tracing
        """
        self.turn_condensation_agent = turn_condensation_agent
        self.logger = logger

        # Context builders for different consumers
        self.state_extractor_context_builder = StateExtractorContextBuilder()

        # Turn stack - each level contains a queue of TurnContext objects
        # Structure: List[List[TurnContext]] where each inner list is a queue at that level
        self.turn_stack: List[List[TurnContext]] = []

        # Message formatter for processing messages (following HistoryManager pattern)
        self.message_formatter = None  # Lazy loaded when needed

        # Storage for current FormattedGameMessage objects (similar to HistoryManager)
        # self._current_messages: List[FormattedGameMessage] = []

        # Completed turns history (for debugging/audit)
        self.completed_turns: List[TurnContext] = []

        # Turn counter for unique IDs
        self._turn_counter = 0

        # Processing turn reference - tracks which turn is being processed by DM
        # This is set at the start of each processing call and used to advance
        # the correct turn's step even if tools create subturns during processing
        self._processing_turn: Optional[TurnContext] = None

        # Current game phase - determines which step list new turns use
        # Starts in EXPLORATION mode, transitions through combat phases
        self._current_game_phase: GamePhase = GamePhase.EXPLORATION

        # Combat state - tracks phase progression and initiative order
        self.combat_state: CombatState = create_combat_state()

        # Pending monster reactions - stored when DM records monster reaction decisions
        # These are merged into start_and_queue_turns when creating reaction subturns
        self._pending_monster_reactions: List[MonsterReactionDecision] = []

    def _get_message_formatter(self):
        """Lazy load MessageFormatter when needed."""
        if self.message_formatter is None:
            from ..services.message_formatter import MessageFormatter
            self.message_formatter = MessageFormatter()
        return self.message_formatter

    # ===== PENDING MONSTER REACTIONS MANAGEMENT =====

    def set_pending_monster_reactions(self, reactions: List[MonsterReactionDecision]) -> None:
        """
        Store pending monster reactions to be merged when creating reaction subturns.

        Called by SessionManager after DM response when monster_reactions field contains
        decisions with will_use=True. These reactions will be automatically merged
        into the next start_and_queue_turns call for reactions.

        Args:
            reactions: List of MonsterReactionDecision objects to store
        """
        # Only store reactions that will actually be used
        self._pending_monster_reactions = [r for r in reactions if r.will_use]

    def get_pending_monster_reactions(self) -> List[MonsterReactionDecision]:
        """Get the currently stored pending monster reactions."""
        return self._pending_monster_reactions

    def clear_pending_monster_reactions(self) -> None:
        """Clear all pending monster reactions."""
        self._pending_monster_reactions = []

    def get_monster_id_to_name_map(self) -> Dict[str, str]:
        """
        Get a mapping from monster character_id to display name from the combat state.

        Maps monster character_id (e.g., "goblin_1") to character_name (e.g., "Goblin Archer").
        This is useful for UI contexts that need to display monster names.

        Returns:
            Dict mapping monster character_id -> display name
        """
        mapping = {}
        for entry in self.combat_state.initiative_order:
            if not entry.is_player:
                mapping[entry.character_id] = entry.character_name
        return mapping

    def get_all_combatant_id_to_name_map(self) -> Dict[str, str]:
        """
        Get a mapping of all combatant character_ids to display names.

        Maps character_id to character_name for all combatants in initiative order.
        Useful for UI display across all combatants.

        Returns:
            Dict mapping character_id -> display_name
        """
        mapping = {}
        for entry in self.combat_state.initiative_order:
            mapping[entry.character_id] = entry.character_name
        return mapping

    def _merge_pending_monster_reactions(
        self,
        player_actions: List[ActionDeclaration]
    ) -> List[ActionDeclaration]:
        """
        Merge pending monster reactions with player actions.

        Monster reactions are converted to ActionDeclarations and appended to the
        player actions list. Duplicate reactions (same monster_id) are skipped.

        Args:
            player_actions: List of player reaction ActionDeclarations

        Returns:
            Merged list with both player and monster reactions
        """
        if not self._pending_monster_reactions:
            return player_actions

        merged_actions = list(player_actions)  # Copy to avoid mutating original

        # Get speakers already in the action list to avoid duplicates
        existing_speakers = {action.speaker for action in player_actions}

        # Convert monster reactions to ActionDeclarations
        for monster_reaction in self._pending_monster_reactions:
            if monster_reaction.monster_id not in existing_speakers:
                merged_actions.append(ActionDeclaration(
                    speaker=monster_reaction.monster_id,
                    content=f"Uses {monster_reaction.reaction_name}"
                ))

        # Clear pending reactions after merging
        self.clear_pending_monster_reactions()

        return merged_actions

    #TODO: using prepare_tools keyword argument in agent calls to control when this tool is available
    def start_and_queue_turns(
        self,
        actions: List[ActionDeclaration],
        phase: Optional[GamePhase] = None
    ) -> Dict[str, Any]:
        """
        Start one or more turns as an action queue with hierarchical turn ID generation.

        Determines the appropriate step list based on:
        1. If phase is explicitly provided, uses the step list for that phase
        2. Otherwise, auto-determines based on turn level:
           - Level 0 (main turn): Uses DEMO_MAIN_ACTION_STEPS (combat turns)
           - Level 1+ (sub-turn/reaction): Uses DEMO_REACTION_STEPS

        Args:
            actions: List of ActionDeclaration objects with speaker and content fields
                Example: [ActionDeclaration(speaker="Alice", content="I attack the orc")]
                For reactions: [ActionDeclaration(speaker="Bob", content="I cast Counterspell"),
                               ActionDeclaration(speaker="Carol", content="I use Shield")]
            phase: Optional GamePhase to explicitly set the step list.
                Use GamePhase.EXPLORATION for non-combat sessions.
                Use GamePhase.COMBAT_START for Phase 1 combat setup.
                Use GamePhase.COMBAT_ROUNDS for Phase 2 combat turns.
                Use GamePhase.COMBAT_END for Phase 3 combat conclusion.

        Returns:
            Dictionary with:
            - "turn_ids": List[str] of created turn IDs
            - "next_to_process": str of first turn ID to process
        """
        if not actions:
            raise ValueError("Cannot start turn with empty actions list")

        turn_level = len(self.turn_stack)  # Stack depth determines nesting level
        created_turn_ids = []

        # Merge pending monster reactions for reaction turns (level 1+)
        # This ensures monster reactions recorded by DM are included alongside player reactions
        if turn_level > 0 and self._pending_monster_reactions:
            actions = self._merge_pending_monster_reactions(actions)

        # Determine game_step_list based on phase, current game phase, or turn level
        if phase is not None:
            # Explicit phase provided - use corresponding step list
            game_step_list = get_steps_for_phase(phase)
        elif turn_level > 0:
            # Sub-turn/reaction - always use reaction steps regardless of game phase
            game_step_list = DEMO_REACTION_STEPS
        else:
            # Level 0 turn - use current game phase to determine step list
            game_step_list = get_steps_for_phase(self._current_game_phase)

        # Get parent turn for subturns
        parent_turn = None
        if turn_level > 0:
            parent_turn = self.turn_stack[-1][0]

        # Create each action as a turn in the queue
        for i, action in enumerate(actions):
            # Generate hierarchical turn ID
            if turn_level == 0:
                # Root level turn - use counter
                self._turn_counter += 1
                turn_id = str(self._turn_counter)
            else:
                # Sub-turn - use parent.number format
                # Increment parent's child_count to get next sequential number
                parent_turn.child_count += 1
                turn_id = f"{parent_turn.turn_id}.{parent_turn.child_count}"

            # Create turn context
            turn_context = TurnContext(
                turn_id=turn_id,
                turn_level=turn_level,
                current_step_objective=game_step_list[0],
                active_character=action.speaker,
                # initiative_order=initiative_order,
                game_step_list=game_step_list,
                current_step_index=0
            )

            # Add the action as initial message
            turn_context.add_live_message(action.content, action.speaker)

            # Add to the appropriate queue level
            if len(self.turn_stack) == turn_level:
                # Create new level queue with first turn
                self.turn_stack.append([turn_context])
            else:
                # Add to existing level queue
                self.turn_stack[turn_level].append(turn_context)

            created_turn_ids.append(turn_id)

        #TODO: return the context of the first turn to be processed
        return {
            "turn_ids": created_turn_ids,
            "next_to_process": created_turn_ids[0]
        }

    def get_next_pending_turn(self) -> Optional[TurnContext]:
        """
        Get the next pending turn in the current level queue.
        Since completed turns are popped immediately, the first turn is always next to process.
        """
        if not self.turn_stack or not self.turn_stack[-1]:
            return None

        current_level_queue = self.turn_stack[-1]
        return current_level_queue[0] if current_level_queue else None

    async def end_turn_and_get_next_async(self) -> Dict[str, Any]:
        """
        Async version: End current turn and get information about next turn to process.
        Combines end_turn() with queue management for GD orchestration.

        Also handles deferred combat end - only processes when a Level 0 (main) turn
        completes, ensuring all reactions resolve before combat transitions.

        Returns:
            Dictionary with turn completion info and next turn details.
            If combat_ended is True, includes combat_end_result with transition info.
        """
        # Capture current level info BEFORE ending turn
        current_level_queue = self.turn_stack[-1] if self.turn_stack else []
        remaining_turns_after_current = len(current_level_queue) - 1  # Minus the one we're about to complete

        # End the current turn (this pops the completed turn and possibly the entire level)
        end_result = await self.end_turn()

        # === PROCESS DEFERRED COMBAT END AT LEVEL 0 ONLY ===
        # Only check for pending combat end when a main turn (Level 0) completes.
        # This ensures all reactions/subturns resolve before combat transitions.
        if end_result.get("turn_level") == 0:
            combat_end_result = self.process_pending_combat_end()
            if combat_end_result:
                # Combat transitioning to COMBAT_END phase
                # start_combat_end() creates a new COMBAT_END turn on the stack
                return {
                    **end_result,
                    "combat_ended": True,
                    "combat_end_result": combat_end_result,
                    "next_pending": None
                }

        # Check if there were more turns at the original level
        if remaining_turns_after_current > 0:
            # More turns to process at the same level - level still exists
            next_turn = self.get_next_pending_turn()
            return {
                **end_result,
                "next_pending": {
                    "subturn_id": next_turn.turn_id,
                    "speaker": next_turn.active_character,
                    "step_needed": next_turn.current_step_objective
                }
            }
        else:
            # No more turns at that level - check if we returned to parent
            has_parent = len(self.turn_stack) > 0

            # === AUTO-ADVANCE COMBAT ROUND ===
            # If this was a Level 0 turn in COMBAT_ROUNDS and no parent, advance to next round
            if (end_result.get("turn_level") == 0
                and not has_parent
                and self._current_game_phase == GamePhase.COMBAT_ROUNDS
                and self.combat_state
                and self.combat_state.phase == CombatPhase.COMBAT_ROUNDS):

                advance_result = self.advance_combat_turn()

                if advance_result.get("combat_over"):
                    # Combat ended naturally (one side eliminated)
                    return {
                        **end_result,
                        "combat_ended": True,
                        "combat_end_result": advance_result,
                        "next_pending": None
                    }

                # New round started or next participant queued
                if advance_result.get("new_round_queued") or self.turn_stack:
                    next_turn = self.get_next_pending_turn()
                    if next_turn:
                        if self.logger:
                            self.logger.combat("Combat round auto-advanced",
                                             round_number=advance_result.get("round_number"),
                                             next_participant=advance_result.get("next_participant"),
                                             is_new_round=advance_result.get("is_new_round"))
                        return {
                            **end_result,
                            "next_pending": {
                                "subturn_id": next_turn.turn_id,
                                "speaker": next_turn.active_character,
                                "step_needed": next_turn.current_step_objective
                            },
                            "new_round": advance_result.get("is_new_round", False),
                            "round_number": advance_result.get("round_number")
                        }

            return {
                **end_result,
                "next_pending": None,
                "return_to_parent": has_parent,
                "parent_context": "Continue with parent turn resolution" if has_parent else None
            }

    def end_turn_and_get_next(self) -> Dict[str, Any]:
        """
        Synchronous version: End current turn and get information about next turn to process.
        Combines end_turn() with queue management for GD orchestration.

        Also handles deferred combat end - only processes when a Level 0 (main) turn
        completes, ensuring all reactions resolve before combat transitions.

        Returns:
            Dictionary with turn completion info and next turn details.
            If combat_ended is True, includes combat_end_result with transition info.
        """
        # Capture current level info BEFORE ending turn
        current_level_queue = self.turn_stack[-1] if self.turn_stack else []
        remaining_turns_after_current = len(current_level_queue) - 1  # Minus the one we're about to complete

        # End the current turn (this pops the completed turn and possibly the entire level)
        end_result = self.end_turn_sync()

        # === PROCESS DEFERRED COMBAT END AT LEVEL 0 ONLY ===
        # Only check for pending combat end when a main turn (Level 0) completes.
        # This ensures all reactions/subturns resolve before combat transitions.
        if end_result.get("turn_level") == 0:
            combat_end_result = self.process_pending_combat_end()
            if combat_end_result:
                # Combat transitioning to COMBAT_END phase
                # start_combat_end() creates a new COMBAT_END turn on the stack
                return {
                    **end_result,
                    "combat_ended": True,
                    "combat_end_result": combat_end_result,
                    "next_pending": None
                }

        # Check if there were more turns at the original level
        if remaining_turns_after_current > 0:
            # More turns to process at the same level - level still exists
            next_turn = self.get_next_pending_turn()
            return {
                **end_result,
                "next_pending": {
                    "subturn_id": next_turn.turn_id,
                    "speaker": next_turn.active_character,
                    "step_needed": next_turn.current_step_objective
                }
            }
        else:
            # No more turns at that level - check if we returned to parent
            has_parent = len(self.turn_stack) > 0

            # === AUTO-ADVANCE COMBAT ROUND ===
            # If this was a Level 0 turn in COMBAT_ROUNDS and no parent, advance to next round
            if (end_result.get("turn_level") == 0
                and not has_parent
                and self._current_game_phase == GamePhase.COMBAT_ROUNDS
                and self.combat_state
                and self.combat_state.phase == CombatPhase.COMBAT_ROUNDS):

                advance_result = self.advance_combat_turn()

                if advance_result.get("combat_over"):
                    # Combat ended naturally (one side eliminated)
                    return {
                        **end_result,
                        "combat_ended": True,
                        "combat_end_result": advance_result,
                        "next_pending": None
                    }

                # New round started or next participant queued
                if advance_result.get("new_round_queued") or self.turn_stack:
                    next_turn = self.get_next_pending_turn()
                    if next_turn:
                        if self.logger:
                            self.logger.combat("Combat round auto-advanced",
                                             round_number=advance_result.get("round_number"),
                                             next_participant=advance_result.get("next_participant"),
                                             is_new_round=advance_result.get("is_new_round"))
                        return {
                            **end_result,
                            "next_pending": {
                                "subturn_id": next_turn.turn_id,
                                "speaker": next_turn.active_character,
                                "step_needed": next_turn.current_step_objective
                            },
                            "new_round": advance_result.get("is_new_round", False),
                            "round_number": advance_result.get("round_number")
                        }

            return {
                **end_result,
                "next_pending": None,
                "return_to_parent": has_parent,
                "parent_context": "Continue with parent turn resolution" if has_parent else None
            }

    async def resolve_action(
        self,
        action_context: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add action context to current turn.
        State extraction is now handled by SessionManager.

        Args:
            action_context: Description of the action being resolved
            metadata: Additional context metadata (unused, kept for backward compatibility)
        """
        if not self.turn_stack or not self.turn_stack[-1]:
            raise ValueError("No active turn to resolve action in")

        # Get the current active turn from the deepest level queue
        current_turn = self.turn_stack[-1][0]  # First turn in the current level queue

        # Add the action context as a live message to the current turn
        current_turn.add_live_message(action_context, current_turn.turn_id)
    #TODO: update turnId and turn_level properly
    async def end_turn(self) -> Dict[str, Any]:
        """
        End the current turn, condense it, and embed in parent turn if applicable.
        
        This method:
        1. Processes end-of-turn effects
        2. Condenses the completed turn into structured action-resolution format
        3. Embeds condensed result in parent turn (if exists)
        4. Removes completed turn from current level queue in stack
        
        Returns:
            Dictionary with turn completion and condensation results
        """
        print("[SYSTEM] Ending current turn...")
        if not self.turn_stack or not self.turn_stack[-1]:
            raise ValueError("No active turn to end")

        # Process any end-of-turn effects first
        # end_of_turn_effects = await self.process_end_of_turn_effects()

        # Get the current turn to be completed (first in current level queue)
        current_level_queue = self.turn_stack[-1]
        completed_turn = current_level_queue[0]
        completed_turn.end_time = datetime.now()
        
        # Condense the turn if condensation agent is available
        condensation_result = None
        if self.turn_condensation_agent:
            try:
                # Condense the turn using TurnContext directly with chronological ordering
                condensation_result: StructuredTurnSummary = await self.turn_condensation_agent.condense_turn(
                    turn_context=completed_turn,
                    additional_context=completed_turn.metadata
                )
                
                # If there's a parent turn, embed the condensed result
                if len(self.turn_stack) > 1:  # Has parent level
                    parent_level_queue = self.turn_stack[-2]
                    if parent_level_queue:  # Parent queue is not empty
                        parent_turn = parent_level_queue[0]  # Current active parent turn
                        parent_turn.add_completed_subturn(
                            condensation_result.structured_summary,
                            completed_turn.turn_id
                        )
                    
            except Exception as e:
                print(f"Turn condensation failed for {completed_turn.turn_id}: {e}")
        
        # Remove completed turn from its queue
        current_level_queue.pop(0)  # Remove first turn from current level

        # If the current level queue is now empty, remove the entire level
        if not current_level_queue:
            self.turn_stack.pop()

        # Add completed global turns (level 0) to history
        if completed_turn.turn_level == 0:
            self.completed_turns.append(completed_turn)

        # Check for phase transitions based on completed turn's step list
        # When COMBAT_START turn ends, transition to COMBAT_ROUNDS
        if (completed_turn.game_step_list is COMBAT_START_STEPS and
            self._current_game_phase == GamePhase.COMBAT_START):
            try:
                # Pass True since we already handled turn completion above
                self.finalize_initiative(combat_start_turn_already_ended=True)
                print(f"[SYSTEM] Phase transitioned: COMBAT_START -> COMBAT_ROUNDS")
            except ValueError as e:
                print(f"[SYSTEM] Could not finalize initiative: {e}")

        # Clear current messages after processing
        # self._current_messages = []

        return {
            "turn_id": completed_turn.turn_id,
            "turn_level": completed_turn.turn_level,
            "duration": (completed_turn.end_time - completed_turn.start_time).total_seconds(),
            "message_count": len(completed_turn.messages),
            # "end_of_turn_effects": end_of_turn_effects,
            "condensation_result": condensation_result,
            "embedded_in_parent": len(self.turn_stack) >= 1  # Still has turns after popping
        }
    
    async def process_end_of_turn_effects(self) -> List[str]:
        """
        Process any effects that trigger at the end of a turn.
        This handles duration-based effects, cleanup, and other end-of-turn triggers.
        
        Returns:
            List of effect descriptions that were processed
        """
        if not self.turn_stack or not self.turn_stack[-1]:
            return []

        current_turn = self.turn_stack[-1][0]  # First turn in current level queue
        effects_processed = []
        
        # TODO: Implement end-of-turn effect processing
        # This would handle:
        # - Duration-based condition expiration
        # - End-of-turn damage (poison, burning, etc.)
        # - Spell effect expiration
        # - Regeneration effects
        # - Other turn-based triggers
        
        # For now, return any carry-over modifications as processed effects
        if hasattr(current_turn, 'child_modifications'):
            effects_processed.extend(current_turn.child_modifications)
        
        return effects_processed

    def resolve_action_sync(
        self, 
        action_context: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """Synchronous version of resolve_action."""
        return asyncio.run(self.resolve_action(action_context, metadata))

    def end_turn_sync(self) -> Dict[str, Any]:
        """Synchronous version of end_turn."""
        return asyncio.run(self.end_turn())

    # TODO: Should be deprecated in favor of add_messages, keep for now for backward compatibility
    def add_new_message(self, new_message: str, speaker: str):
        if not self.turn_stack or not self.turn_stack[-1]:
            raise Exception("Empty TurnStack, add_new_message failed")
        current_turn = self.turn_stack[-1][0]  # First turn in current level queue
        current_turn.add_live_message(new_message, speaker)

    def add_messages(self, messages: List[Dict[str, str]], is_new: bool = True) -> None:
        """
        Add one or more messages to current turn with automatic batching.

        - If len == 1: Adds as individual TurnMessage
        - If len > 1: Adds as MessageGroup (batched together)

        This provides a unified interface that encapsulates TurnMessage creation
        and automatically handles single vs batch semantics.

        Args:
            messages: List of {"content": str, "speaker": str} dicts
            is_new: Whether these messages should be marked as new (default True).
                   Set to False for DM responses to prevent them appearing as
                   "new messages" in the next DM run.

        Raises:
            ValueError: If no active turn or messages list is empty
        """
        if not messages:
            raise ValueError("Cannot add empty messages list")

        current_turn = self.get_current_turn_context()
        if not current_turn:
            raise ValueError("No active turn to add messages to")

        if len(messages) == 1:
            # Single message - add directly as individual TurnMessage
            msg = messages[0]
            turn_msg = create_live_message(
                content=msg["content"],
                turn_origin=current_turn.turn_id,
                turn_level=str(current_turn.turn_level),
                speaker=msg["speaker"],
                is_new_message=is_new
            )
            current_turn.messages.append(turn_msg)
        else:
            # Multiple messages - create as MessageGroup for batch semantics
            turn_messages = []
            for msg in messages:
                turn_msg = create_live_message(
                    content=msg["content"],
                    turn_origin=current_turn.turn_id,
                    turn_level=str(current_turn.turn_level),
                    speaker=msg["speaker"],
                    is_new_message=is_new
                )
                turn_messages.append(turn_msg)

            # Create group and set is_new_message flag
            message_group = create_message_group(turn_messages)
            message_group.is_new_message = is_new
            current_turn.messages.append(message_group)

    def mark_new_messages_as_responded(self) -> None:
        """
        Mark the most recently added message(s) as responded to by the DM.

        Works for both individual TurnMessage and MessageGroup.
        This should be called after the DM generates a response to player input.

        Uses the processing turn (the turn that was being processed when DM started)
        rather than the current turn, to handle cases where the DM created subturns
        during processing via tool calls like start_and_queue_turns.

        Raises:
            ValueError: If no processing turn or no messages in turn
        """
        # Use processing turn instead of current turn
        # This ensures we mark messages in the turn that was being processed,
        # even if tools created subturns that are now on top of the stack
        processing_turn = self.get_processing_turn()
        if not processing_turn:
            raise ValueError("No processing turn to mark messages in")

        if not processing_turn.messages:
            raise ValueError("No messages in processing turn to mark as responded")

        # Mark the last item (whether TurnMessage or MessageGroup)
        last_item = processing_turn.messages[-1]
        last_item.mark_as_responded()

    def get_processing_turn(self) -> Optional[TurnContext]:
        """Get the turn currently being processed."""
        return self._processing_turn

    def update_processing_turn_to_current(self) -> TurnContext:
        """
        Update the processing turn reference to the current turn on top of stack.

        This should be called:
        - At the start of each processing cycle to establish which turn is being processed
        - After tools create subturns during DM execution to switch to the subturn
        - After ending a turn to switch to the next turn in the queue

        The reference is preserved even if the stack changes, allowing us to
        advance the correct turn's step when DM signals completion.

        Returns:
            The new processing turn (current turn on stack)

        Raises:
            ValueError: If no active turn exists
        """
        current_turn = self.get_current_turn_context()
        if not current_turn:
            raise ValueError("No active turn to update processing reference to")

        self._processing_turn = current_turn
        return self._processing_turn

    def advance_processing_turn_step(self) -> bool:
        """
        Advance the step of the turn currently being processed.

        This advances the step index regardless of whether the processing turn
        is still on top of the stack (it may not be if tools created subturns).

        Returns:
            True if more steps remain in the turn, False if turn is complete

        Raises:
            ValueError: If no turn is currently being processed
        """
        if not self._processing_turn:
            raise ValueError("No turn is currently being processed")

        return self._processing_turn.advance_step()

    def create_message_xml(self, content: str, speaker: str) -> str:
        """
        Create XML representation of a message without adding it to any turn context.
        Useful for passing messages to GD context builder before committing to turn stack.

        Args:
            content: The message content
            speaker: The speaker of the message

        Returns:
            XML string representation of the message
        """
        # Create a temporary message for XML generation
        turn_origin = self.get_current_turn_origin() or "unknown"
        turn_level = str(self.get_turn_level() - 1) if self.get_turn_level() > 0 else "0"

        temp_message = create_live_message(content, turn_origin, turn_level, speaker)
        return temp_message.to_xml_element()
        
    def get_current_turn_context(self) -> Optional[TurnContext]:
        """Get the current active turn context."""
        if self.turn_stack and self.turn_stack[-1]:
            return self.turn_stack[-1][0]  # First turn in current level queue
        return None
    
    def get_turn_level(self) -> int:
        """Get current turn nesting level (stack depth)."""
        return len(self.turn_stack)
    
    def is_in_turn(self) -> bool:
        """Check if we're currently in a turn."""
        return len(self.turn_stack) > 0
    
    def get_current_turn_origin(self) -> Optional[str]:
        """Get the current turn's origin ID for TurnMessage conversion."""
        current_turn = self.get_current_turn_context()
        return current_turn.turn_id if current_turn else None
    
    def get_current_turn_level_str(self) -> str:
        """Get the current turn's level as string for TurnMessage conversion."""
        return str(max(0, self.get_turn_level() - 1))  # Stack depth - 1 for 0-based levels
    
    
    def get_turn_stats(self) -> Dict[str, Any]:
        """Get statistics about turn management."""
        # Count total active turns across all levels
        total_active_turns = sum(len(level_queue) for level_queue in self.turn_stack)

        current_turn = self.get_current_turn_context()
        return {
            "active_turns": total_active_turns,
            "current_turn_level": self.get_turn_level(),
            "completed_turns": len(self.completed_turns),
            "total_turns_started": self._turn_counter,
            "current_turn_id": current_turn.turn_id if current_turn else None,
            "turn_stack_depth": len(self.turn_stack)
        }
    
    def get_turn_stack_summary(self) -> List[str]:
        """Get a summary of the current turn stack."""
        summaries = []
        for level, level_queue in enumerate(self.turn_stack):
            for turn in level_queue:
                summaries.append(f"Level {level}: {turn.get_turn_summary()}")
        return summaries
    
    def clear_turn_history(self) -> None:
        """Clear all turn history and reset counters."""
        self.turn_stack = []
        self.completed_turns = []
        # self._current_messages = []
        self._turn_counter = 0
        # Reset combat state
        self.combat_state = create_combat_state()

    # Helper methods for GD post-run function calls

    def set_next_step_objective(self, objective: str) -> bool:
        """
        Set the next step objective for the current turn (top of stack).
        Used by GD's post-run function to update the current game step objective.

        Args:
            objective: The new step objective to set

        Returns:
            True if objective was set, False if no active turn
        """
        current_turn = self.get_current_turn_context()
        if current_turn:
            current_turn.current_step_objective = objective
            return True
        return False

    def get_current_step_objective(self) -> Optional[str]:
        """
        Get the current step objective from the top turn in the stack.

        Returns:
            The current step objective, or None if no active turn
        """
        current_turn = self.get_current_turn_context()
        return current_turn.current_step_objective if current_turn else None

    def get_snapshot(self) -> TurnManagerSnapshot:
        """Create immutable snapshot of current state."""
        current_step_objective = ""
        current_turn = self.get_current_turn_context()
        if current_turn:
            current_step_objective = current_turn.current_step_objective

        # Extract first TurnContext from each level for context building
        active_turns_by_level = []
        for level_queue in self.turn_stack:
            if level_queue:  # Only add if queue is not empty
                active_turns_by_level.append(level_queue[0])  # First turn in queue is active

        return TurnManagerSnapshot(
            turn_stack=[level_queue.copy() for level_queue in self.turn_stack],  # Shallow copy of structure
            completed_turns=self.completed_turns.copy(),
            current_step_objective=current_step_objective,
            turn_counter=self._turn_counter,
            active_turns_by_level=active_turns_by_level
        )

    # =========================================================================
    # COMBAT PHASE MANAGEMENT
    # =========================================================================
    # Methods for managing combat phase progression (Phase 1 → 2 → 3)

    def enter_combat(
        self,
        participants: List[str],
        encounter_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start Phase 1: Combat Start.

        Transitions from exploration to combat mode and creates the initial
        combat start turn for initiative collection.

        Args:
            participants: List of all combatant names (players + enemies)
            encounter_name: Optional descriptive name for the encounter

        Returns:
            Dictionary with combat start info including turn_id
        """
        if self.combat_state.phase != CombatPhase.NOT_IN_COMBAT:
            raise ValueError(f"Cannot enter combat: already in phase {self.combat_state.phase}")

        # Log combat start
        if self.logger:
            self.logger.combat("Combat started",
                              participants=participants,
                              encounter_name=encounter_name)

        # Transition game phase to COMBAT_START
        self._current_game_phase = GamePhase.COMBAT_START

        # Initialize combat state
        self.combat_state.start_combat(participants, encounter_name)

        # Create Phase 1 turn for initiative collection using current game phase
        self._turn_counter += 1
        turn_id = str(self._turn_counter)

        # Use get_steps_for_phase to ensure consistency
        step_list = get_steps_for_phase(self._current_game_phase)
        combat_start_turn = TurnContext(
            turn_id=turn_id,
            turn_level=0,
            current_step_objective=step_list[0],
            active_character="SYSTEM",
            game_step_list=step_list,
            current_step_index=0
        )

        # Add initial message about combat starting
        combat_start_turn.add_live_message(
            f"Combat initiated: {encounter_name or 'Encounter'} with {len(participants)} participants",
            "SYSTEM"
        )

        # Clear any existing exploration turns before starting combat
        # (Combat is a phase transition, exploration turns should be completed/archived)
        while self.turn_stack:
            for turn in self.turn_stack.pop():
                if turn.end_time is None:
                    turn.end_time = datetime.now()
                self.completed_turns.append(turn)

        # Add combat start turn at level 0
        self.turn_stack.append([combat_start_turn])

        return {
            "phase": CombatPhase.COMBAT_START.value,
            "turn_id": turn_id,
            "participants": participants,
            "encounter_name": encounter_name,
            "step_objective": COMBAT_START_STEPS[0]
        }

    def add_initiative_roll(
        self,
        character_id: str,
        character_name: str,
        roll: int,
        is_player: bool = True,
        dex_modifier: int = 0
    ) -> Dict[str, Any]:
        """
        Add an initiative roll during Phase 1.

        Note on 2024 PHB Surprise Rules:
        - Surprise gives DISADVANTAGE on initiative roll (not "skip first turn")
        - The disadvantage should be applied BEFORE rolling
        - The roll parameter should be the final result with all modifiers applied

        Args:
            character_id: Unique identifier for the character (e.g., 'fighter', 'goblin_1')
            character_name: Display name of the character
            roll: Total initiative roll result (with any advantage/disadvantage already applied)
            is_player: Whether this is a player character
            dex_modifier: Dexterity modifier for tie-breaking

        Returns:
            Dictionary with roll info and collection status

        Raises:
            ValueError: If phase is not COMBAT_START
        """
        if self.combat_state.phase != CombatPhase.COMBAT_START:
            raise ValueError(f"Cannot add initiative in phase {self.combat_state.phase}")

        entry = InitiativeEntry(
            character_id=character_id,
            character_name=character_name,
            roll=roll,
            is_player=is_player,
            dex_modifier=dex_modifier
        )

        self.combat_state.add_initiative_roll(entry)

        # Check if all participants have rolled (by character_id)
        rolled = {e.character_id for e in self.combat_state.initiative_order}
        missing = [p for p in self.combat_state.participants if p not in rolled]

        # Log initiative roll
        if self.logger:
            self.logger.combat("Initiative roll added",
                              character_id=character_id,
                              character_name=character_name,
                              roll=roll,
                              is_player=is_player,
                              dex_modifier=dex_modifier,
                              collected=len(self.combat_state.initiative_order),
                              total=len(self.combat_state.participants))

        return {
            "character_id": character_id,
            "character_name": character_name,
            "roll": roll,
            "collected": len(self.combat_state.initiative_order),
            "total_participants": len(self.combat_state.participants),
            "missing": missing,
            "all_collected": len(missing) == 0
        }

    def finalize_initiative(self, combat_start_turn_already_ended: bool = False) -> Dict[str, Any]:
        """
        Finalize initiative order and transition Phase 1 → Phase 2.

        Sorts the initiative order and queues the first round of combat turns.

        Args:
            combat_start_turn_already_ended: If True, skip ending the combat start turn
                (used when called from end_turn() which already handled turn completion)

        Returns:
            Dictionary with initiative order and first turn info
        """
        if self.combat_state.phase != CombatPhase.COMBAT_START:
            raise ValueError(f"Cannot finalize initiative in phase {self.combat_state.phase}")

        # Transition game phase to COMBAT_ROUNDS
        self._current_game_phase = GamePhase.COMBAT_ROUNDS

        # Finalize the initiative order in combat state
        self.combat_state.finalize_initiative()

        # Log initiative finalized
        if self.logger:
            self.logger.combat("Initiative finalized",
                              order=[{"id": e.character_id, "name": e.character_name, "roll": e.roll}
                                     for e in self.combat_state.initiative_order],
                              round_number=self.combat_state.round_number)

        # Validate that initiative order is not empty
        if not self.combat_state.initiative_order:
            raise ValueError(
                "Cannot transition to COMBAT_ROUNDS: initiative_order is empty. "
                "No initiative rolls were registered. Ensure all players submitted initiative "
                "via the modal and monster initiative was added via add_monster_initiative()."
            )

        # End the combat start turn if one exists and not already ended
        if not combat_start_turn_already_ended and self.turn_stack and self.turn_stack[-1]:
            combat_start_turn = self.turn_stack[-1][0]
            combat_start_turn.end_time = datetime.now()
            self.turn_stack[-1].pop(0)
            if not self.turn_stack[-1]:
                self.turn_stack.pop()
            self.completed_turns.append(combat_start_turn)

        # Queue the first round of combat turns
        self._queue_combat_round()

        # Get the first participant
        first_participant = self.combat_state.get_current_participant_id()

        return {
            "phase": CombatPhase.COMBAT_ROUNDS.value,
            "round_number": self.combat_state.round_number,
            "initiative_order": [
                {
                    "character": e.character_name,
                    "roll": e.roll,
                    "is_player": e.is_player
                }
                for e in self.combat_state.initiative_order
            ],
            "first_participant": first_participant,
            "initiative_summary": self.combat_state.get_initiative_summary()
        }

    def _is_player_character(self, character_id: str) -> bool:
        """
        Check if a character is a player character using the initiative order.

        Looks up the character by their character_id in the initiative order
        and returns the is_player flag from the InitiativeEntry.

        Args:
            character_id: The character's unique identifier (e.g., "fighter", "goblin_1")

        Returns:
            True if the character is a player, False if monster/NPC
        """
        for entry in self.combat_state.initiative_order:
            if entry.character_id == character_id:
                return entry.is_player
        # Default to True if not found in initiative (for non-combat scenarios)
        return True

    def _get_step_list_for_character(self, character_id: str, turn_level: int) -> list:
        """
        Get the appropriate step list based on character type and turn level.

        Args:
            character_id: The character's unique identifier (e.g., "fighter", "goblin_1")
            turn_level: The turn nesting level (0=main, 1+=sub-turn/reaction)

        Returns:
            The appropriate step list for this character/turn
        """
        if turn_level > 0:
            # Sub-turns/reactions use reaction steps regardless of character type
            return DEMO_REACTION_STEPS

        # Level 0 turns: check if player or monster using is_player flag
        if self._is_player_character(character_id):
            return get_steps_for_phase(self._current_game_phase)
        else:
            return MONSTER_TURN_STEPS

    def _queue_combat_round(self) -> None:
        """
        Queue turns for the current combat round based on initiative order.

        Creates a turn for each participant in initiative order.
        Uses COMBAT_TURN_STEPS for players and MONSTER_TURN_STEPS for monsters.
        """
        if not self.combat_state.initiative_order:
            return

        turn_level = len(self.turn_stack)

        for entry in self.combat_state.initiative_order:
            self._turn_counter += 1
            turn_id = str(self._turn_counter)

            # Select step list based on whether this is a player or monster (using is_player flag)
            step_list = self._get_step_list_for_character(entry.character_id, turn_level)

            turn_context = TurnContext(
                turn_id=turn_id,
                turn_level=turn_level,
                current_step_objective=step_list[0],
                active_character=entry.character_id,  # Use character_id for system lookups
                initiative_order=[e.character_id for e in self.combat_state.initiative_order],
                game_step_list=step_list,
                current_step_index=0
            )

            # Add the turn start message (use display name for narrative)
            turn_context.add_live_message(
                f"{entry.character_name}'s turn begins",
                entry.character_id
            )

            # Add to turn stack
            if len(self.turn_stack) == turn_level:
                self.turn_stack.append([turn_context])
            else:
                self.turn_stack[turn_level].append(turn_context)

    def advance_combat_turn(self) -> Dict[str, Any]:
        """
        Advance to the next participant in combat order.

        Should be called after a participant's turn ends to move to the next.
        Handles round wrap-around and checks for combat end conditions.

        Returns:
            Dictionary with next turn info or combat end trigger
        """
        if self.combat_state.phase != CombatPhase.COMBAT_ROUNDS:
            raise ValueError(f"Cannot advance combat turn in phase {self.combat_state.phase}")

        next_participant, is_new_round = self.combat_state.advance_turn()

        # Log turn advancement
        if self.logger:
            self.logger.combat("Turn advanced",
                              next_character=next_participant,
                              round_number=self.combat_state.round_number,
                              is_new_round=is_new_round)

        # Check if combat should end
        if self.combat_state.is_combat_over():
            return {
                "combat_over": True,
                "reason": "One side eliminated",
                "remaining_players": self.combat_state.get_remaining_player_ids(),
                "remaining_monsters": self.combat_state.get_remaining_monster_ids()
            }

        result = {
            "combat_over": False,
            "next_participant": next_participant,
            "is_new_round": is_new_round,
            "round_number": self.combat_state.round_number
        }

        # If new round, queue new turns
        if is_new_round:
            self._queue_combat_round()
            result["new_round_queued"] = True

        return result

    def start_combat_end(self, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Start Phase 3: Combat End.

        Transitions from combat rounds to the conclusion phase.

        Args:
            reason: Optional reason for combat ending

        Returns:
            Dictionary with combat end phase info
        """
        if self.combat_state.phase != CombatPhase.COMBAT_ROUNDS:
            raise ValueError(f"Cannot end combat from phase {self.combat_state.phase}")

        # Transition game phase to COMBAT_END
        self._current_game_phase = GamePhase.COMBAT_END

        # Transition combat state
        self.combat_state.start_combat_end()

        # Properly end all remaining combat turns before clearing
        # This ensures they're added to completed_turns with proper end_time
        turns_ended = 0
        for level_queue in self.turn_stack:
            for turn in level_queue:
                if turn.end_time is None:
                    turn.end_time = datetime.now()
                self.completed_turns.append(turn)
                turns_ended += 1

        if self.logger and turns_ended > 0:
            self.logger.turn("Combat turns ended for combat conclusion",
                           turns_ended=turns_ended,
                           reason=reason)

        # Clear the turn stack
        self.turn_stack = []

        # Create Phase 3 turn for conclusion using current game phase
        self._turn_counter += 1
        turn_id = str(self._turn_counter)

        # Use get_steps_for_phase to ensure consistency
        step_list = get_steps_for_phase(self._current_game_phase)
        combat_end_turn = TurnContext(
            turn_id=turn_id,
            turn_level=0,
            current_step_objective=step_list[0],
            active_character="SYSTEM",
            game_step_list=step_list,
            current_step_index=0
        )

        # Add summary message
        players_remaining = self.combat_state.get_remaining_players()
        enemies_remaining = self.combat_state.get_remaining_enemies()
        combat_end_turn.add_live_message(
            f"Combat concluding. Rounds: {self.combat_state.round_number}. "
            f"Players remaining: {len(players_remaining)}. "
            f"Enemies remaining: {len(enemies_remaining)}. "
            f"Reason: {reason or 'Combat conditions met'}",
            "SYSTEM"
        )

        self.turn_stack.append([combat_end_turn])

        return {
            "phase": CombatPhase.COMBAT_END.value,
            "turn_id": turn_id,
            "rounds_fought": self.combat_state.round_number,
            "players_remaining": players_remaining,
            "enemies_remaining": enemies_remaining,
            "reason": reason,
            "step_objective": step_list[0]
        }

    def finish_combat(self) -> Dict[str, Any]:
        """
        Complete combat and return to exploration mode.

        Should be called after Phase 3 steps are complete.

        Returns:
            Dictionary with combat summary
        """
        if self.combat_state.phase != CombatPhase.COMBAT_END:
            raise ValueError(f"Cannot finish combat from phase {self.combat_state.phase}")

        # Transition game phase back to EXPLORATION
        self._current_game_phase = GamePhase.EXPLORATION

        # Capture summary before clearing
        summary = {
            "encounter_name": self.combat_state.encounter_name,
            "rounds_fought": self.combat_state.round_number,
            "final_participants": self.combat_state.participants.copy(),
            "players_remaining": self.combat_state.get_remaining_players(),
            "enemies_remaining": self.combat_state.get_remaining_enemies()
        }

        # End combat end turn if exists
        if self.turn_stack and self.turn_stack[-1]:
            combat_end_turn = self.turn_stack[-1][0]
            combat_end_turn.end_time = datetime.now()
            self.completed_turns.append(combat_end_turn)

        # Reset everything
        self.combat_state.finish_combat()
        self.turn_stack = []

        return {
            "phase": CombatPhase.NOT_IN_COMBAT.value,
            "combat_complete": True,
            "summary": summary
        }

    def process_pending_combat_end(self) -> Optional[Dict[str, Any]]:
        """
        Check for and process any pending combat end.

        Called by session_manager after state extraction to handle deferred
        combat end. This ensures the final action's damage/effects are properly
        recorded before transitioning to COMBAT_END phase.

        Returns:
            Result from start_combat_end() if combat end was pending, None otherwise
        """
        if not self.combat_state:
            return None

        reason = self.combat_state.consume_pending_end()
        if reason is None:
            return None

        # Log the deferred transition
        if self.logger:
            self.logger.combat("Processing deferred combat end", reason=reason)

        # Now actually transition to combat end
        return self.start_combat_end(reason=reason)

    def get_combat_phase(self) -> CombatPhase:
        """Get the current combat phase."""
        return self.combat_state.phase

    def is_in_combat(self) -> bool:
        """Check if currently in any combat phase."""
        return self.combat_state.phase != CombatPhase.NOT_IN_COMBAT

    def get_current_phase(self) -> GamePhase:
        """
        Get the current game phase.

        Returns:
            The current GamePhase (EXPLORATION, COMBAT_START, COMBAT_ROUNDS, COMBAT_END, or REACTION)
        """
        return self._current_game_phase

    def set_phase(self, phase: GamePhase) -> None:
        """
        Explicitly set the current game phase.

        Use this for manual phase transitions (e.g., from Discord commands).
        For combat phase transitions, prefer using enter_combat(), finalize_initiative(),
        start_combat_end(), and finish_combat() methods.

        Args:
            phase: The GamePhase to transition to
        """
        self._current_game_phase = phase

    def get_combat_summary(self) -> Dict[str, Any]:
        """Get a summary of the current combat state."""
        return {
            "phase": self.combat_state.phase.value,
            "game_phase": self._current_game_phase.value,
            "round_number": self.combat_state.round_number,
            "current_participant": self.combat_state.get_current_participant_id(),
            "participants_count": len(self.combat_state.participants),
            "initiative_order": [
                {"name": e.character_name, "roll": e.roll, "is_player": e.is_player}
                for e in self.combat_state.initiative_order
            ],
            "players_remaining": len(self.combat_state.get_remaining_player_ids()),
            "monsters_remaining": len(self.combat_state.get_remaining_monster_ids())
        }


def create_turn_manager(
    turn_condensation_agent: Optional[Any] = None,
    logger: Optional[GameLogger] = None
) -> TurnManager:
    """
    Factory function to create a configured turn manager.

    Args:
        turn_condensation_agent: Optional agent for turn condensation
        logger: Optional GameLogger for tracing

    Returns:
        Configured TurnManager instance
    """
    return TurnManager(
        turn_condensation_agent=turn_condensation_agent,
        logger=logger
    )