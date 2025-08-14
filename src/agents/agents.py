from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from pydantic_ai.messages import ModelMessage
import os
from agents.prompts import DUNGEON_MASTER_DEFAULT_INSTRUCTIONS
from agents.dm_response import DMResponse
from memory import MessageHistoryProcessor, create_summarizer, create_history_processor, MemoryConfig, DEFAULT_MEMORY_CONFIG
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
        history_processor: Optional[MessageHistoryProcessor] = None,
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
        self.history_processor = history_processor
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
        """Clear the conversation memory/summary."""
        if self.history_processor:
            self.history_processor.clear_summary()
        if self.session_manager:
            self.session_manager.clear_session_context()

# Optionally, keep the function for backward compatibility

def create_dungeon_master_agent(
    instructions: str = None, 
    memory_config: Optional[MemoryConfig] = None,
    use_memory: bool = False,
    use_structured_output: bool = False,
    enable_state_management: bool = False
):
    """
    Factory function to create a DM agent with optional memory and state management.
    
    Args:
        instructions: Custom system prompt (uses default if None)
        memory_config: Memory configuration (uses default if None)
        use_memory: Enable memory management
        use_structured_output: Enable structured DMResponse output
        enable_state_management: Enable automatic state management
    
    Returns:
        Configured DungeonMasterAgent instance
    """
    history_processor = None
    session_manager = None
    
    # Setup memory management
    if use_memory and memory_config is None:
        memory_config = DEFAULT_MEMORY_CONFIG
    
    if use_memory and memory_config.enable_memory:
        summarizer = None
        if memory_config.enable_summarization:
            summarizer = create_summarizer(memory_config.summarizer_model)
            
            async def summarize_func(messages: List[ModelMessage]) -> List[ModelMessage]:
                return await summarizer.create_integrated_summary(messages)
        else:
            summarize_func = None
        
        history_processor = create_history_processor(
            max_tokens=memory_config.max_tokens,
            min_tokens=memory_config.min_tokens,
            summarizer_func=summarize_func
        )
    
    # Setup state management
    if enable_state_management:
        session_manager = create_session_manager(
            enable_state_management=True
        )
    
    return DungeonMasterAgent(
        instructions=instructions,
        history_processor=history_processor,
        use_structured_output=use_structured_output,
        session_manager=session_manager
    )
