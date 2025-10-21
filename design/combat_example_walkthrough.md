# Combat Example: Action with Nested Reactions

This document walks through a concrete example of how the different components of the agentic dungeon master work together during combat, specifically showing one action with two reactions.

## Architecture Overview

**Key Design Principle:** The **Dungeon Master (DM)** is the primary endpoint that interacts with players. The **Gameflow Director (GD)** only activates when the DM signals that a game step is complete (`game_step_completed: True`).

**Processing Flow:**
1. Player input → DM processes and responds
2. IF DM signals step completion → GD activates to manage flow/state
3. GD sets new step objective → Loop back to DM with new objective
4. Continue until DM doesn't signal completion (waiting for player input)

**TurnStack Structure - Stack of Queues:**

The TurnStack is a **stack of queues**, not a simple stack. This structure enables:
- **Hierarchical turns:** Each level represents a nesting depth (Level 0 = main turns, Level 1 = reactions)
- **Sequential processing within a level:** Turns at the same level are queued and processed in order
- **Context building:** When building context, the system includes:
  - The **first turn (active or suspended)** from each parent level (for parent context)
  - The **first turn (active)** from the top level (currently processing)

**Example Stack of Queues Structure:**
```
Level 2 Queue: [Turn A ← ACTIVE, Turn B (queued)]  ← Top of stack
Level 1 Queue: [Turn C (SUSPENDED)]                 ← Parent context
Level 0 Queue: [Turn D (SUSPENDED)]                 ← Root context

Context for Turn A includes:
- Turn D context (Level 0, Queue[0])
- Turn C context (Level 1, Queue[0])
- Turn A context (Level 2, Queue[0])
```

When a turn completes:
1. **Dequeue** from front of current level's queue
2. If queue becomes empty → **pop entire level** from stack
3. Next queued turn in same level becomes active, OR
4. Parent turn (from level below) becomes active if no siblings remain

## Scenario Setup

**Characters:**
- **Aragorn** (Player Character, Fighter) - HP: 45/45, AC: 18
- **Goblin Scout** (Enemy) - HP: 7/7, AC: 13
- **Goblin Shaman** (Enemy) - HP: 15/15, AC: 12

**Situation:** Combat Round 2, Goblin Scout's turn just started. The turn is empty, waiting for action declaration.

**Initial TurnManager State:**
```
TurnStack (Stack of Queues):
Level 0 Queue: [Goblin Scout's Turn ← ACTIVE]

Details:
- active_character: "Goblin Scout"
- step_objective: "Prompt for and receive action declaration"
- messages: []  # Turn just started, empty
```

---

## Example Flow: Goblin Scout Attacks Aragorn (with 2 reactions)

### Step 0: DM Prompts for Action Declaration (Turn Start)

**Previous State:** End of previous turn, GD created new turn for Goblin Scout

**DM Context Builder provides:**
- **History:** Previous combat rounds
- **Turn Context:** Empty turn, just created
- **Current Step Objective:** "Prompt for and receive action declaration"
- **New Messages:** None (turn just started)

**DM Run #0:**

The DM prompts the player to declare the Goblin Scout's action.

**DM Output (DungeonMasterResponse):**
```python
{
    "narrative": "It's the Goblin Scout's turn. What action does the Goblin Scout take?",
    "game_step_completed": False  # NOT complete - waiting for player to declare action
}
```

**SessionManager Processing:**
- Adds DM prompt to TurnManager
- Returns narrative to player

**TurnManager State After DM Prompt:**
```
TurnStack:
├─ [Level 0] Turn: Goblin Scout's Turn
   └─ active_character: "Goblin Scout"
   └─ step_objective: "Prompt for and receive action declaration"
   └─ messages:
       └─ [LIVE_MESSAGE] "It's the Goblin Scout's turn. What action does the Goblin Scout take?"
```

---

### Step 1: PHASE 1 - Player Declares Action

**Player Input (ChatMessage):**
```python
player_message = ChatMessage(
    player_id="player_1",
    character_id="goblin_scout",
    text="Goblin Scout attacks Aragorn with his scimitar",
    message_type="player_action"
)
```

**SessionManager Processing:**

1. **Extract character info** from player_message:
   ```python
   character_name = player_character_registry.get_character_id_by_player_id("goblin_scout")
   # Returns: "Goblin Scout"
   ```

2. **Create message entry** (held temporarily, not yet added to TurnManager):
   ```python
   new_messages_holder = [{
       'player_message': player_message,
       'player_id': 'player_1',
       'character_id': 'Goblin Scout'
   }]
   ```

3. **Get TurnManager snapshot** (before adding new messages):
   ```python
   turn_manager_snapshot = turn_manager.get_snapshot()
   ```

**Current TurnManager Snapshot:**
```
TurnStack:
├─ [Level 0] Turn: Goblin Scout's Turn
   └─ active_character: "Goblin Scout"
   └─ step_objective: "Prompt for and receive action declaration"
   └─ messages:
       └─ [LIVE_MESSAGE] DM's previous prompt (from Step 0)
```

---

### Step 2: PHASE 2 - DM Receives Action Declaration

