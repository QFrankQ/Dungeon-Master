"""
Context builder for StateExtractor that provides isolated current turn context.

Builds context with only live messages from the current turn to prevent
duplicate state extractions while providing sufficient context for accurate
state change identification.
"""

from typing import Optional, Dict, Any
from ..models.turn_context import TurnContext


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
        Build isolated XML context for StateExtractor from current turn only.

        Note: additional_context metadata is passed separately via game_context parameter
        to the state extractor, so this method focuses purely on message XML structure.

        Args:
            current_turn: The current turn being processed for state extraction
            additional_context: Optional additional context (unused here, passed via game_context)

        Returns:
            XML-formatted context string with current turn unprocessed live messages only
        """
        if not current_turn:
            return "```xml\n<turn_log>\n</turn_log>\n```"

        # Get only unprocessed live messages from the current turn
        unprocessed_messages = [msg for msg in current_turn.messages
                        if msg.is_live_message() and msg.turn_origin == current_turn.turn_id
                        and not msg.processed_for_state_extraction]

        # Build XML structure with unprocessed messages only
        # Metadata is handled separately via game_context in state extractor
        xml_parts = ["```xml", "<turn_log>"]

        # Add unprocessed messages as XML elements
        if unprocessed_messages:
            for msg in unprocessed_messages:
                element = msg.to_xml_element()
                xml_parts.append(f"  {element}")

        xml_parts.extend(["</turn_log>", "```"])
        return "\n".join(xml_parts)
    
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

        # Add only unprocessed live messages from current turn
        unprocessed_messages = current_turn.get_unprocessed_live_messages()

        if unprocessed_messages:
            context_parts.extend([
                "=== TURN MESSAGES ===",
                *unprocessed_messages
            ])
        else:
            context_parts.append("=== NO UNPROCESSED MESSAGES IN CURRENT TURN ===")

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
            "unprocessed_message_count": 0,
            "completed_subturn_count": 0
        }

        live_messages = [msg for msg in current_turn.messages if msg.is_live_message()]
        unprocessed_messages = current_turn.get_unprocessed_live_messages()
        completed_subturns = [msg for msg in current_turn.messages if msg.is_completed_subturn()]

        validation["live_message_count"] = len(live_messages)
        validation["unprocessed_message_count"] = len(unprocessed_messages)
        validation["completed_subturn_count"] = len(completed_subturns)

        # Check for potential isolation issues
        if completed_subturns:
            validation["warnings"].append(
                f"Turn contains {len(completed_subturns)} completed subturns. "
                "StateExtractor will only see live messages to prevent duplicate extractions."
            )

        if not unprocessed_messages:
            validation["warnings"].append(
                "Turn contains no unprocessed messages. State extraction may return empty results."
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
    
    def build_xml_context(self, current_turn: TurnContext) -> str:
        """
        Build XML context for StateExtractor with isolated current turn context.

        Provides XML context containing only unprocessed live messages from the current turn
        to prevent duplicate state extractions while maintaining proper context
        for accurate state change identification.

        Args:
            current_turn: The current turn being processed for state extraction

        Returns:
            XML string wrapped in markdown code fences with current turn context only
        """
        if not current_turn:
            return "```xml\n<turn_log>\n</turn_log>\n```"

        # Get only unprocessed live messages from the current turn (excludes completed subturns and processed messages)
        unprocessed_messages = [msg for msg in current_turn.messages
                        if msg.is_live_message() and msg.turn_origin == current_turn.turn_id
                        and not msg.processed_for_state_extraction]

        if not unprocessed_messages:
            return "```xml\n<turn_log>\n</turn_log>\n```"

        # Build XML structure with only unprocessed live messages
        xml_parts = ["```xml", "<turn_log>"]

        for msg in unprocessed_messages:
            element = msg.to_xml_element()
            xml_parts.append(f"  {element}")

        xml_parts.extend(["</turn_log>", "```"])
        return "\n".join(xml_parts)
    
    def build_xml_context_from_stack(self, turn_stack: list) -> str:
        """
        Build XML context from turn stack, focusing on current turn only.
        
        Extracts the current (top) turn from the stack and builds isolated
        XML context for state extraction.
        
        Args:
            turn_stack: List of TurnContext objects (stack format)
            
        Returns:
            XML string with current turn context only
        """
        if not turn_stack:
            return "```xml\n<turn_log>\n</turn_log>\n```"
        
        # Get current (top) turn from stack
        current_turn = turn_stack[-1]
        return self.build_xml_context(current_turn)


def create_state_extractor_context_builder() -> StateExtractorContextBuilder:
    """
    Factory function to create a StateExtractor context builder.
    
    Returns:
        Configured StateExtractorContextBuilder instance
    """
    return StateExtractorContextBuilder()