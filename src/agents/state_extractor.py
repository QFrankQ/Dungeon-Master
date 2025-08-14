"""
State extraction agent that analyzes DM narrative responses and extracts state changes.
"""

from typing import Optional
from pydantic_ai import Agent
import google.genai as genai

from .state_updates import StateExtractionResult
from .prompts import STATE_EXTRACTOR_INSTRUCTIONS


class StateExtractorAgent:
    """
    Agent that analyzes DM narrative text and extracts structured state changes.
    
    This agent reads the DM's narrative response and identifies what character
    states need to be updated (HP changes, conditions, inventory, etc.) without
    actually making the changes.
    """
    
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        """Initialize the state extraction agent."""
        self.model = genai.GenerativeModel(model_name)
        self.agent = Agent(
            self.model,
            name="State Extractor",
            instructions=STATE_EXTRACTOR_INSTRUCTIONS,
            output_type=StateExtractionResult
        )
    
    async def extract_state_changes(
        self, 
        narrative: str,
        context: Optional[dict] = None
    ) -> StateExtractionResult:
        """
        Extract state changes from a DM narrative response.
        
        Args:
            narrative: The DM's narrative text to analyze
            context: Optional context about current game state, characters, etc.
        
        Returns:
            StateExtractionResult with all identified state changes
        """
        try:
            # Prepare the prompt with narrative and context
            prompt = self._prepare_extraction_prompt(narrative, context)
            
            # Run the extraction agent
            result = await self.agent.run(prompt)
            
            # Return the structured result
            return result.output if hasattr(result, 'output') else result
            
        except Exception as e:
            # Return empty result on failure with error info
            return StateExtractionResult(
                character_updates=[],
                new_characters=[],
                combat_info={},
                extracted_from=narrative,
                confidence=0.0,
                notes=f"Extraction failed: {str(e)}"
            )
    
    def extract_state_changes_sync(
        self,
        narrative: str, 
        context: Optional[dict] = None
    ) -> StateExtractionResult:
        """
        Synchronous version of extract_state_changes.
        """
        import asyncio
        return asyncio.run(self.extract_state_changes(narrative, context))
    
    def _prepare_extraction_prompt(self, narrative: str, context: Optional[dict] = None) -> str:
        """
        Prepare the prompt for state extraction.
        
        Args:
            narrative: The DM narrative to analyze
            context: Optional context information
        
        Returns:
            Formatted prompt string
        """
        #TODO: additional context from previous messages may be needed
        prompt_parts = [
            "Analyze the following DM narrative and extract all state changes:",
            "",
            f"NARRATIVE: {narrative}",
            ""
        ]
        
        if context:
            prompt_parts.extend([
                "CONTEXT:",
                f"Current characters: {context.get('characters', 'Unknown')}",
                f"Combat round: {context.get('combat_round', 'N/A')}",
                f"Current initiative: {context.get('current_initiative', 'N/A')}",
                ""
            ])
        
        prompt_parts.extend([
            "Extract and return all character state changes in the structured format.",
            "Focus on:",
            "- HP changes (damage, healing)",
            "- Condition changes (add/remove conditions)", 
            "- Inventory changes (use items, gain items)",
            "- Spell slot usage",
            "- Death saving throws",
            "- New character appearances",
            "",
            "If no state changes are detected, return empty lists but still include",
            "the extracted_from field and set confidence appropriately."
        ])
        
        return "\n".join(prompt_parts)


def create_state_extractor_agent(model_name: str = "gemini-2.5-flash-lite") -> StateExtractorAgent:
    """
    Factory function to create a configured state extraction agent.
    
    Args:
        model_name: Gemini model to use for state extraction
    
    Returns:
        Configured StateExtractorAgent instance
    """
    return StateExtractorAgent(model_name=model_name)