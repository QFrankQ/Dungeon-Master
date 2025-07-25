# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a D&D Dungeon Master AI assistant built with PydanticAI and Google's Gemini models. The project provides both a command-line interface and a Flask web interface for interactive D&D sessions.

## Architecture

### Core Components

- **Agent System** (`src/agents/`): Contains the main DungeonMasterAgent class that handles AI interactions
  - `agents.py`: Main agent implementation using PydanticAI with Gemini 2.5 Flash model
  - `prompts.py`: System prompts for the Dungeon Master persona
  - `tools.py`: Currently minimal, contains placeholder for future tool implementations

- **User Interfaces**:
  - `src/main.py`: Command-line interface with message tracing
  - `src/app.py`: Flask web server with HTML template interface

- **Data & Knowledge Base** (`src/db/`):
  - `combat_rules.json`: Comprehensive D&D combat rules and guidelines with semantic tags
  - `prepare_embeddings.py`: Vector embedding preparation using Google's embedding model
  - `upload_to_vector_DB.py`: For uploading to vector databases (likely Qdrant based on API key usage)

- **Game Data** (`src/characters/`):
  - `enemies.json`: Enemy stats and information
  - `enemies/` and `players/` directories for character data

## Development Setup

### Dependencies
The project uses `uv` for dependency management with Python 3.11+. Main dependencies:
- `pydantic-ai` (v0.4.6+): AI agent framework
- `pydantic` (v2.11.7+): Data validation
- Flask (for web interface)
- Google AI libraries for Gemini integration

### Environment Variables
Required environment variables:
- `GEMINI_API_KEY`: For Google Gemini model access
- `GOOGLE_API_KEY`: For Google embedding services  
- `QDRANT_API_KEY`: For vector database operations

### Running the Application

**Command Line Interface:**
```bash
python src/main.py
```

**Web Interface:**
```bash
python src/app.py
```
Access at http://localhost:5000

## Key Features

### AI Agent Capabilities
- Dice rolling tool (`roll_dice` function with configurable sides)
- Message history tracking and persistence
- JSON message tracing for debugging/analysis

### Combat Rules Integration
The `combat_rules.json` contains structured D&D 5e combat rules with:
- Detailed rule explanations
- Semantic tags for efficient retrieval
- Topics include initiative, damage, conditions, morale, and encounter management

### Vector Search Preparation
The embedding system processes rule content for semantic search:
- Uses `gemini-embedding-001` model
- Processes rule sections with metadata preservation
- Prepares for vector database storage and retrieval

## File Structure Notes

- Template files are in `src/templates/` (currently just `index.html`)
- Message traces are saved to `src/message_trace/message_trace.json`
- The project uses a flat module structure within `src/`

## Development Patterns

- Agent responses include both structured data and natural language output
- Message history is maintained throughout sessions for context
- JSON serialization is used for message persistence and debugging
- The system separates CLI and web interfaces while sharing the core agent logic