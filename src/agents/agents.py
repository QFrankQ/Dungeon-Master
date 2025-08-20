from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from pydantic_ai.messages import ModelMessage
import os
from agents.prompts import DUNGEON_MASTER_DEFAULT_INSTRUCTIONS
from agents.dm_response import DMResponse
from memory.session_manager import SessionManager, create_session_manager
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
        use_structured_output: bool = False,
        session_manager: Optional[SessionManager] = None
    ):
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        # print(f"GEMINI_API_KEY: {GEMINI_API_KEY}")
        model = GeminiModel(
            MODEL_NAME, provider=GoogleGLAProvider(api_key=GEMINI_API_KEY)
        )
        if instructions is None:
            instructions = DUNGEON_MASTER_DEFAULT_INSTRUCTIONS
        
        self.use_structured_output = use_structured_output
        self.session_manager = session_manager
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
    ) -> Union[str, DMResponse, dict]:
        """
        Send a message to the Dungeon Master agent and get a response.
        
        Args:
            message: User message
            message_history: Optional message history
            session_context: Optional session context for state management
        
        Returns:
            Either string response, DMResponse, or dict with processing results
        """
        # Get the response from the agent
        result = self.agent.run_sync(message, message_history=message_history)
        
        # Handle structured responses with state management
        if self.use_structured_output and self.session_manager:
            dm_response = result.output if hasattr(result, 'output') else result
            
            # Process the response through session manager for state updates
            processing_results = self.session_manager.process_dm_response_sync(
                dm_response, session_context
            )
            
            return processing_results
        
        # Return the raw result for non-structured responses
        return result
    
    def clear_memory(self):
        """Clear the session context. History management is now external."""
        if self.session_manager:
            self.session_manager.clear_session_context()

# Optionally, keep the function for backward compatibility

def create_dungeon_master_agent(
    instructions: str = None,
    use_structured_output: bool = False,
    enable_state_management: bool = False
):
    """
    Factory function to create a DM agent with optional state management.
    Note: Memory management is now handled externally via HistoryManager.
    
    Args:
        instructions: Custom system prompt (uses default if None)
        use_structured_output: Enable structured DMResponse output
        enable_state_management: Enable automatic state management
    
    Returns:
        Configured DungeonMasterAgent instance
    """
    session_manager = None
    
    # Setup state management
    if enable_state_management:
        session_manager = create_session_manager(
            enable_state_management=True
        )
    
    return DungeonMasterAgent(
        instructions=instructions,
        use_structured_output=use_structured_output,
        session_manager=session_manager
    )
