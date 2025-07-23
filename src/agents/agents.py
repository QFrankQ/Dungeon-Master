from pydantic_ai import Agent, Tool
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
import os
from agents.prompts import DUNGEON_MASTER_DEFAULT_PROMPT
import random


MODEL_NAME = 'gemini-2.5-flash'


def roll_dice(sides: int = 20) -> int:
    """Roll a dice with a given number of sides (default: 20)."""
    return random.randint(1, sides)

class DungeonMasterAgent:
    def __init__(self, system_prompt: str = None):
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        print(f"GEMINI_API_KEY: {GEMINI_API_KEY}")
        model = GeminiModel(
            MODEL_NAME, provider=GoogleGLAProvider(api_key=GEMINI_API_KEY)
        )
        if system_prompt is None:
            system_prompt = DUNGEON_MASTER_DEFAULT_PROMPT
        self.agent = Agent(
            model,
            name="Dungeon Master",
            system_prompt=system_prompt,
            tools=[roll_dice],  # Register the tool here
        )

    def respond(self, message: str):
        """Send a message to the Dungeon Master agent and get a response."""
        return self.agent.run_sync(message)

# Optionally, keep the function for backward compatibility

def create_dungeon_master_agent(system_prompt: str = None):
    return DungeonMasterAgent(system_prompt=system_prompt)
