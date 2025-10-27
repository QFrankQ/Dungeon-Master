"""
Turn condensation agent that creates structured action-resolution summaries.

Analyzes complete turn context (live messages + completed subturn results)
and produces nested action-resolution structure with proper chronological
flow and indentation for embedding in parent turn contexts.
"""

import os
from typing import Optional
from anyio import Path
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from dotenv import load_dotenv
load_dotenv()
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





class StructuredTurnSummarizer:
    """
    Agent that condenses complete turn context into structured action-resolution summaries.
    
    Takes live messages and any completed subturn results and creates a clean,
    nested summary that preserves chronological order and can be embedded
    in parent turn contexts.
    """
    
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        """Initialize the turn condensation agent."""
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.model = GoogleModel(
            model_name, provider=GoogleProvider(api_key=GOOGLE_API_KEY)
        )
        self.agent = Agent(
            self.model,
            name="Turn Condensation Agent",
            instructions=self.get_system_prompt(),
            output_type=StructuredTurnSummary
        )
        
    def get_system_prompt(self):
        # Load DM system prompt from file
        prompts_dir = Path(__file__).parent.parent / "prompts"
        prompt_file = prompts_dir / "structured_turn_summarizer_prompt.txt"

        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            # Fallback prompt if file not found
            return """You are a Structured Turn Summarizer for a D&D game. Generate nested action-resolution summaries in chronological order."""
    
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