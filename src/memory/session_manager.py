"""
Session manager that integrates state management with the DM agent.
Coordinates between DM responses, state extraction, and state updates.
"""

from typing import Optional, Dict, Any, List
import asyncio



from ..models.dm_response import DungeonMasterResponse
from ..models.chat_message import ChatMessage
from ..agents.state_extraction_orchestrator import (
    StateExtractionOrchestrator,
    create_state_extraction_orchestrator
)
from .state_manager import StateManager, create_state_manager
from .session_tools import SessionToolRegistry, create_default_tool_registry
from .session_tools import StateExtractionTool
from .turn_manager import TurnManager, create_turn_manager
from .player_character_registry import PlayerCharacterRegistry, create_player_character_registry
from ..agents.gameflow_director import GameflowDirectorAgent
from ..models.turn_message import TurnMessage, MessageType
from ..models.gd_response import GameflowDirectorResponse
from ..context.gd_context_builder import GDContextBuilder
from ..context.dm_context_builder import DMContextBuilder
from ..context.state_extractor_context_builder import StateExtractorContextBuilder
from ..models.state_updates import StateExtractionResult

# Forward reference to avoid circular import - will import in factory function
from typing import TYPE_CHECKING

from models import dm_response
if TYPE_CHECKING:
    from ..agents.dungeon_master import DungeonMasterAgent


