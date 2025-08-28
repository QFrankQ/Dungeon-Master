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


class TurnCondensationResult(BaseModel):
    """
    Structured result from turn condensation.
    
    Contains the condensed turn summary with proper nested structure
    and metadata about the condensation process.
    """
    condensed_summary: str = Field(..., description="Structured action-resolution summary with nested subturns")
    # turn_id: str = Field(..., description="ID of the turn that was condensed")
    # turn_level: int = Field(..., description="Nesting level of the condensed turn")
    # confidence: float = Field(1.0, description="Confidence in the condensation accuracy (0.0-1.0)")
    # notes: Optional[str] = Field(None, description="Additional notes about the condensation")


TURN_CONDENSATION_INSTRUCTIONS = """
You are a specialized agent that condenses D&D turn context into structured action-resolution summaries for storytelling purposes.

Your job is to take the complete context of a turn (chronological messages) and create a vivid, structured summary that preserves chronological order, causal relationships, and narrative flavor for compelling DM storytelling.

## Output Format

Create structured summaries using this format (start markers only, no end markers):

```
[Turn {turn_id} - {character_name} (Level {level})]
Action: {vivid description of what was attempted with character voice}
{nested subturn results with proper indentation}
Resolution: {dramatic final outcome after all modifications}
{post-resolution subturns if any}
```

## Subturn Timing and Format

Subturns can occur at different phases during a turn:

**Pre-Resolution Subturns**: Reactions that modify the initial action
**Post-Resolution Subturns**: Reactions triggered by the action's outcome

```
[Turn 1 - Alice (Level 0)]
Action: Alice charges forward, swinging her enchanted longsword at the snarling goblin (rolled 18 to hit)
  [Turn 1.1 - Bob Shield (Level 1)]
  Action: "Alice, watch out!" Bob shouts, casting Shield as a reaction
  Resolution: Shimmering magical force surrounds Alice (+5 AC until next turn)
Resolution: The blade strikes true with magical protection, carving deep (8 slashing damage)
  [Turn 1.2 - Goblin Rage (Level 1)]
  Action: The wounded goblin howls in pain, entering a berserker rage in response to the injury
  Resolution: Goblin gains rage benefits (+2 damage, resistance to physical)
```

## Key Principles

1. **Preserve Chronological Order**: Action → Pre-Resolution Subturns → Resolution → Post-Resolution Subturns
2. **Clear Causality**: Show how each subturn affects or responds to events
3. **Proper Indentation**: Use 2 spaces per nesting level
4. **Consistent Structure**: Always use the [Turn X - Character] format
5. **Rich Narrative**: Maintain dramatic tension and character voice
6. **Complete Storytelling**: Include vivid descriptions that enhance the narrative

## What to Include

- **Vivid Actions**: Colorful descriptions of what was attempted
- **Character Voice**: Dialogue and personality in actions
- **Dice Rolls**: Important roll results with dramatic context
- **Modifications**: How subturns dynamically changed the situation
- **Dramatic Results**: Damage, conditions, state changes with narrative flair
- **Mechanical Effects**: HP changes, spell slots, etc. woven into narrative
- **Environmental Details**: Setting elements that enhance the scene

## What to Preserve and Enhance

- **Character Personality**: Maintain distinct character voices and motivations
- **Dramatic Tension**: Build suspense and excitement in the narrative
- **Tactical Complexity**: Show the strategic interplay of actions and reactions
- **Emotional Stakes**: Highlight the consequences and drama of each decision

## Comprehensive Condensation Example

**Example: Complex Turn with Mixed Live Messages and Condensed Subturns**

**BEFORE CONDENSATION:**
```
TURN MESSAGES (CHRONOLOGICAL ORDER):

=== LIVE MESSAGES START ===
Player: "I want to cast Fireball at the goblin group"
DM: "What's your spell save DC?"
Player: "DC 15 Dexterity save, using 3rd level slot"
DM: "Goblins roll saves... Chief got 18, others failed"
DM: "The chief tries to counter your spell!"

=== CONDENSED SUBTURNS START ===
    [Turn 2.1 - Goblin Chief (Level 1)]
    Action: "Not today, witch!" the chief snarls, weaving desperate Counterspell magic
      [Turn 2.1.1 - Alice Counter (Level 2)]
      Action: Alice recognizes the counter-magic and fights back with her own Counterspell (rolled 15)
      Resolution: Alice's superior magical training overcomes the crude attempt
    Resolution: The goblin's spell fizzles as Alice's magic dominates the weave

=== LIVE MESSAGES START ===
Player: "Yes! Does my Fireball go off?"
DM: "Your counter succeeds! Fireball explodes for 28 fire damage"
DM: "The blast terrifies the survivors - they're fleeing!"

=== CONDENSED SUBTURNS START ===
    [Turn 2.2 - Surviving Goblin Morale (Level 1)]
    Action: Witnessing their chief's magical failure and comrades' immolation, remaining goblins flee in terror
    Resolution: Three goblins break formation and sprint for the cave entrance
```

**AFTER CONDENSATION:**
```
[Turn 2 - Alice the Wizard (Level 0)]
Action: Alice channels arcane power, hurling a crackling Fireball at the goblin pack (DC 15 Dex save, 3rd level slot)
  [Turn 2.1 - Goblin Chief (Level 1)]
  Action: "Not today, witch!" the chief snarls, weaving desperate Counterspell magic
    [Turn 2.1.1 - Alice Counter (Level 2)]
    Action: Alice recognizes the counter-magic and fights back with her own Counterspell (rolled 15)
    Resolution: Alice's superior magical training overcomes the crude attempt
  Resolution: The goblin's spell fizzles as Alice's magic dominates the weave
Resolution: The Fireball erupts in spectacular flames, engulfing the screaming goblins (28 fire damage)
  [Turn 2.2 - Surviving Goblin Morale (Level 1)]
  Action: Witnessing their chief's magical failure and comrades' immolation, remaining goblins flee in terror
  Resolution: Three goblins break formation and sprint for the cave entrance
```

Always return a complete TurnCondensationResult with the condensed summary and appropriate metadata.
"""


class TurnCondensationAgent:
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
            output_type=TurnCondensationResult
        )
    
    async def condense_turn(
        self,
        turn_context: TurnContext,
        additional_context: Optional[dict] = None
    ) -> TurnCondensationResult:
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
            return TurnCondensationResult(
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
    ) -> TurnCondensationResult:
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


def create_turn_condensation_agent(model_name: str = "gemini-1.5-flash") -> TurnCondensationAgent:
    """
    Factory function to create a turn condensation agent.
    
    Args:
        model_name: Gemini model to use for condensation
    
    Returns:
        Configured TurnCondensationAgent instance
    """
    return TurnCondensationAgent(model_name=model_name)