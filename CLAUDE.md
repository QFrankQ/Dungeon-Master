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

- **Agent System** (`src/agents/`): Pure AI response generation and state extraction
  - **DM Agent**: `agents.py` - `DungeonMasterAgent` class for narrative generation (no session management)
  - **4-Agent State Extraction Architecture**: Specialized agents for extracting game state changes
    - `hp_agent.py`: **HPAgent** - Extracts HP changes (damage, healing, temp HP) from HP_CHANGE events
    - `effect_agent.py`: **EffectAgent** - Extracts conditions and spell effects from EFFECT_APPLIED events
    - `resource_agent.py`: **ResourceAgent** - Extracts spell slots, items, hit dice from RESOURCE_USAGE events
    - `lifecycle_agent.py`: **LifecycleAgent** - Extracts death saves and rests from STATE_CHANGE events
    - `event_detector.py`: **EventDetectorAgent** - Detects which event types occurred in narrative
    - `state_extraction_orchestrator.py`: **StateExtractionOrchestrator** - Coordinates all agents and converts commands to state updates
  - **Deprecated Extractors** (replaced by 4-agent architecture):
    - `combat_state_extractor.py`: ⚠️ DEPRECATED - Use HPAgent + LifecycleAgent instead
    - `resource_extractor.py`: ⚠️ DEPRECATED - Use ResourceAgent instead
  - `prompts.py`: Agent instructions including combat arbiter prompts and specialized extraction instructions
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

- **Turn Management System** (`src/memory/`, `src/agents/`, `src/models/`): **Hierarchical combat turn tracking with context isolation**
  - `turn_manager.py`: **Core turn orchestration** - manages hierarchical turn/sub-turn stack with context isolation for state extraction
  - `turn_condensation_agent.py`: AI agent that condenses completed turns into structured action-resolution summaries for storytelling
  - `dm_context_builder.py`: Builds comprehensive chronological context for DM with full turn hierarchy and nested structure
  - `state_extractor_context_builder.py`: Builds isolated context for state extraction (current turn only) to prevent duplicate extractions
  - `turn_message.py`: Message types (LIVE_MESSAGE, COMPLETED_SUBTURN) with selective filtering for different consumers

- **Vector Database & Knowledge** (`src/db/`): **LanceDB-based rule storage with automatic reference expansion**
  - `lance_rules_service.py`: **Primary vector service** - LanceDB integration with 2,804 embedded D&D rules, automatic reference expansion, and name-based lookups
  - `vector_service.py`: Legacy Qdrant integration (deprecated, being replaced by LanceDB)
  - `combat_rules.json`: 442-line procedural D&D 5e combat rules (not yet integrated into vector DB)
  - `rendered_rules/`: 2,804 rendered D&D rules in markdown format
  - `metadata/`: JSON metadata for each rule with references and tags
  - **Note**: Vector services are NOT yet integrated into the agent - all imports are commented out in `agents.py`

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

- **Utility Scripts** (`scripts/`):
  - `scripts/db/`: Database-related utilities
    - `build_lance_rules_db.py`: Build/rebuild LanceDB from rendered rules
    - `analyze_dangling_references.py`: Identify missing referenced rules
    - `example_lance_usage.py`: Example queries and usage patterns
    - `output/`: Generated reports and analysis (gitignored)

## Development Setup

### Dependencies
The project uses `uv` for dependency management with Python 3.11+. Key dependencies:
- `google-genai` (v1.26.0+): Google Gemini API client
- `pydantic-ai` (v0.4.6+): AI agent framework
- `pydantic` (v2.11.7+): Data validation
- `lancedb` (v0.5.0+): Local vector database with automatic reference expansion
- `qdrant-client` (v1.15.0+): Legacy vector database client (deprecated)
- `flask`: Web interface

### Environment Variables
**Required:**
- `GEMINI_API_KEY` or `GOOGLE_API_KEY`: Google Gemini API access (free tier)

**Optional:**
- `GEMINI_API_KEY_PAID_TIER` or `GOOGLE_API_KEY_PAID_TIER`: Higher rate limit API key for database building (1500 req/min vs 15)
- `QDRANT_API_KEY`: Legacy Qdrant vector database operations (deprecated)

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

