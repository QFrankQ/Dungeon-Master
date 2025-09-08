"""
Turn management system for D&D combat with hierarchical turn/sub-turn tracking.

## Architecture Overview

The TurnManager implements a session-centric design that separates action resolution
(immediate state updates) from turn conclusion (cleanup only). It provides hierarchical
turn tracking with context isolation to prevent duplicate state extractions.

### Key Design Principles

1. **Action Resolution vs Turn Conclusion Separation**
   - `resolve_action()`: Extracts and applies state changes during action resolution
   - `end_turn()`: Handles cleanup and end-of-turn effects only
   - State extraction occurs at resolution time for proper D&D reaction timing

2. **Context Isolation for State Extraction**
   - Each turn maintains its own message context and extraction scope  
   - StateExtractor focuses on current turn's resolution/narrative
   - Child turn messages serve as supplemental context, not primary extraction sources
   - Prevents duplicate state extractions across turn hierarchy

3. **Modification Flow Architecture**
   - Modifications flow upward from child turns to parent turns as context
   - DM incorporates child turn modifications into parent turn narrative generation
   - StateExtractor processes final resolved narrative, not intermediate modifications
   - No special handling needed for bottom-level turns (DM narrative already includes effects)

### Message Flow and Responsibilities

#### DM Agent Integration:
- Reads full message history across all turns
- Incorporates subturn modifications into parent turn narrative
- Generates final resolved narrative reflecting all modification effects

#### StateExtractor Integration:
- Processes current turn's resolution/narrative as primary source
- Uses child turn messages as supplemental context for understanding
- Extracts state changes from final resolved outcomes
- Each extractor focuses on its own turn scope to avoid duplicates

#### StateManager Integration:
- Handles character-bound state changes (HP, conditions, resources)
- Applies immediate state updates during action resolution
- Maintains persistent character state across turn boundaries

### Turn Hierarchy and Types

**Turn Levels** (determined by stack depth):
- Level 0: Main character turns in initiative order
- Level 1: Sub-turns (reactions, opportunity attacks, triggered effects)
- Level 2+: Nested sub-turns (reactions to reactions, etc.)

**Turn Flow:**
1. `start_turn()` - Begin new turn/sub-turn context
2. `resolve_action()` - Extract/apply state changes during resolution
3. `end_turn()` - Process end-of-turn effects and cleanup

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

### Design Rationale

**Why Not Pass Turn Summaries Up?**
- DM already has full message history
- Prevents duplicate state extractions
- Each extractor focuses on its own scope
- Subturn messages provide necessary context without redundancy

**Why Resolve Actions During Resolution, Not at Turn End?**
- Proper D&D reaction timing requirements
- Immediate state availability for cascading effects
- Separation of concerns: resolution vs cleanup

**Why Context Isolation?**  
- Prevents duplicate processing of the same state changes
- Clean separation of extraction responsibilities
- Maintains audit trail while avoiding overlap

This design ensures accurate D&D combat mechanics while maintaining clean
architectural boundaries and preventing common pitfalls in turn-based systems.
"""

from typing import List, Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from ..models.formatted_game_message import FormattedGameMessage
from ..models.turn_message import TurnMessage, MessageType, create_live_message, create_completed_subturn_message
from .state_extractor_context_builder import StateExtractorContextBuilder



# Optional imports for state extraction and message formatting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..services.message_formatter import MessageFormatter
    from ..agents.state_extractor import StateExtractorAgent
    from ..agents.state_updates import StateExtractionResult
    from ..agents.structured_summarizer import StructuredTurnSummarizer

