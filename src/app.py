from flask import Flask, render_template, request, jsonify
from agents.agents import create_dungeon_master_agent
from dotenv import load_dotenv
import os
import random

load_dotenv()

app = Flask(__name__)
# Create DM agent with memory management
agent = create_dungeon_master_agent()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        chat_history = data.get("chatHistory", [])
        agents = data.get("agents", [])
        user_profile = data.get("userProfile", {})
        ai_settings = data.get("settings", {})
        
        # Get the last user message
        last_message = chat_history[-1]["text"] if chat_history else ""
        
        # Get the DM agent from the agents list, or use default
        dm_agent_data = next((a for a in agents if a.get("isDM", False)), None)
        
        # Generate response using the DM agent
        response = agent.respond(last_message)
        
        # Extract the output if it's a response object
        response_text = response.output if hasattr(response, "output") else str(response)
        
        # Calculate mock usage stats (in a real implementation, you'd get these from the model)
        tokens_used = len(response_text.split()) * 1.3  # Rough estimate
        tokens_used = int(tokens_used) + random.randint(10, 50)
        price = (tokens_used / 1000) * 0.0015  # Rough pricing estimate
        
        # Find the DM agent ID from the agents list
        dm_agent_id = dm_agent_data["id"] if dm_agent_data else "agent-dm"
        
        return jsonify({
            "newMessage": {
                "sender": "DM",
                "text": response_text
            },
            "updatedAgentId": dm_agent_id,
            "usageStats": {
                "tokensUsed": tokens_used,
                "price": price
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