**LanceDB vector database operations:**
```bash
# Build/rebuild the rules database (uses paid tier API if available)
uv run python scripts/db/build_lance_rules_db.py

# Test mode - process only first 10 entries
uv run python scripts/db/build_lance_rules_db.py --limit 10

# Analyze dangling references (rules referenced but not in dataset)
uv run python scripts/db/analyze_dangling_references.py

# Example usage and testing
uv run python scripts/db/example_lance_usage.py

# Legacy Qdrant testing (deprecated)
uv run python src/db/test_vector_db.py
```

**Run tests:**
```bash
uv run pytest
uv run pytest -v  # verbose output
uv run pytest path/to/specific_test.py  # single test file
uv run pytest tests/ -k "memory"  # run memory-related tests
uv run pytest tests/test_lance_rules_service.py  # test LanceDB service
```

**IMPORTANT - Test Execution:**
- ALWAYS use `uv run` for running tests (e.g., `uv run pytest` or `uv run python -m pytest`)
- The `-m` flag is fine as long as you use `uv run` (e.g., `uv run python -m pytest tests/`)
- **Note**: `uv` is installed at `/Users/frankchiu/.local/bin/uv`. If not in PATH, use:
  - Full path: `/Users/frankchiu/.local/bin/uv run pytest ...`
  - Or add to PATH: `PATH="$HOME/.local/bin:$PATH" uv run pytest ...`
  - Or use: `.venv/bin/python -m pytest ...` (also valid)
- Never run tests with plain `pytest` or `python -m pytest` without `uv run` or proper environment setup

**Test turn management:**
```bash
uv run python test_turn_management.py  # comprehensive turn system testing
uv run python minimal_turn_test.py     # minimal turn functionality test
```

**Utility Scripts** (`scripts/db/`):
- All database utility scripts are organized in `scripts/db/`
- Generated reports go to `scripts/db/output/` (gitignored)

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

### Turn Management System (Combat Architecture)
- **Hierarchical turn tracking**: Stack-based turn/sub-turn management (Level 0=main turns, Level 1+=sub-turns/reactions)
- **Context isolation**: Each turn maintains isolated context to prevent duplicate state extractions
- **Action resolution vs turn conclusion separation**: `resolve_action()` handles immediate state updates, `end_turn()` handles cleanup only
- **Turn condensation**: AI-powered compression of completed turns into structured action-resolution summaries with narrative preservation
- **Dual context builders**: DM gets full chronological context, StateExtractor gets isolated current-turn context
- **Message type filtering**: LIVE_MESSAGE vs COMPLETED_SUBTURN with selective filtering for different consumers

### Vector Search Integration (LanceDB)
**Current Status**: Rules database fully built and tested, but NOT yet integrated into agent (imports commented out in `agents.py`)

**Architecture**:
- **LanceDB local vector database**: 2,804 D&D rules embedded using `gemini-embedding-001` (768-dim vectors)
- **Hybrid search**: Combines semantic vector search with full-text search (FTS) using reciprocal rank fusion (RRF)
  - Best results for both conceptual queries ("how does advantage work?") and keyword queries ("Shield spell")
  - FTS index created on `content` column during database build
- **Automatic reference expansion**: Queries return related rules (e.g., "Fireball" also returns "Sphere", "burning", etc.)
- **Dual-tier API support**:
  - Free tier (`GEMINI_API_KEY`) for queries (15 req/min)
  - Paid tier (`GEMINI_API_KEY_PAID_TIER`) for building database (1500 req/min)
- **In-memory name index**: O(1) lookup by rule name without requiring source code
- **Reference validation**: All 2,544 valid references validated, 1,462 dangling references identified
- **Type filtering**: Filter by spell, item, condition, action, feat, etc.

**Key Methods**:
```python
service = create_lance_rules_service()

# Hybrid search (vector + full-text) with reference expansion
results = service.search("How does fireball work?", limit=3, expand_references=True)

# Name-based lookup (no source code needed)
entry = service.get_by_name('Shield', entry_type='spell')  # Returns Shield spell

# Direct ID lookup (requires source)
entry = service.get_by_id('Fireball|XPHB')
```

**Data Sources**:
- `rendered_rules/`: 2,804 markdown-formatted rules
- `metadata/`: JSON metadata with references, tags, levels, schools, rarity
- `lancedb/rules.lance/`: Vector database with embeddings (gitignored)

