# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a D&D Dungeon Master AI assistant built with PydanticAI and Google's Gemini models. The project provides both a command-line interface and a Flask web interface for interactive D&D sessions with sophisticated memory management and vector-based rule lookup.

## Architecture

The system follows a modular design with clear separation of concerns:

```
User Interface (CLI/Web) → SessionManager → DungeonMasterAgent → Gemini AI → Vector Database → Response
                              ↓
                     MessageFormatter + HistoryManager + StateManager
```

### Core Components

- **Agent System** (`src/agents/`): Pure AI response generation
  - `agents.py`: `DungeonMasterAgent` class focused solely on AI response generation (no session management)
  - `prompts.py`: Combat arbiter system prompts focused on D&D Rules as Written (RAW)
  - `tools.py`: Dice rolling tool with configurable sides

- **Message Processing System** (`src/services/`, `src/models/`): **New message handling architecture**
  - `message_formatter.py`: Transforms messages between formats, creates structured agent input with player actions + character status
  - `history_manager.py`: **External message history management** with PydanticAI `ModelMessage` storage and filtering
  - `chat_message.py`: Frontend-backend communication format with player/character context
  - `formatted_game_message.py`: Agent processing format with character information for DM decision-making

- **Memory Management System** (`src/memory/`): **Comprehensive session orchestration and memory infrastructure**
  - `config.py`: Configuration with token thresholds (10k max, 5k min) and feature toggles
  - `history_processor.py`: Token-based message trimming and PydanticAI integration
  - `summarizer.py`: Dedicated conversation summarization using Gemini 1.5 Flash
  - `session_manager.py`: **Primary interface** - owns DungeonMasterAgent and orchestrates entire session workflow
  - `state_manager.py`: Handles character and game state updates

- **Vector Database & Knowledge** (`src/db/`):
  - `combat_rules.json`: 442-line comprehensive D&D 5e combat rules with semantic tags
  - `vector_service.py`: Qdrant integration with Google embeddings (`gemini-embedding-001`)
  - `prepare_embeddings.py` & `upload_to_vector_DB.py`: Vector database setup
  - `test_vector_db.py`: Testing utilities

- **Web Interface** (`src/`): **Refactored modular architecture**
  - `app.py`: Flask server with chat endpoint and static file serving (port 5001)
  - `templates/index.html`: Clean HTML template with external file references
  - `static/css/styles.css`: All custom CSS styles
  - `static/js/`: Modular JavaScript architecture
    - `api-service.js`: Backend API communication
    - `app-core.js`: Core application logic and initialization
    - `chat.js`: Chat functionality and dice rolling
    - `rendering.js`: UI rendering methods
    - `agents.js`: Agent management functionality
    - `user-profile.js`: User profile and notes management
    - `templates.js`: D&D data templates and form building
    - `utils.js`: Utility functions and import/export
    - `init.js`: Application initialization

- **CLI Interface**:
  - `src/main.py`: CLI using SessionManager as primary interface with memory commands (`clear`, `exit`, `quit`) and token usage tracking

- **Game Data** (`src/characters/`):
  - `enemies.json`: Enemy stats and information
  - `enemies/` and `players/` directories for character data

## Development Setup

### Dependencies
The project uses `uv` for dependency management with Python 3.11+. Key dependencies:
- `google-genai` (v1.26.0+): Google Gemini API client
- `pydantic-ai` (v0.4.6+): AI agent framework
- `pydantic` (v2.11.7+): Data validation
- `qdrant-client` (v1.15.0+): Vector database client
- `flask`: Web interface

### Environment Variables
Required:
- `GEMINI_API_KEY`: Google Gemini API access
- `QDRANT_API_KEY`: Vector database operations

### Common Commands

**Install dependencies:**
```bash
uv sync
```

**Run CLI interface:**
```bash
uv run python src/main.py
```

**Run web interface:**
```bash
uv run python src/app.py
# Access at http://localhost:5001
```

**Test vector database:**
```bash
uv run python src/db/test_vector_db.py
```

**Run tests:**
```bash
uv run pytest
uv run pytest -v  # verbose output
uv run pytest path/to/specific_test.py  # single test file
```

## Key Features & Architecture Patterns

### Session-Centric Architecture (Current Architecture)
- **SessionManager as Primary Interface**: All user interactions go through `SessionManager.process_user_input()`
- **Dependency Inversion**: SessionManager owns and orchestrates DungeonMasterAgent, not the reverse
- **Clean Separation**: Agent handles pure AI response generation, SessionManager handles session orchestration
- **Unified API**: Consistent interface regardless of agent configuration (structured vs plain text output)

