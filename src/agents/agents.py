from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from pydantic_ai.messages import ModelMessage
import os
from agents.prompts import DUNGEON_MASTER_DEFAULT_INSTRUCTIONS
from ..models.dm_response import DMResponse
from typing import List, Optional, Union
import random

#TODO: gemini-2.5-flash defaults with thinking ability, may be turned off
MODEL_NAME = 'gemini-2.5-flash'


def roll_dice(sides: int = 20) -> int:
    """Roll a dice with a given number of sides (default: 20)."""
    return random.randint(1, sides)

class DungeonMasterAgent:
    def __init__(
        self, 
        instructions: str = None,
        use_structured_output: bool = False
    ):
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        # print(f"GEMINI_API_KEY: {GEMINI_API_KEY}")
        model = GeminiModel(
            MODEL_NAME, provider=GoogleGLAProvider(api_key=GEMINI_API_KEY)
        )
        if instructions is None:
            instructions = DUNGEON_MASTER_DEFAULT_INSTRUCTIONS
        
        self.use_structured_output = use_structured_output
        # Configure agent based on output type
        if use_structured_output:
            self.agent = Agent(
                model,
                name="Dungeon Master",
                instructions=instructions,
                tools=[roll_dice],
                output_type=NativeOutput(
                    [DMResponse], 
                    name='DM Structured Response',
                    description='Provides DM response to the user prompt and the list of tools that needs to be executed after response.'
                ) #there's also strict mode, but may not be needed
            )
        else:
            self.agent = Agent(
                model,
                name="Dungeon Master", 
                instructions=instructions,
                tools=[roll_dice]
            )

    def respond(
        self, 
        message: str, 
        message_history: Optional[List[ModelMessage]] = None,
        session_context: Optional[dict] = None
    ):
        """
        Send a message to the Dungeon Master agent and get a response.
        
        Args:
            message: User message
            message_history: Optional message history
            session_context: Optional session context (unused, kept for compatibility)
        
        Returns:
            Agent result from PydanticAI (either structured output or plain response)
        """
        # Get the response from the agent - this is now the only responsibility
        return self.agent.run_sync(message, message_history=message_history)
    
    def clear_memory(self):
        """
        Clear memory - this is now a no-op as memory management is external.
        Kept for backward compatibility.
        """
        pass

# Optionally, keep the function for backward compatibility

def create_dungeon_master_agent(
    instructions: str = None,
    use_structured_output: bool = False
):
    """
    Factory function to create a DM agent.
    Note: State management and memory management are now handled externally via SessionManager.
    
    Args:
        instructions: Custom system prompt (uses default if None)
        use_structured_output: Enable structured DMResponse output
    
    Returns:
        Configured DungeonMasterAgent instance
    """
    return DungeonMasterAgent(
        instructions=instructions,
        use_structured_output=use_structured_output
    )
