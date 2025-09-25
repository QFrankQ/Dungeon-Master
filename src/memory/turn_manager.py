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
   - Sequential processing through GM orchestration with `end_turn_and_get_next()`

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

#### GM Agent Integration:
- Orchestrates reaction queue creation and processing
- Uses `end_turn_and_get_next()` for seamless transition management
- Determines processing order and sets step objectives

### Reaction Queue Processing Flow

1. **Reaction Collection**: GM collects positive reactions from players
2. **Queue Creation**: `start_and_queue_turns()` creates sibling subturns
3. **Sequential Processing**: GM processes each reaction through adjudication
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

**GM Orchestration**:
- Clear separation: GM handles flow, DM handles content
- Consistent tool interface for reaction management
- Flexible processing order (initiative, timing rules, context)

This design supports complex D&D reaction scenarios while maintaining clean architectural
boundaries and providing efficient queue processing for combat mechanics.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio

from ..models.formatted_game_message import FormattedGameMessage
from ..models.turn_context import TurnContext, TurnExtractionContext
from ..models.turn_message import create_live_message
from .state_extractor_context_builder import StateExtractorContextBuilder

# Optional imports for state extraction and message formatting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..services.message_formatter import MessageFormatter
    from ..agents.state_extractor import StateExtractorAgent
    from ..agents.structured_summarizer import StructuredTurnSummarizer

