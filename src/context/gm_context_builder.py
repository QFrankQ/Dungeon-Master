"""
Context builder for Dungeon Master that provides full chronological context.

Builds comprehensive context including recent condensed history and current turn stack
with both live messages and completed subturn results. Preserves nested structure
and chronological order for optimal DM narrative generation.
"""

from typing import List, Optional

from ..models.dm_response import DMResponse
from ..memory.turn_manager import TurnManagerSnapshot
from ..models.turn_message import TurnMessage
from .. models.turn_context import TurnContext



class GMContextBuilder:
    """
    Builds comprehensive context for Dungeon Master including all available information.
    
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
        new_message: [TurnMessage| DMResponse],
        turn_manager_snapshots: TurnManagerSnapshot,
        # recent_history: Optional[List[str]] = None
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
        turn_stack = turn_manager_snapshots.turn_stack
        completed_turns = turn_manager_snapshots.completed_turns
        #TODO: Objectives for Current Step 
        # Need Default Objectives at the start of game session
        context_parts.append(turn_stack[-1].get_current_step_objective())
        
        # Add recent history if available
        # TODO: history summary + recent history
        if completed_turns:
            context_parts.append("<history_turns")
            context_parts.extend(completed_turns[-3:])  # Last 3 completed turns for now
            context_parts.append("</history_turns>")
        
        #Context from current turn.
        context_parts.append(self.build_xml_context(turn_stack))
        
        # Build New Message
        #TODO: either new Turn Message or new DM Response
        context_parts.append("<new_message>")
        context_parts.append(new_message.to_xml_element())
        context_parts.append("</new_message>")
        
        return "\n".join(context_parts)
    
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