### External Message History Management 
- **HistoryManager**: Handles PydanticAI `ModelMessage` storage outside of the agent
- **Player action filtering**: Stores only conversational content (`"Aragorn: I attack the orc"`), excludes character status bloat
- **Dynamic summarization**: Applies token management (10k max, 5k min) with integrated summarization when limits exceeded
- **Content-based token counting**: Uses estimation-only approach to accurately reflect stored history content

### Message Processing Pipeline
- **MessageFormatter**: Transforms between `ChatMessage` → `FormattedGameMessage` → structured agent input
- **Two-part agent input**: `=== PLAYER ACTIONS ===` (stored in history) + `=== CHARACTER STATUS ===` (fresh context, not stored)
- **Character status separation**: Status information provided each turn but never bloats history
- **Proper PydanticAI serialization**: Uses `ModelMessagesTypeAdapter` and `to_jsonable_python()`

### Agent System (Simplified)
- **Pure AI Response Generation**: DungeonMasterAgent focused solely on generating responses from Gemini AI
- **External Dependencies**: Receives `message_history` parameter, no internal state management
- **Factory pattern**: `create_dungeon_master_agent()` creates lightweight agents for SessionManager use
- **Dual AI models**: Gemini 2.5 Flash for main interactions, Gemini 1.5 Flash for summarization

### Vector Search Integration
- **Qdrant vector database**: Semantic search for D&D combat rules using `gemini-embedding-001`
- **Tagged content**: 442-line rules with semantic tags for precise retrieval
- **Testing utilities**: `test_vector_db.py` for validation

### CLI Memory Commands
- `clear`: Reset conversation memory
- `exit`/`quit`: Terminate with cleanup
- Token usage tracking in message traces

### Configuration Management
- **Environment-based**: Support for environment variables with sensible defaults
- **Dataclass pattern**: Using `@dataclass` for configuration with built-in validation
- **Feature toggles**: Enable/disable memory and summarization features

## Development Notes

### Message Tracing
- Comprehensive conversation logs saved to `src/message_trace/message_trace.json`
- Includes token usage tracking for cost monitoring

### Session-Centric Integration Pattern (Current Recommended Approach)
```python
# Primary integration pattern - SessionManager as main interface
session_manager = create_session_manager(
    enable_state_management=True,
    use_structured_output=True,
    agent_instructions=custom_instructions  # optional
)

# Process user input through unified interface
results = session_manager.process_user_input_sync(
    user_input="I attack the orc with my sword",
    message_history=current_message_history,
    session_context={"characters": {...}, "combat_state": {...}}
)

# Extract results
narrative = results["narrative"]              # Always available
agent_result = results["agent_result"]        # For message history tracking  
state_processing = results["state_processing"] # If state management enabled
errors = results["errors"]                    # Any processing errors
```

### Legacy Direct Agent Pattern (For Advanced Use Cases)
```python
# Direct agent usage when you need fine-grained control
dm_agent = create_dungeon_master_agent(use_structured_output=True)
history_manager = create_history_manager(enable_memory=True)

# Manual orchestration
agent_result = dm_agent.respond(user_input, message_history=current_history)
# ... handle result processing manually
```

### Message Data Types & Flow
The system uses three key message types for different purposes:

1. **ChatMessage** (`src/models/chat_message.py`): Frontend-backend communication
   - Contains `player_id`, `character_id`, `text`, `timestamp`, `message_type`
   - Factory methods: `create_player_message()`, `create_dm_message()`, `create_system_message()`

2. **FormattedGameMessage** (`src/models/formatted_game_message.py`): Agent processing format
   - Contains character stats (`current_hp`, `max_hp`, `armor_class`, `status_effects`) + message text
   - Methods: `to_history_format()` (clean), `get_character_summary()` (status), `to_agent_input()` (full context)

3. **PydanticAI ModelMessage**: Internal agent history storage
   - `ModelRequest` with `UserPromptPart` for player messages
   - `ModelResponse` with `TextPart` for DM responses
   - Serialized using `ModelMessagesTypeAdapter` and `to_jsonable_python()`

### Key Architectural Decisions

- **Session-Centric Design**: SessionManager serves as the primary interface, owning and orchestrating all other components including the DM agent
- **Dependency Inversion**: High-level orchestrator (SessionManager) depends on low-level services (Agent, HistoryManager, StateManager) rather than the reverse
- **Pure Component Responsibilities**: Each component has a single, clear responsibility (Agent=AI responses, HistoryManager=memory, StateManager=game state)
- **History vs Context Separation**: Character status is contextual information (provided fresh each turn) but never stored in history (which only contains conversational content)
- **Content-Based Token Counting**: Token estimation reflects only the content actually stored in filtered history, not full conversation including tool calls
- **Unified Interface**: SessionManager provides consistent API regardless of underlying agent configuration or output format

## Development Workflow Notes

- **Always run with uv**: Use `uv run python` instead of plain `python` for consistent dependency management and virtual environment setup