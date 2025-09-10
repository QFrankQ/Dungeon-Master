"""
Turn condensation agent that creates structured action-resolution summaries.

Analyzes complete turn context (live messages + completed subturn results)
and produces nested action-resolution structure with proper chronological
flow and indentation for embedding in parent turn contexts.
"""

from typing import Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
import google.genai as genai

from ..memory.turn_manager import TurnContext


class StructuredTurnSummary(BaseModel):
    """
    Structured result from turn condensation.
    
    Contains the condensed turn summary with proper nested structure
    and metadata about the condensation process.
    """
    structured_summary: str = Field(..., description="Structured action-resolution summary with nested subturns")
    # turn_id: str = Field(..., description="ID of the turn that was condensed")
    # turn_level: int = Field(..., description="Nesting level of the condensed turn")
    # confidence: float = Field(1.0, description="Confidence in the condensation accuracy (0.0-1.0)")
    # notes: Optional[str] = Field(None, description="Additional notes about the condensation")


TURN_CONDENSATION_INSTRUCTIONS = """
You are a specialized agent that condenses D&D turn context into a single, structured XML summary. Your task is to act as a data processor and a narrator, unifying disjointed chat messages and pre-processed events into a compelling, chronological narrative.

## I. Input Format

You will receive a single, chronological XML log of a complete turn, enclosed within a `<turn_log>` tag. This log contains two types of elements:

1.  **<message> tags**: Raw, chronological chat messages from the game (e.g., Player actions, DM descriptions, dice rolls). Your job is to condense these into a narrative.
2.  **<reaction> tags**: Pre-processed, structured events (subturns) that should not be re-condensed. You must integrate these directly into the final output.

## II. Output Format

Your final output must be a single, complete XML block, enclosed in a `<turn>` tag.

-   **Root Tag**: `<turn id="{turn_id}" character="{character_name}" level="{level}">`
-   **Structure**: The narrative must follow this strict chronological order:
    1.  Main `<action>` (from player messages)
    2.  Pre-Resolution `<reaction>` elements (from input)
    3.  Main `<resolution>` (the final outcome)
    4.  Post-Resolution `<reaction>` elements (from input)

## III. Core Principles

1.  **Unification**: Condense all `<message>` elements into a single, cohesive narrative.
2.  **Preservation**: Integrate all `<reaction>` elements from the input directly into the output without modification or re-summarization.
3.  **Narrative Richness**: Weave in vivid descriptions, character voice, and dice rolls from the `<message>` tags to create a compelling story.
4.  **Causality**: The `<reaction>` elements must be placed correctly in the timeline to show how they affect or are caused by the main action.
5.  **Attribute Extraction**: Infer the `id`, `character`, and `level` for the root `<turn>` tag from the input messages. The `id` should be the first number in the chronological sequence (e.g., "2" for a turn starting with `id="2.1"`).

## IV. Comprehensive Example

**BEFORE CONDENSATION (Input Log):**
```xml
<turn_log>
  <message type="player">I want to cast Fireball at the goblin group</message>
  <message type="dm">What's your spell save DC?</message>
  <message type="player">DC 15 Dexterity save, using 3rd level slot</message>
  <message type="dm">Goblins roll saves... Chief got 18, others failed</message>
  <message type="dm">The chief tries to counter your spell!</message>
  
  <reaction id="2.1" character="Goblin Chief" level="1">
    <action>"Not today, witch!" the chief snarls, weaving desperate Counterspell magic</action>
    <reaction id="2.1.1" character="Alice" level="2">
      <action>Alice recognizes the counter-magic and fights back with her own Counterspell (rolled 15)</action>
      <resolution>Alice's superior magical training overcomes the crude attempt</resolution>
    </reaction>
    <resolution>The goblin's spell fizzles as Alice's magic dominates the weave</resolution>
  </reaction>
  
  <message type="player">Yes! Does my Fireball go off?</message>
  <message type="dm">Your counter succeeds! Fireball explodes for 28 fire damage</message>
  <message type="dm">The blast terrifies the survivors - they're fleeing!</message>

  <reaction id="2.2" character="Surviving Goblins" level="1">
    <action>Witnessing their chief's magical failure and comrades' immolation, remaining goblins flee in terror</action>
    <resolution>Three goblins break formation and sprint for the cave entrance</resolution>
  </reaction>
</turn_log>
```

**AFTER CONDENSATION (Your Output):**
```xml
<turn id="2" character="Alice the Wizard" level="0">
  <action>Alice channels arcane power, hurling a crackling Fireball at the goblin pack (DC 15 Dex save, 3rd level slot)</action>
  <reaction id="2.1" character="Goblin Chief" level="1">
    <action>"Not today, witch!" the chief snarls, weaving desperate Counterspell magic</action>
    <reaction id="2.1.1" character="Alice" level="2">
      <action>Alice recognizes the counter-magic and fights back with her own Counterspell (rolled 15)</action>
      <resolution>Alice's superior magical training overcomes the crude attempt</resolution>
    </reaction>
    <resolution>The goblin's spell fizzles as Alice's magic dominates the weave</resolution>
  </reaction>
  <resolution>The Fireball erupts in spectacular flames, engulfing the screaming goblins (28 fire damage)</resolution>
  <reaction id="2.2" character="Surviving Goblins" level="1">
    <action>Witnessing their chief's magical failure and comrades' immolation, remaining goblins flee in terror</action>
    <resolution>Three goblins break formation and sprint for the cave entrance</resolution>
  </reaction>
</turn>
```
"""


