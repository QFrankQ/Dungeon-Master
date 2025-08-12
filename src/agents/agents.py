from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from pydantic_ai.messages import ModelMessage
import os
from agents.prompts import DUNGEON_MASTER_DEFAULT_PROMPT
from memory import MessageHistoryProcessor, create_summarizer, create_history_processor, MemoryConfig, DEFAULT_MEMORY_CONFIG
from typing import List, Optional
import random


MODEL_NAME = 'gemini-2.5-flash'


def roll_dice(sides: int = 20) -> int:
    """Roll a dice with a given number of sides (default: 20)."""
    return random.randint(1, sides)

class DungeonMasterAgent:
    def __init__(
        self, 
        system_prompt: str = None,
        history_processor: Optional[MessageHistoryProcessor] = None
    ):
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        # print(f"GEMINI_API_KEY: {GEMINI_API_KEY}")
        model = GeminiModel(
            MODEL_NAME, provider=GoogleGLAProvider(api_key=GEMINI_API_KEY)
        )
        if system_prompt is None:
            system_prompt = DUNGEON_MASTER_DEFAULT_PROMPT
        
        self.history_processor = history_processor
        self.agent = Agent(
            model,
            name="Dungeon Master",
            system_prompt=system_prompt,
            tools=[roll_dice]
        )

    def respond(self, message: str, message_history: Optional[List[ModelMessage]] = None):
        """Send a message to the Dungeon Master agent and get a response."""
        return self.agent.run_sync(message, message_history=message_history)
    
    def clear_memory(self):
        """Clear the conversation memory/summary."""
        if self.history_processor:
            self.history_processor.clear_summary()

# Optionally, keep the function for backward compatibility

def create_dungeon_master_agent(
    system_prompt: str = None, 
    memory_config: Optional[MemoryConfig] = None,
    use_memory: bool = False
):
    """Factory function to create a DM agent with optional memory management."""
    history_processor = None
    
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
    
    return DungeonMasterAgent(
        system_prompt=system_prompt,
        history_processor=history_processor
    )
