# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a D&D Dungeon Master AI assistant built with PydanticAI and Google's Gemini models. The project provides both a command-line interface, a Flask web interface, and a demo terminal for interactive D&D sessions with sophisticated multi-agent orchestration, turn management, and rule-based knowledge retrieval.

## Architecture

The system uses a **multi-agent orchestration** pattern with clear separation of concerns:

```
User Interface (CLI/Web/Demo) → SessionManager → Gameflow Director ⟷ Dungeon Master → Gemini AI
                                      ↓                    ↓              ↓
                              TurnManager         StateExtractor    RulesRetriever
                                      ↓                    ↓
                              ContextBuilders        StateManager
```

### Multi-Agent System
- **Gameflow Director (GD)**: Manages game flow, step objectives, and combat state progression
- **Dungeon Master (DM)**: Generates narrative responses and adjudicates rules
- **State Extractor**: Extracts character/combat state changes from narrative
- **Turn Summarizer**: Condenses completed turns into structured summaries

### Core Components

- **Agent System** (`src/agents/`): Multi-agent AI orchestration
  - `dungeon_master.py`: DM agent for narrative generation and rule adjudication
  - `gameflow_director.py`: Flow director agent for game state progression and step objectives
  - `state_extraction_orchestrator.py`: Orchestrates state extraction from narratives
  - `combat_state_extractor.py`: Extracts combat-specific state changes
  - `resource_extractor.py`: Extracts resource usage (spell slots, abilities, etc.)
  - `event_detector.py`: Detects game events for state tracking
  - `structured_summarizer.py`: Turn condensation agent for hierarchical summaries
  - `prompts.py`: System prompts for various agents
  - `tools.py`: Dice rolling and other agent tools

- **Context Building System** (`src/context/`): Specialized context builders for different agents
  - `gd_context_builder.py`: Builds context for Gameflow Director (history, turn context, objectives, new messages)
  - `dm_context_builder.py`: Builds context for Dungeon Master (chronological context with full turn hierarchy)
  - `state_extractor_context_builder.py`: Builds isolated context for state extraction (current turn only)
  - `structured_summarizer_context_builder.py`: Builds context for turn condensation

- **Message Processing System** (`src/services/`, `src/models/`): Message handling architecture
  - `message_formatter.py`: Transforms messages between formats
  - `history_manager.py`: Message history management with PydanticAI `ModelMessage` storage
  - `chat_message.py`: Frontend-backend communication format with player/character context
  - `formatted_game_message.py`: Agent processing format with character information

- **Memory Management System** (`src/memory/`): Session orchestration and state management
  - `session_manager.py`: **Primary orchestrator** - coordinates GD, DM, StateExtractor, and TurnManager
  - `turn_manager.py`: **Core turn orchestration** - hierarchical turn/sub-turn stack with context isolation
  - `player_character_registry.py`: Maps player IDs to character names for multi-player sessions
  - `state_manager.py`: Handles character and game state updates
  - `session_tools.py`: Session-level tool registry and utilities
  - `config.py`: Configuration with token thresholds and feature toggles
  - `history_processor.py`: Token-based message trimming
  - `summarizer.py`: Conversation summarization using Gemini

- **Models** (`src/models/`): Data structures for game state and messaging
  - `turn_context.py`: Turn/subturn data structure with messages and metadata
  - `turn_message.py`: Message types (LIVE_MESSAGE, COMPLETED_SUBTURN) for turn-based filtering
  - `chat_message.py`: Player-DM communication messages
  - `dm_response.py`: DM agent structured output (narrative, step_complete)
  - `gd_response.py`: Gameflow Director structured output (step objectives, state update flags)
  - `state_updates.py`: State extraction results and update structures
  - `state_commands.py`: Structured commands for state modifications

- **Knowledge Retrieval** (`src/db/`, `src/services/`, `rules/`):
  - `src/db/vector_service.py`: Qdrant integration with Google embeddings (`gemini-embedding-001`)
  - `src/db/combat_rules.json`: 442-line D&D 5e combat rules with semantic tags
  - `rules/`: Extensive markdown-based D&D 5e SRD rules (Classes, Equipment, Gameplay, Monsters, etc.)
  - `prepare_embeddings.py` & `upload_to_vector_DB.py`: Vector database setup utilities
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

