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
    - Character name → ID mapping for resolving names in narrative
    - Additional game context if provided
    - Excludes completed subturn results to prevent duplicate extractions
    """

    def __init__(self):
        """Initialize the StateExtractor context builder."""
        pass

    # def build_context(
    #     self,
    #     current_turn: TurnContext,
    #     additional_context: Optional[Dict[str, Any]] = None
    # ) -> str:
    #     """
    #     Build isolated XML context for StateExtractor from current turn only.

    #     Note: This basic method doesn't include character mapping. For production use,
    #     prefer build_context_with_character_map() which provides the name→ID mapping
    #     that agents need for accurate character ID resolution.

    #     Args:
    #         current_turn: The current turn being processed for state extraction
    #         additional_context: Optional additional context (unused here, passed via game_context)

    #     Returns:
    #         XML-formatted context string with current turn unprocessed live messages only
    #     """
    #     if not current_turn:
    #         return "```xml\n<turn_log>\n</turn_log>\n```"

    #     # Get only unprocessed live messages from the current turn
    #     unprocessed_messages = [msg for msg in current_turn.messages
    #                     if msg.is_live_message() and msg.turn_origin == current_turn.turn_id
    #                     and not msg.processed_for_state_extraction]

    #     # Build XML structure with unprocessed messages only
    #     xml_parts = ["```xml", "<turn_log>"]

    #     # Add unprocessed messages as XML elements
    #     if unprocessed_messages:
    #         for msg in unprocessed_messages:
    #             element = msg.to_xml_element()
    #             xml_parts.append(f"  {element}")

    #     xml_parts.extend(["</turn_log>", "```"])
    #     return "\n".join(xml_parts)

    def build_context(
        self,
        current_turn: TurnContext,
        character_map: Dict[str, str],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build XML context with character name→ID mapping for state extraction.

        This is the primary method for building state extraction context.
        Provides the character mapping that agents need to resolve character
        names in narrative to character IDs, wrapped in XML structure.

        Args:
            current_turn: The current turn being processed
            character_map: Name → character_id mapping (e.g., {"Goblin 1": "goblin_1"})
            additional_context: Optional additional game context

        Returns:
            XML-formatted context string with character mapping and turn messages

        Example output:
            ```xml
            <character_mapping>
              <entry name="Tharion Stormwind" id="fighter"/>
              <entry name="Goblin 1" id="goblin_1"/>
            </character_mapping>
            <turn_log>
              <message speaker="DM">Goblin 1 attacks Tharion...</message>
            </turn_log>
            ```
        """
        xml_parts = ["```xml"]

        # Add character mapping as XML
        xml_parts.append("<character_mapping>")
        xml_parts.append("  <!-- Use these mappings to convert character names to character_ids -->")
        for name, char_id in character_map.items():
            xml_parts.append(f'  <entry name="{name}" id="{char_id}"/>')
        xml_parts.append("</character_mapping>")

        # Add additional context if provided
        if additional_context:
            xml_parts.append("<game_context>")
            xml_parts.append(f"  <combat_round>{additional_context.get('combat_round', 'N/A')}</combat_round>")
            xml_parts.append(f"  <active_character>{additional_context.get('active_character', 'N/A')}</active_character>")
            xml_parts.append("</game_context>")

        # Add turn messages as XML
        xml_parts.append("<turn_log>")
        if current_turn:
            # Get only unprocessed live messages from the current turn
            unprocessed_messages = [msg for msg in current_turn.messages
                            if msg.is_live_message() and msg.turn_origin == current_turn.turn_id
                            and not msg.processed_for_state_extraction]

            if unprocessed_messages:
                for msg in unprocessed_messages:
                    element = msg.to_xml_element()
                    xml_parts.append(f"  {element}")
            else:
                xml_parts.append("  <!-- No unprocessed messages -->")
        else:
            xml_parts.append("  <!-- No current turn -->")
        xml_parts.append("</turn_log>")

        xml_parts.append("```")
        return "\n".join(xml_parts)


def create_state_extractor_context_builder() -> StateExtractorContextBuilder:
    """
    Factory function to create a StateExtractor context builder.

    Returns:
        Configured StateExtractorContextBuilder instance
    """
    return StateExtractorContextBuilder()