**Legacy**: Qdrant integration (`vector_service.py`) is deprecated but still present

### Rules Caching System (Turn-Based LanceDB Integration)
**Status**: Fully implemented and integrated with DM agent and state extraction

The caching system provides efficient D&D rule lookup with hierarchical turn-based caching to minimize redundant LanceDB queries and ensure consistency within combat turns.

#### Two-Phase Architecture

**Phase 1: DM Proactive Caching**
- DM agent queries LanceDB via `query_rules_database` tool when needing rule context
- Tool performs hybrid search (exact name match → semantic search fallback)
- Results cached in `current_turn.metadata["rules_cache"]` for reuse
- Cache stores ALL rule types (spells, items, conditions, actions, etc.)

**Phase 2: EffectAgent Reactive Consumption**
- RulesCacheService merges cache from turn hierarchy snapshot
- EffectAgentContextBuilder filters cache to effect/condition types only
- EffectAgent receives formatted context with `=== KNOWN EFFECTS ===` section
- Agent uses cached descriptions when available, generates custom descriptions otherwise

#### Core Components

**RulesCacheService** (`src/services/rules_cache_service.py`):
- `merge_cache_from_snapshot(active_turns_by_level)` - Merges cache from snapshot's active turns
- `filter_cache_by_types(cache, entry_types)` - Filters cache to specific types (e.g., ["spell", "condition"])
- `add_to_cache(rule_entry, turn_context)` - Helper for DM tool to add cache entries

**DM Tools** (`src/agents/dm_tools.py`):
- `query_rules_database(query, limit=3)` - DM tool for LanceDB queries with auto-detect
  - **Auto-detect**: Short queries (≤10 words) try exact match first, long queries use hybrid search
  - **limit**: Maximum number of results to return (default 3, max 10)
  - **Hybrid search**: Vector similarity + full-text search with automatic reciprocal rank fusion
- `DMToolsDependencies` - Dependency injection container for tools
- Tool caches all results automatically in current turn's metadata

**EffectAgentContextBuilder** (`src/context/effect_agent_context_builder.py`):
- `build_context(narrative, active_turns_by_level, game_context)` - Builds formatted context
- Merges cache from snapshot and filters to effect/condition/spell types
- Formats `=== KNOWN EFFECTS ===` section with cached rule descriptions
- Follows same pattern as StateExtractorContextBuilder and DMContextBuilder

#### Cache Storage Structure

**Location**: `TurnContext.metadata["rules_cache"]`

**Schema**:
```python
{
    "rules_cache": {  # Stores ALL rule types
        "bless": {  # Normalized lowercase key
            "name": "Bless",
            "entry_type": "spell",  # Type: spell, item, condition, action, etc.
            "description": "Whenever you make an attack roll or saving throw...",
            "summary": "+1d4 to attack rolls and saving throws",
            "duration_type": "concentration",
            "duration": 10,
            "effect_type": "buff",
            "source": "lancedb",  # or "llm_generated"
            # Additional fields from LanceDB...
        },
        "poisoned": {
            "name": "Poisoned",
            "entry_type": "condition",
            "description": "A poisoned creature has disadvantage...",
            "source": "lancedb"
        }
    }
}
```

#### Hierarchical Inheritance Rules

Cache inherits from parent turns but NOT sibling turns:

```
Turn 1 (Level 0)
├─ Cache: {bless, haste}
└─ Turn 1.1 (sub-turn)
   ├─ Inherits: {bless, haste} from parent
   ├─ Adds: {shield}
   └─ Turn 1.1.1 (nested sub-turn)
      └─ Inherits: {bless, haste, shield} from parents

Turn 1.2 (sibling sub-turn)
└─ Inherits: {bless, haste} from parent ONLY (NOT shield from sibling 1.1)

Turn 2 (new Level 0)
└─ Cache: {} (cleared, starts fresh)
```

**Key Rules**:
- Child turns inherit parent cache
- Siblings do NOT share cache
- Cache cleared between main turns (Level 0)
- Normalized keys (lowercase) prevent duplicates

#### Integration Patterns

