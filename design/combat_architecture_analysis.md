# Combat Architecture Analysis & Design Recommendations

## Problem Statement

The combat arbiter script (`src/agents/combat_arbiter_script.txt`) defines a comprehensive 3-phase combat management system that requires both automated processing and player interaction. The key challenge is implementing a system where the DM can:

1. Execute multiple internal steps automatically during combat
2. Pause for player input only when necessary
3. Ensure proper rule adherence and sequence enforcement
4. Maintain existing turn management architecture

## Combat Script Analysis

The script reveals two distinct types of operations:

### Internal Processing (Automated)
- Checking for turn-start/end effects
- State updates and HP management
- Announcements and round progression
- Rule lookups for unfamiliar abilities
- Initiative order management
- Combat state tracking

### Interactive Checkpoints (Player Input Required)
- Player action declarations
- Initiative roll verification and contests
- Reaction windows (pre-resolution and post-resolution)
- Action confirmation for ambiguous intents
- "Would you like to do anything else?" confirmations

## Recommended Approach: Combat State Machine with Agent Orchestra

### Core Pattern: Pipeline with Pause Points

```
[Internal Steps] → [Player Input Required] → [Internal Steps] → [Player Input] → ...
```

The DM needs to execute multiple steps internally before player interaction. For example, at turn start:
- Check for start-of-turn effects → Update state → Announce current turn → Interpret player action → Confirm action cost → Resolve action → Update combat state → Check for zero HP → Announce next turn

### Architecture Components

#### 1. Combat State Machine
- **Responsibility**: Tracks current phase (Start/Rounds/End) and step within phase
- **Key Features**:
  - Determines whether current step requires player input or is internal
  - Enforces proper sequence and prevents skipping steps
  - Maintains initiative order, round counter, combat participants
  - Tracks combat state (HP, conditions, positions)

#### 2. Combat Controller Agent
- **Responsibility**: Orchestrates the overall combat flow
- **Key Features**:
  - Receives state context and executes appropriate step
  - Can perform multiple internal steps in sequence
  - Pauses for player input only when state machine indicates
  - Compiles internal processing results into single response

#### 3. Specialized Sub-Agents

##### Initiative Agent
- Handles complex initiative establishment with player verification
- Manages initiative contests and ability adjudication
- Processes new combatants joining mid-fight

##### Action Interpreter
- Maps player descriptions to game mechanics (Attack/Dash/Disengage/etc.)
- Handles ambiguous action interpretation
- Confirms action costs when necessary

##### Rule Arbiter
- Performs rule lookups for unfamiliar abilities using vector database
- Ensures "Core Principle: Rule Adjudication" compliance
- Caches looked-up rules for encounter duration

##### Reaction Coordinator
- Manages reaction windows (pre-resolution and post-resolution)
- Handles reaction chains (last-in, first-out)
- Coordinates multiple participants' reactions

#### 4. Enhanced Turn Manager Integration
- Extend existing `TurnManager` to handle combat-specific workflows
- Maintain hierarchical turn structure while adding combat state awareness
- Integrate with combat state machine for proper turn progression

### Internal Processing Flow

For each combat step, the system would:

1. **State Assessment**: Check current combat state and required step
2. **Internal Execution**: If step is internal, execute immediately (announcements, effects, state updates)
3. **Batch Processing**: Chain multiple internal steps together
4. **Interaction Gate**: Pause only when player input is genuinely required
5. **Response Compilation**: Present all internal processing results + player prompt as single response

### Integration with Existing Architecture

This extends the current `SessionManager` → `TurnManager` pattern:

```
SessionManager → Detects combat initiation
     ↓
CombatManager → Orchestrates state machine and agents
     ↓
Combat State Machine → Determines next step(s)
     ↓
Combat Controller Agent → Executes internal steps or requests player input
     ↓
Specialized Sub-Agents → Handle specific combat mechanics
     ↓
Return to SessionManager → When combat ends
```

### Key Design Benefits

- **Automatic Rule Adherence**: State machine enforces the script's sequence
- **Efficient Processing**: Multiple internal steps execute in single "DM turn"
- **Clear Separation**: Internal logic vs player-facing communication
- **Extensible**: Easy to add new combat mechanics or phases
- **Traceable**: Full audit trail of combat steps and decisions
- **Maintains Existing Architecture**: Builds on current turn management and message processing

