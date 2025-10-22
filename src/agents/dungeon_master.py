"""
Dungeon Master LLM Agent for generating narrative responses and managing D&D gameplay.

The Dungeon Master Agent is an LLM agent responsible for:
- Generating narrative responses to player actions
- Managing NPCs and environmental descriptions
- Adjudicating rule interpretations within step objectives
- Signaling step completion to the Gameflow Director
- Creating immersive D&D gameplay experiences

Integrates with existing TurnManager and SessionManager architecture.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from dotenv import load_dotenv
load_dotenv()
from ..memory.turn_manager import TurnManager
# from ..db.vector_service import VectorService
from ..models.dm_response import DungeonMasterResponse
import os
import asyncio

#TODO: gemini-2.5-flash defaults with thinking ability, may be turned off
MODEL_NAME = 'gemini-2.5-flash'

class DungeonMasterAgent:
    """
    LLM Agent for Dungeon Master responsibilities.

    Generate narrative responses, manage NPCs, and adjudicate D&D gameplay within step objectives.
    """
    
    def __init__(
        self,
        turn_manager: Optional[TurnManager] = None,
        # vector_service: Optional[VectorService] = None,
        model_name: str = "gemini-2.0-flash-exp"
    ):
        """
        Initialize the Dungeon Master LLM Agent.

        Args:
            turn_manager: Turn manager for combat turn coordination
            vector_service: Vector service for rule lookups
            model_name: Gemini model to use for the agent
        """
        # Initialize components
        self.turn_manager = turn_manager
        # self.vector_service = vector_service
        
        # Initialize PydanticAI agent
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.model = GoogleModel(
            MODEL_NAME, provider=GoogleProvider(api_key=GOOGLE_API_KEY)
        )
        self.agent = self._create_agent()

    #TODO: add function tools
    def _create_agent(self) -> Agent[DungeonMasterResponse]:
        """Create the PydanticAI agent with system prompt and tools."""
        # Create agent with system prompt
        agent = Agent(
            model=self.model,
            output_type=DungeonMasterResponse,
            instructions=self.get_system_prompt()
        )
        return agent
    
    async def process_message(
        self,
        context: str
    ) -> DungeonMasterResponse:
        """
        Process a pre-built context and return Dungeon Master response.

        Args:
            context: Pre-built context string from external context builder

        Returns:
            DungeonMasterResponse with narrative and step completion status
        """
        # Get response from LLM agent using pre-built context
        result = await self.agent.run(context)

        return result.output
    
    def process_message_sync(
        self,
        context: str
    ) -> DungeonMasterResponse:
        """Synchronous version of process_message."""
        return asyncio.run(self.process_message(context))
        
    def get_system_prompt(self):
        # Load DM system prompt from file
        prompts_dir = Path(__file__).parent.parent / "prompts"
        prompt_file = prompts_dir / "dungeon_master_system_prompt.txt"

        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            # Fallback prompt if file not found
            return """You are a Dungeon Master for a D&D game. Generate narrative responses to player actions,
                     manage NPCs, and adjudicate rules. Signal step completion when objectives are met."""

def create_dungeon_master_agent(
    turn_manager: Optional[TurnManager] = None,
    # vector_service: Optional[VectorService] = None,
    model_name: str = "gemini-2.0-flash-exp"
) -> DungeonMasterAgent:
    """
    Factory function to create a configured Dungeon Master Agent.

    Args:
        turn_manager: Turn manager for combat coordination
        vector_service: Vector service for rule lookups
        model_name: Gemini model name to use

    Returns:
        Configured DungeonMasterAgent instance
    """
    return DungeonMasterAgent(
        turn_manager=turn_manager,
        # vector_service=vector_service,
        model_name=model_name
    )