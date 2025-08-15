"""
Session tools for executing various session management tasks.
Provides a modular tool system for handling different types of session operations.
"""

from typing import Dict, Any, Optional, Protocol, List
from abc import ABC, abstractmethod
import asyncio

from ..agents.dm_response import DMResponse
from ..agents.state_extractor import StateExtractorAgent
from .state_manager import StateManager


class SessionTool(Protocol):
    """Protocol for session tools that can be executed by the session manager."""
    
    @property
    def name(self) -> str:
        """Tool name identifier."""
        ...
    
    async def execute(
        self, 
        dm_response: DMResponse,
        session_context: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the tool with the given parameters.
        
        Args:
            dm_response: The DM response to process
            session_context: Current session context
            **kwargs: Additional tool-specific parameters
            
        Returns:
            Dictionary with execution results
        """
        ...


class StateExtractionTool:
    """Tool for extracting and applying state changes from DM narratives."""
    
    def __init__(
        self, 
        state_extractor: StateExtractorAgent,
        state_manager: StateManager
    ):
        self.state_extractor = state_extractor
        self.state_manager = state_manager
    
    @property
    def name(self) -> str:
        return "state_extraction"
    
    async def execute(
        self,
        dm_response: DMResponse,
        session_context: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract state changes from narrative and apply them.
        
        Returns:
            Dictionary with extraction and update results
        """
        results = {
            "tool_name": self.name,
            "state_extraction": None,
            "state_updates": None,
            "errors": []
        }
        
        try:
            # Extract state changes from the narrative
            extraction_result = await self.state_extractor.extract_state_changes(
                dm_response.narrative,
                context=session_context
            )
            
            results["state_extraction"] = {
                "character_updates": len(extraction_result.character_updates),
                "new_characters": len(extraction_result.new_characters),
                "confidence": extraction_result.confidence,
                "notes": extraction_result.notes
            }
            
            # Apply state updates if any were found
            if extraction_result.character_updates or extraction_result.new_characters:
                update_results = self.state_manager.apply_state_updates(extraction_result)
                results["state_updates"] = update_results
                
                # Collect any state update errors
                if update_results.get("errors"):
                    results["errors"].extend(update_results["errors"])
            
        except Exception as e:
            error_msg = f"State extraction tool error: {str(e)}"
            results["errors"].append(error_msg)
        
        return results


class SessionToolRegistry:
    """Registry for managing and executing session tools."""
    
    def __init__(self):
        self.tools: Dict[str, SessionTool] = {}
    
    def register_tool(self, tool: SessionTool) -> None:
        """Register a tool in the registry."""
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[SessionTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self.tools.keys())
    
    async def execute_tool(
        self,
        tool_name: str,
        dm_response: DMResponse,
        session_context: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            dm_response: DM response to process
            session_context: Current session context
            **kwargs: Additional tool-specific parameters
            
        Returns:
            Dictionary with execution results
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "tool_name": tool_name,
                "errors": [f"Tool '{tool_name}' not found in registry"]
            }
        
        return await tool.execute(dm_response, session_context, **kwargs)
    
    async def execute_tools(
        self,
        tool_names: List[str],
        dm_response: DMResponse,
        session_context: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute multiple tools in sequence.
        
        Args:
            tool_names: List of tool names to execute
            dm_response: DM response to process
            session_context: Current session context
            **kwargs: Additional tool-specific parameters
            
        Returns:
            Dictionary with all execution results
        """
        results = {
            "tools_executed": [],
            "errors": []
        }
        
        for tool_name in tool_names:
            try:
                tool_result = await self.execute_tool(
                    tool_name, dm_response, session_context, **kwargs
                )
                results["tools_executed"].append(tool_result)
                
                # Collect errors from individual tools
                if tool_result.get("errors"):
                    results["errors"].extend(tool_result["errors"])
                    
            except Exception as e:
                error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                results["errors"].append(error_msg)
        
        return results


def create_default_tool_registry() -> SessionToolRegistry:
    """
    Create an empty tool registry for users to populate.
    
    Returns:
        Empty SessionToolRegistry instance
    """
    return SessionToolRegistry()