## Alternative Approaches Considered

### 1. Simple System Prompt Addition
- **Approach**: Add the script directly to the DM agent's system prompt
- **Pros**: Minimal code changes, leverages existing LLM capabilities
- **Cons**: No guarantees of proper step execution, difficult to debug, poor state tracking
- **Verdict**: Not recommended for complex combat sequences

### 2. Rule-Based Workflow Engine
- **Approach**: Hard-coded workflow engine with predefined steps
- **Pros**: Deterministic execution, easy to debug
- **Cons**: Inflexible, requires significant rule maintenance
- **Verdict**: Could work but less adaptable than agent-based approach

### 3. Hybrid: Enhanced Prompting + State Tracking
- **Approach**: Enhanced system prompt with external state tracking
- **Pros**: Simpler than full agent orchestra, some guarantees
- **Cons**: Still relies heavily on LLM consistency
- **Verdict**: Possible fallback if agent approach is too complex

## Implementation Phases

### Phase 1: Combat State Machine Foundation
- Implement basic state machine with phase/step tracking
- Define internal vs interactive step classification
- Create combat state data structures

### Phase 2: Combat Controller Agent
- Build orchestrating agent that can execute multiple steps
- Implement internal processing pipeline
- Add pause points for player interaction

### Phase 3: Specialized Sub-Agents
- Implement Initiative Agent for complex initiative handling
- Create Action Interpreter for player intent mapping
- Build Rule Arbiter with vector database integration
- Add Reaction Coordinator for reaction management

### Phase 4: Integration & Testing
- Integrate with existing TurnManager and SessionManager
- Comprehensive testing of combat scenarios
- Performance optimization and error handling

## Refined Architecture: Responsibility Boundaries and Message Flow

### Clear Responsibility Separation

#### Combat Controller: Process Orchestration (Not Content)
The Combat Controller handles **procedural orchestration only**:

**What the Controller DOES:**
- Tracks "we need player input at this step"
- Knows "confirmation is required before proceeding"
- Determines "all internal steps are complete, pause here"
- Manages "reaction window is open, collect responses"
- Executes mechanical operations (dice rolls, state updates, calculations)
- Maintains combat-specific state separate from message history

**What the Controller DOES NOT DO:**
- Generate narrative descriptions or confirmation text
- Interpret whether an action is ambiguous
- Make rule judgments or interpretations
- Communicate directly with players (except routine confirmations)

#### DM Agent: Content and Judgment (Following Script Guidance)
The DM Agent remains responsible for all content generation and rule interpretation, but receives **structured context** from the Controller:

**DM receives from Controller:**
```
Current Step: ACTION_CONFIRMATION_REQUIRED
Context: Player declared "I try to convince the guard"
Script Guidance: "If participant's described intent is interpreted as Influence/Search/Study/Utilize and they didn't explicitly state using their Action, provide clarification before proceeding"
Required Response Type: CONFIRMATION_REQUEST
```

**DM generates:** "Attempting to persuade the guard would require an Influence action, using your Action for the turn. Do you still want to do this?"

### Step-by-Step Responsibility Breakdown

**Internal Processing Pipeline Example:**

**CHECK_START_EFFECTS:**
- **Controller**: Identifies that start-of-turn effects need checking, queries character state for active conditions
- **DM Agent**: Interprets what those conditions mean ("poisoned condition requires Constitution save")
- **Controller**: Executes the mechanical save (rolls dice, applies modifiers)
- **DM Agent**: Determines narrative outcome ("The poison courses through your veins")

**APPLY_POISON:**
- **Controller**: Calculates damage (1d6 poison = 4 damage), applies to HP mechanically
- **Controller**: Updates character state (HP: 27→23)

**UPDATE_HP & CHECK_CONSCIOUSNESS:**
- **Controller**: Pure state management, no DM involvement needed

### Context Architecture

#### Controller Context
```json
{
  "combat_state": {
    "phase": "COMBAT_ROUNDS",
    "current_step": "CHECK_START_EFFECTS", 
    "round": 3,
    "turn_index": 2,
    "initiative_order": [...],
    "active_participant": "Alice"
  },
  "participant_states": {
    "Alice": {
      "hp": 27,
      "max_hp": 30,
      "conditions": ["poisoned"],
      "spell_slots": {...}
    }
  },
  "pending_reactions": [],
  "script_requirements": {
    "current_step_type": "internal_processing",
    "next_player_input_step": "RECEIVE_ACTIONS"
  }
}
```

