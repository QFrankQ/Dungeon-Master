# D&D Dungeon Master AI Assistant

An intelligent AI Dungeon Master powered by Google's Gemini models that can run interactive D&D 5e sessions with sophisticated rule enforcement, memory management, and combat mechanics.

## What Is This?

This project provides an AI-powered Dungeon Master that can:
- Run full D&D 5e campaigns with proper rule enforcement
- Track character stats, HP, spell slots, and other resources in real-time
- Manage complex combat encounters with turn-based mechanics
- Remember conversation history and maintain campaign continuity
- Look up rules from a comprehensive D&D 5e knowledge base
- Roll dice and arbitrate game mechanics fairly

Whether you're a solo player looking for a DM, want to practice your character, or need a co-DM for complex encounters, this AI assistant has you covered.

## Features

### Intelligent Game Management
- **Natural Language Processing**: Describe your actions naturally, and the AI understands your intent
- **Rule-Based Arbitration**: Uses a vector database of D&D 5e combat rules for accurate rulings
- **Dynamic Storytelling**: Creates engaging narratives while maintaining mechanical accuracy

### Combat & Character Tracking
- **Real-Time State Management**: Automatically tracks HP, spell slots, hit dice, and status effects
- **Turn-Based Combat**: Structured combat flow with proper action resolution
- **Multi-Character Support**: Manages parties and multiple enemies simultaneously

### Smart Memory System
- **Conversation History**: Remembers what happened in previous sessions
- **Intelligent Summarization**: Condenses long conversations while preserving key details
- **Token Management**: Automatically manages context limits for optimal performance

### Dual Interface Options
- **Web Interface**: Beautiful browser-based UI for visual gameplay
- **CLI Interface**: Lightweight command-line option for terminal enthusiasts

## Architecture Overview

The system follows a clean, modular design with fixed turn-based progression:

```
+-------------------------------------------------------------+
|                     User Interface Layer                    |
|               (Web Browser or Command Line)                 |
+-----------------------------+-------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                      Session Manager                        |
|  - Orchestrates entire game session                         |
|  - Manages conversation flow and turn progression           |
|  - Coordinates all subsystems                               |
+--------+--------------------+------------------+------------+
         |                    |                  |
         v                    v                  v
+---------------+   +------------------+   +------------------+
|   Message     |   |     Memory       |   |  State Manager   |
|  Processing   |   |   Management     |   |                  |
|               |   |                  |   |  - HP tracking   |
| - Formats     |   | - History        |   |  - Spell slots   |
|   player      |   |   storage        |   |  - Resources     |
|   actions     |   | - Auto-          |   |  - Effects       |
| - Structures  |   |   summarize      |   |                  |
|   context     |   |                  |   |                  |
+---------------+   +------------------+   +------------------+
         |                    |                  |
         +--------------------+------------------+
                              |
                              v
+-------------------------------------------------------------+
|                   Dungeon Master Agent                      |
|                  (Google Gemini 2.5 Flash)                  |
+------------+-------------------------------+----------------+
             |                               |
             v                               v
+----------------------+      +-----------------------------+
|   Vector Database    |      |      Dice Rolling Tool      |
|                      |      |                             |
| - 442 D&D 5e rules   |      | - Configurable dice         |
| - Semantic search    |      | - Advantage/disadvantage    |
| - Tagged content     |      |                             |
+----------------------+      +-----------------------------+
```

### Key Components

#### Session Manager (Orchestrator)
The central coordinator that manages the entire game session. It handles:
- Processing user input through fixed turn steps
- Coordinating between message processing, memory, and state management
- Ensuring proper game flow and turn progression
- Maintaining session context and game state

#### Message Processing System
Transforms messages between different formats for optimal processing:
- Separates player actions from character status information
- Creates structured input for the AI with relevant context
- Filters messages to keep history clean and focused

#### Memory Management System
Keeps track of the campaign narrative while managing resource constraints:
- Stores conversation history efficiently
- Automatically summarizes old content when limits are reached
- Maintains token budgets (10k max, 5k minimum before summarization)

#### State Management System
Tracks the mechanical aspects of the game in real-time:
- HP and resource changes (spell slots, hit dice, item uses)
- Status effects and conditions
- Combat state and turn order
- Character statistics and inventory

#### Dungeon Master Agent
The AI brain powered by Google's Gemini models:
- Generates narrative responses and describes outcomes
- Makes rulings based on D&D 5e rules
- Creates engaging stories while maintaining game balance
- Uses tools for dice rolling and rule lookup