**DM Agent with Tools** (in `demo_terminal.py` or `session_manager.py`):
```python
from src.agents.dm_tools import create_dm_tools
from src.services.rules_cache_service import create_rules_cache_service
from src.db.lance_rules_service import create_lance_rules_service

# Create services
lance_service = create_lance_rules_service()
rules_cache_service = create_rules_cache_service()

# Create DM tools and dependencies
dm_tools, dm_deps = create_dm_tools(
    lance_service=lance_service,
    turn_manager=turn_manager,
    rules_cache_service=rules_cache_service
)

# Create DM agent with tools
dm_agent = create_dungeon_master_agent(
    model_name="gemini-2.5-flash",
    tools=[turn_manager.start_and_queue_turns] + dm_tools
)

# Store dm_deps for passing to process_message()
dm_agent.dm_deps = dm_deps

# When calling DM - pass deps for tool dependency injection
result = await dm_agent.process_message(context, deps=dm_deps)
```

**StateExtractionOrchestrator** (in `session_manager.py`):
```python
# Create orchestrator - all services created internally
orchestrator = create_state_extraction_orchestrator(
    model_name="gemini-2.5-flash-lite"  # Optional, defaults to this
)

# Extract state changes with snapshot for effect caching
snapshot = turn_manager.get_snapshot()
result = await orchestrator.extract_state_changes(
    formatted_turn_context=context,
    game_context={"turn_id": "1.2", "active_character": "Alice"},
    turn_snapshot=snapshot  # Provides active_turns_by_level for cache merging
)

# The orchestrator creates internally:
# - EventDetector, CombatStateExtractor, ResourceExtractor, EffectAgent
# - RulesCacheService and EffectAgentContextBuilder
```

#### PydanticAI Tool Dependency Injection

**How it works**: The `ctx: RunContext[DMToolsDependencies]` parameter is automatically populated by PydanticAI.

**Flow**:
1. Define tool with `ctx: RunContext[DepsClass]` as first parameter
2. LLM calls tool with only non-context parameters (e.g., `query="Bless"`)
3. PydanticAI injects `ctx` with deps from `agent.run(deps=...)`
4. Tool accesses dependencies via `ctx.deps.lance_service`, etc.

**Example**:
```python
async def query_rules_database(
    ctx: RunContext[DMToolsDependencies],  # ← Auto-injected by PydanticAI
    query: str,  # ← Passed by LLM
    search_type: str = "hybrid"  # ← Passed by LLM
) -> str:
    # Access dependencies
    lance_service = ctx.deps.lance_service
    turn_manager = ctx.deps.turn_manager
    # ... use them
```

**Note**: The LLM never sees `ctx` - it only sees `query` and `limit` in the tool signature.

#### Usage Examples

**Single rule by name:**
```python
# Short query (≤10 words) - tries exact match first
>>> await query_rules_database(ctx, "Bless")
"Bless (Spell, Level 1)
=================
Whenever you make an attack roll or saving throw..."
```

**Multi-concept query:**
```python
# Short query with multiple keywords - exact match fails, uses hybrid search
>>> await query_rules_database(ctx, "bonus action fireball concentration", limit=5)
"Bonus Action (Action)
====================
...

---

Fireball (Spell, Level 3)
=========================
...

---

Concentration (Variantrule)
===========================
..."
```

**Natural language query:**
```python
# Long query (>10 words) - skips exact match, uses hybrid search directly
>>> await query_rules_database(ctx, "how does spellcasting work and what are the components?", limit=10)
"Spellcasting (Variantrule)
===========================
...

---

Components (Variantrule)
========================
..."
```

**Token Savings:**
- Single exact match: 0 embedding cost (O(1) lookup)
- Multi-result query: 1 embedding request for multiple related rules
- All results cached automatically for reuse within turn

#### Benefits

**Performance**:
- **70-80% token savings** for repeated effects (cached descriptions vs. LLM generation)
- **50-75% latency reduction** (cache lookup <1ms vs. LLM generation 1-2s)

**Consistency**:
- Same effect = same description within a turn (from LanceDB)
- Prevents narrative contradictions

**Accuracy**:
- LanceDB provides complete D&D RAW mechanics (2,804 rules)
- DM decides when to query DB (proactive caching)

**Flexibility**:
- Cache is optional - graceful degradation if LanceDB unavailable
- EffectAgent generates descriptions for uncached custom effects
- DM can override RAW with custom mechanics

#### Testing

