from flask import Flask, render_template, request, jsonify
from agents.agents import DungeonMasterAgent
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
agent = DungeonMasterAgent()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    response = agent.respond(user_input)
    # Extract the output attribute if present
    if hasattr(response, "output"):
        response = response.output
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)