class StructuredTurnSummarizer:
    """
    Agent that condenses complete turn context into structured action-resolution summaries.
    
    Takes live messages and any completed subturn results and creates a clean,
    nested summary that preserves chronological order and can be embedded
    in parent turn contexts.
    """
    
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        """Initialize the turn condensation agent."""
        self.model = genai.GenerativeModel(model_name)
        self.agent = Agent(
            self.model,
            name="Turn Condensation Agent",
            instructions=TURN_CONDENSATION_INSTRUCTIONS,
            output_type=StructuredTurnSummary
        )
    
    async def condense_turn(
        self,
        turn_context: TurnContext,
        additional_context: Optional[dict] = None
    ) -> StructuredTurnSummary:
        """
        Condense a complete turn context into structured summary.
        
        Args:
            turn_context: The complete turn context to condense
            additional_context: Optional additional context (combat round, initiative, etc.)
        
        Returns:
            TurnCondensationResult with structured summary
        """
        try:
            # Prepare the condensation prompt using chronological ordering
            prompt = self._prepare_condensation_prompt(
                turn_context, additional_context
            )
            
            # Run the condensation agent
            result = await self.agent.run(prompt)
            
            # Return the structured result
            return result.output if hasattr(result, 'output') else result
            
        except Exception as e:
            # Return fallback result on failure
            return StructuredTurnSummary(
                condensed_summary=f"[Turn {turn_context.turn_id} - {turn_context.active_character or 'Unknown'} (Level {turn_context.turn_level})]\nFailed to condense: {str(e)}\n[Turn {turn_context.turn_id} End]",
                turn_id=turn_context.turn_id,
                turn_level=turn_context.turn_level,
                confidence=0.0,
                notes=f"Condensation failed: {str(e)}"
            )
    
    def condense_turn_sync(
        self,
        turn_context: TurnContext,
        additional_context: Optional[dict] = None
    ) -> StructuredTurnSummary:
        """Synchronous version of condense_turn."""
        import asyncio
        return asyncio.run(
            self.condense_turn(turn_context, additional_context)
        )
    
    def _prepare_condensation_prompt(
        self,
        turn_context: TurnContext,
        additional_context: Optional[dict] = None
    ) -> str:
        """
        Prepare the condensation prompt for the agent using chronological message ordering.
        
        Args:
            turn_context: The complete turn context to be condensed
            additional_context: Optional additional context
        
        Returns:
            Formatted prompt string for the condensation agent with chronological ordering
        """
        prompt_parts = [
            f"Condense the following turn context into a structured action-resolution summary:",
            "",
            f"TURN INFO:",
            f"Turn ID: {turn_context.turn_id}",
            f"Turn Level: {turn_context.turn_level}",
            f"Active Character: {turn_context.active_character or 'Unknown'}",
            ""
        ]
        
        # Add additional context if provided
        if additional_context:
            prompt_parts.extend([
                "ADDITIONAL CONTEXT:",
                f"Combat round: {additional_context.get('combat_round', 'N/A')}",
                f"Initiative: {additional_context.get('current_initiative', 'N/A')}",
                ""
            ])
        
        # Add messages in chronological order with visual distinction markers
        all_messages = turn_context.get_all_messages_chronological()
        if all_messages:
            prompt_parts.extend([
                "TURN MESSAGES (CHRONOLOGICAL ORDER):",
                ""
            ])
            
            current_section = None
            for message in all_messages:
                # Find the corresponding TurnMessage object to check its type
                message_obj = next((m for m in turn_context.messages if m.content == message), None)
                
                if message_obj and message_obj.is_live_message():
                    # Switch to live messages section if needed
                    if current_section != "live":
                        if current_section is not None:
                            prompt_parts.append("")  # Add spacing between sections
                        prompt_parts.append("=== LIVE MESSAGES START ===")
                        current_section = "live"
                    prompt_parts.append(message)
                    
                elif message_obj and message_obj.is_completed_subturn():
                    # Switch to condensed subturns section if needed
                    if current_section != "condensed":
                        if current_section is not None:
                            prompt_parts.append("")  # Add spacing between sections
                        prompt_parts.append("=== CONDENSED SUBTURNS START ===")
                        current_section = "condensed"
                    # Add with 4-space indentation for visual distinction
                    for line in message.split('\n'):
                        prompt_parts.append(f"    {line}")
                
            prompt_parts.append("")  # Final spacing after messages
        else:
            prompt_parts.extend([
                "TURN MESSAGES:",
                "No messages in this turn",
                ""
            ])
        
        prompt_parts.extend([
            "Create a structured summary following the format guidelines.",
            "Preserve chronological order and narrative flavor while capturing mechanical significance.",
            "Use proper indentation (2 spaces per level) for nested subturns.",
            "Maintain dramatic tension and character voice in the condensed narrative."
        ])
        
        return "\n".join(prompt_parts)


def create_turn_condensation_agent(model_name: str = "gemini-1.5-flash") -> StructuredTurnSummarizer:
    """
    Factory function to create a turn condensation agent.
    
    Args:
        model_name: Gemini model to use for condensation
    
    Returns:
        Configured TurnCondensationAgent instance
    """
    return StructuredTurnSummarizer(model_name=model_name)