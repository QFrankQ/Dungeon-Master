"""
Simple structured response class for DM agent.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Basic tool call structure."""
    name: str = Field(..., description="Name of the tool/function to call")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool call")


class DMResponse(BaseModel):
    """
    Simple structured response from the DM agent.
    
    Contains the narrative response and optional basic tool calls.
    State extraction will be handled by a separate agent.
    """
    narrative: str = Field(..., description="The main narrative response for the user")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="Optional list of tool calls to execute")
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "narrative": "The goblin swings its scimitar at you! *rolls dice* That's a 15 to hit. The blade slashes across your arm for 6 slashing damage.",
                    "tool_calls": [
                        {
                            "name": "roll_dice",
                            "parameters": {"sides": 20, "count": 1, "modifier": 3}
                        }
                    ]
                },
                {
                    "narrative": "You successfully cast the healing spell, feeling warmth flow through your wounds.",
                    "tool_calls": None
                }
            ]
        }