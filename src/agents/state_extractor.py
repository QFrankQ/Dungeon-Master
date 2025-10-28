"""
State extraction agent that analyzes DM narrative responses and extracts state changes.

DEPRECATED: Use StateExtractionOrchestrator instead for multi-agent extraction.
"""

from typing import Optional
import warnings
from pydantic_ai import Agent
import google.genai as genai

from ..models.state_updates import StateExtractionResult
from .prompts import STATE_EXTRACTOR_INSTRUCTIONS


class StateExtractorAgent:
    """
    Agent that analyzes DM narrative text and extracts structured state changes.

    DEPRECATED: This single-agent extractor is kept for backward compatibility only.
    New code should use StateExtractionOrchestrator instead for better reliability
    and maintainability with specialized agents.

    This agent reads the DM's narrative response and identifies what character
    states need to be updated (HP changes, conditions, inventory, etc.) without
    actually making the changes.
    """

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        """
        Initialize the state extraction agent.

        DEPRECATED: Use create_state_extraction_orchestrator() instead.
        """
        warnings.warn(
            "StateExtractorAgent is deprecated. Use StateExtractionOrchestrator instead "
            "for multi-agent extraction with better reliability.",
            DeprecationWarning,
            stacklevel=2
        )
        self.model = genai.GenerativeModel(model_name)
        self.agent = Agent(
            self.model,
            name="State Extractor",
            instructions=STATE_EXTRACTOR_INSTRUCTIONS,
            output_type=StateExtractionResult
        )
    
    async def extract_state_changes(
        self, 
        formatted_turn_context: str,
        game_context: Optional[dict] = None
    ) -> StateExtractionResult:
        """
        Extract character state changes from formatted turn context.
        
        Analyzes structured turn context that includes turn metadata, turn messages,
        and carry-over effects to identify what character states need to be updated 
        (HP changes, conditions, spell usage, etc.).
        
        Args:
            formatted_turn_context: Structured turn context with sections for turn info,
                                   turn messages, and carry-over effects from child turns
            game_context: Optional additional context about characters, combat state, etc.
        
        Returns:
            StateExtractionResult with all identified character state changes
        """
        try:
            # Prepare the extraction prompt with formatted turn context and game context
            extraction_prompt = self._prepare_extraction_prompt(formatted_turn_context, game_context)
            
            # Run the state extraction agent
            agent_result = await self.agent.run(extraction_prompt)
            
            # Return the structured state extraction result
            return agent_result.output if hasattr(agent_result, 'output') else agent_result
            
        except Exception as e:
            # Return empty result on failure with error info
            return StateExtractionResult(
                character_updates=[],
                new_characters=[],
                combat_info={},
                extracted_from=formatted_turn_context,
                confidence=0.0,
                notes=f"State extraction failed: {str(e)}"
            )
    
    def extract_state_changes_sync(
        self,
        formatted_turn_context: str, 
        game_context: Optional[dict] = None
    ) -> StateExtractionResult:
        """
        Synchronous version of extract_state_changes.
        
        Args:
            formatted_turn_context: Structured turn context with sections for turn info,
                                   turn messages, and carry-over effects from child turns
            game_context: Optional additional context about characters, combat state, etc.
            
        Returns:
            StateExtractionResult with all identified character state changes
        """
        import asyncio
        return asyncio.run(self.extract_state_changes(formatted_turn_context, game_context))
    
    def _prepare_extraction_prompt(self, formatted_turn_context: str, game_context: Optional[dict] = None) -> str:
        """
        Prepare the extraction prompt for analyzing formatted turn context and identifying state changes.
        
        Args:
            formatted_turn_context: Structured turn context with sections for turn info,
                                   turn messages, and carry-over effects from child turns
            game_context: Optional additional context about characters, combat state, etc.
        
        Returns:
            Formatted prompt string for the state extraction agent
        """
        # Build the extraction prompt with clear sections
        prompt_sections = [
            "Analyze the following structured turn context and extract all character state changes:",
            "",
            "TURN CONTEXT:",
            formatted_turn_context,
            ""
        ]
        
        # Add additional game context if available
        if game_context:
            prompt_sections.extend([
                "ADDITIONAL GAME CONTEXT:",
                f"Combat round: {game_context.get('combat_round', 'N/A')}",
                f"Current initiative: {game_context.get('current_initiative', 'N/A')}",
                ""
            ])
        
        # Add extraction instructions
        prompt_sections.extend([
            "Extract and return all character state changes in the structured format.",
            "Focus on identifying from the turn messages and carry-over effects:",
            "- HP changes (damage taken, healing received)",
            "- Condition changes (new conditions added, existing conditions removed)", 
            "- Resource usage (spell slots consumed, items used)",
            "- Inventory changes (items gained or lost)",
            "- Death saving throws (successes or failures)",
            "- New character appearances or removals",
            "",
            "Important: Only extract state changes that are explicitly described or clearly implied",
            "in the turn context. The turn context includes structured sections with turn metadata,",
            "turn messages (containing DM narratives and player actions), and carry-over effects.",
            "If no state changes are detected, return empty lists but still include the",
            "extracted_from field and set confidence appropriately."
        ])
        
        return "\n".join(prompt_sections)


def create_state_extractor_agent(model_name: str = "gemini-2.5-flash-lite") -> StateExtractorAgent:
    """
    Factory function to create a configured state extraction agent.
    
    Args:
        model_name: Gemini model to use for state extraction
    
    Returns:
        Configured StateExtractorAgent instance
    """
    return StateExtractorAgent(model_name=model_name)