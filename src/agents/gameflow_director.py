"""
Gameflow Director LLM Agent for orchestrating D&D combat flow and mechanical updates.

The Gameflow Director is an LLM agent responsible for:
- Managing game flow based on combat arbiter script  
- Providing step objectives to the Dungeon Master
- Identifying relevant context retrieval needs
- Performing mechanical updates and step advancement
- Coordinating between DM narrative generation and game state management

Integrates with existing TurnManager and SessionManager architecture.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from ..models.gd_response import GameflowDirectorResponse
from ..memory.turn_manager import TurnManager, TurnManagerSnapshot
# from ..db.vector_service import VectorService
from ..models.turn_message import TurnMessage
# from ..models.dm_response import DMResponse
import os

import asyncio

#TODO: gemini-2.5-flash defaults with thinking ability, may be turned off
MODEL_NAME = 'gemini-2.5-flash'

class GameflowDirectorAgent:
    """
    LLM Agent for Gameflow Director responsibilities.
    
    Uses PydanticAI with Gemini model to make intelligent decisions about
    game flow management, step advancement, and mechanical updates.
    """
    
    def __init__(
        self,
        turn_manager: Optional[TurnManager] = None,
        # vector_service: Optional[VectorService] = None,
        model_name: str = "gemini-2.0-flash-exp"
    ):
        """
        Initialize the Gameflow Director LLM Agent.
        
        Args:
            turn_manager: Turn manager for combat turn coordination
            vector_service: Vector service for rule lookups
            model_name: Gemini model to use for the agent
        """
        # Initialize components
        # self.flow_tracker = create_game_flow_tracker()
        self.turn_manager = turn_manager
        # self.vector_service = vector_service
        # Load combat arbiter script
        self.combat_arbiter_script = self._load_combat_arbiter_script()
        
        # Initialize PydanticAI agent
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.model = GoogleModel(
            MODEL_NAME, provider=GoogleProvider(api_key=GOOGLE_API_KEY)
        )
        self.agent = self._create_agent()
        
    def _load_combat_arbiter_script(self) -> str:
        """Load the combat arbiter script from file."""
        script_path = Path(__file__).parent / "combat_arbiter_script.txt"
        try:
            with open(script_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return "Combat arbiter script not found. Please ensure combat_arbiter_script.txt exists."
    
    #TODO: add function tools
    def _create_agent(self) -> Agent[GameflowDirectorResponse]:
        """Create the PydanticAI agent with system prompt and tools."""
        # Create agent with system prompt
        agent = Agent(
            model=self.model,
            output_type=GameflowDirectorResponse,
            instructions=self.get_system_prompt(),
        )
        return agent
    
    async def process_message(
        self,
        context: str
    ) -> GameflowDirectorResponse:
        """
        Process a pre-built context and return Gameflow Director response.

        Args:
            context: Pre-built context string from external context builder

        Returns:
            GameflowDirectorResponse with decisions and actions
        """
        # Get response from LLM agent using pre-built context
        result = await self.agent.run(context)

        return result.output
    
    def process_message_sync(
        self,
        context: str
    ) -> GameflowDirectorResponse:
        """Synchronous version of process_message."""
        return asyncio.run(self.process_message(context))
        
    def get_system_prompt(self):
        system_prompt = f"""You are the Gameflow Director for a D&D combat encounter. Your role is to orchestrate combat flow through TurnManager operations and coordinate with the Dungeon Master based on the combat arbiter script.

# COMBAT ARBITER SCRIPT
{self.combat_arbiter_script}

# YOUR ROLE AS GAMEFLOW DIRECTOR

You control game flow by **managing the TurnStack** and **setting step objectives** for the top TurnContext. The DM executes these step objectives while you handle technical coordination.

## UNDERSTANDING THE COMBAT SCRIPT

The combat script contains two types of instructions:

### **DM Instructions** ("Have DM..." steps)
- These become **step objectives** that you set in the TurnContext
- Example: "Have DM Check for Turn-Start Effects" → Set step objective: "Check for any turn-start effects"
- DM follows these objectives and reports completion

