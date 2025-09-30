"""
Context builder for Dungeon Master that provides full chronological context.

Builds comprehensive context including recent condensed history and current turn stack
with both live messages and completed subturn results. Preserves nested structure
and chronological order for optimal DM narrative generation.
"""

from typing import List, Optional, Dict, Any

from ..memory.turn_manager import TurnManagerSnapshot
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
        turn_manager_snapshots: TurnManagerSnapshot,
        new_message_entries: Optional[List[Dict[str, Any]]] = None,
        # recent_history: Optional[List[str]] = None
    ) -> str:
        """
        Build comprehensive DM context from turn stack and recent history.

        Args:
            turn_manager_snapshots: Current turn manager state snapshot
            new_message_entries: Optional list of message entry dictionaries with keys:
                - 'player_message': ChatMessage object
                - 'player_id': Player's ID
                - 'character_id': Character name/ID
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
        
        #TODO:
        # Context about current relevant Game State
        
        #TODO:
        # Rules relevant to the current turn
        
        # Build New Messages (if provided as parameter)
        if new_message_entries:
            context_parts.append("<new_messages>")
            for message_entry in new_message_entries:
                xml_message = self._convert_message_entry_to_xml(message_entry)
                context_parts.append(xml_message)
            context_parts.append("</new_messages>")

        return "\n".join(context_parts)

    def _convert_message_entry_to_xml(self, message_entry: Dict[str, Any]) -> str:
        """
        Convert a message entry dictionary to XML format.

        Args:
            message_entry: Dictionary containing:
                - 'player_message': ChatMessage object
                - 'player_id': Player's ID
                - 'character_id': Character name/ID

        Returns:
            XML formatted string for the message
        """
        player_message = message_entry['player_message']
        character_name = message_entry['character_id']

        # Format as XML message with character context
        return f'<message speaker="{character_name}">{player_message.text}</message>'
    
    def build_xml_context(self, active_turns_by_level: List[TurnContext]) -> str:
        """
        Build XML context for Dungeon Master with nested turn structure.

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
