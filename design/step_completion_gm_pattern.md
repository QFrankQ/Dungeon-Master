# Step-Completion-Triggered GD Pattern

## Overview

This document describes the **Step-Completion-Triggered GD Pattern**, a key architectural pattern that defines when and how the Gameflow Director (GD) should be invoked during D&D combat sessions.

## Core Principle

**The GD only activates when a step is completed**, not on every message or player action.

## Agent Responsibilities

### Dungeon Master (DM) Agent
- **Primary Role**: Handles ongoing narrative and player interactions within the current step objective
- **Continuous Operation**: Processes messages, generates responses, and manages content
- **Step Awareness**: Works within the current step objective set by the GD
- **Completion Signaling**: Signals when a step objective has been completed

### Gameflow Director (GD)
- **Triggered Operation**: Only activates when DM signals step completion
- **Flow Orchestration**: Manages combat script progression and step transitions
- **Objective Setting**: Sets new step objectives for the DM based on combat arbiter script
- **Turn Management**: Handles turn boundaries, reaction queues, and complex flow decisions

## Message Flow Pattern

```
1. Player Action → DM (processes within current step)
2. DM Response → Player (continues current step)
3. More Player Actions → DM (still within same step)
4. DM Signals: "Step Complete: [step_name]"
5. TRIGGER: GD Activates
6. GD Evaluates: Combat script position, next requirements
7. GD Actions: Set new step objective OR manage turn transitions
8. Return to Step 1 with new objective
```

## Implementation Architecture

### Step Completion Detection
The DM signals step completion through structured responses or function calls:

```python
# DM signals completion
{
    "narrative": "The orc takes 8 damage and falls unconscious.",
    "step_completion": {
        "completed_step": "resolve_damage_and_effects",
        "ready_for_next": True
    }
}
```

### GD Activation Pattern
```python
# GD only processes when step completion is detected
if dm_response.has_step_completion():
    gd_response = await gameflow_director.process_step_completion(
        completed_step=dm_response.step_completion,
        turn_context=current_turn_context
    )

    # GD sets new objective or manages flow
    if gd_response.new_step_objective:
        turn_manager.set_step_objective(gd_response.new_step_objective)
    elif gd_response.end_turn:
        turn_manager.end_turn()
    # etc.
```

## Key Benefits

### 1. Reduced Computational Overhead
- **Fewer GD Invocations**: GD only activates when needed, not on every message
- **Efficient Resource Usage**: DM handles routine interactions, GD handles flow decisions
- **Cleaner Message Flow**: Less back-and-forth between agents

### 2. Clear Separation of Concerns
- **DM**: Content generation, player interaction, rule interpretation
- **GD**: Flow control, step advancement, turn management
- **No Overlap**: Each agent has distinct, non-overlapping responsibilities

### 3. Improved Responsiveness
- **Faster Player Interactions**: DM responds immediately without GD overhead
- **Strategic GD Usage**: GD focuses on important flow decisions
- **Natural Conversation Flow**: Players interact primarily with DM

### 4. Cleaner Architecture
- **Event-Driven**: GD responds to completion events, not every message
- **Stateless GD**: GD doesn't need to track ongoing conversation state
- **Clear Triggers**: Explicit completion signals provide clear activation points

## Combat Script Integration

### Traditional Approach (Every Message)
```
Player: "I attack the orc"
→ GD: Analyze, set objective
→ DM: Process attack
→ GD: Check completion, advance
→ Response to player
```

### Step-Completion Pattern
```
Player: "I attack the orc"
→ DM: Process attack within current objective
→ Response to player

DM: Signals "damage resolution complete"
→ GD: Advance to next step
→ Set new objective for DM
```

## Example Combat Flow

### Step 1: Receive Action
- **GD Sets**: "Receive and interpret declared action"
- **DM Processes**: Player attack declarations, clarifying questions
- **DM Signals**: "Action received and interpreted"
- **GD Activates**: Advances to damage calculation step

### Step 2: Calculate Damage
- **GD Sets**: "Calculate damage and apply effects"
- **DM Processes**: Damage rolls, effect applications
- **DM Signals**: "Damage calculated and applied"
- **GD Activates**: Checks for reactions or advance to next turn

### Step 3: Handle Reactions (If Any)
- **GD Evaluates**: Any reactions declared?
- **GD Creates**: Reaction queue if needed
- **GD Sets**: Reaction processing objectives
- **DM Processes**: Each reaction through adjudication sub-routine

## Implementation Considerations

### DM Step Awareness
The DM must be aware of its current step objective:
```python
# DM context includes current step
context = f"""
Current Step Objective: {current_step_objective}
Your role: Complete this specific step and signal when finished.
"""
```

### Completion Signal Standards
Standardized completion signals ensure reliable GD triggering:
```python
class StepCompletion:
    completed_step: str
    outcome: str
    ready_for_next: bool
    special_conditions: Optional[Dict[str, Any]] = None
```

### Error Handling
- **Incomplete Steps**: GD can prompt DM to complete unfinished steps
- **Ambiguous Completion**: GD requests clarification from DM
- **Flow Exceptions**: GD handles special cases (reactions, interruptions)

## Advantages Over Alternative Patterns

### vs. Message-Driven GD
- **Reduced Overhead**: GD not invoked on every message
- **Better Performance**: Fewer LLM calls for routine interactions
- **Cleaner Logic**: Clear triggers instead of complex message analysis

### vs. Always-Active GD
- **Cost Efficiency**: GD LLM calls only when needed
- **Faster Response**: DM responds immediately without GD preprocessing
- **Simpler State Management**: GD doesn't track conversation state

### vs. Manual Coordination
- **Automated Flow**: DM automatically signals completion
- **Consistent Triggers**: Standardized completion detection
- **Reliable Advancement**: Less prone to missed step transitions

## Future Enhancements

### Parallel Processing
- **Concurrent DM/GD**: DM continues while GD prepares next step
- **Background Preparation**: GD pre-calculates likely next steps
- **Async Activation**: Non-blocking GD processing

### Smart Completion Detection
- **AI-Powered Signals**: Automatic completion detection from DM responses
- **Context Analysis**: GD infers completion from response content
- **Learning System**: Improve completion detection over time

## Conclusion

The Step-Completion-Triggered GD Pattern provides an efficient, clean architecture for D&D combat management by ensuring the GD only activates when flow decisions are needed. This creates better performance, clearer responsibilities, and more natural player interactions while maintaining the structured combat flow required by D&D rules.

The pattern transforms the GD from a **constant coordinator** into an **event-driven orchestrator**, resulting in a more efficient and maintainable system architecture.