**DM Context Builder provides:**
```python
dungeon_master_context = dm_context_builder.build_context(
    turn_manager_snapshot=turn_manager_snapshot,
    new_message_entries=new_messages_holder
)
```

**DM Context includes:**
- **History:** Previous combat rounds
- **Turn Context:** DM's prompt for action
- **Current Step Objective:** "Prompt for and receive action declaration"
- **New Messages:** Player's attack declaration
- **Character States:** Current HP, AC, status effects

**DM Run #1:**

The DM acknowledges the action declaration and signals step complete.

**DM Output (DungeonMasterResponse):**
```python
{
    "narrative": "The Goblin Scout declares an attack against Aragorn with his scimitar!",
    "game_step_completed": True  # ✅ STEP COMPLETE - action declared
}
```

---

### Step 3: PHASE 4 - GD Activation (Step Complete)

**SessionManager Processing:**

1. **Add DM narrative to response queue:**
   ```python
   response_queue = [dungeon_master_response.narrative]
   ```

2. **Add DM narrative to new_messages_holder:**
   ```python
   new_messages_holder.append({
       'player_message': dungeon_master_response.narrative,
       'player_id': None,
       'character_id': "DM"
   })
   ```

3. **Check step completion:**
   ```python
   if dungeon_master_response.game_step_completed:  # TRUE - activate GD
       while dungeon_master_response.game_step_completed:
   ```

4. **Build GD context:**
   ```python
   turn_manager_snapshot = turn_manager.get_snapshot()  # Fresh snapshot
   gameflow_director_context = gd_context_builder.build_context(
       turn_manager_snapshot=turn_manager_snapshot,
       new_message_entries=new_messages_holder
   )
   ```

5. **Add messages to TurnManager BEFORE GD processes:**
   ```python
   for message_entry in new_messages_holder:
       turn_manager.add_new_message(
           new_message=message_entry["player_message"],
           speaker=message_entry["character_id"]
       )
   ```

**TurnManager State After Adding Messages:**
```
TurnStack:
├─ [Level 0] Turn: Goblin Scout's Turn
   └─ active_character: "Goblin Scout"
   └─ step_objective: "Prompt for and receive action declaration"
   └─ messages:
       ├─ [LIVE_MESSAGE] "It's the Goblin Scout's turn. What action does the Goblin Scout take?" (DM)
       ├─ [LIVE_MESSAGE] "Goblin Scout attacks Aragorn with his scimitar" (Player)
       └─ [LIVE_MESSAGE] "The Goblin Scout declares an attack against Aragorn..." (DM)
```

---

### Step 4: GD Processes Action Declaration and Sets Next Step

**GD Context includes:**
- **History:** Previous combat rounds
- **Turn Context:** Action declaration received
- **Current Step Objective:** "Prompt for and receive action declaration"
- **New Messages:** Player's declaration + DM's acknowledgment

**GD Run #1:**

The GD recognizes the action has been declared and moves to the next step: prompting for reactions.

**GD Output (GameflowDirectorResponse):**
```python
{
    "next_game_step_objectives": "Prompt for reactions to the attack, then resolve attack",
    "game_state_updates_required": False
}
```

**SessionManager Processing:**

1. **Set new step objective:**
   ```python
   turn_manager.set_next_step_objective(
       "Prompt for reactions to the attack, then resolve attack"
   )
   ```

2. **Clear new_messages_holder:**
   ```python
   new_messages_holder = []
   ```

3. **Continue while loop** - Build DM context with NEW objective

---

### Step 5: DM Prompts for Reactions (New Objective)

**DM Context Builder provides:**
- **History:** Previous combat
- **Turn Context:** Action declaration messages
- **Current Step Objective:** "Prompt for reactions to the attack, then resolve attack" ← NEW
- **New Messages:** None (new_messages_holder is empty)

**DM Run #2:**

The DM prompts for reactions based on the new objective.

**DM Output (DungeonMasterResponse):**
```python
{
    "narrative": "The Goblin Scout lunges forward, scimitar gleaming as it arcs toward Aragorn!\n\nBefore the blade connects, does anyone wish to use a reaction? Aragorn, you could use defensive abilities. Allies, you could cast protective spells or use other reactions.",
    "game_step_completed": False  # NOT complete - waiting for player reactions
}
```

**SessionManager Processing:**

1. **Add narrative to response queue:**
   ```python
   response_queue.append(dungeon_master_response.narrative)
   ```

2. **Add narrative to new_messages_holder:**
   ```python
   new_messages_holder.append({
       'player_message': dungeon_master_response.narrative,
       'player_id': None,
       'character_id': "DM"
   })
   ```

3. **Check step completion:**
   ```python
   while dungeon_master_response.game_step_completed:  # NOW FALSE - EXIT LOOP
   ```

4. **Add messages to TurnManager** (since step not complete):
   ```python
   for message_entry in new_messages_holder:
       turn_manager.add_new_message(...)
   ```

**TurnManager State After Adding Messages:**
```
TurnStack:
├─ [Level 0] Turn: Goblin Scout's Turn
   └─ active_character: "Goblin Scout"
   └─ step_objective: "Prompt for reactions to the attack, then resolve attack"
   └─ messages:
       ├─ [LIVE_MESSAGE] DM's initial prompt
       ├─ [LIVE_MESSAGE] Player's attack declaration
       ├─ [LIVE_MESSAGE] DM's acknowledgment
       └─ [LIVE_MESSAGE] DM's reaction prompt
```