#TODO: Integrate current step objectives for the narrator as part of context provided by the game manager 
@dataclass 
class TurnContext:
    """
    Context for a single turn or sub-turn in the turn stack.
    
    Contains messages with selective filtering capabilities to serve both
    DM (full chronological context) and StateExtractor (current turn only) needs.
    
    Uses TurnMessage system to distinguish between live conversation messages
    and condensed subturn results for proper context isolation.
    """
    turn_id: str
    turn_level: int  # Stack depth (0=main turn, 1=sub-turn, 2=sub-sub-turn, etc.)
    active_character: Optional[str] = None
    initiative_order: Optional[List[str]] = None
    
    # Enhanced message management with selective filtering
    messages: List[TurnMessage] = field(default_factory=list)
    
    # Legacy message storage for backward compatibility
    _formatted_messages: List[FormattedGameMessage] = field(default_factory=list)
    
    # Turn metadata
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_live_message(self, content: str) -> None:
        """Add a live conversation message to this turn's context."""
        message = create_live_message(content, self.turn_id, self.turn_level, self.turn_level)
        self.messages.append(message)
    
    def add_completed_subturn(self, condensed_content: str, subturn_id: str) -> None:
        """Add a condensed subturn result to this turn's context."""
        message = create_completed_subturn_message(condensed_content, subturn_id, self.turn_level, self.turn_level)
        self.messages.append(message)
    
    def get_live_messages_only(self) -> List[str]:
        """
        Get only live conversation messages from this specific turn.
        Used by StateExtractor to avoid processing condensed subturn results.
        """
        return [msg.content for msg in self.messages 
                if msg.message_type == MessageType.LIVE_MESSAGE and 
                   msg.turn_origin == self.turn_id]
    
    def get_all_messages_chronological(self) -> List[str]:
        """
        Get all messages (live + condensed subturns) in chronological order.
        Used by DM context builder for full turn context.
        """
        return [msg.content for msg in self.messages]
    
    # Legacy compatibility methods 
    # #TODO: change this so that the TurnContext takes str message directly
    def add_message(self, message: FormattedGameMessage) -> None:
        """Legacy method - add FormattedGameMessage and convert to live message."""
        self._formatted_messages.append(message)
        # Convert to live message for new system
        self.add_live_message(message.to_agent_input())
    
    def get_turn_context_messages(self) -> List[str]:
        """
        Legacy method - get messages for state extraction.
        Now returns only live messages from current turn.
        """
        return self.get_live_messages_only()
    
    def is_completed(self) -> bool:
        """Check if this turn has been completed."""
        return self.end_time is not None
    
    def to_xml_context(self) -> str:
        """
        Convert this TurnContext to XML format for agent consumption.
        
        Generates the XML structure used by agents with proper nesting and formatting:
        ```xml
        <turn_log>
          <message type="player/dm">content</message>
          <reaction id="..." level="...">
            <action>...</action>
            <resolution>...</resolution>
          </reaction>
        </turn_log>
        ```
        
        Returns:
            XML string wrapped in markdown code fences
        """
        xml_parts = ["```xml", "<turn_log>"]
        
        # Process messages chronologically
        for msg in self.messages:
            element = msg.to_xml_element()
            
            # Add proper indentation
            if msg.message_type == MessageType.LIVE_MESSAGE:
                xml_parts.append(f"  {element}")
            else:
                # For reactions, add with base indentation (element already has internal indentation)
                xml_parts.append(f"  {element}")
        
        xml_parts.extend(["</turn_log>", "```"])
        return "\n".join(xml_parts)


@dataclass
class TurnExtractionContext:
    """
    Context passed to StateExtractor containing isolated turn messages and metadata.
    """
    turn_id: str
    turn_level: int
    turn_messages: List[str]
    active_character: Optional[str] = None
    parent_modifications: List[str] = field(default_factory=list)  # From child turns
    metadata: Dict[str, Any] = field(default_factory=dict)


