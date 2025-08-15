"""
Session manager that integrates state management with the DM agent.
Coordinates between DM responses, state extraction, and state updates.
"""

from typing import Optional, Dict, Any, List
import asyncio

from ..agents.dm_response import DMResponse
from ..agents.state_extractor import StateExtractorAgent, create_state_extractor_agent
from .state_manager import StateManager, create_state_manager
from .session_tools import SessionToolRegistry, create_default_tool_registry
from .session_tools import StateExtractionTool


class SessionManager:
    """
    Manages a D&D session with integrated state management.
    
    Coordinates between:
    - DM agent responses (DMResponse)  
    - State extraction (StateExtractorAgent)
    - State updates (StateManager)
    - Tool execution for extensible session operations
    """
    
    def __init__(
        self,
        state_extractor: Optional[StateExtractorAgent] = None,
        state_manager: Optional[StateManager] = None,
        enable_state_management: bool = True,
        tool_registry: Optional[SessionToolRegistry] = None
    ):
        """
        Initialize session manager.
        
        Args:
            state_extractor: Agent for extracting state changes from narratives
            state_manager: Manager for applying state updates
            enable_state_management: Whether to enable automatic state management
            tool_registry: Registry for session tools (created with defaults if None)
        """
        self.enable_state_management = enable_state_management
        
        # Initialize components
        self.state_extractor = state_extractor or create_state_extractor_agent()
        self.state_manager = state_manager or create_state_manager()
        
        # Initialize tool registry
        self.tool_registry = tool_registry or create_default_tool_registry()
        
        # Register default tools if components are available
        if self.state_extractor and self.state_manager:
            state_tool = StateExtractionTool(self.state_extractor, self.state_manager)
            self.tool_registry.register_tool(state_tool)
        
        # Session state
        self.session_context: Dict[str, Any] = {}
        self.recent_narratives: list = []
        
    async def process_dm_response(
        self, 
        dm_response: DMResponse,
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
        
        # Execute tools based on DM response tool calls
        if dm_response.tool_calls and self.enable_state_management:
            tool_results = await self._execute_tool_calls(
                dm_response.tool_calls, dm_response, session_context
            )
            
            # Merge tool results into main results
            if tool_results.get("tools_executed"):
                results["tool_executions"] = tool_results["tools_executed"]
            
            if tool_results.get("errors"):
                results["errors"].extend(tool_results["errors"])
        
        return results
    
    async def _execute_tool_calls(
        self,
        tool_calls: List[str],
        dm_response: DMResponse,
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
        dm_response: DMResponse,
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
        dm_response: DMResponse,
        session_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Manually execute a specific tool."""
        if not session_context:
            session_context = self.session_context
            
        return await self.tool_registry.execute_tool(
            tool_name, dm_response, session_context, **kwargs
        )


def create_session_manager(
    enable_state_management: bool = True,
    character_data_path: str = "src/characters/",
    tool_registry: Optional[SessionToolRegistry] = None
) -> SessionManager:
    """
    Factory function to create a configured session manager.
    
    Args:
        enable_state_management: Whether to enable automatic state management
        character_data_path: Path to character data files
        tool_registry: Custom tool registry (creates default if None)
    
    Returns:
        Configured SessionManager instance
    """
    state_extractor = create_state_extractor_agent()
    state_manager = create_state_manager(character_data_path)
    
    return SessionManager(
        state_extractor=state_extractor,
        state_manager=state_manager,
        enable_state_management=enable_state_management,
        tool_registry=tool_registry
    )