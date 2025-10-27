"""
Context builder for Structured Turn Summarizer.

Builds XML-formatted turn logs containing live messages and completed subturn summaries
for the Structured Turn Summarizer agent.
"""

from typing import Optional
from ..models.turn_context import TurnContext
from ..models.turn_message import MessageType, TurnMessage, MessageGroup


class StructuredSummarizerContextBuilder:
    """
    Builds XML context for the Structured Turn Summarizer agent.

    The summarizer receives:
    - Live messages from the active turn (raw conversation as <message> tags)
    - Completed subturn summaries (already structured as <reaction> tags)

    Context builder creates INPUT in this format:
    ```xml
    <turn_log>
      <message speaker="player">I cast Fireball</message>
      <message speaker="dm">The goblin chief counters!</message>
      <reaction id="2.1" level="1">
        <action>The chief snarls and casts Counterspell</action>
        <resolution>The spell fizzles out</resolution>
      </reaction>
      <message speaker="player">My Fireball explodes!</message>
      <message speaker="dm">Roll damage</message>
    </turn_log>
    ```

    The summarizer then condenses this into OUTPUT:
    ```xml
    <turn id="2" character="Alice" level="0">
      <action>Alice casts Fireball at the goblin group</action>
      <reaction id="2.1" level="1">
        <action>The chief snarls and casts Counterspell</action>
        <resolution>The spell fizzles out</resolution>
      </reaction>
      <resolution>Fireball explodes, dealing massive damage</resolution>
    </turn>
    ```

    Note: The builder creates the INPUT, not the OUTPUT. The agent produces the condensed turn.
    """

    def build_context(
        self,
        turn_context: TurnContext,
        include_metadata: bool = True
    ) -> str:
        """
        Build XML context for the Structured Turn Summarizer.

        Args:
            turn_context: The active turn context to build context from
            include_metadata: Whether to include turn metadata as XML comments

        Returns:
            XML string wrapped in <turn_log> tag with chronological messages and reactions
        """
        xml_parts = []

        # Add metadata comment if requested
        if include_metadata:
            xml_parts.extend([
                f"<!-- Turn ID: {turn_context.turn_id} -->",
                f"<!-- Turn Level: {turn_context.turn_level} -->",
                f"<!-- Active Character: {turn_context.active_character or 'Unknown'} -->",
                ""
            ])

        # Opening tag
        xml_parts.append("<turn_log>")

        # Process all messages chronologically
        # The dataclass methods handle indentation automatically
        for item in turn_context.messages:
            if isinstance(item, MessageGroup):
                # Process each message in the group
                for msg in item.messages:
                    xml_element = msg.to_xml_element(base_indent=2)
                    xml_parts.append(xml_element)
            elif isinstance(item, TurnMessage):
                xml_element = item.to_xml_element(base_indent=2)
                xml_parts.append(xml_element)

        # Closing tag
        xml_parts.append("</turn_log>")

        return "\n".join(xml_parts)

    def build_prompt(
        self,
        turn_context: TurnContext,
        additional_instructions: Optional[str] = None
    ) -> str:
        """
        Build complete prompt for the Structured Turn Summarizer including context and instructions.

        Args:
            turn_context: The active turn context to condense
            additional_instructions: Optional additional instructions for the summarizer

        Returns:
            Complete prompt string with context and instructions
        """
        prompt_parts = [
            "Condense the following turn into a structured action-resolution summary.",
            "",
            "INPUT:",
            self.build_context(turn_context, include_metadata=False),
            "",
            "TURN METADATA:",
            f"- Turn ID: {turn_context.turn_id}",
            f"- Turn Level: {turn_context.turn_level}",
            f"- Active Character: {turn_context.active_character or 'Unknown'}",
        ]

        if additional_instructions:
            prompt_parts.extend([
                "",
                "ADDITIONAL INSTRUCTIONS:",
                additional_instructions
            ])

        prompt_parts.extend([
            "",
            "Provide your output as a structured <turn> element following the format guidelines.",
            "Preserve all <reaction> elements from the input exactly as they appear.",
            "Condense the <message> elements into narrative action/resolution structure.",
        ])

        return "\n".join(prompt_parts)


def create_structured_summarizer_context_builder() -> StructuredSummarizerContextBuilder:
    """
    Factory function to create a Structured Summarizer context builder.

    Returns:
        Configured StructuredSummarizerContextBuilder instance
    """
    return StructuredSummarizerContextBuilder()