class TurnManager:
    """
    Manages hierarchical turn tracking with context isolation for safe state extraction.
    
    Separates action resolution (immediate state updates) from turn conclusion (cleanup).
    Key methods:
    - start_turn(): Begin a new turn/sub-turn
    - resolve_action(): Extract and apply state changes during action resolution  
    - end_turn(): Clean turn conclusion with end-of-turn effects only
    - process_end_of_turn_effects(): Handle duration-based effects and cleanup
    
    Turn nesting level is determined by stack depth.
    Applies HistoryManager pattern for message management and filtering.
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
        
        # Turn stack - each entry is a TurnContext
        self.turn_stack: List[TurnContext] = []
        
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
    
    def start_turn(
        self, 
        active_character: Optional[str] = None,
        initiative_order: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a new turn or sub-turn.
        Turn type (turn/sub-turn/etc.) is determined by current stack depth.
        
        Args:
            active_character: Character whose turn it is
            initiative_order: Current initiative order
            metadata: Additional turn metadata
        
        Returns:
            Turn ID for this turn
        """
        self._turn_counter += 1
        #TODO: just the number
        turn_id = f"turn_{self._turn_counter}"
        turn_level = len(self.turn_stack)  # Stack depth determines nesting level
        
        turn_context = TurnContext(
            turn_id=turn_id,
            turn_level=turn_level,
            active_character=active_character,
            initiative_order=initiative_order,
            metadata=metadata or {}
        )
        
        self.turn_stack.append(turn_context)
        
        return turn_id
    
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
        if not self.turn_stack:
            raise ValueError("No active turn to resolve action in")
        
        current_turn = self.turn_stack[-1]
        
        # Add the action context as a live message to the current turn
        current_turn.add_live_message(action_context, current_turn.turn_id)
        
        # Perform state extraction if extractor is available
        state_result = None
        if self.state_extractor:
            state_result = await self._extract_state_changes_from_turn_context(
                current_turn, metadata or {}
            )
        
        return state_result

    async def end_turn(self) -> Dict[str, Any]:
        """
        End the current turn, condense it, and embed in parent turn if applicable.
        
        This method:
        1. Processes end-of-turn effects
        2. Condenses the completed turn into structured action-resolution format
        3. Embeds condensed result in parent turn (if exists)
        4. Removes completed turn from stack
        
        Returns:
            Dictionary with turn completion and condensation results
        """
        if not self.turn_stack:
            raise ValueError("No active turn to end")
        
        # Process any end-of-turn effects first
        end_of_turn_effects = await self.process_end_of_turn_effects()
        
        # Get the current turn to be completed
        completed_turn = self.turn_stack[-1]
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
                if len(self.turn_stack) > 1:  # Has parent
                    parent_turn = self.turn_stack[-2]  # Parent is one level up
                    parent_turn.add_completed_subturn(
                        condensation_result.condensed_summary,
                        completed_turn.turn_id
                    )
                    
            except Exception as e:
                print(f"Turn condensation failed for {completed_turn.turn_id}: {e}")
        
        # Remove completed turn from stack
        self.turn_stack.pop()
        
        # Add to completed turns history
        self.completed_turns.append(completed_turn)
        
        # Clear current messages after processing
        self._current_messages = []
        
        return {
            "turn_id": completed_turn.turn_id,
            "turn_level": completed_turn.turn_level,
            "duration": (completed_turn.end_time - completed_turn.start_time).total_seconds(),
            "message_count": len(completed_turn.messages),
            "end_of_turn_effects": end_of_turn_effects,
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
        if not self.turn_stack:
            return []
        
        current_turn = self.turn_stack[-1]
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
    
    def store_turn_messages(self, messages: List[FormattedGameMessage]) -> None:
        """
        Store FormattedGameMessage objects for the current turn (following HistoryManager pattern).
        
        Args:
            messages: List of FormattedGameMessage objects from current turn
        """
        self._current_messages = messages
        
        # Add messages to current turn context if we have an active turn
        if self.turn_stack:
            current_turn = self.turn_stack[-1]
            for message in messages:
                current_turn.add_message(message)
    
    def get_current_turn_context(self) -> Optional[TurnContext]:
        """Get the current active turn context."""
        return self.turn_stack[-1] if self.turn_stack else None
    
    def get_turn_level(self) -> int:
        """Get current turn nesting level (stack depth)."""
        return len(self.turn_stack)
    
    def is_in_turn(self) -> bool:
        """Check if we're currently in a turn."""
        return len(self.turn_stack) > 0
    
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
        return {
            "active_turns": len(self.turn_stack),
            "current_turn_level": self.get_turn_level(),
            "completed_turns": len(self.completed_turns),
            "total_turns_started": self._turn_counter,
            "current_turn_id": self.turn_stack[-1].turn_id if self.turn_stack else None,
            "turn_stack_depth": len(self.turn_stack)
        }
    
    def get_turn_stack_summary(self) -> List[str]:
        """Get a summary of the current turn stack."""
        return [turn.get_turn_summary() for turn in self.turn_stack]
    
    def clear_turn_history(self) -> None:
        """Clear all turn history and reset counters."""
        self.turn_stack = []
        self.completed_turns = []
        self._current_messages = []
        self._turn_counter = 0


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