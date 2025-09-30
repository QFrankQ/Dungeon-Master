"""
Simple structured response class for DM agent.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# class ToolCall(BaseModel):
#     """Basic tool call structure."""
#     name: str = Field(..., description="Name of the tool/function to call")
#     parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool call")


class DMResponse(BaseModel):
    """
    Simple structured response from the DM agent.
    
    Contains the narrative response and optional basic tool calls.
    State extraction will be handled by a separate agent.
    """
    narrative: str = Field(..., description="The game narrative and your message to the active player(s)")
    # tool_calls: Optional[List[ToolCall]] = Field(None, description="Optional list of tool calls to execute")
    game_step_completed: bool = Field(..., description='''"True" only if current step objectives are met; "False" if step objectives are not met or you're asking the players for more information.''')
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "narrative": "You successfully cast the healing spell, feeling warmth flow through your wounds. The goblin falls unconscious from its wounds, ending the combat encounter.",
                    "game_step_completed": True
                },
                {
                    "narrative": "What would you like to do? You can attack, cast a spell, or try to negotiate.",
                    "game_step_completed": False
                }
            ]
        }