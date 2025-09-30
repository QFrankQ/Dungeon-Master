# Reaction Queue Architecture

## Overview

This document outlines the architectural approach for handling multiple reactions in D&D combat using a **sibling subturn pattern** with **GD-controlled queue orchestration**.

## Core Architecture: Sibling Subturn Approach

### Problem Solved
When multiple players declare reactions to a single event (e.g., "Anyone want to react to this fireball?"), the system needs to:
1. Collect all reaction declarations
2. Filter out negative responses ("No, I don't react")
3. Queue positive reactions for sequential processing
4. Process each reaction through the full adjudication sub-routine
5. Return to parent action resolution when complete

### Solution: Sibling Subturns as Natural Queue
Instead of maintaining separate queue metadata, **leverage the turn stack itself as the queue structure**:

```
Parent Turn: "Alice casts Fireball"
├── Subturn 2.1: Bob's Counterspell [pending]
├── Subturn 2.2: Carol's Shield [pending]
└── Subturn 2.3: Dave's Evasion [pending]
```

## Implementation Flow

### Phase 1: Reaction Collection
1. **DM provides reaction window**: "Anyone want to react to this fireball?"
2. **System collects responses**:
   - "Bob: I cast Counterspell!"
   - "Carol: I use Shield!"
   - "Dave: No reaction"
   - "Eve: I'll pass"
3. **Messages bundled and sent to DM**: All collected responses
4. **DM signals completion**: "reaction_window_complete"

### Phase 2: GD Queue Processing
1. **GD receives completion signal**
2. **GD filters reactions**: Identifies positive reactions (Bob, Carol) vs negative (Dave, Eve)
3. **GD creates sibling subturns**: One subturn per positive reaction

#### Tool Call Pattern: `create_reaction_subturns()`
```python
# Input: Filtered positive reactions
reactions = [
    {"speaker": "Bob", "content": "I cast Counterspell!"},
    {"speaker": "Carol", "content": "I use Shield!"}
]

# Creates sibling subturns with reaction messages
subturn_2_1 = TurnContext(
    turn_id="2.1",
    turn_level=1,
    messages=[TurnMessage("Bob: I cast Counterspell!", speaker="Bob")],
    step_objectives_queue=[]  # Empty - GD will set objectives
)

subturn_2_2 = TurnContext(
    turn_id="2.2",
    turn_level=1,
    messages=[TurnMessage("Carol: I use Shield!", speaker="Carol")],
    step_objectives_queue=[]  # Empty - GD will set objectives
)

# Tool returns context for first reaction to process
return {
    "subturns_created": ["2.1", "2.2"],
    "next_to_process": {
        "subturn_id": "2.1",
        "reaction": "Bob's Counterspell",
        "step_needed": "Receive and interpret declared action"
    }
}
```

### Phase 3: Sequential Reaction Processing

#### Setting Objectives
**GD sets step objectives** for each subturn (maintaining consistent responsibility):
```python
# GD advances step for subturn 2.1
current_objective = "Receive and interpret declared action"  # Start of adjudication sub-routine
```

#### Processing Flow
1. **GD sets objective** for current reaction subturn
2. **DM processes reaction** through full adjudication sub-routine (Steps 1-6)
3. **GD ends subturn** and checks for next pending reaction

#### Tool Call Pattern: `end_subturn_and_get_next()`
```python
# Combined tool call for clean transitions
result = {
    "current_subturn": "2.1",
    "status": "completed",
    "next_pending": {
        "subturn_id": "2.2",
        "reaction": "Carol's Shield",
        "step_needed": "Receive and interpret declared action"
    }
}

# OR when no more reactions:
result = {
    "current_subturn": "2.3",
    "status": "completed",
    "next_pending": None,  # Return to parent turn
    "parent_context": "Continue with Fireball resolution"
}
```

## Key Architectural Benefits

### 1. Natural Queue Structure
- **Turn stack IS the queue** - no separate queue metadata needed
- **Visual representation** of pending work via incomplete subturns
- **Leverages existing turn management infrastructure**

### 2. Clean Context Management
- **Parent turn retains all messages** - full context for DM narration
- **Each subturn focuses on specific reaction** - clear objective setting
- **Context builder uses "first TurnContext of each level"** for proper isolation

### 3. Elegant Completion Tracking
```python
# GD can easily determine remaining work
pending_reactions = [turn for turn in current_level_subturns if not turn.is_completed()]
if pending_reactions:
    process_next_reaction()
else:
    return_to_parent_action()
```

### 4. Consistent Responsibility Separation
- **GD**: Queue orchestration, objective setting, flow control
- **DM**: Reaction processing, narrative generation, adjudication
- **TurnManager**: Structure management, context isolation

## Adjudication Sub-routine Modifications

### Current Script (new_combat_script.txt)
```
Step 3: If a Reaction is declared, you initiate this adjudication sub-routine recursively
```

### Updated Script Pattern
```
Step 3: If reactions are declared, create sibling subturns for each positive reaction and process sequentially through adjudication sub-routine
```

## Implementation Advantages

### Compared to Sequential Approach
- **Eliminates complex queue management** - turn stack handles structure
- **Better visual representation** - can see all pending reactions
- **Cleaner tool interface** - fewer specialized queue operations

### Compared to Message-Driven Approach
- **GD maintains flow control** - determines processing order and objectives
- **Consistent agent responsibilities** - no confusion about who handles what
- **Clear state tracking** - completion status visible in turn structure

## Processing Order Options

GD can determine reaction order based on:
1. **D&D Timing Rules**: Counterspell before Shield before Evasion
2. **Initiative Order**: Highest initiative reacts first
3. **Declaration Order**: First declared, first processed
4. **Contextual Priority**: GD uses judgment based on situation

## Context Building Strategy

### DM Context (Full Chronological)
- **Sees parent turn messages** + current subturn focus
- **Understands full situation** for proper narration
- **Current step objective** guides specific action to process

### StateExtractor Context (Isolated)
- **Sees only current subturn messages** to avoid duplicate extractions
- **Processes reaction-specific state changes** without parent context bleeding

## Migration Path

This architecture maintains compatibility with existing:
- **TurnManager structure** - extends rather than replaces
- **Message handling** - uses existing TurnMessage patterns
- **Agent interfaces** - GD and DM responsibilities remain clear
- **Context builders** - leverages existing isolation patterns

The sibling subturn approach provides a **natural, scalable solution** for complex reaction handling while maintaining clean architectural separation and leveraging existing infrastructure.