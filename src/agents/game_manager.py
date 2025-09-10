"""
Game Manager LLM Agent for orchestrating D&D combat flow and mechanical updates.

The Game Manager is an LLM agent responsible for:
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
from pydantic_ai.agent import _system_prompt
from pydantic_ai.models.gemini import GeminiModel

from ..models.gm_response import GameManagerResponse
from ..memory.game_flow_tracker import create_game_flow_tracker
from ..memory.turn_manager import TurnManager, TurnManagerSnapshot
from ..db.vector_service import VectorService
from ..context.gm_context_builder import GMContextBuilder
from ..models.turn_message import TurnMessage
from ..models.dm_response import DMResponse

import asyncio


class GameManagerAgent:
    """
    LLM Agent for Game Manager responsibilities.
    
    Uses PydanticAI with Gemini model to make intelligent decisions about
    game flow management, step advancement, and mechanical updates.
    """
    
    def __init__(
        self,
        turn_manager: Optional[TurnManager] = None,
        vector_service: Optional[VectorService] = None,
        model_name: str = "gemini-2.0-flash-exp"
    ):
        """
        Initialize the Game Manager LLM Agent.
        
        Args:
            turn_manager: Turn manager for combat turn coordination
            vector_service: Vector service for rule lookups
            model_name: Gemini model to use for the agent
        """
        # Initialize components
        # self.flow_tracker = create_game_flow_tracker()
        self.turn_manager = turn_manager
        self.vector_service = vector_service
        self.context_builder = GMContextBuilder()
        # Load combat arbiter script
        self.combat_arbiter_script = self._load_combat_arbiter_script()
        
        # Initialize PydanticAI agent
        self.model = GeminiModel(model_name)
        self.agent = self._create_agent()
        
    def _load_combat_arbiter_script(self) -> str:
        """Load the combat arbiter script from file."""
        script_path = Path(__file__).parent / "combat_arbiter_script.txt"
        try:
            with open(script_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return "Combat arbiter script not found. Please ensure combat_arbiter_script.txt exists."
    
    def _create_agent(self) -> Agent[GameManagerResponse]:
        """Create the PydanticAI agent with system prompt and tools."""
        
       

        # Create agent with system prompt
        agent = Agent(
            model=self.model,
            output_type=GameManagerResponse,
            system_prompt=self.get_system_prompt()
        )
        
        #TODO: Add Actual tools
        # Add tools
        # self._register_tools(agent)
        
        return agent
    
    async def process_message(
        self,
        new_message: [TurnMessage | DMResponse],
        turn_manager_snapshot: TurnManagerSnapshot
    ) -> GameManagerResponse:
        """
        Process a new message and return Game Manager response.
        
        Args:
            new_message: The new message content
            message_source: Source of message ("player" or "dm")
            step_complete_signal: Whether message signals step completion
            additional_context: Additional context (history, turn context, etc.)
        
        Returns:
            GameManagerResponse with decisions and actions
        """
        context = self.context_builder(new_message, turn_manager_snapshot)
        # Get response from LLM agent
        result = await self.agent.run(context)
        
        return result.output
    
    def process_message_sync(
        self,
        new_message: [TurnMessage | DMResponse],
        turn_manager_snapshot: TurnManagerSnapshot
    ) -> GameManagerResponse:
        """Synchronous version of process_message."""
        return asyncio.run(self.process_message(
            new_message, turn_manager_snapshot
        ))
    
    # def get_current_position(self) -> str:
    #     """Get current position in game flow."""
    #     return self.flow_tracker.get_current_position()
    
    # def get_current_step_objective(self) -> str:
    #     """Get current step objective."""
    #     if self.flow_tracker.step:
    #         return f"Accomplish: {self.flow_tracker.step}"
    #     elif self.flow_tracker.phase:
    #         return f"Begin: {self.flow_tracker.phase}"
    #     else:
    #         return "No current objective set"
    
    # def get_position_context_for_dm(self) -> str:
    #     """Get formatted context for DM including current position and objectives."""
    #     if self.flow_tracker.is_empty():
    #         return "=== GAME MANAGER CONTEXT ===\nNo current position set"
        
    #     context_parts = [
    #         "=== GAME MANAGER CONTEXT ===",
    #         f"Current Position: {self.flow_tracker.get_current_position()}",
    #         f"Step Objective: {self.get_current_step_objective()}"
    #     ]
        
    #     if self.flow_tracker.context:
    #         context_parts.append(f"Context: {self.flow_tracker.context}")
        
    #     return "\n".join(context_parts)
    
    # def get_flow_summary(self) -> Dict[str, Any]:
    #     """Get summary of current flow state."""
    #     return {
    #         **self.flow_tracker.get_position_summary(),
    #         "objective": self.get_current_step_objective()
    #     }
        
    def get_system_prompt(self):
        system_prompt = f"""You are the Game Manager for a D&D combat encounter. Your role is to orchestrate combat flow and mechanical updates based on the combat arbiter script.

# COMBAT ARBITER SCRIPT
{self.combat_arbiter_script}

# YOUR RESPONSIBILITIES

1. **Game Flow Management**: Follow the combat arbiter script to determine current phase and step progression
2. **Step Objectives**: Provide clear objectives for the Dungeon Master to accomplish
3. **Mechanical Updates**: Perform necessary mechanical updates (advance steps, start/end turns, resolve actions)
4. **Context Retrieval**: Identify when rules or character state information is needed

# DECISION LOGIC

## When processing NEW PLAYER MESSAGES:
- Usually just identify relevant context retrieval tool calls
- Rarely advance steps unless the player message indicates completion of an objective

## When processing NEW DM MESSAGES (especially with step_complete_signal=True):
- The DM has accomplished the current step objective
- Perform mechanical updates based on the current step
- Advance to the next logical step according to the combat arbiter script
- Set new step objectives for the DM
- Identify any context retrieval needed for the new step

# TOOL USAGE

Use tools when mechanical updates are needed:
- `advance_step`: When progressing through combat flow
- `start_turn`: When beginning new turns/subturns
- `end_turn`: When concluding turns/subturns  
- `resolve_action`: When actions need state extraction
- `retrieve_rules`: When rule clarification is needed
- `retrieve_state`: When character information is needed

# OUTPUT FORMAT

Always provide structured responses with:
- Clear step objectives for the DM
- List of mechanical updates performed
- Context retrieval calls needed
- Whether step was advanced
- Whether DM action is required
- Notes explaining your reasoning

Focus on following the combat arbiter script precisely while making intelligent decisions about game flow progression."""
        return system_prompt

def create_game_manager(
    turn_manager: Optional[TurnManager] = None,
    vector_service: Optional[VectorService] = None,
    model_name: str = "gemini-2.0-flash-exp"
) -> GameManagerAgent:
    """
    Factory function to create a configured Game Manager Agent.
    
    Args:
        turn_manager: Turn manager for combat coordination
        vector_service: Vector service for rule lookups  
        model_name: Gemini model name to use
    
    Returns:
        Configured GameManagerAgent instance
    """
    return GameManagerAgent(
        turn_manager=turn_manager,
        vector_service=vector_service,
        model_name=model_name
    )