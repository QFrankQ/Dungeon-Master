# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a D&D Dungeon Master AI assistant built with PydanticAI and Google's Gemini models. The project provides both a command-line interface and a Flask web interface for interactive D&D sessions with sophisticated memory management and vector-based rule lookup.

## Architecture

The system follows a modular design with clear separation of concerns:

```
User Interface (CLI/Web) → DungeonMasterAgent → Memory Management → Gemini AI → Vector Database → Response
```

### Core Components

- **Agent System** (`src/agents/`): Main AI interaction layer
  - `agents.py`: `DungeonMasterAgent` class with factory pattern for flexible creation
  - `prompts.py`: Combat arbiter system prompts focused on D&D Rules as Written (RAW)
  - `tools.py`: Dice rolling tool with configurable sides

- **Memory Management System** (`src/memory/`): **New comprehensive memory infrastructure**
  - `config.py`: Configuration with token thresholds (10k max, 5k min) and feature toggles
  - `history_processor.py`: Token-based message trimming and PydanticAI integration
  - `summarizer.py`: Dedicated conversation summarization using Gemini 1.5 Flash

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
  - `src/main.py`: CLI with memory commands (`clear`, `exit`, `quit`) and token usage tracking

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
python src/main.py
```

**Run web interface:**
```bash
python src/app.py
# Access at http://localhost:5001
```

**Test vector database:**
```bash
python src/db/test_vector_db.py
```

## Key Features & Architecture Patterns

### Memory Management
- **Token-aware processing**: Automatic trimming when exceeding 10k token limit
- **Integrated summarization**: Preserves context using Gemini 1.5 Flash for cost efficiency
- **Persistent summaries**: Saved to JSON with proper serialization using `to_jsonable_python`
- **History processor pattern**: Custom `MessageHistoryProcessor` following PydanticAI conventions

### Agent System
- **Factory pattern**: `create_dungeon_master_agent()` for flexible agent creation with optional memory
- **Dual AI models**: Gemini 2.5 Flash for main interactions, Gemini 1.5 Flash for summarization
- **Combat arbiter**: System prompts focused on D&D Rules as Written (RAW) enforcement

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

### Agent Creation Pattern
```python
# With memory management
agent = create_dungeon_master_agent(use_memory=True)

# Without memory (for testing)
agent = create_dungeon_master_agent(use_memory=False)
```

### Memory Statistics
The history processor provides memory usage statistics and automatic management when token thresholds are exceeded.

## Development Workflow Notes

- **Always run with uv**: Use `uv` for consistent dependency management and virtual environment setup