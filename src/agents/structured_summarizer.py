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
from ..models.turn_context import TurnContext
from ..context.structured_summarizer_context_builder import create_structured_summarizer_context_builder


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
        self.context_builder = create_structured_summarizer_context_builder()
        
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
            # Prepare the condensation prompt using the context builder
            prompt = self.context_builder.build_prompt(
                turn_context,
                additional_instructions=self._format_additional_context(additional_context)
            )

            # Run the condensation agent
            result = await self.agent.run(prompt)

            # Return the structured result
            return result.output if hasattr(result, 'output') else result

        except Exception as e:
            # Return fallback result on failure
            return StructuredTurnSummary(
                structured_summary=f"<turn id=\"{turn_context.turn_id}\" level=\"{turn_context.turn_level}\">\n"
                                  f"  <action>Failed to condense: {str(e)}</action>\n"
                                  f"  <resolution>Turn processing encountered an error</resolution>\n"
                                  f"</turn>"
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
    
    def _format_additional_context(self, additional_context: Optional[dict] = None) -> Optional[str]:
        """
        Format additional context dictionary into instruction string.

        Args:
            additional_context: Optional additional context dictionary

        Returns:
            Formatted string with additional context, or None if no context provided
        """
        if not additional_context:
            return None

        context_parts = []

        if 'combat_round' in additional_context:
            context_parts.append(f"Combat round: {additional_context['combat_round']}")

        if 'current_initiative' in additional_context:
            context_parts.append(f"Initiative: {additional_context['current_initiative']}")

        # Add any other context keys
        for key, value in additional_context.items():
            if key not in ['combat_round', 'current_initiative']:
                context_parts.append(f"{key}: {value}")

        return "\n".join(context_parts) if context_parts else None


def create_turn_condensation_agent(model_name: str = "gemini-1.5-flash") -> StructuredTurnSummarizer:
    """
    Factory function to create a turn condensation agent.
    
    Args:
        model_name: Gemini model to use for condensation
    
    Returns:
        Configured TurnCondensationAgent instance
    """
    return StructuredTurnSummarizer(model_name=model_name)