from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from dotenv import load_dotenv
import os
from memory.session_manager import create_session_manager
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
    # Create session manager with DM agent  
    session_manager = create_session_manager(
        enable_state_management=True,
        use_structured_output=True
    )
    
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
            session_manager.clear_session_context()
            clear_message_trace()
            message_history = []
            print("Conversation memory cleared. Starting fresh!")
            continue
        
        # Use session manager to process user input
        results = session_manager.process_user_input_sync(
            user_input, 
            message_history=message_history
        )
        
        # Extract the agent result for message history tracking
        agent_result = results["agent_result"] 
        message_history = agent_result.all_messages()
        
        # Display the narrative response 
        print("Dungeon Master:", results["narrative"])
        
        # Trace messages with token information  
        messages_json = agent_result.all_messages_json().decode("utf-8")
        messages = json.loads(messages_json)
        
        # Add token usage info to trace if available
        if hasattr(agent_result, 'usage') and agent_result.usage:
            messages.append({
                "usage_info": {
                    "request_tokens": agent_result.usage.request_tokens,
                    "response_tokens": agent_result.usage.response_tokens,
                    "total_tokens": agent_result.usage.total_tokens
                }
            })
        
        append_message_trace(messages)

if __name__ == "__main__":
    start_game()
