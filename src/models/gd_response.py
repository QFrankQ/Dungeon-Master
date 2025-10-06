from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal, Union

# class RetrieveRules(BaseModel):
#     function_name: Literal["retrieve_rules"] = "retrieve_rules"
#     queries: List[str] = Field(..., description="Rule queries to search for in descending order of relevance")
#     #TODO: Limit the number of Rules

# class RetrieveState(BaseModel):
#     function_name: Literal["retrieve_state"] = "retrieve_state"
#     #TODO: change schema
#     character_ids: List[str] = Field(..., description="Character IDs to retrieve")
#     fields: Optional[List[str]] = Field(None, description="Specific fields to retrieve")

# class StartTurn(BaseModel):
#     function_name: Literal["start_turn"] = "start_turn"
#     active_character: str = Field(..., description="Character whose turn it is")
#     initiative: Optional[List[str]]
    # turn_type: Optional[str] = Field("combat", description="Type of turn")
    # metadata: Optional[Dict[str, Any]] = Field(None, description="Turn metadata")

# class AdvanceStep(BaseModel):
#     function_name: Literal["advance_step"] = "advance_step"
#     new_objective: str = Field(..., description="New step objective")

class GameflowDirectorResponse(BaseModel):
    """Enhanced Gameflow Director response with structured function
calls."""

    # Boolean flags for parameterless functions
    # end_turn: bool = Field(False, description="End the current turn")
    game_state_updates_required: bool = Field(False, description='''"True" if DM resolves any action or effects in the current game step and theirs a change to the game state; otherwise "False"''')

    # Typed models for functions with parameters
    # retrieve_rules: Optional[RetrieveRules] = Field(None, description="Retrieve rules from knowledge base")
    # retrieve_state: Optional[RetrieveState] = Field(None, description="Retrieve character state")
    # start_turn: Optional[StartTurn] = Field(None, description="Start new turn")
    next_game_step_objectives: str = Field(None, description="The next step objective outlined in the combat flow")


# class Config:
#     json_schema_extra = {
#         "examples": [
#             {
#                 "step_objectives": "Roll initiative for all combat participants",
#                 "function_calls": [
#                     {
#                         "function_name": "retrieve_rules",
#                         "parameters": {"queries": ["initiative order", "dexterity bonus"]}
#                     },
#                     {
#                         "function_name": "advance_step",
#                         "parameters": {"new_objective": "Establish turn order"}
#                     }
#                 ],
#                 "step_advancement": True,
#                 "notes": "DM completed surprise check, advancing to initiative"
#             }
#         ]
#     }