5. **Return to player:**
   ```python
   return response_queue  # Contains BOTH narratives
   ```

**Response returned to player:**
```python
[
    "The Goblin Scout declares an attack against Aragorn with his scimitar!",
    "The Goblin Scout lunges forward, scimitar gleaming as it arcs toward Aragorn!..."
]
```

**⚠️ Important:** Player sees TWO narratives from a single input (action declaration triggered DM → GD → DM cycle)

---

### Step 6: Players Declare Reactions (New Input)

**Player Input (Multiple ChatMessages):**
```python
new_messages = [
    ChatMessage(
        player_id="player_2",
        character_id="aragorn",
        text="Aragorn uses Shield of Faith reaction (+2 AC)",
        message_type="reaction"
    ),
    ChatMessage(
        player_id="player_1",
        character_id="goblin_shaman",
        text="Goblin Shaman casts Shield spell on Goblin Scout (reaction, +5 AC)",
        message_type="reaction"
    )
]
```

**SessionManager Processing (PHASE 1 again):**

1. **Create message entries:**
   ```python
   new_messages_holder = [
       {'player_message': msg1, 'player_id': 'player_2', 'character_id': 'Aragorn'},
       {'player_message': msg2, 'player_id': 'player_1', 'character_id': 'Goblin Shaman'}
   ]
   ```

2. **Get snapshot:**
   ```python
   turn_manager_snapshot = turn_manager.get_snapshot()
   ```

---

### Step 7: PHASE 2 - DM Processes Reactions

**DM Context Builder provides:**
- **History:** Previous combat
- **Turn Context:** Attack declaration + previous DM prompt + NEW reaction declarations
- **Current Step Objective:** "Prompt for reactions to the attack, then resolve attack"
- **New Messages:** Both reaction declarations

**DM Run #3:**

The DM acknowledges reactions and signals completion of this step.

**DM Output (DungeonMasterResponse):**
```python
{
    "narrative": "Two reactions are declared:\n- Aragorn invokes Shield of Faith\n- Goblin Shaman prepares to cast Shield\n\nThese reactions will be resolved before the attack continues.",
    "game_step_completed": True  # ✅ STEP COMPLETE - triggers GD activation
}
```

---

### Step 8: PHASE 4 - GD Activation (Step Completion Loop Begins)

**SessionManager Processing:**

1. **Add DM narrative to response queue and new_messages_holder**

2. **Check step completion:**
   ```python
   if dungeon_master_response.game_step_completed:
       while dungeon_master_response.game_step_completed:
   ```

3. **Build GD context:**
   ```python
   turn_manager_snapshot = turn_manager.get_snapshot()  # Fresh snapshot
   gameflow_director_context = gd_context_builder.build_context(
       turn_manager_snapshot=turn_manager_snapshot,
       new_message_entries=new_messages_holder
   )
   ```

4. **⚠️ Add messages to TurnManager AFTER GD gets snapshot, BEFORE GD processes:**
   ```python
   for message_entry in new_messages_holder:
       turn_manager.add_new_message(
           new_message=message_entry["player_message"],
           speaker=message_entry["character_id"]
       )
   ```

**TurnManager State After Adding Messages:**
```
TurnStack:
├─ [Level 0] Turn: Goblin Scout's Attack
   └─ messages:
       ├─ [LIVE_MESSAGE] Attack declaration
       ├─ [LIVE_MESSAGE] DM prompt for reactions
       ├─ [LIVE_MESSAGE] "Aragorn uses Shield of Faith reaction"
       ├─ [LIVE_MESSAGE] "Goblin Shaman casts Shield spell"
       └─ [LIVE_MESSAGE] DM acknowledgment of reactions
```

---

### Step 9: GD Processes and Queues Reactions

**GD Context includes:**
- **History:** Combat history
- **Turn Context:** Full context with reaction declarations
- **Current Step Objective:** "Resolve attack declaration and prompt for reactions"
- **New Messages:** Reaction declarations + DM acknowledgment

**GD Run #2:**

The GD identifies that reactions need to be processed and uses tool calls.

**GD Tool Call:**
```python
start_and_queue_turns([
    {
        "active_character": "Aragorn",
        "turn_metadata": {"action_type": "reaction", "ability": "Shield of Faith"}
    },
    {
        "active_character": "Goblin Shaman",
        "turn_metadata": {"action_type": "reaction", "spell": "Shield"}
    }
])
```

**TurnManager Response:**
Creates Level 1 turn queue with both reactions, pushes queue onto stack.