@dataclass(frozen=True)
class TurnManagerSnapshot:
    """Immutable snapshot of TurnManager state."""
    turn_stack: List[List[TurnContext]]  # Stack of turn queues
    completed_turns: List[TurnContext]
    current_step_objective: str
    turn_counter: int

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
    1. GM creates reaction queue via start_and_queue_turns()
    2. DM processes each reaction through resolve_action()
    3. GM uses end_turn_and_get_next() for seamless queue transitions
    4. Automatic return to parent when queue is empty

    Turn nesting level determined by stack depth.
    Applies HistoryManager pattern for message management and filtering.
    Supports GM orchestration of complex D&D reaction scenarios.
    """
    
    def __init__(
        self, 
        state_extractor: Optional["StateExtractorAgent"] = None,
        turn_condensation_agent: Optional["StructuredTurnSummarizer"] = None
    ):
        """
        Initialize the turn manager.
        
        Args:
            state_extractor: Optional state extractor for automatic processing
            turn_condensation_agent: Optional agent for turn condensation
        """
        self.state_extractor = state_extractor
        self.turn_condensation_agent = turn_condensation_agent
        
        # Context builders for different consumers
        self.state_extractor_context_builder = StateExtractorContextBuilder()
        
        # Turn stack - each level contains a queue of TurnContext objects
        # Structure: List[List[TurnContext]] where each inner list is a queue at that level
        self.turn_stack: List[List[TurnContext]] = []
        
        # Message formatter for processing messages (following HistoryManager pattern)
        self.message_formatter = None  # Lazy loaded when needed
        
        # Storage for current FormattedGameMessage objects (similar to HistoryManager)
        self._current_messages: List[FormattedGameMessage] = []
        
        # Completed turns history (for debugging/audit)
        self.completed_turns: List[TurnContext] = []
        
        # Turn counter for unique IDs
        self._turn_counter = 0
    
    def _get_message_formatter(self):
        """Lazy load MessageFormatter when needed."""
        if self.message_formatter is None:
            from ..services.message_formatter import MessageFormatter
            self.message_formatter = MessageFormatter()
        return self.message_formatter
    
    def start_and_queue_turns(
        self,
        actions: List[Dict[str, str]],
        new_step_objective: str,
        initiative_order: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Start one or more turns as an action queue with hierarchical turn ID generation.

        For single action: actions = [{"speaker": "Alice", "content": "I attack the orc"}]
        For reactions: actions = [{"speaker": "Bob", "content": "I cast Counterspell"},
                                 {"speaker": "Carol", "content": "I use Shield"}]

        Args:
            actions: List of {"speaker": str, "content": str} actions to queue
            new_step_objective: objective of the first step in new turns
            initiative_order: Current initiative order
            metadata: Additional turn metadata

        Returns:
            Dictionary with:
            - "turn_ids": List[str] of created turn IDs
            - "next_to_process": str of first turn ID to process
        """
        if not actions:
            raise ValueError("Cannot start turn with empty actions list")

        turn_level = len(self.turn_stack)  # Stack depth determines nesting level
        created_turn_ids = []

        # Get parent ID for subturns
        parent_id = None
        if turn_level > 0:
            parent_turn = self.turn_stack[-1][0]
            parent_id = parent_turn.turn_id

        # Create each action as a turn in the queue
        for i, action in enumerate(actions):
            # Generate hierarchical turn ID
            if turn_level == 0:
                # Root level turn - use counter
                self._turn_counter += 1
                turn_id = str(self._turn_counter)
            else:
                # Sub-turn - use parent.number format
                turn_id = f"{parent_id}.{i + 1}"

            # Create turn context
            turn_context = TurnContext(
                turn_id=turn_id,
                turn_level=turn_level,
                current_step_objective=new_step_objective,
                active_character=action["speaker"],
                initiative_order=initiative_order,
                metadata=metadata or {}
            )

            # Add the action as initial message
            turn_context.add_live_message(action["content"], action["speaker"])

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

    def end_turn_and_get_next(self) -> Dict[str, Any]:
        """
        End current turn and get information about next turn to process.
        Combines end_turn() with queue management for GM orchestration.

        Returns:
            Dictionary with turn completion info and next turn details
        """
        # Capture current level info BEFORE ending turn
        current_level_queue = self.turn_stack[-1] if self.turn_stack else []
        remaining_turns_after_current = len(current_level_queue) - 1  # Minus the one we're about to complete

        # End the current turn (this pops the completed turn and possibly the entire level)
        end_result = self.end_turn_sync()

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
    ) -> Optional[Any]:
        """
        Resolve an action and perform immediate state extraction.
        This should be called during action resolution, not at turn end,
        to ensure proper reaction timing and immediate state availability.
        
        Args:
            action_context: Description of the action being resolved
            metadata: Additional context for state extraction
        
        Returns:
            StateExtractionResult if state_extractor is available, None otherwise
        """
        if not self.turn_stack or not self.turn_stack[-1]:
            raise ValueError("No active turn to resolve action in")

        # Get the current active turn from the deepest level queue
        current_turn = self.turn_stack[-1][0]  # First turn in the current level queue
        
        # Add the action context as a live message to the current turn
        current_turn.add_live_message(action_context, current_turn.turn_id)
        
        # Perform state extraction if extractor is available
        state_result = None
        if self.state_extractor:
            state_result = await self._extract_state_changes_from_turn_context(
                current_turn, metadata or {}
            )
        
        return state_result
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
                condensation_result = await self.turn_condensation_agent.condense_turn(
                    turn_context=completed_turn,
                    additional_context=completed_turn.metadata
                )
                
                # If there's a parent turn, embed the condensed result
                if len(self.turn_stack) > 1:  # Has parent level
                    parent_level_queue = self.turn_stack[-2]
                    if parent_level_queue:  # Parent queue is not empty
                        parent_turn = parent_level_queue[0]  # Current active parent turn
                        parent_turn.add_completed_subturn(
                            condensation_result.condensed_summary,
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
        
        # Clear current messages after processing
        self._current_messages = []
        
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
    
    def add_new_message(self, new_message: str, speaker: str):
        if not self.turn_stack or not self.turn_stack[-1]:
            raise Exception("empty stack")
        current_turn = self.turn_stack[-1][0]  # First turn in current level queue
        current_turn.add_live_message(new_message, speaker)

    def create_message_xml(self, content: str, speaker: str) -> str:
        """
        Create XML representation of a message without adding it to any turn context.
        Useful for passing messages to GM context builder before committing to turn stack.

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
    
    
    def _prepare_extraction_context(self, turn_context: TurnContext) -> TurnExtractionContext:
        """
        Prepare extraction context for StateExtractor.
        Follows HistoryManager filtering pattern but for turn-specific content.
        """
        # Get all messages from this turn context
        turn_messages = turn_context.get_turn_context_messages()
        
        # Get any modifications from child turns
        parent_modifications = getattr(turn_context, 'child_modifications', [])
        
        return TurnExtractionContext(
            turn_id=turn_context.turn_id,
            turn_level=turn_context.turn_level,
            turn_messages=turn_messages,
            active_character=turn_context.active_character,
            parent_modifications=parent_modifications,
            metadata=turn_context.metadata
        )
    
    async def _extract_state_changes(self, context: TurnExtractionContext) -> Optional[Any]:
        """
        Extract state changes using the StateExtractor.
        """
        if not self.state_extractor:
            return None
        
        try:
            # Combine all turn messages into a single context string
            full_context = "\n".join([
                f"=== TURN {context.turn_id} (Level {context.turn_level}) ===",
                f"Active Character: {context.active_character or 'Unknown'}",
                "",
                "=== TURN MESSAGES ===",
                *context.turn_messages
            ])
            
            # Add parent modifications if any
            if context.parent_modifications:
                full_context += "\n\n=== CARRY-OVER EFFECTS ===\n"
                full_context += "\n".join(context.parent_modifications)
            
            # Use StateExtractor with structured turn context
            result = await self.state_extractor.extract_state_changes(
                formatted_turn_context=full_context,
                game_context={
                    "turn_id": context.turn_id,
                    "turn_level": context.turn_level,
                    "active_character": context.active_character,
                    **context.metadata
                }
            )
            
            return result
            
        except Exception as e:
            print(f"Failed to extract state changes for turn {context.turn_id}: {e}")
            return None
    
    async def _extract_state_changes_from_turn_context(
        self, 
        current_turn: TurnContext, 
        additional_context: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Extract state changes using StateExtractorContextBuilder for proper context isolation.
        
        Args:
            current_turn: The turn context to extract state changes from
            additional_context: Additional context for state extraction
            
        Returns:
            StateExtractionResult if state_extractor is available, None otherwise
        """
        if not self.state_extractor:
            return None
        
        try:
            # Build isolated context using StateExtractorContextBuilder
            formatted_context = self.state_extractor_context_builder.build_context(
                current_turn=current_turn,
                additional_context=additional_context
            )
            
            # Extract state changes with proper context isolation
            result = await self.state_extractor.extract_state_changes(
                formatted_turn_context=formatted_context,
                game_context={
                    "turn_id": current_turn.turn_id,
                    "turn_level": current_turn.turn_level,
                    "active_character": current_turn.active_character,
                    **additional_context
                }
            )
            
            return result
            
        except Exception as e:
            print(f"Failed to extract state changes for turn {current_turn.turn_id}: {e}")
            return None
    
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
        self._current_messages = []
        self._turn_counter = 0

    def get_snapshot(self) -> TurnManagerSnapshot:
        """Create immutable snapshot of current state."""
        current_step_objective = ""
        current_turn = self.get_current_turn_context()
        if current_turn:
            current_step_objective = current_turn.current_step_objective

        return TurnManagerSnapshot(
            turn_stack=[level_queue.copy() for level_queue in self.turn_stack],  # Shallow copy of structure
            completed_turns=self.completed_turns.copy(),
            current_step_objective=current_step_objective,
            turn_counter=self._turn_counter
        )

def create_turn_manager(
    state_extractor: Optional[Any] = None,
    turn_condensation_agent: Optional[Any] = None
) -> TurnManager:
    """
    Factory function to create a configured turn manager.
    
    Args:
        state_extractor: Optional state extractor for automatic processing
        turn_condensation_agent: Optional agent for turn condensation
    
    Returns:
        Configured TurnManager instance
    """
    return TurnManager(
        state_extractor=state_extractor,
        turn_condensation_agent=turn_condensation_agent
    )