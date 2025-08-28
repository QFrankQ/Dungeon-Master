"""
Context builder for StateExtractor that provides isolated current turn context.

Builds context with only live messages from the current turn to prevent
duplicate state extractions while providing sufficient context for accurate
state change identification.
"""

from typing import Optional, Dict, Any
from .turn_manager import TurnContext


class StateExtractorContextBuilder:
    """
    Builds isolated context for StateExtractor focused on current turn only.
    
    Provides context that includes:
    - Only live messages from the current turn being processed
    - Turn metadata (ID, level, active character)
    - Additional game context if provided
    - Excludes completed subturn results to prevent duplicate extractions
    """
    
    def __init__(self):
        """Initialize the StateExtractor context builder."""
        pass
    
    def build_context(
        self, 
        current_turn: TurnContext, 
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build isolated context for StateExtractor from current turn only.
        
        Args:
            current_turn: The current turn being processed for state extraction
            additional_context: Optional additional context (combat round, etc.)
        
        Returns:
            Formatted context string with current turn live messages only
        """
        context_parts = [
            f"=== TURN {current_turn.turn_id} (Level {current_turn.turn_level}) ===",
            f"Active Character: {current_turn.active_character or 'Unknown'}",
            ""
        ]
        
        # Add additional context if provided
        if additional_context:
            context_parts.extend([
                "=== ADDITIONAL GAME CONTEXT ===",
                f"Combat round: {additional_context.get('combat_round', 'N/A')}",
                f"Current initiative: {additional_context.get('current_initiative', 'N/A')}",
                ""
            ])
        
        # Add only live messages from current turn
        live_messages = current_turn.get_live_messages_only()
        
        if live_messages:
            context_parts.extend([
                "=== TURN MESSAGES ===",
                *live_messages
            ])
        else:
            context_parts.append("=== NO MESSAGES IN CURRENT TURN ===")
        
        return "\n".join(context_parts)
    
    def build_context_with_metadata(
        self,
        current_turn: TurnContext,
        turn_metadata: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build context with explicit turn metadata inclusion.
        
        Args:
            current_turn: The current turn being processed
            turn_metadata: Metadata about the turn (from turn_manager context)
            additional_context: Optional additional game context
            
        Returns:
            Formatted context string with metadata and current turn messages
        """
        context_parts = [
            f"=== TURN {current_turn.turn_id} (Level {current_turn.turn_level}) ===",
            f"Active Character: {current_turn.active_character or 'Unknown'}",
            ""
        ]
        
        # Add turn metadata
        if turn_metadata:
            context_parts.extend([
                "=== TURN METADATA ===",
                f"Turn ID: {turn_metadata.get('turn_id', current_turn.turn_id)}",
                f"Turn Level: {turn_metadata.get('turn_level', current_turn.turn_level)}",
                f"Active Character: {turn_metadata.get('active_character', current_turn.active_character)}",
                ""
            ])
        
        # Add additional context if provided
        if additional_context:
            context_parts.extend([
                "=== ADDITIONAL GAME CONTEXT ===",
                f"Combat round: {additional_context.get('combat_round', 'N/A')}",
                f"Current initiative: {additional_context.get('current_initiative', 'N/A')}",
                ""
            ])
        
        # Add only live messages from current turn
        live_messages = current_turn.get_live_messages_only()
        
        if live_messages:
            context_parts.extend([
                "=== TURN MESSAGES ===",
                *live_messages
            ])
        else:
            context_parts.append("=== NO MESSAGES IN CURRENT TURN ===")
        
        return "\n".join(context_parts)
    
    def validate_context_isolation(self, current_turn: TurnContext) -> Dict[str, Any]:
        """
        Validate that the context is properly isolated for state extraction.
        
        Args:
            current_turn: The turn context to validate
            
        Returns:
            Dictionary with validation results and warnings
        """
        validation = {
            "is_isolated": True,
            "warnings": [],
            "live_message_count": 0,
            "completed_subturn_count": 0
        }
        
        live_messages = [msg for msg in current_turn.messages if msg.is_live_message()]
        completed_subturns = [msg for msg in current_turn.messages if msg.is_completed_subturn()]
        
        validation["live_message_count"] = len(live_messages)
        validation["completed_subturn_count"] = len(completed_subturns)
        
        # Check for potential isolation issues
        if completed_subturns:
            validation["warnings"].append(
                f"Turn contains {len(completed_subturns)} completed subturns. "
                "StateExtractor will only see live messages to prevent duplicate extractions."
            )
        
        if not live_messages:
            validation["warnings"].append(
                "Turn contains no live messages. State extraction may return empty results."
            )
            validation["is_isolated"] = False
        
        # Check for cross-turn message origins
        foreign_messages = [msg for msg in live_messages if msg.turn_origin != current_turn.turn_id]
        if foreign_messages:
            validation["warnings"].append(
                f"Found {len(foreign_messages)} live messages with foreign turn origins. "
                "This may indicate improper message attribution."
            )
            validation["is_isolated"] = False
        
        return validation
    
    def get_extraction_summary(self, current_turn: TurnContext) -> str:
        """
        Get a summary of what will be extracted from this turn.
        
        Args:
            current_turn: The turn context being processed
            
        Returns:
            Brief summary of extraction scope
        """
        live_count = len(current_turn.get_live_messages_only())
        subturn_count = len([msg for msg in current_turn.messages if msg.is_completed_subturn()])
        
        return (f"Turn {current_turn.turn_id} (L{current_turn.turn_level}): "
                f"Extracting from {live_count} live messages, "
                f"ignoring {subturn_count} completed subturns")


def create_state_extractor_context_builder() -> StateExtractorContextBuilder:
    """
    Factory function to create a StateExtractor context builder.
    
    Returns:
        Configured StateExtractorContextBuilder instance
    """
    return StateExtractorContextBuilder()