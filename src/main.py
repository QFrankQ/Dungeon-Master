from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from dotenv import load_dotenv
import os
from agents.agents import create_dungeon_master_agent
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
    # Create DM agent with memory management enabled
    agent = create_dungeon_master_agent()
    
    print("Welcome to the DnD Dungeon Master! Type 'exit', 'quit', or 'clear' to manage session.")
    print("- 'clear': Clear conversation memory and start fresh")
    print("- 'exit'/'quit': End session")
    
    clear_message_trace()
    message_history = []
    
    while True:
        user_input = input("You: ")
        command = user_input.strip().lower()
        
        if command in {"exit", "quit"}:
            print("Goodbye!")
            break
        elif command == "clear":
            agent.clear_memory()
            clear_message_trace()
            message_history = []
            print("Conversation memory cleared. Starting fresh!")
            continue
        
        response = agent.respond(user_input, message_history=message_history)
        message_history = response.all_messages()
        print("Dungeon Master:", response.output)
        
        # Trace messages with token information
        messages_json = response.all_messages_json().decode("utf-8")
        messages = json.loads(messages_json)
        
        # Add token usage info to trace if available
        if hasattr(response, 'usage') and response.usage:
            messages.append({
                "usage_info": {
                    "request_tokens": response.usage.request_tokens,
                    "response_tokens": response.usage.response_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            })
        
        append_message_trace(messages)

if __name__ == "__main__":
    start_game()
