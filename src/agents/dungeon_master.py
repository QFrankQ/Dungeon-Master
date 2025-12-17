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

from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from dotenv import load_dotenv
load_dotenv()
# from ..memory.turn_manager import TurnManager
# from ..db.vector_service import VectorService
from ..models.dm_response import DungeonMasterResponse
# from ..memory.turn_manager import
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
        model_name: str,
        api_key: str,
        tools: Optional[List[Callable]] = None
    ):
        """
        Initialize the Dungeon Master LLM Agent.

        Args:
            model_name: Gemini model to use for the agent
            api_key: API key (required for guild-level BYOK)
            tools: Optional list of tool functions to provide to the agent
        """
        # Initialize components
        self.tools = tools or []

        # Initialize PydanticAI agent with guild-level API key
        if not api_key:
            raise ValueError("API key is required for DungeonMasterAgent")

        self.model = GoogleModel(
            model_name, provider=GoogleProvider(api_key=api_key)
        )
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent[DungeonMasterResponse]:
        """Create the PydanticAI agent with system prompt and tools."""
        # Create agent with system prompt and tools
        agent = Agent(
            model=self.model,
            output_type=DungeonMasterResponse,
            instructions=self.get_system_prompt(),
            tools=self.tools
        )
        return agent
    
    async def process_message(
        self,
        context: str,
        deps: Optional[Any] = None
    ):
        """
        Process a pre-built context and return Dungeon Master AgentRunResult.

        Args:
            context: Pre-built context string from external context builder
            deps: Optional dependencies for tool execution (e.g., DMToolsDependencies)

        Returns:
            AgentRunResult containing:
                - output: DungeonMasterResponse with narrative and step completion status
                - usage(): Method to get token and request usage
        """
        # Get response from LLM agent using pre-built context
        # Pass deps to agent.run() for tool dependency injection
        result = await self.agent.run(context, deps=deps)

        return result
    
    def process_message_sync(
        self,
        context: str,
        deps: Optional[Any] = None
    ) -> DungeonMasterResponse:
        """Synchronous version of process_message."""
        return asyncio.run(self.process_message(context, deps=deps))
        
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
    model_name: str,
    api_key: str,
    tools: Optional[List[Callable]] = None
) -> DungeonMasterAgent:
    """
    Factory function to create a configured Dungeon Master Agent.

    Args:
        model_name: Gemini model name to use
        api_key: API key (required for guild-level BYOK)
        tools: Optional list of tool functions to provide to the agent

    Returns:
        Configured DungeonMasterAgent instance
    """
    return DungeonMasterAgent(
        model_name=model_name,
        api_key=api_key,
        tools=tools
    )