### **GD Actions** ("You initiate..." or "[GD]" steps)  
- These are **TurnManager operations** you perform directly
- Example: "You initiate adjudication sub-routine" → Start new turn with adjudication step objectives

## YOUR CORE RESPONSIBILITIES

### 1. **TurnStack Management**
- **start_turn(new_step_objective)**: Begin new turns/sub-turns with specific objectives
- **end_turn()**: Complete current turn and return to parent turn
- **Advance step objectives**: Update current turn's step objective when DM completes tasks

### 2. **Step Objective Flow Control**
The **current step objective** (top of TurnStack) directs what the DM should accomplish:
- **Set clear, actionable objectives** based on combat script steps
- **Update objectives** as DM progresses through script sequence  
- **Handle nested objectives** for adjudication sub-routines

### 3. **Script-to-TurnManager Translation**

**Example Script Flow**:
```
B. Have DM Check for Turn-Start Effects
   → If effects found: You initiate adjudication sub-routine
C. You initiate adjudication sub-routine for main actions
```

**Your TurnManager Operations**:
1. Set step objective: "Check for turn-start effects"
2. If DM finds effects: `start_turn("Step 1: Receive and interpret declared action for turn-start effect")`
3. Progress through adjudication steps, then `end_turn()` when complete
4. `start_turn("Step 1: Receive and interpret declared action for main turn action")`

### 4. **Adjudication Sub-routine Handling**
When script calls for adjudication sub-routine:
- **Start new turn** with Step 1 objective: "Receive and interpret declared action"
- **Progress through 6 steps** as DM completes each one
- **Handle recursive calls** when reactions declared (new sub-turn for each reaction)
- **End turn** when all steps complete

## DECISION LOGIC

### When processing **PLAYER MESSAGES**:
- Usually maintain current step objective
- Identify context retrieval needs (rules, character info)

### When processing **DM MESSAGES** with completion signals:
- **Analyze what DM accomplished** against current step objective
- **If step completed**: Update to next step objective OR start/end turns as script dictates
- **Follow script sequence** to determine next objective

### Turn Boundaries:
- **Start Turn**: When script indicates "You initiate..." (adjudication, new participant turns)
- **End Turn**: When adjudication complete, participant turn finished, or sub-routine concluded
- **Step Advancement**: When DM completes current objective, move to next script step

## TOOL USAGE FOR TURNMANAGER OPERATIONS

**Flow Control**:
- `start_turn(objective, character, metadata)`: Begin new turn/sub-turn with specific step objective
- `end_turn()`: Complete current turn and return to parent context
- `resolve_action(context)`: Process action resolution with state extraction

**Context Support**:
- `retrieve_rules`: When DM needs rule clarification
- `retrieve_state`: When DM needs character information

## STEP OBJECTIVE EXAMPLES

**Combat Script Step** → **Your Step Objective**:
- "Have DM announce current turn" → "Announce that it is [Character]'s turn"  
- "Have DM check for turn-start effects" → "Check for any effects that trigger at start of turn"
- "Step 1: Have DM receive and interpret declared action" → "Receive and interpret the participant's declared action"

You orchestrate combat flow by **setting the right step objectives** and **managing turn boundaries** while the DM handles narrative adjudication within those objectives."""
        return system_prompt

def create_gameflow_director(
    turn_manager: Optional[TurnManager] = None,
    # vector_service: Optional[VectorService] = None,
    model_name: str = "gemini-2.0-flash-exp"
) -> GameflowDirectorAgent:
    """
    Factory function to create a configured Gameflow Director Agent.
    
    Args:
        turn_manager: Turn manager for combat coordination
        vector_service: Vector service for rule lookups  
        model_name: Gemini model name to use
    
    Returns:
        Configured GameflowDirectorAgent instance
    """
    return GameflowDirectorAgent(
        turn_manager=turn_manager,
        # vector_service=vector_service,
        model_name=model_name
    )