**TurnStack After start_and_queue_turns:**
```
TurnStack (Stack of Queues):
Level 1 Queue: [Aragorn's Reaction ← ACTIVE, Goblin Shaman's Reaction (QUEUED)]
Level 0 Queue: [Goblin Scout's Attack (SUSPENDED)]

Structure:
┌─────────────────────────────────────────────────────────┐
│ Level 1 (Top of Stack) - Reaction Queue                │
│  ┌────────────────────────────────────────────────┐    │
│  │ [0] Aragorn's Reaction ← ACTIVE (processing)   │    │
│  │ [1] Goblin Shaman's Reaction (queued, waiting) │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ Level 0 (Bottom of Stack) - Main Turn Queue            │
│  ┌────────────────────────────────────────────────┐    │
│  │ [0] Goblin Scout's Attack (SUSPENDED)          │    │
│  │     └─ messages: [attack decl, DM prompt, etc] │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘

Context Building:
- DM sees: Level 0 Queue[0] context (parent) + Level 1 Queue[0] context (active)
- State Extractor sees: Only Level 1 Queue[0] live messages (active turn only)
```

**GD Output (GameflowDirectorResponse):**
```python
{
    "next_game_step_objectives": "Resolve Aragorn's Shield of Faith reaction",
    "game_state_updates_required": False
}
```

**SessionManager Processing:**

1. **Set new step objective:**
   ```python
   turn_manager.set_next_step_objective(
       "Resolve Aragorn's Shield of Faith reaction"
   )
   ```

2. **Clear new_messages_holder** (messages already added to TurnManager):
   ```python
   new_messages_holder = []
   ```

3. **Continue loop** - Build DM context with NEW objective

---

### Step 10: DM Resolves First Reaction

**DM Context Builder provides:**
- **History:** Combat history
- **Turn Context:** NOW focused on Aragorn's reaction turn (Level 1, empty messages)
- **Current Step Objective:** "Resolve Aragorn's Shield of Faith reaction" ← NEW
- **New Messages:** None (new_messages_holder is empty)

**DM Run #4:**

**DM Output (DungeonMasterResponse):**
```python
{
    "narrative": "Aragorn raises his shield with divine conviction! A shimmering aura of holy protection surrounds him. (Aragorn gains +2 AC until the start of his next turn, AC now 20)",
    "game_step_completed": True  # ✅ Reaction resolved, step complete
}
```

**TurnManager State:**
```
Aragorn's Reaction Turn (Level 1):
└─ messages:
    └─ [LIVE_MESSAGE] DM narrative resolving Shield of Faith
```

---

### Step 11: PHASE 4 - GD Activation (Loop Continues - Step Complete)

**SessionManager Processing:**

1. **Add DM narrative to response queue:**
   ```python
   response_queue.append(dungeon_master_response.narrative)
   ```

2. **Add DM narrative to new_messages_holder:**
   ```python
   new_messages_holder.append({
       'player_message': dungeon_master_response.narrative,
       'player_id': None,
       'character_id': "DM"
   })
   ```

3. **Check step completion - TRUE, continue while loop:**
   ```python
   while dungeon_master_response.game_step_completed:  # Still True
   ```

4. **Get fresh snapshot and build GD context:**
   ```python
   turn_manager_snapshot = turn_manager.get_snapshot()
   gameflow_director_context = gd_context_builder.build_context(...)
   ```

5. **Add messages to TurnManager:**
   ```python
   # Adds DM's Shield of Faith resolution narrative
   turn_manager.add_new_message(new_message=..., speaker="DM")
   ```

**GD Run #3:**

**GD Output (GameflowDirectorResponse):**
```python
{
    "next_game_step_objectives": "Complete Aragorn's reaction turn",
    "game_state_updates_required": True  # ✅ Extract state changes
}
```

---

### Step 12: State Extraction for First Reaction

**SessionManager Processing:**

1. **GD signaled state updates required:**
   ```python
   if gameflow_director_response.game_state_updates_required:
   ```

2. **Build State Extractor context:**
   ```python
   current_turn_snapshot = turn_manager.get_snapshot().turn_stack[-1][0]
   state_extractor_context = state_extractor_context_builder.build_context(
       current_turn=current_turn_snapshot
   )
   ```

**State Extractor Context Builder provides:**
- **Unprocessed Live Messages ONLY:** DM's Shield of Faith resolution narrative
- **NO nested summaries** (preventing duplicate extractions)

**State Extractor Output (StateExtractionResult):**
```python
{
    "character_updates": {
        "Aragorn": {
            "status_effects": [
                {
                    "name": "Shield of Faith",
                    "effect": "+2 AC",
                    "duration": "until start of Aragorn's next turn",
                    "ac_modifier": +2
                }
            ],
            "reactions_used": 1
        }
    }
}
```

**State Manager applies updates** → Aragorn's AC: 18 → 20

---

### Step 13: GD Ends First Reaction Turn

**GD Run #3 (continued) - Tool Call:**
```python
end_turn_and_get_next()
```

**TurnManager Processing:**

1. **Turn Summarizer is invoked** with:
   - **Live Messages:** DM's resolution narrative
   - **Nested Summaries:** None (leaf turn)

2. **Turn Summarizer Output:**
   ```python
   {
       "condensed_summary": "⤷ [REACTION - Aragorn] Shield of Faith: Aragorn raises his shield with divine conviction, gaining +2 AC (now AC 20) until his next turn."
   }
   ```

