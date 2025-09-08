"""
Context builder for Dungeon Master that provides full chronological context.

Builds comprehensive context including recent condensed history and current turn stack
with both live messages and completed subturn results. Preserves nested structure
and chronological order for optimal DM narrative generation.
"""

from typing import List, Optional
from ..models.turn_context import TurnContext


class DMContextBuilder:
    """
    Builds comprehensive context for Dungeon Master including all available information.
    
    Provides full chronological context with:
    - Recent condensed turn history
    - Current turn stack with live messages and completed subturn results
    - Proper indentation to show turn hierarchy
    - Chronological order preservation
    """
    
    def __init__(self):
        """Initialize the DM context builder."""
        pass
    
    def build_context(
        self, 
        turn_stack: List[TurnContext], 
        recent_history: Optional[List[str]] = None
    ) -> str:
        """
        Build comprehensive DM context from turn stack and recent history.
        
        Args:
            turn_stack: Current active turn stack (may be nested)
            recent_history: Recent condensed turn history (last few completed turns)
        
        Returns:
            Formatted context string with full chronological information
        """
        context_parts = []
        
        # Add recent history if available
        # TODO: history summary + recent history
        if recent_history:
            context_parts.append("=== RECENT TURN HISTORY ===")
            context_parts.extend(recent_history[-3:])  # Last 3 completed turns
            context_parts.append("")
        
        # Add current turn stack with full context
        if turn_stack:
            context_parts.append("=== CURRENT TURN STACK ===")
            
            for turn in turn_stack:
                # Add turn header with proper indentation
                indent = "  " * turn.turn_level
                context_parts.append(
                    f"{indent}[Turn {turn.turn_id} - {turn.active_character or 'Unknown'} (Level {turn.turn_level})]"
                )
                
                # Add all messages (live + completed subturns) with indentation
                for message in turn.get_all_messages_chronological():
                    # Split multi-line messages and indent each line
                    message_lines = message.split('\n')
                    for line in message_lines:
                        context_parts.append(f"{indent}{line}")
        else:
            context_parts.append("=== NO ACTIVE TURNS ===")
        
        return "\n".join(context_parts)
    
    def build_context_for_turn_level(
        self,
        turn_stack: List[TurnContext],
        target_level: int,
        recent_history: Optional[List[str]] = None
    ) -> str:
        """
        Build context focused on a specific turn level.
        
        Useful when generating responses for a particular nested turn level
        while maintaining awareness of the broader context.
        
        Args:
            turn_stack: Current active turn stack
            target_level: The turn level to focus on (0=main, 1=subturn, etc.)
            recent_history: Recent condensed turn history
            
        Returns:
            Context string with focus on target level while maintaining hierarchy
        """
        context_parts = []
        
        # Add recent history
        # TODO: history summary + recent history
        if recent_history:
            context_parts.append("=== RECENT TURN HISTORY ===")
            context_parts.extend(recent_history[-2:])  # Less history for focused view
            context_parts.append("")
        
        # Add current turn stack up to target level
        relevant_turns = [turn for turn in turn_stack if turn.turn_level <= target_level]
        
        if relevant_turns:
            context_parts.append(f"=== CURRENT CONTEXT (Focus: Level {target_level}) ===")
            
            for turn in relevant_turns:
                indent = "  " * turn.turn_level
                
                # Highlight the target level
                level_marker = " >>> CURRENT FOCUS <<<" if turn.turn_level == target_level else ""
                context_parts.append(
                    f"{indent}[Turn {turn.turn_id} - {turn.active_character or 'Unknown'} (Level {turn.turn_level})]{level_marker}"
                )
                
                # Add messages with indentation
                for message in turn.get_all_messages_chronological():
                    message_lines = message.split('\n')
                    for line in message_lines:
                        context_parts.append(f"{indent}{line}")
        
        return "\n".join(context_parts)
    
    def get_context_summary(self, turn_stack: List[TurnContext]) -> str:
        """
        Get a brief summary of the current context state.
        
        Args:
            turn_stack: Current active turn stack
            
        Returns:
            Brief summary of current context state
        """
        if not turn_stack:
            return "No active turns"
        
        summary_parts = []
        
        for turn in turn_stack:
            live_messages = len([msg for msg in turn.messages if msg.is_live_message()])
            completed_subturns = len([msg for msg in turn.messages if msg.is_completed_subturn()])
            
            summary_parts.append(
                f"Turn {turn.turn_id} (L{turn.turn_level}): {live_messages} messages, {completed_subturns} subturns"
            )
        
        return " | ".join(summary_parts)
    
    def build_xml_context(self, turn_stack: List[TurnContext]) -> str:
        """
        Build XML context for Dungeon Master with full chronological information.
        
        Provides comprehensive XML context including all turns and subturns
        in chronological order for optimal DM narrative generation.
        
        Args:
            turn_stack: Current active turn stack (may be nested)
            
        Returns:
            XML string wrapped in markdown code fences with full turn context
        """
        if not turn_stack:
            return "```xml\n<turn_log>\n</turn_log>\n```"
        
        # Collect all messages chronologically across all turns
        all_messages = []
        for turn_context in turn_stack:
            all_messages.extend(turn_context.messages)
        
        # Sort by timestamp to ensure chronological order
        all_messages.sort(key=lambda msg: msg.timestamp)
        
        # Build XML structure
        xml_parts = ["```xml", "<turn_log>"]
        
        for msg in all_messages:
            element = msg.to_xml_element()
            
            # Add proper indentation
            if msg.message_type.value == "live_message":
                xml_parts.append(f"  {element}")
            else:
                # For reactions, add with base indentation (element already has internal indentation)
                xml_parts.append(f"  {element}")
        
        xml_parts.extend(["</turn_log>", "```"])
        return "\n".join(xml_parts)

def create_dm_context_builder() -> DMContextBuilder:
    """
    Factory function to create a DM context builder.
    
    Returns:
        Configured DMContextBuilder instance
    """
    return DMContextBuilder()