#### Vector Database (Rule Lookup)
A searchable knowledge base of D&D 5e rules:
- 442 lines of comprehensive combat rules
- Semantic search for contextually relevant rulings
- Tagged content for precise retrieval

## Quick Start

### Prerequisites
- Python 3.11 or higher
- `uv` package manager (recommended) or `pip`
- Google Gemini API key
- Qdrant API key (for vector database)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd DnD
   ```

2. **Set up environment variables**

   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   QDRANT_API_KEY=your_qdrant_api_key_here
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

   Or with pip:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

#### Web Interface (Recommended)
Start the Flask web server:
```bash
uv run python src/app.py
```

Then open your browser to `http://localhost:5001`

#### Command Line Interface
Start the CLI:
```bash
uv run python src/main.py
```

Available commands:
- `clear`: Reset conversation memory and start fresh
- `exit` or `quit`: End the session

## Usage Examples

### Starting a Combat Encounter
```
You: I draw my sword and charge at the goblin!

DM: Roll for initiative! *rolls d20* You rolled a 16.
The goblin rolls a 12. You go first!

You take your action. Describe your attack!

You: I swing my longsword at the goblin's head!

DM: *You rolled 18 to hit* That's a hit! *rolls 1d8+3 for damage*
You deal 7 slashing damage to the goblin!

The goblin now has 3 HP remaining. It's badly wounded...
```

### Spell Casting with Resource Tracking
```
You: I cast Magic Missile at 1st level at the orc!

DM: *Tracking: You use 1 first-level spell slot*

Three darts of magical force streak toward the orc!
*Rolling 3d4+3* The missiles deal 11 force damage!

You have 2 first-level spell slots remaining.
```

### Memory and Context
The AI remembers previous conversations:
```
You: I return to the tavern we visited yesterday.

DM: You push open the door of the Prancing Pony.
The innkeeper recognizes you from yesterday and waves...
```

## Project Structure

```
DnD/
├── src/
│   ├── agents/              # AI agent definitions and tools
│   ├── memory/              # Session and memory management
│   ├── models/              # Data models and structures
│   ├── services/            # Message processing services
│   ├── db/                  # Vector database and rules
│   ├── characters/          # Character data and templates
│   ├── static/              # Web interface assets (CSS/JS)
│   ├── templates/           # HTML templates
│   ├── app.py              # Flask web server
│   └── main.py             # CLI entry point
├── tests/                   # Unit and integration tests
├── .env                     # Environment variables (not committed)
└── README.md               # This file
```

## Configuration

### Memory Settings
Adjust token limits in `src/memory/config.py`:
- `max_token_threshold`: Maximum tokens before summarization (default: 10,000)
- `min_token_threshold`: Minimum tokens to retain (default: 5,000)

### AI Model Selection
The system uses two Gemini models:
- **Gemini 2.5 Flash**: Main DM responses (fast, high-quality)
- **Gemini 1.5 Flash**: Summarization (efficient for compression)

## Testing

Run the test suite:
```bash
# All tests
uv run pytest

# Verbose output
uv run pytest -v

# Specific test file
uv run pytest tests/test_state_extraction.py

# Tests matching a pattern
uv run pytest -k "memory"
```

## Development

### Setting Up Vector Database
If you need to rebuild the vector database:
```bash
# Prepare embeddings
uv run python src/db/prepare_embeddings.py

# Upload to Qdrant
uv run python src/db/upload_to_vector_DB.py

# Test the database
uv run python src/db/test_vector_db.py
```

### Contributing
Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Technical Stack

- **AI Framework**: PydanticAI for structured agent development
- **Language Models**: Google Gemini (2.5 Flash & 1.5 Flash)
- **Vector Database**: Qdrant with semantic search
- **Web Framework**: Flask with modular JavaScript frontend
- **Data Validation**: Pydantic v2 for type safety
- **Testing**: pytest for comprehensive test coverage

## Roadmap

Future enhancements planned:
- [ ] Support for non-combat encounters and social interactions
- [ ] Campaign persistence and save/load functionality
- [ ] Multi-player support with DM oversight mode
- [ ] Integration with D&D Beyond character sheets
- [ ] Voice interaction capabilities
- [ ] Custom rule sets and homebrew content support

## License

[Add your license here]

## Acknowledgments

- Built with [PydanticAI](https://ai.pydantic.dev/)
- Powered by Google's [Gemini models](https://deepmind.google/technologies/gemini/)
- D&D 5e rules and content are property of Wizards of the Coast

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing documentation in `CLAUDE.md`
- Review test files for usage examples

---

*Happy adventuring! May your rolls be high and your campaigns epic!*