3. **TurnManager actions:**
   - Dequeues Aragorn's reaction from Level 1 queue (pops from front of queue)
   - Appends condensed summary to parent turn's messages (as COMPLETED_SUBTURN)
   - Returns context for next turn in Level 1 queue (Goblin Shaman's reaction becomes active)

**TurnStack After end_turn_and_get_next:**
```
TurnStack (Stack of Queues):
Level 1 Queue: [Goblin Shaman's Reaction ← ACTIVE]
Level 0 Queue: [Goblin Scout's Attack (SUSPENDED)]

Structure:
┌─────────────────────────────────────────────────────────┐
│ Level 1 (Top of Stack) - Reaction Queue                │
│  ┌────────────────────────────────────────────────┐    │
│  │ [0] Goblin Shaman's Reaction ← ACTIVE          │    │
│  │     (Aragorn's reaction completed & dequeued)  │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ Level 0 (Bottom of Stack) - Main Turn Queue            │
│  ┌────────────────────────────────────────────────┐    │
│  │ [0] Goblin Scout's Attack (SUSPENDED)          │    │
│  │     └─ messages:                               │    │
│  │         ├─ [LIVE_MESSAGE] Attack declaration   │    │
│  │         ├─ [LIVE_MESSAGE] DM prompt            │    │
│  │         ├─ [LIVE_MESSAGE] Reaction decls       │    │
│  │         ├─ [LIVE_MESSAGE] DM acknowledgment    │    │
│  │         └─ [COMPLETED_SUBTURN] Aragorn summary │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘

Context Building:
- DM sees: Level 0 Queue[0] context (parent, including Aragorn's completed summary)
           + Level 1 Queue[0] context (Goblin Shaman's reaction, active)
- State Extractor sees: Only Level 1 Queue[0] live messages (no COMPLETED_SUBTURN)
```

**GD Output (GameflowDirectorResponse):**
```python
{
    "next_game_step_objectives": "Resolve Goblin Shaman's Shield spell reaction",
    "game_state_updates_required": False
}
```

**SessionManager Processing:**

1. **Set new step objective:**
   ```python
   turn_manager.set_next_step_objective(
       "Resolve Goblin Shaman's Shield spell reaction"
   )
   ```

2. **Clear new_messages_holder:**
   ```python
   new_messages_holder = []
   ```

3. **Continue while loop** - Build DM context with NEW objective

---

### Step 14: DM Resolves Second Reaction

**DM Context Builder provides:**
- **History:** Combat history
- **Turn Context:** Goblin Shaman's reaction turn (Level 1, empty messages initially)
- **Current Step Objective:** "Resolve Goblin Shaman's Shield spell reaction" ← NEW
- **New Messages:** None (new_messages_holder is empty)
- **Parent Context Visible:** Can see Aragorn's COMPLETED_SUBTURN summary in parent

**DM Run #5:**

**DM Output (DungeonMasterResponse):**
```python
{
    "narrative": "The Goblin Shaman thrusts his gnarled staff forward and barks an arcane word! An invisible barrier of magical force springs into existence around the attacking Goblin Scout. (Goblin Scout gains +5 AC until the start of his next turn, AC now 18)",
    "game_step_completed": True  # ✅ Step complete
}
```

---

### Step 15: GD Processes Second Reaction Completion

**SessionManager Processing:** (Same pattern as Step 11-13)

1. Add narrative to response queue and new_messages_holder
2. Continue while loop (step_completed = True)
3. Build GD context, add messages to TurnManager
4. Run GD

**GD Run #4:**

**GD Output (GameflowDirectorResponse):**
```python
{
    "next_game_step_objectives": "Complete Goblin Shaman's reaction turn",
    "game_state_updates_required": True  # ✅ Extract state
}
```

**State Extraction:**
```python
{
    "character_updates": {
        "Goblin Scout": {
            "status_effects": [
                {
                    "name": "Shield (spell)",
                    "effect": "+5 AC",
                    "duration": "until start of Goblin Scout's next turn",
                    "ac_modifier": +5
                }
            ]
        },
        "Goblin Shaman": {
            "spell_slots_used": {"level_1": 1},
            "reactions_used": 1
        }
    }
}
```

**State Manager applies updates** → Goblin Scout's AC: 13 → 18

**GD Tool Call:**
```python
end_turn_and_get_next()
```

**Turn Summarizer Output:**
```python
{
    "condensed_summary": "⤷ [REACTION - Goblin Shaman] Shield Spell: The Shaman casts Shield on the Scout, granting +5 AC (now AC 18) until his next turn."
}
```

**TurnManager Processing:**
- Dequeues Goblin Shaman's reaction from Level 1 queue
- Level 1 queue is now empty → pops entire Level 1 from stack
- Appends Goblin Shaman's summary to parent turn (Level 0 Queue[0])
- Returns context for Level 0 Queue[0] (parent turn becomes active again)

**TurnStack After end_turn_and_get_next:**
```
TurnStack (Stack of Queues):
Level 0 Queue: [Goblin Scout's Attack ← ACTIVE] (back to active)

Structure:
┌─────────────────────────────────────────────────────────┐
│ Level 0 (Only Level Now) - Main Turn Queue             │
│  ┌────────────────────────────────────────────────┐    │
│  │ [0] Goblin Scout's Attack ← ACTIVE             │    │
│  │     └─ messages:                               │    │
│  │         ├─ [LIVE_MESSAGE] Attack declaration   │    │
│  │         ├─ [LIVE_MESSAGE] DM prompt for react. │    │
│  │         ├─ [LIVE_MESSAGE] Reaction decls       │    │
│  │         ├─ [LIVE_MESSAGE] DM acknowledgment    │    │
│  │         ├─ [COMPLETED_SUBTURN] Aragorn summary │    │
│  │         └─ [COMPLETED_SUBTURN] Shaman summary  │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘

Context Building:
- DM sees: Level 0 Queue[0] full context (including BOTH completed reaction summaries)
- State Extractor sees: Only Level 0 Queue[0] live messages (excludes COMPLETED_SUBTURN)
- Level 1 has been popped - all reactions completed
```

**GD Output (GameflowDirectorResponse):**
```python
{
    "next_game_step_objectives": "Resolve Goblin Scout's attack with all modifiers",
    "game_state_updates_required": False
}
```

**SessionManager Processing:**

1. **Set new step objective:**
   ```python
   turn_manager.set_next_step_objective(
       "Resolve Goblin Scout's attack with all modifiers"
   )
   ```

2. **Continue while loop** - Build DM context with NEW objective

---

### Step 16: DM Resolves Original Attack (Full Context)

**DM Context Builder provides:**
- **History:** Previous combat
- **Turn Context:** Full Level 0 turn including BOTH COMPLETED_SUBTURN summaries
- **Current Step Objective:** "Resolve Goblin Scout's attack with all modifiers" ← NEW
- **New Messages:** None
- **Game State:** Aragorn AC=20, Goblin Scout AC=18 (updated)

**DM Run #6:**

The DM has full knowledge of both reactions through the COMPLETED_SUBTURN summaries.

**DM Output (DungeonMasterResponse):**
```python
{
    "narrative": "With both combatants now magically warded, the Goblin Scout's scimitar flashes toward Aragorn!\n\n🎲 Attack Roll: 1d20+4 = 12 (rolled 8)\n\nThe blade strikes true, but glances harmlessly off Aragorn's divinely enhanced defenses! The Scout's attack (12) fails to penetrate Aragorn's bolstered armor class of 20.\n\nAragorn, you remain unscathed! What do you do?",
    "game_step_completed": True  # ✅ Attack fully resolved
}
```

---

### Step 17: GD Processes Attack Completion

**SessionManager Processing:**

1. Add narrative to response queue and new_messages_holder
2. Continue while loop
3. Build GD context, add messages
4. Run GD

**GD Run #5:**

**GD Output (GameflowDirectorResponse):**
```python
{
    "next_game_step_objectives": "Complete Goblin Scout's attack turn",
    "game_state_updates_required": True  # Extract final state
}
```

**State Extractor Context:**
- **Unprocessed Live Messages:** Only attack resolution narrative
- **COMPLETED_SUBTURN messages EXCLUDED** (preventing duplicate extraction of reactions)

**State Extractor Output:**
```python
{
    "character_updates": {
        "Goblin Scout": {
            "actions_used": {"action": 1}
        }
    }
}
```

**GD Tool Call:**
```python
end_turn_and_get_next()
```

**Turn Summarizer Context:**
- **Live Messages:** All live messages from Level 0 turn
- **Nested Summaries:** Both reaction COMPLETED_SUBTURN summaries

**Turn Summarizer Output:**
```python
{
    "condensed_summary": """[Turn - Goblin Scout] Attack Action:
The Goblin Scout swings his scimitar at Aragorn.
  ⤷ [REACTION - Aragorn] Shield of Faith: Aragorn raises his shield with divine conviction, gaining +2 AC (now AC 20) until his next turn.
  ⤷ [REACTION - Goblin Shaman] Shield Spell: The Shaman casts Shield on the Scout, granting +5 AC (now AC 18) until his next turn.
Resolution: The Scout's attack (rolled 12) misses against Aragorn's enhanced AC of 20."""
}
```

**TurnManager Response:**
1. Pops attack turn from stack
2. Appends summary to combat history
3. Stack now empty (ready for next turn)

**GD Output (GameflowDirectorResponse):**
```python
{
    "next_game_step_objectives": "Await next player action",
    "game_state_updates_required": False
}
```

---

### Step 18: Exit While Loop and Return to Player

**SessionManager Processing:**

1. **Set new step objective:**
   ```python
   turn_manager.set_next_step_objective("Await next player action")
   ```

2. **Build DM context with new objective**

**DM Run #7:**

**DM Output (DungeonMasterResponse):**
```python
{
    "narrative": "The combat continues. What would you like to do next?",
    "game_step_completed": False  # ❌ NOT complete - waiting for player
}
```

3. **Check step completion:**
   ```python
   while dungeon_master_response.game_step_completed:  # NOW FALSE - EXIT LOOP
   ```

4. **Add final messages to TurnManager** (since step not complete):
   ```python
   # Adds final DM prompt to current/next turn
   ```

5. **Return to player:**
   ```python
   return response_queue  # Contains ALL narratives from the sequence
   ```

**Final response_queue returned to player:**
```python
[
    "Two reactions are declared...",
    "Aragorn raises his shield with divine conviction!...",
    "The Goblin Shaman thrusts his gnarled staff forward...",
    "With both combatants now magically warded...",
    "The combat continues. What would you like to do next?"
]
```

---

## Final State Summary

**Character States After Action + Reactions:**
- **Aragorn:** HP 45/45, AC 20 (18 base +2 Shield of Faith), Reaction used
- **Goblin Scout:** HP 7/7, AC 18 (13 base +5 Shield spell), Action used
- **Goblin Shaman:** HP 15/15, AC 12, Reaction used, 1st level spell slot used

**History Updated:**
The entire nested action-reaction sequence is now a single condensed summary in the combat history, preserving the narrative flavor and showing the hierarchical structure.

**Total Agent Runs in This Example:**
- **DM Runs:** 7 total
  - Run #0: Prompt for action declaration
  - Run #1: Acknowledge action declaration (step complete)
  - Run #2: Prompt for reactions (new objective from GD)
  - Run #3: Acknowledge reaction declarations (step complete)
  - Run #4: Resolve Aragorn's reaction (step complete)
  - Run #5: Resolve Goblin Shaman's reaction (step complete)
  - Run #6: Resolve attack with all modifiers (step complete)
  - Run #7: Final prompt for next action (step NOT complete)
- **GD Runs:** 5 total
  - Run #1: After action declaration → set next objective "Prompt for reactions"
  - Run #2: After reaction declarations → queue reaction turns
  - Run #3: After first reaction → extract state, end turn, set next objective
  - Run #4: After second reaction → extract state, end turn, set next objective
  - Run #5: After attack resolution → extract state, end turn, set next objective
- **State Extractions:** 3 (once per turn completion: 2 reactions + 1 attack)

---

## Key Architectural Patterns Demonstrated

### 1. **DM as Primary Endpoint (NEW ARCHITECTURE)**
- **DM always runs first** when player input arrives
- **GD only activates** when DM signals `game_step_completed = True`
- **While loop pattern:** GD → set new objective → DM runs again → check completion
- **Exit condition:** Loop exits when DM returns `game_step_completed = False`
- **Player sees seamless flow:** All narratives accumulated in response_queue

### 2. **Step Completion Signal as Control Flow**
- `game_step_completed = False`: DM waiting for player input → add messages, return to player
- `game_step_completed = True`: DM finished step → activate GD for flow management
- GD sets new step objective → DM runs automatically with new objective
- Pattern continues until DM needs player input

### 3. **Message Holder Pattern**
- `new_messages_holder`: Temporary storage for messages during processing
- Messages held until **AFTER** context builders get snapshot
- Messages added to TurnManager **BEFORE** GD processes
- Holder cleared after GD sets new objective (messages already in TurnManager)
- Ensures proper sequencing and context isolation

### 4. **Hierarchical Turn Management (Stack of Queues)**
- **Stack of Queues structure:** Each level is a queue, levels are stacked
- **Level 0:** Main action (Goblin Scout's attack)
- **Level 1:** Nested reactions queue [Aragorn's Shield of Faith, Goblin Shaman's Shield]
- **FIFO within level:** Reactions processed in declaration order (queue behavior)
- **LIFO between levels:** Child levels must complete before parent resumes (stack behavior)
- **`start_and_queue_turns()`:** Creates new level queue with multiple turns, pushes onto stack
- **`end_turn_and_get_next()`:**
  - Dequeues completed turn from current level's queue
  - If queue empty → pops entire level from stack
  - Returns next queued sibling OR parent turn
- **Context building:** Includes Queue[0] from each parent level + Queue[0] from top level

### 5. **Context Isolation for State Extraction**
- **State Extractor** sees only `LIVE_MESSAGE` types (unprocessed content)
- `COMPLETED_SUBTURN` summaries filtered out to prevent duplicate state updates
- Each turn's state extracted independently when turn completes
- GD controls when state extraction occurs via `game_state_updates_required` flag

### 6. **Dual Context for DM**
- **DM Context Builder** provides complete chronological view
- Includes both `LIVE_MESSAGE` (current conversation) AND `COMPLETED_SUBTURN` (nested summaries)
- DM can reference completed reactions when resolving parent action
- Enables coherent narrative acknowledging all previous events

### 7. **Progressive Condensation**
- Each sub-turn (reaction) condensed when it ends
- Condensed summaries appended to parent turn as `COMPLETED_SUBTURN` messages
- Final turn condensation creates hierarchical summary preserving nested context
- Keeps history manageable while maintaining narrative continuity

### 8. **State Management Timing**
- State updates applied **immediately** after turn resolution (proper D&D timing)
- Updated game state available for next turn's processing
- Turn end (`end_turn_and_get_next`) handles cleanup and summarization
- State extraction happens **before** turn end (during GD processing)

### 9. **Agent Separation of Concerns**
- **SessionManager:** Orchestrates entire flow, manages while loop, accumulates response_queue
- **Dungeon Master:** Narrative generation, rule adjudication, player interaction, step completion signaling
- **Gameflow Director:** Flow control, turn management, state update signaling, step objective setting
- **State Extractor:** Game state updates from unprocessed content only
- **Turn Summarizer:** Condensation with full context including nested summaries
- **Context Builders:** Specialized context assembly for each agent type

### 10. **Response Accumulation**
- `response_queue` accumulates ALL narratives during while loop
- Player receives complete sequence in single response
- Single player input can trigger multiple DM-GD cycles
- Entire reaction sequence feels like one cohesive response

---

## Flow Summary Diagram

```
Player Input
    ↓
┌─────────────────────────────────────────────┐
│ PHASE 1: Input Processing                  │
│ - Extract character info                   │
│ - Create new_messages_holder               │
│ - Get TurnManager snapshot                 │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ PHASE 2: DM Processing                     │
│ - Build DM context (with snapshot + new)   │
│ - Run DM agent                             │
│ - Get narrative + game_step_completed flag │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ PHASE 3: Process DM Response               │
│ - Add narrative to response_queue          │
│ - Add narrative to new_messages_holder     │
└─────────────────────────────────────────────┘
    ↓
    Is game_step_completed True?
    │
    ├─ NO ────────────────────────────────────┐
    │                                         │
    │  Add messages to TurnManager            │
    │  Return response_queue to player        │
    │                                         │
    └─ YES ───────────────────────────────────┤
       │                                      │
       WHILE game_step_completed == True:    │
       │                                      │
    ┌──▼────────────────────────────────────┐│
    │ PHASE 4: GD Activation                ││
    │ - Get fresh snapshot                  ││
    │ - Build GD context                    ││
    │ - Add messages to TurnManager         ││
    │ - Run GD agent                        ││
    │   • start_and_queue_turns()           ││
    │   • end_turn_and_get_next()           ││
    │   • Set game_state_updates_required   ││
    │ - Set new step objective              ││
    │ - Extract state if required           ││
    │ - Clear new_messages_holder           ││
    └───────────────────────────────────────┘│
       │                                      │
    ┌──▼────────────────────────────────────┐│
    │ PHASE 2 (AGAIN): DM with New Objective││
    │ - Build DM context with NEW objective ││
    │ - Run DM agent                        ││
    │ - Get narrative + completion flag     ││
    └───────────────────────────────────────┘│
       │                                      │
       └──────────────────────────────────────┘
          (Loop continues until
           game_step_completed = False)
```

---

## TurnStack Evolution Diagram

This diagram shows how the TurnStack (stack of queues) evolves through the example:

```
INITIAL STATE (Step 0-5):
┌─────────────────────────────────┐
│ Level 0: [Goblin Scout Attack]  │ ← ACTIVE
└─────────────────────────────────┘

AFTER start_and_queue_turns (Step 9):
┌─────────────────────────────────────────────────────┐
│ Level 1: [Aragorn React, Goblin Shaman React]      │ ← ACTIVE (Aragorn)
│          └─ Queue of 2 reactions                    │
└─────────────────────────────────────────────────────┘
┌─────────────────────────────────┐
│ Level 0: [Goblin Scout Attack]  │ ← SUSPENDED
│          └─ has LIVE_MESSAGE    │
└─────────────────────────────────┘

AFTER 1st end_turn_and_get_next (Step 13):
┌─────────────────────────────────┐
│ Level 1: [Goblin Shaman React]  │ ← ACTIVE (next in queue)
│          └─ Aragorn dequeued    │
└─────────────────────────────────┘
┌───────────────────────────────────────────────┐
│ Level 0: [Goblin Scout Attack]                │ ← SUSPENDED
│          └─ has COMPLETED_SUBTURN (Aragorn)   │
└───────────────────────────────────────────────┘

AFTER 2nd end_turn_and_get_next (Step 15):
┌─────────────────────────────────────────────────────┐
│ Level 0: [Goblin Scout Attack]                      │ ← ACTIVE (resumed)
│          └─ has 2 COMPLETED_SUBTURN (both reactions)│
└─────────────────────────────────────────────────────┘
          ↑
    Level 1 popped (queue empty)

AFTER final end_turn_and_get_next (Step 17):
(Stack empty - turn completed and added to history)
```

**Key Observations:**
1. **Queue behavior within level:** Aragorn processes first, then Goblin Shaman (FIFO)
2. **Stack behavior between levels:** Level 1 must fully complete before Level 0 resumes (LIFO)
3. **Context inheritance:** Each active turn sees Queue[0] from all parent levels
4. **Summary propagation:** Completed subturns append to parent's messages as COMPLETED_SUBTURN

---

## Comparison: Old vs New Architecture

### Old Architecture (GD-First)
- ❌ Player input → **GD** → set objective → DM responds
- ❌ GD always processes every input first
- ❌ Harder to handle multi-turn player dialogue
- ❌ GD must decide when DM needs to speak

### New Architecture (DM-First)
- ✅ Player input → **DM** → signals completion → GD activates
- ✅ DM is primary player-facing interface
- ✅ Natural conversation flow (DM always responds)
- ✅ DM controls when flow management needed
- ✅ GD only invoked for mechanical flow management
- ✅ Cleaner separation: DM = narration, GD = flow control