- **User Interfaces**:
  - `src/main.py`: Full CLI with SessionManager orchestrating multi-agent workflow
  - `demo_terminal.py`: **Demo interface** - simplified terminal bypassing GD agent for testing DM interactions
    - Multi-character support (switch between hero, wizard, rogue, cleric)
    - Commands: `/help`, `/turn`, `/history`, `/stats`, `/usage`, `/context`, `/switch`, `/who`, `/quit`
    - Uses `session_manager.demo_process_player_input()` for simplified flow

- **Game Data** (`src/characters/`):
  - `enemies.json`: Enemy stats and information
  - `enemies/` and `players/` directories for character data

## Development Setup

### Dependencies
The project uses `uv` for dependency management with Python 3.11+. Key dependencies:
- `pydantic-ai` (v1.2.1+): AI agent framework with structured outputs
- `pydantic` (v2.11.7+): Data validation and modeling
- `flask`: Web interface server
- `pytest` & `pytest-asyncio`: Testing framework
- `sentence-transformers`: Local embeddings for LanceDB rule retrieval
- `lancedb`: Local vector database for rule retrieval
- `qdrant-client`: Cloud vector database (optional)

### Environment Variables
Required:
- `GOOGLE_API_KEY`: Google Gemini API access (for PydanticAI agents)

Optional:
- `QDRANT_API_KEY`: Qdrant cloud vector database (if using Qdrant instead of LanceDB)

### Common Commands

**Install dependencies:**
```bash
uv sync
```

**Run demo terminal (recommended for testing):**
```bash
uv run python demo_terminal.py
# Simplified interface with multi-character support
# Commands: /help, /turn, /history, /stats, /usage, /context, /switch, /who, /quit
```

**Run full CLI interface:**
```bash
uv run python src/main.py
# Full multi-agent system with GD + DM orchestration
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
uv run pytest                          # run all tests
uv run pytest -v                       # verbose output
uv run pytest tests/test_memory_integration.py  # single test file
uv run pytest tests/ -k "turn"         # run turn-related tests
uv run pytest tests/ -k "DungeonMaster"  # run DM agent tests
```

## Key Features & Architecture Patterns

### Multi-Agent Orchestration (Current Architecture)
- **SessionManager as Primary Orchestrator**: Coordinates Gameflow Director, Dungeon Master, State Extractor, and Turn Manager
- **Agent Separation of Concerns**:
  - **Gameflow Director**: Manages game flow, step objectives, determines when state updates are needed
  - **Dungeon Master**: Generates narrative, adjudicates rules, signals step completion
  - **State Extractor**: Extracts state changes from completed narrative
- **Context Builders**: Each agent receives specialized context from dedicated context builders
- **Two Operating Modes**:
  - **Full Mode** (`src/main.py`): GD + DM multi-agent orchestration with state management
  - **Demo Mode** (`demo_terminal.py`): DM-only simplified flow for testing narratives

### Context Building System
- **Specialized Context Builders**: Each agent type has a dedicated context builder
  - `GDContextBuilder`: Provides GD with history, turn context, step objectives, new messages
  - `DMContextBuilder`: Provides DM with chronological narrative context and full turn hierarchy
  - `StateExtractorContextBuilder`: Provides isolated current-turn context to prevent duplicate extractions
- **Hierarchical Turn Structure**: Context includes nested turn/subturn representation for reactions and complex sequences
- **Message Filtering**: Different agents see different message types (LIVE_MESSAGE vs COMPLETED_SUBTURN)

### Agent Design Pattern
- **Structured Outputs**: All agents use PydanticAI structured output types for reliability
  - `DungeonMasterResponse`: `narrative` (str), `step_complete` (bool)
  - `GameflowDirectorResponse`: `new_game_step_objective` (str), `game_state_update_required` (bool)
  - `StateExtractionResult`: Structured state changes (HP, conditions, resources, etc.)
- **Factory Functions**: Each agent has a `create_*` factory function for consistent initialization
- **Model Selection**: Default to `gemini-2.5-flash` for main agents, configurable via factory parameters