#### DM Agent Context (Curated, Not Full History)
```json
{
  "current_instruction": "Generate narrative for internal processing batch",
  "script_guidance": "Provide 1-2 sentences of evocative narration for turn start effects",
  "state_changes_to_narrate": [
    {"type": "constitution_save", "target": 12, "rolled": 8, "result": "failed"},
    {"type": "poison_damage", "amount": 4, "hp_before": 27, "hp_after": 23}
  ],
  "character_context": {
    "name": "Alice",
    "current_condition": "poisoned since round 1"
  },
  "message_history_summary": "Last 3 exchanges for continuity",
  "required_response_type": "narrative_compilation"
}
```

### Communication Architecture

**Single Point of Player Interface: SessionManager**
All player communication flows through SessionManager:

```
Player → SessionManager → Combat System → SessionManager → Player
```

**Internal Flow During Combat:**
```
Player Input → SessionManager → CombatManager → Combat Controller
                                                      ↓
Combat Controller → Analyzes step requirements → Provides context to DM Agent
                                                      ↓
DM Agent → Generates response content → Returns to Combat Controller
                                                      ↓
Combat Controller → Updates state machine → Returns to SessionManager
                                                      ↓
SessionManager → Sends response to player
```

### Message Flow Optimizations

#### Direct Controller-Player Interactions (Routine Operations)

**Standard Combat Actions:**
```
Player: "I attack the orc"
Controller: Recognizes standard attack → processes directly → updates to DM
```

**Routine Confirmations:**
```
Player: "I try to convince the guard"
Controller: Detects ambiguity → generates standard clarification request
Controller: "This sounds like an Influence action (uses your Action). Confirm?"
Player: "Yes" 
Controller: Continues with action resolution
```

#### Optimized Flow Patterns

**Pattern 1: Pure Mechanical Sequences**
```
Controller → Executes internal steps → Provides summary to DM → DM generates narrative → Response to player
```

**Pattern 2: Standard Confirmations**
```
Player → Controller → Standard confirmation → Player response → Controller → Continue
(DM bypassed for routine confirmations)
```

**Pattern 3: Complex Situations**
```
Player → Controller → Detects complexity → Full DM consultation → DM response → Controller updates state
```

### Responsibility Matrix

| Function | Combat Controller | DM Agent | SessionManager |
|----------|------------------|----------|----------------|
| Step sequencing | ✓ | | |
| Mechanical operations | ✓ | | |
| State changes | ✓ | | |
| Pause point detection | ✓ | | |
| Rule interpretation | | ✓ | |
| Narrative generation | | ✓ | |
| Player communication | | | ✓ |
| Combat initiation detection | | | ✓ |
| Session orchestration | | | ✓ |
| Routine confirmations | ✓ | | |

### Context Optimization Benefits

**Selective History Passing:**
- Controller tracks "narrative continuity needs" 
- Only passes relevant context to DM (not full conversation)
- DM gets "Alice was poisoned by trap in round 1" vs entire conversation

**State-Based Context:**
- Controller provides rich combat state instead of conversational history
- DM focuses on current situation rather than parsing conversation flow

**Template-Based Responses:**
- Common combat interactions use pre-generated templates
- Controller fills in variables rather than generating from scratch
- DM only invoked for novel situations

### Architectural Benefits

**Reduced DM Load:**
- DM doesn't track combat state (Controller does)
- DM doesn't determine step sequencing (Controller does)
- DM focuses on content generation with rich context

**Faster Response Times:**
- Routine operations bypass DM entirely
- Internal processing batches execute quickly
- Complex situations get full DM attention

**Better Consistency:**
- Combat flow follows script exactly (Controller enforces)
- State management is centralized and reliable
- DM rulings remain consistent within encounters

## Conclusion

The Combat State Machine with Smart Controller pattern provides optimal separation of concerns while maintaining efficient message flow. The Controller acts as a **smart preprocessing layer** that handles routine combat operations and provides curated context to the DM Agent, which focuses on content generation and complex rule interpretation.

This approach ensures that the DM can properly follow the comprehensive combat guidelines while optimizing performance through direct Controller-Player interactions for routine operations and selective DM consultation for complex situations.