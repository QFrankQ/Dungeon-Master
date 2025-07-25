from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from dotenv import load_dotenv
import os
from agents.agents import DungeonMasterAgent
import json

load_dotenv()
MESSAGE_TRACE_FILENAME = "message_trace/message_trace.json"

def clear_message_trace(filename=MESSAGE_TRACE_FILENAME):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("")

def append_message_trace(messages, filename=MESSAGE_TRACE_FILENAME):
    with open(filename, "a", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
        f.write("\n")

def start_game():
    agent = DungeonMasterAgent()
    print("Welcome to the DnD Dungeon Master! Type 'exit' or 'quit' to leave.")
    clear_message_trace()
    message_history = []
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() in {"exit", "quit"}:
            print("Goodbye!")
            break
        response = agent.respond(user_input, message_history=message_history)
        message_history = response.all_messages()
        print("Dungeon Master:", response.output)
        messages = json.loads(response.all_messages_json().decode("utf-8"))
        append_message_trace(messages)

if __name__ == "__main__":
    start_game()