### Turn Management System (Combat Architecture)
- **Hierarchical turn tracking**: Stack-based turn/sub-turn management (Level 0=main turns, Level 1+=sub-turns/reactions)
- **Context isolation**: Each turn maintains isolated context to prevent duplicate state extractions
- **Turn Manager Tool**: `turn_manager.start_and_queue_turns()` available as tool to DM agent for declaring reactions
- **Turn condensation**: AI-powered compression of completed turns into structured summaries via `StructuredSummarizer` agent
- **Action Declaration**: Player actions stored as `ActionDeclaration` (speaker, content) in turn context
- **Turn snapshots**: `get_snapshot()` provides immutable view of turn state for context builders
- **Multi-turn coordination**: Supports nested reaction chains (last-in-first-out processing)

### Knowledge Retrieval System
- **Dual vector database support**:
  - **LanceDB** (local): Sentence-transformers embeddings for semantic search over SRD markdown files
  - **Qdrant** (cloud, optional): Google embeddings for combat rules JSON
- **Extensive SRD rules**: `rules/` directory contains comprehensive D&D 5e markdown (Classes, Monsters, Equipment, Gameplay)
- **Semantic chunking**: Markdown files split by headers for precise rule retrieval
- **Combat rules JSON**: 442-line structured combat rules with semantic tags

### Player Character Registry
- **Multi-player support**: Maps `player_id` to `character_name` for multi-player sessions
- **Turn-aware character tracking**: Identifies which player controls which character
- **Demo terminal integration**: Demo supports switching between multiple characters (`/switch hero`, `/switch wizard`, etc.)

### Configuration & Feature Toggles
- **SessionManager configuration**:
  - `enable_state_management`: Toggle state extraction/updates
  - `enable_turn_management`: Toggle hierarchical turn tracking
- **Memory configuration**: Token thresholds for history management
- **Model selection**: Configurable Gemini model selection per agent

## Development Notes

### Testing Strategy
- **Unit tests**: Individual agent and component testing in `tests/`
- **Integration tests**: Memory, turn management, and multi-agent coordination tests
- **Demo terminal**: Use `demo_terminal.py` for rapid DM agent iteration and testing
- **Test organization**:
  - `tests/DungeonMasterAgent Tests/`: DM agent behavior tests
  - `tests/TurnManager tests/`: Turn management system tests
  - `tests/structured_turn_summarizer/`: Turn summarization tests
  - `tests/test_memory_*.py`: Memory system tests

### Multi-Agent Integration Pattern (Full System)
```python
# Create session manager with full multi-agent orchestration
from src.memory.session_manager import SessionManager
from src.agents.gameflow_director import create_gameflow_director
from src.agents.dungeon_master import create_dungeon_master_agent
from src.agents.state_extraction_orchestrator import create_state_extraction_orchestrator
from src.memory.turn_manager import create_turn_manager
from src.memory.state_manager import create_state_manager

# Create turn manager with condensation
turn_manager = create_turn_manager(turn_condensation_agent=condensation_agent)

# Create DM with turn manager tool
dm_agent = create_dungeon_master_agent(
    model_name='gemini-2.5-flash',
    tools=[turn_manager.start_and_queue_turns]
)

# Create session manager
session_manager = SessionManager(
    gameflow_director_agent=gd_agent,
    dungeon_master_agent=dm_agent,
    state_extraction_orchestrator=state_extractor,
    state_manager=state_manager,
    turn_manager=turn_manager,
    enable_state_management=True,
    enable_turn_management=True
)
```

### Demo Mode Integration Pattern (Simplified Testing)
```python
# Simplified demo pattern - DM only, no GD
from demo_terminal import create_demo_session_manager, DemoTerminal

# Create demo session manager (bypasses GD agent)
session_manager = create_demo_session_manager(dm_model_name='gemini-2.5-flash')

# Use demo processing method
result = await session_manager.demo_process_player_input(
    new_messages=[chat_message]
)

# Access responses and usage
responses = result["responses"]  # List of DM narrative responses
usage = result["usage"]          # Token usage tracking
```

### Turn Management Pattern
```python
# Start new turn with action declarations
turn_manager.start_and_queue_turns(
    actions=[
        ActionDeclaration(speaker="Hero", content="I attack the goblin"),
        ActionDeclaration(speaker="Goblin", content="I cast Shield as a reaction")
    ]
)

# Get turn context for current turn
current_turn = turn_manager.get_current_turn_context()

# Update processing turn reference before marking messages as responded
turn_manager.update_processing_turn_to_current()
turn_manager.mark_new_messages_as_responded()

# Get snapshot for context builders
snapshot = turn_manager.get_snapshot()
context = dm_context_builder.build_demo_context(turn_manager_snapshots=snapshot)
```

