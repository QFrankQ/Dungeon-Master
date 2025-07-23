from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from dotenv import load_dotenv
import os
from agents.agents import DungeonMasterAgent

load_dotenv()

if __name__ == "__main__":
    agent = DungeonMasterAgent()
    print("Welcome to the DnD Dungeon Master! Type 'exit' or 'quit' to leave.")
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() in {"exit", "quit"}:
            print("Goodbye!")
            break
        response = agent.respond(user_input)
        print("Dungeon Master:", response)
    print(response.all_messages())
