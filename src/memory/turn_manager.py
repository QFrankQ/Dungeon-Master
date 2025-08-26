"""
Turn management system for D&D combat with hierarchical turn/sub-turn tracking.
Provides context isolation for safe state extraction and prevents duplicate updates.
"""

from typing import List, Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from ..models.formatted_game_message import FormattedGameMessage

# Optional imports for state extraction and message formatting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..services.message_formatter import MessageFormatter
    from ..agents.state_extractor import StateExtractorAgent
    from ..agents.state_updates import StateExtractionResult


@dataclass 
class TurnContext:
    """
    Context for a single turn or sub-turn in the turn stack.
    Contains all messages and metadata for this specific turn scope.
    """
    turn_id: str
    turn_level: int  # Stack depth (0=main turn, 1=sub-turn, 2=sub-sub-turn, etc.)
    active_character: Optional[str] = None
    initiative_order: Optional[List[str]] = None
    
    # Message management following HistoryManager pattern
    messages: List[FormattedGameMessage] = field(default_factory=list)
    
    # Turn metadata
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, message: FormattedGameMessage) -> None:
        """Add a message to this turn's context."""
        self.messages.append(message)
    
    def get_turn_context_messages(self) -> List[str]:
        """
        Get all messages from this turn context formatted for state extraction.
        Uses HistoryManager pattern - includes ALL turn content, not just player actions.
        """
        context_messages = []
        
        for message in self.messages:
            # For state extraction, we want rich context including character stats
            context_messages.append(message.to_agent_input())
        
        return context_messages
    
    def get_turn_summary(self) -> str:
        """Get a brief summary of what happened in this turn."""
        if not self.messages:
            return f"Turn {self.turn_id} (Level {self.turn_level}): No messages"
        
        message_count = len(self.messages)
        character_names = list(set(msg.character_name for msg in self.messages))
        
        return (f"Turn {self.turn_id} (Level {self.turn_level}): "
                f"{message_count} messages from {', '.join(character_names)}")
    
    def is_completed(self) -> bool:
        """Check if this turn has been completed."""
        return self.end_time is not None


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
    
    Uses unified start_turn()/end_turn() methods for all turn types.
    Turn nesting level is determined by stack depth.
    Applies HistoryManager pattern for message management and filtering.
    """
    
    def __init__(self, state_extractor: Optional[Any] = None):
        """
        Initialize the turn manager.
        
        Args:
            state_extractor: Optional state extractor for automatic processing
        """
        self.state_extractor = state_extractor
        
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
    
    async def end_turn(self) -> Optional[Any]:
        """
        End the current turn and perform state extraction.
        
        Returns:
            StateExtractionResult if state_extractor is available, None otherwise
        """
        if not self.turn_stack:
            raise ValueError("No active turn to end")
        
        # Pop the current turn from stack
        completed_turn = self.turn_stack.pop()
        completed_turn.end_time = datetime.now()
        
        # Add to completed turns history
        self.completed_turns.append(completed_turn)
        
        # Perform state extraction if extractor is available
        state_result = None
        if self.state_extractor:
            extraction_context = self._prepare_extraction_context(completed_turn)
            state_result = await self._extract_state_changes(extraction_context)
            
            # If there are modifications from this turn and we have a parent turn,
            # add them to the parent turn's context
            if state_result and hasattr(state_result, 'modifications') and self.turn_stack:
                parent_turn = self.turn_stack[-1]
                if not hasattr(parent_turn, 'child_modifications'):
                    parent_turn.child_modifications = []
                parent_turn.child_modifications.extend(getattr(state_result, 'modifications', []))
        
        # Clear current messages after processing
        self._current_messages = []
        
        return state_result
    
    def end_turn_sync(self) -> Optional[Any]:
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
            
            # Use existing StateExtractor method
            result = await self.state_extractor.extract_state_changes(
                narrative=full_context,
                context={
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


def create_turn_manager(state_extractor: Optional[Any] = None) -> TurnManager:
    """
    Factory function to create a configured turn manager.
    
    Args:
        state_extractor: Optional state extractor for automatic processing
    
    Returns:
        Configured TurnManager instance
    """
    return TurnManager(state_extractor=state_extractor)