class SessionManager:
    """
    Manages a D&D session with integrated state management.
    
    Coordinates between:
    - DM agent responses (DungeonMasterResponse)  
    - State extraction (StateExtractorAgent)
    - State updates (StateManager)
    - Tool execution for extensible session operations
    """
    
    def __init__(
        self,
        gameflow_director_agent: Optional[GameflowDirectorAgent] = None,
        dungeon_master_agent: Optional[DungeonMasterAgent] = None,
        state_extraction_orchestrator: Optional[StateExtractionOrchestrator] = None,
        state_manager: Optional[StateManager] = None,
        enable_state_management: bool = True,
        tool_registry: Optional[SessionToolRegistry] = None,
        turn_manager: Optional[TurnManager] = None,
        enable_turn_management: bool = False,
        player_character_registry: Optional[PlayerCharacterRegistry] = None
    ):
        """
        Initialize session manager.
        
        Args:
            dungeon_master_agent: The DM agent for generating responses
            state_extractor: Agent for extracting state changes from narratives
            state_manager: Manager for applying state updates
            enable_state_management: Whether to enable automatic state management
            tool_registry: Registry for session tools (created with defaults if None)
            turn_manager: Manager for turn tracking and context isolation
            enable_turn_management: Whether to enable turn-aware processing
        """
        self.enable_state_management = enable_state_management
        self.enable_turn_management = enable_turn_management
        
        # Store the GD agent
        self.gameflow_director_agent: GameflowDirectorAgent = gameflow_director_agent
        # Store the DM agent 
        self.dungeon_master_agent: DungeonMasterAgent = dungeon_master_agent
        
        # Initialize components
        self.state_extraction_orchestrator = (
            state_extraction_orchestrator or create_state_extraction_orchestrator()
        )
        self.state_manager = state_manager or create_state_manager()

        # Initialize turn manager (optional)
        self.turn_manager = turn_manager
        if enable_turn_management and not turn_manager:
            self.turn_manager = create_turn_manager()
        
        # Initialize player character registry
        self.player_character_registry: PlayerCharacterRegistry = player_character_registry or create_player_character_registry()
        
        # Initialize tool registry
        self.tool_registry = tool_registry or create_default_tool_registry()

        # Initialize context builders
        self.gd_context_builder = GDContextBuilder()
        self.dm_context_builder = DMContextBuilder()
        self.state_extractor_context_builder = StateExtractorContextBuilder

        # Register default tools if components are available
        if self.state_extraction_orchestrator and self.state_manager:
            state_tool = StateExtractionTool(self.state_extraction_orchestrator, self.state_manager)
            self.tool_registry.register_tool(state_tool)
        
        # Session state
        self.session_context: Dict[str, Any] = {}
        self.recent_narratives: list = []
        
    async def process_player_input(
        self,
        new_messages: List[ChatMessage],
        message_history: Optional[List] = None,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process user input through the DM agent and handle state management.
        This is the primary interface for session interaction.
        
        Args:
            user_input: User's message/input
            message_history: Optional message history for the agent
            session_context: Current session context (characters, combat state, etc.)
        
        Returns:
            Dictionary with agent response and processing results
        """
        if not self.dungeon_master_agent:
            raise ValueError("No DungeonMasterAgent configured. Use create_session_manager() factory function.")
        
        #     # === PHASE 1: INPUT PROCESSING ===
        #   1. Extract character info from player_message
        #   2. Add player_message to current turn context
        #   3. Get turn_manager_snapshot

        #   # === PHASE 2: DM PROCESSING (DEFAULT PATH) ===
        #   4. Build DM context including:
        #      - Current step objective (if any)
        #      - Turn history and state
        #      - Character information
        #      - Player message

        #   5. Run DM agent within current step objective
        #   6. Get DM response

        #   # === PHASE 3: CHECK FOR STEP COMPLETION ===
        #   7. IF DM signals step completion:
        #       # GD ACTIVATION (ONLY WHEN STEP COMPLETE)
        #       8. Build GD context from turn_manager_snapshot
        #       9. Run GD with step completion signal
        #       10. Process GD response:
        #           - Set NEW step objective
        #           - Manage turn boundaries (start/end turns)
        #           - Handle reaction queues
        #           - Advance combat script position

        #       # CONTINUE DM PROCESSING WITH NEW OBJECTIVE
        #       11. Build NEW DM context with updated step objective
        #       12. Run DM agent again with new step objective
        #       13. Get DM response for new step

        #   # === PHASE 4: RESPONSE COMPILATION ===
        #   14. Process final DM response:
        #       - Extract state changes
        #       - Update game state
        #       - Execute tools

        #   15. Compile and return response to player
        
        
        #     # === PHASE 1: INPUT PROCESSING ===
        #   1. Extract character info from player_message
        #   2. Hold on to the new messages until end of agent runs

        # Create chronological list of message entries for each input message
        # Using a new message holder instead of adding new messages to TurnManager directly
        # makes it easier to handle simultaneous player message
        new_messages_holder = []
        for player_message in new_messages:
            character_name = self.player_character_registry.get_character_id_by_player_id(player_message.character_id)
            message_entry = {
                'player_message': player_message,
                'player_id': player_message.character_id,
                'character_id': character_name
            }
            new_messages_holder.append(message_entry)
        
        
        #   3. Get turn_manager_snapshot
        turn_manager_snapshot = self.turn_manager.get_snapshot()
        
        #   # === PHASE 2: DM PROCESSING (DEFAULT PATH) ===
        #   4. Build DM context including:
        #      - Current step objective (if any)
        #      - Turn history and state
        #      - Character information
        #      - Player message
        dungeon_master_context = self.dm_context_builder.build_context(turn_manager_snapshots=turn_manager_snapshot, new_message_entries=new_messages_holder)

        #   5. Run DM agent and get DM response
        dungeon_master_response: DungeonMasterResponse = self.dungeon_master_agent.process_message(dungeon_master_context) 
        
        #   # === PHASE 3: PROCESS DM RESPONSE ===
        
        #   DM narrative to response queue
        response_queue: List[str] = []
        response_queue.append(dungeon_master_response.narrative)
        
        #   Add DM narrative to new_message_holder
        dungeon_master_narrative_entry = {
                        'player_message': dungeon_master_response.narrative,
                        'player_id': None,
                        'character_id': "DM"
                    }
        new_messages_holder.append(dungeon_master_narrative_entry) 

        #   # === PHASE 4: CHECK FOR STEP COMPLETION ===
        if not dungeon_master_response.game_step_completed:
            #   ==== ADD NEW MESSAGES TO TURN STACK ====
            #   Add new player messages & DM narrative to current Turn in TurnManager
            for message_entry in new_messages_holder:
                message, speaker = message_entry["player_message"], message_entry["character_id"]
                self.turn_manager.add_new_message(new_message=message, speaker=speaker)
            #   =========================================
        else:
            #   7. WHILE DM signals step completion:
            while dungeon_master_response.game_step_completed:   
                #   Add DM narrative to new_messages_holder for GD context
                # GD ACTIVATION (ONLY WHEN STEP COMPLETE)
                # 8. Build GD context from new turn_manager_snapshot
                turn_manager_snapshot = self.turn_manager.get_snapshot()
                gameflow_director_context = self.gd_context_builder.build_context(turn_manager_snapshots=turn_manager_snapshot, new_message_entries=new_messages_holder)
                
                #   ==== ADD NEW MESSAGES TO TURN STACK ====
                #   Add new player messages & DM narrative to current Turn in TurnManager
                #   AFTER GD obtains snapshot for building context but 
                #   BEFORE GD starts/ends turns
                for message_entry in new_messages_holder:
                    message, speaker = message_entry["player_message"], message_entry["character_id"]
                    self.turn_manager.add_new_message(new_message=message, speaker=speaker)
                #   =========================================
                
                # 9. Run GD with step completion signal
                gameflow_director_response:GameflowDirectorResponse = self.gameflow_director_agent.process_message(gameflow_director_context)
                
                # 10. Process GD response:
                #     - Advance combat script position by Set NEW step objective
                #     - UPDATE game state if required
                self.turn_manager.set_next_step_objective(gameflow_director_response.next_game_step_objectives)
                if gameflow_director_response.game_state_updates_required:
                    #TODO: build relevant context
                    current_TurnContext_snapshot = self.turn_manager.get_snapshot().turn_stack[-1][0]
                    state_extractor_context = self.state_extractor_context_builder.build_context(
                        current_turn=current_TurnContext_snapshot,
                    )
                    # Use orchestrator instead of single extractor
                    state_changes: StateExtractionResult = await self.state_extraction_orchestrator.extract_state_changes(
                        formatted_turn_context=state_extractor_context,
                        # TODO: game_context TBD
                        game_context={
                            "turn_id": current_TurnContext_snapshot.turn_id,
                            "turn_level": current_TurnContext_snapshot.turn_level,
                            "active_character": current_TurnContext_snapshot.active_character
                        }
                    )
                    
                

                # # CONTINUE DM PROCESSING WITH NEW OBJECTIVE
                # 11. Build NEW DM context with updated step objective
                # 12. Run DM agent again with new step objective
                # 13. Get DM response for new step

        
        
        

        return response_queue
    
    def process_user_input_sync(
        self,
        player_message: ChatMessage,
        message_history: Optional[List] = None,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Synchronous version of process_user_input."""
        return asyncio.run(self.process_user_input(player_message, message_history, session_context))
        
    def process_gd_response(self, gd_response: GameflowDirectorResponse):
        #TODO: be careful of the order of post-run function calls.
        pass
        
        
    async def process_dm_response(
        self, 
        dm_response: DungeonMasterResponse,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a DM response with automatic state management.
        
        Args:
            dm_response: Response from the DM agent
            session_context: Current session context (characters, combat state, etc.)
        
        Returns:
            Dictionary with processing results including state updates
        """
        results = {
            "narrative": dm_response.narrative,
            "tool_calls": dm_response.tool_calls or [],
            "state_extraction": None,
            "state_updates": None,
            "errors": []
        }
        
        # Update session context
        if session_context:
            self.session_context.update(session_context)
        
        # Store narrative for context
        #TODO: include user narrative as well
        self.recent_narratives.append(dm_response.narrative)
        if len(self.recent_narratives) > 10:  # Keep last 10 narratives
            self.recent_narratives.pop(0)
        

        
        return results
    
    async def _execute_tool_calls(
        self,
        tool_calls: List[str],
        dm_response: DungeonMasterResponse,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute tools based on tool calls from DM response.
        
        Args:
            tool_calls: List of tool names to execute
            dm_response: DM response containing the tool calls
            session_context: Current session context
            
        Returns:
            Dictionary with tool execution results
        """
        if not session_context:
            session_context = self.session_context
            
        return await self.tool_registry.execute_tools(
            tool_calls, dm_response, session_context
        )
    
    def process_dm_response_sync(
        self,
        dm_response: DungeonMasterResponse,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Synchronous version of process_dm_response.
        """
        return asyncio.run(self.process_dm_response(dm_response, session_context))
    
    def get_character(self, character_id: str):
        """Get a character by ID."""
        return self.state_manager.get_character(character_id)

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        return {
            "narratives_processed": len(self.recent_narratives),
            "state_management_enabled": self.enable_state_management,
            "state_manager_stats": self.state_manager.get_update_stats(),
            "session_context_keys": list(self.session_context.keys())
        }
    
    def update_session_context(self, context: Dict[str, Any]) -> None:
        """Update the session context."""
        self.session_context.update(context)
    
    def clear_session_context(self) -> None:
        """Clear the session context."""
        self.session_context.clear()
        self.recent_narratives.clear()
    
    def set_state_management_enabled(self, enabled: bool) -> None:
        """Enable or disable state management."""
        self.enable_state_management = enabled
    
    def register_tool(self, tool) -> None:
        """Register a new tool in the tool registry."""
        self.tool_registry.register_tool(tool)
    
    def list_available_tools(self) -> List[str]:
        """List all available tools in the registry."""
        return self.tool_registry.list_tools()
    
    async def execute_tool_manually(
        self,
        tool_name: str,
        dm_response: DungeonMasterResponse,
        session_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Manually execute a specific tool."""
        if not session_context:
            session_context = self.session_context
            
        return await self.tool_registry.execute_tool(
            tool_name, dm_response, session_context, **kwargs
        )
    
    # Turn Management Methods
    
    def get_turn_context(self) -> Optional[Dict[str, Any]]:
        """Get information about the current turn context."""
        if not self.enable_turn_management or not self.turn_manager:
            return None
        
        current_turn = self.turn_manager.get_current_turn_context()
        if not current_turn:
            return None
        
        return {
            "turn_id": current_turn.turn_id,
            "turn_level": current_turn.turn_level,
            "active_character": current_turn.active_character,
            "message_count": len(current_turn.messages),
            "turn_stats": self.turn_manager.get_turn_stats(),
            "turn_stack": self.turn_manager.get_turn_stack_summary()
        }
    
    def is_in_turn(self) -> bool:
        """Check if currently in a turn."""
        if not self.enable_turn_management or not self.turn_manager:
            return False
        return self.turn_manager.is_in_turn()


def create_session_manager(
    enable_state_management: bool = True,
    character_data_path: str = "src/characters/",
    tool_registry: Optional[SessionToolRegistry] = None,
    agent_instructions: Optional[str] = None,
    use_structured_output: bool = True,
    dungeon_master_agent: Optional["DungeonMasterAgent"] = None,
    enable_turn_management: bool = False,
    turn_manager: Optional[TurnManager] = None
) -> SessionManager:
    """
    Factory function to create a configured session manager with DM agent.
    
    Args:
        enable_state_management: Whether to enable automatic state management
        character_data_path: Path to character data files  
        tool_registry: Custom tool registry (creates default if None)
        agent_instructions: Custom instructions for the DM agent
        use_structured_output: Enable structured output for the DM agent
        dungeon_master_agent: Existing agent to use (creates new one if None)
        enable_turn_management: Whether to enable turn tracking and context isolation
        turn_manager: Existing turn manager to use (creates new one if None and enabled)
    
    Returns:
        Configured SessionManager instance with DM agent
    """
    # Import here to avoid circular imports
    from ..agents.agents import create_dungeon_master_agent
    
    # Create or use provided DM agent
    if dungeon_master_agent is None:
        dungeon_master_agent = create_dungeon_master_agent(
            instructions=agent_instructions,
            use_structured_output=use_structured_output
        )
    
    # Create other components
    state_extractor = create_state_extractor_agent()
    state_manager = create_state_manager(character_data_path)
    
    return SessionManager(
        dungeon_master_agent=dungeon_master_agent,
        state_extractor=state_extractor,
        state_manager=state_manager,
        enable_state_management=enable_state_management,
        tool_registry=tool_registry,
        turn_manager=turn_manager,
        enable_turn_management=enable_turn_management
    )