"""
Context builder for Gameflow Director that provides full chronological context.

Builds comprehensive context including recent condensed history and current turn stack
with both live messages and completed subturn results. Preserves nested structure
and chronological order for optimal DM narrative generation.
"""

from typing import List, Optional

from ..models.dm_response import DMResponse
from ..memory.turn_manager import TurnManagerSnapshot
from ..models.turn_message import TurnMessage
from .. models.turn_context import TurnContext



class GDContextBuilder:
    """
    Builds comprehensive context for Gameflow Director including all available information.
    
    Provides full chronological context with:
    - Recent condensed turn history
    - Current turn stack with live messages and completed subturn results
    - Proper indentation to show turn hierarchy
    - Chronological order preservation
    """
    
    def __init__(self):
        """Initialize the GM context builder."""
        pass
    
    def build_context(
        self,
        turn_manager_snapshots: TurnManagerSnapshot,
        new_message_xml: Optional[str] = None,
        # recent_history: Optional[List[str]] = None
    ) -> str:
        """
        Build comprehensive GD context from turn stack and recent history.

        Args:
            turn_manager_snapshots: Current turn manager state snapshot
            new_message_xml: Optional new message content in XML format to include
            recent_history: Recent condensed turn history (last few completed turns)

        Returns:
            Formatted context string with full chronological information
        """
        context_parts = []
        completed_turns = turn_manager_snapshots.completed_turns
        #TODO: Objectives for Current Step
        # Need Default Objectives at the start of game session
        context_parts.append(turn_manager_snapshots.current_step_objective)
        
        # Add recent history if available
        # TODO: history summary + recent history
        if completed_turns:
            context_parts.append("<history_turns")
            context_parts.extend(completed_turns[-3:])  # Last 3 completed turns for now
            context_parts.append("</history_turns>")
        
        #Context from current turn.
        context_parts.extend("<current_turn>")
        context_parts.append(self.build_xml_context(turn_manager_snapshots.active_turns_by_level))
        context_parts.extend("</current_turn>")
        
        # Build New Message (if provided as parameter)
        if new_message_xml:
            context_parts.append("<new_message>")
            context_parts.append(new_message_xml)
            context_parts.append("</new_message>")
        
        return "\n".join(context_parts)
    
    def build_xml_context(self, active_turns_by_level: List[TurnContext]) -> str:
        """
        Build XML context for Gameflow Director with nested turn structure.

        Uses each TurnContext's to_xml_context method to build properly nested
        XML with appropriate indentation for each turn level. Excludes the last
        message from the deepest-level turn as it represents the new message.

        Args:
            active_turns_by_level: First TurnContext from each level (provided by snapshot)

        Returns:
            XML string with nested turn/subturn structure and proper indentation
        """
        if not active_turns_by_level:
            return "<turn_log>\n</turn_log>"

        context_parts = []

        for turn_context in active_turns_by_level:
            # Get XML context from the turn (no need to exclude messages since
            # new messages are passed separately as parameters)
            turn_xml = turn_context.to_xml_context(exclude_last=False)
            
            # Apply indentation based on turn level for nested structure
            indent = "  " * turn_context.turn_level
            xml_lines = turn_xml.split('\n')
            
            for line in xml_lines:
                if line.strip():  # Only indent non-empty lines
                    context_parts.append(f"{indent}{line}")
                else:
                    context_parts.append("")
        
        return "\n".join(context_parts)