### Message Data Types & Flow

1. **ChatMessage** (`src/models/chat_message.py`): Frontend-backend communication
   - Contains `player_id`, `character_id`, `text`, `timestamp`, `message_type`
   - Factory methods: `create_player_message()`, `create_dm_message()`, `create_system_message()`

2. **TurnMessage** (`src/models/turn_message.py`): Turn-based context management
   - Contains `speaker`, `content`, `message_type`, `turn_origin`, `timestamp`, `responded`
   - Types: `LIVE_MESSAGE` (active conversation) vs `COMPLETED_SUBTURN` (condensed summaries)
   - Used by TurnContext to track messages within turns
   - Filter by `responded` flag to identify new vs processed messages

3. **ActionDeclaration** (`src/memory/turn_manager.py`): Turn initialization
   - Simple structure: `speaker` and `content`
   - Used when starting new turns/reactions with `start_and_queue_turns()`

4. **TurnContext** (`src/models/turn_context.py`): Turn state container
   - Contains turn metadata, messages list, active character, step objectives
   - Methods: `add_message()`, `get_turn_summary()`, `get_snapshot()` (immutable view)
   - Hierarchical: parent/child relationships for nested reactions

5. **Agent Response Types**:
   - `DungeonMasterResponse`: `narrative` (str), `step_complete` (bool)
   - `GameflowDirectorResponse`: `new_game_step_objective` (str), `game_state_update_required` (bool)
   - `StateExtractionResult`: Structured state changes (HP, conditions, resources, detected events)

### Key Architectural Decisions

- **Multi-Agent Orchestration**: SessionManager coordinates multiple specialized agents (GD, DM, StateExtractor) instead of a single monolithic agent
- **Separation of Concerns**:
  - **Gameflow Director**: Game flow management and step objectives
  - **Dungeon Master**: Narrative generation and rule adjudication
  - **State Extractor**: State change extraction from completed narratives
- **Context Builder Specialization**: Each agent receives tailored context from dedicated context builders
- **Turn-Based Context Isolation**:
  - StateExtractor sees only current turn (prevents duplicate extractions)
  - DM sees full chronological history with nested turn structure
  - GD sees history + current turn + step objectives
- **Hierarchical Turn Management**: Stack-based turn/subturn tracking for complex reaction chains
- **Turn Condensation**: Completed turns compressed into structured summaries to manage context size while preserving narrative
- **Tool-Based Turn Coordination**: DM agent can declare reactions via `start_and_queue_turns` tool call
- **Dual Operating Modes**: Full multi-agent mode (`main.py`) and simplified demo mode (`demo_terminal.py`) for testing
- **Structured Outputs**: All agents use PydanticAI structured output types for reliability and type safety
- **Player Character Registry**: Maps player IDs to character names for multi-player session support

## Development Workflow Notes

### Important Guidelines
- **Always run with uv**: Use `uv run python` instead of plain `python` for consistent dependency management and virtual environment setup
- **Start with demo mode**: Use `demo_terminal.py` for rapid iteration when testing DM narrative generation
- **Test turn management**: Use `/turn`, `/history`, `/stats` commands in demo terminal to inspect turn state
- **Context inspection**: Use `/context` command to see exactly what context the DM receives

### Architecture Documentation
- **design/architecture.md**: Multi-agent system overview (GD + DM coordination)
- **design/TurnManagement.md**: Turn management system details
- **design/combat_architecture_analysis.md**: Combat flow analysis and recommendations
- **design/reaction_architecture_documentation.md**: Reaction handling architecture
- **design/step_completion_gm_pattern.md**: Step completion patterns

### Common Development Tasks
- **Adding new agent**: Create agent file in `src/agents/`, add factory function, create corresponding context builder in `src/context/`
- **Modifying turn behavior**: Update `src/memory/turn_manager.py` and corresponding tests in `tests/TurnManager tests/`
- **Adding rules**: Add markdown files to `rules/` directory, run embedding script to update vector database
- **Testing multi-agent flow**: Run full CLI (`src/main.py`) or create integration test in `tests/`