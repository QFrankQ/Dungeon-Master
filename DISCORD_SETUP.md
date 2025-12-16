# Discord Bot Setup Guide

This guide walks you through setting up and running the D&D Dungeon Master Discord bot.

## Phase 1: Basic Discord Bot (Current Implementation)

### Prerequisites

1. **Python 3.11+** with `uv` package manager
2. **Discord Account** to create the bot application
3. **Gemini API Key** (free tier works fine)

---

## Step 1: Create Discord Bot Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name (e.g., "D&D DM AI")
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot" and confirm
5. **⚠️ IMPORTANT**: Under "Privileged Gateway Intents", enable:
   - ✅ **MESSAGE CONTENT INTENT** (REQUIRED - bot won't work without this!)
   - Click "Save Changes" at the bottom after enabling
6. Click "Reset Token" and copy your bot token (you'll need this later)
7. Save the Application ID from the "General Information" page

---

## Step 2: Generate Bot Invite URL

1. Go to "OAuth2" → "URL Generator" in the left sidebar
2. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select bot permissions:
   - ✅ Send Messages
   - ✅ Send Messages in Threads
   - ✅ Embed Links
   - ✅ Read Message History
   - ✅ Use Slash Commands
4. Copy the generated URL at the bottom
5. Open the URL in your browser and invite the bot to your Discord server

---

## Step 3: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```bash
   DISCORD_BOT_TOKEN=your_bot_token_from_step_1
   DISCORD_APPLICATION_ID=your_application_id_from_step_1
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. Get a Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey) (free tier)

---

## Step 4: Install Dependencies

```bash
# Install dependencies using uv
uv sync

# Or if you need to add discord.py manually:
uv pip install discord.py>=2.3.0
```

---

## Step 5: Run the Bot

```bash
# Run the Discord bot
uv run python src/discord/bot.py
```

You should see output like:
```
✓ Bot connected as YourBotName (ID: ...)
✓ Connected to 1 guild(s)
✓ Synced 12 command(s)
✓ D&D Dungeon Master Bot is ready!
```

---

## Step 6: Use the Bot in Discord

1. Go to your Discord server where you invited the bot
2. In any channel, type `/start` to begin a game session
3. Register a character with `/register fighter` (or wizard, cleric)
4. Start playing by just typing messages!

### Example Session

```
/start
✓ Bot responds with welcome message

/register fighter
✓ Bot confirms registration

Player: "I look around the room"
DM: "You find yourself in a dimly lit tavern..."

Player: "I attack the goblin with my sword"
DM: "Roll for attack! ... You hit! Roll 1d8+3 for damage..."
```

---

## Available Commands

### Session Management
- `/start` - Start a game session in current channel
- `/end` - End the current session

### Character Management
- `/register <character_id>` - Register a character (fighter, wizard, cleric)
- `/character` - View your character stats
- `/switch <character_id>` - Switch characters
- `/who` - Show available characters

### Game Information
- `/turn` - Show current turn info
- `/history` - Show completed turns
- `/stats` - Show turn manager statistics
- `/context` - View DM context (debug)
- `/usage` - Show token usage
- `/help` - Show help message

---

## Troubleshooting

### ❌ "Privileged intents that have not been explicitly enabled" error

**This is the most common error!**

**Solution**: Go to [Discord Developer Portal](https://discord.com/developers/applications) → Your Application → Bot → Scroll down to "Privileged Gateway Intents" → Enable **MESSAGE CONTENT INTENT** → Click **Save Changes**

Without this enabled, the bot cannot read message content and will fail to start.

### Bot doesn't respond to messages
- Make sure MESSAGE CONTENT INTENT is enabled in Discord Developer Portal
- Check that the bot has permission to read/send messages in the channel
- Verify you started a session with `/start`

### "No character registered" error
- Run `/register <character_id>` first (available: fighter, wizard, cleric)

### Commands not showing up
- Wait a few minutes for Discord to sync slash commands
- Try kicking and re-inviting the bot

### ImportError or ModuleNotFoundError
- Make sure you're running with `uv run python src/discord/bot.py`
- Run `uv sync` to install all dependencies

---

## Phase 2: PostgreSQL Database (Optional)

Phase 2 adds persistent storage for multi-guild support and session persistence. This is **optional** - the bot works fine without it using Phase 1 in-memory storage.

### Prerequisites

- **Docker** and **Docker Compose** (for local PostgreSQL)
- OR a hosted PostgreSQL database (Railway, Render, etc.)

### Step 1: Start PostgreSQL

**Option A: Local with Docker (Recommended for Development)**
```bash
# Start PostgreSQL in Docker
docker-compose up -d postgres

# Verify it's running
docker ps
```

**Option B: Use Hosted PostgreSQL**
- Get a PostgreSQL database URL from your hosting provider
- Update `DATABASE_URL` in `.env` with your connection string

### Step 2: Install Database Dependencies

```bash
# Install Phase 2 dependencies
uv sync
```

### Step 3: Update Environment Variables

Add to your `.env` file:
```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://dnd:dev_password@localhost:5432/dnd_bot
```

### Step 4: Run Database Migrations

```bash
# Create all database tables
uv run alembic upgrade head
```

You should see output like:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial database schema
```

### Step 5: Run the Bot

```bash
# Same command as Phase 1
uv run python src/discord/bot.py
```

### What Phase 2 Adds

✅ **Multi-Guild Support**: Bot works in multiple Discord servers simultaneously with data isolation
✅ **Session Persistence**: Sessions are saved to database (ready for future resume-after-restart feature)
✅ **Guild Registry**: Each Discord server gets a database record
✅ **Graceful Degradation**: If database is unavailable, bot falls back to Phase 1 in-memory mode

### Database Management

**View database with pgAdmin (Optional)**:
```bash
# Start pgAdmin
docker-compose --profile tools up -d

# Open http://localhost:5050
# Login: admin@dnd.local / admin
```

**Stop PostgreSQL**:
```bash
docker-compose down
```

**Reset database**:
```bash
# WARNING: Deletes all data!
docker-compose down -v
docker-compose up -d postgres
uv run alembic upgrade head
```

---

## Next Steps (Future Phases)

Phase 3 will add:
- BYOK (Bring Your Own Key) system for Gemini API
- Per-user or per-guild API keys
- Encrypted storage of API keys

Phase 4 will add:
- Custom character creation via JSON templates
- Character import/export
- Per-player character storage in database

---

## Architecture Notes

### Current Implementation (Phase 1)

- **In-memory sessions**: Each channel can have one active session
- **Temporary character files**: Character state is stored in temp directories (cleaned on `/end`)
- **No persistence**: Sessions are lost when bot restarts
- **Feature parity with demo_terminal.py**: All terminal commands work in Discord

### Key Files

- `src/discord/bot.py` - Main bot entry point
- `src/discord/cogs/session_commands.py` - /start, /end, on_message handler
- `src/discord/cogs/game_commands.py` - /turn, /history, /stats, /context, /help
- `src/discord/cogs/character_commands.py` - /character, /register, /switch, /who
- `src/discord/utils/session_pool.py` - Manages SessionManager instances per channel
- `src/discord/utils/message_converter.py` - Converts Discord messages to ChatMessage format

---

## Support

For issues, check:
1. This setup guide
2. The plan file at `.claude/plans/wondrous-rolling-fern.md`
3. Existing `demo_terminal.py` for reference implementation

Have fun DMing on Discord! 🎲🗡️🛡️