**Tests**:
- `tests/test_rules_cache_service.py` (18 tests) - Cache merging and filtering
- `tests/test_dm_tools.py` (19 tests) - DM tool functionality
- `tests/test_effect_agent_context_builder.py` (21 tests) - Context building
- `tests/test_effect_agent.py::TestEffectCaching` (5 tests) - EffectAgent caching behavior

**Run caching tests**:
```bash
uv run pytest tests/test_rules_cache_service.py -v
uv run pytest tests/test_dm_tools.py -v
uv run pytest tests/test_effect_agent_context_builder.py -v
uv run pytest tests/test_effect_agent.py::TestEffectCaching -v
```

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

### Turn Management Integration Pattern (Combat Sessions)
```python
# For combat sessions with turn-based mechanics
turn_manager = TurnManager(state_extractor, turn_condensation_agent)

# Start a new turn
turn_id = await turn_manager.start_turn(
    active_character="Alice",
    turn_metadata={"initiative": 15, "combat_round": 2}
)

# Resolve actions during the turn (applies state changes immediately)
state_result = await turn_manager.resolve_action(
    action_context="Alice attacks with longsword",
    metadata={"damage_roll": 8}
)

# End turn (cleanup and condensation)
turn_result = await turn_manager.end_turn()
condensed_summary = turn_result["condensation_result"].condensed_summary
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

4. **TurnMessage** (`src/models/turn_message.py`): Turn-based context management
   - Contains `content`, `message_type`, `turn_origin`, `timestamp`
   - Types: `LIVE_MESSAGE` (active conversation) vs `COMPLETED_SUBTURN` (condensed results)
   - Factory methods: `create_live_message()`, `create_completed_subturn_message()`

### Key Architectural Decisions

- **Session-Centric Design**: SessionManager serves as the primary interface, owning and orchestrating all other components including the DM agent
- **Dependency Inversion**: High-level orchestrator (SessionManager) depends on low-level services (Agent, HistoryManager, StateManager) rather than the reverse
- **Pure Component Responsibilities**: Each component has a single, clear responsibility (Agent=AI responses, HistoryManager=memory, StateManager=game state)
- **History vs Context Separation**: Character status is contextual information (provided fresh each turn) but never stored in history (which only contains conversational content)
- **Content-Based Token Counting**: Token estimation reflects only the content actually stored in filtered history, not full conversation including tool calls
- **Unified Interface**: SessionManager provides consistent API regardless of underlying agent configuration or output format
- **Turn-Based Context Isolation**: StateExtractor sees only current turn context to prevent duplicate extractions, while DM sees full chronological context
- **Action Resolution Timing**: State changes applied during action resolution (proper D&D timing) rather than at turn end
- **Progressive Turn Condensation**: Completed turns condensed into structured summaries for efficient context management and narrative preservation

## Development Workflow Notes

- **Always run with uv**: Use `uv run python` instead of plain `python` for consistent dependency management and virtual environment setup

### LanceDB Implementation Notes

**Google GenAI API Compatibility:**
- The `task_type` parameter has been removed from `embed_content()` in recent Google GenAI SDK versions
- Do NOT use: `client.models.embed_content(..., task_type="RETRIEVAL_QUERY")`
- Use: `client.models.embed_content(model="gemini-embedding-001", contents=[text])`

**Name Index Performance:**
- The name index is built eagerly on `connect()` by fetching all entries and extracting name/type/id
- ~2,804 entries × 50 bytes ≈ 140KB memory overhead (negligible)
- Provides O(1) name lookups vs O(n) semantic search
- Use `get_by_name()` when you have the rule name but not the source code

**Reference Expansion:**
- References are validated and deduplicated during database build
- Cycle detection prevents infinite loops in recursive expansion
- 2,544 valid references, 1,462 dangling references (pointing to rules not in dataset)
- Use `expand_references=True` for context-rich results

**Hybrid Search:**
- The `search()` method automatically uses hybrid search combining vector and full-text search
- Uses reciprocal rank fusion (RRF) to merge results from both methods
- FTS index created on `content` column during database build
- Best results for both semantic queries ("how does advantage work?") and keyword queries ("Shield spell")
- Fully backward compatible - same API, just better quality results

**Database Statistics:**
- Total entries: 2,804
- Reference types: variantrule (1144), spell (396), action (343), condition (330), item (260), etc.
- Top sources: XPHB (Player's Handbook), XDMG (Dungeon Master's Guide), XMM (Monster Manual)